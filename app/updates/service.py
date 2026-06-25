from __future__ import annotations

import hashlib
import os
import shutil
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.services.ingestion.acquisition import _head_remote_resource, probe_remote_source
from app.services.ingestion.file_manager import (
    compute_file_sha256,
    count_csv_rows,
    detect_encoding_and_delimiter,
    download_file_to_disk,
    get_csv_header,
)
from app.services.ingestion.source_registry import listar_datasets, listar_fontes
from app.updates.models import PendingUpdate, PendingUpdateMember, UpdateScanRun, UpdateSession, UpdateSessionItem


def _agora() -> datetime:
    return datetime.now(UTC)


def _header_hash(header: list[str] | None) -> str | None:
    if not header:
        return None
    return hashlib.sha256("|".join(header).encode("utf-8")).hexdigest()


def get_last_successful_run(db: Session, tipo_fonte: str, ano: int | None) -> IngestionRun | None:
    stmt = (
        select(IngestionRun)
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano == ano,
            IngestionRun.status.in_(["sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"])
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


def get_source_url(settings: Any, fonte: str, ano: int | None) -> str:
    if fonte == "cadastro":
        return f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    tipo_formulario = fonte.upper()
    arquivo_zip = f"{fonte}_cia_aberta_{ano}.zip"
    return f"{settings.cvm_base_url}/CIA_ABERTA/DOC/{tipo_formulario}/DADOS/{arquivo_zip}"


def _mark_pending_stale(pending: PendingUpdate, *, resolved_by: str = "scanner") -> None:
    pending.status = "stale"
    pending.resolved_timestamp = _agora()
    pending.resolved_by = resolved_by


def _has_confirmed_artifact_change(probe_res: dict[str, Any]) -> bool:
    return probe_res.get("decision") == "changed"


def _probe_cadastro_sources(db: Session, settings: Any) -> dict[str, Any]:
    url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
    urls = [url_aberta, url_estrang]

    previous_run = get_last_successful_run(db, "cadastro", None)
    previous_files_by_url: dict[str, IngestionFile] = {}
    if previous_run is not None:
        previous_files_by_url = {item.source_url: item for item in get_successful_files(db, previous_run.id)}

    changed_sources: list[dict[str, Any]] = []
    matched_sources: list[str] = []
    unknown_sources: list[str] = []

    for url in urls:
        probe = _head_remote_resource(url, timeout=30.0)
        previous_file = previous_files_by_url.get(url)
        if previous_file is None:
            changed_sources.append({"url": url, "reason": "sem_referencia_anterior", "probe": probe})
            continue

        current_etag = probe.get("resource_etag")
        previous_etag = previous_file.etag
        if current_etag is not None and previous_etag is not None:
            if current_etag != previous_etag:
                changed_sources.append({"url": url, "reason": "metadata_changed:resource_etag", "probe": probe})
            else:
                matched_sources.append(url)
            continue

        current_last_modified = probe.get("resource_last_modified")
        current_length = probe.get("resource_content_length")
        previous_last_modified = previous_file.last_modified
        previous_length = (
            str(previous_file.content_length_bytes)
            if previous_file.content_length_bytes is not None
            else None
        )
        if (
            current_last_modified is not None
            and previous_last_modified is not None
            and current_length is not None
            and previous_length is not None
        ):
            if current_last_modified != previous_last_modified or current_length != previous_length:
                changed_sources.append(
                    {
                        "url": url,
                        "reason": "metadata_changed:resource_last_modified,resource_content_length",
                        "probe": probe,
                    }
                )
            else:
                matched_sources.append(url)
            continue

        unknown_sources.append(url)

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
            },
        }

    return {
        "decision": "unchanged" if len(matched_sources) == len(urls) else "unknown",
        "decision_reason": "all_sources_matched" if len(matched_sources) == len(urls) else "metadados_inconclusivos",
        "artifact_url": f"{url_aberta}|{url_estrang}",
        "probe_etag": None,
        "probe_last_modified": None,
        "probe_content_length": None,
        "change_summary": {
            "changed_sources": [],
            "matched_sources": matched_sources,
            "unknown_sources": unknown_sources,
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


def create_scan_run(db: Session) -> UpdateScanRun:
    now = _agora()
    scan_run = UpdateScanRun(status="queued", created_at=now, updated_at=now)
    db.add(scan_run)
    db.commit()
    db.refresh(scan_run)
    return scan_run


def get_latest_scan_run(db: Session) -> UpdateScanRun | None:
    return db.scalar(select(UpdateScanRun).order_by(UpdateScanRun.created_at.desc()).limit(1))


def run_scanner(db: Session, *, scan_run_id: uuid.UUID | None = None) -> dict[str, Any]:
    settings = get_settings()
    detected_updates: list[PendingUpdate] = []
    scan_run = db.get(UpdateScanRun, scan_run_id) if scan_run_id is not None else None
    if scan_run is not None:
        scan_run.status = "running"
        scan_run.started_at = _agora()
        db.commit()

    scan_items: list[dict[str, Any]] = []

    try:
        fontes = listar_fontes()
        for fonte_reg in fontes:
            tipo_fonte = fonte_reg.fonte

            scopes: list[tuple[int | None, str | None]]
            if tipo_fonte == "cadastro":
                scopes = [(None, None)]
            else:
                anos_config = getattr(settings, f"anos_iniciais_{tipo_fonte}", "")
                anos = settings.parse_anos(anos_config)
                scopes = [(ano, get_source_url(settings, tipo_fonte, ano)) for ano in anos]

            for ano, url in scopes:
                scan_item: dict[str, Any] = {
                    "fonte": tipo_fonte,
                    "ano": ano,
                }
                stmt = select(PendingUpdate).where(
                    PendingUpdate.fonte == tipo_fonte,
                    PendingUpdate.ano == ano,
                    PendingUpdate.status.in_(["change_detected", "analysis_queued", "analyzing", "ready_for_ingestion"])
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
                        artifact_url = str(url)
                    scan_item.update(
                        {
                            "artifact_url": artifact_url,
                            "artifact_decision": probe_res.get("decision", "unknown"),
                            "decision_reason": probe_res.get("decision_reason"),
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
                    if existing is not None:
                        _mark_pending_stale(existing)
                        scan_item["existing_pending_action"] = "marked_stale"
                    stop_reason = "artifact_unchanged" if probe_res.get("decision") == "unchanged" else "probe_inconclusive"
                    scan_item["member_scan"] = {"analyzed": False, "stop_reason": stop_reason}
                    scan_items.append(scan_item)
                    continue

                last_run = get_last_successful_run(db, tipo_fonte, ano)
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
                analyzed_pending = run_deep_analysis(db, pending.id)
                scan_item["pending_update_id"] = str(pending.id)
                scan_item["pending_status"] = analyzed_pending.status
                scan_item["member_scan"] = _build_member_scan_summary(db, pending.id)
                scan_items.append(scan_item)

        result = {
            "status": "success",
            "scanned_scopes": len(scan_items),
            "detected_count": len(detected_updates),
            "unchanged_count": sum(1 for item in scan_items if item.get("artifact_decision") == "unchanged"),
            "changed_count": sum(1 for item in scan_items if item.get("artifact_decision") == "changed"),
            "inconclusive_count": sum(1 for item in scan_items if item.get("artifact_decision") == "unknown"),
            "error_count": sum(1 for item in scan_items if item.get("artifact_decision") == "error"),
            "detected_ids": [str(item.id) for item in detected_updates],
            "items": scan_items,
        }
        if scan_run is not None:
            scan_run.status = "completed"
            scan_run.finished_at = _agora()
            scan_run.summary = result
        db.commit()
        return result
    except Exception:
        if scan_run is not None:
            db.rollback()
            scan_run = db.get(UpdateScanRun, scan_run.id)
            if scan_run is not None:
                scan_run.status = "failed"
                scan_run.finished_at = _agora()
                scan_run.summary = {
                    "status": "failed",
                    "items": scan_items,
                }
                db.commit()
        raise


def run_deep_analysis(db: Session, pending_update_id: uuid.UUID) -> PendingUpdate:
    settings = get_settings()
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    if pending.status not in ("change_detected", "analysis_queued"):
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

        if pending.fonte == "cadastro":
            # Cadastro downloads 2 files
            url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
            url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"

            dest_aberta = temp_dir / "cad_cia_aberta.csv"
            dest_estrang = temp_dir / "cad_cia_estrang.csv"

            hash_aberta = download_file_to_disk(url_aberta, str(dest_aberta))
            hash_estrang = download_file_to_disk(url_estrang, str(dest_estrang))

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
            download_file_to_disk(pending.artifact_url, str(zip_path))

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

        # Load previous successful members
        prev_members_by_name = {}
        if pending.last_successful_run_id:
            prev_members = get_successful_members(db, pending.last_successful_run_id)
            for pm in prev_members:
                prev_members_by_name[pm.member_name] = pm

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
                prev_sha = prev.member_sha256
                prev_rows = prev.row_count
                prev_hdr_hash = _header_hash(prev.header)

                if prev.member_sha256 == m_info["sha256"]:
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
                is_req = prev_name in required_names
                status_member = "required_missing" if is_req else "removed"
                
                if is_req:
                    required_missing.append(prev_name)
                else:
                    members_removed.append(prev_name)

                db.add(PendingUpdateMember(
                    pending_update_id=pending.id,
                    member_name=prev_name,
                    member_role=prev_member.delimiter, # reuse
                    previous_member_sha256=prev_member.member_sha256,
                    current_member_sha256=None,
                    previous_row_count=prev_member.row_count,
                    current_row_count=None,
                    previous_header_hash=_header_hash(prev_member.header),
                    current_header_hash=None,
                    change_category="removed",
                    row_kind=prev_member.encoding, # reuse
                    is_required=is_req,
                    status=status_member,
                ))

        pending.status = "ready_for_ingestion"
        pending.change_summary = {
            "artifact_changed": True,
            "members_added": members_added,
            "members_removed": members_removed,
            "members_modified": members_modified,
            "required_missing": required_missing,
            "total_changes": len(members_added) + len(members_removed) + len(members_modified) + len(required_missing),
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


def trigger_update(db: Session, pending_update_id: uuid.UUID, user: str | None = None) -> str:
    pending = db.get(PendingUpdate, pending_update_id)
    if pending is None:
        raise ValueError(f"PendingUpdate not found: {pending_update_id}")

    if pending.status != "ready_for_ingestion":
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
