import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api.auth import AutenticacaoApi, autenticar_requisicao, exigir_admin_api, validar_token_api
from app.api.deps import DbSession
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.ingestion import (
    IngestionCancellationRequest,
    IngestionDispatchPlan,
    IngestionFile,
    IngestionFileMember,
    IngestionFinanceiroStageRow,
    IngestionIdempotencyRecord,
    IngestionOperationAudit,
    IngestionPhaseExecution,
    IngestionRow,
    IngestionRowEvent,
    IngestionRun,
    QuarantineItem,
    SourceArtifactSnapshot,
    SourceDeliverySnapshot,
    SourceMemberSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.schemas.admin import (
    AnaliseArquivo,
    ArquivoErroQuantidade,
    ArquivoQuantidade,
    AuditoriaFonteResposta,
    AuditoriaFontesRequisicao,
    AuditoriaFontesResposta,
    DashboardExecucoesResposta,
    ErroQuantidade,
    ExecucaoSincronizacaoDetalhe,
    ExecucaoSincronizacaoResumo,
    FonteDatasetResumoResposta,
    FonteDetalheResposta,
    FonteResumoResposta,
    HistoricoAlteracaoCampoResposta,
    IngestionDispatchPlanRequest,
    IngestionDispatchPlanResponse,
    IngestionDispatchRequest,
    IngestionDispatchResponse,
    IngestionFailureAcknowledgement,
    IngestionFailureAcknowledgementRequest,
    IngestionOperationRunPreview,
    IngestionOperationsResumo,
    IngestionRecovery,
    IngestionRunMemberResumo,
    IngestionRunPhaseExecutionResumo,
    IngestionRunResumo,
    IngestionWorkItemList,
    ListaExecucoesSincronizacao,
    ListaFontesResposta,
    ListaHistoricoAlteracoes,
    ListaIngestionRunMembers,
    ListaIngestionRunPhaseExecutions,
    ListaIngestionRuns,
    ListaQuarantineItems,
    QuarantineItemResposta,
    QuarentenaResumoResposta,
    ReplayQuarantineRequisicao,
    ReplayResposta,
    RespostaAgendamentoEmLote,
    RespostaAgendamentoSincronizacao,
    RespostaCancelamentoSincronizacao,
    SolicitacaoCancelamentoSincronizacao,
    TarefaAgendadaResumo,
)
from app.schemas.comum import Paginacao
from app.services.ingestion.audit import build_dataset_discovery_audit
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias
from app.services.ingestion.events import list_operational_events
from app.services.ingestion.lifecycle import (
    build_artifact_snapshot_response,
    build_delivery_snapshot_summary,
    build_member_snapshot_summary,
)
from app.services.ingestion.operational import (
    build_liveness_snapshot,
    get_latest_phase_execution,
    latest_cancellation_request_for_execucao,
    latest_cancellation_request_for_run,
    list_phase_executions,
)
from app.services.ingestion.recovery import (
    NoRecoverySourceError,
    assess_ingestion_run_recovery,
    assess_ingestion_run_recovery_eligibility,
)
from app.services.ingestion.replay import replay_ingestion_run as replay_ingestion_run_service
from app.services.ingestion.replay import replay_quarantine
from app.services.ingestion.scheduling import (
    criar_execucao_sincronizacao_agendada,
    marcar_agendamento_com_falha,
    novo_task_id,
)
from app.services.ingestion.source_registry import listar_datasets, listar_fontes, obter_fonte
from app.services.ingestion.staging import (
    create_cancellation_request,
    formatar_tamanho,
    mark_cancellation_request_completed,
    mark_cancellation_request_propagated,
    update_run_state,
)
from app.worker.celery_app import celery_app
from app.worker.tasks import (
    ingerir_sincronizacao_task,
    pre_processar_sincronizacao_task,
    sincronizar_cadastro_companhias_task,
    sincronizar_cgvn_task,
    sincronizar_dfp_task,
    sincronizar_fca_task,
    sincronizar_fre_task,
    sincronizar_ipe_task,
    sincronizar_itr_task,
    sincronizar_vlmo_task,
)

router = APIRouter(prefix="/ingestion")


def _format_sse(*, event_id: str, event_type: str, payload: dict[str, Any]) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"


@router.get(
    "/events/stream",
    summary="Stream SSE de eventos operacionais de ingestao",
    description=(
        "Stream autenticado de invalidacoes compactas do ledger operacional. Cada evento usa `id`, `event` e "
        "`data` JSON; detalhes continuam nos recursos REST. Aceita `Last-Event-ID`, `cursor` ou "
        "`since_revision` para retomada. `scope=fonte:ano` restringe um escopo real de ingestao."
    ),
    responses={401: {"description": "Token bearer ausente ou invalido."}, 403: {"description": "Permissao administrativa requerida."}},
)
async def stream_eventos_ingestao(
    _: Annotated[None, Depends(exigir_admin_api)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    cursor: str | None = None,
    since_revision: str | None = None,
    scope: str | None = None,
) -> StreamingResponse:
    if sum(value is not None for value in (last_event_id, cursor, since_revision)) > 1:
        raise HTTPException(status_code=422, detail="Informe apenas um cursor de retomada.")
    after_revision = cursor or since_revision or last_event_id
    settings = get_settings()

    async def event_generator() -> Any:
        nonlocal after_revision
        seconds_since_heartbeat = 0.0
        while True:
            db = SessionLocal()
            pool_exhausted = False
            try:
                events = list_operational_events(db, after_revision=after_revision, scope=scope)
            except SQLAlchemyTimeoutError:
                pool_exhausted = True
                now = datetime.now(UTC)
                revision = f"heartbeat:{int(now.timestamp() * 1_000_000)}"
                yield _format_sse(
                    event_id=revision,
                    event_type="heartbeat",
                    payload={
                        "event_id": revision,
                        "revision": revision,
                        "occurred_at": now.isoformat(),
                        "entity_type": "operations",
                        "entity_id": None,
                        "reason_code": "DATABASE_POOL_EXHAUSTED",
                        "data": {"retry_after_seconds": settings.ingestion_events_stream_poll_seconds},
                    },
                )
                seconds_since_heartbeat = 0.0
            except ValueError as exc:
                yield _format_sse(
                    event_id=after_revision or "invalid-cursor",
                    event_type="ingestion.operations.updated",
                    payload={"event_id": after_revision or "invalid-cursor", "revision": after_revision or "0", "occurred_at": datetime.now(UTC).isoformat(), "entity_type": "operations", "entity_id": None, "reason_code": str(exc), "data": {}},
                )
                return
            finally:
                db.close()
            if pool_exhausted:
                await asyncio.sleep(settings.ingestion_events_stream_poll_seconds)
                continue
            if events:
                for event in events:
                    after_revision = event["revision"]
                    event_type = str(event.pop("event_type"))
                    yield _format_sse(event_id=str(event["event_id"]), event_type=event_type, payload=event)
                seconds_since_heartbeat = 0.0
            else:
                seconds_since_heartbeat += settings.ingestion_events_stream_poll_seconds
                if seconds_since_heartbeat >= settings.ingestion_events_stream_heartbeat_seconds:
                    now = datetime.now(UTC)
                    revision = f"heartbeat:{int(now.timestamp() * 1_000_000)}"
                    yield _format_sse(event_id=revision, event_type="heartbeat", payload={"event_id": revision, "revision": revision, "occurred_at": now.isoformat(), "entity_type": "operations", "entity_id": None, "reason_code": "HEARTBEAT", "data": {}})
                    seconds_since_heartbeat = 0.0
            await asyncio.sleep(settings.ingestion_events_stream_poll_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _reconcile_summary_from_run(run: IngestionRun) -> dict[str, Any] | None:
    quality_summary = run.quality_summary or {}
    rows_reconciled_deleted = quality_summary.get("reconciled_deleted")
    if rows_reconciled_deleted in (None, 0):
        return None
    return {
        "rows_reconciled_deleted": rows_reconciled_deleted,
        "scope": "member_replace",
        "target_tables": quality_summary.get("reconcile_target_tables", []),
    }


def _lifecycle_decision_from_run(run: IngestionRun) -> dict[str, Any]:
    quality_summary = run.quality_summary or {}
    remote_probe = run.remote_probe or {}
    return {
        "remote_probe": remote_probe.get("decision"),
        "artifact_sha": remote_probe.get("sha_confirmation_result"),
        "members_skipped_by_sha": quality_summary.get("members_skipped", 0),
        "members_processed": quality_summary.get("members_processados"),
        "members_reused_from_previous": quality_summary.get("members_reused_from_previous", 0),
        "members_reused_from_failed_parent": quality_summary.get("members_reused_from_failed_parent", 0),
    }


def _state_from_run(*, run: IngestionRun, liveness: dict[str, Any] | None) -> str:
    if run.status == "cancelada":
        return "cancelled"
    if run.status == "falha":
        return "failed"
    if run.status == "agendada":
        return "queued"
    if run.status == "aguardando_ingestao":
        return "waiting"
    if run.status == "em_execucao":
        if liveness and liveness.get("is_stale"):
            return "stale"
        return "running"
    if run.status in {"skipped", "sem_alteracao"}:
        return "skipped"
    return "succeeded"


def _state_from_execucao(*, execucao: ExecucaoSincronizacao, liveness: dict[str, Any] | None) -> str:
    if execucao.status == "cancelada":
        return "cancelled"
    if execucao.status == "falha":
        return "failed"
    if execucao.status == "agendada":
        return "queued"
    if execucao.status == "aguardando_ingestao":
        return "waiting"
    if execucao.status == "em_execucao":
        if liveness and liveness.get("is_stale"):
            return "stale"
        return "running"
    if execucao.status in {"skipped", "sem_alteracao"}:
        return "skipped"
    return "succeeded"


def _build_blocking_from_state(*, state: str, status: str) -> dict[str, Any]:
    if state == "queued":
        return {"reason_code": "queued", "detail": "Execucao ainda nao iniciou processamento."}
    if status == "aguardando_ingestao":
        return {"reason_code": "awaiting_ingestion", "detail": "Pre-processamento concluido; aguardando etapa explicita de ingestao."}
    if state == "stale":
        return {"reason_code": "stale", "detail": "Heartbeat da fase ativa ficou velho demais para um processamento ainda marcado como em execucao."}
    if status == "cancelada":
        return {"reason_code": "manual_cancel", "detail": "Execucao interrompida por cancelamento administrativo."}
    return {"reason_code": "none", "detail": None}


def _build_progress_for_run(run: IngestionRun) -> dict[str, Any]:
    quality_summary = run.quality_summary or {}
    return {
        "members_total": quality_summary.get("members_total"),
        "members_processed": quality_summary.get("members_processados"),
        "members_reprocessed": quality_summary.get("members_reprocessed"),
        "members_skipped": quality_summary.get("members_skipped"),
        "members_reused_from_previous": quality_summary.get("members_reused_from_previous"),
        "quarantine_total": quality_summary.get("quarantine_total"),
        "row_status_counts": quality_summary.get("row_status_counts"),
        "staged_rows_purged": quality_summary.get("staged_rows_purged"),
        "typed_stage_rows_loaded": quality_summary.get("typed_stage_rows_loaded"),
        "typed_stage_bytes_loaded": quality_summary.get("typed_stage_bytes_loaded"),
        "typed_stage_rows_replaced": quality_summary.get("typed_stage_rows_replaced"),
        "typed_stage_rows_purged": quality_summary.get("typed_stage_rows_purged"),
        "typed_stage_copy_loads": quality_summary.get("typed_stage_copy_loads"),
        "reconciled_deleted": quality_summary.get("reconciled_deleted"),
    }


def _build_progress_for_execucao(execucao: ExecucaoSincronizacao) -> dict[str, Any]:
    return {
        "total_linhas_lidas": execucao.total_linhas_lidas,
        "total_inseridos": execucao.total_inseridos,
        "total_atualizados": execucao.total_atualizados,
        "total_inalterados": execucao.total_inalterados,
        "total_rejeitados": execucao.total_rejeitados,
    }


def _serialize_cancellation(request: Any) -> dict[str, Any]:
    if request is None:
        return {
            "status": "none",
            "requested_by": None,
            "reason": None,
            "terminate_immediately": None,
            "requested_at": None,
            "propagated_at": None,
            "completed_at": None,
            "affected_task_ids": None,
        }
    return {
        "status": request.status,
        "requested_by": request.requested_by,
        "reason": request.reason,
        "terminate_immediately": request.terminate_immediately,
        "requested_at": request.created_at,
        "propagated_at": request.propagated_at,
        "completed_at": request.completed_at,
        "affected_task_ids": request.affected_task_ids,
    }


def _cleanup_transient_state_for_run(db: DbSession, *, run: IngestionRun) -> dict[str, Any]:
    execucao_ids: list[UUID] = []
    if run.execucao_sincronizacao_id is not None:
        execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)
        if execucao is not None:
            execucao_ids.append(execucao.id)
            if execucao.parent_execucao_id is None:
                execucao_ids.extend(
                    db.scalars(
                        select(ExecucaoSincronizacao.id).where(
                            ExecucaoSincronizacao.parent_execucao_id == execucao.id
                        )
                    ).all()
                )

    run_ids = [run.id]
    if execucao_ids:
        run_ids.extend(
            db.scalars(select(IngestionRun.id).where(IngestionRun.execucao_sincronizacao_id.in_(execucao_ids))).all()
        )
    run_ids = list(dict.fromkeys(run_ids))

    member_ids = db.scalars(
        select(IngestionFileMember.id)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .where(IngestionFile.ingestion_run_id.in_(run_ids))
    ).all()
    row_ids = db.scalars(select(IngestionRow.id).where(IngestionRow.ingestion_run_id.in_(run_ids))).all()

    deleted_quarantine = 0
    deleted_events = 0
    deleted_rows = 0
    deleted_stage = 0
    if row_ids:
        deleted_quarantine_result = db.execute(delete(QuarantineItem).where(QuarantineItem.ingestion_row_id.in_(row_ids)))
        deleted_events_result = db.execute(delete(IngestionRowEvent).where(IngestionRowEvent.ingestion_row_id.in_(row_ids)))
        deleted_rows_result = db.execute(delete(IngestionRow).where(IngestionRow.id.in_(row_ids)))
        deleted_quarantine = int(getattr(deleted_quarantine_result, "rowcount", 0) or 0)
        deleted_events = int(getattr(deleted_events_result, "rowcount", 0) or 0)
        deleted_rows = int(getattr(deleted_rows_result, "rowcount", 0) or 0)
    if member_ids:
        deleted_stage_result = db.execute(
            delete(IngestionFinanceiroStageRow).where(
                IngestionFinanceiroStageRow.ingestion_file_member_id.in_(member_ids)
            )
        )
        deleted_stage = int(getattr(deleted_stage_result, "rowcount", 0) or 0)

    now = datetime.now(UTC)
    closed_phases = 0
    phases = db.scalars(
        select(IngestionPhaseExecution).where(
            IngestionPhaseExecution.ingestion_run_id.in_(run_ids),
            IngestionPhaseExecution.finished_at.is_(None),
        )
    ).all()
    for phase in phases:
        phase.status = "cancelled"
        phase.cancelled_at = phase.cancelled_at or now
        phase.cancel_reason = phase.cancel_reason or "Limpeza administrativa de estado transitorio."
        phase.finished_at = now
        closed_phases += 1

    closed_executions = 0
    if execucao_ids:
        execucoes = db.scalars(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id.in_(execucao_ids))).all()
        for execucao in execucoes:
            if execucao.status not in _STATUS_FINAL_EXECUCAO:
                execucao.status = "cancelada"
                execucao.finalizada_em = now
                execucao.mensagem_erro = "Estado transitorio limpo administrativamente."
                closed_executions += 1

    for run_item in db.scalars(select(IngestionRun).where(IngestionRun.id.in_(run_ids))).all():
        if run_item.status not in _STATUS_FINAL_EXECUCAO:
            update_run_state(
                run_item,
                status="cancelada",
                phase="complete",
                message="Estado transitorio limpo administrativamente.",
                finished_at=now,
            )

    db.commit()
    return {
        "run_ids": [str(item) for item in run_ids],
        "execucao_ids": [str(item) for item in execucao_ids],
        "member_ids": [str(item) for item in member_ids],
        "deleted_quarantine_items": deleted_quarantine,
        "deleted_row_events": deleted_events,
        "deleted_ingestion_rows": deleted_rows,
        "deleted_typed_stage_rows": deleted_stage,
        "closed_phase_executions": closed_phases,
        "closed_executions": closed_executions,
    }


def _serialize_last_error(*, message: str | None, phase_execution: Any, status: str) -> dict[str, Any] | None:
    if status == "falha" and message and message.startswith(_RECOVERY_DISPATCH_FAILURE_PREFIX):
        return {
            "error_type": "recovery_dispatch_failed",
            "error_message": message,
            "retryable": False,
            "phase": "complete",
        }
    if phase_execution is not None and (
        phase_execution.error_message is not None or phase_execution.error_type is not None
    ):
        return {
            "error_type": phase_execution.error_type,
            "error_message": phase_execution.error_message,
            "retryable": phase_execution.error_retryable,
            "phase": phase_execution.phase,
        }
    if status == "falha" and message:
        return {"error_type": "run_failed", "error_message": message, "retryable": False, "phase": None}
    return None


def _next_action(
    *,
    state: str,
    last_error: dict[str, Any] | None,
    recovery: dict[str, Any] | None = None,
    failure_acknowledged: bool = False,
    rejected_total: int | None = None,
) -> str:
    if state in {"queued", "running"}:
        return "wait"
    if state == "waiting":
        if recovery is not None and recovery.get("strategy") == "rerun_member_execution":
            return "recover"
        return "start_ingestion"
    if state == "stale":
        return "recover" if recovery is not None and recovery["eligible"] else "inspect_error"
    if state == "failed":
        if failure_acknowledged:
            return "none"
        if last_error is not None and last_error.get("retryable") is True:
            return "recover" if recovery is not None and recovery["eligible"] else "inspect_error"
        return "inspect_error"
    if rejected_total and rejected_total > 0:
        return "inspect_quarantine"
    return "none"


def _failure_key(run: IngestionRun, latest_phase: IngestionPhaseExecution | None) -> str:
    if latest_phase is not None and latest_phase.status == "failed_final":
        return f"phase:{latest_phase.id}"
    return f"run:{run.status}:{run.updated_at.isoformat()}:{run.message or ''}"


def _failure_acknowledgement(
    db: DbSession,
    *,
    run: IngestionRun,
    latest_phase: IngestionPhaseExecution | None,
) -> dict[str, Any] | None:
    if run.status != "falha":
        return None
    failure_key = _failure_key(run, latest_phase)
    audit = db.scalar(
        select(IngestionOperationAudit)
        .where(
            IngestionOperationAudit.scope_type == "run",
            IngestionOperationAudit.scope_id == str(run.id),
            IngestionOperationAudit.operation == "acknowledge_failure",
        )
        .order_by(IngestionOperationAudit.created_at.desc())
        .limit(1)
    )
    if audit is None or (audit.consequence or {}).get("failure_key") != failure_key:
        return None
    return {
        "acknowledged_at": audit.created_at,
        "acknowledged_by": audit.requested_by,
        "reason": audit.reason or "",
        "failure_key": failure_key,
    }


def _build_run_operational_fields(db: DbSession, run: IngestionRun) -> dict[str, Any]:
    latest_phase = get_latest_phase_execution(db, run_id=run.id)
    liveness = build_liveness_snapshot(latest_phase)
    state = _state_from_run(run=run, liveness=liveness)
    cancellation = _serialize_cancellation(latest_cancellation_request_for_run(db, run_id=run.id))
    last_error = _serialize_last_error(message=run.message, phase_execution=latest_phase, status=run.status)
    quality_summary = run.quality_summary or {}
    recovery = assess_ingestion_run_recovery_eligibility(
        db,
        run=run,
        state=state,
        error_retryable=bool(last_error and last_error.get("retryable")),
    ).as_dict()
    failure_acknowledgement = _failure_acknowledgement(db, run=run, latest_phase=latest_phase)
    return {
        "state": state,
        "progress": _build_progress_for_run(run),
        "liveness": liveness,
        "blocking": _build_blocking_from_state(state=state, status=run.status),
        "cancellation": cancellation,
        "last_error": last_error,
        "recovery": recovery,
        "failure_acknowledgement": failure_acknowledgement,
        "next_action": _next_action(
            state=state,
            last_error=last_error,
            recovery=recovery,
            failure_acknowledged=failure_acknowledgement is not None,
            rejected_total=quality_summary.get("quarantine_total"),
        ),
        "links": {
            "run_detail": f"/ingestion/runs/{run.id}",
            "run_phases": f"/ingestion/runs/{run.id}/phases",
            "run_replay": f"/ingestion/runs/{run.id}/replay",
            "quarantine": f"/ingestion/quarentena?ingestion_run_id={run.id}",
        },
    }


def _build_execucao_operational_fields(
    db: DbSession,
    *,
    execucao: ExecucaoSincronizacao,
    run: IngestionRun | None,
) -> dict[str, Any]:
    latest_phase = get_latest_phase_execution(db, run_id=run.id) if run is not None else None
    liveness = build_liveness_snapshot(latest_phase)
    state = _state_from_execucao(execucao=execucao, liveness=liveness)
    cancellation = _serialize_cancellation(latest_cancellation_request_for_execucao(db, execucao_id=execucao.id))
    last_error = _serialize_last_error(message=execucao.mensagem_erro, phase_execution=latest_phase, status=execucao.status)
    run_detail = f"/ingestion/runs/{run.id}" if run is not None else None
    links = {
        "execucao_detail": f"/ingestion/sincronizacoes/{execucao.id}",
        "quarantine": f"/ingestion/quarentena?execucao_sincronizacao_id={execucao.id}",
    }
    if run_detail is not None:
        links["run_detail"] = run_detail
    return {
        "state": state,
        "liveness": liveness,
        "blocking": _build_blocking_from_state(state=state, status=execucao.status),
        "cancellation": cancellation,
        "last_error": last_error,
        "next_action": _next_action(
            state=state,
            last_error=last_error,
            recovery={"eligible": True},
            rejected_total=execucao.total_rejeitados,
        ),
        "links": links,
    }


def _serialize_run_resumo(db: DbSession, run: IngestionRun) -> IngestionRunResumo:
    return IngestionRunResumo(
        **{
            "id": str(run.id),
            "execucao_sincronizacao_id": None if run.execucao_sincronizacao_id is None else str(run.execucao_sincronizacao_id),
            "tipo_fonte": run.tipo_fonte,
            "ano": run.ano,
            "status": run.status,
            "phase": run.phase,
            "remote_probe": run.remote_probe,
            "change_summary": run.change_summary,
            "quality_summary": run.quality_summary,
            "artifact_snapshot": build_artifact_snapshot_response(db, run_id=run.id),
            "member_snapshot_summary": build_member_snapshot_summary(db, run_id=run.id),
            "delivery_snapshot_summary": build_delivery_snapshot_summary(db, run_id=run.id),
            "reconcile_summary": _reconcile_summary_from_run(run),
            "rows_reconciled_deleted": (run.quality_summary or {}).get("reconciled_deleted"),
            "lifecycle_decision": _lifecycle_decision_from_run(run),
            **_build_run_operational_fields(db, run),
        }
    )


def _serialize_run_preview(db: DbSession, run: IngestionRun) -> IngestionOperationRunPreview:
    operational = _build_run_operational_fields(db, run)
    return IngestionOperationRunPreview(
        id=str(run.id),
        execucao_sincronizacao_id=None if run.execucao_sincronizacao_id is None else str(run.execucao_sincronizacao_id),
        tipo_fonte=run.tipo_fonte,
        ano=run.ano,
        status=run.status,
        phase=run.phase,
        state=operational["state"],
        next_action=operational["next_action"],
        recovery=IngestionRecovery(**operational["recovery"]),
        failure_acknowledgement=operational["failure_acknowledgement"],
        liveness=operational["liveness"],
        blocking=operational["blocking"],
    )


def _count_ingestion_tasks(tasks_by_worker: dict[str, Any] | None) -> int:
    if not tasks_by_worker:
        return 0
    task_names = {
        "app.worker.tasks.sincronizar_cadastro_companhias_task",
        "app.worker.tasks.sincronizar_member_task",
        "app.worker.tasks.disparar_dependentes_task",
        "app.worker.tasks.finalizar_sincronizacao_zip_task",
        "app.worker.tasks.sincronizar_dfp_task",
        "app.worker.tasks.sincronizar_itr_task",
        "app.worker.tasks.sincronizar_fre_task",
        "app.worker.tasks.sincronizar_fca_task",
        "app.worker.tasks.sincronizar_ipe_task",
        "app.worker.tasks.sincronizar_vlmo_task",
        "app.worker.tasks.sincronizar_cgvn_task",
        "app.worker.tasks.pre_processar_sincronizacao_task",
        "app.worker.tasks.ingerir_sincronizacao_task",
    }
    total = 0
    for worker_tasks in tasks_by_worker.values():
        if not isinstance(worker_tasks, list):
            continue
        for task in worker_tasks:
            if isinstance(task, dict) and task.get("name") in task_names:
                total += 1
    return total


def _cancelar_sincronizacao_por_seletor(
    *,
    db: DbSession,
    id_execucao: UUID | None,
    id_tarefa: str | None,
    terminar_imediatamente: bool,
    motivo: str | None,
) -> RespostaCancelamentoSincronizacao:
    if bool(id_execucao) == bool(id_tarefa):
        raise HTTPException(status_code=422, detail="Informe exatamente um seletor: id_execucao ou id_tarefa.")

    execucao: ExecucaoSincronizacao | None
    if id_execucao is not None:
        execucao = db.get(ExecucaoSincronizacao, id_execucao)
        if execucao is None:
            raise HTTPException(status_code=404, detail="Execucao ou task nao encontrada.")
        id_tarefa_efetivo = execucao.id_tarefa
    else:
        id_tarefa_efetivo = id_tarefa
        execucao = db.scalar(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id_tarefa == id_tarefa_efetivo))

    if execucao is not None and execucao.status in _STATUS_FINAL_EXECUCAO:
        raise HTTPException(status_code=409, detail="Execucao nao esta em andamento e nao pode ser cancelada.")

    execucoes_relacionadas = (
        _execucoes_relacionadas_cancelamento(db, execucao=execucao) if execucao is not None else []
    )
    run_map = {
        run.execucao_sincronizacao_id: run
        for run in db.scalars(
            select(IngestionRun).where(
                IngestionRun.execucao_sincronizacao_id.in_([item.id for item in execucoes_relacionadas])
            )
        ).all()
    }
    cancellation_requests = []
    for item in execucoes_relacionadas:
        related_run = run_map.get(item.id)
        cancellation_requests.append(
            create_cancellation_request(
                db,
                scope_type="execucao_sincronizacao",
                scope_id=str(item.id),
                execucao_sincronizacao_id=item.id,
                ingestion_run_id=related_run.id if related_run is not None else None,
                requested_by="api_admin",
                reason=motivo,
                terminate_immediately=terminar_imediatamente,
                affected_execution_ids=[str(rel.id) for rel in execucoes_relacionadas],
            )
        )
    task_ids_para_revogar = _cancelar_execucoes_relacionadas(
        db,
        execucoes=execucoes_relacionadas,
        motivo=motivo,
    )
    if id_tarefa_efetivo is not None:
        task_ids_para_revogar = list(dict.fromkeys([*task_ids_para_revogar, id_tarefa_efetivo]))

    revogacao_solicitada = False
    for task_id in task_ids_para_revogar:
        celery_app.control.revoke(task_id, terminate=terminar_imediatamente, signal="SIGTERM")
        revogacao_solicitada = True
    for request in cancellation_requests:
        if revogacao_solicitada:
            mark_cancellation_request_propagated(
                request,
                affected_task_ids=task_ids_para_revogar,
                affected_execution_ids=[str(rel.id) for rel in execucoes_relacionadas],
            )
        else:
            mark_cancellation_request_completed(
                request,
                affected_task_ids=task_ids_para_revogar,
                affected_execution_ids=[str(rel.id) for rel in execucoes_relacionadas],
            )

    if execucao is not None:
        if revogacao_solicitada:
            for request in cancellation_requests:
                mark_cancellation_request_completed(
                    request,
                    affected_task_ids=task_ids_para_revogar,
                    affected_execution_ids=[str(rel.id) for rel in execucoes_relacionadas],
                )
        db.commit()
        return RespostaCancelamentoSincronizacao(
            id_execucao=str(execucao.id),
            id_tarefa=id_tarefa_efetivo,
            execucao_encontrada=True,
            status_execucao=execucao.status,
            revogacao_solicitada=revogacao_solicitada,
            terminar_imediatamente=terminar_imediatamente,
            mensagem=(
                "Sincronizacao cancelada com sucesso."
                if revogacao_solicitada
                else "Execucao marcada como cancelada no banco sem revogacao remota."
            ),
        )

    if cancellation_requests:
        for request in cancellation_requests:
            mark_cancellation_request_completed(
                request,
                affected_task_ids=task_ids_para_revogar,
                affected_execution_ids=[str(rel.id) for rel in execucoes_relacionadas],
            )
        db.commit()

    return RespostaCancelamentoSincronizacao(
        id_execucao=None,
        id_tarefa=id_tarefa_efetivo,
        execucao_encontrada=False,
        status_execucao=None,
        revogacao_solicitada=revogacao_solicitada,
        terminar_imediatamente=terminar_imediatamente,
        mensagem="Revogacao enviada para task sem execucao materializada no banco.",
    )

_DESC_SYNC_ANUAL = (
    "Agenda uma sincronizacao administrativa de uma fonte anual CVM. "
    "Antes de publicar a task Celery, o backend persiste uma `ExecucaoSincronizacao` com `status=agendada` e `id_tarefa` igual ao ID que sera usado pelo Celery. "
    "Esse estado ja fecha o gate de materializacao, entao novas campanhas/chunks de analise deixam de iniciar enquanto a ingestao estiver em `agendada`, `em_execucao` ou `aguardando_ingestao`. "
    "A task resultante executa um ciclo em quatro momentos operacionais: "
    "`acquire` com preflight remoto (`CKAN`/`HEAD`) para decidir se o recurso parece alterado; "
    "`stage` com extracao de members, headers, contagem de linhas e hashes; "
    "`promote` com normalizacao, resolucao de companhia, deduplicacao e escrita nas tabelas de dominio; "
    "e `reconcile`, quando necessario, para remover linhas promovidas antigas do mesmo `arquivo_origem`/`ano_origem` que nao existem mais no member atual. "
    "A CVM republica pacotes anuais por substituicao completa, nao por append. "
    "Por isso, uma sincronizacao bem-sucedida pode terminar sem download (`sem_alteracao`), "
    "com download mas reaproveitamento por SHA (`skipped`), "
    "ou com processamento parcial de members alterados enquanto members identicos sao reaproveitados por `member_sha256`. "
    "Em reruns de recuperacao, um member bem-sucedido continua elegivel para reaproveitamento mesmo se a execucao anual anterior tiver terminado em `falha`, desde que o SHA do member seja igual e `force_reimport` nao esteja ativo."
)

_RESPOSTA_TOKEN_INVALIDO: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Token de acesso ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    },
    503: {
        "description": "Pool PostgreSQL temporariamente saturado; a requisicao pode ser repetida.",
        "headers": {"Retry-After": {"schema": {"type": "integer"}}},
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "reason_code": "DATABASE_POOL_EXHAUSTED",
                        "retryable": True,
                    }
                }
            }
        },
    },
}

_STATUS_FINAL_EXECUCAO = {"sucesso", "sem_alteracao", "skipped", "falha", "cancelada"}
_RECOVERY_DISPATCH_FAILURE_PREFIX = "Falha ao agendar recovery de member:"


def _agora() -> datetime:
    return datetime.now(UTC)


_DISPATCHABLE_SOURCES = {"cadastro", "dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"}
_ANNUAL_DISPATCH_SOURCES = _DISPATCHABLE_SOURCES - {"cadastro"}
_WORK_ITEM_PREVIEW_LIMIT = 50


def _actor(auth: AutenticacaoApi) -> str:
    return auth.usuario.username if auth.usuario is not None else "system"


def _scope_key(fonte: str, ano: int | None) -> str:
    return f"{fonte.lower().strip()}:{'' if ano is None else ano}"


def _parse_work_item_id(work_item_id: str) -> tuple[str, int | None]:
    fonte, separator, ano_text = work_item_id.partition(":")
    if not separator or fonte not in _DISPATCHABLE_SOURCES:
        raise HTTPException(status_code=404, detail="Work item nao encontrado.")
    if fonte in _ANNUAL_DISPATCH_SOURCES and not ano_text.isdigit():
        raise HTTPException(status_code=404, detail="Work item nao encontrado.")
    return fonte, int(ano_text) if ano_text else None


def _allowed_actions_for_run(
    db: DbSession,
    run: IngestionRun | None,
    *,
    has_quarantine: bool = False,
) -> list[dict[str, Any]]:
    if run is None:
        return [{"code": "start_ingestion", "operation": "POST", "resource": "/ingestion/dispatch", "requires_confirmation": True, "reason_code": "NO_ACTIVE_WORK", "constraints": {}}]
    operational = _build_run_operational_fields(db, run)
    recovery = operational["recovery"]
    if run.status == "aguardando_ingestao":
        if recovery["eligible"] and recovery["strategy"] == "rerun_member_execution":
            return [
                {
                    "code": "recover",
                    "operation": "POST",
                    "resource": f"/ingestion/runs/{run.id}/recover",
                    "requires_confirmation": True,
                    "reason_code": recovery["reason_code"],
                    "constraints": {"strategy": recovery["strategy"]},
                }
            ]
        execucao = (
            db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)
            if run.execucao_sincronizacao_id is not None
            else None
        )
        if execucao is not None and execucao.status == "aguardando_ingestao":
            return [
                {
                    "code": "start_ingestion",
                    "operation": "POST",
                    "resource": f"/ingestion/sincronizacoes/{execucao.id}/ingerir",
                    "requires_confirmation": True,
                    "reason_code": "AWAITING_INGESTION",
                    "constraints": {"force_reimport": False},
                }
            ]
        return [
            {
                "code": "inspect_error",
                "operation": "GET",
                "resource": f"/ingestion/runs/{run.id}",
                "requires_confirmation": False,
                "reason_code": "MISSING_AWAITING_EXECUTION",
                "constraints": {},
            }
        ]
    if run.status == "em_execucao":
        return [{"code": "cancel", "operation": "POST", "resource": f"/ingestion/runs/{run.id}/cancel", "requires_confirmation": True, "reason_code": "RUN_ACTIVE", "constraints": {}}]
    if run.status == "falha":
        if operational["next_action"] == "recover":
            return [{"code": "recover", "operation": "POST", "resource": f"/ingestion/runs/{run.id}/recover", "requires_confirmation": True, "reason_code": recovery["reason_code"], "constraints": {"strategy": recovery["strategy"]}}]
        actions = []
        if operational["failure_acknowledgement"] is None:
            actions.extend(
                [
                    {"code": "inspect_error", "operation": "GET", "resource": f"/ingestion/runs/{run.id}", "requires_confirmation": False, "reason_code": recovery["reason_code"], "constraints": {}},
                    {"code": "acknowledge_failure", "operation": "POST", "resource": f"/ingestion/runs/{run.id}/acknowledge-failure", "requires_confirmation": True, "reason_code": "INVESTIGATION_REQUIRED", "constraints": {"reason_required": True}},
                ]
            )
        else:
            actions.append({"code": "inspect", "operation": "GET", "resource": f"/ingestion/runs/{run.id}", "requires_confirmation": False, "reason_code": "FAILURE_ACKNOWLEDGED", "constraints": {}})
        actions.append({"code": "start_ingestion", "operation": "POST", "resource": "/ingestion/dispatch", "requires_confirmation": True, "reason_code": "TERMINAL_RUN_REDISPATCH_ALLOWED", "constraints": {"fonte": run.tipo_fonte, "ano": run.ano}})
        return actions
    if run.status == "cancelada":
        return [
            {"code": "inspect", "operation": "GET", "resource": f"/ingestion/runs/{run.id}", "requires_confirmation": False, "reason_code": "RUN_CANCELLED", "constraints": {}},
            {"code": "start_ingestion", "operation": "POST", "resource": "/ingestion/dispatch", "requires_confirmation": True, "reason_code": "TERMINAL_RUN_REDISPATCH_ALLOWED", "constraints": {"fonte": run.tipo_fonte, "ano": run.ano}},
        ]
    if has_quarantine:
        return [{"code": "open_quarantine", "operation": "GET", "resource": f"/ingestion/quarentena?ingestion_run_id={run.id}", "requires_confirmation": False, "reason_code": "QUARANTINE_PRESENT", "constraints": {}}]
    return [{"code": "inspect", "operation": "GET", "resource": f"/ingestion/runs/{run.id}", "requires_confirmation": False, "reason_code": "COMPLETED", "constraints": {}}]


def _work_item_from_scope(db: DbSession, *, fonte: str, ano: int | None) -> dict[str, Any] | None:
    from app.updates.models import PendingUpdate

    run = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.tipo_fonte == fonte, IngestionRun.ano == ano)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    execution = db.scalar(
        select(ExecucaoSincronizacao)
        .where(ExecucaoSincronizacao.tipo_fonte == fonte, ExecucaoSincronizacao.ano == ano)
        .order_by(ExecucaoSincronizacao.iniciada_em.desc())
        .limit(1)
    )
    update = db.scalar(
        select(PendingUpdate)
        .where(PendingUpdate.fonte == fonte, PendingUpdate.ano == ano)
        .order_by(PendingUpdate.detection_timestamp.desc())
        .limit(1)
    )
    if run is None and execution is None and update is None:
        return None
    run_fields = _build_run_operational_fields(db, run) if run is not None else None
    execution_fields = (
        _build_execucao_operational_fields(db, execucao=execution, run=run) if execution is not None else None
    )
    quarantine_total = 0 if run is None else int(db.scalar(select(func.count(QuarantineItem.id)).where(QuarantineItem.ingestion_run_id == run.id)) or 0)
    state = (run_fields or execution_fields or {}).get("state", "waiting")
    next_action = (run_fields or execution_fields or {}).get("next_action", "none")
    origin = "scanner" if update is not None else "manual"
    requested_at = update.detection_timestamp if update is not None else (execution.iniciada_em if execution is not None else run.started_at if run is not None else None)
    requested_by = update.resolved_by if update is not None else None
    run_payload = None
    if run is not None and run_fields is not None:
        run_payload = {"id": str(run.id), "status": run.status, "state": run_fields["state"], "phase": run.phase, "progress": run_fields["progress"], "liveness": run_fields["liveness"], "started_at": run.started_at, "last_activity_at": run.updated_at}
    return {
        "id": _scope_key(fonte, ano),
        "fonte": fonte,
        "ano": ano,
        "origin": origin,
        "requested_by": requested_by,
        "requested_at": requested_at,
        "state": state,
        "update": None if update is None else {"id": str(update.id), "status": update.status, "next_action": update.recommended_action},
        "execution": None if execution is None else {"id": str(execution.id), "status": execution.status, "started_at": execution.iniciada_em},
        "run": run_payload,
        "result": None if run is None else {"status": run.status, "quarantine_total": quarantine_total, "has_drift": bool((run.change_summary or {}).get("schema_changed"))},
        "next_action": next_action,
        "allowed_actions": _allowed_actions_for_run(db, run, has_quarantine=quarantine_total > 0),
    }


def _validate_scope(scope: dict[str, Any]) -> str | None:
    fonte = str(scope["fonte"]).lower().strip()
    ano = scope.get("ano")
    if fonte not in _DISPATCHABLE_SOURCES:
        return "UNSUPPORTED_SOURCE"
    if fonte in _ANNUAL_DISPATCH_SOURCES and ano is None:
        return "YEAR_REQUIRED"
    if fonte == "cadastro" and ano is not None:
        return "CADASTRO_DOES_NOT_USE_YEAR"
    return None


def _active_scope_conflict(db: DbSession, *, fonte: str, ano: int | None) -> dict[str, str | None] | None:
    run = db.scalar(select(IngestionRun).where(IngestionRun.tipo_fonte == fonte, IngestionRun.ano == ano, IngestionRun.status.in_(("agendada", "aguardando_ingestao", "em_execucao"))).order_by(IngestionRun.started_at.desc()).limit(1))
    execution = db.scalar(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.tipo_fonte == fonte, ExecucaoSincronizacao.ano == ano, ExecucaoSincronizacao.status.in_(("agendada", "aguardando_ingestao", "em_execucao"))).order_by(ExecucaoSincronizacao.iniciada_em.desc()).limit(1))
    if run is None and execution is None:
        return None
    return {"existing_work_item_id": _scope_key(fonte, ano), "existing_run_id": None if run is None else str(run.id), "existing_execution_id": None if execution is None else str(execution.id)}


def _agendar_task_sincronizacao(
    db: DbSession,
    *,
    task: Any,
    tipo_fonte: str,
    ano: int | None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> str:
    task_id = novo_task_id()
    criar_execucao_sincronizacao_agendada(db, tipo_fonte=tipo_fonte, ano=ano, task_id=task_id)
    db.commit()
    try:
        task.apply_async(args=args, kwargs=kwargs or {}, task_id=task_id)
    except Exception as exc:
        marcar_agendamento_com_falha(db, task_ids=[task_id], erro=str(exc))
        db.commit()
        raise
    return task_id


def _mensagem_cancelamento_administrativo(*, motivo: str | None, id_tarefa: str | None) -> str:
    mensagem = "Execucao cancelada via endpoint administrativo."
    if motivo:
        mensagem = f"{mensagem} Motivo: {motivo}"
    if id_tarefa is None:
        mensagem = (
            f"{mensagem} Execucao encerrada apenas no banco, sem revogacao remota, "
            "pois o registro nao possui id_tarefa associado."
        )
    return mensagem


def _execucoes_relacionadas_cancelamento(
    db: DbSession,
    *,
    execucao: ExecucaoSincronizacao,
) -> list[ExecucaoSincronizacao]:
    if execucao.parent_execucao_id is not None:
        return [execucao]
    return list(
        db.scalars(
        select(ExecucaoSincronizacao)
        .where(
            (ExecucaoSincronizacao.id == execucao.id)
            | (ExecucaoSincronizacao.parent_execucao_id == execucao.id)
        )
        .order_by(ExecucaoSincronizacao.iniciada_em.asc())
    ).all()
    )


def _cancelar_execucoes_relacionadas(
    db: DbSession,
    *,
    execucoes: list[ExecucaoSincronizacao],
    motivo: str | None,
) -> list[str]:
    if not execucoes:
        return []

    agora = _agora()
    task_ids: list[str] = []
    mensagens_por_execucao: dict[UUID, str] = {}

    for execucao in execucoes:
        mensagem = _mensagem_cancelamento_administrativo(motivo=motivo, id_tarefa=execucao.id_tarefa)
        mensagens_por_execucao[execucao.id] = mensagem
        if execucao.status not in _STATUS_FINAL_EXECUCAO:
            execucao.status = "cancelada"
            execucao.finalizada_em = agora
            execucao.mensagem_erro = mensagem
        elif execucao.status == "cancelada" and execucao.mensagem_erro is None:
            execucao.mensagem_erro = mensagem
        if execucao.id_tarefa:
            task_ids.append(execucao.id_tarefa)

    run_map = {
        run.execucao_sincronizacao_id: run
        for run in db.scalars(
            select(IngestionRun).where(
                IngestionRun.execucao_sincronizacao_id.in_([execucao.id for execucao in execucoes])
            )
        ).all()
    }
    for execucao in execucoes:
        run = run_map.get(execucao.id)
        if run is None or run.status in _STATUS_FINAL_EXECUCAO:
            continue
        update_run_state(
            run,
            status="cancelada",
            phase="complete",
            message=mensagens_por_execucao[execucao.id],
            finished_at=agora,
        )

    return list(dict.fromkeys(task_ids))


def _extrair_ano_arquivo(arquivo: str) -> int | None:
    numeros = "".join(ch if ch.isdigit() else " " for ch in arquivo).split()
    for bloco in numeros[::-1]:
        if len(bloco) == 4:
            ano = int(bloco)
            if 2003 <= ano <= 2100:
                return ano
    return None


def _resolver_arquivo_suportado_por_fonte(fonte: str, arquivo: str, ano: int | None) -> str | None:
    arquivo_normalizado = arquivo.lower().strip()
    fonte_item = obter_fonte(fonte)
    if fonte_item is None:
        return None
    if fonte == "cadastro":
        for item in listar_datasets("cadastro"):
            member_name = item.render_member_name(ano=0)
            if member_name.lower() == arquivo_normalizado:
                return member_name
        return None
    if ano is None:
        return None
    arquivo_principal = fonte_item.render_arquivo_principal(ano=ano)
    if arquivo_principal.lower() == arquivo_normalizado:
        return arquivo_principal
    for item in listar_datasets(fonte):
        member_name = item.render_member_name(ano=ano)
        if member_name.lower() == arquivo_normalizado:
            return member_name
    return None


def _arquivo_suportado_por_fonte(fonte: str, arquivo: str, ano: int | None) -> bool:
    return _resolver_arquivo_suportado_por_fonte(fonte, arquivo, ano) is not None


def _agendar_por_arquivo(
    db: DbSession, arquivo: str, ano: int | None, force_reimport: bool = False
) -> TarefaAgendadaResumo:
    arquivo_informado = arquivo.strip()
    arquivo_normalizado = arquivo_informado.lower()
    ano_efetivo = ano if ano is not None else _extrair_ano_arquivo(arquivo_normalizado)

    if _arquivo_suportado_por_fonte("cadastro", arquivo_informado, None):
        task_id = _agendar_task_sincronizacao(
            db,
            task=sincronizar_cadastro_companhias_task,
            tipo_fonte="cadastro",
            ano=None,
            kwargs={"force_reimport": force_reimport},
        )
        return TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=task_id)

    tipo_fonte = None
    arquivo_canonico = None
    for src in ("dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"):
        arquivo_resolvido = _resolver_arquivo_suportado_por_fonte(src, arquivo_informado, ano_efetivo)
        if arquivo_resolvido is not None:
            tipo_fonte = src
            arquivo_canonico = arquivo_resolvido
            break

    if tipo_fonte is None or arquivo_canonico is None:
        raise HTTPException(status_code=422, detail="Arquivo nao suportado para reprocessamento seletivo.")

    if ano_efetivo is None:
        raise HTTPException(status_code=422, detail=f"Ano obrigatorio para reprocessar arquivo {tipo_fonte.upper()}.")

    is_zip = arquivo_canonico.endswith(".zip") or arquivo_canonico == f"{tipo_fonte}_cia_aberta_{ano_efetivo}.zip"

    if is_zip:
        task_mapper = {
            "dfp": sincronizar_dfp_task,
            "itr": sincronizar_itr_task,
            "fre": sincronizar_fre_task,
            "fca": sincronizar_fca_task,
            "ipe": sincronizar_ipe_task,
            "vlmo": sincronizar_vlmo_task,
            "cgvn": sincronizar_cgvn_task,
        }
        task_func = task_mapper[tipo_fonte]
        task_id = _agendar_task_sincronizacao(
            db,
            task=task_func,
            tipo_fonte=tipo_fonte,
            ano=ano_efetivo,
            args=(ano_efetivo,),
            kwargs={"force_reimport": force_reimport},
        )
        return TarefaAgendadaResumo(tipo_fonte=tipo_fonte, ano=ano_efetivo, id_tarefa=task_id)
    else:
        from app.models.sincronizacao import ExecucaoSincronizacao
        from app.worker.tasks import sincronizar_member_task

        exec_pai = db.scalar(
            select(ExecucaoSincronizacao)
            .where(
                ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
                ExecucaoSincronizacao.ano == ano_efetivo,
                ExecucaoSincronizacao.tipo_execucao == "arquivo_zip",
            )
            .order_by(ExecucaoSincronizacao.iniciada_em.desc())
            .limit(1)
        )
        if exec_pai is None:
            raise HTTPException(
                status_code=404,
                detail=f"Execucao pai nao encontrada para fonte {tipo_fonte} e ano {ano_efetivo}."
            )

        task_id = novo_task_id()
        child_exec = ExecucaoSincronizacao(
            parent_execucao_id=exec_pai.id,
            tipo_execucao="arquivo_membro",
            tipo_fonte=tipo_fonte,
            ano=ano_efetivo,
            id_tarefa=task_id,
            arquivo=arquivo_canonico,
            url=exec_pai.url,
            status="agendada",
        )
        db.add(child_exec)
        db.commit()
        db.refresh(child_exec)

        try:
            sincronizar_member_task.apply_async(
                kwargs={
                    "tipo_fonte": tipo_fonte,
                    "ano": ano_efetivo,
                    "member_name": arquivo_canonico,
                    "parent_execucao_id": str(exec_pai.id),
                    "child_execucao_id": str(child_exec.id),
                    "force_reimport": force_reimport,
                },
                task_id=task_id,
            )
        except Exception as exc:
            marcar_agendamento_com_falha(db, task_ids=[task_id], erro=str(exc))
            db.commit()
            raise
        return TarefaAgendadaResumo(
            tipo_fonte=f"{tipo_fonte}_membro",
            ano=ano_efetivo,
            id_tarefa=task_id,
        )


def _resumo_fonte(fonte: Any) -> FonteResumoResposta:
    return FonteResumoResposta(
        fonte=fonte.fonte,
        familia=fonte.familia,
        descricao=fonte.descricao,
        tipo_distribuicao=fonte.tipo_distribuicao,
        status_suporte=fonte.status_suporte,
        dependencias=list(fonte.dependencias),
        primeiro_ano=fonte.primeiro_ano,
        ultimo_ano=fonte.ultimo_ano,
        total_datasets=fonte.total_datasets,
        datasets_obrigatorios=fonte.datasets_obrigatorios,
        datasets_opcionais=fonte.datasets_opcionais,
    )


def _resumo_dataset(dataset: Any) -> FonteDatasetResumoResposta:
    return FonteDatasetResumoResposta(
        dataset=dataset.dataset,
        descricao=dataset.descricao,
        member_name_template=dataset.member_name_template,
        row_kind=dataset.row_kind,
        destino_promovido=dataset.destino_promovido,
        obrigatorio=dataset.obrigatorio,
        status_suporte=dataset.status_suporte,
        normalizador=dataset.normalizador,
        chaves_relacao=list(dataset.chaves_relacao),
        observacoes=dataset.observacoes,
    )


@router.post(
    "/sincronizacoes/cadastro",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao de Cadastro",
    description="Agenda tarefa assincrona de sincronizacao do arquivo cadastral de companhias.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoCadastroAdmin",
)
def disparar_sincronizacao_cadastro(
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_cadastro_companhias_task,
        tipo_fonte="cadastro",
        ano=None,
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/dfp/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao DFP",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoDfpAdmin",
)
def disparar_sincronizacao_dfp(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote DFP.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_dfp_task,
        tipo_fonte="dfp",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/itr/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao ITR",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoItrAdmin",
)
def disparar_sincronizacao_itr(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote ITR.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_itr_task,
        tipo_fonte="itr",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/fre/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao FRE",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoFreAdmin",
)
def disparar_sincronizacao_fre(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote FRE.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_fre_task,
        tipo_fonte="fre",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/fca/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao FCA",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoFcaAdmin",
)
def disparar_sincronizacao_fca(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote FCA.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_fca_task,
        tipo_fonte="fca",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/ipe/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao IPE",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoIpeAdmin",
)
def disparar_sincronizacao_ipe(
    ano: Annotated[int, Path(ge=2003, description="Ano do pacote IPE.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_ipe_task,
        tipo_fonte="ipe",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/vlmo/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao VLMO",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoVlmoAdmin",
)
def disparar_sincronizacao_vlmo(
    ano: Annotated[int, Path(ge=2018, description="Ano do pacote VLMO.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_vlmo_task,
        tipo_fonte="vlmo",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/cgvn/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao CGVN",
    description=_DESC_SYNC_ANUAL,
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoCgvnAdmin",
)
def disparar_sincronizacao_cgvn(
    ano: Annotated[int, Path(ge=2018, description="Ano do pacote CGVN.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    task_id = _agendar_task_sincronizacao(
        db,
        task=sincronizar_cgvn_task,
        tipo_fonte="cgvn",
        ano=ano,
        args=(ano,),
        kwargs={"force_reimport": force_reimport},
    )
    return {"id_tarefa": task_id, "status": "agendada"}


@router.post(
    "/sincronizacoes/tudo/{ano}",
    response_model=RespostaAgendamentoEmLote,
    summary="Disparar Sincronizacao Completa por Ano",
    description=(
        "Agenda um lote administrativo para um ano especifico. "
        "O backend registra `cadastro`, `dfp`, `itr`, `fre`, `fca`, `ipe`, `vlmo` e `cgvn` como `agendada` e publica primeiro a task de `cadastro`. "
        "Quando `cadastro` termina com sucesso, skip ou sem alteracao, o worker publica as fontes anuais ja registradas para o mesmo ano. "
        "Este endpoint nao usa `ANOS_INICIAIS_*` do ambiente: o ano processado eh exclusivamente o argumento recebido em `/{ano}`. "
        "Todas as execucoes do lote sao persistidas como `agendada` antes da primeira publicacao Celery, e esses registros ja fecham o gate de materializacao. "
        "Cada fonte anual executa o mesmo mecanismo: preflight remoto em `acquire`, possivel skip sem download quando os metadados remotos permanecem inalterados, "
        "download apenas quando necessario, `stage` orientado a headers/row counts/member hashes, promocao apenas dos members alterados e `reconcile` para exclusao de linhas promovidas obsoletas do mesmo member. "
        "Se uma execucao anual anterior tiver terminado em `falha`, members que ja haviam sido concluidos com sucesso continuam elegiveis para reaproveitamento por `member_sha256` no rerun do mesmo ano, salvo quando `force_reimport=true`. "
        "A resposta lista todas as tasks Celery criadas para acompanhamento posterior por `id_tarefa`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoTudoAdmin",
)
def disparar_sincronizacao_tudo(
    ano: Annotated[int, Path(ge=2003, description="Ano que sera usado em todas as sincronizacoes anuais do lote.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    db: DbSession,
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> RespostaAgendamentoEmLote:
    tarefas: list[TarefaAgendadaResumo] = []

    cadastro_id = novo_task_id()
    criar_execucao_sincronizacao_agendada(db, tipo_fonte="cadastro", ano=None, task_id=cadastro_id)
    tarefas.append(TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=cadastro_id))

    for tipo_fonte in ("dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"):
        tid = novo_task_id()
        criar_execucao_sincronizacao_agendada(db, tipo_fonte=tipo_fonte, ano=ano, task_id=tid)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte=tipo_fonte, ano=ano, id_tarefa=tid))

    task_ids = [tarefa.id_tarefa for tarefa in tarefas]
    db.commit()
    try:
        sincronizar_cadastro_companhias_task.apply_async(
            kwargs={
                "force_reimport": force_reimport,
                "dispatch_year_after_success": ano,
            },
            task_id=cadastro_id,
        )
    except Exception as exc:
        marcar_agendamento_com_falha(db, task_ids=task_ids, erro=str(exc))
        db.commit()
        raise

    return RespostaAgendamentoEmLote(status="agendada", tarefas=tarefas)


@router.post(
    "/sincronizacoes/pre-processar/cadastro",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Pre-processar Cadastro",
    description="Executa apenas a Fase 1 (download, extração e análise de metadados) do arquivo cadastral de companhias.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="preProcessarCadastroAdmin",
)
def pre_processar_cadastro_route(
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = pre_processar_sincronizacao_task.delay(tipo_fonte="cadastro", force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/pre-processar/{tipo_fonte}/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Pre-processar Fonte Anual (Fase 1)",
    description="Executa apenas a Fase 1 (download, extração e análise de metadados) para uma fonte anual específica (ZIP).",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="preProcessarFonteAnualAdmin",
)
def pre_processar_fonte_anual_route(
    tipo_fonte: Annotated[str, Path(description="Tipo de fonte (ex.: dfp, ITR, FCA).")],
    ano: Annotated[int, Path(description="Ano de referência.")],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    fonte_lower = tipo_fonte.lower().strip()
    if fonte_lower not in ("dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"):
        raise HTTPException(status_code=422, detail=f"Fonte '{tipo_fonte}' nao suportada ou nao necessita de ano.")
    
    tarefa = pre_processar_sincronizacao_task.delay(
        tipo_fonte=fonte_lower,
        ano=ano,
        force_reimport=force_reimport,
    )
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/{id_execucao}/ingerir",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Ingerir Fonte Pré-processada (Fase 2)",
    description=(
        "Dispara a Fase 2 (ingestão dos dados de cada arquivo membro para o banco de dados) "
        "para uma execução que está no status 'aguardando_ingestao'."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Execução não encontrada."},
        400: {"description": "Execução não está no status 'aguardando_ingestao'."},
    },
    operation_id="ingerirFontePreProcessadaAdmin",
)
def ingerir_fonte_pre_processada(
    id_execucao: Annotated[UUID, Path(description="ID da execução de sincronização.")],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, força reimportação das tabelas.", examples=[False])
    ] = False,
) -> dict[str, str]:
    execucao = db.get(ExecucaoSincronizacao, id_execucao)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    
    if execucao.status != "aguardando_ingestao":
        raise HTTPException(
            status_code=400,
            detail=f"Execucao {id_execucao} esta com status '{execucao.status}', mas deve estar em 'aguardando_ingestao' para iniciar a ingestao."
        )
    
    tarefa = ingerir_sincronizacao_task.delay(
        execucao_id=str(execucao.id),
        force_reimport=force_reimport,
    )
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/reprocessar-arquivo",
    response_model=RespostaAgendamentoEmLote,
    summary="Reprocessar Arquivo Seletivo",
    description=(
        "Dispara reprocessamento seletivo por nome de arquivo CVM. "
        "Aceita arquivos `cad_cia_aberta.csv`, `dfp_cia_aberta_*`, `itr_cia_aberta_*`, "
        "`fre_cia_aberta_*`, `fca_cia_aberta_*`, `ipe_cia_aberta_*`, `vlmo_cia_aberta_*` e `cgvn_cia_aberta_*`. "
        "O backend persiste a execucao seletiva em `agendada` antes de publicar a task Celery, usando o mesmo `id_tarefa` retornado na resposta. "
        "Para members CSV, a validacao do nome e case-insensitive, mas o nome canonico do arquivo e preservado na execucao e no despacho da task. "
        "Use `force_reimport=true` no payload para ignorar o skip por hash repetido. "
        "Este endpoint permanece util para recuperacao cirurgica por member/arquivo, mas o fluxo normal de rerun anual agora tenta reaproveitar automaticamente members ja bem-sucedidos por `member_sha256`, inclusive quando a execucao anual anterior terminou em `falha`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="reprocessarArquivoAdmin",
)
def reprocessar_arquivo(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    payload: Annotated[
        dict[str, str | int | bool | None],
        Body(
            examples=[
                {"arquivo": "dfp_cia_aberta_2025.zip"},
                {"arquivo": "fre_cia_aberta_2025.csv", "ano": 2025},
                {"arquivo": "fca_cia_aberta_2025.zip"},
                {"arquivo": "ipe_cia_aberta_2025.zip"},
                {"arquivo": "vlmo_cia_aberta_2025.zip"},
                {"arquivo": "dfp_cia_aberta_2025.zip", "force_reimport": True},
            ],
        ),
    ],
) -> RespostaAgendamentoEmLote:
    arquivo = payload.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo.strip():
        raise HTTPException(status_code=422, detail="Campo 'arquivo' obrigatorio.")
    ano = payload.get("ano")
    if ano is not None and not isinstance(ano, int):
        raise HTTPException(status_code=422, detail="Campo 'ano' deve ser inteiro quando informado.")
    force_reimport = payload.get("force_reimport", False)
    if not isinstance(force_reimport, bool):
        raise HTTPException(status_code=422, detail="Campo 'force_reimport' deve ser booleano quando informado.")

    tarefa = _agendar_por_arquivo(db, arquivo, ano, force_reimport)
    return RespostaAgendamentoEmLote(status="agendada", tarefas=[tarefa])


@router.get(
    "/fontes",
    response_model=ListaFontesResposta,
    summary="Listar Fontes Registradas",
    description="Retorna catálogo interno de fontes CVM suportadas e planejadas na aplicação.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarFontesAdmin",
)
def listar_fontes_admin(
    _: Annotated[None, Depends(validar_token_api)],
) -> ListaFontesResposta:
    return ListaFontesResposta(dados=[_resumo_fonte(item) for item in listar_fontes()])


@router.get(
    "/fontes/{fonte}",
    response_model=FonteDetalheResposta,
    summary="Detalhar Fonte Registrada",
    description="Retorna detalhe dos datasets conhecidos para uma fonte do catálogo interno.",
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Fonte nao encontrada."}},
    operation_id="detalharFonteAdmin",
)
def detalhar_fonte_admin(
    fonte: Annotated[str, Path(description="Chave canônica da fonte.", examples=["fre"])],
    _: Annotated[None, Depends(validar_token_api)],
) -> FonteDetalheResposta:
    fonte_item = obter_fonte(fonte)
    if fonte_item is None:
        raise HTTPException(status_code=404, detail="Fonte nao encontrada.")
    resumo = _resumo_fonte(fonte_item)
    return FonteDetalheResposta(
        **resumo.model_dump(),
        obrigatorio=fonte_item.obrigatorio,
        dataset_path_template=fonte_item.dataset_path_template,
        arquivo_principal_template=fonte_item.arquivo_principal_template,
        datasets=[_resumo_dataset(dataset) for dataset in fonte_item.datasets],
    )


@router.post(
    "/fontes/auditar",
    response_model=AuditoriaFontesResposta,
    summary="Auditar Fontes Registradas",
    description=(
        "Executa auditoria on-demand das fontes CVM registradas no registry interno. "
        "Retorna cobertura, datasets encontrados e faltantes, drift estrutural resumido, metadados de lifecycle do registry e um resumo consultivo da pagina oficial `Novidades`, sem persistir resultado. "
        "A auditoria compara a forma remota atual com o `source_registry` interno usando a mesma semantica estrutural do sync normal: "
        "members obrigatorios/opcionais, nomes esperados por ano, aderencia do pacote, inventario remoto observado, artefato esperado (`artifact_type`), estrategia de probe (`remote_probe_strategy`) e politica de reconcile."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="auditarFontesAdmin",
)
def auditar_fontes_admin(
    _: Annotated[None, Depends(validar_token_api)],
    payload: AuditoriaFontesRequisicao | None = None,
) -> AuditoriaFontesResposta:
    fontes = tuple(payload.fontes) if payload and payload.fontes is not None else None
    ano = payload.ano if payload else None
    auditoria = build_dataset_discovery_audit(year=ano, fontes=fontes)
    return AuditoriaFontesResposta(
        ano=auditoria["ano"],
        fontes=[AuditoriaFonteResposta(**item) for item in auditoria["fontes"]],
        total_fontes=auditoria["total_fontes"],
        total_fontes_acessiveis=auditoria["total_fontes_acessiveis"],
        total_datasets_faltantes=auditoria["total_datasets_faltantes"],
        novidades=auditoria.get("novidades"),
    )


@router.post(
    "/sincronizacoes/cancelar",
    response_model=RespostaCancelamentoSincronizacao,
    summary="Cancelar Sincronizacao em Andamento ou na Fila",
    description=(
        "Interrompe uma sincronização administrativa já disparada. "
        "A operação aceita **um e apenas um** seletor: `id_execucao` ou `id_tarefa`.\n\n"
        "**Quando usar `id_execucao`:**\n"
        "- a execução já aparece em `GET /ingestion/sincronizacoes`;\n"
        "- você deseja cancelar uma execução identificada no banco, "
        "preservando contadores já consolidados;\n"
        "- a API atualizará o status da execução para `cancelada`, "
        "preencherá `finalizada_em` e registrará mensagem administrativa;\n"
        "- se essa execução antiga não possuir `id_tarefa`, o cancelamento "
        "ainda assim será aceito como baixa administrativa local.\n\n"
        "**Quando usar `id_tarefa`:**\n"
        "- você acabou de receber `id_tarefa` no disparo e a execução ainda "
        "não foi materializada em banco;\n"
        "- você precisa revogar diretamente a task no Celery;\n"
        "- se a task já tiver criado execução com mesmo `id_tarefa`, a API "
        "também marcará essa execução como `cancelada`.\n\n"
        "**Semântica operacional:**\n"
        "- por padrão, `terminar_imediatamente=true`, o que envia "
        "`revoke(..., terminate=True, signal='SIGTERM')` ao Celery;\n"
        "- este modo é recomendado para sincronizações em andamento, pois "
        "tenta parar o worker imediatamente;\n"
        "- tarefas já finalizadas não podem ser canceladas e retornam `409`;\n"
        "- se o seletor apontar apenas para task em fila, a resposta informará "
        "`execucao_encontrada=false`.\n\n"
        "**Observações importantes:**\n"
        "- a revogação é comando assíncrono ao Celery; portanto, em cenários "
        "distribuídos extremos pode haver pequeno atraso entre solicitação e "
        "parada efetiva;\n"
        "- execuções antigas sem `id_tarefa` não podem ser revogadas "
        "remotamente, mas podem ser encerradas administrativamente com status "
        "`cancelada`;\n"
        "- contadores (`total_linhas_lidas`, `total_inseridos`, etc.) "
        "permanecem com último valor persistido no momento do cancelamento;\n"
        "- use `GET /ingestion/sincronizacoes/{id_execucao}` após cancelamento para auditoria detalhada."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {
            "description": "Execução ou task não localizada.",
            "content": {"application/json": {"example": {"detail": "Execucao ou task nao encontrada."}}},
        },
        409: {
            "description": "Sincronização já finalizada.",
            "content": {
                "application/json": {"example": {"detail": "Execucao nao esta em andamento e nao pode ser cancelada."}}
            },
        },
        422: {
            "description": "Payload inválido, com seletor ausente ou múltiplo.",
            "content": {
                "application/json": {"example": {"detail": "Informe exatamente um seletor: id_execucao ou id_tarefa."}}
            },
        },
    },
    operation_id="cancelarSincronizacaoAdmin",
)
def cancelar_sincronizacao(
    payload: Annotated[
        SolicitacaoCancelamentoSincronizacao,
        Body(
            description=(
                "Payload de cancelamento. "
                "Envie `id_execucao` **ou** `id_tarefa`. "
                "Se ambos forem enviados, a API rejeita a solicitação com `422`."
            )
        ),
    ],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> RespostaCancelamentoSincronizacao:
    return _cancelar_sincronizacao_por_seletor(
        db=db,
        id_execucao=payload.id_execucao,
        id_tarefa=payload.id_tarefa,
        terminar_imediatamente=payload.terminar_imediatamente,
        motivo=payload.motivo,
    )


@router.get(
    "/sincronizacoes",
    response_model=ListaExecucoesSincronizacao,
    summary="Listar Execucoes de Sincronizacao",
    description=(
        "Lista paginada das execucoes registradas no sistema de sincronizacao. "
        "Suporta filtragem por tipo de execucao (arquivo_zip, arquivo_membro, arquivo_simples), "
        "id da execucao pai, somente filhos, ou somente pais. "
        "Para execucoes do tipo arquivo_zip, retorna contadores de progresso dos membros filhos."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarExecucoesSincronizacaoAdmin",
)
def listar_execucoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Numero da pagina.", examples=[1])] = 1,
    tamanho_pagina: Annotated[
        int, Query(ge=1, le=500, description="Quantidade de itens por pagina.", examples=[100])
    ] = 100,
    tipo_execucao: Annotated[str | None, Query(description="Filtrar por tipo de execucao.")] = None,
    id_execucao_pai: Annotated[UUID | None, Query(description="Filtrar pelo ID da execucao pai.")] = None,
    somente_filhos: Annotated[
        bool, Query(description="Se True, retorna apenas execucoes filhas (membros).")
    ] = False,
    somente_pais: Annotated[
        bool, Query(description="Se True, retorna apenas execucoes pais (ZIP ou simples).")
    ] = False,
    fonte: str | None = None,
    ano: int | None = None,
    status: str | None = None,
    periodo_inicio: datetime | None = None,
    periodo_fim: datetime | None = None,
    operador: str | None = None,
    origem: str | None = None,
    correlacao: str | None = None,
    ordenar: str = "iniciada_em:desc",
) -> ListaExecucoesSincronizacao:
    offset = (pagina - 1) * tamanho_pagina
    stmt = select(ExecucaoSincronizacao)
    stmt_count = select(func.count(ExecucaoSincronizacao.id))
    
    if tipo_execucao:
        stmt = stmt.where(ExecucaoSincronizacao.tipo_execucao == tipo_execucao)
        stmt_count = stmt_count.where(ExecucaoSincronizacao.tipo_execucao == tipo_execucao)
    if id_execucao_pai:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id == id_execucao_pai)
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id == id_execucao_pai)
    if somente_filhos:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id.isnot(None))
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id.isnot(None))
    if somente_pais:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id.is_(None))
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id.is_(None))
    for condition in (
        ExecucaoSincronizacao.tipo_fonte == fonte if fonte else None,
        ExecucaoSincronizacao.ano == ano if ano is not None else None,
        ExecucaoSincronizacao.status == status if status else None,
        ExecucaoSincronizacao.iniciada_em >= periodo_inicio if periodo_inicio else None,
        ExecucaoSincronizacao.iniciada_em <= periodo_fim if periodo_fim else None,
        ExecucaoSincronizacao.id_tarefa == correlacao if correlacao else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
            stmt_count = stmt_count.where(condition)
    del operador, origem  # origem/operator are not persisted in legacy executions; retained for forward-compatible clients.
        
    execucoes = (
        db.execute(
            stmt.order_by(ExecucaoSincronizacao.iniciada_em.asc() if ordenar.endswith(":asc") else ExecucaoSincronizacao.iniciada_em.desc())
            .offset(offset)
            .limit(tamanho_pagina)
        )
        .scalars()
        .all()
    )
    total = db.scalar(stmt_count) or 0

    # Bulk-fetch child stats for parent executions to avoid N+1
    parent_ids_in_list = [item.id for item in execucoes if item.tipo_execucao == "arquivo_zip"]
    child_stats = {}
    if parent_ids_in_list:
        stats_rows = db.execute(
            select(
                ExecucaoSincronizacao.parent_execucao_id,
                ExecucaoSincronizacao.status,
                func.count(ExecucaoSincronizacao.id)
            )
            .where(ExecucaoSincronizacao.parent_execucao_id.in_(parent_ids_in_list))
            .group_by(ExecucaoSincronizacao.parent_execucao_id, ExecucaoSincronizacao.status)
        ).all()
        
        for pid, status_val, count_val in stats_rows:
            if pid not in child_stats:
                child_stats[pid] = {"total": 0, "concluidos": 0, "falha": 0, "em_andamento": 0}
            child_stats[pid]["total"] += count_val
            if status_val in ("sucesso", "sem_alteracao", "skipped"):
                child_stats[pid]["concluidos"] += count_val
            elif status_val in ("falha", "cancelada", "quality_fail"):
                child_stats[pid]["falha"] += count_val
            else:
                child_stats[pid]["em_andamento"] += count_val

    # Bulk-fetch parents for child executions to get file name (arquivo_principal)
    parent_ids_to_fetch = {item.parent_execucao_id for item in execucoes if item.parent_execucao_id}
    parents_by_id = {}
    if parent_ids_to_fetch:
        parents = db.scalars(
            select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id.in_(list(parent_ids_to_fetch)))
        ).all()
        parents_by_id = {p.id: p for p in parents}

    # Bulk-fetch members for all execucoes to avoid N+1.
    # Group by parent ID. For parent/simple execution, key is item.id.
    # For child execution, key is item.parent_execucao_id.
    all_parent_ids = {item.parent_execucao_id or item.id for item in execucoes}
    members_by_parent: dict[Any, dict[str, IngestionFileMember]] = {}
    if all_parent_ids:
        rows = db.execute(
            select(IngestionRun.execucao_sincronizacao_id, IngestionFileMember)
            .join(IngestionFile, IngestionFile.ingestion_run_id == IngestionRun.id)
            .join(IngestionFileMember, IngestionFileMember.ingestion_file_id == IngestionFile.id)
            .where(IngestionRun.execucao_sincronizacao_id.in_(list(all_parent_ids)))
        ).all()
        for parent_id, member in rows:
            members_by_parent.setdefault(parent_id, {})[member.member_name] = member

    runs_by_execucao_id = {
        run.execucao_sincronizacao_id: run
        for run in db.scalars(
            select(IngestionRun).where(
                IngestionRun.execucao_sincronizacao_id.in_([item.id for item in execucoes if item.id is not None])
            )
        ).all()
        if run.execucao_sincronizacao_id is not None
    }

    dados = []
    for item in execucoes:
        # Resolve associated members for analysis
        if item.tipo_execucao == "arquivo_membro":
            m = members_by_parent.get(item.parent_execucao_id, {}).get(item.arquivo)
            members_for_item = [m] if m else []
        else:
            members_for_item = list(members_by_parent.get(item.id, {}).values())
        run = runs_by_execucao_id.get(item.id)
        operational = _build_execucao_operational_fields(db, execucao=item, run=run)

        dados.append(
            ExecucaoSincronizacaoResumo(
                id=str(item.id),
                id_tarefa=item.id_tarefa,
                tipo_fonte=item.tipo_fonte,
                arquivo=item.arquivo,
                status=item.status,
                iniciada_em=item.iniciada_em,
                finalizada_em=item.finalizada_em,
                total_linhas_lidas=item.total_linhas_lidas,
                total_inseridos=item.total_inseridos,
                total_atualizados=item.total_atualizados,
                total_inalterados=item.total_inalterados,
                total_rejeitados=item.total_rejeitados,
                id_execucao_pai=str(item.parent_execucao_id) if item.parent_execucao_id else None,
                tipo_execucao=item.tipo_execucao,
                arquivo_principal=(
                    parents_by_id[item.parent_execucao_id].arquivo
                    if (item.parent_execucao_id and item.parent_execucao_id in parents_by_id)
                    else None
                ),
                filhos_total=(
                    child_stats[item.id]["total"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_concluidos=(
                    child_stats[item.id]["concluidos"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_falha=(
                    child_stats[item.id]["falha"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_em_andamento=(
                    child_stats[item.id]["em_andamento"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                analise_arquivos=[
                    AnaliseArquivo(
                        file_name=m.member_name,
                        file_size=formatar_tamanho(m.member_size_bytes),
                        rows_count=m.row_count,
                        columns_count=len(m.header) if m.header else 0,
                        header_columns=m.header or [],
                        encoding=m.encoding,
                        delimiter=m.delimiter,
                    )
                    for m in members_for_item
                ] or None,
                state=operational["state"],
                liveness=operational["liveness"],
                blocking=operational["blocking"],
                cancellation=operational["cancellation"],
                last_error=operational["last_error"],
                next_action=operational["next_action"],
                links=operational["links"],
            )
        )

    return ListaExecucoesSincronizacao(
        dados=dados,
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/sincronizacoes/{id_execucao}",
    response_model=ExecucaoSincronizacaoDetalhe,
    summary="Detalhar Execucao de Sincronizacao",
    description=(
        "Retorna o detalhamento completo de uma execucao pelo identificador. "
        "Se a execucao for um arquivo membro (filho), inclui o nome do arquivo "
        "principal ZIP (arquivo_principal). Se for uma execucao pai (arquivo_zip), "
        "retorna o progresso agregado e a lista detalhada de execucoes filhas "
        "(execucoes_filhas)."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {
            "description": "Execucao nao encontrada.",
            "content": {"application/json": {"example": {"detail": "Execucao nao encontrada."}}},
        },
    },
    operation_id="detalharExecucaoSincronizacaoAdmin",
)
def detalhar_execucao(
    id_execucao: Annotated[UUID, Path(description="ID da execucao de sincronizacao.", examples=["uuid"])],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ExecucaoSincronizacaoDetalhe:
    execucao = db.get(ExecucaoSincronizacao, id_execucao)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")

    # Fetch parent's ZIP file name as arquivo_principal for child executions
    arquivo_principal = None
    if execucao.parent_execucao_id:
        parent = db.get(ExecucaoSincronizacao, execucao.parent_execucao_id)
        if parent:
            arquivo_principal = parent.arquivo

    # List child summaries in execucoes_filhas for parent executions
    execucoes_filhas = None
    filhos_total = None
    filhos_concluidos = None
    filhos_falha = None
    filhos_em_andamento = None

    if execucao.tipo_execucao == "arquivo_zip":
        children = db.scalars(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.parent_execucao_id == execucao.id)
            .order_by(ExecucaoSincronizacao.arquivo.asc())
        ).all()
        child_runs_by_execucao_id = {
            run.execucao_sincronizacao_id: run
            for run in db.scalars(
                select(IngestionRun).where(
                    IngestionRun.execucao_sincronizacao_id.in_([child.id for child in children])
                )
            ).all()
            if run.execucao_sincronizacao_id is not None
        }
        
        filhos_total = len(children)
        filhos_concluidos = 0
        filhos_falha = 0
        filhos_em_andamento = 0
        
        # We need the parent's IngestionFile to associate child files with AnaliseArquivo
        parent_run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        child_members = {}
        if parent_run:
            parent_file = db.scalar(
                select(IngestionFile).where(IngestionFile.ingestion_run_id == parent_run.id)
            )
            if parent_file:
                members_list = db.scalars(
                    select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == parent_file.id)
                ).all()
                child_members = {m.member_name: m for m in members_list}
        
        execucoes_filhas = []
        for c in children:
            if c.status in ("sucesso", "sem_alteracao", "skipped"):
                filhos_concluidos += 1
            elif c.status in ("falha", "cancelada", "quality_fail"):
                filhos_falha += 1
            else:
                filhos_em_andamento += 1
                
            m = child_members.get(c.arquivo)
            analise_c = None
            if m:
                analise_c = [
                    AnaliseArquivo(
                        file_name=m.member_name,
                        file_size=formatar_tamanho(m.member_size_bytes),
                        rows_count=m.row_count,
                        columns_count=len(m.header) if m.header else 0,
                        header_columns=m.header or [],
                        encoding=m.encoding,
                        delimiter=m.delimiter,
                    )
                ]
            operational_child = _build_execucao_operational_fields(
                db,
                execucao=c,
                run=child_runs_by_execucao_id.get(c.id),
            )
                
            execucoes_filhas.append(
                ExecucaoSincronizacaoResumo(
                    id=str(c.id),
                    id_tarefa=c.id_tarefa,
                    tipo_fonte=c.tipo_fonte,
                    arquivo=c.arquivo,
                    status=c.status,
                    iniciada_em=c.iniciada_em,
                    finalizada_em=c.finalizada_em,
                    total_linhas_lidas=c.total_linhas_lidas,
                    total_inseridos=c.total_inseridos,
                    total_atualizados=c.total_atualizados,
                    total_inalterados=c.total_inalterados,
                    total_rejeitados=c.total_rejeitados,
                    id_execucao_pai=str(c.parent_execucao_id) if c.parent_execucao_id else None,
                    tipo_execucao=c.tipo_execucao,
                    arquivo_principal=execucao.arquivo,
                    analise_arquivos=analise_c,
                    state=operational_child["state"],
                    liveness=operational_child["liveness"],
                    blocking=operational_child["blocking"],
                    cancellation=operational_child["cancellation"],
                    last_error=operational_child["last_error"],
                    next_action=operational_child["next_action"],
                    links=operational_child["links"],
                )
            )
            
    # Populate analise_arquivos for the current execution itself
    analise_arquivos = None
    run_for_execucao: IngestionRun | None = None
    if execucao.tipo_execucao == "arquivo_membro":
        if execucao.parent_execucao_id:
            run = db.scalar(
                select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.parent_execucao_id)
            )
            run_for_execucao = db.scalar(
                select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
            ) or run
            if run:
                file = db.scalar(
                    select(IngestionFile).where(IngestionFile.ingestion_run_id == run.id)
                )
                if file:
                    m = db.scalar(
                        select(IngestionFileMember)
                        .where(IngestionFileMember.ingestion_file_id == file.id)
                        .where(IngestionFileMember.member_name == execucao.arquivo)
                    )
                    if m:
                        analise_arquivos = [
                            AnaliseArquivo(
                                file_name=m.member_name,
                                file_size=formatar_tamanho(m.member_size_bytes),
                                rows_count=m.row_count,
                                columns_count=len(m.header) if m.header else 0,
                                header_columns=m.header or [],
                                encoding=m.encoding,
                                delimiter=m.delimiter,
                            )
                        ]
    else:
        # parent or simple execution
        run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        run_for_execucao = run
        if run:
            files = db.scalars(
                select(IngestionFile).where(IngestionFile.ingestion_run_id == run.id)
            ).all()
            if files:
                analise_arquivos = []
                for f in files:
                    members = db.scalars(
                        select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == f.id)
                    ).all()
                    for m in members:
                        analise_arquivos.append(
                            AnaliseArquivo(
                                file_name=m.member_name,
                                file_size=formatar_tamanho(m.member_size_bytes),
                                rows_count=m.row_count,
                                columns_count=len(m.header) if m.header else 0,
                                header_columns=m.header or [],
                                encoding=m.encoding,
                                delimiter=m.delimiter,
                            )
                        )

    operational = _build_execucao_operational_fields(db, execucao=execucao, run=run_for_execucao)

    return ExecucaoSincronizacaoDetalhe(
        id=str(execucao.id),
        id_tarefa=execucao.id_tarefa,
        tipo_fonte=execucao.tipo_fonte,
        ano=execucao.ano,
        arquivo=execucao.arquivo,
        url=execucao.url,
        hash_arquivo=execucao.hash_arquivo,
        status=execucao.status,
        iniciada_em=execucao.iniciada_em,
        finalizada_em=execucao.finalizada_em,
        total_linhas_lidas=execucao.total_linhas_lidas,
        total_inseridos=execucao.total_inseridos,
        total_atualizados=execucao.total_atualizados,
        total_inalterados=execucao.total_inalterados,
        total_rejeitados=execucao.total_rejeitados,
        mensagem_erro=execucao.mensagem_erro,
        analise_arquivos=analise_arquivos,
        id_execucao_pai=str(execucao.parent_execucao_id) if execucao.parent_execucao_id else None,
        tipo_execucao=execucao.tipo_execucao,
        arquivo_principal=arquivo_principal,
        filhos_total=filhos_total,
        filhos_concluidos=filhos_concluidos,
        filhos_falha=filhos_falha,
        filhos_em_andamento=filhos_em_andamento,
        execucoes_filhas=execucoes_filhas,
        state=operational["state"],
        liveness=operational["liveness"],
        blocking=operational["blocking"],
        cancellation=operational["cancellation"],
        last_error=operational["last_error"],
        next_action=operational["next_action"],
        links=operational["links"],
    )



@router.get(
    "/alteracoes",
    response_model=ListaHistoricoAlteracoes,
    summary="Listar Historico de Alteracoes",
    description="Lista paginada de alteracoes campo a campo registradas nas sincronizacoes.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarAlteracoesAdmin",
)
def listar_alteracoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Numero da pagina.", examples=[1])] = 1,
    tamanho_pagina: Annotated[
        int, Query(ge=1, le=500, description="Quantidade de itens por pagina.", examples=[100])
    ] = 100,
    entidade: Annotated[
        str | None,
        Query(description="Filtrar por entidade alterada.", examples=["documentos_financeiros"]),
    ] = None,
) -> ListaHistoricoAlteracoes:
    offset = (pagina - 1) * tamanho_pagina
    query = select(HistoricoAlteracaoCampo)
    query_total = select(func.count()).select_from(HistoricoAlteracaoCampo)
    if entidade:
        query = query.where(HistoricoAlteracaoCampo.entidade == entidade)
        query_total = query_total.where(HistoricoAlteracaoCampo.entidade == entidade)
    itens = (
        db.execute(query.order_by(HistoricoAlteracaoCampo.alterado_em.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.scalar(query_total) or 0
    return ListaHistoricoAlteracoes(
        dados=[
            HistoricoAlteracaoCampoResposta(
                id=str(item.id),
                entidade=item.entidade,
                entidade_id=str(item.entidade_id),
                companhia_id=None if item.companhia_id is None else str(item.companhia_id),
                campo=item.campo,
                valor_anterior=item.valor_anterior,
                valor_novo=item.valor_novo,
                alterado_em=item.alterado_em,
                execucao_sincronizacao_id=str(item.execucao_sincronizacao_id),
                arquivo_origem=item.arquivo_origem,
                ano_origem=item.ano_origem,
            )
            for item in itens
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/dashboard",
    response_model=DashboardExecucoesResposta,
    summary="Dashboard de Execucoes",
    description="Consolidado simples para operacao: status, rejeicoes e ultimas execucoes.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dashboardExecucoesAdmin",
)
def dashboard_execucoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> DashboardExecucoesResposta:
    total_execucoes = db.scalar(select(func.count()).select_from(ExecucaoSincronizacao)) or 0
    total_sucesso = (
        db.scalar(
            select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "sucesso")
        )
        or 0
    )
    total_sem_alteracao = (
        db.scalar(
            select(func.count())
            .select_from(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.status == "sem_alteracao")
        )
        or 0
    )
    total_falha = (
        db.scalar(
            select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "falha")
        )
        or 0
    )
    total_rejeitados = db.scalar(select(func.coalesce(func.sum(ExecucaoSincronizacao.total_rejeitados), 0))) or 0
    ultimas = (
        db.execute(select(ExecucaoSincronizacao).order_by(ExecucaoSincronizacao.iniciada_em.desc()).limit(10))
        .scalars()
        .all()
    )
    return DashboardExecucoesResposta(
        total_execucoes=total_execucoes,
        total_sucesso=total_sucesso,
        total_sem_alteracao=total_sem_alteracao,
        total_falha=total_falha,
        total_rejeitados=total_rejeitados,
        ultimas_execucoes=[
            ExecucaoSincronizacaoResumo(
                id=str(item.id),
                tipo_fonte=item.tipo_fonte,
                arquivo=item.arquivo,
                status=item.status,
                iniciada_em=item.iniciada_em,
                finalizada_em=item.finalizada_em,
                total_linhas_lidas=item.total_linhas_lidas,
                total_inseridos=item.total_inseridos,
                total_atualizados=item.total_atualizados,
                total_inalterados=item.total_inalterados,
                total_rejeitados=item.total_rejeitados,
            )
            for item in ultimas
        ],
    )


@router.get(
    "/runs",
    response_model=ListaIngestionRuns,
    summary="Listar Runs de Ingestion",
    description=(
        "Lista paginada das runs do pipeline de ingestao. "
        "Este e o endpoint principal para monitoramento operacional. "
        "Cada item consolida `status`, `phase`, `state`, `progress`, `liveness`, `blocking`, `cancellation`, `last_error`, "
        "`remote_probe`, `change_summary`, `quality_summary`, `artifact_snapshot`, `member_snapshot_summary`, "
        "`delivery_snapshot_summary`, `reconcile_summary`, `lifecycle_decision` e `links`. "
        "Para progresso e cards, use `progress` e `quality_summary`. "
        "Em DFP/ITR financeiro, linhas validas seguem direct path artifact-backed; progresso deve ser lido por fases, "
        "`quality_summary` e snapshots de artifacts, nao por volume em `ingestion_rows`. "
        "Para explicar members reaproveitados ou reprocessados, use `member_snapshot_summary` e `lifecycle_decision`. "
        "Para diagnostico operacional, use `state`, `liveness`, `blocking`, `cancellation`, `last_error` e `next_action`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarIngestionRunsAdmin",
)
def listar_ingestion_runs(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
    state: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    next_action: str | None = None,
    fonte: str | None = None,
    ano: int | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    has_quarantine: bool | None = None,
    has_error: bool | None = None,
    execucao_sincronizacao_id: UUID | None = None,
    ordenar: str = "started_at:desc",
) -> ListaIngestionRuns:
    offset = (pagina - 1) * tamanho_pagina
    stmt = select(IngestionRun)
    for condition in (
        IngestionRun.status == status if status else None,
        IngestionRun.phase == phase if phase else None,
        IngestionRun.tipo_fonte == fonte if fonte else None,
        IngestionRun.ano == ano if ano is not None else None,
        IngestionRun.started_at >= started_from if started_from else None,
        IngestionRun.started_at <= started_to if started_to else None,
        IngestionRun.execucao_sincronizacao_id == execucao_sincronizacao_id if execucao_sincronizacao_id else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
    candidates = list(db.scalars(stmt).all())
    def include(run: IngestionRun) -> bool:
        fields = _build_run_operational_fields(db, run)
        quarantine = int(db.scalar(select(func.count(QuarantineItem.id)).where(QuarantineItem.ingestion_run_id == run.id)) or 0)
        return ((state is None or fields["state"] == state) and (next_action is None or fields["next_action"] == next_action) and (has_quarantine is None or bool(quarantine) == has_quarantine) and (has_error is None or bool(fields.get("last_error")) == has_error))
    candidates = [run for run in candidates if include(run)]
    candidates.sort(key=lambda run: run.started_at, reverse=not ordenar.endswith(":asc"))
    total = len(candidates)
    runs = candidates[offset : offset + tamanho_pagina]
    return ListaIngestionRuns(
        dados=[_serialize_run_resumo(db, run) for run in runs],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/runs/{run_id}",
    response_model=IngestionRunResumo,
    summary="Detalhar Run de Ingestion",
    description=(
        "Retorna o detalhe completo de uma run do pipeline. "
        "Use este endpoint para drill-down operacional, leitura de snapshots estruturais, progresso, liveness, bloqueios, "
        "cancelamento, erro mais recente, reconcile, inventario de members e decisao de lifecycle. "
        "Para DFP/ITR, fases e counters representam o direct path financeiro: profile, artifact normalizado, staging tipado, "
        "promocao e reconcile. "
        "Para explicar por que uma run anual reaproveitou ou reprocessou members, use `quality_summary`, `member_snapshot_summary` e `lifecycle_decision`."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run nao encontrado."},
    },
    operation_id="detalharIngestionRunAdmin",
)
def detalhar_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> IngestionRunResumo:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    return _serialize_run_resumo(db, run)


@router.get(
    "/runs/{run_id}/phases",
    response_model=ListaIngestionRunPhaseExecutions,
    summary="Listar fases de uma run de ingestion",
    description=(
        "Retorna a timeline persistida de fases da run. "
        "Use este endpoint para drill-down operacional, principalmente quando a UI precisar distinguir "
        "heartbeat stale, tentativas repetidas da mesma fase, cancelamento e falha final sem recorrer a logs de worker. "
        "Em members financeiros DFP/ITR, a timeline pode incluir `profile`, `normalize_artifact`, `load_typed_staging`, "
        "`promote`, `reconcile` e `complete`, com counters em `metrics`."
    ),
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Run nao encontrado."}},
    operation_id="listarIngestionRunPhasesAdmin",
)
def listar_ingestion_run_phases(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ListaIngestionRunPhaseExecutions:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    phase_rows = list_phase_executions(db, run_id=run.id)
    return ListaIngestionRunPhaseExecutions(
        dados=[
            IngestionRunPhaseExecutionResumo(
                id=str(item.id),
                phase=item.phase,
                status=item.status,
                attempt=item.attempt,
                task_id=item.task_id,
                lease_owner=item.lease_owner,
                started_at=item.started_at,
                heartbeat_at=item.heartbeat_at,
                finished_at=item.finished_at,
                cancel_requested_at=item.cancel_requested_at,
                cancelled_at=item.cancelled_at,
                cancel_reason=item.cancel_reason,
                error_type=item.error_type,
                error_message=item.error_message,
                error_retryable=item.error_retryable,
                input_artifact_uri=item.input_artifact_uri,
                output_artifact_uri=item.output_artifact_uri,
                metrics=item.metrics,
            )
            for item in phase_rows
        ]
    )


@router.get(
    "/runs/{run_id}/members",
    response_model=ListaIngestionRunMembers,
    summary="Listar members de uma run de ingestion",
    description=(
        "Retorna o inventario paginado de members associados a uma run. "
        "A resposta combina metadados de `ingestion_file_members`, snapshots de lifecycle do artefato, "
        "contagem de deliveries capturadas e volume de quarentena por member. "
        "Use este endpoint para tabelas operacionais de ZIPs anuais e para drill-down do reprocessamento seletivo por CSV."
    ),
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Run nao encontrado."}},
    operation_id="listarIngestionRunMembersAdmin",
)
def listar_ingestion_run_members(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListaIngestionRunMembers:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")

    offset = (pagina - 1) * tamanho_pagina
    members = list(
        db.scalars(
            select(IngestionFileMember)
            .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
            .where(IngestionFile.ingestion_run_id == run.id)
            .order_by(IngestionFileMember.member_name.asc())
            .offset(offset)
            .limit(tamanho_pagina)
        ).all()
    )
    total = int(
        db.scalar(
            select(func.count(IngestionFileMember.id))
            .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
            .where(IngestionFile.ingestion_run_id == run.id)
        )
        or 0
    )
    if not members:
        return ListaIngestionRunMembers(
            dados=[],
            paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
        )

    member_ids = [member.id for member in members]
    member_names = [member.member_name for member in members]
    snapshots = list(
        db.scalars(
            select(SourceMemberSnapshot)
            .where(
                SourceMemberSnapshot.artifact_snapshot_id.in_(
                    select(SourceMemberSnapshot.artifact_snapshot_id)
                    .select_from(SourceMemberSnapshot)
                    .join(SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id)
                    .where(SourceArtifactSnapshot.ingestion_run_id == run.id)
                ),
                SourceMemberSnapshot.member_name.in_(member_names),
            )
        ).all()
    )
    snapshot_by_member_name = {item.member_name: item for item in snapshots}
    quarantine_rows = db.execute(
        select(IngestionFileMember.id, func.count(QuarantineItem.id))
        .select_from(IngestionFileMember)
        .join(IngestionRow, IngestionRow.ingestion_file_member_id == IngestionFileMember.id)
        .join(QuarantineItem, QuarantineItem.ingestion_row_id == IngestionRow.id)
        .where(IngestionFileMember.id.in_(member_ids))
        .group_by(IngestionFileMember.id)
    ).all()
    quarantine_by_member_id = {member_id: int(total_quarantine) for member_id, total_quarantine in quarantine_rows}
    delivery_rows = db.execute(
        select(SourceDeliverySnapshot.ingestion_file_member_id, func.count(SourceDeliverySnapshot.id))
        .where(SourceDeliverySnapshot.ingestion_file_member_id.in_(member_ids))
        .group_by(SourceDeliverySnapshot.ingestion_file_member_id)
    ).all()
    delivery_by_member_id = {member_id: int(total_delivery) for member_id, total_delivery in delivery_rows}

    dados = []
    for member in members:
        snapshot = snapshot_by_member_name.get(member.member_name)
        state = "unknown"
        if snapshot is not None and snapshot.lifecycle_status:
            state = snapshot.lifecycle_status
        elif member.schema_status == "invalid":
            state = "schema_invalid"
        links = {
            "run_detail": f"/ingestion/runs/{run.id}",
            "quarantine": f"/ingestion/quarentena?ingestion_run_id={run.id}&arquivo_origem={member.member_name}",
            "cancel": f"/ingestion/runs/{run.id}/members/{member.id}/cancel",
        }
        dados.append(
            IngestionRunMemberResumo(
                id=str(member.id),
                ingestion_file_id=str(member.ingestion_file_id),
                member_name=member.member_name,
                member_sha256=member.member_sha256,
                member_size_bytes=member.member_size_bytes,
                row_count=member.row_count,
                encoding=member.encoding,
                delimiter=member.delimiter,
                header=member.header,
                schema_status=member.schema_status,
                schema_message=member.schema_message,
                row_kind=None if snapshot is None else snapshot.row_kind,
                destino_promovido=None if snapshot is None else snapshot.destino_promovido,
                required_member=None if snapshot is None else snapshot.required_member,
                lifecycle_status=None if snapshot is None else snapshot.lifecycle_status,
                quarantine_total=quarantine_by_member_id.get(member.id, 0),
                delivery_total=delivery_by_member_id.get(member.id, 0),
                state=state,
                links=links,
            )
        )

    return ListaIngestionRunMembers(
        dados=dados,
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/operations",
    response_model=IngestionOperationsResumo,
    summary="Snapshot operacional consolidado da ingestion",
    description=(
        "Retorna um snapshot consolidado para consumidores desacoplados, agregando runs, execucoes, "
        "cancelamentos, sinais de fila Celery e o estado atual do gate de materializacao visto pela ingestao."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="obterIngestionOperationsAdmin",
)
def obter_ingestion_operations(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> IngestionOperationsResumo:
    inspect = celery_app.control.inspect(timeout=1.0)
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}

    candidate_runs = list(
        db.scalars(
            select(IngestionRun)
            .where(IngestionRun.status.in_(("agendada", "aguardando_ingestao", "em_execucao", "falha", "cancelada")))
            .order_by(IngestionRun.started_at.desc())
        ).all()
    )
    run_counts: dict[str, int] = {}
    active_runs: list[IngestionOperationRunPreview] = []
    recoverable_runs: list[IngestionOperationRunPreview] = []
    for run in candidate_runs:
        preview = _serialize_run_preview(db, run)
        run_counts[preview.state] = run_counts.get(preview.state, 0) + 1
        if preview.state in {"queued", "waiting", "running", "stale"}:
            active_runs.append(preview)
        if preview.next_action == "recover":
            recoverable_runs.append(preview)

    execution_rows = db.execute(
        select(ExecucaoSincronizacao.status, func.count(ExecucaoSincronizacao.id))
        .group_by(ExecucaoSincronizacao.status)
    ).all()
    execution_counts = {status: int(total) for status, total in execution_rows}

    cancellation_rows = db.execute(
        select(IngestionCancellationRequest.status, func.count(IngestionCancellationRequest.id))
        .group_by(IngestionCancellationRequest.status)
    ).all()
    cancellation_counts = {status: int(total) for status, total in cancellation_rows}

    from app.services.analise import obter_estado_gate_materializacao

    gate = obter_estado_gate_materializacao(db)
    materialization_gate = {
        "status": gate.status,
        "reason_code": gate.reason_code,
        "gate_enabled": gate.gate_enabled,
        "manual_control": gate.manual_control,
        "manual_reason": gate.manual_reason,
        "blocking_ingestions": gate.blocking_ingestions,
        "pending_ingestions": gate.pending_ingestions,
        "next_check_at": gate.next_check_at,
        "blockers": [
            {
                "tipo_fonte": item.source_type,
                "execucao_sincronizacao_id": item.execution_id,
                "ingestion_run_id": item.run_id,
                "ano": item.year,
                "status": item.status,
                "phase": item.phase,
                "started_at": item.started_at,
            }
            for item in gate.blockers
        ],
    }

    queue_names = ("ingestion", "ingestion_control", "analise_materializacao")
    worker_nodes = set(active) | set(reserved) | set(scheduled)
    queue_health = []
    for queue_name in queue_names:
        active_items = [item for items in active.values() if isinstance(items, list) for item in items if item.get("delivery_info", {}).get("routing_key") == queue_name]
        reserved_items = [item for items in reserved.values() if isinstance(items, list) for item in items if item.get("delivery_info", {}).get("routing_key") == queue_name]
        scheduled_items = [item for items in scheduled.values() if isinstance(items, list) for item in items if item.get("request", {}).get("delivery_info", {}).get("routing_key") == queue_name]
        queue_health.append({"name": queue_name, "workers_online": len(worker_nodes), "total_concurrency": None, "occupied_slots": len(active_items), "active_tasks": len(active_items), "reserved_tasks": len(reserved_items), "scheduled_tasks": len(scheduled_items), "backlog": len(reserved_items) + len(scheduled_items), "oldest_item_age_seconds": None, "state": "without_worker" if not worker_nodes else "ready"})

    active_total = len(active_runs)
    recoverable_total = len(recoverable_runs)
    action_counts: dict[str, int] = {}
    aggregate_progress = {"members_total": 0, "members_processed": 0, "quarantine_total": 0}
    for run in candidate_runs:
        preview = _serialize_run_preview(db, run)
        action = preview.next_action or "none"
        action_counts[action] = action_counts.get(action, 0) + 1
        progress = _build_progress_for_run(run)
        for key in aggregate_progress:
            aggregate_progress[key] += int(progress.get(key) or 0)
    oldest_waiting = min((run.started_at for run in candidate_runs if _serialize_run_preview(db, run).state in {"waiting", "stale"}), default=None)
    revision = int(max((int(run.updated_at.timestamp() * 1000) for run in candidate_runs), default=0))
    return IngestionOperationsResumo(
        generated_at=_agora(),
        run_counts=run_counts,
        execution_counts=execution_counts,
        cancellation_counts=cancellation_counts,
        task_counts={
            "active_total": sum(len(items) for items in active.values() if isinstance(items, list)),
            "reserved_total": sum(len(items) for items in reserved.values() if isinstance(items, list)),
            "scheduled_total": sum(len(items) for items in scheduled.values() if isinstance(items, list)),
            "ingestion_active": _count_ingestion_tasks(active),
            "ingestion_reserved": _count_ingestion_tasks(reserved),
            "ingestion_scheduled": _count_ingestion_tasks(scheduled),
        },
        materialization_gate=materialization_gate,
        active_runs=active_runs[:10],
        recoverable_runs=recoverable_runs[:10],
        revision=revision,
        action_counts=action_counts,
        waiting_for_operator_count=sum(1 for item in active_runs if item.state in {"waiting", "stale"}),
        oldest_action_required_at=oldest_waiting,
        queue_health=queue_health,
        active_runs_total=active_total,
        recoverable_runs_total=recoverable_total,
        previews_truncated=active_total > 10 or recoverable_total > 10,
        aggregate_progress=aggregate_progress,
    )


@router.get("/work-items", response_model=IngestionWorkItemList, summary="Listar trabalhos correlacionados de ingestao")
def listar_work_items(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    state: str | None = None,
    next_action: str | None = None,
    fonte: str | None = None,
    ano: int | None = None,
    origin: str | None = None,
    requested_by: str | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    has_quarantine: bool | None = None,
    has_drift: bool | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
    ordenar: str = "requested_at:desc",
) -> IngestionWorkItemList:
    from app.updates.models import PendingUpdate

    scopes = {(row[0], row[1]) for row in db.execute(select(IngestionRun.tipo_fonte, IngestionRun.ano)).all()}
    scopes |= {(row[0], row[1]) for row in db.execute(select(ExecucaoSincronizacao.tipo_fonte, ExecucaoSincronizacao.ano)).all()}
    scopes |= {(row[0], row[1]) for row in db.execute(select(PendingUpdate.fonte, PendingUpdate.ano)).all()}
    items = [item for key in scopes if (item := _work_item_from_scope(db, fonte=key[0], ano=key[1])) is not None]
    def matches(item: dict[str, Any]) -> bool:
        result = item.get("result") or {}
        run = item.get("run") or {}
        started_at = run.get("started_at") or item.get("requested_at")
        return (
            (state is None or item["state"] == state)
            and (next_action is None or item["next_action"] == next_action)
            and (fonte is None or item["fonte"] == fonte)
            and (ano is None or item["ano"] == ano)
            and (origin is None or item["origin"] == origin)
            and (requested_by is None or item.get("requested_by") == requested_by)
            and (started_from is None or (started_at is not None and started_at >= started_from))
            and (started_to is None or (started_at is not None and started_at <= started_to))
            and (has_quarantine is None or bool(result.get("quarantine_total")) == has_quarantine)
            and (has_drift is None or bool(result.get("has_drift")) == has_drift)
        )
    items = [item for item in items if matches(item)]
    reverse = not ordenar.endswith(":asc")
    items.sort(key=lambda item: item.get("requested_at") or datetime.min.replace(tzinfo=UTC), reverse=reverse)
    total = len(items)
    offset = (pagina - 1) * tamanho_pagina
    return IngestionWorkItemList(dados=items[offset : offset + tamanho_pagina], paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total))


@router.get("/work-items/{work_item_id}", summary="Detalhar trabalho correlacionado de ingestao")
def detalhar_work_item(work_item_id: str, db: DbSession, _: Annotated[None, Depends(validar_token_api)]) -> dict[str, Any]:
    fonte, ano = _parse_work_item_id(work_item_id)
    item = _work_item_from_scope(db, fonte=fonte, ano=ano)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item nao encontrado.")
    return item


@router.post("/dispatch/plan", response_model=IngestionDispatchPlanResponse, summary="Planejar despacho de ingestao")
def planejar_dispatch_ingestao(request: IngestionDispatchPlanRequest, auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)], db: DbSession) -> IngestionDispatchPlanResponse:
    actor = _actor(auth)
    valid_scopes: list[dict[str, Any]] = []
    invalid_scopes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for scope in request.scopes:
        scope_data = scope.model_dump()
        error = _validate_scope(scope_data)
        if error:
            invalid_scopes.append({**scope_data, "reason_code": error})
            continue
        fonte = scope_data["fonte"].lower().strip()
        scope_data["fonte"] = fonte
        scope_data["members_expected"] = [dataset.render_member_name(ano=scope_data["ano"]) for dataset in listar_datasets(fonte) if scope_data["ano"] is not None or fonte == "cadastro"]
        last_success = db.scalar(select(IngestionRun).where(IngestionRun.tipo_fonte == fonte, IngestionRun.ano == scope_data["ano"], IngestionRun.status.in_(("sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"))).order_by(IngestionRun.started_at.desc()).limit(1))
        scope_data["last_successful_run_id"] = None if last_success is None else str(last_success.id)
        scope_data["reuse_forecast"] = "unknown" if last_success is None else "eligible_by_sha256"
        valid_scopes.append(scope_data)
        conflict = _active_scope_conflict(db, fonte=fonte, ano=scope_data["ano"])
        if conflict:
            conflicts.append({**scope_data, **conflict, "reason_code": "ACTIVE_EQUIVALENT_WORK"})
    from app.services.analise import obter_estado_gate_materializacao
    gate = obter_estado_gate_materializacao(db)
    expires_at = _agora() + timedelta(minutes=15)
    plan = IngestionDispatchPlan(token=token_urlsafe(32), requested_by=actor, scopes=[{"fonte": item["fonte"], "ano": item["ano"]} for item in valid_scopes], strategy=request.strategy, force_reimport=request.force_reimport, summary={"conflicts": conflicts, "invalid_scopes": invalid_scopes}, expires_at=expires_at)
    db.add(plan)
    db.commit()
    return IngestionDispatchPlanResponse(plan_token=plan.token, expires_at=expires_at, valid_scopes=valid_scopes, invalid_scopes=invalid_scopes, dependencies=[], conflicts=conflicts, warnings=["FORCE_REIMPORT_REQUIRES_REASON"] if request.force_reimport and not request.reason else [], materialization_gate_impact={"will_block": bool(valid_scopes), "current_status": gate.status, "reason_code": gate.reason_code})


@router.post("/dispatch", response_model=IngestionDispatchResponse, summary="Confirmar e despachar plano de ingestao")
def despachar_ingestao(
    request: IngestionDispatchRequest,
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)],
) -> IngestionDispatchResponse:
    actor = _actor(auth)
    payload = request.model_dump(mode="json")
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    existing = db.scalar(select(IngestionIdempotencyRecord).where(IngestionIdempotencyRecord.requested_by == actor, IngestionIdempotencyRecord.operation == "dispatch", IngestionIdempotencyRecord.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail={"reason_code": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST"})
        return IngestionDispatchResponse(**existing.response_payload, idempotent_replay=True)
    plan = db.scalar(select(IngestionDispatchPlan).where(IngestionDispatchPlan.token == request.plan_token).limit(1))
    normalized_scopes: list[dict[str, Any]] = [{"fonte": scope.fonte.lower().strip(), "ano": scope.ano} for scope in request.scopes]
    if plan is None or plan.requested_by != actor:
        raise HTTPException(status_code=409, detail={"reason_code": "PLAN_NOT_FOUND_OR_NOT_OWNED"})
    plan_expires_at = plan.expires_at if plan.expires_at.tzinfo is not None else plan.expires_at.replace(tzinfo=UTC)
    if plan_expires_at <= _agora() or plan.consumed_at is not None:
        raise HTTPException(status_code=409, detail={"reason_code": "PLAN_EXPIRED_OR_CONSUMED"})
    if plan.scopes != normalized_scopes or plan.strategy != request.strategy or plan.force_reimport != request.force_reimport:
        raise HTTPException(status_code=409, detail={"reason_code": "PLAN_INCOMPATIBLE"})
    if request.force_reimport and not request.reason:
        raise HTTPException(status_code=422, detail={"reason_code": "FORCE_REIMPORT_REASON_REQUIRED"})
    conflicts = [conflict for scope in normalized_scopes if (conflict := _active_scope_conflict(db, fonte=scope["fonte"], ano=scope["ano"]))]
    if conflicts:
        raise HTTPException(status_code=409, detail={"reason_code": "ACTIVE_EQUIVALENT_WORK", **conflicts[0]})
    work_items: list[dict[str, Any]] = []
    tasks = {"cadastro": sincronizar_cadastro_companhias_task, "dfp": sincronizar_dfp_task, "itr": sincronizar_itr_task, "fre": sincronizar_fre_task, "fca": sincronizar_fca_task, "ipe": sincronizar_ipe_task, "vlmo": sincronizar_vlmo_task, "cgvn": sincronizar_cgvn_task}
    staged: list[tuple[dict[str, Any], str, ExecucaoSincronizacao]] = []
    for scope in normalized_scopes:
        task_id = novo_task_id()
        execution = criar_execucao_sincronizacao_agendada(db, tipo_fonte=scope["fonte"], ano=scope["ano"], task_id=task_id)
        staged.append((scope, task_id, execution))
    plan.consumed_at = _agora()
    db.flush()
    for scope, task_id, execution in staged:
        db.add(IngestionOperationAudit(scope_type="scope", scope_id=_scope_key(scope["fonte"], scope["ano"]), operation="force_reimport" if request.force_reimport else "dispatch", requested_by=actor, reason=request.reason, consequence={"execution_id": str(execution.id), "task_id": task_id}))
        task = tasks[scope["fonte"]]
        kwargs = {"force_reimport": request.force_reimport}
        if scope["fonte"] == "cadastro":
            task.apply_async(kwargs=kwargs, task_id=task_id)
        else:
            task.apply_async(args=(scope["ano"],), kwargs=kwargs, task_id=task_id)
        work_items.append({"id": _scope_key(scope["fonte"], scope["ano"]), "execution_id": str(execution.id), "run_id": None, "task_id": task_id, "state": "queued"})
    response_payload: dict[str, Any] = {"status": "accepted", "work_items": work_items}
    db.add(IngestionIdempotencyRecord(requested_by=actor, operation="dispatch", idempotency_key=idempotency_key, request_fingerprint=fingerprint, response_payload=response_payload, expires_at=_agora() + timedelta(hours=24)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(select(IngestionIdempotencyRecord).where(IngestionIdempotencyRecord.requested_by == actor, IngestionIdempotencyRecord.operation == "dispatch", IngestionIdempotencyRecord.idempotency_key == idempotency_key))
        if concurrent is not None and concurrent.request_fingerprint == fingerprint:
            return IngestionDispatchResponse(**concurrent.response_payload, idempotent_replay=True)
        raise
    return IngestionDispatchResponse(**response_payload)


@router.get("/runs/{run_id}/completion-evidence", summary="Obter evidencia de conclusao de uma run")
def obter_evidencia_conclusao(run_id: UUID, db: DbSession, _: Annotated[None, Depends(validar_token_api)]) -> dict[str, Any]:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    artifact = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run.id).order_by(SourceArtifactSnapshot.created_at.desc()).limit(1))
    member_rows = db.execute(select(SourceMemberSnapshot.lifecycle_status, func.count(SourceMemberSnapshot.id)).join(SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id).where(SourceArtifactSnapshot.ingestion_run_id == run.id).group_by(SourceMemberSnapshot.lifecycle_status)).all()
    members = {status: int(total) for status, total in member_rows}
    quarantine_total = int(db.scalar(select(func.count(QuarantineItem.id)).where(QuarantineItem.ingestion_run_id == run.id)) or 0)
    quality = run.quality_summary or {}
    return {"run_id": str(run.id), "artifact": None if artifact is None else {"resource_url": artifact.resource_url, "sha256": artifact.content_sha256, "baseline": artifact.sha_confirmation_result}, "members": {"expected": sum(members.values()), "processed": members.get("processed", 0), "reused": members.get("member_skipped", 0), "missing": len((run.change_summary or {}).get("required_member_missing", [])), "failed": members.get("schema_invalid", 0)}, "canonical_write_confirmed": run.status in {"sucesso", "sucesso_com_alerta"}, "quarantine": {"total": quarantine_total, "present": quarantine_total > 0}, "drift": {"present": bool((run.change_summary or {}).get("schema_changed"))}, "reconcile": _reconcile_summary_from_run(run), "duplicate_avoided": int(quality.get("members_skipped", 0) or 0) > 0, "records_promoted": int(quality.get("members_processados", 0) or 0), "inserted": quality.get("inserted"), "updated": quality.get("updated"), "unchanged": quality.get("unchanged"), "requested_by": run.requested_by_task_id, "started_at": run.started_at, "finished_at": run.finished_at, "follow_up_work": []}


@router.get("/work-items/{work_item_id}/events", summary="Listar timeline correlacionada de um trabalho")
def listar_eventos_work_item(work_item_id: str, db: DbSession, _: Annotated[None, Depends(validar_token_api)], after: str | None = None, tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100) -> dict[str, Any]:
    fonte, ano = _parse_work_item_id(work_item_id)
    item = _work_item_from_scope(db, fonte=fonte, ano=ano)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item nao encontrado.")
    events: list[dict[str, Any]] = []
    audit_scope_ids = [work_item_id]
    update = item.get("update")
    if update:
        from app.updates.models import PendingUpdate
        pending = db.get(PendingUpdate, UUID(update["id"]))
        if pending:
            events.append({"code": "update.detected", "occurred_at": pending.detection_timestamp, "payload": {"status": pending.status}})
    if item.get("execution"):
        execution = db.get(ExecucaoSincronizacao, UUID(item["execution"]["id"]))
        if execution:
            events.append({"code": "execution.scheduled", "occurred_at": execution.iniciada_em, "payload": {"status": execution.status}})
    if item.get("run"):
        run = db.get(IngestionRun, UUID(item["run"]["id"]))
        if run:
            audit_scope_ids.append(str(run.id))
            events.append({"code": "run.started", "occurred_at": run.started_at, "payload": {"phase": run.phase, "status": run.status}})
            for phase in db.scalars(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id).order_by(IngestionPhaseExecution.created_at.asc())).all():
                events.append({"code": f"run.phase.{phase.status}", "occurred_at": phase.updated_at, "payload": {"phase": phase.phase, "attempt": phase.attempt}})
            if run.finished_at:
                events.append({"code": "run.completed", "occurred_at": run.finished_at, "payload": {"status": run.status}})
    for audit in db.scalars(select(IngestionOperationAudit).where(IngestionOperationAudit.scope_id.in_(audit_scope_ids)).order_by(IngestionOperationAudit.created_at.asc())).all():
        events.append({"code": f"operation.{audit.operation}", "occurred_at": audit.created_at, "payload": {"reason": audit.reason, "consequence": audit.consequence}})
    events.sort(key=lambda event: event["occurred_at"])
    if after:
        events = [event for event in events if event["occurred_at"].isoformat() > after]
    returned = events[:tamanho_pagina]
    return {"dados": [{**event, "event_id": f"{work_item_id}:{index}", "revision": index + 1} for index, event in enumerate(returned)], "next_cursor": None if len(events) <= tamanho_pagina or not returned else returned[-1]["occurred_at"].isoformat()}


@router.get("/scopes", summary="Listar cobertura consolidada por fonte e ano")
def listar_escopos_ingestao(db: DbSession, _: Annotated[None, Depends(validar_token_api)], fonte: str | None = None, ano: int | None = None) -> dict[str, Any]:
    from app.updates.models import PendingUpdate
    keys = {(row[0], row[1]) for row in db.execute(select(IngestionRun.tipo_fonte, IngestionRun.ano)).all()}
    keys |= {(row[0], row[1]) for row in db.execute(select(PendingUpdate.fonte, PendingUpdate.ano)).all()}
    scopes = []
    for source, year in sorted(keys):
        if (fonte and source != fonte) or (ano is not None and year != ano):
            continue
        item = _work_item_from_scope(db, fonte=source, ano=year)
        if item is None:
            continue
        run_data = item.get("run") or {}
        result = item.get("result") or {}
        scopes.append({"fonte": source, "ano": year, "last_successful_run_id": run_data.get("id") if run_data.get("status") in {"sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped"} else None, "baseline": run_data.get("id"), "members_required": [dataset.render_member_name(ano=year) for dataset in listar_datasets(source) if year is not None or source == "cadastro"], "pending_update": item.get("update"), "active_work_item": item if item["state"] in {"queued", "waiting", "running", "stale"} else None, "quarantine_pending": result.get("quarantine_total", 0), "coverage_state": "degraded" if result.get("quarantine_total") or result.get("has_drift") else ("covered" if run_data else "missing"), "next_action": item["next_action"], "unavailability_reason": None if run_data else "NO_SUCCESSFUL_RUN"})
    return {"dados": scopes, "total": len(scopes)}


@router.get("/quarentena/grupos", summary="Agrupar quarentena por dimensao operacional")
def grupos_quarentena(db: DbSession, _: Annotated[None, Depends(validar_token_api)], agrupar_por: str = Query(default="motivo", pattern="^(motivo|fonte|ano|arquivo|row_kind|reparabilidade)$")) -> dict[str, Any]:
    field = {"motivo": QuarantineItem.motivo_codigo, "ano": QuarantineItem.ano_origem, "arquivo": QuarantineItem.arquivo_origem, "row_kind": QuarantineItem.row_kind, "reparabilidade": QuarantineItem.reparavel}.get(agrupar_por)
    if agrupar_por == "fonte":
        source_rows = db.execute(select(IngestionRun.tipo_fonte, func.count(QuarantineItem.id), func.min(QuarantineItem.created_at), func.sum(QuarantineItem.tentativas_reprocessamento)).join(IngestionRun, IngestionRun.id == QuarantineItem.ingestion_run_id).group_by(IngestionRun.tipo_fonte)).all()
        return {"grouped_by": agrupar_por, "dados": [{"key": key, "count": int(count), "oldest_at": oldest, "attempts": int(attempts or 0), "recommended_action": "replay" if key else "inspect"} for key, count, oldest, attempts in source_rows]}
    assert field is not None
    grouped_rows = db.execute(select(field, func.count(QuarantineItem.id), func.min(QuarantineItem.created_at), func.sum(QuarantineItem.tentativas_reprocessamento)).group_by(field)).all()
    return {"grouped_by": agrupar_por, "dados": [{"key": key, "count": int(count), "oldest_at": oldest, "attempts": int(attempts or 0), "recommended_action": "replay" if key else "inspect"} for key, count, oldest, attempts in grouped_rows]}


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RespostaCancelamentoSincronizacao,
    summary="Cancelar uma run de ingestion",
    description=(
        "Cancela diretamente a run informada, resolvendo a execucao correlata quando existir. "
        "O comportamento operacional e o mesmo do cancelamento administrativo geral, mas com seletor orientado a `run_id`."
    ),
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Run nao encontrado."}},
    operation_id="cancelarIngestionRunAdmin",
)
def cancelar_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    terminar_imediatamente: Annotated[bool, Query()] = True,
    motivo: Annotated[str | None, Query(max_length=1000)] = None,
) -> RespostaCancelamentoSincronizacao:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    return _cancelar_sincronizacao_por_seletor(
        db=db,
        id_execucao=run.execucao_sincronizacao_id,
        id_tarefa=run.requested_by_task_id if run.execucao_sincronizacao_id is None else None,
        terminar_imediatamente=terminar_imediatamente,
        motivo=motivo,
    )


@router.post(
    "/runs/{run_id}/members/{member_id}/cancel",
    response_model=RespostaCancelamentoSincronizacao,
    summary="Cancelar member especifico de uma run de ingestion",
    description=(
        "Cancela apenas o processamento do member/CSV indicado dentro da run. "
        "A operacao procura a execucao filha correlata quando a run representa um ZIP anual."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run, member ou execucao filha nao encontrados."},
        409: {"description": "Member nao esta em andamento e nao pode ser cancelado."},
    },
    operation_id="cancelarIngestionRunMemberAdmin",
)
def cancelar_ingestion_run_member(
    run_id: Annotated[UUID, Path()],
    member_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    terminar_imediatamente: Annotated[bool, Query()] = True,
    motivo: Annotated[str | None, Query(max_length=1000)] = None,
) -> RespostaCancelamentoSincronizacao:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    member = db.scalar(
        select(IngestionFileMember)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .where(
            IngestionFile.ingestion_run_id == run.id,
            IngestionFileMember.id == member_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member nao encontrado para esta run.")

    execucao_alvo: ExecucaoSincronizacao | None = None
    if run.execucao_sincronizacao_id is not None:
        parent_execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)
        if parent_execucao is not None and parent_execucao.tipo_execucao == "arquivo_membro" and parent_execucao.arquivo == member.member_name:
            execucao_alvo = parent_execucao
        else:
            execucao_alvo = db.scalar(
                select(ExecucaoSincronizacao)
                .where(
                    ExecucaoSincronizacao.parent_execucao_id == run.execucao_sincronizacao_id,
                    ExecucaoSincronizacao.arquivo == member.member_name,
                )
                .order_by(ExecucaoSincronizacao.iniciada_em.desc())
                .limit(1)
            )
    if execucao_alvo is None:
        raise HTTPException(status_code=404, detail="Execucao filha nao encontrada para este member.")

    return _cancelar_sincronizacao_por_seletor(
        db=db,
        id_execucao=execucao_alvo.id,
        id_tarefa=None,
        terminar_imediatamente=terminar_imediatamente,
        motivo=motivo,
    )


@router.post(
    "/runs/{run_id}/recover",
    response_model=ReplayResposta,
    summary="Recuperar administrativamente uma run de ingestion",
    description=(
        "Executa recuperacao administrativa controlada de uma run marcada como stale ou falhada com erro recuperavel. "
        "A operacao so e aceita quando a run possui staging reaplicavel ou uma execucao de member correlata. "
        "Quando nao houver fonte executavel, responde `409` com `reason_code=NO_RECOVERY_SOURCE`. "
        "Runs concluidas ou com falha nao retentavel tambem respondem `409`, respectivamente com "
        "`RUN_ALREADY_COMPLETED` ou `NON_RETRYABLE_FAILURE`, e podem ser sucedidas por novo dispatch equivalente."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run nao encontrado."},
        409: {"description": "Run nao esta em estado recuperavel (`RUN_ALREADY_COMPLETED`, `NON_RETRYABLE_FAILURE` ou `RUN_NOT_RECOVERABLE`) ou nao possui fonte executavel (`NO_RECOVERY_SOURCE`)."},
        503: {
            "description": "Falha temporaria de banco ou falha terminal ao publicar a task de recovery no Celery.",
            "content": {
                "application/json": {
                    "examples": {
                        "database_pool_exhausted": {
                            "value": {"detail": {"reason_code": "DATABASE_POOL_EXHAUSTED", "retryable": True}}
                        },
                        "recovery_dispatch_failed": {
                            "value": {
                                "detail": {
                                    "reason_code": "RECOVERY_DISPATCH_FAILED",
                                    "retryable": False,
                                    "run_id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
                                }
                            }
                        },
                    }
                }
            },
        },
    },
    operation_id="recoverIngestionRunAdmin",
)
def recover_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    operational = _build_run_operational_fields(db, run)
    recovery = operational["recovery"]
    if operational["next_action"] != "recover" or not recovery["eligible"]:
        raise HTTPException(status_code=409, detail={"reason_code": recovery["reason_code"], "recovery": recovery})
    if recovery["strategy"] == "rerun_member_execution":
        execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)
        parent_id = None if execucao is None else execucao.parent_execucao_id
        if execucao is None or parent_id is None:
            raise HTTPException(status_code=409, detail={"reason_code": "NO_RECOVERY_SOURCE", "recovery": recovery})
        from app.worker.tasks import sincronizar_member_task

        task_id = novo_task_id()
        execucao.id_tarefa = task_id
        execucao.status = "agendada"
        execucao.finalizada_em = None
        execucao.mensagem_erro = None
        run.status = "agendada"
        run.requested_by_task_id = task_id
        run.message = "Recovery de member agendado."
        run.finished_at = None
        db.commit()
        try:
            sincronizar_member_task.apply_async(
                kwargs={
                    "tipo_fonte": execucao.tipo_fonte,
                    "ano": execucao.ano or 0,
                    "member_name": execucao.arquivo,
                    "parent_execucao_id": str(parent_id),
                    "child_execucao_id": str(execucao.id),
                    "force_reimport": True,
                },
                task_id=task_id,
            )
        except Exception as exc:
            marcar_agendamento_com_falha(db, task_ids=[task_id], erro=str(exc))
            update_run_state(
                run,
                status="falha",
                phase="complete",
                message=f"{_RECOVERY_DISPATCH_FAILURE_PREFIX} {exc}",
                finished_at=_agora(),
            )
            db.commit()
            raise HTTPException(
                status_code=503,
                detail={
                    "reason_code": "RECOVERY_DISPATCH_FAILED",
                    "retryable": False,
                    "run_id": str(run.id),
                },
            ) from exc
        return ReplayResposta(status="agendada", detalhe={"task_id": task_id, "strategy": recovery["strategy"]})
    try:
        resultado = replay_ingestion_run_service(db, run_id=run_id)
    except NoRecoverySourceError:
        raise HTTPException(status_code=409, detail={"reason_code": "NO_RECOVERY_SOURCE", "recovery": recovery}) from None
    except SQLAlchemyTimeoutError:
        raise HTTPException(status_code=503, detail={"reason_code": "DATABASE_POOL_EXHAUSTED"}) from None
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.post(
    "/runs/{run_id}/acknowledge-failure",
    response_model=IngestionFailureAcknowledgement,
    summary="Reconhecer falha investigada de uma run",
    description=(
        "Encerra a pendencia operacional `inspect_error` depois da investigacao, sem apagar a run, fases, "
        "staging, filas ou dados promovidos. Registra ator, motivo e a ocorrencia exata da falha em auditoria "
        "imutavel. Depois do reconhecimento, a run preserva `state=failed`, passa a `next_action=none` e deixa "
        "de aparecer em consultas de work items com `next_action=inspect_error`. Uma falha posterior na mesma "
        "run cria uma nova ocorrencia e exige novo reconhecimento."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run nao encontrada."},
        409: {"description": "A run nao possui uma falha terminal aguardando investigacao."},
    },
    operation_id="acknowledgeIngestionRunFailureAdmin",
)
def acknowledge_ingestion_run_failure(
    run_id: Annotated[UUID, Path()],
    payload: IngestionFailureAcknowledgementRequest,
    db: DbSession,
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> IngestionFailureAcknowledgement:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrada.")
    operational = _build_run_operational_fields(db, run)
    existing = operational["failure_acknowledgement"]
    if existing is not None:
        return IngestionFailureAcknowledgement(**existing)
    if operational["state"] != "failed" or operational["next_action"] != "inspect_error":
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "FAILURE_NOT_ACKNOWLEDGEABLE"},
        )

    latest_phase = get_latest_phase_execution(db, run_id=run.id)
    failure_key = _failure_key(run, latest_phase)
    audit = IngestionOperationAudit(
        scope_type="run",
        scope_id=str(run.id),
        operation="acknowledge_failure",
        requested_by=_actor(auth),
        reason=payload.reason,
        consequence={
            "failure_key": failure_key,
            "error_type": (operational["last_error"] or {}).get("error_type"),
            "error_message": (operational["last_error"] or {}).get("error_message"),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return IngestionFailureAcknowledgement(
        acknowledged_at=audit.created_at,
        acknowledged_by=audit.requested_by,
        reason=audit.reason or "",
        failure_key=failure_key,
    )


@router.post(
    "/runs/{run_id}/cleanup-transient-state",
    response_model=ReplayResposta,
    summary="Limpar estado transitorio de run cancelada ou falha",
    description=(
        "Remove staging generico, staging tipado financeiro e eventos/quarentena associados a linhas da run, "
        "e fecha fases ou execucoes relacionadas que ainda estejam presas. "
        "Use apos cancelamento administrativo ou falha recuperavel quando a politica operacional permitir reconstruir a ingestao. "
        "A acao nao remove dados canonicos ja promovidos."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run nao encontrada."},
        409: {"description": "A run precisa estar cancelada ou falha para limpeza transitoria."},
    },
    operation_id="cleanupIngestionRunTransientStateAdmin",
)
def cleanup_ingestion_run_transient_state(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrada.")
    if run.status not in {"cancelada", "falha"}:
        raise HTTPException(status_code=409, detail="A run precisa estar cancelada ou falha para limpeza transitoria.")
    resultado = _cleanup_transient_state_for_run(db, run=run)
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.get(
    "/quarentena",
    response_model=ListaQuarantineItems,
    summary="Listar Quarentena de Ingestion",
    description=(
        "Lista paginada da fila de reparo da ingestao.\n\n"
        "Quando `status` nao e informado, o endpoint retorna apenas itens `pendente`. "
        "Use `status=all` para consultar o historico completo.\n\n"
        "Cada item representa uma excecao persistida de linha, com `motivo_codigo`, `status`, `reparavel`, "
        "`tentativas_reprocessamento` e `diagnostico` apropriados para filtragem e suporte operacional.\n\n"
        "Erros de lote durante promote sao isolados por savepoint. Quando uma linha falha individualmente, ela permanece "
        "na quarentena com `motivo_codigo=normalizacao_invalida` e diagnostico estruturado do erro."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarIngestionQuarentenaAdmin",
)
def listar_ingestion_quarentena(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Número da página para listagem paginada.")] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500, description="Quantidade de registros por página.")] = 100,
    motivo_codigo: Annotated[str | None, Query(description="Filtrar itens pelo código estável do motivo de rejeição.")] = None,
    arquivo_origem: Annotated[str | None, Query(description="Filtrar itens pelo nome do arquivo de origem.")] = None,
    status: Annotated[
        str | None,
        Query(description="Filtrar itens pelo status operacional. Padrão implícito: `pendente`. Use `all` para não filtrar por status.")
    ] = None,
    ano_origem: Annotated[int | None, Query(description="Filtrar itens pelo ano de origem.")] = None,
) -> ListaQuarantineItems:
    offset = (pagina - 1) * tamanho_pagina
    query = select(QuarantineItem)
    query_total = select(func.count()).select_from(QuarantineItem)
    if motivo_codigo:
        query = query.where(QuarantineItem.motivo_codigo == motivo_codigo)
        query_total = query_total.where(QuarantineItem.motivo_codigo == motivo_codigo)
    if arquivo_origem:
        query = query.where(QuarantineItem.arquivo_origem == arquivo_origem)
        query_total = query_total.where(QuarantineItem.arquivo_origem == arquivo_origem)
    status_filter = status
    if status_filter is None:
        status_filter = "pendente"
    elif status_filter == "all" or status_filter == "":
        status_filter = None

    if status_filter:
        query = query.where(QuarantineItem.status == status_filter)
        query_total = query_total.where(QuarantineItem.status == status_filter)
    if ano_origem is not None:
        query = query.where(QuarantineItem.ano_origem == ano_origem)
        query_total = query_total.where(QuarantineItem.ano_origem == ano_origem)
        
    itens = (
        db.execute(query.order_by(QuarantineItem.created_at.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.scalar(query_total) or 0
    return ListaQuarantineItems(
        dados=[
            QuarantineItemResposta(
                id=str(item.id),
                ingestion_run_id=None if item.ingestion_run_id is None else str(item.ingestion_run_id),
                ingestion_row_id=str(item.ingestion_row_id),
                arquivo_origem=item.arquivo_origem,
                ano_origem=item.ano_origem,
                linha_origem=item.linha_origem,
                row_kind=item.row_kind,
                status=item.status,
                motivo_codigo=item.motivo_codigo,
                severidade=item.severidade,
                reparavel=item.reparavel,
                tentativas_reprocessamento=item.tentativas_reprocessamento,
                diagnostico=item.diagnostico,
            )
            for item in itens
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/quarentena/resumo",
    response_model=QuarentenaResumoResposta,
    summary="Resumo Analítico da Quarentena",
    description=(
        "Retorna metricas agregadas da fila de reparo. "
        "Quando `status` nao e informado, `total`, `por_erro`, `por_arquivo` e `por_arquivo_e_erro` consideram apenas itens `pendente`. "
        "Use `status=all` para consultar o historico completo. "
        "O retorno agrega distribuicao por status, ranking por `motivo_codigo`, ranking por `arquivo_origem` "
        "e o cruzamento entre arquivo e motivo."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="resumoIngestionQuarentenaAdmin",
)
def obter_resumo_quarentena(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    status: Annotated[
        str | None,
        Query(description="Filtrar resumo por status específico da fila de reparo. Padrão implícito: `pendente`. Use `all` para não filtrar por status.")
    ] = None,
    ingestion_run_id: Annotated[UUID | None, Query(description="Filtrar resumo por ID de execução de run de ingestão (ingestion_run).")] = None,
    execucao_sincronizacao_id: Annotated[UUID | None, Query(description="Filtrar resumo por ID de execução de sincronização (execucao_sincronizacao).")] = None,
) -> QuarentenaResumoResposta:
    # Construir cláusulas de filtragem compartilhadas
    status_filter = status
    if status_filter is None:
        status_filter = "pendente"
    elif status_filter == "all" or status_filter == "":
        status_filter = None

    filtros = []
    if status_filter:
        filtros.append(QuarantineItem.status == status_filter)
    if ingestion_run_id:
        filtros.append(QuarantineItem.ingestion_run_id == ingestion_run_id)
    if execucao_sincronizacao_id:
        filtros.append(QuarantineItem.execucao_sincronizacao_id == execucao_sincronizacao_id)

    # 1. Total Geral (sob filtros)
    query_total = select(func.count(QuarantineItem.id))
    if filtros:
        query_total = query_total.where(*filtros)
    total = db.scalar(query_total) or 0

    # 2. Por Status (sem filtro de status, apenas filtros contextuais)
    filtros_status = []
    if ingestion_run_id:
        filtros_status.append(QuarantineItem.ingestion_run_id == ingestion_run_id)
    if execucao_sincronizacao_id:
        filtros_status.append(QuarantineItem.execucao_sincronizacao_id == execucao_sincronizacao_id)

    query_status = select(QuarantineItem.status, func.count(QuarantineItem.id)).group_by(QuarantineItem.status)
    if filtros_status:
        query_status = query_status.where(*filtros_status)
    status_rows = db.execute(query_status).all()
    por_status = {r[0]: r[1] for r in status_rows}

    # 3. Por Erro (motivo_codigo)
    query_erro = (
        select(QuarantineItem.motivo_codigo, func.count(QuarantineItem.id))
        .group_by(QuarantineItem.motivo_codigo)
        .order_by(func.count(QuarantineItem.id).desc())
    )
    if filtros:
        query_erro = query_erro.where(*filtros)
    erro_rows = db.execute(query_erro).all()
    por_erro = [ErroQuantidade(motivo_codigo=r[0], quantidade=r[1]) for r in erro_rows]

    # 4. Por Arquivo
    query_arquivo = (
        select(QuarantineItem.arquivo_origem, func.count(QuarantineItem.id))
        .group_by(QuarantineItem.arquivo_origem)
        .order_by(func.count(QuarantineItem.id).desc())
    )
    if filtros:
        query_arquivo = query_arquivo.where(*filtros)
    arquivo_rows = db.execute(query_arquivo).all()
    por_arquivo = [ArquivoQuantidade(arquivo_origem=r[0], quantidade=r[1]) for r in arquivo_rows]

    # 5. Por Arquivo e Erro
    query_ae = (
        select(QuarantineItem.arquivo_origem, QuarantineItem.motivo_codigo, func.count(QuarantineItem.id))
        .group_by(QuarantineItem.arquivo_origem, QuarantineItem.motivo_codigo)
        .order_by(QuarantineItem.arquivo_origem, func.count(QuarantineItem.id).desc())
    )
    if filtros:
        query_ae = query_ae.where(*filtros)
    ae_rows = db.execute(query_ae).all()
    por_arquivo_e_erro = [
        ArquivoErroQuantidade(arquivo_origem=r[0], motivo_codigo=r[1], quantidade=r[2]) for r in ae_rows
    ]

    # 6. Métricas Independentes de Status
    total_historico_query = select(func.count(QuarantineItem.id))
    if filtros_status:
        total_historico_query = total_historico_query.where(*filtros_status)
    total_historico = db.scalar(total_historico_query) or 0

    total_pendentes_query = select(func.count(QuarantineItem.id)).where(QuarantineItem.status == "pendente")
    if filtros_status:
        total_pendentes_query = total_pendentes_query.where(*filtros_status)
    total_pendentes = db.scalar(total_pendentes_query) or 0

    total_resolvidos_query = select(func.count(QuarantineItem.id)).where(QuarantineItem.status.like("resolvido_%"))
    if filtros_status:
        total_resolvidos_query = total_resolvidos_query.where(*filtros_status)
    total_resolvidos = db.scalar(total_resolvidos_query) or 0

    return QuarentenaResumoResposta(
        total=total,
        por_status=por_status,
        por_erro=por_erro,
        por_arquivo=por_arquivo,
        por_arquivo_e_erro=por_arquivo_e_erro,
        total_pendentes=total_pendentes,
        total_resolvidos=total_resolvidos,
        total_historico=total_historico,
    )


@router.post(
    "/replay/quarentena",
    response_model=ReplayResposta,
    summary="Reprocessar Quarentena de Ingestion",
    description=(
        "Executa replay sobre itens pendentes da quarentena. "
        "A requisicao aceita filtros opcionais por `reason_code`, `arquivo_origem` e `ano`. "
        "Quando nenhum filtro e enviado, todos os itens `pendente` sao considerados. "
        "O replay atua apenas sobre excecoes persistidas da quarentena e processa cada linha de forma independente. "
        "Se uma linha falhar novamente, o item permanece na quarentena com diagnostico atualizado."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="replayIngestionQuarentenaAdmin",
)
def replay_ingestion_quarentena(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    payload: Annotated[
        ReplayQuarantineRequisicao | None,
        Body(
            examples=[
                {"reason_code": "companhia_nao_encontrada"},
                {"arquivo_origem": "itr_cia_aberta_2021.csv", "ano": 2021},
            ]
        ),
    ] = None,
) -> ReplayResposta:
    payload = payload or ReplayQuarantineRequisicao()
    resultado = replay_quarantine(
        db,
        reason_code=payload.reason_code,
        arquivo_origem=payload.arquivo_origem,
        ano=payload.ano,
    )
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.post(
    "/runs/{run_id}/replay",
    response_model=ReplayResposta,
    summary="Reprocessar Run de Ingestion",
    description=(
        "Executa replay administrativo de uma run a partir dos artefatos retidos. "
        "A operacao reaplica o fluxo operacional da run, incluindo reavaliacao de members, promote, quarentena e reconcile. "
        "Use este endpoint quando uma correcao de regra, parser ou identidade precisar ser aplicada novamente ao escopo inteiro da run."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Run nao encontrado."},
        409: {"description": "Nao existe fonte de recovery executavel para esta run (`NO_RECOVERY_SOURCE`)."},
    },
    operation_id="replayIngestionRunAdmin",
)
def replay_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    try:
        resultado = replay_ingestion_run_service(db, run_id=run_id)
    except NoRecoverySourceError:
        recovery = assess_ingestion_run_recovery(db, run=run)
        raise HTTPException(
            status_code=409,
            detail={"reason_code": recovery.reason_code, "recovery": recovery.as_dict()},
        ) from None
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.post(
    "/identity/rebuild",
    response_model=ReplayResposta,
    summary="Reconstruir Identidade de Ingestion",
    description=(
        "Reprocessa o cadastro para reconstruir a malha de identidade usada por DFP, ITR e FRE. "
        "O frontend deve expor esta acao como operacao administrativa forte, "
        "normalmente seguida de replay da quarentena "
        "por `companhia_nao_encontrada`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="rebuildIngestionIdentityAdmin",
)
def rebuild_ingestion_identity(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    resultado = sincronizar_cadastro_companhias(db)
    return ReplayResposta(status="sucesso", detalhe=resultado)
