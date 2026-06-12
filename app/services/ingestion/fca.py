from __future__ import annotations

import hashlib
import uuid
from typing import Any

import httpx
from sqlalchemy import and_, insert, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.fca import (
    FcaAuditor,
    FcaDepartamentoAcionistas,
    FcaDocumento,
    FcaDri,
    FcaEndereco,
    FcaGeral,
    FcaValorMobiliario,
)
from app.models.ingestion import IngestionRow
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.normalizers import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_cnpj_opcional,
    normalizar_data,
    normalizar_inteiro,
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
from app.services.ingestion.staging import (
    create_run,
    iter_zip_csv_members,
    member_has_successful_match,
    register_file,
    stage_csv_payload,
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
from app.services.sincronizacao_fre import _agora, _digitos, _equivalente, _registrar_quarentena

_BATCH_COMMIT_LINHAS = 5000
_PROMOTE_CHUNK_SIZE = 1000
_PROMOTED_ROW_KINDS = {
    "fca_documento",
    "fca_geral",
    "fca_endereco",
    "fca_dri",
    "fca_auditor",
    "fca_valor_mobiliario",
    "fca_departamento_acionistas",
}


def map_fca_members(ano: int) -> tuple[dict[str, str], dict[str, str], set[str], set[str]]:
    datasets = listar_datasets("fca")
    row_kind_map = {
        item.render_member_name(ano=ano): item.row_kind or "" for item in datasets if item.row_kind is not None
    }
    dataset_map = {item.render_member_name(ano=ano): item.dataset for item in datasets}
    required = {item.render_member_name(ano=ano) for item in datasets if item.obrigatorio}
    optional = {item.render_member_name(ano=ano) for item in datasets if not item.obrigatorio}
    return row_kind_map, dataset_map, required, optional


def _download(url: str, *, timeout: float) -> bytes:
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def normalizar_fca_row(
    *,
    tipo: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    linha: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if tipo == "original":
        data_referencia = normalizar_data(linha.get("DT_REFER"))
        versao = normalizar_inteiro(linha.get("VERSAO"))
        id_documento = normalizar_inteiro(linha.get("ID_DOC"))
        if data_referencia is None or versao is None or id_documento is None:
            raise ValueError("campo_obrigatorio_ausente")
        return (
            "fca_documento",
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
        "nome_empresarial": normalizar_texto(linha.get("Nome_Empresarial")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }

    if tipo == "geral":
        return (
            "fca_geral",
            base
            | {
                "codigo_cvm": normalizar_inteiro(linha.get("Codigo_CVM")),
                "data_nome_empresarial": normalizar_data(linha.get("Data_Nome_Empresarial")),
                "nome_empresarial_anterior": normalizar_texto(linha.get("Nome_Empresarial_Anterior")),
                "data_constituicao": normalizar_data(linha.get("Data_Constituicao")),
                "data_registro_cvm": normalizar_data(linha.get("Data_Registro_CVM")),
                "categoria_registro_cvm": normalizar_texto(linha.get("Categoria_Registro_CVM")),
                "data_categoria_registro_cvm": normalizar_data(linha.get("Data_Categoria_Registro_CVM")),
                "situacao_registro_cvm": normalizar_texto(linha.get("Situacao_Registro_CVM")),
                "data_situacao_registro_cvm": normalizar_data(linha.get("Data_Situacao_Registro_CVM")),
                "pais_origem": normalizar_texto(linha.get("Pais_Origem")),
                "pais_custodia_valores_mobiliarios": normalizar_texto(linha.get("Pais_Custodia_Valores_Mobiliarios")),
                "setor_atividade": normalizar_texto(linha.get("Setor_Atividade")),
                "descricao_atividade": normalizar_texto(linha.get("Descricao_Atividade")),
                "situacao_emissor": normalizar_texto(linha.get("Situacao_Emissor")),
                "data_situacao_emissor": normalizar_data(linha.get("Data_Situacao_Emissor")),
                "especie_controle_acionario": normalizar_texto(linha.get("Especie_Controle_Acionario")),
                "data_especie_controle_acionario": normalizar_data(linha.get("Data_Especie_Controle_Acionario")),
                "dia_encerramento_exercicio_social": normalizar_inteiro(linha.get("Dia_Encerramento_Exercicio_Social")),
                "mes_encerramento_exercicio_social": normalizar_inteiro(linha.get("Mes_Encerramento_Exercicio_Social")),
                "data_alteracao_exercicio_social": normalizar_data(linha.get("Data_Alteracao_Exercicio_Social")),
                "pagina_web": normalizar_texto(linha.get("Pagina_Web")),
            },
        )
    if tipo == "endereco":
        return (
            "fca_endereco",
            base
            | {
                "tipo_endereco": normalizar_texto(linha.get("Tipo_Endereco")),
                "logradouro": normalizar_texto(linha.get("Logradouro")),
                "complemento": normalizar_texto(linha.get("Complemento")),
                "bairro": normalizar_texto(linha.get("Bairro")),
                "cidade": normalizar_texto(linha.get("Cidade")),
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                "pais": normalizar_texto(linha.get("Pais")),
                "cep": _digitos(linha.get("CEP")),
                "caixa_postal": normalizar_texto(linha.get("Caixa_Postal")),
                "ddi_telefone": _digitos(linha.get("DDI_Telefone")),
                "ddd_telefone": _digitos(linha.get("DDD_Telefone")),
                "telefone": _digitos(linha.get("Telefone")),
                "ddi_fax": _digitos(linha.get("DDI_Fax")),
                "ddd_fax": _digitos(linha.get("DDD_Fax")),
                "fax": _digitos(linha.get("Fax")),
                "email": normalizar_texto(linha.get("Email")),
            },
        )
    if tipo == "dri":
        return (
            "fca_dri",
            base
            | {
                "tipo_responsavel": normalizar_texto(linha.get("Tipo_Responsavel")),
                "nome_dri": normalizar_texto(linha.get("Responsavel")),
                "cpf_responsavel": _digitos(linha.get("CPF_Responsavel")),
                "tipo_endereco": normalizar_texto(linha.get("Tipo_Endereco")),
                "logradouro": normalizar_texto(linha.get("Logradouro")),
                "complemento": normalizar_texto(linha.get("Complemento")),
                "bairro": normalizar_texto(linha.get("Bairro")),
                "cidade": normalizar_texto(linha.get("Cidade")),
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                "uf": normalizar_texto(linha.get("UF")),
                "pais": normalizar_texto(linha.get("Pais")),
                "cep": _digitos(linha.get("CEP")),
                "ddi_telefone": _digitos(linha.get("DDI_Telefone")),
                "ddd_telefone": _digitos(linha.get("DDD_Telefone")),
                "telefone": _digitos(linha.get("Telefone")),
                "ddi_fax": _digitos(linha.get("DDI_Fax")),
                "ddd_fax": _digitos(linha.get("DDD_Fax")),
                "fax": _digitos(linha.get("Fax")),
                "email_dri": normalizar_texto(linha.get("Email")),
                "data_inicio_atuacao": normalizar_data(linha.get("Data_Inicio_Atuacao")),
                "data_fim_atuacao": normalizar_data(linha.get("Data_Fim_Atuacao")),
            },
        )
    if tipo == "auditor":
        return (
            "fca_auditor",
            base
            | {
                "nome_auditor": normalizar_texto(linha.get("Auditor")),
                "cpf_cnpj_auditor": _digitos(linha.get("CPF_CNPJ_Auditor")),
                "codigo_cvm_auditor": normalizar_inteiro(linha.get("Codigo_CVM_Auditor")),
                "origem_auditor": normalizar_texto(linha.get("Origem_Auditor")),
                "data_inicio_atuacao_auditor": normalizar_data(linha.get("Data_Inicio_Atuacao_Auditor")),
                "data_fim_atuacao_auditor": normalizar_data(linha.get("Data_Fim_Atuacao_Auditor")),
                "responsavel_tecnico": normalizar_texto(linha.get("Responsavel_Tecnico")),
                "cpf_responsavel_tecnico": _digitos(linha.get("CPF_Responsavel_Tecnico")),
                "data_inicio_atuacao_responsavel_tecnico": normalizar_data(
                    linha.get("Data_Inicio_Atuacao_Responsavel_Tecnico")
                ),
                "data_fim_atuacao_responsavel_tecnico": normalizar_data(
                    linha.get("Data_Fim_Atuacao_Responsavel_Tecnico")
                ),
            },
        )
    if tipo == "valor_mobiliario":
        return (
            "fca_valor_mobiliario",
            base
            | {
                "tipo_valor_mobiliario": normalizar_texto(linha.get("Valor_Mobiliario")),
                "sigla_classe_acao_preferencial": normalizar_texto(linha.get("Sigla_Classe_Acao_Preferencial")),
                "classe_acao_preferencial": normalizar_texto(linha.get("Classe_Acao_Preferencial")),
                "codigo_negociacao": normalizar_texto(linha.get("Codigo_Negociacao")),
                "composicao_bdr_unit": normalizar_texto(linha.get("Composicao_BDR_Unit")),
                "mercado": normalizar_texto(linha.get("Mercado")),
                "sigla_entidade_administradora": normalizar_texto(linha.get("Sigla_Entidade_Administradora")),
                "entidade_administradora": normalizar_texto(linha.get("Entidade_Administradora")),
                "data_inicio_negociacao": normalizar_data(linha.get("Data_Inicio_Negociacao")),
                "data_fim_negociacao": normalizar_data(linha.get("Data_Fim_Negociacao")),
                "segmento": normalizar_texto(linha.get("Segmento")),
                "data_inicio_listagem": normalizar_data(linha.get("Data_Inicio_Listagem")),
                "data_fim_listagem": normalizar_data(linha.get("Data_Fim_Listagem")),
            },
        )
    if tipo == "escriturador":
        return (
            "fca_escriturador",
            base
            | {
                "escriturador": normalizar_texto(linha.get("Escriturador")),
                "cnpj_escriturador": normalizar_cnpj_opcional(linha.get("CNPJ_Escriturador")),
                "tipo_endereco": normalizar_texto(linha.get("Tipo_Endereco")),
                "logradouro": normalizar_texto(linha.get("Logradouro")),
                "complemento": normalizar_texto(linha.get("Complemento")),
                "bairro": normalizar_texto(linha.get("Bairro")),
                "cidade": normalizar_texto(linha.get("Cidade")),
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                "pais": normalizar_texto(linha.get("Pais")),
                "cep": _digitos(linha.get("CEP")),
                "ddi_telefone": _digitos(linha.get("DDI_Telefone")),
                "ddd_telefone": _digitos(linha.get("DDD_Telefone")),
                "telefone": _digitos(linha.get("Telefone")),
                "ddi_fax": _digitos(linha.get("DDI_Fax")),
                "ddd_fax": _digitos(linha.get("DDD_Fax")),
                "fax": _digitos(linha.get("Fax")),
                "email": normalizar_texto(linha.get("Email")),
                "data_inicio_atuacao": normalizar_data(linha.get("Data_Inicio_Atuacao")),
                "data_fim_atuacao": normalizar_data(linha.get("Data_Fim_Atuacao")),
            },
        )
    if tipo == "canal_divulgacao":
        return (
            "fca_canal_divulgacao",
            base
            | {
                "canal_divulgacao": normalizar_texto(linha.get("Canal_Divulgacao")),
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
            },
        )
    if tipo == "departamento_acionistas":
        return (
            "fca_departamento_acionistas",
            base
            | {
                "contato": normalizar_texto(linha.get("Contato")),
                "data_inicio_contato": normalizar_data(linha.get("Data_Inicio_Contato")),
                "data_fim_contato": normalizar_data(linha.get("Data_Fim_Contato")),
                "tipo_endereco": normalizar_texto(linha.get("Tipo_Endereco")),
                "logradouro": normalizar_texto(linha.get("Logradouro")),
                "complemento": normalizar_texto(linha.get("Complemento")),
                "bairro": normalizar_texto(linha.get("Bairro")),
                "cidade": normalizar_texto(linha.get("Cidade")),
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                "pais": normalizar_texto(linha.get("Pais")),
                "cep": _digitos(linha.get("CEP")),
                "ddi_telefone": _digitos(linha.get("DDI_Telefone")),
                "ddd_telefone": _digitos(linha.get("DDD_Telefone")),
                "telefone": _digitos(linha.get("Telefone")),
                "ddi_fax": _digitos(linha.get("DDI_Fax")),
                "ddd_fax": _digitos(linha.get("DDD_Fax")),
                "fax": _digitos(linha.get("Fax")),
                "email": normalizar_texto(linha.get("Email")),
            },
        )
    if tipo == "pais_estrangeiro_negociacao":
        return (
            "fca_pais_estrangeiro_negociacao",
            base
            | {
                "pais": normalizar_texto(linha.get("Pais")),
                "data_admissao_negociacao": normalizar_data(linha.get("Data_Admissao_Negociacao")),
            },
        )
    raise ValueError(f"tipo_fca_nao_suportado: {tipo}")


def _resolver_input_from_data(dados: dict[str, Any]) -> ResolverInput:
    return ResolverInput(
        cnpj_companhia=dados.get("cnpj_companhia"),
        codigo_cvm=dados.get("codigo_cvm"),
        denominacao_companhia=dados.get("denominacao_companhia") or dados.get("nome_empresarial"),
        tipo_formulario="FCA",
        id_documento=dados.get("id_documento"),
        versao=dados.get("versao"),
        data_referencia=dados.get("data_referencia"),
    )


def _fca_promotion_spec(
    row_kind: str, dados: dict[str, Any]
) -> tuple[type[Any] | None, str | None, tuple[str, ...] | None, set[str] | None]:
    if row_kind == "fca_documento":
        return (
            FcaDocumento,
            "fca_documentos",
            ("id_documento", "versao", "data_referencia"),
            {
                "companhia_id",
                "cnpj_companhia",
                "codigo_cvm",
                "denominacao_companhia",
                "categoria_documento",
                "data_recebimento",
                "link_documento",
            },
        )
    if row_kind == "fca_geral":
        return (
            FcaGeral,
            "fca_geral",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia"),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    if row_kind == "fca_endereco":
        return (
            FcaEndereco,
            "fca_enderecos",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "tipo_endereco",
                "logradouro",
                "cep",
            ),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "tipo_endereco",
                "logradouro",
                "cep",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    if row_kind == "fca_dri":
        return (
            FcaDri,
            "fca_dri",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "cpf_responsavel",
                "tipo_responsavel",
            ),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "cpf_responsavel",
                "tipo_responsavel",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    if row_kind == "fca_auditor":
        return (
            FcaAuditor,
            "fca_auditores",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "cpf_cnpj_auditor",
                "codigo_cvm_auditor",
            ),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "cpf_cnpj_auditor",
                "codigo_cvm_auditor",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    if row_kind == "fca_valor_mobiliario":
        return (
            FcaValorMobiliario,
            "fca_valores_mobiliarios",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "tipo_valor_mobiliario",
                "codigo_negociacao",
                "mercado",
            ),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "tipo_valor_mobiliario",
                "codigo_negociacao",
                "mercado",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    if row_kind == "fca_departamento_acionistas":
        return (
            FcaDepartamentoAcionistas,
            "fca_departamentos_acionistas",
            (
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "contato",
                "email",
                "tipo_endereco",
            ),
            set(dados)
            - {
                "id_documento",
                "versao",
                "data_referencia",
                "cnpj_companhia",
                "contato",
                "email",
                "tipo_endereco",
                "arquivo_origem",
                "ano_origem",
                "linha_origem",
                "hash_origem",
            },
        )
    return None, None, None, None


def _key_tuple(dados: dict[str, Any], campos_chave: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(dados[campo] for campo in campos_chave)


def _build_key_clause(model: type[Any], campos_chave: tuple[str, ...], chaves: list[tuple[Any, ...]]) -> Any:
    return or_(
        *[
            and_(*[getattr(model, campo) == valor for campo, valor in zip(campos_chave, chave, strict=False)])
            for chave in chaves
        ]
    )


def _prepare_promocao(dados: dict[str, Any]) -> dict[str, Any]:
    dados_promocao = dict(dados)
    dados_promocao["hash_origem"] = gerar_hash_canonico(
        {k: v for k, v in dados_promocao.items() if k != "linha_origem"}
    )
    return dados_promocao


def _promote_fca_chunk(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if not linhas_promovidas:
        return
    model, entidade, campos_chave, campos_negocio = _fca_promotion_spec(row_kind, linhas_promovidas[0][1])
    if model is None or entidade is None or campos_chave is None or campos_negocio is None:
        contadores["inalterados"] += len(linhas_promovidas)
        return
    agora = _agora()
    preparados = [(row, _prepare_promocao(dados)) for row, dados in linhas_promovidas]
    chaves = list(dict.fromkeys(_key_tuple(dados, campos_chave) for _, dados in preparados))
    existentes: list[Any] = []
    if chaves:
        existentes = list(db.execute(select(model).where(_build_key_clause(model, campos_chave, chaves))).scalars())
    existentes_por_chave = {tuple(getattr(item, campo) for campo in campos_chave): item for item in existentes}
    payload_insercao: list[dict[str, Any]] = []
    historicos: list[dict[str, Any]] = []
    for row, dados in preparados:
        chave = _key_tuple(dados, campos_chave)
        existente = existentes_por_chave.get(chave)
        if existente is None:
            novo_id = uuid.uuid4()
            payload_insercao.append(
                {"id": novo_id, **dados, "criado_em": agora, "sincronizado_em": agora, "alterado_em": agora}
            )
            contadores["inseridos"] += 1
            row.promoted_entity = entidade
            row.promoted_entity_id = novo_id
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
        row.promoted_entity = entidade
        row.promoted_entity_id = existente.id
    if payload_insercao:
        db.execute(insert(model), payload_insercao)
    if historicos:
        db.execute(insert(HistoricoAlteracaoCampo), historicos)


def _promote_fca_row(
    db: Session,
    *,
    row_kind: str,
    row: IngestionRow,
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    _promote_fca_chunk(
        db,
        row_kind=row_kind,
        linhas_promovidas=[(row, dados)],
        execucao_id=execucao_id,
        contadores=contadores,
    )


def _process_fca_rows(
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
    _, member_type_map, _, _ = map_fca_members(ano)
    if contadores is None:
        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    if seen_by_row_kind is None:
        seen_by_row_kind = {}
    if header_map is None:
        header_map = {}
    ordered_members = sorted(
        staged_members,
        key=lambda item: (0 if item[0].member_name == f"fca_cia_aberta_{ano}.csv" else 1, item[0].member_name),
    )
    for member, rows in ordered_members:
        schema_result = validate_member_header(rows[0].row_kind if rows else "desconhecido", member.header)
        update_member_schema_validation(member, result=schema_result)
        if schema_result.status == "invalid":
            for row in rows:
                contadores["lidas"] += 1
                write_validation_result(db, ingestion_row=row, result=schema_result)
                create_quarantine_item(
                    db, ingestion_row=row, result=schema_result, execucao_sincronizacao_id=execucao.id
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=row.ano_origem or ano,
                    linha_origem=row.linha_origem,
                    motivo=schema_result.reason_code or "schema_inesperado",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
            continue

        tipo = member_type_map[member.member_name]
        linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]] = []
        for row in rows:
            contadores["lidas"] += 1
            try:
                row_kind, dados = normalizar_fca_row(
                    tipo=tipo,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    linha=row.raw_data,
                )
            except Exception as exc:
                result = invalid_result("normalizacao_invalida", details={"erro": str(exc)})
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
                natural_key=natural_key,
                normalized_hash=gerar_hash_canonico(dados),
                normalized_data=dados,
                seen_by_key=seen_by_row_kind.setdefault(row_kind, {}),
            )
            if duplicate_result.status == "ignored_duplicate":
                write_validation_result(
                    db, ingestion_row=row, result=duplicate_result, normalized_data=dados, natural_key=natural_key
                )
                contadores["inalterados"] += 1
                continue
            if duplicate_result.status == "invalid":
                write_validation_result(
                    db, ingestion_row=row, result=duplicate_result, normalized_data=dados, natural_key=natural_key
                )
                create_quarantine_item(
                    db, ingestion_row=row, result=duplicate_result, execucao_sincronizacao_id=execucao.id
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
                    db, ingestion_row=row, result=result, normalized_data=dados, natural_key=natural_key
                )
                create_quarantine_item(db, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
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
            if row_kind in {"fca_documento", "fca_geral"} and dados.get("codigo_cvm") is None and companhia is not None:
                dados["codigo_cvm"] = companhia.codigo_cvm

            write_validation_result(
                db, ingestion_row=row, result=duplicate_result, normalized_data=dados, natural_key=natural_key
            )
            if promote_enabled and row_kind in _PROMOTED_ROW_KINDS:
                linhas_promovidas.append((row, dados))
                if len(linhas_promovidas) >= _PROMOTE_CHUNK_SIZE:
                    _promote_fca_chunk(
                        db,
                        row_kind=row_kind,
                        linhas_promovidas=linhas_promovidas,
                        execucao_id=execucao.id,
                        contadores=contadores,
                    )
                    linhas_promovidas = []
            else:
                contadores["inalterados"] += 1

            if row_kind == "fca_documento" and resolver_result.companhia_id is not None:
                register_document_header(
                    header_map,
                    tipo_formulario="FCA",
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
        if promote_enabled and linhas_promovidas:
            _promote_fca_chunk(
                db,
                row_kind=linhas_promovidas[0][0].row_kind,
                linhas_promovidas=linhas_promovidas,
                execucao_id=execucao.id,
                contadores=contadores,
            )

    update_run_state(run, phase="promote", quality_summary=build_contadores_quality_summary(contadores))
    return contadores


def _ordered_fca_members(payload: bytes, *, ano: int) -> list[tuple[str, bytes]]:
    order_map = {item.render_member_name(ano=ano): idx for idx, item in enumerate(listar_datasets("fca"))}
    return sorted(iter_zip_csv_members(payload), key=lambda item: (order_map.get(item[0], 999), item[0]))


def sincronizar_fca(
    db: Session,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    limpar_caches_resolver()
    downloader = downloader or (lambda url: _download(url, timeout=300))
    arquivo_zip = f"fca_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/FCA/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte="fca", ano=ano, id_tarefa=task_id, arquivo=arquivo_zip, url=url, status="em_execucao"
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    run = create_run(
        db,
        tipo_fonte="fca",
        ano=ano,
        execucao_sincronizacao_id=execucao.id,
        requested_by_task_id=task_id,
        phase="acquire",
    )
    db.commit()
    db.refresh(run)

    try:
        payload = downloader(url)
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = buscar_execucao_hash_existente(
            db,
            tipo_fonte="fca",
            ano=ano,
            hash_arquivo=hash_arquivo,
            execucao_atual_id=execucao.id,
        )
        if anterior is not None and not force_reimport:
            execucao.status = "skipped"
            execucao.finalizada_em = _agora()
            update_run_state(run, status="skipped", phase="complete", finished_at=_agora())
            db.commit()
            return {"execucao_id": str(execucao.id), "status": "skipped"}

        row_kind_map, _, required_members, optional_members = map_fca_members(ano)
        ingestion_file = register_file(
            db, ingestion_run=run, source_url=url, source_filename=arquivo_zip, payload=payload, is_zip=True
        )
        update_run_state(run, phase="stage")
        db.commit()
        db.refresh(run)
        db.refresh(execucao)

        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        membros_inalterados = 0
        seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
        header_map: dict[tuple[str | None, int | None, int | None, Any], Any] = {}
        staged_names: set[str] = set()

        for member_name, member_payload in _ordered_fca_members(payload, ano=ano):
            staged_names.add(member_name)
            if member_has_successful_match(
                db,
                tipo_fonte="fca",
                ano=ano,
                member_name=member_name,
                member_sha256=hashlib.sha256(member_payload).hexdigest(),
                current_run_id=run.id,
            ):
                membros_inalterados += 1
                update_run_state(
                    run,
                    phase="stage",
                    quality_summary=build_contadores_quality_summary(
                        contadores,
                        extras={"members_skipped": membros_inalterados},
                    ),
                )
                db.commit()
                db.refresh(run)
                db.refresh(execucao)
                continue
            member, rows = stage_csv_payload(
                db,
                ingestion_run=run,
                ingestion_file=ingestion_file,
                payload=member_payload,
                member_name=member_name,
                arquivo_origem=member_name,
                ano_origem=ano,
                row_kind=row_kind_map.get(member_name, "desconhecido"),
            )
            update_run_state(run, phase="stage")
            db.commit()
            db.refresh(run)
            db.refresh(execucao)
            _process_fca_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
            )
            db.commit()
            db.refresh(run)
            db.refresh(execucao)

        faltando = sorted(required_members - optional_members - staged_names)
        if faltando:
            raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")
        quality_summary = build_quality_summary(db, ingestion_run_id=run.id)
        quality_summary["members_skipped"] = membros_inalterados
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
            message=mensagem_status,
            finished_at=_agora(),
        )
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
