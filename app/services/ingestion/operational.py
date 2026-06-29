from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion import IngestionCancellationRequest, IngestionPhaseExecution, IngestionRun

_settings = get_settings()

_RUN_STATUS_TO_PHASE_STATUS = {
    "agendada": "pending",
    "aguardando_ingestao": "pending",
    "em_execucao": "running",
    "sucesso": "succeeded",
    "sucesso_com_alerta": "succeeded",
    "sem_alteracao": "succeeded",
    "skipped": "skipped",
    "falha": "failed_final",
    "cancelada": "cancelled",
}
_TERMINAL_PHASE_STATUSES = {"succeeded", "skipped", "failed_final", "cancelled"}


def _agora() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _phase_status_for_run_status(status: str | None) -> str:
    if not status:
        return "running"
    return _RUN_STATUS_TO_PHASE_STATUS.get(status, "running")


def _latest_phase_execution_stmt(*, run_id: Any) -> Any:
    return (
        select(IngestionPhaseExecution)
        .where(IngestionPhaseExecution.ingestion_run_id == run_id)
        .order_by(IngestionPhaseExecution.started_at.desc(), IngestionPhaseExecution.created_at.desc())
        .limit(1)
    )


def get_latest_phase_execution(db: Session, *, run_id: Any) -> IngestionPhaseExecution | None:
    phase_execution = db.scalar(_latest_phase_execution_stmt(run_id=run_id))
    return phase_execution if isinstance(phase_execution, IngestionPhaseExecution) else None


def list_phase_executions(db: Session, *, run_id: Any) -> list[IngestionPhaseExecution]:
    return list(
        db.scalars(
            select(IngestionPhaseExecution)
            .where(IngestionPhaseExecution.ingestion_run_id == run_id)
            .order_by(IngestionPhaseExecution.started_at.asc(), IngestionPhaseExecution.created_at.asc())
        ).all()
    )


def sync_phase_execution(
    db: Session,
    *,
    run: IngestionRun,
    previous_phase: str | None,
    previous_status: str | None,
    message: str | None,
    quality_summary: dict[str, Any] | None = None,
    force_create: bool = False,
) -> IngestionPhaseExecution:
    now = _agora()
    target_phase = run.phase
    target_status = _phase_status_for_run_status(run.status)
    latest = get_latest_phase_execution(db, run_id=run.id)

    if latest is not None and latest.phase != target_phase and latest.finished_at is None:
        previous_phase_status = _phase_status_for_run_status(previous_status)
        if previous_phase_status in {"running", "pending"}:
            latest.status = "succeeded"
        else:
            latest.status = previous_phase_status
        latest.finished_at = now
        latest.heartbeat_at = latest.heartbeat_at or now
        if latest.status == "cancelled":
            latest.cancel_requested_at = latest.cancel_requested_at or now
            latest.cancelled_at = latest.cancelled_at or now
            latest.cancel_reason = latest.cancel_reason or message
        elif latest.status == "failed_final":
            latest.error_message = latest.error_message or message
            latest.error_type = latest.error_type or "run_failed"
            latest.error_retryable = False

    if latest is not None and latest.phase == target_phase and latest.finished_at is None and not force_create:
        phase_exec = latest
    else:
        latest_same_phase = db.scalar(
            select(IngestionPhaseExecution)
            .where(
                IngestionPhaseExecution.ingestion_run_id == run.id,
                IngestionPhaseExecution.phase == target_phase,
            )
            .order_by(IngestionPhaseExecution.attempt.desc())
            .limit(1)
        )
        next_attempt = 1 if latest_same_phase is None else latest_same_phase.attempt + 1
        phase_exec = IngestionPhaseExecution(
            ingestion_run_id=run.id,
            execucao_sincronizacao_id=run.execucao_sincronizacao_id,
            phase=target_phase,
            status=target_status,
            attempt=next_attempt,
            lease_owner=run.requested_by_task_id,
            task_id=run.requested_by_task_id,
            started_at=now,
            heartbeat_at=now if target_status == "running" else None,
            metrics=quality_summary,
        )
        db.add(phase_exec)
        db.flush()

    phase_exec.execucao_sincronizacao_id = run.execucao_sincronizacao_id
    phase_exec.task_id = run.requested_by_task_id
    phase_exec.lease_owner = run.requested_by_task_id
    phase_exec.status = target_status
    if quality_summary is not None:
        phase_exec.metrics = quality_summary
    if target_status == "running":
        phase_exec.started_at = phase_exec.started_at or now
        phase_exec.heartbeat_at = now
        phase_exec.finished_at = None
    elif target_status == "pending":
        phase_exec.started_at = phase_exec.started_at or now
        phase_exec.finished_at = None
    elif target_status == "cancelled":
        phase_exec.cancel_requested_at = phase_exec.cancel_requested_at or now
        phase_exec.cancelled_at = now
        phase_exec.cancel_reason = message or phase_exec.cancel_reason
        phase_exec.finished_at = phase_exec.finished_at or now
    elif target_status == "failed_final":
        phase_exec.error_type = phase_exec.error_type or "run_failed"
        phase_exec.error_message = message or phase_exec.error_message
        phase_exec.error_retryable = False
        phase_exec.finished_at = phase_exec.finished_at or now
        phase_exec.heartbeat_at = phase_exec.heartbeat_at or now
    elif target_status in _TERMINAL_PHASE_STATUSES:
        phase_exec.finished_at = phase_exec.finished_at or now
        phase_exec.heartbeat_at = phase_exec.heartbeat_at or now

    return phase_exec


def register_cancellation_request(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    execucao_sincronizacao_id: Any = None,
    ingestion_run_id: Any = None,
    requested_by: str | None = None,
    reason: str | None = None,
    terminate_immediately: bool = True,
    status: str = "requested",
    affected_task_ids: list[str] | None = None,
    affected_execution_ids: list[str] | None = None,
) -> IngestionCancellationRequest:
    request = IngestionCancellationRequest(
        scope_type=scope_type,
        scope_id=scope_id,
        execucao_sincronizacao_id=execucao_sincronizacao_id,
        ingestion_run_id=ingestion_run_id,
        requested_by=requested_by,
        reason=reason,
        terminate_immediately=terminate_immediately,
        status=status,
        affected_task_ids=affected_task_ids,
        affected_execution_ids=affected_execution_ids,
    )
    db.add(request)
    db.flush()
    return request


def update_cancellation_request(
    request: IngestionCancellationRequest,
    *,
    status: str,
    affected_task_ids: list[str] | None = None,
    affected_execution_ids: list[str] | None = None,
) -> IngestionCancellationRequest:
    now = _agora()
    request.status = status
    if affected_task_ids is not None:
        request.affected_task_ids = affected_task_ids
    if affected_execution_ids is not None:
        request.affected_execution_ids = affected_execution_ids
    if status in {"propagated", "acknowledged", "completed"}:
        request.propagated_at = request.propagated_at or now
    if status == "completed":
        request.completed_at = now
    return request


def latest_cancellation_request_for_run(
    db: Session,
    *,
    run_id: Any,
) -> IngestionCancellationRequest | None:
    return db.scalar(
        select(IngestionCancellationRequest)
        .where(IngestionCancellationRequest.ingestion_run_id == run_id)
        .order_by(IngestionCancellationRequest.created_at.desc())
        .limit(1)
    )


def latest_cancellation_request_for_execucao(
    db: Session,
    *,
    execucao_id: Any,
) -> IngestionCancellationRequest | None:
    return db.scalar(
        select(IngestionCancellationRequest)
        .where(IngestionCancellationRequest.execucao_sincronizacao_id == execucao_id)
        .order_by(IngestionCancellationRequest.created_at.desc())
        .limit(1)
    )


def build_liveness_snapshot(
    phase_execution: IngestionPhaseExecution | None,
) -> dict[str, Any] | None:
    if phase_execution is None:
        return None
    heartbeat_at = _as_utc(phase_execution.heartbeat_at)
    stale_after_seconds = _settings.ingestion_phase_stale_after_seconds
    stale_cutoff = _agora() - timedelta(seconds=stale_after_seconds)
    is_stale = bool(
        phase_execution.status == "running"
        and heartbeat_at is not None
        and heartbeat_at < stale_cutoff
    )
    age_seconds = None
    if heartbeat_at is not None:
        age_seconds = int((_agora() - heartbeat_at).total_seconds())
    return {
        "heartbeat_at": heartbeat_at,
        "lease_owner": phase_execution.lease_owner,
        "task_id": phase_execution.task_id,
        "phase_status": phase_execution.status,
        "is_stale": is_stale,
        "stale_after_seconds": stale_after_seconds,
        "heartbeat_age_seconds": age_seconds,
    }
