from __future__ import annotations

import hashlib
import os
import shutil
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion import (
    IngestionFile,
    IngestionFileMember,
    IngestionRun,
    SourceArtifactSnapshot,
    SourceMemberSnapshot,
)
from app.services.ingestion.acquisition import _head_remote_resource, probe_remote_source
from app.services.ingestion.file_manager import (
    compute_file_sha256,
    count_csv_rows,
    detect_encoding_and_delimiter,
    download_file_to_disk,
    get_csv_header,
)
from app.services.ingestion.source_registry import DatasetFonte, listar_datasets, listar_fontes
from app.updates.models import (
    AcknowledgedArtifactReference,
    PendingUpdate,
    PendingUpdateMember,
    UpdateScanRun,
    UpdateSession,
    UpdateSessionItem,
)


def _agora() -> datetime:
    return datetime.now(UTC)


def _header_hash(header: list[str] | None) -> str | None:
    if not header:
        return None
    return hashlib.sha256("|".join(header).encode("utf-8")).hexdigest()


def _dataset_for_member_name(fonte: str, ano: int | None, member_name: str) -> DatasetFonte | None:
    for dataset in listar_datasets(fonte):
        try:
            rendered_name = dataset.render_member_name(ano=ano)
        except ValueError:
            continue
        if rendered_name == member_name:
            return dataset
    return None


def _load_previous_member_baselines(
    db: Session,
    *,
    fonte: str,
    ano: int | None,
    run_id: uuid.UUID | None,
) -> dict[str, dict[str, Any]]:
    if run_id is None:
        return {}

    baselines: dict[str, dict[str, Any]] = {}
    snapshots = list(
        db.scalars(
            select(SourceMemberSnapshot)
            .join(SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id)
            .where(SourceArtifactSnapshot.ingestion_run_id == run_id)
        ).all()
    )
    for snapshot in snapshots:
        baselines[snapshot.member_name] = {
            "member_name": snapshot.member_name,
            "member_sha256": snapshot.member_sha256,
            "row_count": snapshot.row_count,
            "header_hash": snapshot.header_hash,
            "header": snapshot.header,
            "row_kind": snapshot.row_kind,
            "is_required": snapshot.required_member,
            "member_role": snapshot.delivery_index_role,
            "baseline_source": "source_member_snapshot",
        }

    previous_members = get_successful_members(db, run_id)
    for member in previous_members:
        if member.member_name in baselines:
            continue
        dataset = _dataset_for_member_name(fonte, ano, member.member_name)
        baselines[member.member_name] = {
            "member_name": member.member_name,
            "member_sha256": member.member_sha256,
            "row_count": member.row_count,
            "header_hash": _header_hash(member.header),
            "header": member.header,
            "row_kind": None if dataset is None else dataset.row_kind,
            "is_required": False if dataset is None else dataset.obrigatorio,
            "member_role": "none" if dataset is None else dataset.delivery_index_role,
            "baseline_source": "ingestion_file_member",
        }

    return baselines


def get_last_successful_run(db: Session, tipo_fonte: str, ano: int | None) -> IngestionRun | None:
    stmt = (
        select(IngestionRun)
        .outerjoin(IngestionFile, IngestionFile.ingestion_run_id == IngestionRun.id)
        .outerjoin(SourceArtifactSnapshot, SourceArtifactSnapshot.ingestion_run_id == IngestionRun.id)
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano == ano,
            IngestionRun.status.in_(["sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"]),
            or_(IngestionFile.id.is_not(None), SourceArtifactSnapshot.id.is_not(None)),
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def get_successful_members(db: Session, run_id: uuid.UUID) -> list[IngestionFileMember]:
    stmt = (
        select(IngestionFileMember)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .where(IngestionFile.ingestion_run_id == run_id)
    )
    return list(db.scalars(stmt).all())


def get_successful_files(db: Session, run_id: uuid.UUID) -> list[IngestionFile]:
    stmt = select(IngestionFile).where(IngestionFile.ingestion_run_id == run_id)
    return list(db.scalars(stmt).all())


def _resource_key(resource_url: str) -> str:
    return hashlib.sha256(resource_url.encode("utf-8")).hexdigest()


def _latest_acknowledged_references(
    db: Session,
    *,
    fonte: str,
    ano: int | None,
    baseline_ingestion_run_id: uuid.UUID | None,
) -> dict[str, AcknowledgedArtifactReference]:
    if baseline_ingestion_run_id is None:
        return {}
    references = db.scalars(
        select(AcknowledgedArtifactReference)
        .where(
            AcknowledgedArtifactReference.fonte == fonte,
            AcknowledgedArtifactReference.ano == ano,
            AcknowledgedArtifactReference.baseline_ingestion_run_id == baseline_ingestion_run_id,
        )
        .order_by(AcknowledgedArtifactReference.confirmed_at.desc())
    ).all()
    by_url: dict[str, AcknowledgedArtifactReference] = {}
    for reference in references:
        by_url.setdefault(reference.resource_url, reference)
    return by_url


def _resolve_probe_against_acknowledged_reference(
    probe: dict[str, Any],
    reference: AcknowledgedArtifactReference | None,
) -> dict[str, Any]:
    if reference is None:
        return probe

    current_etag = probe.get("resource_etag")
    current_last_modified = probe.get("resource_last_modified")
    current_content_length = probe.get("resource_content_length")
    reference_content_length = (
        str(reference.remote_content_length) if reference.remote_content_length is not None else None
    )

    decision: str | None = None
    reason: str | None = None
    confidence: str | None = None
    if current_etag is not None and reference.remote_etag is not None:
        matched = current_etag == reference.remote_etag
        decision = "unchanged" if matched else "changed"
        reason = f"acknowledged_reference_{'matched' if matched else 'changed'}:resource_etag"
        confidence = "strong"
    elif (
        current_last_modified is not None
        and reference.remote_last_modified is not None
        and current_content_length is not None
        and reference_content_length is not None
    ):
        matched = (
            current_last_modified == reference.remote_last_modified
            and str(current_content_length) == reference_content_length
        )
        decision = "unchanged" if matched else "changed"
        reason = (
            f"acknowledged_reference_{'matched' if matched else 'changed'}:"
            "resource_last_modified,resource_content_length"
        )
        confidence = "medium"

    if decision is None:
        return probe

    probe["decision"] = decision
    probe["decision_reason"] = reason
    probe["confidence"] = confidence
    probe["download_required"] = decision == "changed"
    probe["acknowledged_reference_id"] = str(reference.id)
    probe["probe_sources"] = list(
        dict.fromkeys([*probe.get("probe_sources", []), "acknowledged_reference"])
    )
    return probe


def get_source_url(settings: Any, fonte: str, ano: int | None) -> str:
    if fonte == "cadastro":
        return f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    tipo_formulario = fonte.upper()
    arquivo_zip = f"{fonte}_cia_aberta_{ano}.zip"
    return f"{settings.cvm_base_url}/CIA_ABERTA/DOC/{tipo_formulario}/DADOS/{arquivo_zip}"


def _successful_ingested_years(db: Session, tipo_fonte: str) -> list[int]:
    years = db.scalars(
        select(IngestionRun.ano)
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano.is_not(None),
            IngestionRun.status.in_(["sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"]),
        )
        .distinct()
        .order_by(IngestionRun.ano.asc())
    ).all()
    return [year for year in years if year is not None]


def _scanner_scopes_for_source(db: Session, settings: Any, tipo_fonte: str) -> list[tuple[int | None, str | None]]:
    if tipo_fonte == "cadastro":
        return [(None, None)]
    return [
        (year, get_source_url(settings, tipo_fonte, year))
        for year in _successful_ingested_years(db, tipo_fonte)
    ]


def _mark_pending_stale(pending: PendingUpdate, *, resolved_by: str = "scanner") -> None:
    pending.status = "stale"
    pending.resolved_timestamp = _agora()
    pending.resolved_by = resolved_by


def _has_confirmed_artifact_change(probe_res: dict[str, Any]) -> bool:
    return probe_res.get("decision") == "changed"


def _pending_matches_probe(pending: PendingUpdate, probe: dict[str, Any]) -> bool:
    current_etag = probe.get("probe_etag", probe.get("resource_etag"))
    if pending.probe_etag is not None and current_etag is not None:
        return pending.probe_etag == str(current_etag)

    current_last_modified = probe.get("probe_last_modified", probe.get("resource_last_modified"))
    current_length = probe.get("probe_content_length", probe.get("resource_content_length"))
    return (
        pending.probe_last_modified is not None
        and current_last_modified is not None
        and pending.probe_content_length is not None
        and current_length is not None
        and pending.probe_last_modified == str(current_last_modified)
        and str(pending.probe_content_length) == str(current_length)
    )


def _probe_cadastro_sources(db: Session, settings: Any) -> dict[str, Any]:
    url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
    sources = [
        (url_aberta, "cad_cia_aberta.csv"),
        (url_estrang, "cad_cia_estrang.csv"),
    ]

    previous_run = get_last_successful_run(db, "cadastro", None)
    acknowledged_references = _latest_acknowledged_references(
        db,
        fonte="cadastro",
        ano=None,
        baseline_ingestion_run_id=previous_run.id if previous_run is not None else None,
    )
    previous_files_by_url: dict[str, IngestionFile] = {}
    previous_members_by_name: dict[str, dict[str, Any]] = {}
    if previous_run is not None:
        previous_files_by_url = {item.source_url: item for item in get_successful_files(db, previous_run.id)}
        previous_members_by_name = _load_previous_member_baselines(
            db,
            fonte="cadastro",
            ano=None,
            run_id=previous_run.id,
        )

    changed_sources: list[dict[str, Any]] = []
    matched_sources: list[str] = []
    unknown_sources: list[str] = []
    checks: list[dict[str, Any]] = []
    probe_dir = Path(settings.temp_dir) / "scanner_probe" / str(uuid.uuid4())

    try:
        for url, member_name in sources:
            probe = _head_remote_resource(url, timeout=30.0)
            probe = _resolve_probe_against_acknowledged_reference(
                probe,
                acknowledged_references.get(url),
            )
            previous_file = previous_files_by_url.get(url)
            previous_member = previous_members_by_name.get(member_name)
            reason: str | None = None
            changed: bool | None = None
            current_sha256: str | None = None

            if probe.get("decision") in {"changed", "unchanged"}:
                changed = probe["decision"] == "changed"
                reason = str(probe.get("decision_reason"))
            else:
                current_etag = probe.get("resource_etag")
                previous_etag = previous_file.etag if previous_file is not None else None
                if current_etag is not None and previous_etag is not None:
                    changed = current_etag != previous_etag
                    reason = "metadata_changed:resource_etag" if changed else "metadata_matched:resource_etag"
                else:
                    current_last_modified = probe.get("resource_last_modified")
                    current_length = probe.get("resource_content_length")
                    previous_last_modified = previous_file.last_modified if previous_file is not None else None
                    previous_length = (
                        str(previous_file.content_length_bytes)
                        if previous_file is not None and previous_file.content_length_bytes is not None
                        else None
                    )
                    if (
                        current_last_modified is not None
                        and previous_last_modified is not None
                        and current_length is not None
                        and previous_length is not None
                    ):
                        changed = current_last_modified != previous_last_modified or current_length != previous_length
                        reason = (
                            "metadata_changed:resource_last_modified,resource_content_length"
                            if changed
                            else "metadata_matched:resource_last_modified,resource_content_length"
                        )

            if changed is None and previous_member is not None and previous_member.get("member_sha256"):
                current_sha256 = download_file_to_disk(
                    url,
                    str(probe_dir / member_name),
                    timeout=120.0,
                )
                changed = current_sha256 != previous_member["member_sha256"]
                reason = "content_changed:sha256" if changed else "content_matched:sha256"
                probe["probe_sources"] = [*probe.get("probe_sources", []), "content_sha256"]

            if changed is None and previous_file is None and previous_member is None:
                changed = True
                reason = "sem_referencia_anterior"

            check = {
                "url": url,
                "member_name": member_name,
                "decision": "changed" if changed is True else "unchanged" if changed is False else "unknown",
                "decision_reason": reason or "metadados_e_hash_inconclusivos",
                "probe_sources": probe.get("probe_sources", []),
                "resource_etag": probe.get("resource_etag"),
                "resource_last_modified": probe.get("resource_last_modified"),
                "resource_content_length": probe.get("resource_content_length"),
                "content_sha256": current_sha256,
            }
            checks.append(check)
            if changed is True:
                changed_sources.append({"url": url, "reason": check["decision_reason"], "probe": probe})
            elif changed is False:
                matched_sources.append(url)
            else:
                unknown_sources.append(url)
    finally:
        if probe_dir.exists():
            shutil.rmtree(probe_dir)

    if changed_sources:
        first_changed = changed_sources[0]
        first_probe = first_changed["probe"]
        return {
            "decision": "changed",
            "decision_reason": first_changed["reason"],
            "artifact_url": f"{url_aberta}|{url_estrang}",
            "probe_etag": first_probe.get("resource_etag"),
            "probe_last_modified": first_probe.get("resource_last_modified"),
            "probe_content_length": first_probe.get("resource_content_length"),
            "change_summary": {
                "changed_sources": [item["url"] for item in changed_sources],
                "matched_sources": matched_sources,
                "unknown_sources": unknown_sources,
                "checks": checks,
            },
        }

    return {
        "decision": "unchanged" if len(matched_sources) == len(sources) else "unknown",
        "decision_reason": "all_sources_matched" if len(matched_sources) == len(sources) else "metadados_inconclusivos",
        "artifact_url": f"{url_aberta}|{url_estrang}",
        "probe_etag": None,
        "probe_last_modified": None,
        "probe_content_length": None,
        "change_summary": {
            "changed_sources": [],
            "matched_sources": matched_sources,
            "unknown_sources": unknown_sources,
            "checks": checks,
        },
    }


def _serialize_pending_member(member: PendingUpdateMember) -> dict[str, Any]:
    return {
        "member_name": member.member_name,
        "status": member.status,
        "change_category": member.change_category,
        "previous_member_sha256": member.previous_member_sha256,
        "current_member_sha256": member.current_member_sha256,
        "previous_row_count": member.previous_row_count,
        "current_row_count": member.current_row_count,
        "previous_header_hash": member.previous_header_hash,
        "current_header_hash": member.current_header_hash,
        "is_required": member.is_required,
        "row_kind": member.row_kind,
        "member_role": member.member_role,
    }


def _build_member_scan_summary(db: Session, pending_update_id: uuid.UUID) -> dict[str, Any]:
    members = list(
        db.scalars(
            select(PendingUpdateMember)
            .where(PendingUpdateMember.pending_update_id == pending_update_id)
            .order_by(PendingUpdateMember.member_name.asc())
        ).all()
    )
    changed_members = [
        member.member_name
        for member in members
        if member.change_category in {"added", "removed", "modified"} or member.status in {"schema_changed", "required_missing"}
    ]
    unchanged_members = [member.member_name for member in members if member.change_category == "unchanged"]
    return {
        "analyzed": True,
        "total_members": len(members),
        "changed_members": changed_members,
        "unchanged_members": unchanged_members,
        "changed_count": len(changed_members),
        "unchanged_count": len(unchanged_members),
        "members": [_serialize_pending_member(member) for member in members],
    }


def create_scan_run(db: Session, *, trigger: str = "manual") -> UpdateScanRun:
    now = _agora()
    scan_run = UpdateScanRun(
        status="queued",
        summary={"trigger": trigger},
        created_at=now,
        updated_at=now,
    )
    db.add(scan_run)
    db.commit()
    db.refresh(scan_run)
    return scan_run


def get_latest_scan_run(db: Session) -> UpdateScanRun | None:
    return db.scalar(select(UpdateScanRun).order_by(UpdateScanRun.created_at.desc()).limit(1))


def get_latest_scheduled_scan_run(db: Session) -> UpdateScanRun | None:
    return db.scalar(
        select(UpdateScanRun)
        .where(UpdateScanRun.summary["trigger"].as_string() == "scheduled")
        .order_by(UpdateScanRun.created_at.desc())
        .limit(1)
    )


def list_scan_runs(
    db: Session,
    *,
    status: str | None,
    offset: int,
    limit: int,
) -> tuple[list[UpdateScanRun], int]:
    filters = [UpdateScanRun.status == status] if status is not None else []
    total = int(db.scalar(select(func.count(UpdateScanRun.id)).where(*filters)) or 0)
    runs = list(
        db.scalars(
            select(UpdateScanRun)
            .where(*filters)
            .order_by(UpdateScanRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return runs, total


def get_scanner_status_snapshot(
    db: Session,
    *,
    stale_after_hours: int,
    scanner_enabled: bool = True,
    schedule_enabled: bool = True,
) -> dict[str, Any]:
    latest = get_latest_scan_run(db)
    latest_scheduled = get_latest_scheduled_scan_run(db) if schedule_enabled else None
    if latest is None:
        return {
            "status": "idle",
            "health_status": "never_run" if scanner_enabled else "disabled",
            "scanner_enabled": scanner_enabled,
            "schedule_enabled": schedule_enabled,
            "schedule_status": "never_run" if schedule_enabled else "disabled",
            "expected_interval_hours": 24,
            "stale_after_hours": stale_after_hours,
        }

    summary = latest.summary if isinstance(latest.summary, dict) else {}
    operational_status = "running" if latest.status in {"queued", "running"} else "idle"
    reference_at = latest.finished_at or latest.started_at or latest.created_at
    if reference_at.tzinfo is None:
        reference_at = reference_at.replace(tzinfo=UTC)
    stale = _agora() - reference_at > timedelta(hours=stale_after_hours)
    degraded = (
        latest.status == "failed"
        or int(summary.get("inconclusive_count") or 0) > 0
        or int(summary.get("error_count") or 0) > 0
        or int(summary.get("skipped_count") or 0) > 0
        or summary.get("coverage_status") == "degraded"
    )
    scheduled_reference_at = None
    if latest_scheduled is not None:
        scheduled_reference_at = (
            latest_scheduled.finished_at
            or latest_scheduled.started_at
            or latest_scheduled.created_at
        )
        if scheduled_reference_at.tzinfo is None:
            scheduled_reference_at = scheduled_reference_at.replace(tzinfo=UTC)

    if not schedule_enabled:
        schedule_status = "disabled"
    elif latest_scheduled is None:
        schedule_status = "never_run"
    elif latest_scheduled.status in {"queued", "running"}:
        schedule_status = "running"
    elif latest_scheduled.status == "failed":
        schedule_status = "degraded"
    elif scheduled_reference_at is not None and _agora() - scheduled_reference_at > timedelta(hours=stale_after_hours):
        schedule_status = "stale"
    else:
        schedule_status = "healthy"

    if not scanner_enabled:
        health_status = "disabled"
    elif latest.status in {"queued", "running"}:
        health_status = "running"
    elif stale:
        health_status = "stale"
    elif degraded:
        health_status = "degraded"
    elif schedule_status in {"degraded", "stale"}:
        health_status = schedule_status
    elif schedule_status == "never_run":
        health_status = "degraded"
    else:
        health_status = "healthy"
    return {
        "status": operational_status,
        "health_status": health_status,
        "scanner_enabled": scanner_enabled,
        "schedule_enabled": schedule_enabled,
        "schedule_status": schedule_status,
        "last_run": reference_at,
        "last_scan_run_id": str(latest.id),
        "last_scan_status": latest.status,
        "last_scan_started_at": latest.started_at,
        "last_scan_finished_at": latest.finished_at,
        "last_scheduled_scan_run_id": str(latest_scheduled.id) if latest_scheduled is not None else None,
        "last_scheduled_scan_status": latest_scheduled.status if latest_scheduled is not None else None,
        "last_scheduled_scan_started_at": latest_scheduled.started_at if latest_scheduled is not None else None,
        "last_scheduled_scan_finished_at": latest_scheduled.finished_at if latest_scheduled is not None else None,
        "expected_interval_hours": 24,
        "stale_after_hours": stale_after_hours,
        "trigger": summary.get("trigger"),
        "coverage_status": summary.get("coverage_status"),
        "expected_scopes": int(summary.get("expected_scopes") or 0),
        "scanned_scopes": int(summary.get("scanned_scopes") or 0),
        "changed_count": int(summary.get("changed_count") or 0),
        "unchanged_count": int(summary.get("unchanged_count") or 0),
        "inconclusive_count": int(summary.get("inconclusive_count") or 0),
        "error_count": int(summary.get("error_count") or 0),
        "skipped_count": int(summary.get("skipped_count") or 0),
        "sources_without_scope": list(summary.get("sources_without_scope") or []),
    }


def run_scanner(
    db: Session,
    *,
    scan_run_id: uuid.UUID | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    settings = get_settings()
    detected_updates: list[PendingUpdate] = []
    scan_run = db.get(UpdateScanRun, scan_run_id) if scan_run_id is not None else create_scan_run(db, trigger=trigger)
    if scan_run is None:
        raise ValueError(f"UpdateScanRun not found: {scan_run_id}")
    trigger = str((scan_run.summary or {}).get("trigger") or trigger)
    scan_run.status = "running"
    scan_run.started_at = _agora()
    db.commit()

    scan_items: list[dict[str, Any]] = []
    sources_without_scope: list[str] = []
    try:
        fontes = listar_fontes()
        for fonte_reg in fontes:
            tipo_fonte = fonte_reg.fonte
            scopes = _scanner_scopes_for_source(db, settings, tipo_fonte)
            if not scopes:
                sources_without_scope.append(tipo_fonte)
                scan_items.append(
                    {
                        "fonte": tipo_fonte,
                        "ano": None,
                        "artifact_url": None,
                        "artifact_decision": "skipped",
                        "decision_reason": "no_successful_ingestion_baseline",
                        "member_scan": {"analyzed": False, "stop_reason": "no_scan_scope"},
                    }
                )
                continue

            for ano, url in scopes:
                last_run = get_last_successful_run(db, tipo_fonte, ano)
                scan_item: dict[str, Any] = {
                    "fonte": tipo_fonte,
                    "ano": ano,
                }
                stmt = select(PendingUpdate).where(
                    PendingUpdate.fonte == tipo_fonte,
                    PendingUpdate.ano == ano,
                    PendingUpdate.status.in_([
                        "change_detected",
                        "analysis_queued",
                        "analyzing",
                        "ready_for_ingestion",
                        "content_unchanged",
                    ])
                )
                existing = db.scalar(stmt)

                try:
                    if tipo_fonte == "cadastro":
                        probe_res = _probe_cadastro_sources(db, settings)
                        artifact_url = str(probe_res["artifact_url"])
                    else:
                        dummy_run = IngestionRun(id=uuid.uuid4(), tipo_fonte=tipo_fonte, ano=ano)
                        probe_res = probe_remote_source(
                            db,
                            run=dummy_run,
                            tipo_fonte=tipo_fonte,
                            ano=ano,
                            source_url=str(url),
                            timeout=30.0
                        )
                        acknowledged_references = _latest_acknowledged_references(
                            db,
                            fonte=tipo_fonte,
                            ano=ano,
                            baseline_ingestion_run_id=last_run.id if last_run is not None else None,
                        )
                        probe_res = _resolve_probe_against_acknowledged_reference(
                            probe_res,
                            acknowledged_references.get(str(url)),
                        )
                        artifact_url = str(url)
                    scan_item.update(
                        {
                            "artifact_url": artifact_url,
                            "artifact_decision": probe_res.get("decision", "unknown"),
                            "decision_reason": str(probe_res.get("decision_reason") or "decision_without_reason"),
                            "probe_details": {
                                "probe_sources": list(probe_res.get("probe_sources") or []),
                                "confidence": probe_res.get("confidence"),
                                "current_reference": {
                                    "resource_etag": probe_res.get("resource_etag"),
                                    "resource_last_modified": probe_res.get("resource_last_modified"),
                                    "resource_content_length": probe_res.get("resource_content_length"),
                                },
                                "change_summary": probe_res.get("change_summary"),
                                "acknowledged_reference_id": probe_res.get("acknowledged_reference_id"),
                            },
                        }
                    )
                except Exception as exc:
                    scan_item.update(
                        {
                            "artifact_url": str(url) if url is not None else None,
                            "artifact_decision": "error",
                            "decision_reason": f"{type(exc).__name__}: {exc}",
                            "member_scan": {"analyzed": False, "stop_reason": "probe_error"},
                        }
                    )
                    scan_items.append(scan_item)
                    continue

                if not _has_confirmed_artifact_change(probe_res):
                    if existing is not None and probe_res.get("decision") == "unchanged":
                        _mark_pending_stale(existing)
                        scan_item["existing_pending_action"] = "marked_stale"
                    stop_reason = "artifact_unchanged" if probe_res.get("decision") == "unchanged" else "probe_inconclusive"
                    scan_item["member_scan"] = {"analyzed": False, "stop_reason": stop_reason}
                    scan_items.append(scan_item)
                    continue

                content_len = probe_res.get("probe_content_length", probe_res.get("resource_content_length"))
                probe_len = int(content_len) if content_len is not None and str(content_len).isdigit() else None

                pending = existing
                if pending is None:
                    pending = PendingUpdate(
                        fonte=tipo_fonte,
                        ano=ano,
                        status="change_detected",
                        detection_timestamp=_agora(),
                        last_probe_timestamp=_agora(),
                        probe_etag=probe_res.get("probe_etag", probe_res.get("resource_etag")),
                        probe_last_modified=probe_res.get("probe_last_modified", probe_res.get("resource_last_modified")),
                        probe_content_length=probe_len,
                        artifact_url=artifact_url,
                        change_type="artifact_changed",
                        change_summary=probe_res.get("change_summary"),
                        last_successful_run_id=last_run.id if last_run else None,
                    )
                    db.add(pending)
                    db.flush()
                    detected_updates.append(pending)
                else:
                    if pending.status == "content_unchanged" and _pending_matches_probe(pending, probe_res):
                        scan_item["pending_update_id"] = str(pending.id)
                        scan_item["pending_status"] = pending.status
                        scan_item["existing_pending_action"] = "awaiting_reference_update"
                        scan_item["member_scan"] = _build_member_scan_summary(db, pending.id)
                        scan_items.append(scan_item)
                        continue
                    if pending.status == "content_unchanged":
                        pending.status = "change_detected"
                    pending.last_probe_timestamp = _agora()
                    pending.probe_etag = probe_res.get("probe_etag", probe_res.get("resource_etag"))
                    pending.probe_last_modified = probe_res.get(
                        "probe_last_modified",
                        probe_res.get("resource_last_modified"),
                    )
                    pending.probe_content_length = probe_len
                    pending.change_summary = probe_res.get("change_summary")
                scan_item["pending_update_id"] = str(pending.id)
                if settings.auto_analyze_on_detect:
                    analyzed_pending = run_deep_analysis(db, pending.id)
                    scan_item["pending_status"] = analyzed_pending.status
                    scan_item["member_scan"] = _build_member_scan_summary(db, pending.id)
                else:
                    scan_item["pending_status"] = pending.status
                    scan_item["member_scan"] = {
                        "analyzed": False,
                        "stop_reason": "auto_analysis_disabled",
                    }
                scan_items.append(scan_item)

        checked_items = [item for item in scan_items if item.get("artifact_decision") != "skipped"]
        source_names_scanned = sorted({str(item["fonte"]) for item in checked_items})
        result = {
            "status": "success",
            "trigger": trigger,
            "source_count": len(fontes),
            "sources_scanned": source_names_scanned,
            "sources_without_scope": sorted(sources_without_scope),
            "expected_scopes": len(checked_items),
            "scanned_scopes": len(checked_items),
            "detected_count": len(detected_updates),
            "unchanged_count": sum(1 for item in checked_items if item.get("artifact_decision") == "unchanged"),
            "changed_count": sum(1 for item in checked_items if item.get("artifact_decision") == "changed"),
            "inconclusive_count": sum(1 for item in checked_items if item.get("artifact_decision") == "unknown"),
            "error_count": sum(1 for item in checked_items if item.get("artifact_decision") == "error"),
            "skipped_count": len(sources_without_scope),
            "detected_ids": [str(item.id) for item in detected_updates],
            "items": scan_items,
        }
        result["coverage_status"] = (
            "complete"
            if result["inconclusive_count"] == 0
            and result["error_count"] == 0
            and result["skipped_count"] == 0
            else "degraded"
        )
        scan_run.status = "completed"
        scan_run.finished_at = _agora()
        scan_run.summary = result
        db.commit()
        return result
    except Exception:
        db.rollback()
        scan_run = db.get(UpdateScanRun, scan_run.id)
        if scan_run is not None:
            scan_run.status = "failed"
            scan_run.finished_at = _agora()
            scan_run.summary = {
                "status": "failed",
                "trigger": trigger,
                "coverage_status": "degraded",
                "items": scan_items,
            }
            db.commit()
        raise


def run_deep_analysis(db: Session, pending_update_id: uuid.UUID) -> PendingUpdate:
    settings = get_settings()
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    if pending.status not in ("change_detected", "analysis_queued", "content_unchanged"):
        return pending

    pending.status = "analyzing"
    pending.analysis_timestamp = _agora()
    db.commit()

    temp_dir = Path(settings.temp_dir) / str(pending.id)
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        current_members_info: list[dict[str, Any]] = []
        previous_summary = dict(pending.change_summary or {})
        probe_summary = previous_summary.get("probe_summary")
        if not isinstance(probe_summary, dict):
            probe_summary = previous_summary if "total_changes" not in previous_summary else {}
        probe_checks = {
            str(check.get("url")): check
            for check in probe_summary.get("checks", [])
            if isinstance(check, dict) and check.get("url")
        }
        current_artifact_references: list[dict[str, Any]] = []

        if pending.fonte == "cadastro":
            # Cadastro downloads 2 files
            url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
            url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"

            dest_aberta = temp_dir / "cad_cia_aberta.csv"
            dest_estrang = temp_dir / "cad_cia_estrang.csv"

            hash_aberta = download_file_to_disk(url_aberta, str(dest_aberta))
            hash_estrang = download_file_to_disk(url_estrang, str(dest_estrang))
            for url, member_name, content_sha256 in (
                (url_aberta, "cad_cia_aberta.csv", hash_aberta),
                (url_estrang, "cad_cia_estrang.csv", hash_estrang),
            ):
                check = probe_checks.get(url, {})
                current_artifact_references.append(
                    {
                        "resource_url": url,
                        "member_name": member_name,
                        "remote_etag": check.get("resource_etag"),
                        "remote_last_modified": check.get("resource_last_modified"),
                        "remote_content_length": check.get("resource_content_length"),
                        "artifact_content_sha256": content_sha256,
                    }
                )

            # Abertas
            enc_ab, del_ab = detect_encoding_and_delimiter(str(dest_aberta))
            hdr_ab = get_csv_header(str(dest_aberta), enc_ab, del_ab)
            rows_ab = count_csv_rows(str(dest_aberta), enc_ab, del_ab)
            current_members_info.append({
                "name": "cad_cia_aberta.csv",
                "sha256": hash_aberta,
                "row_count": rows_ab,
                "header": hdr_ab,
                "header_hash": _header_hash(hdr_ab),
                "is_required": True,
            })

            # Estrangeiras
            enc_es, del_es = detect_encoding_and_delimiter(str(dest_estrang))
            hdr_es = get_csv_header(str(dest_estrang), enc_es, del_es)
            rows_es = count_csv_rows(str(dest_estrang), enc_es, del_es)
            current_members_info.append({
                "name": "cad_cia_estrang.csv",
                "sha256": hash_estrang,
                "row_count": rows_es,
                "header": hdr_es,
                "header_hash": _header_hash(hdr_es),
                "is_required": True,
            })
        else:
            # Zip downloads the annual zip
            zip_path = temp_dir / f"{pending.fonte}_cia_aberta_{pending.ano}.zip"
            artifact_content_sha256 = download_file_to_disk(pending.artifact_url, str(zip_path))
            current_artifact_references.append(
                {
                    "resource_url": pending.artifact_url,
                    "remote_etag": pending.probe_etag,
                    "remote_last_modified": pending.probe_last_modified,
                    "remote_content_length": pending.probe_content_length,
                    "artifact_content_sha256": artifact_content_sha256,
                }
            )

            # Extract members
            extracted_dir = temp_dir / "extracted"
            extracted_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path) as archive:
                member_names = [name for name in archive.namelist() if name.endswith(".csv")]
                for name in member_names:
                    archive.extract(name, path=extracted_dir)
                    extracted_file = extracted_dir / name
                    
                    sha = compute_file_sha256(str(extracted_file))
                    enc, delimiter = detect_encoding_and_delimiter(str(extracted_file))
                    hdr = get_csv_header(str(extracted_file), enc, delimiter)
                    rows = count_csv_rows(str(extracted_file), enc, delimiter)

                    current_members_info.append({
                        "name": name,
                        "sha256": sha,
                        "row_count": rows,
                        "header": hdr,
                        "header_hash": _header_hash(hdr),
                        "is_required": False,  # Default, will check registry below
                    })

        # Load datasets registry to check required flags and row kinds
        datasets = listar_datasets(pending.fonte)
        required_names = {d.render_member_name(ano=pending.ano or 0) for d in datasets if d.obrigatorio}
        row_kinds = {d.render_member_name(ano=pending.ano or 0): d.row_kind for d in datasets}
        roles = {d.render_member_name(ano=pending.ano or 0): d.delivery_index_role for d in datasets}

        for m_info in current_members_info:
            name = m_info["name"]
            if name in required_names:
                m_info["is_required"] = True
            m_info["row_kind"] = row_kinds.get(name)
            m_info["role"] = roles.get(name, "none")

        prev_members_by_name = _load_previous_member_baselines(
            db,
            fonte=pending.fonte,
            ano=pending.ano,
            run_id=pending.last_successful_run_id,
        )

        # Clear existing members
        db.execute(delete(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == pending.id))

        members_added = []
        members_removed = []
        members_modified = []
        required_missing = []

        # Compare current with previous
        seen_current = set()
        for m_info in current_members_info:
            name = m_info["name"]
            seen_current.add(name)

            prev = prev_members_by_name.get(name)
            if prev is None:
                change_cat = "added"
                status_member = "added"
                members_added.append(name)
                prev_sha = None
                prev_rows = None
                prev_hdr_hash = None
            else:
                prev_sha = prev["member_sha256"]
                prev_rows = prev["row_count"]
                prev_hdr_hash = prev["header_hash"]

                if prev_sha == m_info["sha256"]:
                    change_cat = "unchanged"
                    status_member = "unchanged"
                else:
                    if prev_hdr_hash != m_info["header_hash"]:
                        change_cat = "modified"
                        status_member = "schema_changed"
                        members_modified.append(name)
                    else:
                        change_cat = "modified"
                        status_member = "modified"
                        members_modified.append(name)

            db.add(PendingUpdateMember(
                pending_update_id=pending.id,
                member_name=name,
                member_role=m_info.get("role"),
                previous_member_sha256=prev_sha,
                current_member_sha256=m_info["sha256"],
                previous_row_count=prev_rows,
                current_row_count=m_info["row_count"],
                previous_header_hash=prev_hdr_hash,
                current_header_hash=m_info["header_hash"],
                change_category=change_cat,
                row_kind=m_info.get("row_kind"),
                is_required=m_info["is_required"],
                status=status_member,
            ))

        # Check for removed members
        for prev_name, prev_member in prev_members_by_name.items():
            if prev_name not in seen_current:
                is_req = bool(prev_member["is_required"])
                status_member = "required_missing" if is_req else "removed"
                
                if is_req:
                    required_missing.append(prev_name)
                else:
                    members_removed.append(prev_name)

                db.add(PendingUpdateMember(
                    pending_update_id=pending.id,
                    member_name=prev_name,
                    member_role=prev_member["member_role"],
                    previous_member_sha256=prev_member["member_sha256"],
                    current_member_sha256=None,
                    previous_row_count=prev_member["row_count"],
                    current_row_count=None,
                    previous_header_hash=prev_member["header_hash"],
                    current_header_hash=None,
                    change_category="removed",
                    row_kind=prev_member["row_kind"],
                    is_required=is_req,
                    status=status_member,
                ))

        total_changes = len(members_added) + len(members_removed) + len(members_modified) + len(required_missing)
        content_changed = total_changes > 0
        pending.status = "ready_for_ingestion" if content_changed else "content_unchanged"
        pending.change_type = "artifact_content_changed" if content_changed else "artifact_metadata_changed"
        pending.change_summary = {
            "artifact_changed": True,
            "content_changed": content_changed,
            "members_added": members_added,
            "members_removed": members_removed,
            "members_modified": members_modified,
            "required_missing": required_missing,
            "total_changes": total_changes,
            "recommended_action": "ingest" if content_changed else "update_reference",
            "current_artifact_references": current_artifact_references,
            "probe_summary": probe_summary,
        }
        db.commit()

    except Exception as exc:
        db.rollback()
        pending_erro = db.get(PendingUpdate, pending.id)
        if pending_erro:
            pending_erro.status = "analysis_failed"
            pending_erro.change_summary = {
                "error": type(exc).__name__,
                "details": str(exc)
            }
            db.commit()
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    return pending


def _pending_member_fingerprint(db: Session, pending_update_id: uuid.UUID) -> str:
    members = list(
        db.scalars(
            select(PendingUpdateMember)
            .where(PendingUpdateMember.pending_update_id == pending_update_id)
            .order_by(PendingUpdateMember.member_name.asc())
        ).all()
    )
    if not members:
        raise ValueError("PendingUpdate has no analyzed members to confirm content equivalence.")
    if any(
        member.change_category != "unchanged"
        or member.previous_member_sha256 is None
        or member.current_member_sha256 is None
        or member.previous_member_sha256 != member.current_member_sha256
        for member in members
    ):
        raise ValueError("PendingUpdate members do not prove content equivalence.")
    payload = "\n".join(
        f"{member.member_name}:{member.current_member_sha256}"
        for member in members
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def acknowledge_artifact_reference(
    db: Session,
    pending_update_id: uuid.UUID,
    *,
    user: str | None = None,
) -> tuple[PendingUpdate, list[AcknowledgedArtifactReference]]:
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    existing_references = list(
        db.scalars(
            select(AcknowledgedArtifactReference)
            .where(AcknowledgedArtifactReference.pending_update_id == pending.id)
            .order_by(AcknowledgedArtifactReference.resource_url.asc())
        ).all()
    )
    if pending.status == "reference_updated" and existing_references:
        return pending, existing_references

    total_changes = (pending.change_summary or {}).get("total_changes")
    if pending.status not in {"content_unchanged", "ready_for_ingestion"} or total_changes != 0:
        raise ValueError(
            f"PendingUpdate is in state '{pending.status}' and does not represent content-equivalent artifacts."
        )
    if pending.last_successful_run_id is None:
        raise ValueError("PendingUpdate has no canonical ingestion baseline.")

    member_fingerprint = _pending_member_fingerprint(db, pending.id)
    summary = pending.change_summary or {}
    raw_references = summary.get("current_artifact_references")
    references_payload = list(raw_references) if isinstance(raw_references, list) else []
    if not references_payload and "|" not in pending.artifact_url:
        references_payload = [
            {
                "resource_url": pending.artifact_url,
                "remote_etag": pending.probe_etag,
                "remote_last_modified": pending.probe_last_modified,
                "remote_content_length": pending.probe_content_length,
            }
        ]
    if not references_payload:
        raise ValueError("PendingUpdate has no remote references to acknowledge; run deep analysis again.")

    confirmed_at = _agora()
    created: list[AcknowledgedArtifactReference] = []
    for item in references_payload:
        if not isinstance(item, dict) or not item.get("resource_url"):
            continue
        resource_url = str(item["resource_url"])
        remote_content_length_raw = item.get("remote_content_length")
        remote_content_length = (
            int(remote_content_length_raw)
            if remote_content_length_raw is not None and str(remote_content_length_raw).isdigit()
            else None
        )
        if (
            item.get("remote_etag") is None
            and item.get("remote_last_modified") is None
            and remote_content_length is None
        ):
            raise ValueError(f"Remote reference for '{resource_url}' has no comparable HTTP metadata.")
        reference = AcknowledgedArtifactReference(
            pending_update_id=pending.id,
            baseline_ingestion_run_id=pending.last_successful_run_id,
            fonte=pending.fonte,
            ano=pending.ano,
            resource_url=resource_url,
            resource_key=_resource_key(resource_url),
            remote_etag=item.get("remote_etag"),
            remote_last_modified=item.get("remote_last_modified"),
            remote_content_length=remote_content_length,
            artifact_content_sha256=item.get("artifact_content_sha256"),
            member_fingerprint=member_fingerprint,
            confirmation_method="member_sha256",
            confirmed_by=user or "api",
            confirmed_at=confirmed_at,
        )
        db.add(reference)
        created.append(reference)

    if not created:
        raise ValueError("PendingUpdate has no valid remote references to acknowledge.")
    pending.status = "reference_updated"
    pending.resolved_timestamp = confirmed_at
    pending.resolved_by = user or "api"
    db.commit()
    for reference in created:
        db.refresh(reference)
    return pending, created


def trigger_update(db: Session, pending_update_id: uuid.UUID, user: str | None = None) -> str:
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    if pending.status != "ready_for_ingestion":
        if pending.status == "content_unchanged":
            raise ValueError(
                "PendingUpdate has no content changes; acknowledge the remote reference instead of ingesting."
            )
        raise ValueError(f"PendingUpdate is in state '{pending.status}', not 'ready_for_ingestion'.")

    # Mark triggered
    pending.status = "triggered"
    pending.resolved_timestamp = _agora()
    pending.resolved_by = user or "api"
    db.commit()

    # Call the ingestion workflow
    # Import tasks here to avoid circular imports
    from app.worker.tasks import (
        sincronizar_cadastro_companhias_task,
        sincronizar_cgvn_task,
        sincronizar_dfp_task,
        sincronizar_fca_task,
        sincronizar_fre_task,
        sincronizar_ipe_task,
        sincronizar_itr_task,
        sincronizar_vlmo_task,
    )

    task_map = {
        "dfp": sincronizar_dfp_task,
        "itr": sincronizar_itr_task,
        "fre": sincronizar_fre_task,
        "fca": sincronizar_fca_task,
        "ipe": sincronizar_ipe_task,
        "vlmo": sincronizar_vlmo_task,
        "cgvn": sincronizar_cgvn_task,
    }

    if pending.fonte == "cadastro":
        # Pass skip_probe=True and pending_update_id
        task_res = sincronizar_cadastro_companhias_task.delay(
            force_reimport=False,
            skip_probe=True,
            pending_update_id=str(pending.id)
        )
    else:
        task_func = task_map.get(pending.fonte)
        if task_func is None:
            raise ValueError(f"Invalid fonte: {pending.fonte}")
        
        task_res = task_func.delay(
            pending.ano,
            force_reimport=False,
            skip_probe=True,
            pending_update_id=str(pending.id)
        )

    # Return the run when it gets created, or we can fetch it once the task starts
    # Since the task is async, we return the Celery task ID
    return str(task_res.id)


def discard_update(db: Session, pending_update_id: uuid.UUID) -> PendingUpdate:
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    if pending.status in ("triggered", "discarded"):
        return pending

    pending.status = "discarded"
    pending.resolved_timestamp = _agora()
    db.commit()
    return pending


def create_session(db: Session, user_id: str | None = None) -> UpdateSession:
    session_key = hashlib.sha256(os.urandom(32)).hexdigest()
    expires_at = _agora() + timedelta(hours=24)
    
    sess = UpdateSession(
        session_key=session_key,
        user_id=user_id,
        expires_at=expires_at,
        status="active"
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def add_session_item(db: Session, session_key: str, pending_update_id: uuid.UUID) -> UpdateSessionItem:
    stmt_sess = select(UpdateSession).where(UpdateSession.session_key == session_key, UpdateSession.status == "active")
    sess = db.scalar(stmt_sess)
    if sess is None:
        raise ValueError("Active UpdateSession not found")

    expires_at = sess.expires_at
    now = _agora()
    if expires_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif expires_at.tzinfo is not None and now.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=None)

    if expires_at < now:
        sess.status = "expired"
        db.commit()
        raise ValueError("UpdateSession has expired")

    # Check pending update
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError("PendingUpdate not found")

    # Check if already exists in session
    stmt_item = select(UpdateSessionItem).where(
        UpdateSessionItem.session_id == sess.id,
        UpdateSessionItem.pending_update_id == pending_update_id
    )
    item = db.scalar(stmt_item)
    if item is not None:
        item.action = "selected"
        db.commit()
        return item

    item = UpdateSessionItem(
        session_id=sess.id,
        pending_update_id=pending_update_id,
        added_at=_agora(),
        action="selected"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove_session_item(db: Session, session_key: str, pending_update_id: uuid.UUID) -> None:
    stmt_sess = select(UpdateSession).where(UpdateSession.session_key == session_key, UpdateSession.status == "active")
    sess = db.scalar(stmt_sess)
    if sess is None:
        raise ValueError("Active UpdateSession not found")

    stmt_item = select(UpdateSessionItem).where(
        UpdateSessionItem.session_id == sess.id,
        UpdateSessionItem.pending_update_id == pending_update_id
    )
    item = db.scalar(stmt_item)
    if item is not None:
        db.delete(item)
        db.commit()


def trigger_session(db: Session, session_key: str, user: str | None = None) -> list[str]:
    stmt_sess = select(UpdateSession).where(UpdateSession.session_key == session_key, UpdateSession.status == "active")
    sess = db.scalar(stmt_sess)
    if sess is None:
        raise ValueError("Active UpdateSession not found")

    stmt_items = select(UpdateSessionItem).where(
        UpdateSessionItem.session_id == sess.id,
        UpdateSessionItem.action == "selected"
    )
    items = db.scalars(stmt_items).all()
    
    task_ids = []
    for item in items:
        try:
            tid = trigger_update(db, item.pending_update_id, user=user)
            if tid:
                task_ids.append(tid)
                item.action = "triggered"
        except Exception:
            continue

    db.commit()
    return task_ids


def cleanup_temp_files() -> int:
    settings = get_settings()
    temp_dir = Path(settings.temp_dir)
    if not temp_dir.exists():
        return 0

    cleaned = 0
    now = datetime.now()
    # Clean files older than 24 hours
    for path in temp_dir.iterdir():
        if path.is_dir():
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if now - mtime > timedelta(hours=24):
                try:
                    shutil.rmtree(path)
                    cleaned += 1
                except Exception:
                    pass
    return cleaned
