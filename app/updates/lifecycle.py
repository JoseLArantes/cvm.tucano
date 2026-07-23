import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionPhaseExecution, IngestionRun
from app.updates.models import PendingUpdate

SUCCESSFUL_RUN_STATUSES = {"sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"}
FAILED_RUN_STATUSES = {"falha", "quality_fail", "cancelada"}
RECONCILABLE_UPDATE_STATUSES = {
    "triggered",
    "ingestion_queued",
    "ingesting",
    "ingested",
    "ingestion_failed",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _latest_retryable(db: Session, run: IngestionRun) -> bool:
    phase = db.scalar(
        select(IngestionPhaseExecution)
        .where(
            IngestionPhaseExecution.ingestion_run_id == run.id,
            IngestionPhaseExecution.phase == run.phase,
        )
        .order_by(
            IngestionPhaseExecution.attempt.desc(),
            IngestionPhaseExecution.created_at.desc(),
        )
        .limit(1)
    )
    return bool(phase is not None and phase.error_retryable is True)


def _is_terminal_success(run: IngestionRun) -> bool:
    return run.status in SUCCESSFUL_RUN_STATUSES and run.phase == "complete"


def _is_terminal_failure(run: IngestionRun) -> bool:
    return run.status in FAILED_RUN_STATUSES and (
        run.phase == "complete" or run.finished_at is not None
    )


def link_pending_update_to_run(
    db: Session,
    *,
    pending_update_id: str | uuid.UUID | None,
    run: IngestionRun,
) -> PendingUpdate | None:
    if pending_update_id is None:
        return None
    pending = db.get(PendingUpdate, uuid.UUID(str(pending_update_id)))
    if pending is None:
        return None

    pending.status = "triggered"
    pending.current_run_id = run.id
    pending.current_execution_id = run.execucao_sincronizacao_id
    return pending


def finalize_pending_update_for_run(
    db: Session,
    *,
    pending: PendingUpdate,
    run: IngestionRun,
) -> bool:
    if _is_terminal_success(run):
        pending.status = "ingested"
        pending.last_successful_run_id = run.id
        pending.ingestion_result = {
            "status": run.status,
            "run_id": str(run.id),
            "retryable": False,
            "next_action": "none",
        }
    elif _is_terminal_failure(run):
        retryable = _latest_retryable(db, run)
        pending.status = "ingestion_failed"
        pending.last_failed_run_id = run.id
        pending.ingestion_result = {
            "status": run.status,
            "run_id": str(run.id),
            "message": run.message,
            "retryable": retryable,
            "next_action": "retry_ingestion" if retryable else "inspect_error",
        }
    else:
        return False

    pending.resolved_timestamp = run.finished_at or _now()
    pending.resolved_by = "system:ingestion_lifecycle"
    pending.current_run_id = None
    pending.current_execution_id = None
    pending.ingestion_task_id = None
    return True


def reconcile_pending_updates(
    db: Session,
    *,
    pending_update_id: uuid.UUID | None = None,
) -> dict[str, int]:
    stmt = select(PendingUpdate).where(
        PendingUpdate.status.in_(RECONCILABLE_UPDATE_STATUSES)
    )
    if pending_update_id is not None:
        stmt = stmt.where(PendingUpdate.id == pending_update_id)

    checked = 0
    updated = 0
    for pending in db.scalars(stmt).all():
        checked += 1
        run: IngestionRun | None = None

        if pending.current_run_id is not None:
            run = db.get(IngestionRun, pending.current_run_id)
        elif pending.current_execution_id is not None:
            run = db.scalar(
                select(IngestionRun)
                .where(
                    IngestionRun.execucao_sincronizacao_id
                    == pending.current_execution_id
                )
                .order_by(IngestionRun.created_at.desc())
                .limit(1)
            )
        elif (
            pending.status == "triggered"
            and pending.last_successful_run_id is not None
        ):
            # Read-repair estritamente limitado ao formato legado comprovável.
            run = db.get(IngestionRun, pending.last_successful_run_id)

        if run is None:
            continue
        if finalize_pending_update_for_run(db, pending=pending, run=run):
            updated += 1
        elif pending.status in {"ingestion_queued", "ingesting"}:
            pending.status = "triggered"
            pending.current_run_id = run.id
            pending.current_execution_id = run.execucao_sincronizacao_id
            updated += 1

    if updated:
        db.commit()
    return {"checked": checked, "updated": updated}


def finalize_pending_update_by_run_id(
    db: Session,
    *,
    pending_update_id: str | uuid.UUID | None,
    run: IngestionRun | None,
) -> bool:
    if pending_update_id is None or run is None:
        return False
    pending = db.get(PendingUpdate, uuid.UUID(str(pending_update_id)))
    if pending is None:
        return False
    return finalize_pending_update_for_run(db, pending=pending, run=run)
