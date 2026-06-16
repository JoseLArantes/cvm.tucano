from __future__ import annotations

import hashlib
import uuid
from typing import Any

import httpx
from sqlalchemy import and_, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.ingestion import IngestionRow, IngestionRun
from app.models.ipe import IpeDocumento
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.ingestion.acquisition import annotate_probe_with_sha_confirmation, probe_remote_source
from app.services.ingestion.change_tracking import (
    compare_member_with_previous,
    finalize_member_change_summary,
    previous_successful_members,
    reconcile_promoted_rows,
)
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.lifecycle import (
    build_custom_remote_probe,
    capture_member_lifecycle_snapshot,
    upsert_artifact_snapshot,
)
from app.services.ingestion.normalizers import (
    gerar_hash_canonico,
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
    resolve_companhia,
)
from app.services.ingestion.sql_batches import iter_lookup_batches, iter_parameter_batches, mapping_parameter_width
from app.services.ingestion.source_registry import listar_datasets
from app.services.ingestion.staging import (
    create_run,
    iter_zip_csv_members,
    member_has_successful_match,
    purge_member_success_rows,
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
from app.services.sincronizacao_fre import _agora, _equivalente, _registrar_quarentena

_BATCH_COMMIT_LINHAS = 5000
_PROMOTE_CHUNK_SIZE = 1000  # max rows per _promote_ipe_chunk call (PG 65535 param limit)
_PROMOTED_ROW_KINDS = {"ipe_documento"}
_ARQUIVO_PRINCIPAL = "ipe_cia_aberta_{ano}.csv"

_CAMPOS_NEGOCIO = {
    "companhia_id",
    "cnpj_companhia",
    "codigo_cvm",
    "nome_companhia",
    "data_referencia",
    "categoria",
    "tipo",
    "especie",
    "assunto",
    "data_entrega",
    "tipo_apresentacao",
    "protocolo_entrega",
    "versao",
    "link_download",
}


def map_ipe_members(ano: int) -> tuple[dict[str, str], dict[str, str], set[str], set[str]]:
    datasets = listar_datasets("ipe")
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


def normalizar_ipe_row(
    *,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    linha: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if arquivo_origem != _ARQUIVO_PRINCIPAL.format(ano=ano_origem):
        raise ValueError(f"arquivo_nao_mapeado: {arquivo_origem}")

    data_referencia = normalizar_data(linha.get("Data_Referencia"))
    data_entrega = normalizar_data(linha.get("Data_Entrega"))
    versao = normalizar_inteiro(linha.get("Versao"))
    if data_referencia is None or data_entrega is None or versao is None:
        raise ValueError("campo_obrigatorio_ausente")

    return (
        "ipe_documento",
        {
            "cnpj_companhia": normalizar_cnpj_opcional(linha.get("CNPJ_Companhia")),
            "codigo_cvm": normalizar_inteiro(linha.get("Codigo_CVM")),
            "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
            "data_referencia": data_referencia,
            "categoria": normalizar_texto(linha.get("Categoria")),
            "tipo": normalizar_texto(linha.get("Tipo")),
            "especie": normalizar_texto(linha.get("Especie")),
            "assunto": (normalizar_texto(linha.get("Assunto")) or "")[:1000] or None,
            "data_entrega": data_entrega,
            "tipo_apresentacao": normalizar_texto(linha.get("Tipo_Apresentacao")),
            "protocolo_entrega": normalizar_texto(linha.get("Protocolo_Entrega")),
            "versao": versao,
            "link_download": normalizar_texto(linha.get("Link_Download")),
            "arquivo_origem": arquivo_origem,
            "ano_origem": ano_origem,
            "linha_origem": linha_origem,
        },
    )


def _resolver_input_from_data(dados: dict[str, Any]) -> ResolverInput:
    return ResolverInput(
        cnpj_companhia=dados.get("cnpj_companhia"),
        codigo_cvm=dados.get("codigo_cvm"),
        denominacao_companhia=dados.get("nome_companhia"),
        tipo_formulario="IPE",
        id_documento=None,
        versao=dados.get("versao"),
        data_referencia=dados.get("data_referencia"),
    )


def _ipe_campos_chave(dados: dict[str, Any]) -> tuple[str, ...]:
    return (
        "cnpj_companhia",
        "codigo_cvm",
        "data_referencia",
        "categoria",
        "tipo",
        "especie",
        "assunto",
        "data_entrega",
        "protocolo_entrega",
        "versao",
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


def _prepare_promocao(dados: dict[str, Any]) -> dict[str, Any]:
    dados_promocao = dict(dados)
    dados_promocao["hash_origem"] = gerar_hash_canonico(
        {k: v for k, v in dados_promocao.items() if k != "linha_origem"}
    )
    return dados_promocao


def _promote_ipe_chunk(
    db: Session,
    *,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    if not linhas_promovidas:
        return
    agora = _agora()
    preparados = [(row, _prepare_promocao(dados)) for row, dados in linhas_promovidas]

    # Group by key strategy so rows with and without protocolo_entrega
    # are looked up against the correct unique constraint.
    groups: dict[tuple[str, ...], list[tuple[IngestionRow, dict[str, Any]]]] = {}
    for row, dados in preparados:
        campos_chave = _ipe_campos_chave(dados)
        groups.setdefault(campos_chave, []).append((row, dados))

    for campos_chave, grupo in groups.items():
        chaves = list(dict.fromkeys(_key_tuple(dados, campos_chave) for _, dados in grupo))
        existentes: list[Any] = []
        if chaves:
            for batch in iter_lookup_batches(chaves, parameter_width=len(campos_chave)):
                existentes.extend(
                    db.execute(select(IpeDocumento).where(_build_key_clause(IpeDocumento, campos_chave, batch))).scalars()
                )
        existentes_por_chave = {tuple(getattr(item, campo) for campo in campos_chave): item for item in existentes}
        payload_insercao: list[dict[str, Any]] = []
        historicos: list[dict[str, Any]] = []

        for row, dados in grupo:
            chave = _key_tuple(dados, campos_chave)
            existente = existentes_por_chave.get(chave)
            if existente is None:
                novo_id = uuid.uuid4()
                payload_insercao.append(
                    {"id": novo_id, **dados, "criado_em": agora, "sincronizado_em": agora, "alterado_em": agora}
                )
                contadores["inseridos"] += 1
                continue
            alteracoes: dict[str, tuple[Any, Any]] = {}
            for campo in _CAMPOS_NEGOCIO:
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
                            "entidade": "ipe_documentos",
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
            # Use __table__ to bypass ORM bulk_persistence, which strips ON CONFLICT.
            # ON CONFLICT DO NOTHING handles:
            # 1. Intra-batch: two rows share the same alternate composite key
            #    (different protocolo_entrega, same company/date/category/...) — first wins.
            # 2. Cross-chunk races after db.flush().
            for batch in iter_parameter_batches(
                payload_insercao,
                parameter_width=mapping_parameter_width(payload_insercao),
            ):
                db.execute(pg_insert(IpeDocumento).values(batch).on_conflict_do_nothing())
                # Flush so the next group's lookup sees these newly-inserted rows.
                db.flush()
        if historicos:
            for batch in iter_parameter_batches(historicos, parameter_width=mapping_parameter_width(historicos)):
                db.execute(insert(HistoricoAlteracaoCampo), batch)



def _promote_ipe_row(
    db: Session,
    *,
    row: IngestionRow,
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    _promote_ipe_chunk(
        db,
        linhas_promovidas=[(row, dados)],
        execucao_id=execucao_id,
        contadores=contadores,
    )


def _process_ipe_rows(
    db: Session,
    *,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun,
    ano: int,
    staged_members: list[tuple[Any, list[IngestionRow]]],
    promote_enabled: bool,
    contadores: dict[str, int] | None = None,
    seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, int]:
    _, _, required_members, _ = map_ipe_members(ano)
    if contadores is None:
        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    if seen_by_row_kind is None:
        seen_by_row_kind = {}

    for member, rows in staged_members:
        current_hashes: set[str] = set()
        schema_result = validate_member_header(rows[0].row_kind if rows else "desconhecido", member.header)
        update_member_schema_validation(member, result=schema_result)
        if schema_result.status == "invalid":
            contadores["members_invalid_schema"] = contadores.get("members_invalid_schema", 0) + 1
            contadores["lidas"] += member.row_count
            contadores["rejeitados"] += member.row_count
            continue

        linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]] = []
        for row in rows:
            contadores["lidas"] += 1
            try:
                row_kind, dados = normalizar_ipe_row(
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

            resolver_result = resolve_companhia(db, _resolver_input_from_data(dados), provisional_enabled=True)
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
            if dados.get("codigo_cvm") is None and companhia is not None:
                dados["codigo_cvm"] = companhia.codigo_cvm

            write_validation_result(
                db, ingestion_row=row, result=duplicate_result, normalized_data=dados, natural_key=natural_key
            )
            if promote_enabled and row_kind in _PROMOTED_ROW_KINDS:
                current_hashes.add(_prepare_promocao(dados)["hash_origem"])
                linhas_promovidas.append((row, dados))
                if len(linhas_promovidas) >= _PROMOTE_CHUNK_SIZE:
                    _promote_ipe_chunk(
                        db,
                        linhas_promovidas=linhas_promovidas,
                        execucao_id=execucao.id,
                        contadores=contadores,
                    )
                    linhas_promovidas = []
            else:
                contadores["inalterados"] += 1

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
            _promote_ipe_chunk(
                db,
                linhas_promovidas=linhas_promovidas,
                execucao_id=execucao.id,
                contadores=contadores,
            )
        if promote_enabled and current_hashes:
            contadores["reconciled_deleted"] = contadores.get("reconciled_deleted", 0) + reconcile_promoted_rows(
                db,
                model=IpeDocumento,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                arquivo_origem=member.member_name,
                ano_origem=ano,
                current_hashes=current_hashes,
            )

    update_run_state(run, phase="promote", quality_summary=build_contadores_quality_summary(contadores))
    return contadores


def sincronizar_ipe(
    db: Session,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    limpar_caches_resolver()
    custom_downloader = downloader is not None
    downloader = downloader or (lambda url: _download(url, timeout=300))
    arquivo_zip = f"ipe_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/IPE/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte="ipe", ano=ano, id_tarefa=task_id, arquivo=arquivo_zip, url=url, status="em_execucao"
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    run = create_run(
        db,
        tipo_fonte="ipe",
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
            else probe_remote_source(db, run=run, tipo_fonte="ipe", ano=ano, source_url=url)
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
                tipo_fonte="ipe",
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
            tipo_fonte="ipe",
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

        row_kind_map, _, required_members, optional_members = map_ipe_members(ano)
        staged_names = {member_name for member_name, _ in iter_zip_csv_members(payload)}
        faltando = sorted(required_members - staged_names)
        if faltando:
            raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")
        inesperados = sorted(name for name in staged_names if name not in row_kind_map)
        if inesperados:
            raise ValueError(f"arquivo_nao_mapeado: {','.join(inesperados)}")

        ingestion_file = register_file(
            db, ingestion_run=run, source_url=url, source_filename=arquivo_zip, payload=payload, is_zip=True
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
        membros_inalterados = 0
        seen_by_row_kind: dict[str, dict[str, dict[str, Any]]] = {}
        staged_rows_purged = 0
        previous_members = previous_successful_members(
            db,
            tipo_fonte="ipe",
            ano=ano,
            current_run_id=run.id,
        )
        change_summary = finalize_member_change_summary(
            current_member_names=[],
            previous_members=previous_members,
            required_members=required_members,
            optional_members=optional_members,
        )

        for member_name, member_payload in sorted(iter_zip_csv_members(payload), key=lambda item: item[0]):
            if member_has_successful_match(
                db,
                tipo_fonte="ipe",
                ano=ano,
                member_name=member_name,
                member_sha256=hashlib.sha256(member_payload).hexdigest(),
                current_run_id=run.id,
            ):
                membros_inalterados += 1
                lifecycle = capture_member_lifecycle_snapshot(
                    db,
                    artifact_snapshot=artifact_snapshot,
                    tipo_fonte="ipe",
                    ano=ano,
                    current_run_id=run.id,
                    member_name=member_name,
                    payload=member_payload,
                    row_kind=row_kind_map.get(member_name, "desconhecido"),
                    required_member=member_name in required_members,
                    schema_status="reused",
                    schema_message="member_sha256_reused",
                    lifecycle_status="member_skipped",
                )
                if lifecycle["delivery_delta"] is not None:
                    delivery_changed = list(change_summary.get("delivery_index_changed", []))
                    delivery_changed.append({"member_name": member_name, **lifecycle["delivery_delta"]})
                    change_summary["delivery_index_changed"] = delivery_changed
                update_run_state(
                    run,
                    phase="stage",
                    change_summary=change_summary,
                    quality_summary=build_contadores_quality_summary(
                        contadores,
                        extras={"members_skipped": membros_inalterados, "staged_rows_purged": staged_rows_purged},
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
            update_run_state(run, phase="stage", change_summary=change_summary)
            db.commit()
            db.refresh(run)
            db.refresh(execucao)
            _process_ipe_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
            )
            member = db.get(type(member), member.id) or member
            lifecycle = capture_member_lifecycle_snapshot(
                db,
                artifact_snapshot=artifact_snapshot,
                tipo_fonte="ipe",
                ano=ano,
                current_run_id=run.id,
                member_name=member_name,
                payload=member_payload,
                row_kind=row_kind_map.get(member_name, "desconhecido"),
                required_member=member_name in required_members,
                schema_status=member.schema_status,
                schema_message=member.schema_message,
                lifecycle_status="processed",
                ingestion_file_member_id=member.id,
            )
            change_summary = compare_member_with_previous(
                member=member,
                previous_members=previous_members,
                change_summary=change_summary,
            )
            if lifecycle["delivery_delta"] is not None:
                delivery_changed = list(change_summary.get("delivery_index_changed", []))
                delivery_changed.append({"member_name": member_name, **lifecycle["delivery_delta"]})
                change_summary["delivery_index_changed"] = delivery_changed
            staged_rows_purged += purge_member_success_rows(db, ingestion_file_member_id=member.id)
            db.commit()
            db.refresh(run)
            db.refresh(execucao)

        change_summary = finalize_member_change_summary(
            current_member_names=staged_names,
            previous_members=previous_members,
            required_members=required_members,
            optional_members=optional_members,
            change_summary=change_summary,
        )
        quality_summary = build_quality_summary(db, ingestion_run_id=run.id)
        quality_summary["members_skipped"] = membros_inalterados
        quality_summary["staged_rows_purged"] = staged_rows_purged
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
            change_summary=change_summary,
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
