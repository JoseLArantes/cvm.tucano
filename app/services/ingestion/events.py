"""Consulta incremental para o stream SSE operacional de ingestao.

O stream nao substitui os recursos REST: ele publica apenas invalidacoes compactas
derivadas do ledger persistido para que qualquer consumidor autorizado decida qual
recurso reler.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analise import AnaliseMaterializacaoCampanha
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def revision_for(value: datetime, *, entity_type: str, entity_id: str) -> str:
    return f"{int(_aware(value).timestamp() * 1_000_000):020d}:{entity_type}:{entity_id}"


def revision_timestamp(revision: str | None) -> datetime | None:
    if not revision:
        return None
    try:
        microseconds = int(revision.split(":", 1)[0])
    except ValueError:
        return None
    return datetime.fromtimestamp(microseconds / 1_000_000, tz=UTC)


def _event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | None,
    occurred_at: datetime,
    reason_code: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    revision = revision_for(occurred_at, entity_type=entity_type, entity_id=entity_id or "global")
    return {
        "event_id": revision,
        "revision": revision,
        "occurred_at": _aware(occurred_at).isoformat(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "reason_code": reason_code,
        "data": data,
        "event_type": event_type,
    }


def list_operational_events(
    db: Session,
    *,
    after_revision: str | None,
    scope: str | None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Retorna mudanças persistidas posteriores à revisão, em ordem estável."""
    after = revision_timestamp(after_revision)
    source: str | None = None
    year: int | None = None
    if scope:
        source, separator, year_text = scope.partition(":")
        if not separator or not source:
            raise ValueError("INVALID_SCOPE_CURSOR")
        year = int(year_text) if year_text else None

    run_stmt = select(IngestionRun).order_by(IngestionRun.updated_at.asc()).limit(limit)
    if after is not None:
        run_stmt = run_stmt.where(IngestionRun.updated_at > after)
    if source is not None:
        run_stmt = run_stmt.where(IngestionRun.tipo_fonte == source, IngestionRun.ano == year)
    runs = list(db.scalars(run_stmt).all())

    events: list[dict[str, Any]] = []
    for run in runs:
        occurred_at = run.updated_at
        payload = {"run_id": str(run.id), "source": run.tipo_fonte, "year": run.ano, "state": run.status, "phase": run.phase}
        events.append(_event(event_type="ingestion.run.updated", entity_type="run", entity_id=str(run.id), occurred_at=occurred_at, reason_code="RUN_CHANGED", data=payload))
        events.append(_event(event_type="ingestion.work_item.updated", entity_type="work_item", entity_id=f"{run.tipo_fonte}:{'' if run.ano is None else run.ano}", occurred_at=occurred_at, reason_code="RUN_CHANGED", data=payload))

    member_stmt = (
        select(IngestionFileMember, IngestionRun)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
        .order_by(IngestionFileMember.updated_at.asc())
        .limit(limit)
    )
    if after is not None:
        member_stmt = member_stmt.where(IngestionFileMember.updated_at > after)
    if source is not None:
        member_stmt = member_stmt.where(IngestionRun.tipo_fonte == source, IngestionRun.ano == year)
    for member, run in db.execute(member_stmt).all():
        events.append(_event(event_type="ingestion.member.updated", entity_type="member", entity_id=str(member.id), occurred_at=member.updated_at, reason_code="MEMBER_CHANGED", data={"run_id": str(run.id), "source": run.tipo_fonte, "year": run.ano, "member_name": member.member_name, "schema_status": member.schema_status}))

    materialization_stmt = select(AnaliseMaterializacaoCampanha).order_by(AnaliseMaterializacaoCampanha.updated_at.asc()).limit(limit)
    if after is not None:
        materialization_stmt = materialization_stmt.where(AnaliseMaterializacaoCampanha.updated_at > after)
    for campaign in db.scalars(materialization_stmt).all():
        events.append(_event(event_type="ingestion.materialization.updated", entity_type="materialization", entity_id=str(campaign.id), occurred_at=campaign.updated_at, reason_code="MATERIALIZATION_CHANGED", data={"status": campaign.status, "source": campaign.source, "source_execution_id": None if campaign.source_execucao_id is None else str(campaign.source_execucao_id)}))

    if events:
        latest = max(events, key=lambda event: event["revision"])
        occurred_at = datetime.fromisoformat(latest["occurred_at"])
        events.append(_event(event_type="ingestion.operations.updated", entity_type="operations", entity_id=None, occurred_at=occurred_at, reason_code="OPERATIONAL_LEDGER_CHANGED", data={"source_event_id": latest["event_id"]}))
        events.append(_event(event_type="ingestion.queue.updated", entity_type="queue", entity_id="ingestion", occurred_at=occurred_at, reason_code="OPERATIONAL_LEDGER_CHANGED", data={"queue": "ingestion"}))
    events.sort(key=lambda event: event["revision"])
    return events[:limit]
