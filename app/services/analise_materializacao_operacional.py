from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analise import (
    AnaliseMaterializacaoCampanha,
    AnaliseMaterializacaoCampanhaItem,
    AnaliseMaterializacaoChunkExecucao,
    AnaliseMaterializacaoExecucao,
    AnaliseMaterializacaoReconciliacao,
)

OperationalState = Literal[
    "active",
    "queued",
    "waiting_for_gate",
    "completion_pending",
    "stalled_recoverable",
    "stalled_unrecoverable",
    "terminal_success",
    "terminal_failed",
    "unknown",
]


@dataclass(frozen=True)
class MaterializationOperationalSnapshot:
    operational_state: OperationalState
    reason_code: str
    last_activity_at: datetime | None
    age_seconds: int | None
    has_active_task: bool
    task_inspection_available: bool
    has_active_chunk: bool
    has_active_lease: bool
    is_stalled: bool
    stalled_threshold_seconds: int
    technical_progress_complete: bool
    total_knowledge_dates: int | None
    processed_knowledge_dates: int | None
    finalization_pending: bool
    completion_reason_code: str
    recovery_eligible: bool
    recovery_strategy: str | None
    recovery_reason_code: str
    allowed_actions: tuple[dict[str, Any], ...]

    @property
    def has_action_required(self) -> bool:
        return bool(self.allowed_actions)

    def evidence(self) -> dict[str, Any]:
        return {
            "operational_state": self.operational_state,
            "reason_code": self.reason_code,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "age_seconds": self.age_seconds,
            "has_active_task": self.has_active_task,
            "task_inspection_available": self.task_inspection_available,
            "has_active_chunk": self.has_active_chunk,
            "has_active_lease": self.has_active_lease,
            "is_stalled": self.is_stalled,
            "technical_progress_complete": self.technical_progress_complete,
            "processed_knowledge_dates": self.processed_knowledge_dates,
            "total_knowledge_dates": self.total_knowledge_dates,
            "recovery": {
                "eligible": self.recovery_eligible,
                "strategy": self.recovery_strategy,
                "reason_code": self.recovery_reason_code,
            },
        }


class MaterializationReconcileConflict(Exception):
    def __init__(
        self,
        *,
        reason_code: str,
        snapshot: MaterializationOperationalSnapshot,
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.snapshot = snapshot


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _latest_activity(
    execution: AnaliseMaterializacaoExecucao,
    chunk: AnaliseMaterializacaoChunkExecucao | None,
    item: AnaliseMaterializacaoCampanhaItem | None,
) -> datetime | None:
    values = [
        _utc(execution.updated_at),
        _utc(execution.started_at),
        _utc(chunk.heartbeat_at) if chunk else None,
        _utc(chunk.updated_at) if chunk else None,
        _utc(item.updated_at) if item else None,
    ]
    return max((value for value in values if value is not None), default=None)


def _progress(execution: AnaliseMaterializacaoExecucao) -> tuple[int | None, int | None]:
    summary = execution.summary if isinstance(execution.summary, dict) else {}
    progress = summary.get("progress")
    progress = progress if isinstance(progress, dict) else {}
    total = progress.get("total_knowledge_dates", summary.get("window_total_knowledge_dates"))
    processed = progress.get(
        "processed_knowledge_dates",
        summary.get("window_processed_knowledge_dates"),
    )
    return (
        total if isinstance(total, int) and total >= 0 else None,
        processed if isinstance(processed, int) and processed >= 0 else None,
    )


def build_materialization_operational_snapshot(
    db: Session,
    execution: AnaliseMaterializacaoExecucao,
    *,
    active_task_ids: set[str],
    task_inspection_available: bool,
    gate_status: str,
    gate_reason_code: str,
    stalled_threshold_seconds: int,
    now: datetime | None = None,
) -> MaterializationOperationalSnapshot:
    reference_time = _utc(now) or datetime.now(UTC)
    chunk = (
        db.get(AnaliseMaterializacaoChunkExecucao, execution.chunk_execucao_id)
        if execution.chunk_execucao_id is not None
        else None
    )
    item = (
        db.get(AnaliseMaterializacaoCampanhaItem, execution.campanha_item_id)
        if execution.campanha_item_id is not None
        else None
    )
    campanha = (
        db.get(AnaliseMaterializacaoCampanha, execution.campanha_id)
        if execution.campanha_id is not None
        else None
    )
    last_activity_at = _latest_activity(execution, chunk, item)
    age_seconds = (
        max(0, int((reference_time - last_activity_at).total_seconds()))
        if last_activity_at is not None
        else None
    )
    is_stalled = age_seconds is not None and age_seconds >= stalled_threshold_seconds
    lease_expires_at = _utc(chunk.lease_expires_at) if chunk else None
    has_active_lease = bool(
        chunk is not None
        and chunk.status in {"queued", "running"}
        and (lease_expires_at is None or lease_expires_at >= reference_time)
    )
    has_active_chunk = has_active_lease
    has_active_task = bool(
        execution.task_id
        and task_inspection_available
        and execution.task_id in active_task_ids
    )
    total, processed = _progress(execution)
    technical_complete = total is not None and processed is not None and processed >= total
    summary = execution.summary if isinstance(execution.summary, dict) else {}
    has_terminal_error = bool(summary.get("error") or (item.last_error if item else None))
    stale_chunk = bool(
        chunk is not None
        and (
            chunk.status == "stale"
            or (
                chunk.status in {"queued", "running"}
                and lease_expires_at is not None
                and lease_expires_at < reference_time
            )
        )
    )
    recovery_eligible = bool(
        stale_chunk
        and campanha is not None
        and campanha.status in {"pending", "running"}
        and item is not None
        and item.status in {"pending", "running"}
    )
    recovery_strategy = "recover_stale_chunk" if recovery_eligible else None
    recovery_reason = "STALE_CHUNK" if recovery_eligible else "NO_RECOVERY_SOURCE"

    operational_state: OperationalState
    reason_code: str
    if execution.status == "success":
        operational_state = "terminal_success"
        reason_code = "EXECUTION_SUCCEEDED"
    elif execution.status == "failed":
        operational_state = "terminal_failed"
        reason_code = "EXECUTION_FAILED"
    elif has_active_task or has_active_chunk:
        operational_state = "active"
        reason_code = "ACTIVE_WORK_PRESENT"
    elif execution.started_at is None:
        operational_state = "queued"
        reason_code = "EXECUTION_NOT_STARTED"
    elif gate_status == "red" and not technical_complete:
        operational_state = "waiting_for_gate"
        reason_code = gate_reason_code
    elif (
        technical_complete
        and is_stalled
        and task_inspection_available
        and not has_terminal_error
        and gate_status != "red"
    ):
        operational_state = "completion_pending"
        reason_code = "EXECUTION_FINALIZATION_MISSING"
    elif recovery_eligible:
        operational_state = "stalled_recoverable"
        reason_code = "STALE_CHUNK"
    elif is_stalled:
        operational_state = "stalled_unrecoverable"
        if not task_inspection_available and execution.task_id is not None:
            reason_code = "TASK_INSPECTION_UNAVAILABLE"
        elif has_terminal_error:
            reason_code = "TERMINAL_ERROR_RECORDED"
        elif technical_complete and gate_status == "red":
            reason_code = "GATE_BLOCKS_FINALIZATION"
        else:
            reason_code = "NO_RECOVERY_SOURCE"
    else:
        operational_state = "unknown"
        reason_code = "INSUFFICIENT_TERMINAL_EVIDENCE"

    finalization_pending = operational_state == "completion_pending"
    if finalization_pending:
        completion_reason = "EXECUTION_FINALIZATION_MISSING"
    elif technical_complete:
        completion_reason = "TECHNICAL_PROGRESS_COMPLETE"
    else:
        completion_reason = "TECHNICAL_PROGRESS_INCOMPLETE"

    actions: list[dict[str, Any]] = []
    if operational_state == "completion_pending":
        actions.append(
            {
                "code": "reconcile_terminal",
                "operation": "POST",
                "path": f"/analise/materializacoes/{execution.id}/reconcile",
                "requires_confirmation": True,
                "reason_code": "EXECUTION_FINALIZATION_MISSING",
            }
        )
    elif operational_state == "stalled_recoverable" and execution.campanha_id:
        actions.append(
            {
                "code": "recover_stale_chunk",
                "operation": "POST",
                "path": f"/analise/materializacoes/campanhas/{execution.campanha_id}/reativar",
                "requires_confirmation": True,
                "reason_code": "STALE_CHUNK",
            }
        )
    elif (
        operational_state == "stalled_unrecoverable"
        and task_inspection_available
        and not has_active_task
        and not has_active_chunk
    ):
        actions.append(
            {
                "code": "reconcile_terminal",
                "operation": "POST",
                "path": f"/analise/materializacoes/{execution.id}/reconcile",
                "requires_confirmation": True,
                "reason_code": reason_code,
            }
        )

    return MaterializationOperationalSnapshot(
        operational_state=operational_state,
        reason_code=reason_code,
        last_activity_at=last_activity_at,
        age_seconds=age_seconds,
        has_active_task=has_active_task,
        task_inspection_available=task_inspection_available,
        has_active_chunk=has_active_chunk,
        has_active_lease=has_active_lease,
        is_stalled=is_stalled,
        stalled_threshold_seconds=stalled_threshold_seconds,
        technical_progress_complete=technical_complete,
        total_knowledge_dates=total,
        processed_knowledge_dates=processed,
        finalization_pending=finalization_pending,
        completion_reason_code=completion_reason,
        recovery_eligible=recovery_eligible,
        recovery_strategy=recovery_strategy,
        recovery_reason_code=recovery_reason,
        allowed_actions=tuple(actions),
    )


def reconcile_materialization_execution(
    db: Session,
    execution: AnaliseMaterializacaoExecucao,
    *,
    decision: Literal["auto", "mark_success", "mark_failed"],
    reason: str,
    actor: str,
    snapshot: MaterializationOperationalSnapshot,
    now: datetime | None = None,
) -> AnaliseMaterializacaoReconciliacao | None:
    if execution.status in {"success", "failed"}:
        return db.scalar(
            select(AnaliseMaterializacaoReconciliacao)
            .where(AnaliseMaterializacaoReconciliacao.execucao_id == execution.id)
            .order_by(AnaliseMaterializacaoReconciliacao.created_at.desc())
            .limit(1)
        )
    if snapshot.has_active_task or snapshot.has_active_chunk or snapshot.has_active_lease:
        raise MaterializationReconcileConflict(
            reason_code="ACTIVE_WORK_PRESENT",
            snapshot=snapshot,
        )

    if decision == "mark_success":
        if snapshot.operational_state != "completion_pending":
            raise MaterializationReconcileConflict(
                reason_code="SUCCESS_INVARIANTS_NOT_SATISFIED",
                snapshot=snapshot,
            )
        target_status = "success"
        reason_code = "TECHNICAL_PROGRESS_COMPLETE_NO_ACTIVE_WORK"
    elif decision == "mark_failed":
        if not snapshot.task_inspection_available and execution.task_id is not None:
            raise MaterializationReconcileConflict(
                reason_code="TASK_INSPECTION_UNAVAILABLE",
                snapshot=snapshot,
            )
        target_status = "failed"
        reason_code = "TERMINAL_INCONSISTENCY_MARKED_FAILED"
    elif snapshot.operational_state == "completion_pending":
        target_status = "success"
        reason_code = "TECHNICAL_PROGRESS_COMPLETE_NO_ACTIVE_WORK"
    elif snapshot.operational_state in {"stalled_unrecoverable", "stalled_recoverable"}:
        target_status = "failed"
        reason_code = "TERMINAL_INCONSISTENCY_MARKED_FAILED"
    else:
        raise MaterializationReconcileConflict(
            reason_code="INSUFFICIENT_TERMINAL_EVIDENCE",
            snapshot=snapshot,
        )

    reconciled_at = _utc(now) or datetime.now(UTC)
    previous_status = execution.status
    evidence = snapshot.evidence()
    execution.status = target_status
    execution.coverage_complete = target_status == "success"
    execution.finished_at = reconciled_at
    execution.updated_at = reconciled_at
    execution.summary = {
        **(execution.summary or {}),
        "operational_reconciliation": {
            "decision": decision,
            "previous_status": previous_status,
            "status": target_status,
            "reconciled_at": reconciled_at.isoformat(),
            "reconciled_by": actor,
            "reason_code": reason_code,
            "reason": reason,
            "evidence": evidence,
        },
    }
    audit = AnaliseMaterializacaoReconciliacao(
        execucao_id=execution.id,
        decision=decision,
        previous_status=previous_status,
        status=target_status,
        reconciled_by=actor,
        reason_code=reason_code,
        reason=reason,
        evidence=evidence,
        created_at=reconciled_at,
    )
    db.add(audit)

    item = (
        db.get(AnaliseMaterializacaoCampanhaItem, execution.campanha_item_id)
        if execution.campanha_item_id is not None
        else None
    )
    if item is not None and item.status in {"pending", "running"}:
        item.status = target_status
        item.materializacao_execucao_id = execution.id
        item.finished_at = reconciled_at
        item.updated_at = reconciled_at
        item.last_error = None if target_status == "success" else reason
        campanha = db.get(AnaliseMaterializacaoCampanha, item.campanha_id)
        if campanha is not None:
            from app.services.analise import _recalcular_materializacao_campanha

            _recalcular_materializacao_campanha(db, campanha)

    db.commit()
    db.refresh(audit)
    return audit


def reconcile_completion_pending_executions(
    db: Session,
    *,
    active_task_ids: set[str],
    task_inspection_available: bool,
    gate_status: str,
    gate_reason_code: str,
    stalled_threshold_seconds: int,
    limit: int = 100,
) -> dict[str, Any]:
    checked = 0
    reconciled_ids: list[str] = []
    if not task_inspection_available:
        return {
            "status": "capacity_unavailable",
            "reason_code": "TASK_INSPECTION_UNAVAILABLE",
            "checked": 0,
            "reconciled_execution_ids": [],
        }
    executions = db.scalars(
        select(AnaliseMaterializacaoExecucao)
        .where(AnaliseMaterializacaoExecucao.status == "running")
        .order_by(AnaliseMaterializacaoExecucao.updated_at.asc())
        .limit(limit)
    ).all()
    for execution in executions:
        checked += 1
        snapshot = build_materialization_operational_snapshot(
            db,
            execution,
            active_task_ids=active_task_ids,
            task_inspection_available=task_inspection_available,
            gate_status=gate_status,
            gate_reason_code=gate_reason_code,
            stalled_threshold_seconds=stalled_threshold_seconds,
        )
        if snapshot.operational_state != "completion_pending":
            continue
        reconcile_materialization_execution(
            db,
            execution,
            decision="auto",
            reason="Reconciliação automática de execução com progresso técnico integral e sem trabalho ativo.",
            actor="system:materialization_reconciler",
            snapshot=snapshot,
        )
        reconciled_ids.append(str(execution.id))
    return {
        "status": "success",
        "reason_code": "RECONCILIATION_SWEEP_COMPLETED",
        "checked": checked,
        "reconciled_execution_ids": reconciled_ids,
    }
