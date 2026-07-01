from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from typing import Any

import httpx
from sqlalchemy import case, insert, or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import identity_key

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.ingestion import (
    IngestionFileMember,
    IngestionFinanceiroStageRow,
    IngestionRow,
    IngestionRun,
    SourceArtifactSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.acquisition import annotate_probe_with_sha_confirmation, probe_remote_source
from app.services.ingestion.artifact_store import describe_member_artifact, member_artifact_exists, read_member_artifact
from app.services.ingestion.change_tracking import reconcile_promoted_rows
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.dependencies import ensure_identity_graph_ready
from app.services.ingestion.engine import ZipIngestionSpec, process_zip_members
from app.services.ingestion.lifecycle import (
    build_custom_remote_probe,
    extract_delivery_rows,
    record_member_snapshot,
    resolve_delivery_index_role,
    upsert_artifact_snapshot,
)
from app.services.ingestion.normalized_artifacts import NormalizedArtifactWriter
from app.services.ingestion.normalizers import gerar_hash_canonico
from app.services.ingestion.operational import record_phase_artifact, touch_run_heartbeat
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
from app.services.ingestion.source_registry import dataset_por_member_name, listar_datasets
from app.services.ingestion.sql_batches import iter_lookup_batches, iter_parameter_batches, mapping_parameter_width
from app.services.ingestion.staging import (
    create_run,
    insert_rows,
    iter_csv_rows_from_disk,
    iter_staged_member_chunks,
    iter_zip_csv_members,
    register_file,
    register_member,
    safe_promote_chunk,
    update_run_state,
)
from app.services.ingestion.summary import build_contadores_quality_summary, build_quality_summary_snapshot
from app.services.ingestion.typed_staging import clear_financeiro_stage_rows, load_financeiro_artifact_to_stage
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
    typed_stage_rows_loaded_raw = quality_counters.get("typed_stage_rows_loaded", 0)
    typed_stage_bytes_loaded_raw = quality_counters.get("typed_stage_bytes_loaded", 0)
    typed_stage_rows_replaced_raw = quality_counters.get("typed_stage_rows_replaced", 0)
    typed_stage_rows_purged_raw = quality_counters.get("typed_stage_rows_purged", 0)
    typed_stage_copy_loads_raw = quality_counters.get("typed_stage_copy_loads", 0)
    typed_stage_rows_loaded = typed_stage_rows_loaded_raw if isinstance(typed_stage_rows_loaded_raw, int) else 0
    typed_stage_bytes_loaded = typed_stage_bytes_loaded_raw if isinstance(typed_stage_bytes_loaded_raw, int) else 0
    typed_stage_rows_replaced = (
        typed_stage_rows_replaced_raw if isinstance(typed_stage_rows_replaced_raw, int) else 0
    )
    typed_stage_rows_purged = typed_stage_rows_purged_raw if isinstance(typed_stage_rows_purged_raw, int) else 0
    typed_stage_copy_loads = typed_stage_copy_loads_raw if isinstance(typed_stage_copy_loads_raw, int) else 0
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
        extras={
            "reconciled_deleted": contadores.get("reconciled_deleted", 0),
            "typed_stage_rows_loaded": typed_stage_rows_loaded,
            "typed_stage_bytes_loaded": typed_stage_bytes_loaded,
            "typed_stage_rows_replaced": typed_stage_rows_replaced,
            "typed_stage_rows_purged": typed_stage_rows_purged,
            "typed_stage_copy_loads": typed_stage_copy_loads,
            **(extras or {}),
        },
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
                "data_inicio_exercicio",
                "data_fim_exercicio",
                "codigo_conta",
                "coluna_df",
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


def _build_key_clause(model: type[Any], campos_chave: tuple[str, ...], chaves: Sequence[tuple[Any, ...]]) -> Any:
    if len(campos_chave) == 1:
        return getattr(model, campos_chave[0]).in_([chave[0] for chave in chaves])
    return tuple_(*[getattr(model, campo) for campo in campos_chave]).in_(list(chaves))


def _load_existing_rows(
    db: Session,
    *,
    model: type[Any],
    campos_chave: tuple[str, ...],
    campos_negocio: Collection[str],
    chaves: list[tuple[Any, ...]],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not chaves:
        return {}
    campos_select = tuple(dict.fromkeys(("id", *campos_chave, *campos_negocio)))
    colunas = [getattr(model, campo) for campo in campos_select]
    existentes: dict[tuple[Any, ...], dict[str, Any]] = {}
    for batch in iter_lookup_batches(chaves, parameter_width=len(campos_chave)):
        rows = db.execute(select(*colunas).where(_build_key_clause(model, campos_chave, batch))).mappings()
        for row in rows:
            item = dict(row)
            existentes[tuple(item[campo] for campo in campos_chave)] = item
    return existentes


def _load_existing_row_hashes(
    db: Session,
    *,
    model: type[Any],
    campos_chave: tuple[str, ...],
    chaves: list[tuple[Any, ...]],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not chaves:
        return {}
    campos_select = ("id", *campos_chave, "hash_origem")
    colunas = [getattr(model, campo) for campo in campos_select]
    existentes: dict[tuple[Any, ...], dict[str, Any]] = {}
    for batch in iter_lookup_batches(chaves, parameter_width=len(campos_chave)):
        rows = db.execute(select(*colunas).where(_build_key_clause(model, campos_chave, batch))).mappings()
        for row in rows:
            item = dict(row)
            existentes[tuple(item[campo] for campo in campos_chave)] = item
    return existentes


def _expire_updated_instances(db: Session, model: type[Any], ids: Iterable[Any]) -> None:
    for item_id in ids:
        instance = db.identity_map.get(identity_key(class_=model, ident=(item_id,)))
        if instance is not None:
            db.expire(instance)


def _is_postgresql(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _preparar_dados_promocao(dados: dict[str, Any]) -> dict[str, Any]:
    dados_promocao = dict(dados)
    dados_para_hash = {k: v for k, v in dados_promocao.items() if k not in {"linha_origem"}}
    dados_promocao["hash_origem"] = gerar_hash_canonico(dados_para_hash, campos_ignorados={"hash_origem"})
    return dados_promocao


def _filtrar_payload_promocao_por_modelo(model: type[Any], dados: dict[str, Any]) -> dict[str, Any]:
    colunas_modelo = set(model.__table__.columns.keys())
    return {chave: valor for chave, valor in dados.items() if chave in colunas_modelo}


def _promote_financeiro_payloads_internal(
    db: Session,
    *,
    row_kind: str,
    dados_promovidos: list[dict[str, Any]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if not dados_promovidos:
        return

    if _is_postgresql(db):
        _promote_financeiro_payloads_postgresql(
            db,
            row_kind=row_kind,
            dados_promovidos=dados_promovidos,
            execucao_id=execucao_id,
            contadores=contadores,
        )
        return

    _promote_financeiro_payloads_fallback(
        db,
        row_kind=row_kind,
        dados_promovidos=dados_promovidos,
        execucao_id=execucao_id,
        contadores=contadores,
    )


def _promote_financeiro_payloads_postgresql(
    db: Session,
    *,
    row_kind: str,
    dados_promovidos: list[dict[str, Any]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    model, entidade, campos_chave, campos_negocio = _financeiro_promotion_spec(row_kind)
    agora = _agora()
    preparados = [
        _preparar_dados_promocao(_filtrar_payload_promocao_por_modelo(model, dados)) for dados in dados_promovidos
    ]
    preparados_por_chave: dict[tuple[Any, ...], dict[str, Any]] = {}
    for dados in preparados:
        preparados_por_chave[_key_tuple(dados, campos_chave)] = dados
    preparados_unicos = list(preparados_por_chave.values())
    chaves = list(preparados_por_chave)
    existentes_hash_por_chave = _load_existing_row_hashes(
        db,
        model=model,
        campos_chave=campos_chave,
        chaves=chaves,
    )
    chaves_com_mudanca = [
        chave
        for chave, dados in preparados_por_chave.items()
        if (existente := existentes_hash_por_chave.get(chave)) is not None
        and existente["hash_origem"] != dados["hash_origem"]
    ]
    existentes_por_chave = _load_existing_rows(
        db,
        model=model,
        campos_chave=campos_chave,
        campos_negocio=campos_negocio,
        chaves=chaves_com_mudanca,
    )

    historicos: list[Any] = []
    payload_upsert: list[dict[str, Any]] = []
    for dados in preparados_unicos:
        chave = _key_tuple(dados, campos_chave)
        existente_hash = existentes_hash_por_chave.get(chave)
        if existente_hash is None:
            contadores["inseridos"] += 1
            row_id = uuid.uuid4()
        elif existente_hash["hash_origem"] == dados["hash_origem"]:
            contadores["inalterados"] += 1
            row_id = existente_hash["id"]
        else:
            row_id = existente_hash["id"]
            existente = existentes_por_chave[chave]
            houve_alteracao = False
            for campo in campos_negocio:
                valor_antigo = existente[campo]
                valor_novo = dados[campo]
                if _equivalente(valor_antigo, valor_novo):
                    continue
                houve_alteracao = True
                historicos.append(
                    {
                        "entidade": entidade,
                        "entidade_id": existente["id"],
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
            if houve_alteracao:
                contadores["atualizados"] += 1
            else:
                contadores["inalterados"] += 1

        payload_upsert.append(
            {
                "id": row_id,
                **dados,
                "criado_em": agora,
                "sincronizado_em": agora,
                "alterado_em": agora,
            }
        )

    if payload_upsert:
        for batch in iter_parameter_batches(payload_upsert, parameter_width=mapping_parameter_width(payload_upsert)):
            stmt = pg_insert(model).values(batch)
            business_change_expression = or_(
                *[
                    getattr(model, campo).is_distinct_from(getattr(stmt.excluded, campo))
                    for campo in sorted(campos_negocio)
                ]
            )
            update_columns = {
                campo: getattr(stmt.excluded, campo)
                for campo in sorted(
                    {
                        *campos_negocio,
                        "arquivo_origem",
                        "ano_origem",
                        "linha_origem",
                        "hash_origem",
                        "sincronizado_em",
                    }
                )
            }
            update_columns["alterado_em"] = case(
                (
                    business_change_expression,
                    stmt.excluded.alterado_em,
                ),
                else_=model.alterado_em,
            )
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=[getattr(model, campo) for campo in campos_chave],
                    set_=update_columns,
                )
            )
        db.flush()

    if historicos:
        from app.models.sincronizacao import HistoricoAlteracaoCampo

        for batch in iter_parameter_batches(historicos, parameter_width=mapping_parameter_width(historicos)):
            db.execute(insert(HistoricoAlteracaoCampo), batch)


def _promote_financeiro_payloads_fallback(
    db: Session,
    *,
    row_kind: str,
    dados_promovidos: list[dict[str, Any]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    model, entidade, campos_chave, campos_negocio = _financeiro_promotion_spec(row_kind)
    agora = _agora()
    preparados = [
        _preparar_dados_promocao(_filtrar_payload_promocao_por_modelo(model, dados)) for dados in dados_promovidos
    ]
    chaves = list(dict.fromkeys(_key_tuple(dados, campos_chave) for dados in preparados))
    existentes_hash_por_chave = _load_existing_row_hashes(
        db,
        model=model,
        campos_chave=campos_chave,
        chaves=chaves,
    )
    chaves_com_mudanca = list(
        dict.fromkeys(
            chave
            for dados in preparados
            if (chave := _key_tuple(dados, campos_chave)) in existentes_hash_por_chave
            and existentes_hash_por_chave[chave]["hash_origem"] != dados["hash_origem"]
        )
    )
    existentes_por_chave = _load_existing_rows(
        db,
        model=model,
        campos_chave=campos_chave,
        campos_negocio=campos_negocio,
        chaves=chaves_com_mudanca,
    )

    payload_insercao: list[dict[str, Any]] = []
    historicos: list[Any] = []
    chaves_no_lote: dict[tuple[Any, ...], dict[str, Any]] = {}
    payload_atualizacao: dict[Any, dict[str, Any]] = {}
    for dados in preparados:
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
        existente_hash = existentes_hash_por_chave.get(chave)
        if existente_hash is None:
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
        if existente_hash["hash_origem"] == dados["hash_origem"]:
            atualizacao = payload_atualizacao.setdefault(
                existente_hash["id"],
                {
                    "id": existente_hash["id"],
                    "sincronizado_em": agora,
                    "arquivo_origem": dados["arquivo_origem"],
                    "ano_origem": dados["ano_origem"],
                    "linha_origem": dados["linha_origem"],
                    "hash_origem": dados["hash_origem"],
                },
            )
            atualizacao["sincronizado_em"] = agora
            atualizacao["arquivo_origem"] = dados["arquivo_origem"]
            atualizacao["ano_origem"] = dados["ano_origem"]
            atualizacao["linha_origem"] = dados["linha_origem"]
            atualizacao["hash_origem"] = dados["hash_origem"]
            contadores["inalterados"] += 1
            continue

        existente = existentes_por_chave[chave]
        alteracoes: dict[str, tuple[Any, Any]] = {}
        for campo in campos_negocio:
            valor_antigo = existente[campo]
            valor_novo = dados[campo]
            if not _equivalente(valor_antigo, valor_novo):
                alteracoes[campo] = (valor_antigo, valor_novo)

        atualizacao = payload_atualizacao.setdefault(
            existente["id"],
            {
                "id": existente["id"],
                "sincronizado_em": agora,
                "arquivo_origem": dados["arquivo_origem"],
                "ano_origem": dados["ano_origem"],
                "linha_origem": dados["linha_origem"],
                "hash_origem": dados["hash_origem"],
            },
        )
        atualizacao["sincronizado_em"] = agora
        atualizacao["arquivo_origem"] = dados["arquivo_origem"]
        atualizacao["ano_origem"] = dados["ano_origem"]
        atualizacao["linha_origem"] = dados["linha_origem"]
        atualizacao["hash_origem"] = dados["hash_origem"]
        existente["sincronizado_em"] = agora
        existente["arquivo_origem"] = dados["arquivo_origem"]
        existente["ano_origem"] = dados["ano_origem"]
        existente["linha_origem"] = dados["linha_origem"]
        existente["hash_origem"] = dados["hash_origem"]

        if not alteracoes:
            contadores["inalterados"] += 1
        else:
            for campo, (_, valor_novo) in alteracoes.items():
                atualizacao[campo] = valor_novo
                existente[campo] = valor_novo
            atualizacao["alterado_em"] = agora
            existente["alterado_em"] = agora
            contadores["atualizados"] += 1
            for campo, (valor_antigo, valor_novo) in alteracoes.items():
                historicos.append(
                    {
                        "entidade": entidade,
                        "entidade_id": existente["id"],
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

    if payload_insercao:
        for batch in iter_parameter_batches(payload_insercao, parameter_width=mapping_parameter_width(payload_insercao)):
            if _is_postgresql(db):
                db.execute(pg_insert(model).values(batch).on_conflict_do_nothing())
                db.flush()
            else:
                db.execute(insert(model), batch)
    if payload_atualizacao:
        db.bulk_update_mappings(model, list(payload_atualizacao.values()))
        _expire_updated_instances(db, model, payload_atualizacao.keys())
    if historicos:
        from app.models.sincronizacao import HistoricoAlteracaoCampo

        for batch in iter_parameter_batches(historicos, parameter_width=mapping_parameter_width(historicos)):
            db.execute(insert(HistoricoAlteracaoCampo), batch)


def _promote_financeiro_chunk(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    safe_promote_chunk(
        db,
        promote_func=_promote_financeiro_chunk_internal,
        linhas_promovidas=linhas_promovidas,
        execucao_id=execucao_id,
        contadores=contadores,
        registrar_quarentena_fn=_registrar_quarentena,
        row_kind=row_kind,
    )


def _promote_financeiro_chunk_internal(
    db: Session,
    *,
    row_kind: str,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    _promote_financeiro_payloads_internal(
        db,
        row_kind=row_kind,
        dados_promovidos=[dados for _row, dados in linhas_promovidas],
        execucao_id=execucao_id,
        contadores=contadores,
    )


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


def _stage_row_to_promocao_payload(stage_row: IngestionFinanceiroStageRow) -> dict[str, Any]:
    return {
        "companhia_id": stage_row.companhia_id,
        "tipo_formulario": stage_row.tipo_formulario,
        "cnpj_companhia": stage_row.cnpj_companhia,
        "codigo_cvm": stage_row.codigo_cvm,
        "data_referencia": stage_row.data_referencia,
        "versao": stage_row.versao,
        "denominacao_companhia": stage_row.denominacao_companhia,
        "categoria_documento": stage_row.categoria_documento,
        "id_documento": stage_row.id_documento,
        "data_recebimento": stage_row.data_recebimento,
        "link_documento": stage_row.link_documento,
        "tipo_demonstracao": stage_row.tipo_demonstracao,
        "escopo_demonstracao": stage_row.escopo_demonstracao,
        "grupo_demonstracao": stage_row.grupo_demonstracao,
        "moeda": stage_row.moeda,
        "escala_moeda": stage_row.escala_moeda,
        "ordem_exercicio": stage_row.ordem_exercicio,
        "data_inicio_exercicio": stage_row.data_inicio_exercicio,
        "data_fim_exercicio": stage_row.data_fim_exercicio,
        "codigo_conta": stage_row.codigo_conta,
        "coluna_df": stage_row.coluna_df or "",
        "descricao_conta": stage_row.descricao_conta,
        "valor_conta": stage_row.valor_conta,
        "conta_fixa": stage_row.conta_fixa,
        "quantidade_acoes_ordinarias_capital_integralizado": stage_row.quantidade_acoes_ordinarias_capital_integralizado,
        "quantidade_acoes_preferenciais_capital_integralizado": stage_row.quantidade_acoes_preferenciais_capital_integralizado,
        "quantidade_total_acoes_capital_integralizado": stage_row.quantidade_total_acoes_capital_integralizado,
        "quantidade_acoes_ordinarias_tesouraria": stage_row.quantidade_acoes_ordinarias_tesouraria,
        "quantidade_acoes_preferenciais_tesouraria": stage_row.quantidade_acoes_preferenciais_tesouraria,
        "quantidade_total_acoes_tesouraria": stage_row.quantidade_total_acoes_tesouraria,
        "tipo_relatorio_auditor": stage_row.tipo_relatorio_auditor,
        "tipo_parecer_declaracao": stage_row.tipo_parecer_declaracao,
        "numero_item_parecer_declaracao": stage_row.numero_item_parecer_declaracao,
        "texto_parecer_declaracao": stage_row.texto_parecer_declaracao,
        "arquivo_origem": stage_row.arquivo_origem,
        "ano_origem": stage_row.ano_origem,
        "linha_origem": stage_row.linha_origem,
    }


def _iter_financeiro_stage_chunks(
    db: Session,
    *,
    ingestion_file_member_id: Any,
    row_kind: str,
    chunk_size: int,
) -> Iterable[list[IngestionFinanceiroStageRow]]:
    last_line = 0
    while True:
        query = (
            select(IngestionFinanceiroStageRow)
            .where(
                IngestionFinanceiroStageRow.ingestion_file_member_id == ingestion_file_member_id,
                IngestionFinanceiroStageRow.row_kind == row_kind,
                IngestionFinanceiroStageRow.linha_origem > last_line,
            )
            .order_by(IngestionFinanceiroStageRow.linha_origem.asc())
            .limit(chunk_size)
        )
        chunk = list(db.execute(query).scalars())
        if not chunk:
            break
        yield chunk
        last_line = chunk[-1].linha_origem
        for item in chunk:
            db.expunge(item)


def _promote_financeiro_member_from_stage(
    db: Session,
    *,
    member_id: Any,
    run_id: Any | None = None,
    execucao_id: Any,
    contadores: dict[str, int],
    chunk_size: int,
) -> None:
    if _is_postgresql(db):
        _promote_financeiro_member_from_stage_postgresql(
            db,
            member_id=member_id,
            run_id=run_id,
            execucao_id=execucao_id,
            contadores=contadores,
            chunk_size=chunk_size,
        )
        return

    _promote_financeiro_member_from_stage_fallback(
        db,
        member_id=member_id,
        run_id=run_id,
        execucao_id=execucao_id,
        contadores=contadores,
        chunk_size=chunk_size,
    )


def _promote_financeiro_member_from_stage_postgresql(
    db: Session,
    *,
    member_id: Any,
    run_id: Any | None = None,
    execucao_id: Any,
    contadores: dict[str, int],
    chunk_size: int,
) -> None:
    row_kinds = list(
        db.execute(
            select(IngestionFinanceiroStageRow.row_kind)
            .where(IngestionFinanceiroStageRow.ingestion_file_member_id == member_id)
            .distinct()
            .order_by(IngestionFinanceiroStageRow.row_kind.asc())
        ).scalars()
    )
    for row_kind in row_kinds:
        stats = _promote_financeiro_stage_row_kind_postgresql(db, member_id=member_id, row_kind=row_kind)
        contadores["inseridos"] += stats["inserted"]
        contadores["atualizados"] += stats["updated"]
        contadores["inalterados"] += stats["unchanged"]
        if run_id is not None:
            touch_run_heartbeat(
                db,
                run_id=run_id,
                metrics={
                    "rows_promoted": (
                        contadores.get("inseridos", 0)
                        + contadores.get("atualizados", 0)
                        + contadores.get("inalterados", 0)
                    ),
                    "promote_row_kind": row_kind,
                },
            )


def _quote_ident(identifier: str) -> str:
    if not identifier.replace("_", "").isalnum():
        raise ValueError(f"identificador_sql_invalido: {identifier}")
    return f'"{identifier}"'


def _financeiro_stage_target_columns(model: type[Any]) -> tuple[str, ...]:
    if model is DocumentoFinanceiro:
        return (
            "companhia_id",
            "tipo_formulario",
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "versao",
            "denominacao_companhia",
            "categoria_documento",
            "id_documento",
            "data_recebimento",
            "link_documento",
            "arquivo_origem",
            "ano_origem",
            "linha_origem",
            "hash_origem",
        )
    if model is DemonstracaoFinanceira:
        return (
            "companhia_id",
            "tipo_formulario",
            "tipo_demonstracao",
            "escopo_demonstracao",
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "versao",
            "denominacao_companhia",
            "grupo_demonstracao",
            "moeda",
            "escala_moeda",
            "ordem_exercicio",
            "data_inicio_exercicio",
            "data_fim_exercicio",
            "codigo_conta",
            "coluna_df",
            "descricao_conta",
            "valor_conta",
            "conta_fixa",
            "arquivo_origem",
            "ano_origem",
            "linha_origem",
            "hash_origem",
        )
    if model is ComposicaoCapital:
        return (
            "companhia_id",
            "tipo_formulario",
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "versao",
            "denominacao_companhia",
            "quantidade_acoes_ordinarias_capital_integralizado",
            "quantidade_acoes_preferenciais_capital_integralizado",
            "quantidade_total_acoes_capital_integralizado",
            "quantidade_acoes_ordinarias_tesouraria",
            "quantidade_acoes_preferenciais_tesouraria",
            "quantidade_total_acoes_tesouraria",
            "arquivo_origem",
            "ano_origem",
            "linha_origem",
            "hash_origem",
        )
    return (
        "companhia_id",
        "tipo_formulario",
        "cnpj_companhia",
        "codigo_cvm",
        "data_referencia",
        "versao",
        "denominacao_companhia",
        "tipo_relatorio_auditor",
        "tipo_parecer_declaracao",
        "numero_item_parecer_declaracao",
        "texto_parecer_declaracao",
        "arquivo_origem",
        "ano_origem",
        "linha_origem",
        "hash_origem",
    )


def _promote_financeiro_stage_row_kind_postgresql(
    db: Session,
    *,
    member_id: Any,
    row_kind: str,
) -> dict[str, int]:
    model, _entidade, campos_chave, campos_negocio = _financeiro_promotion_spec(row_kind)
    table_name = model.__tablename__
    target_columns = _financeiro_stage_target_columns(model)
    business_columns = tuple(campo for campo in sorted(campos_negocio) if campo in target_columns)
    quoted_table = _quote_ident(table_name)
    quoted_target_columns = ", ".join(_quote_ident(column) for column in target_columns)
    insert_columns = ", ".join(
        (
            _quote_ident("id"),
            quoted_target_columns,
            _quote_ident("criado_em"),
            _quote_ident("sincronizado_em"),
            _quote_ident("alterado_em"),
        )
    )
    source_select_columns = []
    for column in target_columns:
        if column == "coluna_df":
            source_select_columns.append("coalesce(s.coluna_df, '') as coluna_df")
        else:
            quoted = _quote_ident(column)
            source_select_columns.append(f"s.{quoted} as {quoted}")
    source_columns_sql = ",\n                ".join(source_select_columns)
    conflict_columns = ", ".join(_quote_ident(column) for column in campos_chave)
    order_columns = ", ".join(_quote_ident(column) for column in (*campos_chave, "linha_origem"))
    source_insert_values = ", ".join(
        ("gen_random_uuid()", *(f"source.{_quote_ident(column)}" for column in target_columns), "now()", "now()", "now()")
    )
    update_columns = tuple(
        dict.fromkeys((*business_columns, "arquivo_origem", "ano_origem", "linha_origem", "hash_origem", "sincronizado_em"))
    )
    set_columns = ",\n                ".join(
        f"{_quote_ident(column)} = EXCLUDED.{_quote_ident(column)}" for column in update_columns
    )
    business_change_sql = " OR ".join(
        f"{quoted_table}.{_quote_ident(column)} IS DISTINCT FROM EXCLUDED.{_quote_ident(column)}"
        for column in business_columns
    ) or "false"
    existing_business_change_sql = " OR ".join(
        f"target.{_quote_ident(column)} IS DISTINCT FROM source.{_quote_ident(column)}"
        for column in business_columns
    ) or "false"
    key_join_sql = " AND ".join(
        f"target.{_quote_ident(column)} IS NOT DISTINCT FROM source.{_quote_ident(column)}" for column in campos_chave
    )
    sql = f"""
        WITH raw_source AS (
            SELECT
                {source_columns_sql}
            FROM ingestion_financeiro_stage_rows s
            WHERE s.ingestion_file_member_id = :member_id
              AND s.row_kind = :row_kind
        ),
        source AS (
            SELECT DISTINCT ON ({conflict_columns}) *
            FROM raw_source
            ORDER BY {order_columns} DESC
        ),
        existing AS (
            SELECT
                source.hash_origem AS source_hash_origem,
                target.hash_origem AS target_hash_origem,
                target.id AS target_id,
                ({existing_business_change_sql}) AS business_changed
            FROM source
            LEFT JOIN {quoted_table} target ON {key_join_sql}
        ),
        stats AS (
            SELECT
                count(*) FILTER (WHERE target_id IS NULL) AS inserted,
                count(*) FILTER (
                    WHERE target_id IS NOT NULL
                      AND target_hash_origem IS DISTINCT FROM source_hash_origem
                ) AS updated,
                count(*) FILTER (
                    WHERE target_id IS NOT NULL
                      AND target_hash_origem IS NOT DISTINCT FROM source_hash_origem
                ) AS unchanged
            FROM existing
        ),
        upsert AS (
            INSERT INTO {quoted_table} ({insert_columns})
            SELECT {source_insert_values}
            FROM source
            ON CONFLICT ({conflict_columns}) DO UPDATE SET
                {set_columns},
                alterado_em = CASE
                    WHEN {business_change_sql} THEN EXCLUDED.alterado_em
                    ELSE {quoted_table}.alterado_em
                END
            WHERE {quoted_table}.hash_origem IS DISTINCT FROM EXCLUDED.hash_origem
            RETURNING 1
        )
        SELECT
            coalesce(stats.inserted, 0) AS inserted,
            coalesce(stats.updated, 0) AS updated,
            coalesce(stats.unchanged, 0) AS unchanged,
            (SELECT count(*) FROM upsert) AS affected
        FROM stats
    """
    row = db.execute(text(sql), {"member_id": member_id, "row_kind": row_kind}).mappings().one()
    db.flush()
    return {
        "inserted": int(row["inserted"] or 0),
        "updated": int(row["updated"] or 0),
        "unchanged": int(row["unchanged"] or 0),
    }


def _promote_financeiro_member_from_stage_fallback(
    db: Session,
    *,
    member_id: Any,
    run_id: Any | None = None,
    execucao_id: Any,
    contadores: dict[str, int],
    chunk_size: int,
) -> None:
    row_kinds = list(
        db.execute(
            select(IngestionFinanceiroStageRow.row_kind)
            .where(IngestionFinanceiroStageRow.ingestion_file_member_id == member_id)
            .distinct()
            .order_by(IngestionFinanceiroStageRow.row_kind.asc())
        ).scalars()
    )
    for row_kind in row_kinds:
        for chunk in _iter_financeiro_stage_chunks(
            db,
            ingestion_file_member_id=member_id,
            row_kind=row_kind,
            chunk_size=chunk_size,
        ):
            _promote_financeiro_payloads_internal(
                db,
                row_kind=row_kind,
                dados_promovidos=[_stage_row_to_promocao_payload(item) for item in chunk],
                execucao_id=execucao_id,
                contadores=contadores,
            )
            if run_id is not None:
                touch_run_heartbeat(
                    db,
                    run_id=run_id,
                    metrics={
                        "rows_promoted": (
                            contadores.get("inseridos", 0)
                            + contadores.get("atualizados", 0)
                            + contadores.get("inalterados", 0)
                        ),
                        "promote_row_kind": row_kind,
                    },
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
            contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
            contadores["lidas"] += member.row_count
            contadores["rejeitados"] += member.row_count
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

            resolver_result = resolve_companhia(
                db,
                _resolver_input_from_data(dados, tipo_formulario=tipo_formulario),
                header_map=header_map,
                provisional_enabled=True,
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


def _create_financeiro_quarantine_row(
    db: Session,
    *,
    execucao_id: Any,
    run: IngestionRun,
    member: IngestionFileMember,
    arquivo_origem: str,
    ano: int,
    linha_origem: int,
    row_kind: str,
    raw_data: dict[str, str],
    result: Any,
    legacy_reason: str | None = None,
    normalized_data: dict[str, Any] | None = None,
    natural_key: dict[str, Any] | None = None,
) -> None:
    rows = insert_rows(
        db,
        ingestion_run=run,
        ingestion_file_member=member,
        arquivo_origem=arquivo_origem,
        ano_origem=ano,
        row_kind=row_kind,
        rows=[(linha_origem, raw_data)],
        validation_status="invalid",
        fetch_inserted_rows=True,
        use_copy=False,
    )
    if not rows:
        raise ValueError("linha_quarentena_nao_criada")
    row = rows[0]
    write_validation_result(
        db,
        ingestion_row=row,
        result=result,
        normalized_data=normalized_data,
        natural_key=natural_key,
    )
    create_quarantine_item(
        db,
        ingestion_row=row,
        result=result,
        execucao_sincronizacao_id=execucao_id,
        legacy_reason=legacy_reason,
    )
    _registrar_quarentena(
        db,
        execucao_id=execucao_id,
        arquivo_origem=arquivo_origem,
        ano_origem=ano,
        linha_origem=linha_origem,
        motivo=legacy_reason or result.reason_code or "linha_rejeitada",
        dados_originais=raw_data,
    )


def process_financeiro_member_direct_from_disk(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun,
    ingestion_file: Any,
    file_path: str,
    member_name: str,
    row_kind: str,
    member_sha256: str,
    member_size_bytes: int,
    encoding: str,
    delimiter: str,
    reconcile_required: bool,
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
    settings = get_settings()
    if not settings.ingestion_financeiro_typed_staging_enabled:
        raise ValueError("financial_direct_path_requires_typed_staging")

    reason_counts = quality_counters.setdefault("reason_counts", Counter())
    resolver_methods = quality_counters.setdefault("resolver_methods", Counter())
    top_quarantine_files = quality_counters.setdefault("top_quarantine_files", Counter())
    quality_counters.setdefault("provisional_company_count", 0)
    quality_counters.setdefault("typed_stage_rows_loaded", 0)
    quality_counters.setdefault("typed_stage_bytes_loaded", 0)
    quality_counters.setdefault("typed_stage_rows_replaced", 0)
    quality_counters.setdefault("typed_stage_rows_purged", 0)
    quality_counters.setdefault("typed_stage_copy_loads", 0)

    update_run_state(run, status="em_execucao", phase="profile")
    header, row_iter, encoding = iter_csv_rows_from_disk(file_path, encoding, delimiter=delimiter)
    member = register_member(
        db,
        ingestion_file=ingestion_file,
        member_name=member_name,
        member_sha256=member_sha256,
        member_size_bytes=member_size_bytes,
        header=header,
        row_count=0,
        encoding=encoding,
        delimiter=delimiter,
    )
    schema_result = validate_member_header(row_kind, member.header)
    update_member_schema_validation(member, result=schema_result)
    db.commit()
    db.refresh(member)

    execucao_id = execucao.id
    run_id = run.id
    member_id = member.id
    normalized_writers: dict[str, NormalizedArtifactWriter] = {}
    current_row_kinds_by_model: dict[type[Any], set[str]] = {}
    total_rows = 0
    reconciled_deleted = 0

    if schema_result.status == "invalid":
        for linha_origem, raw_data in row_iter:
            total_rows += 1
            contadores["lidas"] += 1
            contadores["rejeitados"] += 1
            assert isinstance(reason_counts, Counter)
            assert isinstance(top_quarantine_files, Counter)
            reason_counts[schema_result.reason_code or "schema_inesperado"] += 1
            top_quarantine_files[member_name] += 1
            _create_financeiro_quarantine_row(
                db,
                execucao_id=execucao_id,
                run=run,
                member=member,
                arquivo_origem=member_name,
                ano=ano,
                linha_origem=linha_origem,
                row_kind=row_kind,
                raw_data=raw_data,
                result=schema_result,
                legacy_reason=schema_result.reason_code or "schema_inesperado",
            )
        member.row_count = total_rows
        contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
        update_run_state(
            run,
            phase="complete",
            quality_summary=_build_incremental_quality_summary(contadores, quality_counters),
        )
        _atualizar_execucao(execucao, contadores)
        db.commit()
        return execucao, run, member

    update_run_state(run, phase="normalize_artifact")
    db.commit()
    for linha_origem, raw_data in row_iter:
        total_rows += 1
        contadores["lidas"] += 1
        try:
            resolved_row_kind, dados = normalizar_financeiro_row(
                prefixo=prefixo,
                tipo_formulario=tipo_formulario,
                arquivo_origem=member_name,
                ano_origem=ano,
                linha_origem=linha_origem,
                linha=raw_data,
            )
        except Exception as exc:
            result = invalid_result(
                f"normalizacao_invalida: {exc}",
                details={"erro": str(exc)},
                repairable=True,
            )
            _create_financeiro_quarantine_row(
                db,
                execucao_id=execucao_id,
                run=run,
                member=member,
                arquivo_origem=member_name,
                ano=ano,
                linha_origem=linha_origem,
                row_kind=row_kind,
                raw_data=raw_data,
                result=result,
                legacy_reason=f"normalizacao_invalida: {exc}",
            )
            contadores["rejeitados"] += 1
            assert isinstance(reason_counts, Counter)
            assert isinstance(top_quarantine_files, Counter)
            reason_counts["normalizacao_invalida"] += 1
            top_quarantine_files[member_name] += 1
            continue

        natural_key = build_natural_key(resolved_row_kind, dados)
        duplicate_result = classify_duplicate(
            row_kind=resolved_row_kind,
            natural_key=natural_key,
            normalized_hash=gerar_hash_canonico(dados),
            normalized_data=dados,
            seen_by_key=seen_by_row_kind.setdefault(resolved_row_kind, {}),
        )
        if duplicate_result.status == "ignored_duplicate":
            contadores["inalterados"] += 1
            continue
        if duplicate_result.status == "invalid":
            _create_financeiro_quarantine_row(
                db,
                execucao_id=execucao_id,
                run=run,
                member=member,
                arquivo_origem=member_name,
                ano=ano,
                linha_origem=linha_origem,
                row_kind=resolved_row_kind,
                raw_data=raw_data,
                result=duplicate_result,
                normalized_data=dados,
                natural_key=natural_key,
            )
            contadores["rejeitados"] += 1
            assert isinstance(reason_counts, Counter)
            assert isinstance(top_quarantine_files, Counter)
            reason_counts[duplicate_result.reason_code or "chave_natural_duplicada_conflitante"] += 1
            top_quarantine_files[member_name] += 1
            continue

        resolver_result = resolve_companhia(
            db,
            _resolver_input_from_data(dados, tipo_formulario=tipo_formulario),
            header_map=header_map,
            provisional_enabled=True,
        )
        if resolver_result.status not in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
            result = invalid_result(
                resolver_result.resolution_method or "companhia_nao_encontrada",
                details=resolver_result.details,
                repairable=True,
            )
            _create_financeiro_quarantine_row(
                db,
                execucao_id=execucao_id,
                run=run,
                member=member,
                arquivo_origem=member_name,
                ano=ano,
                linha_origem=linha_origem,
                row_kind=resolved_row_kind,
                raw_data=raw_data,
                result=result,
                legacy_reason=resolver_result.resolution_method or "companhia_nao_encontrada",
                normalized_data=dados,
                natural_key=natural_key,
            )
            contadores["rejeitados"] += 1
            assert isinstance(reason_counts, Counter)
            assert isinstance(top_quarantine_files, Counter)
            reason_counts[resolver_result.resolution_method or "companhia_nao_encontrada"] += 1
            top_quarantine_files[member_name] += 1
            continue

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
        model, _, _, _ = _financeiro_promotion_spec(resolved_row_kind)
        dados_promocao = _preparar_dados_promocao(_filtrar_payload_promocao_por_modelo(model, dados))

        writer = normalized_writers.get(resolved_row_kind)
        if writer is None:
            writer = NormalizedArtifactWriter(
                run_id=str(run_id),
                member_id=str(member_id),
                member_name=member.member_name,
                row_kind=resolved_row_kind,
            )
            normalized_writers[resolved_row_kind] = writer
        writer.write_row(
            {
                "row_kind": resolved_row_kind,
                "linha_origem": linha_origem,
                "arquivo_origem": member_name,
                "ano_origem": ano,
                "companhia_id": dados.get("companhia_id"),
                "normalized_hash": gerar_hash_canonico(dados),
                "hash_origem": dados_promocao["hash_origem"],
                "natural_key": natural_key,
                **dados,
            }
        )
        current_row_kinds_by_model.setdefault(model, set()).add(resolved_row_kind)
        if resolved_row_kind.endswith("_documento") and resolver_result.companhia_id is not None:
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

        if total_rows % chunk_size == 0:
            member.row_count = total_rows
            touch_run_heartbeat(
                db,
                run_id=run_id,
                metrics={
                    "rows_read": contadores["lidas"],
                    "rows_normalized": total_rows - contadores["rejeitados"],
                },
            )
            _atualizar_execucao(execucao, contadores)
            db.commit()

    member.row_count = total_rows
    normalized_artifacts = {kind: writer.close() for kind, writer in normalized_writers.items()}
    for artifact in normalized_artifacts.values():
        record_phase_artifact(db, run_id=run_id, direction="output", artifact=artifact)

    update_run_state(run, phase="load_typed_staging")
    db.commit()
    for artifact in normalized_artifacts.values():
        load_result = load_financeiro_artifact_to_stage(
            db,
            ingestion_run_id=run_id,
            ingestion_file_member_id=member_id,
            artifact_uri=str(artifact["uri"]),
        )
        rows_loaded = quality_counters.get("typed_stage_rows_loaded", 0)
        bytes_loaded = quality_counters.get("typed_stage_bytes_loaded", 0)
        rows_replaced = quality_counters.get("typed_stage_rows_replaced", 0)
        copy_loads = quality_counters.get("typed_stage_copy_loads", 0)
        quality_counters["typed_stage_rows_loaded"] = (
            (rows_loaded if isinstance(rows_loaded, int) else 0) + load_result.rows_loaded
        )
        quality_counters["typed_stage_bytes_loaded"] = (
            (bytes_loaded if isinstance(bytes_loaded, int) else 0) + load_result.bytes_loaded
        )
        quality_counters["typed_stage_rows_replaced"] = (
            (rows_replaced if isinstance(rows_replaced, int) else 0) + load_result.rows_replaced
        )
        if load_result.copy_used:
            quality_counters["typed_stage_copy_loads"] = (copy_loads if isinstance(copy_loads, int) else 0) + 1
    db.commit()

    if promote_enabled:
        update_run_state(run, phase="promote")
        db.commit()
        _promote_financeiro_member_from_stage(
            db,
            member_id=member_id,
            run_id=run_id,
            execucao_id=execucao_id,
            contadores=contadores,
            chunk_size=chunk_size,
        )
    else:
        typed_stage_rows_loaded_raw = quality_counters.get("typed_stage_rows_loaded", 0)
        contadores["inalterados"] += (
            typed_stage_rows_loaded_raw if isinstance(typed_stage_rows_loaded_raw, int) else 0
        )

    if promote_enabled and reconcile_required:
        update_run_state(run, phase="reconcile")
        db.commit()
        for model, row_kinds in current_row_kinds_by_model.items():
            normalized_artifact_uri = None
            for current_row_kind in sorted(row_kinds):
                artifact_metadata = normalized_artifacts.get(current_row_kind)
                if artifact_metadata is not None:
                    normalized_artifact_uri = str(artifact_metadata["uri"])
                    break
            reconciled_deleted += reconcile_promoted_rows(
                db,
                model=model,
                ingestion_run_id=run_id,
                ingestion_file_member_id=member_id,
                arquivo_origem=member_name,
                ano_origem=ano,
                row_kinds=row_kinds,
                normalized_artifact_uri=normalized_artifact_uri,
            )
        contadores["reconciled_deleted"] = contadores.get("reconciled_deleted", 0) + reconciled_deleted

    purged_rows = clear_financeiro_stage_rows(db, ingestion_file_member_id=member_id)
    typed_stage_rows_purged = quality_counters.get("typed_stage_rows_purged", 0)
    quality_counters["typed_stage_rows_purged"] = (
        (typed_stage_rows_purged if isinstance(typed_stage_rows_purged, int) else 0) + purged_rows
    )

    artifact_snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run_id))
    dataset = dataset_por_member_name(prefixo, member.member_name, ano)
    raw_artifact = None
    delivery_rows: list[dict[str, Any]] = []
    if member_artifact_exists(execution_id=str(execucao_id), member_name=member.member_name):
        raw_artifact = describe_member_artifact(
            execution_id=str(execucao_id),
            member_name=member.member_name,
            content_sha256=member.member_sha256,
        )
        payload = read_member_artifact(execution_id=str(execucao_id), member_name=member.member_name)
        delivery_rows = extract_delivery_rows(payload=payload, member_name=member.member_name, dataset=dataset)
    normalized_artifact = next(iter(normalized_artifacts.values()), None)
    if artifact_snapshot is not None:
        record_member_snapshot(
            db,
            artifact_snapshot=artifact_snapshot,
            member_name=member.member_name,
            member_sha256=member.member_sha256,
            row_count=member.row_count,
            header=member.header,
            row_kind=None if dataset is None else dataset.row_kind,
            required_member=False if dataset is None else dataset.obrigatorio,
            schema_status=member.schema_status,
            schema_message=member.schema_message,
            lifecycle_status="processed",
            delivery_index_role=resolve_delivery_index_role(dataset),
            destino_promovido=None if dataset is None else dataset.destino_promovido,
            ingestion_file_member_id=member.id,
            delivery_rows=delivery_rows,
            raw_artifact=raw_artifact,
            normalized_artifact=normalized_artifact,
        )

    update_run_state(
        run,
        phase="complete",
        quality_summary=_build_incremental_quality_summary(
            contadores,
            quality_counters,
            extras={
                "rows_read": contadores["lidas"],
                "rows_normalized": total_rows - contadores["rejeitados"],
                "rows_loaded_to_stage": quality_counters.get("typed_stage_rows_loaded", 0),
                "rows_reconciled_deleted": reconciled_deleted,
            },
        ),
    )
    _atualizar_execucao(execucao, contadores)
    db.commit()
    db.expunge_all()
    execucao_final = db.get(ExecucaoSincronizacao, execucao_id)
    run_final = db.get(IngestionRun, run_id)
    member_final = db.get(IngestionFileMember, member_id)
    if execucao_final is None or run_final is None or member_final is None:
        raise ValueError("estado_execucao_financeiro_direct_path_inconsistente")
    return execucao_final, run_final, member_final


def _process_financeiro_member(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun,
    member: IngestionFileMember,
    reconcile_required: bool,
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
    quality_counters.setdefault("typed_stage_rows_loaded", 0)
    quality_counters.setdefault("typed_stage_bytes_loaded", 0)
    quality_counters.setdefault("typed_stage_rows_replaced", 0)
    quality_counters.setdefault("typed_stage_rows_purged", 0)
    quality_counters.setdefault("typed_stage_copy_loads", 0)
    typed_staging_enabled = get_settings().ingestion_financeiro_typed_staging_enabled
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
        contadores["lidas"] += member.row_count
        contadores["rejeitados"] += member.row_count
        assert isinstance(reason_counts, Counter)
        reason_counts[schema_result.reason_code or "schema_inesperado"] += member.row_count
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
    reconciled_deleted = 0
    current_row_kinds_by_model: dict[type[Any], set[str]] = {}
    fallback_row_kind = f"{prefixo}_documento"
    current_model, _, _, _ = _financeiro_promotion_spec(member_row_kind or fallback_row_kind)
    current_row_kinds_by_model.setdefault(current_model, set()).add(member_row_kind or fallback_row_kind)
    normalized_writers: dict[str, NormalizedArtifactWriter] = {}
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
                    f"normalizacao_invalida: {exc}",
                    details={"erro": str(exc)},
                    repairable=True,
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
                provisional_enabled=True,
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
            writer = normalized_writers.get(row_kind)
            if writer is None:
                writer = NormalizedArtifactWriter(
                    run_id=str(run_id),
                    member_id=str(member_id),
                    member_name=member.member_name,
                    row_kind=row_kind,
                )
                normalized_writers[row_kind] = writer
            writer.write_row(
                {
                    "row_kind": row_kind,
                    "linha_origem": row.linha_origem,
                    "arquivo_origem": row.arquivo_origem,
                    "ano_origem": ano,
                    "companhia_id": dados.get("companhia_id"),
                    "normalized_hash": gerar_hash_canonico(dados),
                    "natural_key": natural_key,
                    **dados,
                }
            )
            model, _, _, _ = _financeiro_promotion_spec(row_kind)
            current_row_kinds_by_model.setdefault(model, set()).add(row_kind)
            if promote_enabled and not typed_staging_enabled:
                linhas_promovidas.append((row, dados))
            elif not promote_enabled:
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

    normalized_artifacts = {
        row_kind: writer.close()
        for row_kind, writer in normalized_writers.items()
    }
    settings = get_settings()
    if settings.ingestion_financeiro_typed_staging_enabled:
        for artifact in normalized_artifacts.values():
            load_result = load_financeiro_artifact_to_stage(
                db,
                ingestion_run_id=run_id,
                ingestion_file_member_id=member.id,
                artifact_uri=str(artifact["uri"]),
            )
            rows_loaded = quality_counters.get("typed_stage_rows_loaded", 0)
            bytes_loaded = quality_counters.get("typed_stage_bytes_loaded", 0)
            rows_replaced = quality_counters.get("typed_stage_rows_replaced", 0)
            copy_loads = quality_counters.get("typed_stage_copy_loads", 0)
            quality_counters["typed_stage_rows_loaded"] = (
                (rows_loaded if isinstance(rows_loaded, int) else 0) + load_result.rows_loaded
            )
            quality_counters["typed_stage_bytes_loaded"] = (
                (bytes_loaded if isinstance(bytes_loaded, int) else 0) + load_result.bytes_loaded
            )
            quality_counters["typed_stage_rows_replaced"] = (
                (rows_replaced if isinstance(rows_replaced, int) else 0) + load_result.rows_replaced
            )
            if load_result.copy_used:
                quality_counters["typed_stage_copy_loads"] = (copy_loads if isinstance(copy_loads, int) else 0) + 1
        if promote_enabled:
            _promote_financeiro_member_from_stage(
                db,
                member_id=member.id,
                run_id=run_id,
                execucao_id=execucao_id,
                contadores=contadores,
                chunk_size=chunk_size,
            )
        purged_rows = clear_financeiro_stage_rows(db, ingestion_file_member_id=member.id)
        typed_stage_rows_purged = quality_counters.get("typed_stage_rows_purged", 0)
        quality_counters["typed_stage_rows_purged"] = (
            (typed_stage_rows_purged if isinstance(typed_stage_rows_purged, int) else 0) + purged_rows
        )
    for artifact in normalized_artifacts.values():
        record_phase_artifact(
            db,
            run_id=run_id,
            direction="output",
            artifact=artifact,
        )

    artifact_snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run_id))
    dataset = dataset_por_member_name(tipo_formulario, member.member_name, ano)
    raw_artifact = None
    delivery_rows: list[dict[str, Any]] = []
    if member_artifact_exists(execution_id=str(execucao_id), member_name=member.member_name):
        raw_artifact = describe_member_artifact(
            execution_id=str(execucao_id),
            member_name=member.member_name,
            content_sha256=member.member_sha256,
        )
        payload = read_member_artifact(execution_id=str(execucao_id), member_name=member.member_name)
        delivery_rows = extract_delivery_rows(payload=payload, member_name=member.member_name, dataset=dataset)
    normalized_artifact = next(iter(normalized_artifacts.values()), None)
    if artifact_snapshot is not None:
        record_member_snapshot(
            db,
            artifact_snapshot=artifact_snapshot,
            member_name=member.member_name,
            member_sha256=member.member_sha256,
            row_count=member.row_count,
            header=member.header,
            row_kind=None if dataset is None else dataset.row_kind,
            required_member=False if dataset is None else dataset.obrigatorio,
            schema_status=member.schema_status,
            schema_message=member.schema_message,
            lifecycle_status="processed",
            delivery_index_role=resolve_delivery_index_role(dataset),
            destino_promovido=None if dataset is None else dataset.destino_promovido,
            ingestion_file_member_id=member.id,
            delivery_rows=delivery_rows,
            raw_artifact=raw_artifact,
            normalized_artifact=normalized_artifact,
        )

    if promote_enabled and reconcile_required:
        for model, row_kinds in current_row_kinds_by_model.items():
            normalized_artifact_uri = None
            for row_kind in sorted(row_kinds):
                artifact_metadata = normalized_artifacts.get(row_kind)
                if artifact_metadata is not None:
                    normalized_artifact_uri = str(artifact_metadata["uri"])
                    break
            reconciled_deleted += reconcile_promoted_rows(
                db,
                model=model,
                ingestion_run_id=run_id,
                ingestion_file_member_id=member.id,
                arquivo_origem=member.arquivo_origem if hasattr(member, "arquivo_origem") else member.member_name,
                ano_origem=ano,
                row_kinds=row_kinds,
                normalized_artifact_uri=normalized_artifact_uri,
            )
        contadores["reconciled_deleted"] = contadores.get("reconciled_deleted", 0) + reconciled_deleted

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
    reconcile_required: bool,
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
        reconcile_required=reconcile_required,
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
    custom_downloader = downloader is not None
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
        remote_probe = (
            build_custom_remote_probe(source_url=url)
            if custom_downloader
            else probe_remote_source(
                db,
                run=run,
                tipo_fonte=prefixo,
                ano=ano,
                source_url=url,
            )
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
                tipo_fonte=prefixo,
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
            tipo_fonte=prefixo,
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

        member_map, required_members = map_financeiro_members(prefixo, ano)
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
            artifact_snapshot=artifact_snapshot,
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
                    reconcile_required=context.reconcile_required,
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
