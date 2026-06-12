from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import and_, insert, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.ingestion import IngestionFileMember, IngestionRow, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.dependencies import ensure_identity_graph_ready
from app.services.ingestion.engine import ZipIngestionSpec, process_zip_members
from app.services.ingestion.normalizers import gerar_hash_canonico
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
    iter_staged_member_chunks,
    iter_zip_csv_members,
    register_file,
    update_run_state,
)
from app.services.ingestion.summary import build_contadores_quality_summary, build_quality_summary_snapshot
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
    _equivalente,
    _normalizar_composicao_capital,
    _normalizar_demonstracao,
    _normalizar_documento,
    _normalizar_parecer,
    _registrar_quarentena,
    _upsert_registro,
    _valor_historico,
)


def map_financeiro_members(prefixo: str, ano: int) -> tuple[dict[str, str], set[str]]:
    datasets = listar_datasets(prefixo)
    member_map = {
        item.render_member_name(ano=ano): item.row_kind or "" for item in datasets if item.row_kind is not None
    }
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


def _build_incremental_quality_summary(
    contadores: dict[str, int],
    quality_counters: dict[str, Counter[str] | int],
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason_counts_raw = quality_counters.get("reason_counts", Counter())
    resolver_methods_raw = quality_counters.get("resolver_methods", Counter())
    top_quarantine_files_raw = quality_counters.get("top_quarantine_files", Counter())
    reason_counts = reason_counts_raw if isinstance(reason_counts_raw, Counter) else Counter()
    resolver_methods = resolver_methods_raw if isinstance(resolver_methods_raw, Counter) else Counter()
    top_quarantine_files = (
        top_quarantine_files_raw if isinstance(top_quarantine_files_raw, Counter) else Counter()
    )
    provisional_raw = quality_counters.get("provisional_company_count", 0)
    provisional_count = provisional_raw if isinstance(provisional_raw, int) else 0
    validos = contadores.get("inseridos", 0) + contadores.get("atualizados", 0) + contadores.get("inalterados", 0)
    rejeitados = contadores.get("rejeitados", 0)
    return build_quality_summary_snapshot(
        row_status_counts={"valid": validos, "invalid": rejeitados},
        reason_counts=dict(reason_counts),
        resolver_methods=dict(resolver_methods),
        top_quarantine_files=[
            {"arquivo_origem": arquivo, "total": total} for arquivo, total in top_quarantine_files.most_common(10)
        ],
        provisional_company_count=provisional_count,
        quarantine_total=rejeitados,
        extras=extras,
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
    entidade_db = _upsert_registro(
        db,
        model=model,
        entidade=entidade,
        campos_chave=campos_chave,
        campos_negocio=campos_negocio,
        dados=dados,
        execucao_id=execucao_id,
        contadores=contadores,
    )
    row.promoted_entity = entidade
    row.promoted_entity_id = None if entidade_db is None else entidade_db.id


def _financeiro_promotion_spec(row_kind: str) -> tuple[type[Any], str, tuple[str, ...], set[str]]:
    if row_kind.endswith("_documento"):
        return (
            DocumentoFinanceiro,
            "documentos_financeiros",
            ("tipo_formulario", "id_documento", "versao", "data_referencia"),
            _CAMPOS_NEGOCIO_DOCUMENTOS,
        )
    if row_kind.endswith("_demonstracao"):
        return (
            DemonstracaoFinanceira,
            "demonstracoes_financeiras",
            (
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
            _CAMPOS_NEGOCIO_DEMONSTRACOES,
        )
    if row_kind.endswith("_composicao_capital"):
        return (
            ComposicaoCapital,
            "composicoes_capital",
            ("tipo_formulario", "cnpj_companhia", "data_referencia", "versao"),
            _CAMPOS_NEGOCIO_COMPOSICAO,
        )
    return (
        ParecerFinanceiro,
        "pareceres_financeiros",
        (
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "tipo_relatorio_auditor",
            "tipo_parecer_declaracao",
            "numero_item_parecer_declaracao",
        ),
        _CAMPOS_NEGOCIO_PARECERES,
    )


def _key_tuple(dados: dict[str, Any], campos_chave: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(dados[campo] for campo in campos_chave)


def _build_key_clause(model: type[Any], campos_chave: tuple[str, ...], chaves: list[tuple[Any, ...]]) -> Any:
    return or_(
        *[
            and_(*[getattr(model, campo) == valor for campo, valor in zip(campos_chave, chave, strict=False)])
            for chave in chaves
        ]
    )


def _preparar_dados_promocao(dados: dict[str, Any]) -> dict[str, Any]:
    dados_promocao = dict(dados)
    dados_para_hash = {k: v for k, v in dados_promocao.items() if k not in {"linha_origem"}}
    dados_promocao["hash_origem"] = gerar_hash_canonico(dados_para_hash, campos_ignorados={"hash_origem"})
    return dados_promocao


def _promote_financeiro_chunk(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if not linhas_promovidas:
        return

    model, entidade, campos_chave, campos_negocio = _financeiro_promotion_spec(row_kind)
    agora = _agora()
    preparados = [(row, _preparar_dados_promocao(dados)) for row, dados in linhas_promovidas]
    chaves = list(dict.fromkeys(_key_tuple(dados, campos_chave) for _, dados in preparados))
    existentes = []
    if chaves:
        existentes = list(
            db.execute(select(model).where(_build_key_clause(model, campos_chave, chaves))).scalars()
        )
    existentes_por_chave = {tuple(getattr(item, campo) for campo in campos_chave): item for item in existentes}

    payload_insercao: list[dict[str, Any]] = []
    historicos: list[Any] = []
    entidades_por_linha: dict[tuple[Any, ...], Any] = {}

    for row, dados in preparados:
        chave = _key_tuple(dados, campos_chave)
        existente = existentes_por_chave.get(chave)
        if existente is None:
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
            row.promoted_entity = entidade
            row.promoted_entity_id = novo_id
            continue

        alteracoes: dict[str, tuple[Any, Any]] = {}
        for campo in campos_negocio:
            valor_antigo = getattr(existente, campo)
            valor_novo = dados[campo]
            if not _equivalente(valor_antigo, valor_novo):
                alteracoes[campo] = (valor_antigo, valor_novo)

        existente.sincronizado_em = agora
        existente.arquivo_origem = dados["arquivo_origem"]
        existente.ano_origem = dados["ano_origem"]
        existente.linha_origem = dados["linha_origem"]
        existente.hash_origem = dados["hash_origem"]

        if not alteracoes:
            contadores["inalterados"] += 1
        else:
            for campo, (_, valor_novo) in alteracoes.items():
                setattr(existente, campo, valor_novo)
            existente.alterado_em = agora
            contadores["atualizados"] += 1
            for campo, (valor_antigo, valor_novo) in alteracoes.items():
                historicos.append(
                    {
                        "entidade": entidade,
                        "entidade_id": existente.id,
                        "companhia_id": dados.get("companhia_id"),
                        "campo": campo,
                        "valor_anterior": _valor_historico(valor_antigo),
                        "valor_novo": _valor_historico(valor_novo),
                        "alterado_em": agora,
                        "execucao_sincronizacao_id": execucao_id,
                        "arquivo_origem": dados["arquivo_origem"],
                        "ano_origem": dados["ano_origem"],
                    }
                )
        row.promoted_entity = entidade
        row.promoted_entity_id = existente.id
        entidades_por_linha[chave] = existente

    if payload_insercao:
        db.execute(insert(model), payload_insercao)
    if historicos:
        from app.models.sincronizacao import HistoricoAlteracaoCampo

        db.execute(insert(HistoricoAlteracaoCampo), historicos)


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
    promote_enabled: bool,
    contadores: dict[str, int] | None = None,
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] | None = None,
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any] | None = None,
) -> dict[str, int]:
    if contadores is None:
        contadores = {
            "lidas": 0,
            "inseridos": 0,
            "atualizados": 0,
            "inalterados": 0,
            "rejeitados": 0,
            "members_invalid_schema": 0,
        }
    if seen_by_row_kind is None:
        seen_by_row_kind = {}
    if header_map is None:
        header_map = {}

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
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=schema_result,
                    execucao_sincronizacao_id=execucao.id,
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

            resolver_result = resolve_companhia(
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
            if promote_enabled:
                _promote_financeiro_row(
                    db,
                    row_kind=row_kind,
                    row=row,
                    dados=dados,
                    execucao_id=execucao.id,
                    contadores=contadores,
                )
            else:
                contadores["inalterados"] += 1
            if row_kind.endswith("_documento"):
                if resolver_result.companhia_id is not None:
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
                update_run_state(
                    run, phase="promote", quality_summary=build_contadores_quality_summary(contadores)
                )
                _atualizar_execucao(execucao, contadores)
                db.commit()

    update_run_state(run, phase="promote", quality_summary=build_contadores_quality_summary(contadores))
    return contadores


def _process_financeiro_member(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun,
    member: IngestionFileMember,
    prefixo: str,
    tipo_formulario: str,
    ano: int,
    promote_enabled: bool,
    contadores: dict[str, int],
    quality_counters: dict[str, Counter[str] | int],
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]],
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any],
    chunk_size: int,
) -> tuple[ExecucaoSincronizacao, IngestionRun, IngestionFileMember]:
    reason_counts = quality_counters.setdefault("reason_counts", Counter())
    resolver_methods = quality_counters.setdefault("resolver_methods", Counter())
    top_quarantine_files = quality_counters.setdefault("top_quarantine_files", Counter())
    quality_counters.setdefault("provisional_company_count", 0)
    member_row_kind = db.scalar(
        select(IngestionRow.row_kind)
        .where(IngestionRow.ingestion_file_member_id == member.id)
        .order_by(IngestionRow.linha_origem.asc())
        .limit(1)
    )
    schema_result = validate_member_header(member_row_kind or "desconhecido", member.header)
    update_member_schema_validation(member, result=schema_result)
    db.commit()

    execucao_id = execucao.id
    run_id = run.id
    member_id = member.id

    if schema_result.status == "invalid":
        contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
        for rows in iter_staged_member_chunks(db, member_id=member_id, chunk_size=chunk_size):
            for row in rows:
                contadores["lidas"] += 1
                write_validation_result(db, ingestion_row=row, result=schema_result)
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=schema_result,
                    execucao_sincronizacao_id=execucao_id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao_id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=row.ano_origem or ano,
                    linha_origem=row.linha_origem,
                    motivo=schema_result.reason_code or "schema_inesperado",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                assert isinstance(reason_counts, Counter)
                assert isinstance(top_quarantine_files, Counter)
                reason_counts[schema_result.reason_code or "schema_inesperado"] += 1
                top_quarantine_files[row.arquivo_origem] += 1
            execucao_atual = db.get(ExecucaoSincronizacao, execucao_id)
            run_atual = db.get(IngestionRun, run_id)
            if execucao_atual is not None and run_atual is not None:
                update_run_state(
                    run_atual,
                    phase="promote",
                    quality_summary=_build_incremental_quality_summary(contadores, quality_counters),
                )
                _atualizar_execucao(execucao_atual, contadores)
            db.commit()
            db.expunge_all()
        execucao_recuperada = db.get(ExecucaoSincronizacao, execucao_id)
        run_recuperada = db.get(IngestionRun, run_id)
        member_recuperado = db.get(IngestionFileMember, member_id)
        assert execucao_recuperada is not None and run_recuperada is not None and member_recuperado is not None
        return execucao_recuperada, run_recuperada, member_recuperado

    execucao_final: ExecucaoSincronizacao | None = None
    run_final: IngestionRun | None = None
    member_final: IngestionFileMember | None = None
    for rows in iter_staged_member_chunks(db, member_id=member_id, chunk_size=chunk_size):
        linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]] = []
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
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao_id,
                    legacy_reason=f"normalizacao_invalida: {exc}",
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao_id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=f"normalizacao_invalida: {exc}",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                assert isinstance(reason_counts, Counter)
                assert isinstance(top_quarantine_files, Counter)
                reason_counts["normalizacao_invalida"] += 1
                top_quarantine_files[row.arquivo_origem] += 1
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
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=duplicate_result,
                    execucao_sincronizacao_id=execucao_id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao_id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=duplicate_result.reason_code or "chave_natural_duplicada_conflitante",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                assert isinstance(reason_counts, Counter)
                assert isinstance(top_quarantine_files, Counter)
                reason_counts[duplicate_result.reason_code or "chave_natural_duplicada_conflitante"] += 1
                top_quarantine_files[row.arquivo_origem] += 1
                continue

            resolver_result = resolve_companhia(
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
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao_id,
                )
                _registrar_quarentena(
                    db,
                    execucao_id=execucao_id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=ano,
                    linha_origem=row.linha_origem,
                    motivo=resolver_result.resolution_method or "companhia_nao_encontrada",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] += 1
                assert isinstance(reason_counts, Counter)
                assert isinstance(top_quarantine_files, Counter)
                reason_counts[resolver_result.resolution_method or "companhia_nao_encontrada"] += 1
                top_quarantine_files[row.arquivo_origem] += 1
                continue

            persist_resolution_result(db, ingestion_row=row, result=resolver_result)
            assert isinstance(resolver_methods, Counter)
            resolver_methods[resolver_result.resolution_method or "none"] += 1
            if resolver_result.status == STATUS_PROVISIONAL_CREATED:
                provisional_raw = quality_counters.get("provisional_company_count", 0)
                quality_counters["provisional_company_count"] = (
                    (provisional_raw if isinstance(provisional_raw, int) else 0) + 1
                )
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
            if promote_enabled:
                linhas_promovidas.append((row, dados))
            else:
                contadores["inalterados"] += 1
            if row_kind.endswith("_documento"):
                if resolver_result.companhia_id is not None:
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

        if promote_enabled and linhas_promovidas:
            _promote_financeiro_chunk(
                db,
                row_kind=linhas_promovidas[0][0].row_kind,
                linhas_promovidas=linhas_promovidas,
                execucao_id=execucao_id,
                contadores=contadores,
            )

        execucao_atual = db.get(ExecucaoSincronizacao, execucao_id)
        run_atual = db.get(IngestionRun, run_id)
        if execucao_atual is not None and run_atual is not None:
            update_run_state(
                run_atual,
                phase="promote",
                quality_summary=_build_incremental_quality_summary(contadores, quality_counters),
            )
            _atualizar_execucao(execucao_atual, contadores)
        db.commit()
        db.expunge_all()
        execucao_final = db.get(ExecucaoSincronizacao, execucao_id)
        run_final = db.get(IngestionRun, run_id)
        member_final = db.get(IngestionFileMember, member_id)

    if execucao_final is None or run_final is None or member_final is None:
        execucao_final = db.get(ExecucaoSincronizacao, execucao_id)
        run_final = db.get(IngestionRun, run_id)
        member_final = db.get(IngestionFileMember, member_id)
    if execucao_final is None or run_final is None or member_final is None:
        raise ValueError("estado_execucao_financeiro_inconsistente")
    return execucao_final, run_final, member_final


def _ordered_financeiro_members(
    payload: bytes,
    *,
    prefixo: str,
    ano: int,
) -> list[tuple[str, bytes]]:
    members = iter_zip_csv_members(payload)
    principal = f"{prefixo}_cia_aberta_{ano}.csv"
    return sorted(members, key=lambda item: (0 if item[0] == principal else 1, item[0]))


def _process_financeiro_member_callback(
    db: Session,
    *,
    context_member: IngestionFileMember,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun,
    prefixo: str,
    tipo_formulario: str,
    ano: int,
    promote_enabled: bool,
    contadores: dict[str, int],
    quality_counters: dict[str, Counter[str] | int],
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]],
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any],
    chunk_size: int,
) -> None:
    _process_financeiro_member(
        db,
        execucao=execucao,
        run=run,
        member=context_member,
        prefixo=prefixo,
        tipo_formulario=tipo_formulario,
        ano=ano,
        promote_enabled=promote_enabled,
        contadores=contadores,
        quality_counters=quality_counters,
        seen_by_row_kind=seen_by_row_kind,
        header_map=header_map,
        chunk_size=chunk_size,
    )


def _sincronizar_financeiro(
    db: Session,
    *,
    prefixo: str,
    tipo_formulario: str,
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
    db.commit()
    db.refresh(run)

    try:
        payload = downloader(url)
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = buscar_execucao_hash_existente(
            db,
            tipo_fonte=prefixo,
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
        db.commit()
        db.refresh(run)
        db.refresh(execucao)

        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        quality_counters: dict[str, Counter[str] | int] = {
            "reason_counts": Counter(),
            "resolver_methods": Counter(),
            "top_quarantine_files": Counter(),
            "provisional_company_count": 0,
        }
        seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
        header_map: dict[tuple[str | None, int | None, int | None, Any], Any] = {}
        member_summary = process_zip_members(
            db,
            run=run,
            ingestion_file=ingestion_file,
            spec=ZipIngestionSpec(
                tipo_fonte=prefixo,
                ano=ano,
                ordered_members=_ordered_financeiro_members(payload, prefixo=prefixo, ano=ano),
                required_members=required_members,
                optional_members=set(),
                row_kind_by_member=member_map,
                process_member=lambda db_session, context: _process_financeiro_member_callback(
                    db_session,
                    context_member=context.member,
                    execucao=execucao,
                    run=run,
                    prefixo=prefixo,
                    tipo_formulario=tipo_formulario,
                    ano=ano,
                    promote_enabled=settings.ingestion_promote_enabled,
                    contadores=contadores,
                    quality_counters=quality_counters,
                    seen_by_row_kind=seen_by_row_kind,
                    header_map=header_map,
                    chunk_size=settings.ingestion_promote_batch_size,
                ),
                commit_progress=lambda counters: _atualizar_execucao(execucao, counters),
                commit_after_stage=False,
                commit_after_process=False,
            ),
            contadores=contadores,
            stage_chunk_size=settings.ingestion_stage_batch_size,
        )
        quality_summary = _build_incremental_quality_summary(
            contadores,
            quality_counters,
            extras={
                **member_summary,
                "members_invalid_schema": contadores.get("members_invalid_schema", 0),
            },
        )
        status_execucao, mensagem_status = enforce_quality_gate(quality_summary=quality_summary)
        _atualizar_execucao(execucao, contadores, status=status_execucao)
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


def sincronizar_dfp(
    db: Session,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    return _sincronizar_financeiro(
        db,
        prefixo="dfp",
        tipo_formulario="DFP",
        ano=ano,
        task_id=task_id,
        force_reimport=force_reimport,
        downloader=downloader,
    )


def sincronizar_itr(
    db: Session,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    return _sincronizar_financeiro(
        db,
        prefixo="itr",
        tipo_formulario="ITR",
        ano=ano,
        task_id=task_id,
        force_reimport=force_reimport,
        downloader=downloader,
    )
