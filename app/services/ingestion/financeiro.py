from __future__ import annotations

import hashlib
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.ingestion import IngestionRow
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    persist_resolution_result,
    register_document_header,
    resolve_companhia_v2,
)
from app.services.ingestion.normalizers import gerar_hash_canonico
from app.services.ingestion.staging import (
    create_run,
    register_file,
    stage_zip_payload,
    update_run_state,
)
from app.services.ingestion.validation import (
    build_natural_key,
    classify_duplicate,
    invalid_result,
    update_member_schema_validation,
    validate_member_header,
    write_validation_result,
)
from app.services.sincronizacao_financeiro import (
    _BATCH_COMMIT_LINHAS,
    _CAMPOS_NEGOCIO_COMPOSICAO,
    _CAMPOS_NEGOCIO_DEMONSTRACOES,
    _CAMPOS_NEGOCIO_DOCUMENTOS,
    _CAMPOS_NEGOCIO_PARECERES,
    _agora,
    _atualizar_execucao,
    _normalizar_composicao_capital,
    _normalizar_demonstracao,
    _normalizar_documento,
    _normalizar_parecer,
    _registrar_quarentena,
    _upsert_registro,
)


def map_financeiro_members(prefixo: str, ano: int) -> tuple[dict[str, str], set[str]]:
    member_map = {
        f"{prefixo}_cia_aberta_{ano}.csv": f"{prefixo}_documento",
        f"{prefixo}_cia_aberta_composicao_capital_{ano}.csv": f"{prefixo}_composicao_capital",
        f"{prefixo}_cia_aberta_parecer_{ano}.csv": f"{prefixo}_parecer",
    }
    for nome_arquivo, _, _ in arquivos_demonstracao(prefixo, ano):
        member_map[nome_arquivo] = f"{prefixo}_demonstracao"
    return member_map, set(member_map)


def normalizar_financeiro_row(
    *,
    prefixo: str,
    tipo_formulario: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    linha: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if arquivo_origem == f"{prefixo}_cia_aberta_{ano_origem}.csv":
        return (
            f"{prefixo}_documento",
            _normalizar_documento(
                linha,
                tipo_formulario=tipo_formulario,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                linha_origem=linha_origem,
            ),
        )
    if arquivo_origem == f"{prefixo}_cia_aberta_composicao_capital_{ano_origem}.csv":
        return (
            f"{prefixo}_composicao_capital",
            _normalizar_composicao_capital(
                linha,
                tipo_formulario=tipo_formulario,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                linha_origem=linha_origem,
            ),
        )
    if arquivo_origem == f"{prefixo}_cia_aberta_parecer_{ano_origem}.csv":
        return (
            f"{prefixo}_parecer",
            _normalizar_parecer(
                linha,
                tipo_formulario=tipo_formulario,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                linha_origem=linha_origem,
            ),
        )

    member_map, _ = map_financeiro_members(prefixo, ano_origem)
    if member_map.get(arquivo_origem) != f"{prefixo}_demonstracao":
        raise ValueError(f"arquivo_nao_mapeado: {arquivo_origem}")

    mapa_demonstracoes = {
        nome_arquivo: (tipo_demonstracao, escopo)
        for nome_arquivo, tipo_demonstracao, escopo in arquivos_demonstracao(prefixo, ano_origem)
    }
    tipo_demonstracao, escopo_demonstracao = mapa_demonstracoes[arquivo_origem]
    return (
        f"{prefixo}_demonstracao",
        _normalizar_demonstracao(
            linha,
            tipo_formulario=tipo_formulario,
            tipo_demonstracao=tipo_demonstracao,
            escopo_demonstracao=escopo_demonstracao,
            arquivo_origem=arquivo_origem,
            ano_origem=ano_origem,
            linha_origem=linha_origem,
        ),
    )


def _download(url: str, *, timeout: float) -> bytes:
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content

def _resolver_input_from_data(
    dados: dict[str, Any],
    *,
    tipo_formulario: str,
) -> ResolverInput:
    return ResolverInput(
        cnpj_companhia=dados.get("cnpj_companhia"),
        codigo_cvm=dados.get("codigo_cvm"),
        denominacao_companhia=dados.get("denominacao_companhia"),
        tipo_formulario=tipo_formulario,
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
    _upsert_registro(
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


def _promote_financeiro_row(
    db: Session,
    *,
    row_kind: str,
    row: IngestionRow,
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if row_kind.endswith("_documento"):
        _promote_with_tracking(
            db,
            row=row,
            model=DocumentoFinanceiro,
            entidade="documentos_financeiros",
            campos_chave=("tipo_formulario", "id_documento", "versao", "data_referencia"),
            campos_negocio=_CAMPOS_NEGOCIO_DOCUMENTOS,
            dados=dados,
            execucao_id=execucao_id,
            contadores=contadores,
        )
        return
    if row_kind.endswith("_demonstracao"):
        _promote_with_tracking(
            db,
            row=row,
            model=DemonstracaoFinanceira,
            entidade="demonstracoes_financeiras",
            campos_chave=(
                "tipo_formulario",
                "tipo_demonstracao",
                "escopo_demonstracao",
                "cnpj_companhia",
                "data_referencia",
                "versao",
                "grupo_demonstracao",
                "ordem_exercicio",
                "data_fim_exercicio",
                "codigo_conta",
            ),
            campos_negocio=_CAMPOS_NEGOCIO_DEMONSTRACOES,
            dados=dados,
            execucao_id=execucao_id,
            contadores=contadores,
        )
        return
    if row_kind.endswith("_composicao_capital"):
        _promote_with_tracking(
            db,
            row=row,
            model=ComposicaoCapital,
            entidade="composicoes_capital",
            campos_chave=("tipo_formulario", "cnpj_companhia", "data_referencia", "versao"),
            campos_negocio=_CAMPOS_NEGOCIO_COMPOSICAO,
            dados=dados,
            execucao_id=execucao_id,
            contadores=contadores,
        )
        return
    _promote_with_tracking(
        db,
        row=row,
        model=ParecerFinanceiro,
        entidade="pareceres_financeiros",
        campos_chave=(
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "tipo_relatorio_auditor",
            "tipo_parecer_declaracao",
            "numero_item_parecer_declaracao",
        ),
        campos_negocio=_CAMPOS_NEGOCIO_PARECERES,
        dados=dados,
        execucao_id=execucao_id,
        contadores=contadores,
    )


def _process_financeiro_rows(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: Any,
    prefixo: str,
    tipo_formulario: str,
    ano: int,
    staged_members: list[tuple[Any, list[IngestionRow]]],
) -> dict[str, int]:
    contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any] = {}

    ordered_members = sorted(
        staged_members,
        key=lambda item: (0 if item[0].member_name == f"{prefixo}_cia_aberta_{ano}.csv" else 1, item[0].member_name),
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

        for row in rows:
            contadores["lidas"] += 1
            try:
                row_kind, dados = normalizar_financeiro_row(
                    prefixo=prefixo,
                    tipo_formulario=tipo_formulario,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    linha=row.raw_data,
                )
            except Exception as exc:
                result = invalid_result(
                    "normalizacao_invalida",
                    details={"erro": str(exc)},
                    repairable=False,
                )
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

            resolver_result = resolve_companhia_v2(
                db,
                _resolver_input_from_data(dados, tipo_formulario=tipo_formulario),
                header_map=header_map,
            )
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
            dados["companhia_id"] = resolver_result.companhia_id
            if dados.get("codigo_cvm") is None and resolver_result.companhia_id is not None:
                companhia = db.get(Companhia, resolver_result.companhia_id)
                if companhia is not None:
                    dados["codigo_cvm"] = companhia.codigo_cvm

            write_validation_result(
                db,
                ingestion_row=row,
                result=duplicate_result,
                normalized_data=dados,
                natural_key=natural_key,
            )
            _promote_financeiro_row(
                db,
                row_kind=row_kind,
                row=row,
                dados=dados,
                execucao_id=execucao.id,
                contadores=contadores,
            )
            if row_kind.endswith("_documento"):
                register_document_header(
                    header_map,
                    tipo_formulario=tipo_formulario,
                    id_documento=dados.get("id_documento"),
                    versao=dados.get("versao"),
                    data_referencia=dados.get("data_referencia"),
                    companhia_id=resolver_result.companhia_id,
                    cnpj_companhia=dados.get("cnpj_companhia"),
                    codigo_cvm=dados.get("codigo_cvm"),
                )

            if contadores["lidas"] % _BATCH_COMMIT_LINHAS == 0:
                update_run_state(run, phase="promote", quality_summary=contadores.copy())
                _atualizar_execucao(execucao, contadores)
                db.commit()

    update_run_state(run, phase="promote", quality_summary=contadores.copy())
    return contadores


def _sincronizar_financeiro_v2(
    db: Session,
    *,
    prefixo: str,
    tipo_formulario: str,
    ano: int,
    task_id: str | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    if db.query(Companhia).count() == 0:
        raise ValueError("cadastro_companhias_nao_ingestado")

    settings = get_settings()
    downloader = downloader or (lambda url: _download(url, timeout=300))
    arquivo_zip = f"{prefixo}_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/{tipo_formulario}/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte=prefixo,
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
        tipo_fonte=prefixo,
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
                ExecucaoSincronizacao.tipo_fonte == prefixo,
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

        member_map, required_members = map_financeiro_members(prefixo, ano)
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
            row_kind_by_member=member_map,
        )
        staged_names = {member.member_name for member, _ in staged_members}
        faltando = sorted(required_members - staged_names)
        if faltando:
            raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

        contadores = _process_financeiro_rows(
            db,
            execucao=execucao,
            run=run,
            prefixo=prefixo,
            tipo_formulario=tipo_formulario,
            ano=ano,
            staged_members=staged_members,
        )
        _atualizar_execucao(execucao, contadores, status="sucesso")
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


def sincronizar_dfp_v2(
    db: Session,
    ano: int,
    task_id: str | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    return _sincronizar_financeiro_v2(
        db,
        prefixo="dfp",
        tipo_formulario="DFP",
        ano=ano,
        task_id=task_id,
        downloader=downloader,
    )


def sincronizar_itr_v2(
    db: Session,
    ano: int,
    task_id: str | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    return _sincronizar_financeiro_v2(
        db,
        prefixo="itr",
        tipo_formulario="ITR",
        ano=ano,
        task_id=task_id,
        downloader=downloader,
    )
