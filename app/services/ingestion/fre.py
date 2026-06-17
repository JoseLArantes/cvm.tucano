from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from sqlalchemy import and_, insert, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.fre import (
    FreAcaoEntregue,
    FreAdministradorDeclaracaoGenero,
    FreAdministradorDeclaracaoRaca,
    FreAdministradorMembroConselhoFiscal,
    FreAdministradorPcd,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialAumento,
    FreCapitalSocialAumentoClasseAcao,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialDesdobramento,
    FreCapitalSocialDesdobramentoClasseAcao,
    FreCapitalSocialReducao,
    FreCapitalSocialReducaoClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDireitoAcao,
    FreDistribuicaoCapital,
    FreDistribuicaoCapitalClasseAcao,
    FreDocumento,
    FreEmpregadoLocalDeclaracaoGenero,
    FreEmpregadoLocalDeclaracaoRaca,
    FreEmpregadoLocalFaixaEtaria,
    FreEmpregadoPcd,
    FreEmpregadoPosicaoDeclaracaoRaca,
    FreEmpregadoPosicaoFaixaEtaria,
    FreEmpregadoPosicaoGenero,
    FreEmpregadoPosicaoLocal,
    FreMembroComite,
    FreMercadoEstrangeiro,
    FreOutroValorMobiliario,
    FreParticipacaoSociedade,
    FrePlanoRecompra,
    FrePlanoRecompraClasseAcao,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreRelacaoFamiliar,
    FreRelacaoSubordinacao,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
    FreTitularValorMobiliario,
    FreTituloExterior,
    FreTransacaoParteRelacionada,
    FreValorMobiliarioTesourariaMovimentacao,
    FreValorMobiliarioTesourariaUltimoExercicio,
    FreVolumeValorMobiliario,
)
from app.models.ingestion import IngestionRow
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.ingestion.acquisition import annotate_probe_with_sha_confirmation, probe_remote_source
from app.services.ingestion.change_tracking import reconcile_promoted_rows
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.dependencies import ensure_identity_graph_ready
from app.services.ingestion.engine import ZipIngestionSpec, process_zip_members
from app.services.ingestion.lifecycle import build_custom_remote_probe, upsert_artifact_snapshot
from app.services.ingestion.normalizers import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_cnpj_opcional,
    normalizar_data,
    normalizar_decimal_cvm,
    normalizar_inteiro,
    normalizar_sigla_uf,
    normalizar_texto,
)
from app.services.ingestion.quality import enforce_quality_gate
from app.services.ingestion.quarantine import create_quarantine_item
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    limpar_caches_resolver,
    persist_resolution_result,
    register_document_header,
    resolve_companhia,
)
from app.services.ingestion.source_registry import listar_datasets
from app.services.ingestion.sql_batches import iter_lookup_batches, iter_parameter_batches, mapping_parameter_width
from app.services.ingestion.staging import (
    create_run,
    iter_staged_member_chunks,
    iter_zip_csv_members,
    register_file,
    safe_promote_chunk,
    update_run_state,
)
from app.services.ingestion.summary import build_contadores_quality_summary, build_quality_summary
from app.services.ingestion.validation import (
    build_natural_key,
    classify_duplicate,
    invalid_result,
    update_member_schema_validation,
    validate_member_header,
    write_validation_result,
)
from app.services.sincronizacao_fre import (
    _agora,
    _digitos,
    _equivalente,
    _normalizar_booleano,
    _registrar_quarentena,
)

_BATCH_COMMIT_LINHAS = 5000


def map_fre_members(ano: int) -> tuple[dict[str, str], set[str], set[str]]:
    datasets = listar_datasets("fre")
    row_kind_map = {
        item.render_member_name(ano=ano): item.row_kind or "" for item in datasets if item.row_kind is not None
    }
    required = {item.render_member_name(ano=ano) for item in datasets}
    optional = {item.render_member_name(ano=ano) for item in datasets if not item.obrigatorio}
    return row_kind_map, required, optional


def _download(url: str, *, timeout: float) -> bytes:
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def normalizar_fre_row(
    *,
    tipo: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    linha: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if tipo == "documentos":
        data_referencia = normalizar_data(linha.get("DT_REFER"))
        versao = normalizar_inteiro(linha.get("VERSAO"))
        id_documento = normalizar_inteiro(linha.get("ID_DOC"))
        if data_referencia is None or versao is None or id_documento is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_documento",
            {
                "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
                "codigo_cvm": normalizar_inteiro(linha.get("CD_CVM")),
                "data_referencia": data_referencia,
                "versao": versao,
                "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
                "categoria_documento": normalizar_texto(linha.get("CATEG_DOC")),
                "id_documento": id_documento,
                "data_recebimento": normalizar_data(linha.get("DT_RECEB")),
                "link_documento": normalizar_texto(linha.get("LINK_DOC")),
                "arquivo_origem": arquivo_origem,
                "ano_origem": ano_origem,
                "linha_origem": linha_origem,
            },
        )

    cnpj_companhia = normalizar_cnpj_opcional(linha.get("CNPJ_Companhia"))
    data_referencia = normalizar_data(linha.get("Data_Referencia"))
    versao = normalizar_inteiro(linha.get("Versao"))
    id_documento = normalizar_inteiro(linha.get("ID_Documento"))
    if data_referencia is None or versao is None or id_documento is None:
        raise ValueError("campo_obrigatorio_ausente")

    base = {
        "cnpj_companhia": cnpj_companhia,
        "data_referencia": data_referencia,
        "versao": versao,
        "id_documento": id_documento,
        "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }

    if tipo == "auditores":
        id_auditor = normalizar_inteiro(linha.get("ID_Auditor"))
        if id_auditor is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_auditor",
            base
            | {
                "id_auditor": id_auditor,
                "auditor": normalizar_texto(linha.get("Auditor")),
                "cpf_auditor": _digitos(linha.get("CPF_Auditor")),
                "cnpj_auditor": (
                    normalizar_cnpj(str(linha.get("CNPJ_Auditor")))
                    if normalizar_texto(linha.get("CNPJ_Auditor"))
                    else None
                ),
                "codigo_cvm_auditor": normalizar_texto(linha.get("Codigo_CVM_Auditor")),
                "tipo_origem_auditor": normalizar_texto(linha.get("Tipo_Origem_Auditor")),
                "data_inicio_contratacao": normalizar_data(linha.get("Data_Inicio_Contratacao")),
                "data_fim_contratacao": normalizar_data(linha.get("Data_Fim_Contratacao")),
                "data_inicio_prestacao_servico": normalizar_data(linha.get("Data_Inicio_Prestacao_Servico")),
                "servico_contratado": normalizar_texto(linha.get("Servico_Contratado")),
                "remuneracao_auditor": normalizar_texto(linha.get("Remuneracao_Auditor")),
                "justificativa_substituicao": normalizar_texto(linha.get("Justificativa_Substituicao")),
                "razao_apresentada": normalizar_texto(linha.get("Razao_Apresentada")),
            },
        )
    if tipo == "capital_social":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social",
            base
            | {
                "id_capital_social": id_capital_social,
                "tipo_capital": normalizar_texto(linha.get("Tipo_Capital")),
                "data_autorizacao_aprovacao": normalizar_data(linha.get("Data_Autorizacao_Aprovacao")),
                "valor_capital": normalizar_decimal_cvm(linha.get("Valor_Capital")),
                "prazo_integralizacao": normalizar_texto(linha.get("Prazo_Integralizacao")),
                "quantidade_acoes_ordinarias": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Ordinarias")),
                "quantidade_acoes_preferenciais": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Preferenciais")),
                "quantidade_total_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Total_Acoes")),
            },
        )
    if tipo == "posicao_acionaria":
        id_acionista = normalizar_inteiro(linha.get("ID_Acionista"))
        if id_acionista is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_posicao_acionaria",
            base
            | {
                "id_acionista": id_acionista,
                "acionista": normalizar_texto(linha.get("Acionista")),
                "tipo_pessoa_acionista": normalizar_texto(linha.get("Tipo_Pessoa_Acionista")),
                "cpf_cnpj_acionista": _digitos(linha.get("CPF_CNPJ_Acionista")),
                "id_acionista_relacionado": normalizar_inteiro(linha.get("ID_Acionista_Relacionado")),
                "acionista_relacionado": normalizar_texto(linha.get("Acionista_Relacionado")),
                "tipo_pessoa_acionista_relacionado": normalizar_texto(linha.get("Tipo_Pessoa_Acionista_Relacionado")),
                "cpf_cnpj_acionista_relacionado": _digitos(linha.get("CPF_CNPJ_Acionista_Relacionado")),
                "quantidade_acao_ordinaria_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acao_Ordinaria_Circulacao")
                ),
                "percentual_acao_ordinaria_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Acao_Ordinaria_Circulacao")
                ),
                "quantidade_acao_preferencial_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acao_Preferencial_Circulacao")
                ),
                "percentual_acao_preferencial_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Acao_Preferencial_Circulacao")
                ),
                "quantidade_total_acoes_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Total_Acoes_Circulacao")
                ),
                "percentual_total_acoes_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Total_Acoes_Circulacao")
                ),
                "nacionalidade": normalizar_texto(linha.get("Nacionalidade")),
                "sigla_uf": normalizar_sigla_uf(linha.get("Sigla_UF")),
                "residente_exterior": _normalizar_booleano(linha.get("Residente_Exterior")),
                "representante_legal": normalizar_texto(linha.get("Representante_Legal")),
                "tipo_pessoa_representante_legal": normalizar_texto(linha.get("Tipo_Pessoa_Representante_Legal")),
                "cpf_cnpj_representante_legal": _digitos(linha.get("CPF_CNPJ_Representante_legal")),
                "data_composicao_capital_social": normalizar_data(linha.get("Data_Composicao_Capital_Social")),
                "data_ultima_alteracao": normalizar_data(linha.get("Data_Ultima_Alteracao")),
                "acionista_controlador": _normalizar_booleano(linha.get("Acionista_Controlador")),
                "participante_acordo_acionistas": _normalizar_booleano(linha.get("Participante_Acordo_Acionistas")),
            },
        )
    if tipo == "remuneracao_total_orgao":
        return (
            "fre_remuneracao_total_orgao",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "total_remuneracao": normalizar_decimal_cvm(linha.get("Total_Remuneracao")),
                "orgao_administracao": normalizar_texto(linha.get("Orgao_Administracao")),
                "numero_membros": normalizar_inteiro(linha.get("Numero_Membros")),
                "total_remuneracao_orgao": normalizar_decimal_cvm(linha.get("Total_Remuneracao_Orgao")),
                "numero_membros_remunerados": normalizar_inteiro(linha.get("Numero_Membros_Remunerados")),
                "salario": normalizar_decimal_cvm(linha.get("Salario")),
                "beneficios_diretos_indiretos": normalizar_decimal_cvm(linha.get("Beneficios_Diretos_Indiretos")),
                "participacoes_comites": normalizar_decimal_cvm(linha.get("Participacoes_Comites")),
                "outros_valores_fixos": normalizar_decimal_cvm(linha.get("Outros_Valores_Fixos")),
                "descricao_outros_remuneracoes_fixas": normalizar_texto(
                    linha.get("Descricao_Outros_Remuneracoes_Fixas")
                ),
                "bonus": normalizar_decimal_cvm(linha.get("Bonus")),
                "participacao_resultados": normalizar_decimal_cvm(linha.get("Participacao_Resultados")),
                "participacao_reunioes": normalizar_decimal_cvm(linha.get("Participacao_Reunioes")),
                "outros_valores_variaveis": normalizar_decimal_cvm(linha.get("Outros_Valores_Variaveis")),
                "comissoes": normalizar_decimal_cvm(linha.get("Comissoes")),
                "descricao_outros_remuneracoes_variaveis": normalizar_texto(
                    linha.get("Descricao_Outros_Remuneracoes_Variaveis")
                ),
                "pos_emprego": normalizar_decimal_cvm(linha.get("Pos_emprego")),
                "cessacao_cargo": normalizar_decimal_cvm(linha.get("Cessacao_Cargo")),
                "baseada_acoes": normalizar_decimal_cvm(linha.get("Baseada_Acoes")),
                "observacao": normalizar_texto(linha.get("Observacao")),
            },
        )

    if tipo == "responsavel":
        nome_responsavel = normalizar_texto(linha.get("Nome_Responsavel"))
        cargo_responsavel = normalizar_texto(linha.get("Cargo_Responsavel"))
        if nome_responsavel is None or cargo_responsavel is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_responsavel",
            base
            | {
                "nome_responsavel": nome_responsavel,
                "cargo_responsavel": cargo_responsavel,
            },
        )
    if tipo == "capital_social_classe_acao":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_classe_acao",
            base
            | {
                "id_capital_social": id_capital_social,
                "tipo_classe_acao_preferencial": normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial")),
                "quantidade_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Acoes")),
            },
        )
    if tipo == "capital_social_titulo_conversivel":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_titulo_conversivel",
            base
            | {
                "id_capital_social": id_capital_social,
                "titulo_conversivel_acao": normalizar_texto(linha.get("Titulo_Conversivel_Acao")),
                "condicoes_conversao": normalizar_texto(linha.get("Condicoes_Conversao")),
            },
        )
    if tipo == "distribuicao_capital":
        return (
            "fre_distribuicao_capital",
            base
            | {
                "data_ultima_assembleia": normalizar_data(linha.get("Data_Ultima_Assembleia")),
                "quantidade_acoes_ordinarias_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acoes_Ordinarias_Circulacao")
                ),
                "percentual_acoes_ordinarias_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Acoes_Ordinarias_Circulacao")
                ),
                "quantidade_acoes_preferenciais_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acoes_Preferenciais_Circulacao")
                ),
                "percentual_acoes_preferenciais_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Acoes_Preferenciais_Circulacao")
                ),
                "quantidade_total_acoes_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Total_Acoes_Circulacao")
                ),
                "percentual_total_acoes_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Total_Acoes_Circulacao")
                ),
                "quantidade_acionistas_pf": normalizar_decimal_cvm(linha.get("Quantidade_Acionistas_PF")),
                "quantidade_acionistas_pj": normalizar_decimal_cvm(linha.get("Quantidade_Acionistas_PJ")),
                "quantidade_acionistas_investidores_institucionais": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acionistas_Investidores_Institucionais")
                ),
            },
        )
    if tipo == "distribuicao_capital_classe_acao":
        return (
            "fre_distribuicao_capital_classe_acao",
            base
            | {
                "classe_acoes_preferenciais": normalizar_texto(linha.get("Classe_Acoes_Preferenciais")),
                "sigla_classe_acoes_preferenciais": normalizar_texto(linha.get("Sigla_Classe_Acoes_Preferenciais")),
                "quantidade_acoes_preferenciais_circulacao": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acoes_Preferenciais_Circulacao")
                ),
                "percentual_acoes_preferenciais_circulacao": normalizar_decimal_cvm(
                    linha.get("Percentual_Acoes_Preferenciais_Circulacao")
                ),
            },
        )
    if tipo == "posicao_acionaria_classe_acao":
        id_acionista = normalizar_inteiro(linha.get("ID_Acionista"))
        if id_acionista is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_posicao_acionaria_classe_acao",
            base
            | {
                "id_acionista": id_acionista,
                "tipo_classe_acao_preferencial": normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial")),
                "quantidade_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Acoes")),
                "percentual_acoes": normalizar_decimal_cvm(linha.get("Percentual_Acoes")),
            },
        )
    if tipo == "remuneracao_maxima_minima_media":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_remuneracao_maxima_minima_media",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "orgao_administracao": orgao,
                "numero_membros": normalizar_decimal_cvm(linha.get("Numero_Membros")),
                "numero_membros_remunerados": normalizar_decimal_cvm(linha.get("Numero_Membros_Remunerados")),
                "valor_maior_remuneracao": normalizar_decimal_cvm(linha.get("Valor_Maior_Remuneracao")),
                "valor_medio_remuneracao": normalizar_decimal_cvm(linha.get("Valor_Medio_Remuneracao")),
                "valor_menor_remuneracao": normalizar_decimal_cvm(linha.get("Valor_Menor_Remuneracao")),
                "observacao": normalizar_texto(linha.get("Observacao")),
            },
        )
    if tipo == "remuneracao_variavel":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_remuneracao_variavel",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "orgao_administracao": orgao,
                "quantidade_total_membros": normalizar_decimal_cvm(linha.get("Quantidade_Total_Membros")),
                "quantidade_membros_remunerados": normalizar_decimal_cvm(linha.get("Quantidade_Membros_Remunerados")),
                "bonus_valor_minimo": normalizar_decimal_cvm(linha.get("Bonus_Valor_Minimo")),
                "bonus_valor_maximo": normalizar_decimal_cvm(linha.get("Bonus_Valor_Maximo")),
                "bonus_valor_metas_atingidas": normalizar_decimal_cvm(linha.get("Bonus_Valor_Metas_Atingidas")),
                "bonus_valor_efetivo": normalizar_decimal_cvm(linha.get("Bonus_Valor_Efetivo")),
                "participacao_valor_minimo": normalizar_decimal_cvm(linha.get("Participacao_Valor_Minimo")),
                "participacao_valor_maximo": normalizar_decimal_cvm(linha.get("Participacao_Valor_Maximo")),
                "participacao_valor_metas_atingidas": normalizar_decimal_cvm(
                    linha.get("Participacao_Valor_Metas_Atingidas")
                ),
                "participacao_valor_efetivo": normalizar_decimal_cvm(linha.get("Participacao_Valor_Efetivo")),
            },
        )
    if tipo == "remuneracao_acao":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_remuneracao_acao",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "orgao_administracao": orgao,
                "quantidade_total_membros": normalizar_decimal_cvm(linha.get("Quantidade_Total_Membros")),
                "quantidade_membros_remunerados": normalizar_decimal_cvm(linha.get("Quantidade_Membros_Remunerados")),
                "preco_medio_ponderado_opcoes_em_aberto": normalizar_decimal_cvm(
                    linha.get("Preco_Medio_Ponderado_Opcoes_Em_Aberto")
                ),
                "preco_medio_ponderado_opcoes_exercidas": normalizar_decimal_cvm(
                    linha.get("Preco_Medio_Ponderado_Opcoes_Exercidas")
                ),
                "preco_medio_ponderado_opcoes_perdidas": normalizar_decimal_cvm(
                    linha.get("Preco_Medio_Ponderado_Opcoes_Perdidas")
                ),
                "diluicao_potencial": normalizar_decimal_cvm(linha.get("Diluicao_Potencial")),
            },
        )
    if tipo == "acao_entregue":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_acao_entregue",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "orgao_administracao": orgao,
                "quantidade_total_membros": normalizar_decimal_cvm(linha.get("Quantidade_Total_Membros")),
                "quantidade_membros_remunerados": normalizar_decimal_cvm(linha.get("Quantidade_Membros_Remunerados")),
                "quantidade_acoes": normalizar_inteiro(linha.get("Quantidade_Acoes")),
                "preco_medio_ponderado_aquisicao": normalizar_decimal_cvm(linha.get("Preco_Medio_Ponderado_Aquisicao")),
                "preco_medio_ponderado_mercado": normalizar_decimal_cvm(linha.get("Preco_Medio_Ponderado_Mercado")),
                "valor_diferenca_aquisicao_mercado": normalizar_decimal_cvm(
                    linha.get("Valor_Diferenca_Aquisicao_Mercado")
                ),
            },
        )
    if tipo == "administrador_membro_conselho_fiscal":
        nome = normalizar_texto(linha.get("Nome"))
        if nome is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_administrador_membro_conselho_fiscal",
            base
            | {
                "orgao_administracao": normalizar_texto(linha.get("Orgao_Administracao")),
                "nome": nome,
                "cpf": _digitos(linha.get("CPF")),
                "profissao": normalizar_texto(linha.get("Profissao")),
                "cargo_eletivo_ocupado": normalizar_texto(linha.get("Cargo_Eletivo_Ocupado")),
                "complemento_cargo_eletivo_ocupado": normalizar_texto(linha.get("Complemento_Cargo_Eletivo_Ocupado")),
                "data_eleicao": normalizar_data(linha.get("Data_Eleicao")),
                "data_posse": normalizar_data(linha.get("Data_Posse")),
                "data_inicio_primeiro_mandato": normalizar_data(linha.get("Data_Inicio_Primeiro_Mandato")),
                "prazo_mandato": normalizar_texto(linha.get("Prazo_Mandato")),
                "eleito_controlador": normalizar_texto(linha.get("Eleito_Controlador")),
                "outro_cargo_funcao": normalizar_texto(linha.get("Outro_Cargo_Funcao")),
                "experiencia_profissional": normalizar_texto(linha.get("Experiencia_Profissional")),
                "data_nascimento": normalizar_data(linha.get("Data_Nascimento")),
                "numero_mandatos_consecutivos": normalizar_inteiro(linha.get("Numero_Mandatos_Consecutivos")),
                "percentual_participacao_reunioes": normalizar_decimal_cvm(linha.get("Percentual_Participacao_Reunioes")),
            },
        )
    if tipo == "membro_comite":
        nome = normalizar_texto(linha.get("Nome"))
        if nome is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_membro_comite",
            base
            | {
                "nome": nome,
                "cpf": _digitos(linha.get("CPF")),
                "profissao": normalizar_texto(linha.get("Profissao")),
                "tipo_comite": normalizar_texto(linha.get("Tipo_Comite")),
                "descricao_outros_comites": normalizar_texto(linha.get("Descricao_Outros_Comites")),
                "cargo_ocupado": normalizar_texto(linha.get("Cargo_Ocupado")),
                "descricao_outro_cargo_ocupado": normalizar_texto(linha.get("Descricao_Outro_Cargo_Ocupado")),
                "data_eleicao": normalizar_data(linha.get("Data_Eleicao")),
                "data_posse": normalizar_data(linha.get("Data_Posse")),
                "data_inicio_primeiro_mandato": normalizar_data(linha.get("Data_Inicio_Primeiro_Mandato")),
                "prazo_mandato": normalizar_texto(linha.get("Prazo_Mandato")),
                "outro_cargo_funcao": normalizar_texto(linha.get("Outro_Cargo_Funcao")),
                "experiencia_profissional": normalizar_texto(linha.get("Experiencia_Profissional")),
                "data_nascimento": normalizar_data(linha.get("Data_Nascimento")),
                "numero_mandatos_consecutivos": normalizar_inteiro(linha.get("Numero_Mandatos_Consecutivos")),
                "percentual_participacao_reunioes": normalizar_decimal_cvm(linha.get("Percentual_Participacao_Reunioes")),
            },
        )
    if tipo == "relacao_familiar":
        nome_admin = normalizar_texto(linha.get("Nome_Administrador"))
        nome_rel = normalizar_texto(linha.get("Nome_Pessoa_Relacionada"))
        if nome_admin is None or nome_rel is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_relacao_familiar",
            base
            | {
                "nome_administrador": nome_admin,
                "cpf_administrador": _digitos(linha.get("CPF_Administrador")),
                "nome_emissor": normalizar_texto(linha.get("Nome_Emissor")),
                "cnpj_emissor": normalizar_cnpj_opcional(linha.get("CNPJ_Emissor")),
                "cargo_administrador": normalizar_texto(linha.get("Cargo_Administrador")),
                "nome_pessoa_relacionada": nome_rel,
                "cpf_pessoa_relacionada": _digitos(linha.get("CPF_Pessoa_Relacionada")),
                "nome_emissor_pessoa_relacionada": normalizar_texto(linha.get("Nome_Emissor_Pessoa_Relacionada")),
                "cnpj_emissor_pessoa_relacionada": normalizar_cnpj_opcional(linha.get("CNPJ_Emissor_Pessoa_Relacionada")),
                "cargo_Pessoa_relacionada": normalizar_texto(linha.get("Cargo_Pessoa_Relacionada")),
                "tipo_parentesco": normalizar_texto(linha.get("Tipo_Parentesco")),
                "observacao": normalizar_texto(linha.get("Observacao")),
            },
        )
    if tipo == "participacao_sociedade":
        id_sociedade = normalizar_inteiro(linha.get("ID_Sociedade"))
        if id_sociedade is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_participacao_sociedade",
            base
            | {
                "id_sociedade": id_sociedade,
                "razao_social": normalizar_texto(linha.get("Razao_Social")),
                "cnpj": normalizar_cnpj_opcional(linha.get("CNPJ")),
                "tipo_sociedade": normalizar_texto(linha.get("Tipo_Sociedade")),
                "descricao_atividades": normalizar_texto(linha.get("Descricao_Atividades")),
                "pais_sede": normalizar_texto(linha.get("Pais_Sede")),
                "uf_sede": normalizar_sigla_uf(linha.get("UF_Sede")),
                "municipio_sede": normalizar_texto(linha.get("Municipio_Sede")),
                "participacao_emissor": normalizar_decimal_cvm(linha.get("Participacao_Emissor")),
                "possui_registro_cvm": _normalizar_booleano(linha.get("Possui_Registro_CVM")),
                "codigo_cvm": normalizar_inteiro(linha.get("Codigo_CVM")),
                "razao_aquisicao_manutencao": normalizar_texto(linha.get("Razao_Aquisicao_Manutencao")),
                "data_valor_mercado": normalizar_data(linha.get("Data_Valor_Mercado")),
                "data_valor_contabil": normalizar_data(linha.get("Data_Valor_Contabil")),
                "valor_mercado": normalizar_decimal_cvm(linha.get("Valor_Mercado")),
                "valor_contabil": normalizar_decimal_cvm(linha.get("Valor_Contabil")),
            },
        )
    if tipo == "relacao_subordinacao":
        nome_admin = normalizar_texto(linha.get("Nome_Administrador"))
        nome_rel = normalizar_texto(linha.get("Nome_Pessoa_Relacionada"))
        if nome_admin is None or nome_rel is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_relacao_subordinacao",
            base
            | {
                "data_inicio_exercicio_social": normalizar_data(linha.get("Data_Inicio_Exercicio_Social")),
                "data_fim_exercicio_social": normalizar_data(linha.get("Data_Fim_Exercicio_Social")),
                "nome_administrador": nome_admin,
                "cpf_administrador": _digitos(linha.get("CPF_Administrador")),
                "cargo_administrador": normalizar_texto(linha.get("Cargo_Administrador")),
                "nome_pessoa_relacionada": nome_rel,
                "tipo_pessoa_relacionada": normalizar_texto(linha.get("Tipo_Pessoa_Relacionada")),
                "documento_pessoa_relacionada": _digitos(linha.get("Documento_Pessoa_Relacionada")),
                "cargo_pessoa_relacionada": normalizar_texto(linha.get("Cargo_Pessoa_Relacionada")),
                "categoria_pessoa_relacionada": normalizar_texto(linha.get("Categoria_Pessoa_Relacionada")),
                "tipo_relacao": normalizar_texto(linha.get("Tipo_Relacao")),
                "observacao": normalizar_texto(linha.get("Observacao")),
            },
        )
    if tipo == "transacao_parte_relacionada":
        parte_rel = normalizar_texto(linha.get("Parte_Relacionada"))
        if parte_rel is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_transacao_parte_relacionada",
            base
            | {
                "parte_relacionada": parte_rel,
                "tipo_pessoa": normalizar_texto(linha.get("Tipo_Pessoa")),
                "documento_parte_relacionada": _digitos(linha.get("Documento_Parte_Relacionada")),
                "relacao_emissor": normalizar_texto(linha.get("Relacao_Emissor")),
                "data_transacao": normalizar_data(linha.get("Data_Transacao")),
                "objeto_contrato": normalizar_texto(linha.get("Objeto_Contrato")),
                "montante_envolvido": normalizar_decimal_cvm(linha.get("Montante_Envolvido")),
                "saldo_existente": normalizar_texto(linha.get("Saldo_Existente")),
                "montante_interesse_parte_relacionada": normalizar_texto(linha.get("Montante_Interesse_Parte_Relacionada")),
                "garantia_seguro": normalizar_texto(linha.get("Garantia_Seguro")),
                "duracao_transacao": normalizar_texto(linha.get("Duracao_Transacao")),
                "emprestimo_divida": normalizar_texto(linha.get("Emprestimo_Divida")),
                "rescisao": normalizar_texto(linha.get("Rescisao")),
                "natureza_razao_operacao": normalizar_texto(linha.get("Natureza_Razao_Operacao")),
                "taxa_juros": normalizar_texto(linha.get("Taxa_Juros")),
                "posicao_contratual_emissor": normalizar_texto(linha.get("Posicao_Contratual_Emissor")),
                "especificacao_posicao_contratual_emissor": normalizar_texto(linha.get("Especificacao_Posicao_Contratual_Emissor")),
            },
        )
    if tipo == "capital_social_aumento":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_aumento",
            base
            | {
                "id_capital_social": id_capital_social,
                "data_deliberacao": normalizar_data(linha.get("Data_Deliberacao")),
                "valor_aumento": normalizar_decimal_cvm(linha.get("Valor_Aumento")),
                "origem_aumento": normalizar_texto(linha.get("Origem_Aumento")),
                "quantidade_acoes_ordinarias": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Ordinarias")),
                "quantidade_acoes_preferenciais": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Preferenciais")),
                "quantidade_total_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Total_Acoes")),
            },
        )
    if tipo == "capital_social_aumento_classe_acao":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        tipo_classe = normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial"))
        if id_capital_social is None or tipo_classe is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_aumento_classe_acao",
            base
            | {
                "id_capital_social": id_capital_social,
                "tipo_classe_acao_preferencial": tipo_classe,
                "quantidade_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Acoes")),
            },
        )
    if tipo == "capital_social_desdobramento":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_desdobramento",
            base
            | {
                "id_capital_social": id_capital_social,
                "data_deliberacao": normalizar_data(linha.get("Data_Deliberacao")),
                "tipo_desdobramento": normalizar_texto(linha.get("Tipo_Desdobramento")),
                "proporcao_acoes_novas": normalizar_decimal_cvm(linha.get("Proporcao_Acoes_Novas")),
                "proporcao_acoes_antigas": normalizar_decimal_cvm(linha.get("Proporcao_Acoes_Antigas")),
                "quantidade_acoes_ordinarias": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Ordinarias")),
                "quantidade_acoes_preferenciais": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Preferenciais")),
                "quantidade_total_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Total_Acoes")),
            },
        )
    if tipo == "capital_social_desdobramento_classe_acao":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        tipo_classe = normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial"))
        if id_capital_social is None or tipo_classe is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_desdobramento_classe_acao",
            base
            | {
                "id_capital_social": id_capital_social,
                "tipo_classe_acao_preferencial": tipo_classe,
                "quantidade_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Acoes")),
            },
        )
    if tipo == "capital_social_reducao":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        if id_capital_social is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_reducao",
            base
            | {
                "id_capital_social": id_capital_social,
                "data_deliberacao": normalizar_data(linha.get("Data_Deliberacao")),
                "valor_reducao": normalizar_decimal_cvm(linha.get("Valor_Reducao")),
                "motivo_reducao": normalizar_texto(linha.get("Motivo_Reducao")),
                "quantidade_acoes_ordinarias": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Ordinarias")),
                "quantidade_acoes_preferenciais": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Preferenciais")),
                "quantidade_total_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Total_Acoes")),
            },
        )
    if tipo == "capital_social_reducao_classe_acao":
        id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
        tipo_classe = normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial"))
        if id_capital_social is None or tipo_classe is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_capital_social_reducao_classe_acao",
            base
            | {
                "id_capital_social": id_capital_social,
                "tipo_classe_acao_preferencial": tipo_classe,
                "quantidade_acoes": normalizar_decimal_cvm(linha.get("Quantidade_Acoes")),
            },
        )
    if tipo == "direito_acao":
        tipo_classe = normalizar_texto(linha.get("Tipo_Classe_Acao"))
        direito_voto = normalizar_texto(linha.get("Direito_Voto"))
        if tipo_classe is None or direito_voto is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_direito_acao",
            base
            | {
                "tipo_classe_acao": tipo_classe,
                "direito_voto": direito_voto,
                "outros_direitos": normalizar_texto(linha.get("Outros_Direitos")),
            },
        )
    if tipo == "volume_valor_mobiliario":
        classe_val = normalizar_texto(linha.get("Classe_Valor_Mobiliario"))
        if classe_val is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_volume_valor_mobiliario",
            base
            | {
                "classe_valor_mobiliario": classe_val,
                "sigla_classe_acoes_preferenciais": normalizar_texto(linha.get("Sigla_Classe_Acoes_Preferenciais")),
                "volume_negociacao": normalizar_decimal_cvm(linha.get("Volume_Negociacao")),
            },
        )
    if tipo == "outro_valor_mobiliario":
        nome_val = normalizar_texto(linha.get("Nome_Valor_Mobiliario"))
        if nome_val is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_outro_valor_mobiliario",
            base
            | {
                "nome_valor_mobiliario": nome_val,
                "caracteristicas_valor_mobiliario": normalizar_texto(linha.get("Caracteristicas_Valor_Mobiliario")),
            },
        )
    if tipo == "titular_valor_mobiliario":
        nome_tit = normalizar_texto(linha.get("Nome_Titular"))
        classe_val = normalizar_texto(linha.get("Classe_Valor_Mobiliario"))
        if nome_tit is None or classe_val is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_titular_valor_mobiliario",
            base
            | {
                "nome_titular": nome_tit,
                "cpf_cnpj_titular": _digitos(linha.get("CPF_CNPJ_Titular")),
                "classe_valor_mobiliario": classe_val,
                "quantidade_valores_mobiliarios": normalizar_decimal_cvm(linha.get("Quantidade_Valores_Mobiliarios")),
                "percentual_classe": normalizar_decimal_cvm(linha.get("Percentual_Classe")),
            },
        )
    if tipo == "mercado_estrangeiro":
        nome_mer = normalizar_texto(linha.get("Nome_Mercado"))
        if nome_mer is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_mercado_estrangeiro",
            base
            | {
                "nome_mercado": nome_mer,
                "orgao_regulador": normalizar_texto(linha.get("Orgao_Regulador")),
                "data_admissao": normalizar_data(linha.get("Data_Admissao")),
            },
        )
    if tipo == "titulo_exterior":
        nome_tit = normalizar_texto(linha.get("Nome_Titulo"))
        if nome_tit is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_titulo_exterior",
            base
            | {
                "nome_titulo": nome_tit,
                "pais_emissao": normalizar_texto(linha.get("Pais_Emissao")),
                "caracteristicas": normalizar_texto(linha.get("Caracteristicas")),
            },
        )
    if tipo == "plano_recompra":
        id_plano = normalizar_inteiro(linha.get("ID_Plano_Recompra"))
        if id_plano is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_plano_recompra",
            base
            | {
                "id_plano_recompra": id_plano,
                "data_deliberacao": normalizar_data(linha.get("Data_Deliberacao")),
                "objetivo_plano": normalizar_texto(linha.get("Objetivo_Plano")),
                "limite_prazo_aquisicao": normalizar_texto(linha.get("Limite_Prazo_Aquisicao")),
                "quantidade_total_ordinarias_adquiridas": normalizar_decimal_cvm(linha.get("Quantidade_Total_Ordinarias_Adquiridas")),
                "quantidade_total_preferenciais_adquiridas": normalizar_decimal_cvm(linha.get("Quantidade_Total_Preferenciais_Adquiridas")),
            },
        )
    if tipo == "plano_recompra_classe_acao":
        id_plano = normalizar_inteiro(linha.get("ID_Plano_Recompra"))
        tipo_classe = normalizar_texto(linha.get("Tipo_Classe_Acao_Preferencial"))
        if id_plano is None or tipo_classe is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_plano_recompra_classe_acao",
            base
            | {
                "id_plano_recompra": id_plano,
                "tipo_classe_acao_preferencial": tipo_classe,
                "quantidade_acoes_adquiridas": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Adquiridas")),
            },
        )
    if tipo == "valor_mobiliario_tesouraria_movimentacao":
        classe_val = normalizar_texto(linha.get("Classe_Valor_Mobiliario"))
        data_mov = normalizar_data(linha.get("Data_Movimentacao"))
        if classe_val is None or data_mov is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_valor_mobiliario_tesouraria_movimentacao",
            base
            | {
                "classe_valor_mobiliario": classe_val,
                "data_movimentacao": data_mov,
                "quantidade_movimentada": normalizar_decimal_cvm(linha.get("Quantidade_Movimentada")),
                "natureza_movimentacao": normalizar_texto(linha.get("Natureza_Movimentacao")),
            },
        )
    if tipo == "valor_mobiliario_tesouraria_ultimo_exercicio":
        classe_val = normalizar_texto(linha.get("Classe_Valor_Mobiliario"))
        hist_ex = normalizar_texto(linha.get("Historico_Exercicio"))
        if classe_val is None or hist_ex is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_valor_mobiliario_tesouraria_ultimo_exercicio",
            base
            | {
                "classe_valor_mobiliario": classe_val,
                "historico_exercicio": hist_ex,
                "quantidade_acoes_tesouraria": normalizar_decimal_cvm(linha.get("Quantidade_Acoes_Tesouraria")),
            },
        )
    if tipo == "administrador_declaracao_genero":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_administrador_declaracao_genero",
            base
            | {
                "orgao_administracao": orgao,
                "quantidade_feminino": normalizar_inteiro(linha.get("Quantidade_Feminino")),
                "quantidade_masculino": normalizar_inteiro(linha.get("Quantidade_Masculino")),
                "quantidade_nao_binario": normalizar_inteiro(linha.get("Quantidade_Nao_Binario")),
                "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
                "nao_aplicavel": _normalizar_booleano(linha.get("Nao_Aplicavel")),
            },
        )
    if tipo == "administrador_pcd":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_administrador_pcd",
            base
            | {
                "orgao_administracao": orgao,
                "quantidade_pcd": normalizar_inteiro(linha.get("Quantidade_PCD")),
                "quantidade_nao_pcd": normalizar_inteiro(linha.get("Quantidade_Nao_PCD")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
                "nao_aplicavel": _normalizar_booleano(linha.get("Nao_Aplicavel")),
            },
        )
    if tipo == "administrador_declaracao_raca":
        orgao = normalizar_texto(linha.get("Orgao_Administracao"))
        if orgao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_administrador_declaracao_raca",
            base
            | {
                "orgao_administracao": orgao,
                "quantidade_amarelo": normalizar_inteiro(linha.get("Quantidade_Amarelo")),
                "quantidade_branco": normalizar_inteiro(linha.get("Quantidade_Branco")),
                "quantidade_preto": normalizar_inteiro(linha.get("Quantidade_Preto")),
                "quantidade_pardo": normalizar_inteiro(linha.get("Quantidade_Pardo")),
                "quantidade_indigena": normalizar_inteiro(linha.get("Quantidade_Indigena")),
                "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
                "nao_aplicavel": _normalizar_booleano(linha.get("Nao_Aplicavel")),
            },
        )
    if tipo == "empregado_posicao_local":
        posicao = normalizar_texto(linha.get("Posicao"))
        if posicao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_posicao_local",
            base
            | {
                "posicao": posicao,
                "quantidade_norte": normalizar_inteiro(linha.get("Quantidade_Norte")),
                "quantidade_nordeste": normalizar_inteiro(linha.get("Quantidade_Nordeste")),
                "quantidade_centro_oeste": normalizar_inteiro(linha.get("Quantidade_Centro_Oeste")),
                "quantidade_sudeste": normalizar_inteiro(linha.get("Quantidade_Sudeste")),
                "quantidade_sul": normalizar_inteiro(linha.get("Quantidade_Sul")),
                "quantidade_exterior": normalizar_inteiro(linha.get("Quantidade_Exterior")),
            },
        )
    if tipo == "empregado_posicao_faixa_etaria":
        posicao = normalizar_texto(linha.get("Posicao"))
        if posicao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_posicao_faixa_etaria",
            base
            | {
                "posicao": posicao,
                "quantidade_ate_30_anos": normalizar_inteiro(linha.get("Quantidade_Ate30Anos")),
                "quantidade_30_a_50_anos": normalizar_inteiro(linha.get("Quantidade_30a50Anos")),
                "quantidade_acima_50_anos": normalizar_inteiro(linha.get("Quantidade_Acima50Anos")),
            },
        )
    if tipo == "empregado_posicao_declaracao_raca":
        posicao = normalizar_texto(linha.get("Posicao"))
        if posicao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_posicao_declaracao_raca",
            base
            | {
                "posicao": posicao,
                "quantidade_amarelo": normalizar_inteiro(linha.get("Quantidade_Amarelo")),
                "quantidade_branco": normalizar_inteiro(linha.get("Quantidade_Branco")),
                "quantidade_preto": normalizar_inteiro(linha.get("Quantidade_Preto")),
                "quantidade_pardo": normalizar_inteiro(linha.get("Quantidade_Pardo")),
                "quantidade_indigena": normalizar_inteiro(linha.get("Quantidade_Indigena")),
                "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
            },
        )
    if tipo == "empregado_pcd":
        posicao = normalizar_texto(linha.get("Posicao"))
        if posicao is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_pcd",
            base
            | {
                "codigo_posicao": normalizar_inteiro(linha.get("Codigo_Posicao")),
                "posicao": posicao,
                "quantidade_pcd": normalizar_inteiro(linha.get("Quantidade_PCD")),
                "quantidade_nao_pcd": normalizar_inteiro(linha.get("Quantidade_Nao_PCD")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
            },
        )
    if tipo == "empregado_local_faixa_etaria":
        local = normalizar_texto(linha.get("Local"))
        if local is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_local_faixa_etaria",
            base
            | {
                "local": local,
                "quantidade_ate_30_anos": normalizar_inteiro(linha.get("Quantidade_Ate30Anos")),
                "quantidade_30_a_50_anos": normalizar_inteiro(linha.get("Quantidade_30a50Anos")),
                "quantidade_acima_50_anos": normalizar_inteiro(linha.get("Quantidade_Acima50Anos")),
            },
        )
    if tipo == "empregado_local_declaracao_raca":
        local = normalizar_texto(linha.get("Local"))
        if local is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_local_declaracao_raca",
            base
            | {
                "local": local,
                "quantidade_amarelo": normalizar_inteiro(linha.get("Quantidade_Amarelo")),
                "quantidade_branco": normalizar_inteiro(linha.get("Quantidade_Branco")),
                "quantidade_preto": normalizar_inteiro(linha.get("Quantidade_Preto")),
                "quantidade_pardo": normalizar_inteiro(linha.get("Quantidade_Pardo")),
                "quantidade_indigena": normalizar_inteiro(linha.get("Quantidade_Indigena")),
                "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
            },
        )
    if tipo == "empregado_local_declaracao_genero":
        local = normalizar_texto(linha.get("Local"))
        if local is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fre_empregado_local_declaracao_genero",
            base
            | {
                "local": local,
                "quantidade_feminino": normalizar_inteiro(linha.get("Quantidade_Feminino")),
                "quantidade_masculino": normalizar_inteiro(linha.get("Quantidade_Masculino")),
                "quantidade_nao_binario": normalizar_inteiro(linha.get("Quantidade_Nao_Binario")),
                "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
            },
        )
    posicao = normalizar_texto(linha.get("Posicao"))
    if posicao is None:
        raise ValueError("campo_obrigatorio_ausente")
    return (
        "fre_empregado_posicao_genero",
        base
        | {
            "posicao": posicao,
            "quantidade_feminino": normalizar_inteiro(linha.get("Quantidade_Feminino")),
            "quantidade_masculino": normalizar_inteiro(linha.get("Quantidade_Masculino")),
            "quantidade_nao_binario": normalizar_inteiro(linha.get("Quantidade_Nao_Binario")),
            "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
            "quantidade_sem_resposta": normalizar_inteiro(linha.get("Quantidade_Sem_Resposta")),
        },
    )


def _resolver_input_from_data(dados: dict[str, Any]) -> ResolverInput:
    return ResolverInput(
        cnpj_companhia=dados.get("cnpj_companhia"),
        codigo_cvm=dados.get("codigo_cvm"),
        denominacao_companhia=dados.get("denominacao_companhia") or dados.get("nome_companhia"),
        tipo_formulario="FRE",
        id_documento=dados.get("id_documento"),
        versao=dados.get("versao"),
        data_referencia=dados.get("data_referencia"),
    )


def _fre_promotion_spec(row_kind: str) -> tuple[type[Any], str, tuple[str, ...]]:
    if row_kind == "fre_documento":
        return (
            FreDocumento,
            "fre_documentos",
            ("id_documento", "versao", "data_referencia"),
        )
    if row_kind == "fre_auditor":
        return (
            FreAuditor,
            "fre_auditores",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_auditor"),
        )
    if row_kind == "fre_capital_social":
        return (
            FreCapitalSocial,
            "fre_capital_social",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social"),
        )
    if row_kind == "fre_posicao_acionaria":
        return (
            FrePosicaoAcionaria,
            "fre_posicoes_acionarias",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_acionista"),
        )
    if row_kind == "fre_remuneracao_total_orgao":
        return (
            FreRemuneracaoTotalOrgao,
            "fre_remuneracoes_totais_orgaos",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "orgao_administracao",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
            ),
        )
    if row_kind == "fre_participacao_sociedade":
        return (
            FreParticipacaoSociedade,
            "fre_participacoes_sociedades",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_sociedade"),
        )
    if row_kind == "fre_empregado_posicao_local":
        return (
            FreEmpregadoPosicaoLocal,
            "fre_empregados_posicao_local",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao"),
        )
    if row_kind == "fre_empregado_posicao_faixa_etaria":
        return (
            FreEmpregadoPosicaoFaixaEtaria,
            "fre_empregados_posicao_faixa_etaria",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao"),
        )
    if row_kind == "fre_empregado_posicao_declaracao_raca":
        return (
            FreEmpregadoPosicaoDeclaracaoRaca,
            "fre_empregados_posicao_declaracao_raca",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao"),
        )
    if row_kind == "fre_empregado_pcd":
        return (
            FreEmpregadoPcd,
            "fre_empregados_pcd",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "codigo_posicao", "posicao"),
        )
    if row_kind == "fre_empregado_local_faixa_etaria":
        return (
            FreEmpregadoLocalFaixaEtaria,
            "fre_empregados_local_faixa_etaria",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "local"),
        )
    if row_kind == "fre_empregado_local_declaracao_raca":
        return (
            FreEmpregadoLocalDeclaracaoRaca,
            "fre_empregados_local_declaracao_raca",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "local"),
        )
    if row_kind == "fre_empregado_local_declaracao_genero":
        return (
            FreEmpregadoLocalDeclaracaoGenero,
            "fre_empregados_local_declaracao_genero",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "local"),
        )
    if row_kind == "fre_responsavel":
        return (
            FreResponsavel,
            "fre_responsaveis",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "nome_responsavel", "cargo_responsavel"),
        )
    if row_kind == "fre_capital_social_classe_acao":
        return (
            FreCapitalSocialClasseAcao,
            "fre_capital_social_classes_acoes",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "id_capital_social",
                "tipo_classe_acao_preferencial",
            ),
        )
    if row_kind == "fre_capital_social_titulo_conversivel":
        return (
            FreCapitalSocialTituloConversivel,
            "fre_capital_social_titulos_conversiveis",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "id_capital_social",
                "titulo_conversivel_acao",
            ),
        )
    if row_kind == "fre_distribuicao_capital":
        return (
            FreDistribuicaoCapital,
            "fre_distribuicao_capital",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia"),
        )
    if row_kind == "fre_distribuicao_capital_classe_acao":
        return (
            FreDistribuicaoCapitalClasseAcao,
            "fre_distribuicao_capital_classes_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "sigla_classe_acoes_preferenciais"),
        )
    if row_kind == "fre_posicao_acionaria_classe_acao":
        return (
            FrePosicaoAcionariaClasseAcao,
            "fre_posicoes_acionarias_classes_acoes",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "id_acionista",
                "tipo_classe_acao_preferencial",
                "quantidade_acoes",
                "percentual_acoes",
            ),
        )
    if row_kind == "fre_remuneracao_maxima_minima_media":
        return (
            FreRemuneracaoMaximaMinimaMedia,
            "fre_remuneracoes_maximas_minimas_medias",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "orgao_administracao",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
            ),
        )
    if row_kind == "fre_remuneracao_variavel":
        return (
            FreRemuneracaoVariavel,
            "fre_remuneracoes_variaveis",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "orgao_administracao",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
            ),
        )
    if row_kind == "fre_remuneracao_acao":
        return (
            FreRemuneracaoAcao,
            "fre_remuneracoes_acoes",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "orgao_administracao",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
            ),
        )
    if row_kind == "fre_acao_entregue":
        return (
            FreAcaoEntregue,
            "fre_acoes_entregues",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "orgao_administracao",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
            ),
        )
    if row_kind == "fre_administrador_membro_conselho_fiscal":
        return (
            FreAdministradorMembroConselhoFiscal,
            "fre_administradores_membros_conselho_fiscal",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "nome",
                "cpf",
                "orgao_administracao",
                "data_eleicao",
                "data_posse",
                "cargo_eletivo_ocupado",
                "outro_cargo_funcao",
            ),
        )
    if row_kind == "fre_membro_comite":
        return (
            FreMembroComite,
            "fre_membros_comites",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "nome",
                "cpf",
                "tipo_comite",
                "descricao_outros_comites",
            ),
        )
    if row_kind == "fre_relacao_familiar":
        return (
            FreRelacaoFamiliar,
            "fre_relacoes_familiares",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "nome_administrador",
                "nome_pessoa_relacionada",
                "tipo_parentesco",
                "cnpj_emissor_pessoa_relacionada",
                "nome_emissor_pessoa_relacionada",
                "cargo_Pessoa_relacionada",
                "cnpj_emissor",
                "nome_emissor",
                "cargo_administrador",
            ),
        )
    if row_kind == "fre_relacao_subordinacao":
        return (
            FreRelacaoSubordinacao,
            "fre_relacoes_subordinacao",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "data_inicio_exercicio_social",
                "data_fim_exercicio_social",
                "nome_administrador",
                "nome_pessoa_relacionada",
                "tipo_relacao",
                "cargo_administrador",
                "cargo_pessoa_relacionada",
            ),
        )
    if row_kind == "fre_transacao_parte_relacionada":
        return (
            FreTransacaoParteRelacionada,
            "fre_transacoes_partes_relacionadas",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "parte_relacionada",
                "documento_parte_relacionada",
                "relacao_emissor",
                "data_transacao",
                "montante_envolvido",
                "saldo_existente",
                "montante_interesse_parte_relacionada",
                "posicao_contratual_emissor",
            ),
        )
    if row_kind == "fre_capital_social_aumento":
        return (
            FreCapitalSocialAumento,
            "fre_capital_social_aumentos",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social"),
        )
    if row_kind == "fre_capital_social_aumento_classe_acao":
        return (
            FreCapitalSocialAumentoClasseAcao,
            "fre_capital_social_aumento_classes_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social", "tipo_classe_acao_preferencial"),
        )
    if row_kind == "fre_capital_social_desdobramento":
        return (
            FreCapitalSocialDesdobramento,
            "fre_capital_social_desdobramentos",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social"),
        )
    if row_kind == "fre_capital_social_desdobramento_classe_acao":
        return (
            FreCapitalSocialDesdobramentoClasseAcao,
            "fre_capital_social_desdobramento_classes_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social", "tipo_classe_acao_preferencial"),
        )
    if row_kind == "fre_capital_social_reducao":
        return (
            FreCapitalSocialReducao,
            "fre_capital_social_reducoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social"),
        )
    if row_kind == "fre_capital_social_reducao_classe_acao":
        return (
            FreCapitalSocialReducaoClasseAcao,
            "fre_capital_social_reducao_classes_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social", "tipo_classe_acao_preferencial"),
        )
    if row_kind == "fre_direito_acao":
        return (
            FreDireitoAcao,
            "fre_direitos_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "tipo_classe_acao", "direito_voto"),
        )
    if row_kind == "fre_volume_valor_mobiliario":
        return (
            FreVolumeValorMobiliario,
            "fre_volumes_valores_mobiliarios",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "classe_valor_mobiliario"),
        )
    if row_kind == "fre_outro_valor_mobiliario":
        return (
            FreOutroValorMobiliario,
            "fre_outros_valores_mobiliarios",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "nome_valor_mobiliario"),
        )
    if row_kind == "fre_titular_valor_mobiliario":
        return (
            FreTitularValorMobiliario,
            "fre_titulares_valores_mobiliarios",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "nome_titular", "classe_valor_mobiliario"),
        )
    if row_kind == "fre_mercado_estrangeiro":
        return (
            FreMercadoEstrangeiro,
            "fre_mercados_estrangeiros",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "nome_mercado"),
        )
    if row_kind == "fre_titulo_exterior":
        return (
            FreTituloExterior,
            "fre_titulos_exterior",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "nome_titulo"),
        )
    if row_kind == "fre_plano_recompra":
        return (
            FrePlanoRecompra,
            "fre_planos_recompra",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_plano_recompra"),
        )
    if row_kind == "fre_plano_recompra_classe_acao":
        return (
            FrePlanoRecompraClasseAcao,
            "fre_plano_recompra_classes_acoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_plano_recompra", "tipo_classe_acao_preferencial"),
        )
    if row_kind == "fre_valor_mobiliario_tesouraria_movimentacao":
        return (
            FreValorMobiliarioTesourariaMovimentacao,
            "fre_valores_mobiliarios_tesouraria_movimentacoes",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "classe_valor_mobiliario", "data_movimentacao"),
        )
    if row_kind == "fre_valor_mobiliario_tesouraria_ultimo_exercicio":
        return (
            FreValorMobiliarioTesourariaUltimoExercicio,
            "fre_valores_mobiliarios_tesouraria_ultimos_exercicios",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "classe_valor_mobiliario", "historico_exercicio"),
        )
    if row_kind == "fre_administrador_declaracao_genero":
        return (
            FreAdministradorDeclaracaoGenero,
            "fre_administradores_declaracao_genero",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "orgao_administracao"),
        )
    if row_kind == "fre_administrador_pcd":
        return (
            FreAdministradorPcd,
            "fre_administradores_pcd",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "orgao_administracao"),
        )
    if row_kind == "fre_administrador_declaracao_raca":
        return (
            FreAdministradorDeclaracaoRaca,
            "fre_administradores_declaracao_raca",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "orgao_administracao"),
        )
    return (
        FreEmpregadoPosicaoGenero,
        "fre_empregados_posicao_genero",
        ("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao"),
    )


def _key_tuple(dados: dict[str, Any], campos_chave: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(dados[campo] for campo in campos_chave)


def _build_key_clause(model: type[Any], campos_chave: tuple[str, ...], chaves: Sequence[tuple[Any, ...]]) -> Any:
    return or_(
        *[
            and_(*[getattr(model, campo) == valor for campo, valor in zip(campos_chave, chave, strict=False)])
            for chave in chaves
        ]
    )


def _preparar_dados_promocao(dados: dict[str, Any]) -> dict[str, Any]:
    dados_promocao = dict(dados)
    dados_promocao["hash_origem"] = gerar_hash_canonico(
        {k: v for k, v in dados_promocao.items() if k != "linha_origem"}
    )
    return dados_promocao


def _promote_fre_chunk(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    safe_promote_chunk(
        db,
        promote_func=_promote_fre_chunk_internal,
        linhas_promovidas=linhas_promovidas,
        execucao_id=execucao_id,
        contadores=contadores,
        registrar_quarentena_fn=_registrar_quarentena,
        row_kind=row_kind,
    )


def _promote_fre_chunk_internal(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if not linhas_promovidas:
        return

    model, entidade, campos_chave = _fre_promotion_spec(row_kind)
    campos_negocio = set(linhas_promovidas[0][1].keys()) - {
        "arquivo_origem",
        "ano_origem",
        "linha_origem",
        "hash_origem",
    }
    agora = _agora()
    preparados = [(row, _preparar_dados_promocao(dados)) for row, dados in linhas_promovidas]
    chaves = list(dict.fromkeys(_key_tuple(dados, campos_chave) for _, dados in preparados))
    existentes: list[Any] = []
    if chaves:
        for batch in iter_lookup_batches(chaves, parameter_width=len(campos_chave)):
            existentes.extend(db.execute(select(model).where(_build_key_clause(model, campos_chave, batch))).scalars())
    existentes_por_chave = {tuple(getattr(item, campo) for campo in campos_chave): item for item in existentes}

    payload_insercao: list[dict[str, Any]] = []
    historicos: list[dict[str, Any]] = []
    chaves_no_lote: dict[tuple[Any, ...], dict[str, Any]] = {}

    for _row, dados in preparados:
        chave = _key_tuple(dados, campos_chave)
        existente_lote = chaves_no_lote.get(chave)
        if existente_lote is not None:
            for campo in campos_negocio:
                if campo in dados and dados[campo] is not None and dados[campo] != existente_lote.get(campo):
                    existente_lote[campo] = dados[campo]
            existente_lote["arquivo_origem"] = dados["arquivo_origem"]
            existente_lote["ano_origem"] = dados["ano_origem"]
            existente_lote["linha_origem"] = dados["linha_origem"]
            existente_lote["hash_origem"] = dados["hash_origem"]
            contadores["atualizados"] += 1
            continue
        existente = existentes_por_chave.get(chave)
        if existente is None:
            chaves_no_lote[chave] = dados
            novo_id = uuid.uuid4()
            payload_insercao.append(
                {
                    "id": novo_id,
                    **dados,
                    "criado_em": agora,
                    "sincronizado_em": agora,
                    "alterado_em": agora,
                }
            )
            contadores["inseridos"] += 1
            continue

        alteracoes: dict[str, tuple[Any, Any]] = {}
        for campo in campos_negocio:
            antigo = getattr(existente, campo)
            novo = dados[campo]
            if not _equivalente(antigo, novo):
                alteracoes[campo] = (antigo, novo)

        existente.sincronizado_em = agora
        existente.arquivo_origem = dados["arquivo_origem"]
        existente.ano_origem = dados["ano_origem"]
        existente.linha_origem = dados["linha_origem"]
        existente.hash_origem = dados["hash_origem"]

        if not alteracoes:
            contadores["inalterados"] += 1
        else:
            for campo, (_, novo) in alteracoes.items():
                setattr(existente, campo, novo)
            existente.alterado_em = agora
            contadores["atualizados"] += 1
            for campo, (antigo, novo) in alteracoes.items():
                historicos.append(
                    {
                        "entidade": entidade,
                        "entidade_id": existente.id,
                        "companhia_id": dados.get("companhia_id"),
                        "campo": campo,
                        "valor_anterior": None if antigo is None else str(antigo),
                        "valor_novo": None if novo is None else str(novo),
                        "alterado_em": agora,
                        "execucao_sincronizacao_id": execucao_id,
                        "arquivo_origem": dados["arquivo_origem"],
                        "ano_origem": dados["ano_origem"],
                    }
                )
    if payload_insercao:
        for batch in iter_parameter_batches(payload_insercao, parameter_width=mapping_parameter_width(payload_insercao)):
            db.execute(insert(model), batch)
    if historicos:
        for batch in iter_parameter_batches(historicos, parameter_width=mapping_parameter_width(historicos)):
            db.execute(insert(HistoricoAlteracaoCampo), batch)


def _promote_fre_row(
    db: Session,
    *,
    row_kind: str,
    row: IngestionRow,
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    _promote_fre_chunk(
        db,
        row_kind=row_kind,
        linhas_promovidas=[(row, dados)],
        execucao_id=execucao_id,
        contadores=contadores,
    )


def _process_fre_rows(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: Any,
    ano: int,
    staged_members: list[tuple[Any, list[IngestionRow]]],
    promote_enabled: bool,
    contadores: dict[str, int] | None = None,
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] | None = None,
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any] | None = None,
) -> dict[str, int]:
    member_type_map = {item.render_member_name(ano=ano): item.dataset for item in listar_datasets("fre")}
    if contadores is None:
        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    if seen_by_row_kind is None:
        seen_by_row_kind = {}
    if header_map is None:
        header_map = {}

    ordered_members = sorted(
        staged_members,
        key=lambda item: (0 if item[0].member_name == f"fre_cia_aberta_{ano}.csv" else 1, item[0].member_name),
    )

    for member, rows in ordered_members:
        if not rows or rows[0].row_kind == "desconhecido":
            continue
        schema_result = validate_member_header(rows[0].row_kind if rows else "desconhecido", member.header)
        update_member_schema_validation(member, result=schema_result)
        if schema_result.status == "invalid":
            contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
            contadores["lidas"] += member.row_count
            contadores["rejeitados"] += member.row_count
            continue

        tipo = member_type_map.get(member.member_name)
        if tipo is None:
            # Unknown CSV member not registered in the source registry - skip gracefully.
            continue
        for row in rows:
            contadores["lidas"] += 1
            try:
                row_kind, dados = normalizar_fre_row(
                    tipo=tipo,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    linha=row.raw_data,
                )
            except Exception as exc:
                result = invalid_result(
                    f"normalizacao_invalida: {exc}",
                    details={"erro": str(exc)},
                    repairable=True,
                )
                write_validation_result(db, ingestion_row=row, result=result)
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao.id,
                    legacy_reason=f"normalizacao_invalida: {exc}",
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=f"normalizacao_invalida: {exc}",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            natural_key = build_natural_key(row_kind, dados)
            duplicate_result = classify_duplicate(
                row_kind=row_kind,
                natural_key=natural_key,
                normalized_hash=gerar_hash_canonico(dados),
                normalized_data=dados,
                seen_by_key=seen_by_row_kind.setdefault(row_kind, {}),
            )
            if duplicate_result.status == "ignored_duplicate":
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                contadores["inalterados"] += 1
                continue
            if duplicate_result.status == "invalid":
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    execucao_sincronizacao_id=execucao.id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=duplicate_result.reason_code or "chave_natural_duplicada_conflitante",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            resolver_result = resolve_companhia(db, _resolver_input_from_data(dados), header_map=header_map)
            if resolver_result.status not in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
                result = invalid_result(
                    resolver_result.resolution_method or "companhia_nao_encontrada",
                    details=resolver_result.details,
                    repairable=True,
                )
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao.id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=resolver_result.resolution_method or "companhia_nao_encontrada",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            persist_resolution_result(db, ingestion_row=row, result=resolver_result)
            companhia = db.get(Companhia, resolver_result.companhia_id) if resolver_result.companhia_id else None
            dados["companhia_id"] = resolver_result.companhia_id
            if dados.get("cnpj_companhia") is None and companhia is not None:
                dados["cnpj_companhia"] = companhia.cnpj_companhia
            if row_kind == "fre_documento" and dados.get("codigo_cvm") is None and companhia is not None:
                dados["codigo_cvm"] = companhia.codigo_cvm

            write_validation_result(
                db,
                ingestion_row=row,
                result=duplicate_result,
                normalized_data=dados,
                natural_key=natural_key,
            )
            if promote_enabled:
                _promote_fre_row(
                    db,
                    row_kind=row_kind,
                    row=row,
                    dados=dados,
                    execucao_id=execucao.id,
                    contadores=contadores,
                )
            else:
                contadores["inalterados"] += 1
            if row_kind == "fre_documento":
                if resolver_result.companhia_id is not None:
                    register_document_header(
                        header_map,
                        tipo_formulario="FRE",
                        id_documento=dados.get("id_documento"),
                        versao=dados.get("versao"),
                        data_referencia=dados.get("data_referencia"),
                        companhia_id=resolver_result.companhia_id,
                        cnpj_companhia=dados.get("cnpj_companhia"),
                        codigo_cvm=dados.get("codigo_cvm"),
                    )

            if contadores["lidas"] % _BATCH_COMMIT_LINHAS == 0:
                update_run_state(
                    run, phase="promote", quality_summary=build_contadores_quality_summary(contadores)
                )
                execucao.total_linhas_lidas = contadores["lidas"]
                execucao.total_inseridos = contadores["inseridos"]
                execucao.total_atualizados = contadores["atualizados"]
                execucao.total_inalterados = contadores["inalterados"]
                execucao.total_rejeitados = contadores["rejeitados"]
                db.commit()

    update_run_state(run, phase="promote", quality_summary=build_contadores_quality_summary(contadores))
    return contadores


def _ordered_fre_members(payload: bytes, *, ano: int) -> list[tuple[str, bytes]]:
    members = iter_zip_csv_members(payload)
    principal = f"fre_cia_aberta_{ano}.csv"
    return sorted(members, key=lambda item: (0 if item[0] == principal else 1, item[0]))


def _process_fre_member(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: Any,
    ano: int,
    member: Any,
    reconcile_required: bool,
    promote_enabled: bool,
    contadores: dict[str, int],
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]],
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any],
    chunk_size: int,
) -> None:
    member_type_map = {item.render_member_name(ano=ano): item.dataset for item in listar_datasets("fre")}
    chunks = iter_staged_member_chunks(db, member_id=member.id, chunk_size=chunk_size)
    first_rows = next(chunks, [])
    if not first_rows or first_rows[0].row_kind == "desconhecido":
        return

    schema_result = validate_member_header(first_rows[0].row_kind, member.header)
    update_member_schema_validation(member, result=schema_result)
    if schema_result.status == "invalid":
        contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
        contadores["lidas"] += member.row_count
        contadores["rejeitados"] += member.row_count
        return

    tipo = member_type_map.get(member.member_name)
    if tipo is None:
        return

    current_hashes_by_model: dict[type[Any], set[str]] = {}
    for rows in [first_rows, *chunks]:
        linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]] = []
        for row in rows:
            contadores["lidas"] += 1
            try:
                row_kind, dados = normalizar_fre_row(
                    tipo=tipo,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    linha=row.raw_data,
                )
            except Exception as exc:
                result = invalid_result(
                    f"normalizacao_invalida: {exc}",
                    details={"erro": str(exc)},
                    repairable=True,
                )
                write_validation_result(db, ingestion_row=row, result=result)
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao.id,
                    legacy_reason=f"normalizacao_invalida: {exc}",
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=f"normalizacao_invalida: {exc}",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            natural_key = build_natural_key(row_kind, dados)
            duplicate_result = classify_duplicate(
                row_kind=row_kind,
                natural_key=natural_key,
                normalized_hash=gerar_hash_canonico(dados),
                normalized_data=dados,
                seen_by_key=seen_by_row_kind.setdefault(row_kind, {}),
            )
            if duplicate_result.status == "ignored_duplicate":
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                contadores["inalterados"] += 1
                continue
            if duplicate_result.status == "invalid":
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    execucao_sincronizacao_id=execucao.id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=duplicate_result.reason_code or "chave_natural_duplicada_conflitante",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            resolver_result = resolve_companhia(db, _resolver_input_from_data(dados), header_map=header_map)
            if resolver_result.status not in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
                result = invalid_result(
                    resolver_result.resolution_method or "companhia_nao_encontrada",
                    details=resolver_result.details,
                    repairable=True,
                )
                write_validation_result(
                    db,
                    ingestion_row=row,
                    result=result,
                    normalized_data=dados,
                    natural_key=natural_key,
                )
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao.id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=resolver_result.resolution_method or "companhia_nao_encontrada",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                continue

            persist_resolution_result(db, ingestion_row=row, result=resolver_result)
            companhia = db.get(Companhia, resolver_result.companhia_id) if resolver_result.companhia_id else None
            dados["companhia_id"] = resolver_result.companhia_id
            if dados.get("cnpj_companhia") is None and companhia is not None:
                dados["cnpj_companhia"] = companhia.cnpj_companhia
            if row_kind == "fre_documento" and dados.get("codigo_cvm") is None and companhia is not None:
                dados["codigo_cvm"] = companhia.codigo_cvm

            write_validation_result(
                db,
                ingestion_row=row,
                result=duplicate_result,
                normalized_data=dados,
                natural_key=natural_key,
            )
            if promote_enabled:
                model, _, _ = _fre_promotion_spec(row_kind)
                current_hashes_by_model.setdefault(model, set()).add(_preparar_dados_promocao(dados)["hash_origem"])
                linhas_promovidas.append((row, dados))
            else:
                contadores["inalterados"] += 1
            if row_kind == "fre_documento" and resolver_result.companhia_id is not None:
                register_document_header(
                    header_map,
                    tipo_formulario="FRE",
                    id_documento=dados.get("id_documento"),
                    versao=dados.get("versao"),
                    data_referencia=dados.get("data_referencia"),
                    companhia_id=resolver_result.companhia_id,
                    cnpj_companhia=dados.get("cnpj_companhia"),
                    codigo_cvm=dados.get("codigo_cvm"),
                )

        if promote_enabled and linhas_promovidas:
            _promote_fre_chunk(
                db,
                row_kind=linhas_promovidas[0][0].row_kind,
                linhas_promovidas=linhas_promovidas,
                execucao_id=execucao.id,
                contadores=contadores,
            )
        update_run_state(run, phase="promote", quality_summary=build_contadores_quality_summary(contadores))
        execucao.total_linhas_lidas = contadores["lidas"]
        execucao.total_inseridos = contadores["inseridos"]
        execucao.total_atualizados = contadores["atualizados"]
        execucao.total_inalterados = contadores["inalterados"]
        execucao.total_rejeitados = contadores["rejeitados"]
        db.commit()

    if promote_enabled and reconcile_required:
        for model, current_hashes in current_hashes_by_model.items():
            contadores["reconciled_deleted"] = contadores.get("reconciled_deleted", 0) + reconcile_promoted_rows(
                db,
                model=model,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                arquivo_origem=member.member_name,
                ano_origem=ano,
                current_hashes=current_hashes,
            )


def sincronizar_fre(
    db: Session,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    limpar_caches_resolver()
    ensure_identity_graph_ready(db)
    if db.query(Companhia).count() == 0:
        raise ValueError("cadastro_companhias_nao_ingestado")
    custom_downloader = downloader is not None
    downloader = downloader or (lambda url: _download(url, timeout=300))
    arquivo_zip = f"fre_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/FRE/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte="fre",
        ano=ano,
        id_tarefa=task_id,
        arquivo=arquivo_zip,
        url=url,
        status="em_execucao",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    run = create_run(
        db,
        tipo_fonte="fre",
        ano=ano,
        execucao_sincronizacao_id=execucao.id,
        requested_by_task_id=task_id,
        phase="acquire",
    )
    db.commit()
    db.refresh(run)

    try:
        remote_probe = (
            build_custom_remote_probe(source_url=url)
            if custom_downloader
            else probe_remote_source(db, run=run, tipo_fonte="fre", ano=ano, source_url=url)
        )
        update_run_state(run, phase="acquire", remote_probe=remote_probe)
        if remote_probe.get("decision") == "unchanged" and not force_reimport:
            upsert_artifact_snapshot(
                db,
                run=run,
                source_url=url,
                source_filename=arquivo_zip,
                remote_probe=remote_probe,
                ingestion_file=None,
                status="sem_alteracao",
            )
            execucao.status = "sem_alteracao"
            execucao.finalizada_em = _agora()
            update_run_state(
                run,
                status="sem_alteracao",
                phase="complete",
                message=remote_probe.get("decision_reason"),
                remote_probe=remote_probe,
                finished_at=_agora(),
            )
            db.commit()
            return {"execucao_id": str(execucao.id), "status": "sem_alteracao"}

        payload = downloader(url)
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        remote_probe = annotate_probe_with_sha_confirmation(
            remote_probe,
            current_sha256=hash_arquivo,
            previous_sha256=hash_arquivo if buscar_execucao_hash_existente(
                db,
                tipo_fonte="fre",
                ano=ano,
                hash_arquivo=hash_arquivo,
                execucao_atual_id=execucao.id,
            )
            is not None
            else None,
        )
        execucao.hash_arquivo = hash_arquivo

        anterior = buscar_execucao_hash_existente(
            db,
            tipo_fonte="fre",
            ano=ano,
            hash_arquivo=hash_arquivo,
            execucao_atual_id=execucao.id,
        )
        if anterior is not None and not force_reimport:
            upsert_artifact_snapshot(
                db,
                run=run,
                source_url=url,
                source_filename=arquivo_zip,
                remote_probe=remote_probe,
                ingestion_file=None,
                status="sem_alteracao",
            )
            execucao.status = "sem_alteracao"
            execucao.finalizada_em = _agora()
            update_run_state(
                run,
                status="sem_alteracao",
                phase="complete",
                message="download_sha_igual_referencia",
                remote_probe=remote_probe,
                finished_at=_agora(),
            )
            db.commit()
            return {"execucao_id": str(execucao.id), "status": "sem_alteracao"}

        row_kind_map, required_members, optional_members = map_fre_members(ano)
        ingestion_file = register_file(
            db,
            ingestion_run=run,
            source_url=url,
            source_filename=arquivo_zip,
            payload=payload,
            is_zip=True,
        )
        artifact_snapshot = upsert_artifact_snapshot(
            db,
            run=run,
            source_url=url,
            source_filename=arquivo_zip,
            remote_probe=remote_probe,
            ingestion_file=ingestion_file,
            status="downloaded",
        )
        update_run_state(run, phase="stage")
        db.commit()
        db.refresh(run)
        db.refresh(execucao)

        contadores = {
            "lidas": 0,
            "inseridos": 0,
            "atualizados": 0,
            "inalterados": 0,
            "rejeitados": 0,
            "members_invalid_schema": 0,
        }
        seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
        header_map: dict[tuple[str | None, int | None, int | None, Any], Any] = {}
        member_summary = process_zip_members(
            db,
            run=run,
            ingestion_file=ingestion_file,
            artifact_snapshot=artifact_snapshot,
            spec=ZipIngestionSpec(
                tipo_fonte="fre",
                ano=ano,
                ordered_members=_ordered_fre_members(payload, ano=ano),
                required_members=required_members,
                optional_members=optional_members,
                row_kind_by_member=row_kind_map,
                process_member=lambda db_session, context: _process_fre_member(
                    db_session,
                    execucao=execucao,
                    run=run,
                    ano=ano,
                    member=context.member,
                    reconcile_required=context.reconcile_required,
                    promote_enabled=settings.ingestion_promote_enabled,
                    contadores=contadores,
                    seen_by_row_kind=seen_by_row_kind,
                    header_map=header_map,
                    chunk_size=settings.ingestion_promote_batch_size,
                ),
            ),
            contadores=contadores,
            stage_chunk_size=settings.ingestion_stage_batch_size,
        )
        quality_summary = build_quality_summary(db, ingestion_run_id=run.id)
        quality_summary.update(member_summary)
        quality_summary["members_invalid_schema"] = contadores.get("members_invalid_schema", 0)
        quality_summary["reconciled_deleted"] = contadores.get("reconciled_deleted", 0)
        status_execucao, mensagem_status = enforce_quality_gate(quality_summary=quality_summary)
        execucao.total_linhas_lidas = contadores["lidas"]
        execucao.total_inseridos = contadores["inseridos"]
        execucao.total_atualizados = contadores["atualizados"]
        execucao.total_inalterados = contadores["inalterados"]
        execucao.total_rejeitados = contadores["rejeitados"]
        execucao.status = status_execucao
        execucao.finalizada_em = _agora()
        update_run_state(
            run,
            status=status_execucao,
            phase="complete",
            quality_summary=quality_summary,
            change_summary=member_summary.get("change_summary"),
            remote_probe=remote_probe,
            message=mensagem_status,
            finished_at=_agora(),
        )
        artifact_snapshot.status = status_execucao
        db.commit()
        return {
            "execucao_id": str(execucao.id),
            "status": "sucesso",
            "total_linhas_lidas": contadores["lidas"],
            "total_inseridos": contadores["inseridos"],
            "total_atualizados": contadores["atualizados"],
            "total_inalterados": contadores["inalterados"],
            "total_rejeitados": contadores["rejeitados"],
        }
    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = _agora()
        run_erro = db.get(type(run), run.id)
        if run_erro is not None:
            update_run_state(run_erro, status="falha", phase="complete", message=str(exc), finished_at=_agora())
        db.commit()
        raise
