from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.services.ingestion.dedup import STATUSS_REAPROVEITAVEIS_EXECUCAO
from app.services.ingestion.sql_batches import iter_lookup_batches


def empty_change_summary() -> dict[str, Any]:
    return {
        "member_added": [],
        "member_removed": [],
        "required_member_missing": [],
        "optional_member_missing": [],
        "header_changed": [],
        "schema_changed": [],
        "row_count_changed": [],
        "delivery_index_changed": [],
    }


def previous_successful_members(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    current_run_id: Any,
) -> dict[str, IngestionFileMember]:
    previous_run = db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano == ano,
            IngestionRun.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
            IngestionRun.id != current_run_id,
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    if previous_run is None:
        return {}
    members = (
        db.execute(
            select(IngestionFileMember)
            .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
            .where(IngestionFile.ingestion_run_id == previous_run.id)
        )
        .scalars()
        .all()
    )
    return {member.member_name: member for member in members}


def finalize_member_change_summary(
    *,
    current_member_names: Iterable[str],
    previous_members: dict[str, IngestionFileMember],
    required_members: set[str],
    optional_members: set[str],
    change_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = empty_change_summary() if change_summary is None else dict(change_summary)
    current_names = set(current_member_names)
    previous_names = set(previous_members)
    summary["member_added"] = sorted(current_names - previous_names)
    summary["member_removed"] = sorted(previous_names - current_names)
    summary["required_member_missing"] = sorted(required_members - current_names)
    summary["optional_member_missing"] = sorted(optional_members - current_names)
    return summary


def compare_member_with_previous(
    *,
    member: IngestionFileMember,
    previous_members: dict[str, IngestionFileMember],
    change_summary: dict[str, Any],
) -> dict[str, Any]:
    previous_member = previous_members.get(member.member_name)
    if previous_member is None:
        return change_summary

    summary = dict(change_summary)
    header_changed = list(summary.get("header_changed", []))
    schema_changed = list(summary.get("schema_changed", []))

    if list(previous_member.header or []) != list(member.header or []):
        header_changed.append(
            {
                "member_name": member.member_name,
                "before": list(previous_member.header or []),
                "after": list(member.header or []),
            }
        )

    if (
        previous_member.schema_status != member.schema_status
        or (previous_member.schema_message or None) != (member.schema_message or None)
    ):
        schema_changed.append(
            {
                "member_name": member.member_name,
                "before_status": previous_member.schema_status,
                "after_status": member.schema_status,
                "before_message": previous_member.schema_message,
                "after_message": member.schema_message,
            }
        )

    if previous_member.row_count != member.row_count:
        row_count_changed = list(summary.get("row_count_changed", []))
        row_count_changed.append(
            {
                "member_name": member.member_name,
                "before": previous_member.row_count,
                "after": member.row_count,
            }
        )
        summary["row_count_changed"] = row_count_changed

    summary["header_changed"] = header_changed
    summary["schema_changed"] = schema_changed
    return summary


def reconcile_promoted_rows(
    db: Session,
    *,
    model: type[Any],
    ingestion_run_id: Any,
    ingestion_file_member_id: Any,
    arquivo_origem: str,
    ano_origem: int | None,
    current_hashes: set[str],
) -> int:
    db.flush()
    existing_rows = db.execute(
        select(model.id, model.hash_origem).where(model.arquivo_origem == arquivo_origem, model.ano_origem == ano_origem)
    ).all()
    stale_ids = [row.id for row in existing_rows if row.hash_origem not in current_hashes]
    if not stale_ids:
        return 0

    deleted_count = 0
    for batch in iter_lookup_batches(stale_ids, parameter_width=1):
        deleted = db.execute(delete(model).where(model.id.in_(list(batch))))
        rowcount = getattr(deleted, "rowcount", None)
        deleted_count += int(rowcount if rowcount is not None else 0)
    return deleted_count
