from __future__ import annotations

import hashlib
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.models.ingestion import IngestionRow
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.normalizers import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_cnpj_opcional,
    normalizar_data,
    normalizar_decimal_cvm,
    normalizar_inteiro,
    normalizar_texto,
)
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    persist_resolution_result,
    register_document_header,
    resolve_companhia_v2,
)
from app.services.ingestion.staging import create_run, register_file, stage_zip_payload, update_run_state
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
    _arquivos_fre_mvp,
    _arquivos_fre_opcionais,
    _digitos,
    _normalizar_booleano,
    _registrar_quarentena,
    _upsert,
)

_BATCH_COMMIT_LINHAS = 5000


def map_fre_members(ano: int) -> tuple[dict[str, str], set[str], set[str]]:
    tipos = _arquivos_fre_mvp(ano)
    row_kind_map = {
        nome: {
            "documentos": "fre_documento",
            "auditores": "fre_auditor",
            "capital_social": "fre_capital_social",
            "posicao_acionaria": "fre_posicao_acionaria",
            "remuneracao_total_orgao": "fre_remuneracao_total_orgao",
            "empregado_posicao_genero": "fre_empregado_posicao_genero",
        }[tipo]
        for nome, tipo in tipos.items()
    }
    return row_kind_map, set(tipos), _arquivos_fre_opcionais(ano)


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
                "codigo_cvm_auditor": normalizar_inteiro(linha.get("Codigo_CVM_Auditor")),
                "tipo_origem_auditor": normalizar_texto(linha.get("Tipo_Origem_Auditor")),
                "data_inicio_contratacao": normalizar_data(linha.get("Data_Inicio_Contratacao")),
                "data_fim_contratacao": normalizar_data(linha.get("Data_Fim_Contratacao")),
                "data_inicio_prestacao_servico": normalizar_data(linha.get("Data_Inicio_Prestacao_Servico")),
                "servico_contratado": normalizar_texto(linha.get("Servico_Contratado")),
                "remuneracao_auditor": normalizar_decimal_cvm(linha.get("Remuneracao_Auditor")),
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
                "quantidade_acoes_preferenciais": normalizar_decimal_cvm(
                    linha.get("Quantidade_Acoes_Preferenciais")
                ),
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
                "tipo_pessoa_acionista_relacionado": normalizar_texto(
                    linha.get("Tipo_Pessoa_Acionista_Relacionado")
                ),
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
                "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                "residente_exterior": _normalizar_booleano(linha.get("Residente_Exterior")),
                "representante_legal": normalizar_texto(linha.get("Representante_Legal")),
                "tipo_pessoa_representante_legal": normalizar_texto(
                    linha.get("Tipo_Pessoa_Representante_Legal")
                ),
                "cpf_cnpj_representante_legal": _digitos(linha.get("CPF_CNPJ_Representante_legal")),
                "data_composicao_capital_social": normalizar_data(linha.get("Data_Composicao_Capital_Social")),
                "data_ultima_alteracao": normalizar_data(linha.get("Data_Ultima_Alteracao")),
                "acionista_controlador": _normalizar_booleano(linha.get("Acionista_Controlador")),
                "participante_acordo_acionistas": _normalizar_booleano(
                    linha.get("Participante_Acordo_Acionistas")
                ),
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
                "beneficios_diretos_indiretos": normalizar_decimal_cvm(
                    linha.get("Beneficios_Diretos_Indiretos")
                ),
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


def _promote_with_tracking(
    db: Session,
    *,
    row: IngestionRow,
    model: type[Any],
    entidade: str,
    campos_chave: tuple[str, ...],
    campos_negocio: set[str],
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    _upsert(
        db,
        model=model,
        entidade=entidade,
        campos_chave=campos_chave,
        campos_negocio=campos_negocio,
        dados=dados,
        execucao_id=execucao_id,
        contadores=contadores,
    )
    filtros = [getattr(model, campo) == dados[campo] for campo in campos_chave]
    entidade_db = db.scalar(select(model).where(*filtros))
    row.promoted_entity = entidade
    row.promoted_entity_id = None if entidade_db is None else entidade_db.id


def _promote_fre_row(
    db: Session,
    *,
    row_kind: str,
    row: IngestionRow,
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if row_kind == "fre_documento":
        _promote_with_tracking(
            db,
            row=row,
            model=FreDocumento,
            entidade="fre_documentos",
            campos_chave=("id_documento", "versao", "data_referencia"),
            campos_negocio={
                "companhia_id",
                "cnpj_companhia",
                "codigo_cvm",
                "data_referencia",
                "versao",
                "denominacao_companhia",
                "categoria_documento",
                "id_documento",
                "data_recebimento",
                "link_documento",
            },
            dados=dados,
            execucao_id=execucao_id,
            contadores=contadores,
        )
        return
    if row_kind == "fre_auditor":
        model, entidade, campos_chave = (
            FreAuditor,
            "fre_auditores",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_auditor"),
        )
    elif row_kind == "fre_capital_social":
        model, entidade, campos_chave = (
            FreCapitalSocial,
            "fre_capital_social",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_capital_social"),
        )
    elif row_kind == "fre_posicao_acionaria":
        model, entidade, campos_chave = (
            FrePosicaoAcionaria,
            "fre_posicoes_acionarias",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "id_acionista"),
        )
    elif row_kind == "fre_remuneracao_total_orgao":
        model, entidade, campos_chave = (
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
    else:
        model, entidade, campos_chave = (
            FreEmpregadoPosicaoGenero,
            "fre_empregados_posicao_genero",
            ("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao"),
        )

    _promote_with_tracking(
        db,
        row=row,
        model=model,
        entidade=entidade,
        campos_chave=campos_chave,
        campos_negocio=set(dados.keys()) - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
        dados=dados,
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
) -> dict[str, int]:
    member_type_map = _arquivos_fre_mvp(ano)
    contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any] = {}

    ordered_members = sorted(
        staged_members,
        key=lambda item: (0 if item[0].member_name == f"fre_cia_aberta_{ano}.csv" else 1, item[0].member_name),
    )

    for member, rows in ordered_members:
        schema_result = validate_member_header(rows[0].row_kind if rows else "desconhecido", member.header)
        update_member_schema_validation(member, result=schema_result)
        if schema_result.status == "invalid":
            for row in rows:
                contadores["lidas"] += 1
                write_validation_result(db, ingestion_row=row, result=schema_result)
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
                result = invalid_result("normalizacao_invalida", details={"erro": str(exc)})
                write_validation_result(db, ingestion_row=row, result=result)
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

            resolver_result = resolve_companhia_v2(db, _resolver_input_from_data(dados), header_map=header_map)
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
            _promote_fre_row(
                db,
                row_kind=row_kind,
                row=row,
                dados=dados,
                execucao_id=execucao.id,
                contadores=contadores,
            )
            if row_kind == "fre_documento":
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
                update_run_state(run, phase="promote", quality_summary=contadores.copy())
                execucao.total_linhas_lidas = contadores["lidas"]
                execucao.total_inseridos = contadores["inseridos"]
                execucao.total_atualizados = contadores["atualizados"]
                execucao.total_inalterados = contadores["inalterados"]
                execucao.total_rejeitados = contadores["rejeitados"]
                db.commit()

    update_run_state(run, phase="promote", quality_summary=contadores.copy())
    return contadores


def sincronizar_fre_v2(
    db: Session,
    ano: int,
    task_id: str | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    if db.query(Companhia).count() == 0:
        raise ValueError("cadastro_companhias_nao_ingestado")

    settings = get_settings()
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

    try:
        payload = downloader(url)
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = db.scalar(
            select(ExecucaoSincronizacao).where(
                ExecucaoSincronizacao.tipo_fonte == "fre",
                ExecucaoSincronizacao.ano == ano,
                ExecucaoSincronizacao.hash_arquivo == hash_arquivo,
                ExecucaoSincronizacao.status == "sucesso",
                ExecucaoSincronizacao.id != execucao.id,
            )
        )
        if anterior is not None:
            execucao.status = "sem_alteracao"
            execucao.finalizada_em = _agora()
            update_run_state(run, status="sem_alteracao", phase="complete", finished_at=_agora())
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
        update_run_state(run, phase="stage")
        staged_members = stage_zip_payload(
            db,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=payload,
            ano_origem=ano,
            row_kind_by_member=row_kind_map,
        )
        staged_names = {member.member_name for member, _ in staged_members}
        faltando = sorted(required_members - optional_members - staged_names)
        if faltando:
            raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

        contadores = _process_fre_rows(
            db,
            execucao=execucao,
            run=run,
            ano=ano,
            staged_members=staged_members,
        )
        execucao.total_linhas_lidas = contadores["lidas"]
        execucao.total_inseridos = contadores["inseridos"]
        execucao.total_atualizados = contadores["atualizados"]
        execucao.total_inalterados = contadores["inalterados"]
        execucao.total_rejeitados = contadores["rejeitados"]
        execucao.status = "sucesso"
        execucao.finalizada_em = _agora()
        update_run_state(run, status="sucesso", phase="complete", quality_summary=contadores.copy(), finished_at=_agora())
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
