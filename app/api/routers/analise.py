from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select

from app.api.auth import exigir_admin_api, exigir_operador_materializacao_api
from app.api.deps import DbSession, PaginacaoQuery
from app.core.config import get_settings
from app.models.analise import (
    AnaliseMaterializacaoCampanha,
    AnaliseMaterializacaoCampanhaItem,
    AnaliseMaterializacaoChunkExecucao,
    AnaliseMaterializacaoControle,
    AnaliseMaterializacaoExecucao,
)
from app.models.companhia import Companhia
from app.schemas.analise import (
    AnaliseBasePeriodo,
    AnaliseBriefResposta,
    AnaliseComparacoesResposta,
    AnaliseEscopo,
    AnaliseEventosResposta,
    AnaliseGovernancaResposta,
    AnaliseManifestoResposta,
    AnaliseMaterializacaoCampanhaItemPreview,
    AnaliseMaterializacaoCampanhaResumo,
    AnaliseMaterializacaoChunkExecucaoPreview,
    AnaliseMaterializacaoChunkExecucaoResumo,
    AnaliseMaterializacaoControleResposta,
    AnaliseMaterializacaoExecucaoDetalhe,
    AnaliseMaterializacaoExecucaoResumo,
    AnaliseMaterializacaoExecucoesListaResposta,
    AnaliseMaterializacaoExecucoesResumo,
    AnaliseMaterializacaoFilaSnapshot,
    AnaliseMaterializacaoGateSnapshot,
    AnaliseMaterializacaoIngestionBlocker,
    AnaliseMaterializacaoMonitoramentoResposta,
    AnaliseMaterializacaoProgress,
    AnaliseMaterializacaoReativacaoResposta,
    AnaliseMaterializacaoReativacaoSweepResposta,
    AnaliseMaterializacaoRecuperacaoResposta,
    AnaliseMetricasCatalogoResposta,
    AnalisePeriodicidade,
    AnalisePessoasResposta,
    AnaliseQualidadeResposta,
    AnaliseRestatementsResposta,
    AnaliseSeriesResposta,
    AnaliseSinaisResposta,
)
from app.schemas.comum import Paginacao
from app.services.analise import (
    contar_chunks_stale_campanha,
    listar_metricas,
    obter_brief,
    obter_chunk_ativo_campanha,
    obter_chunks_stale_ativos,
    obter_comparacoes,
    obter_controle_materializacao,
    obter_estado_gate_materializacao,
    obter_eventos,
    obter_governanca,
    obter_manifesto,
    obter_pessoas,
    obter_qualidade,
    obter_restatements,
    obter_series,
    obter_sinais,
    pausar_controle_materializacao,
    reativar_materializacao_campanha,
    recuperar_chunks_materializacao_stale,
    recuperar_materializacao_pendente,
    retomar_controle_materializacao,
)
from app.worker.celery_app import celery_app

router = APIRouter(prefix="/analise")
_MATERIALIZACAO_TASK_NAME = "app.worker.tasks.materializar_analise_companhia_task"
_MATERIALIZACAO_CAMPANHA_TASK_NAME = "app.worker.tasks.materializar_analise_campanha_task"
_MATERIALIZACAO_CHUNK_TASK_NAME = "app.worker.tasks.materializar_analise_chunk_task"
_MATERIALIZACAO_RECOVERY_TASK_NAME = "app.worker.tasks.reconciliar_materializacao_stale_task"
_MATERIALIZACAO_PENDING_RECOVERY_TASK_NAME = "app.worker.tasks.recuperar_materializacao_pendente_task"
_STALL_THRESHOLD_SECONDS = 300
_settings = get_settings()

_RESPOSTAS_PADRAO: dict[int | str, dict[str, Any]] = {
    404: {
        "description": "Recurso não encontrado para os critérios informados.",
        "content": {"application/json": {"example": {"detail": "Companhia nao encontrada."}}},
    },
    422: {
        "description": "Parâmetro inválido.",
        "content": {"application/json": {"example": {"detail": "Campo invalido."}}},
    },
}

_RESPOSTAS_OPERACAO_MATERIALIZACAO: dict[int | str, dict[str, Any]] = {
    **_RESPOSTAS_PADRAO,
    401: {
        "description": "Token ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    },
    403: {
        "description": "Permissao operacional de materializacao requerida.",
        "content": {
            "application/json": {"example": {"detail": "Permissao de operacao de materializacao requerida."}}
        },
    },
}


def _obter_companhia_por_codigo_cvm_or_404(db: DbSession, codigo_cvm: int) -> Companhia:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return companhia


def _parse_metricas(metricas: str | None) -> list[str] | None:
    if metricas is None:
        return None
    return [item.strip() for item in metricas.split(",") if item.strip()]


def _progress_from_summary(summary: dict[str, Any] | None) -> AnaliseMaterializacaoProgress:
    progress = summary.get("progress") if isinstance(summary, dict) else None
    if not isinstance(progress, dict):
        progress = {}
    return AnaliseMaterializacaoProgress(
        total_knowledge_dates=progress.get("total_knowledge_dates"),
        processed_knowledge_dates=progress.get("processed_knowledge_dates"),
        current_known_from=progress.get("current_known_from"),
        progress_ratio=progress.get("progress_ratio"),
        context_revisions=progress.get("context_revisions"),
        fact_revisions=progress.get("fact_revisions"),
    )


def _elapsed_seconds(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    if started_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    ended_at = finished_at or datetime.now(UTC)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    return max(0, int((ended_at - started_at).total_seconds()))


def _estimate_finish(
    started_at: datetime | None,
    finished_at: datetime | None,
    progress: AnaliseMaterializacaoProgress,
) -> tuple[int | None, datetime | None]:
    if finished_at is not None or started_at is None or progress.progress_ratio is None:
        return None, None
    ratio = progress.progress_ratio
    if ratio <= 0 or ratio >= 1:
        return None, None
    elapsed = _elapsed_seconds(started_at, None)
    if elapsed is None or elapsed <= 0:
        return None, None
    total_estimated = elapsed / ratio
    remaining = max(0, int(total_estimated - elapsed))
    return remaining, datetime.now(UTC) + timedelta(seconds=remaining)


def _serializar_materializacao_execucao(execucao: AnaliseMaterializacaoExecucao) -> AnaliseMaterializacaoExecucaoResumo:
    progress = _progress_from_summary(execucao.summary)
    elapsed = _elapsed_seconds(execucao.started_at, execucao.finished_at)
    remaining, finish_at = _estimate_finish(execucao.started_at, execucao.finished_at, progress)
    summary = execucao.summary if isinstance(execucao.summary, dict) else {}
    return AnaliseMaterializacaoExecucaoResumo(
        id=str(execucao.id),
        codigo_cvm=execucao.codigo_cvm,
        escopo=cast(AnaliseEscopo, execucao.escopo),
        calculation_version=cast(Any, execucao.calculation_version),
        status=cast(Any, execucao.status),
        coverage_complete=execucao.coverage_complete,
        source=execucao.source,
        materialization_mode=cast(Any, execucao.materialization_mode),
        invalidated_from=execucao.invalidated_from,
        started_at=execucao.started_at,
        finished_at=execucao.finished_at,
        updated_at=execucao.updated_at,
        elapsed_seconds=elapsed,
        estimated_remaining_seconds=remaining,
        estimated_finish_at=finish_at,
        campanha_id=str(execucao.campanha_id) if execucao.campanha_id is not None else None,
        campanha_item_id=str(execucao.campanha_item_id) if execucao.campanha_item_id is not None else None,
        chunk_execucao_id=str(execucao.chunk_execucao_id) if execucao.chunk_execucao_id is not None else None,
        queue_name=execucao.queue_name,
        position_in_chunk=execucao.position_in_chunk,
        window_total_knowledge_dates=summary.get("window_total_knowledge_dates"),
        window_processed_knowledge_dates=summary.get("window_processed_knowledge_dates"),
        inserted_context_revisions=summary.get("inserted_context_revisions"),
        inserted_fact_revisions=summary.get("inserted_fact_revisions"),
        closed_context_revisions=summary.get("closed_context_revisions"),
        closed_fact_revisions=summary.get("closed_fact_revisions"),
        deleted_future_context_revisions=summary.get("deleted_future_context_revisions"),
        deleted_future_fact_revisions=summary.get("deleted_future_fact_revisions"),
        progress=progress,
    )


def _materializacao_task_count(
    payload: dict[str, Any] | None,
    *,
    scheduled: bool = False,
    task_names: set[str] | None = None,
) -> int:
    if not payload:
        return 0
    names = task_names or {_MATERIALIZACAO_TASK_NAME}
    total = 0
    for tasks in payload.values():
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if scheduled:
                request = task.get("request", {}) if isinstance(task, dict) else {}
                name = request.get("name")
            else:
                name = task.get("name") if isinstance(task, dict) else None
            if name in names:
                total += 1
    return total


def _queue_depth() -> int | None:
    try:
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            client = getattr(channel, "client", None)
            if client is None or not hasattr(client, "llen"):
                return None
            return int(client.llen(_settings.analise_materializacao_queue_name))
    except Exception:
        return None


def _campaign_progress_ratio(campanha: AnaliseMaterializacaoCampanha) -> float | None:
    counts = (campanha.summary or {}).get("counts", {}) if isinstance(campanha.summary, dict) else {}
    progress_ratio = counts.get("progress_ratio") if isinstance(counts, dict) else None
    return float(progress_ratio) if progress_ratio is not None else None


def _serializar_chunk(chunk: AnaliseMaterializacaoChunkExecucao) -> AnaliseMaterializacaoChunkExecucaoResumo:
    return AnaliseMaterializacaoChunkExecucaoResumo(
        chunk_execucao_id=str(chunk.id),
        campanha_id=str(chunk.campanha_id),
        status=cast(Any, chunk.status),
        lease_owner=chunk.lease_owner,
        lease_expires_at=chunk.lease_expires_at,
        heartbeat_at=chunk.heartbeat_at,
        item_count=chunk.item_count,
        processed_items=chunk.processed_items,
        success_items=chunk.success_items,
        failed_items=chunk.failed_items,
        started_at=chunk.started_at,
        finished_at=chunk.finished_at,
        updated_at=chunk.updated_at,
    )


def _serializar_campanha(db: DbSession, campanha: AnaliseMaterializacaoCampanha) -> AnaliseMaterializacaoCampanhaResumo:
    processed_items = campanha.success_items + campanha.failed_items + campanha.skipped_items
    progress_ratio = _campaign_progress_ratio(campanha)
    remaining = None
    active_chunk = db.scalar(
        select(AnaliseMaterializacaoChunkExecucao)
        .where(
            AnaliseMaterializacaoChunkExecucao.campanha_id == campanha.id,
            AnaliseMaterializacaoChunkExecucao.status.in_(("queued", "running")),
        )
        .order_by(AnaliseMaterializacaoChunkExecucao.created_at.desc())
        .limit(1)
    )
    stale_chunks = contar_chunks_stale_campanha(db, campanha.id)
    if progress_ratio is not None and campanha.started_at is not None and 0 < progress_ratio < 1:
        elapsed = _elapsed_seconds(campanha.started_at, None)
        if elapsed is not None and elapsed > 0:
            remaining = max(0, int((elapsed / progress_ratio) - elapsed))
    return AnaliseMaterializacaoCampanhaResumo(
        campanha_id=str(campanha.id),
        source=campanha.source,
        status=cast(Any, campanha.status),
        chunk_size=campanha.chunk_size,
        total_items=campanha.total_items,
        processed_items=processed_items,
        pending_items=campanha.pending_items,
        running_items=campanha.running_items,
        failed_items=campanha.failed_items,
        skipped_items=campanha.skipped_items,
        progress_ratio=progress_ratio,
        started_at=campanha.started_at,
        updated_at=campanha.updated_at,
        estimated_remaining_seconds=remaining,
        active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
        active_chunk_lease_expires_at=active_chunk.lease_expires_at if active_chunk is not None else None,
        stale_chunks=stale_chunks,
        wait_reason=(campanha.summary or {}).get("wait_reason") if isinstance(campanha.summary, dict) else None,
        recovery_state=(campanha.summary or {}).get("recovery_state") if isinstance(campanha.summary, dict) else None,
        last_recovery_check_at=(campanha.summary or {}).get("last_recovery_check_at") if isinstance(campanha.summary, dict) else None,
        last_recovery_action=(campanha.summary or {}).get("last_recovery_action") if isinstance(campanha.summary, dict) else None,
        last_recovery_reason_code=(campanha.summary or {}).get("last_recovery_reason_code") if isinstance(campanha.summary, dict) else None,
    )


def _serializar_item_preview(item: AnaliseMaterializacaoCampanhaItem) -> AnaliseMaterializacaoCampanhaItemPreview:
    return AnaliseMaterializacaoCampanhaItemPreview(
        item_id=str(item.id),
        codigo_cvm=item.codigo_cvm,
        escopo=cast(AnaliseEscopo, item.escopo),
        campanha_id=str(item.campanha_id),
        materialization_mode="incremental" if item.invalidated_from is not None else "full",
        invalidated_from=item.invalidated_from,
        chunk_execucao_id=str(item.chunk_execucao_id) if item.chunk_execucao_id is not None else None,
        status=item.status,
        started_at=item.started_at,
    )


def _serializar_gate(db: DbSession, controle: AnaliseMaterializacaoControle | None = None) -> AnaliseMaterializacaoGateSnapshot:
    gate = obter_estado_gate_materializacao(db)
    return AnaliseMaterializacaoGateSnapshot(
        status=gate.status,
        reason_code=gate.reason_code,
        gate_enabled=gate.gate_enabled,
        manual_control=gate.manual_control,
        manual_reason=gate.manual_reason,
        blocking_ingestions=gate.blocking_ingestions,
        pending_ingestions=gate.pending_ingestions,
        next_check_at=gate.next_check_at,
        blockers=[
            AnaliseMaterializacaoIngestionBlocker(
                source_type=item.source_type,
                execution_id=item.execution_id,
                run_id=item.run_id,
                year=item.year,
                status=item.status,
                phase=item.phase,
                started_at=item.started_at,
            )
            for item in gate.blockers
        ],
    )


@router.get(
    "/metricas",
    response_model=AnaliseMetricasCatalogoResposta,
    summary="Catalogo de Metricas Analiticas",
    description=(
        "Retorna o catálogo versionado de métricas analíticas, com identificadores estáveis, unidade, fórmula, "
        "contas CVM candidatas, estratégia de resolução e limitações metodológicas."
    ),
    operation_id="listarMetricasAnaliticas",
)
def listar_metricas_analiticas() -> AnaliseMetricasCatalogoResposta:
    return listar_metricas()


@router.get(
    "/materializacoes/monitoramento",
    response_model=AnaliseMaterializacaoMonitoramentoResposta,
    summary="Monitorar Materializacoes Analiticas",
    description=(
        "Retorna snapshot operacional das execuções, campanhas, itens e filas Celery da materialização analítica, "
        "incluindo contagem de tasks orquestradoras, tasks de chunk, profundidade de fila dedicada e previews "
        "dos itens pendentes/em andamento. Campanhas automáticas não incluem companhias com "
        "`situacao_registro=CANCELADA`; canceladas só aparecem se uma execução pontual tiver sido disparada com "
        "override explícito. O snapshot também expõe sinais específicos de self-healing, como campanhas pendentes "
        "recuperáveis, campanhas presas sem despacho inicial, último sweep automático persistido e tasks ativas do "
        "fluxo de recuperação de pendências."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="monitorarMaterializacoesAnaliticas",
)
def monitorar_materializacoes_analiticas(db: DbSession) -> AnaliseMaterializacaoMonitoramentoResposta:
    inspect = celery_app.control.inspect(timeout=1.0)
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}

    running = list(
        db.scalars(
            select(AnaliseMaterializacaoExecucao)
            .where(AnaliseMaterializacaoExecucao.status == "running")
            .order_by(AnaliseMaterializacaoExecucao.started_at.asc(), AnaliseMaterializacaoExecucao.created_at.asc())
        ).all()
    )
    now = datetime.now(UTC)
    stalled_ids = [
        str(execucao.id)
        for execucao in running
        if execucao.updated_at is not None and (now - execucao.updated_at).total_seconds() > _STALL_THRESHOLD_SECONDS
    ]
    stalled_incremental_ids = [
        str(execucao.id)
        for execucao in running
        if execucao.materialization_mode == "incremental"
        and execucao.updated_at is not None
        and (now - execucao.updated_at).total_seconds() > _STALL_THRESHOLD_SECONDS
    ]
    running_full_executions = sum(1 for execucao in running if execucao.materialization_mode == "full")
    running_incremental_executions = sum(1 for execucao in running if execucao.materialization_mode == "incremental")
    lowest_running_invalidated_from = min(
        (execucao.invalidated_from for execucao in running if execucao.invalidated_from is not None),
        default=None,
    )
    oldest_started_at = running[0].started_at if running else None
    longest_elapsed = _elapsed_seconds(oldest_started_at, None) if oldest_started_at else None
    controle = obter_controle_materializacao(db)
    campanhas = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanha)
            .where(AnaliseMaterializacaoCampanha.status.in_(("pending", "running", "partial", "failed")))
            .order_by(AnaliseMaterializacaoCampanha.created_at.desc())
            .limit(10)
        ).all()
    )
    campanhas_resumo = [_serializar_campanha(db, campanha) for campanha in campanhas]
    campaign_counts = db.execute(
        select(
            func.sum(case((AnaliseMaterializacaoCampanha.status == "pending", 1), else_=0)),
            func.sum(case((AnaliseMaterializacaoCampanha.status == "running", 1), else_=0)),
            func.sum(AnaliseMaterializacaoCampanha.pending_items),
            func.sum(AnaliseMaterializacaoCampanha.running_items),
            func.sum(AnaliseMaterializacaoCampanha.success_items),
            func.sum(AnaliseMaterializacaoCampanha.failed_items),
            func.sum(AnaliseMaterializacaoCampanha.skipped_items),
        )
    ).one()
    (
        pending_campaigns,
        running_campaigns,
        pending_items,
        running_items,
        success_items,
        failed_items,
        skipped_items,
    ) = campaign_counts
    chunk_counts = db.execute(
        select(
            func.sum(case((AnaliseMaterializacaoChunkExecucao.status == "queued", 1), else_=0)),
            func.sum(case((AnaliseMaterializacaoChunkExecucao.status == "running", 1), else_=0)),
            func.sum(case((AnaliseMaterializacaoChunkExecucao.status == "stale", 1), else_=0)),
        )
    ).one()
    queued_chunks, running_chunks, stale_chunks = chunk_counts
    waiting_for_gate_campaigns = sum(
        1
        for summary in db.scalars(
            select(AnaliseMaterializacaoCampanha.summary).where(AnaliseMaterializacaoCampanha.status == "pending")
        ).all()
        if isinstance(summary, dict) and summary.get("wait_reason") in {"INGESTION_ACTIVE", "MANUAL_PAUSE"}
    )
    recovering_campaigns = sum(
        1
        for summary in db.scalars(
            select(AnaliseMaterializacaoCampanha.summary).where(AnaliseMaterializacaoCampanha.status == "pending")
        ).all()
        if isinstance(summary, dict) and summary.get("wait_reason") in {"STALE_CHUNK_RECOVERED", "STALE_CHUNK_DETECTED"}
    )
    pending_campaign_rows = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanha)
            .where(AnaliseMaterializacaoCampanha.status == "pending")
            .order_by(AnaliseMaterializacaoCampanha.created_at.asc())
        ).all()
    )
    recoverable_campaign_ids: list[str] = []
    undispatched_campaigns: list[AnaliseMaterializacaoCampanha] = []
    for campanha in pending_campaign_rows:
        active_chunk = obter_chunk_ativo_campanha(db, campanha.id)
        stale_chunk_count = len(obter_chunks_stale_ativos(db, campanha_id=campanha.id)) + contar_chunks_stale_campanha(db, campanha.id)
        wait_reason = (campanha.summary or {}).get("wait_reason") if isinstance(campanha.summary, dict) else None
        running_execucoes = int(
            db.scalar(
                select(func.count(AnaliseMaterializacaoExecucao.id)).where(
                    AnaliseMaterializacaoExecucao.campanha_id == campanha.id,
                    AnaliseMaterializacaoExecucao.status == "running",
                )
            )
            or 0
        )
        age_seconds = _elapsed_seconds(campanha.created_at, None)
        if stale_chunk_count > 0:
            recoverable_campaign_ids.append(str(campanha.id))
        elif (
            campanha.pending_items > 0
            and active_chunk is None
            and running_execucoes == 0
            and campanha.running_items == 0
            and wait_reason not in {"INGESTION_ACTIVE", "MANUAL_PAUSE", "MAX_ACTIVE_CAMPAIGNS_REACHED"}
            and age_seconds is not None
            and age_seconds >= _settings.analise_materializacao_pending_recovery_min_age_seconds
        ):
            recoverable_campaign_ids.append(str(campanha.id))
            undispatched_campaigns.append(campanha)
    oldest_undispatched_campaign = undispatched_campaigns[0] if undispatched_campaigns else None
    last_pending_recovery = (
        ((controle.summary or {}).get("pending_recovery", {}))
        if isinstance(controle.summary, dict)
        else {}
    )
    stale_item_count = int(
        db.scalar(
            select(func.count(AnaliseMaterializacaoCampanhaItem.id)).where(
                AnaliseMaterializacaoCampanhaItem.chunk_execucao_id.in_(
                    select(AnaliseMaterializacaoChunkExecucao.id).where(
                        AnaliseMaterializacaoChunkExecucao.status == "stale"
                    )
                )
            )
        )
        or 0
    )
    stale_chunk_preview = list(
        db.scalars(
            select(AnaliseMaterializacaoChunkExecucao)
            .where(AnaliseMaterializacaoChunkExecucao.status == "stale")
            .order_by(AnaliseMaterializacaoChunkExecucao.updated_at.desc(), AnaliseMaterializacaoChunkExecucao.created_at.desc())
            .limit(10)
        ).all()
    )
    running_items_preview = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanhaItem)
            .where(AnaliseMaterializacaoCampanhaItem.status == "running")
            .order_by(AnaliseMaterializacaoCampanhaItem.updated_at.desc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
            .limit(10)
        ).all()
    )
    pending_items_preview = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanhaItem)
            .where(AnaliseMaterializacaoCampanhaItem.status == "pending")
            .order_by(AnaliseMaterializacaoCampanhaItem.created_at.asc(), AnaliseMaterializacaoCampanhaItem.ordem.asc())
            .limit(10)
        ).all()
    )

    return AnaliseMaterializacaoMonitoramentoResposta(
        as_of=now,
        fila=AnaliseMaterializacaoFilaSnapshot(
            workers_reporting=len(set(active) | set(reserved) | set(scheduled)),
            materialization_active_tasks=_materializacao_task_count(
                active,
                task_names={
                    _MATERIALIZACAO_TASK_NAME,
                    _MATERIALIZACAO_CAMPANHA_TASK_NAME,
                    _MATERIALIZACAO_CHUNK_TASK_NAME,
                    _MATERIALIZACAO_RECOVERY_TASK_NAME,
                    _MATERIALIZACAO_PENDING_RECOVERY_TASK_NAME,
                },
            ),
            materialization_reserved_tasks=_materializacao_task_count(
                reserved,
                task_names={
                    _MATERIALIZACAO_TASK_NAME,
                    _MATERIALIZACAO_CAMPANHA_TASK_NAME,
                    _MATERIALIZACAO_CHUNK_TASK_NAME,
                    _MATERIALIZACAO_RECOVERY_TASK_NAME,
                    _MATERIALIZACAO_PENDING_RECOVERY_TASK_NAME,
                },
            ),
            materialization_scheduled_tasks=_materializacao_task_count(
                scheduled,
                scheduled=True,
                task_names={
                    _MATERIALIZACAO_TASK_NAME,
                    _MATERIALIZACAO_CAMPANHA_TASK_NAME,
                    _MATERIALIZACAO_CHUNK_TASK_NAME,
                    _MATERIALIZACAO_RECOVERY_TASK_NAME,
                    _MATERIALIZACAO_PENDING_RECOVERY_TASK_NAME,
                },
            ),
            materialization_orchestrator_active_tasks=_materializacao_task_count(active, task_names={_MATERIALIZACAO_CAMPANHA_TASK_NAME}),
            materialization_chunk_active_tasks=_materializacao_task_count(active, task_names={_MATERIALIZACAO_CHUNK_TASK_NAME}),
            materialization_queue_depth=_queue_depth(),
        ),
        gate=_serializar_gate(db, controle),
        running_executions=len(running),
        running_full_executions=running_full_executions,
        running_incremental_executions=running_incremental_executions,
        lowest_running_invalidated_from=lowest_running_invalidated_from,
        pending_campaigns=int(pending_campaigns or 0),
        running_campaigns=int(running_campaigns or 0),
        waiting_for_gate_campaigns=int(waiting_for_gate_campaigns or 0),
        recovering_campaigns=int(recovering_campaigns or 0),
        recoverable_pending_campaigns=len(recoverable_campaign_ids),
        undispatched_stuck_campaigns=len(undispatched_campaigns),
        oldest_undispatched_campaign_created_at=oldest_undispatched_campaign.created_at if oldest_undispatched_campaign is not None else None,
        oldest_undispatched_campaign_elapsed_seconds=_elapsed_seconds(oldest_undispatched_campaign.created_at, None) if oldest_undispatched_campaign is not None else None,
        recoverable_campaign_ids=recoverable_campaign_ids[:10],
        last_pending_recovery_sweep_at=last_pending_recovery.get("triggered_at"),
        last_pending_recovery_sweep_summary=last_pending_recovery if isinstance(last_pending_recovery, dict) else {},
        pending_items=int(pending_items or 0),
        running_items=int(running_items or 0),
        success_items=int(success_items or 0),
        failed_items=int(failed_items or 0),
        skipped_items=int(skipped_items or 0),
        queued_chunks=int(queued_chunks or 0),
        running_chunks=int(running_chunks or 0),
        stale_chunks=int(stale_chunks or 0),
        stale_item_count=stale_item_count,
        oldest_running_started_at=oldest_started_at,
        longest_running_elapsed_seconds=longest_elapsed,
        stalled_threshold_seconds=_STALL_THRESHOLD_SECONDS,
        stalled_execution_ids=stalled_ids,
        stalled_incremental_execution_ids=stalled_incremental_ids,
        pending_recovery_active_tasks=_materializacao_task_count(active, task_names={_MATERIALIZACAO_PENDING_RECOVERY_TASK_NAME}),
        running_execution_previews=[_serializar_materializacao_execucao(item) for item in running[:10]],
        campaigns=campanhas_resumo,
        stale_chunk_preview=[AnaliseMaterializacaoChunkExecucaoPreview(**_serializar_chunk(chunk).model_dump()) for chunk in stale_chunk_preview],
        running_items_preview=[_serializar_item_preview(item) for item in running_items_preview],
        pending_items_preview=[_serializar_item_preview(item) for item in pending_items_preview],
    )


@router.get(
    "/materializacoes/controle",
    response_model=AnaliseMaterializacaoControleResposta,
    summary="Consultar Controle de Materializacao Analitica",
    description="Retorna o estado atual do gate de admissão da materialização analítica e o modo manual persistido.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="consultarControleMaterializacaoAnalitica",
)
def consultar_controle_materializacao_analitica(db: DbSession) -> AnaliseMaterializacaoControleResposta:
    controle = obter_controle_materializacao(db)
    return AnaliseMaterializacaoControleResposta(
        gate=_serializar_gate(db, controle),
        updated_at=controle.updated_at,
    )


@router.post(
    "/materializacoes/controle/pause",
    response_model=AnaliseMaterializacaoControleResposta,
    summary="Pausar Materializacao Analitica",
    description="Ativa pausa manual do gate de materialização. Novos chunks deixam de iniciar até o resume.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="pausarControleMaterializacaoAnalitica",
)
def pausar_controle_materializacao_analitica(
    db: DbSession,
    reason: Annotated[str | None, Query(description="Motivo textual opcional para a pausa manual.")] = None,
) -> AnaliseMaterializacaoControleResposta:
    controle = pausar_controle_materializacao(db, reason=reason)
    return AnaliseMaterializacaoControleResposta(
        gate=_serializar_gate(db, controle),
        updated_at=controle.updated_at,
    )


@router.post(
    "/materializacoes/controle/resume",
    response_model=AnaliseMaterializacaoControleResposta,
    summary="Retomar Materializacao Analitica",
    description="Remove a pausa manual e devolve o gate ao modo automático baseado no estado de ingestão.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="retomarControleMaterializacaoAnalitica",
)
def retomar_controle_materializacao_analitica(db: DbSession) -> AnaliseMaterializacaoControleResposta:
    controle = retomar_controle_materializacao(db)
    return AnaliseMaterializacaoControleResposta(
        gate=_serializar_gate(db, controle),
        updated_at=controle.updated_at,
    )


@router.post(
    "/materializacoes/recuperar-stale",
    response_model=AnaliseMaterializacaoRecuperacaoResposta,
    summary="Recuperar Chunks Stale de Materializacao",
    description="Executa recuperação imediata de chunks stale de materialização e devolve itens inacabados para pending.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="recuperarMaterializacaoStale",
)
def recuperar_materializacao_stale_analitica(
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> AnaliseMaterializacaoRecuperacaoResposta:
    resultado = recuperar_chunks_materializacao_stale(db)
    from app.worker.tasks import materializar_analise_campanha_task
    for c_id in resultado.affected_campaigns:
        materializar_analise_campanha_task.delay(c_id)
    return AnaliseMaterializacaoRecuperacaoResposta(
        recovered_chunks=resultado.recovered_chunks,
        recovered_items=resultado.recovered_items,
        affected_campaigns=list(resultado.affected_campaigns),
        chunk_ids=list(resultado.chunk_ids),
    )


@router.post(
    "/materializacoes/campanhas/{campanha_id}/recuperar",
    response_model=AnaliseMaterializacaoRecuperacaoResposta,
    summary="Recuperar Chunks Stale de uma Campanha",
    description="Executa recuperação imediata dos chunks stale associados a uma campanha específica.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="recuperarMaterializacaoCampanha",
)
def recuperar_materializacao_campanha_analitica(
    campanha_id: str,
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> AnaliseMaterializacaoRecuperacaoResposta:
    try:
        campanha_uuid = UUID(campanha_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="campanha_id invalido.") from exc
    resultado = recuperar_chunks_materializacao_stale(db, campanha_id=campanha_uuid)
    from app.worker.tasks import materializar_analise_campanha_task
    for c_id in resultado.affected_campaigns:
        materializar_analise_campanha_task.delay(c_id)
    return AnaliseMaterializacaoRecuperacaoResposta(
        recovered_chunks=resultado.recovered_chunks,
        recovered_items=resultado.recovered_items,
        affected_campaigns=list(resultado.affected_campaigns),
        chunk_ids=list(resultado.chunk_ids),
    )


@router.post(
    "/materializacoes/campanhas/{campanha_id}/reativar",
    response_model=AnaliseMaterializacaoReativacaoResposta,
    summary="Reativar Campanha de Materializacao",
    description=(
        "Classifica uma campanha pendente da materialização analítica e executa reativação operacional limitada. "
        "A chamada exige token de sistema, usuario admin ou usuario com `pode_operar_materializacao=true`. "
        "A operação pode reenfileirar uma campanha presa sem chunk inicial ou recuperar chunks stale já detectados, "
        "mas não ignora gate vermelho nem saturação de slots. A resposta sempre traz `status`, `reason_code`, "
        "`affected_campaigns`, `requeued_campaigns`, `recovered_chunks`, `recovered_items`, "
        "`dispatcher_enqueued` e `triggered_at`, permitindo que o cliente diferencie retry efetivo de `noop` "
        "operacional."
    ),
    responses=_RESPOSTAS_OPERACAO_MATERIALIZACAO,
    operation_id="reativarMaterializacaoCampanha",
)
def reativar_materializacao_campanha_analitica(
    campanha_id: str,
    db: DbSession,
    _: Annotated[None, Depends(exigir_operador_materializacao_api)],
) -> AnaliseMaterializacaoReativacaoResposta:
    try:
        campanha_uuid = UUID(campanha_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="campanha_id invalido.") from exc
    resultado = reativar_materializacao_campanha(db, campanha_uuid)
    from app.worker.tasks import materializar_analise_campanha_task
    for c_id in resultado.requeued_campaigns:
        materializar_analise_campanha_task.delay(c_id)
    return AnaliseMaterializacaoReativacaoResposta(
        status=cast(Any, resultado.status),
        reason_code=cast(Any, resultado.reason_code),
        affected_campaigns=list(resultado.affected_campaigns),
        requeued_campaigns=list(resultado.requeued_campaigns),
        recovered_chunks=resultado.recovered_chunks,
        recovered_items=resultado.recovered_items,
        dispatcher_enqueued=resultado.dispatcher_enqueued,
        triggered_at=resultado.triggered_at,
    )


@router.post(
    "/materializacoes/recuperacao/trigger",
    response_model=AnaliseMaterializacaoReativacaoSweepResposta,
    summary="Disparar Sweep de Recuperacao de Materializacao",
    description=(
        "Executa uma varredura operacional limitada sobre campanhas pendentes da materialização analítica, "
        "exigindo token de sistema, usuario admin ou usuario com `pode_operar_materializacao=true`. "
        "reativando apenas campanhas elegíveis para self-healing e respeitando os limites configurados de batch. "
        "O sweep não força bypass de gate nem de concorrência; ele apenas recupera `STALE_CHUNK` e reenfileira "
        "`PENDING_UNDISPATCHED` maduros o suficiente para reativação automática."
    ),
    responses=_RESPOSTAS_OPERACAO_MATERIALIZACAO,
    operation_id="triggerMaterializacaoRecoverySweep",
)
def trigger_recuperacao_materializacao_analitica(
    db: DbSession,
    _: Annotated[None, Depends(exigir_operador_materializacao_api)],
) -> AnaliseMaterializacaoReativacaoSweepResposta:
    resultado = recuperar_materializacao_pendente(db)
    from app.worker.tasks import materializar_analise_campanha_task
    for campanha_id in resultado.requeued_campaigns:
        materializar_analise_campanha_task.delay(campanha_id)
    return AnaliseMaterializacaoReativacaoSweepResposta(
        status=cast(Any, resultado.status),
        reason_code=cast(Any, resultado.reason_code),
        affected_campaigns=list(resultado.affected_campaigns),
        requeued_campaigns=list(resultado.requeued_campaigns),
        recovered_chunks=resultado.recovered_chunks,
        recovered_items=resultado.recovered_items,
        dispatcher_enqueued=resultado.dispatcher_enqueued,
        triggered_at=resultado.triggered_at,
        scanned_campaigns=resultado.scanned_campaigns,
        recoverable_campaigns=resultado.recoverable_campaigns,
    )


@router.get(
    "/materializacoes",
    response_model=AnaliseMaterializacaoExecucoesListaResposta,
    summary="Listar Materializacoes Analiticas",
    description=(
        "Lista execuções de materialização analítica com status, progresso, tempo decorrido, estimativa de conclusão "
        "e vínculo opcional com campanhas e itens de campanha. Campanhas automáticas e fluxos padrão excluem "
        "companhias com `situacao_registro=CANCELADA`; execuções pontuais só processam canceladas mediante "
        "override explícito no disparo operacional."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarMaterializacoesAnaliticas",
)
def listar_materializacoes_analiticas(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    status: Annotated[str | None, Query(description="Filtra por status: `running`, `success` ou `failed`.")] = None,
    codigo_cvm: Annotated[int | None, Query(description="Filtra por código CVM da companhia.")] = None,
    escopo: Annotated[AnaliseEscopo | None, Query(description="Filtra por escopo societário.")] = None,
    source: Annotated[str | None, Query(description="Filtra por origem do disparo da materialização.")] = None,
    campanha_id: Annotated[str | None, Query(description="Filtra por identificador da campanha de materialização.")] = None,
) -> AnaliseMaterializacaoExecucoesListaResposta:
    filters = []
    if status is not None:
        filters.append(AnaliseMaterializacaoExecucao.status == status)
    if codigo_cvm is not None:
        filters.append(AnaliseMaterializacaoExecucao.codigo_cvm == codigo_cvm)
    if escopo is not None:
        filters.append(AnaliseMaterializacaoExecucao.escopo == escopo)
    if source is not None:
        filters.append(AnaliseMaterializacaoExecucao.source == source)
    if campanha_id is not None:
        try:
            filters.append(AnaliseMaterializacaoExecucao.campanha_id == UUID(campanha_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="campanha_id invalido.") from exc

    stmt = select(AnaliseMaterializacaoExecucao)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(
        AnaliseMaterializacaoExecucao.started_at.desc().nullslast(),
        AnaliseMaterializacaoExecucao.created_at.desc(),
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    execucoes = list(db.scalars(stmt.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).all())

    resumo_stmt = select(
        func.count(AnaliseMaterializacaoExecucao.id),
        func.sum(case((AnaliseMaterializacaoExecucao.status == "running", 1), else_=0)),
        func.sum(case((AnaliseMaterializacaoExecucao.status == "success", 1), else_=0)),
        func.sum(case((AnaliseMaterializacaoExecucao.status == "failed", 1), else_=0)),
    )
    if filters:
        resumo_stmt = resumo_stmt.where(*filters)
    total_count, running_count, success_count, failed_count = db.execute(resumo_stmt).one()

    return AnaliseMaterializacaoExecucoesListaResposta(
        dados=[_serializar_materializacao_execucao(item) for item in execucoes],
        paginacao=Paginacao(
            pagina=paginacao.pagina,
            tamanho_pagina=paginacao.tamanho_pagina,
            total=total,
        ),
        resumo=AnaliseMaterializacaoExecucoesResumo(
            total=int(total_count or 0),
            running=int(running_count or 0),
            success=int(success_count or 0),
            failed=int(failed_count or 0),
        ),
    )


@router.get(
    "/materializacoes/{execucao_id}",
    response_model=AnaliseMaterializacaoExecucaoDetalhe,
    summary="Detalhar Materializacao Analitica",
    description=(
        "Retorna detalhe completo de uma execução de materialização analítica específica, incluindo resumo bruto "
        "persistido e vínculos opcionais com campanha, item e posição em chunk. Execuções disparadas sem override "
        "explícito podem concluir como skip operacional quando a companhia estiver com `situacao_registro=CANCELADA`."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="detalharMaterializacaoAnalitica",
)
def detalhar_materializacao_analitica(execucao_id: str, db: DbSession) -> AnaliseMaterializacaoExecucaoDetalhe:
    try:
        execucao_uuid = UUID(execucao_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Execucao de materializacao nao encontrada.") from exc
    execucao = db.get(AnaliseMaterializacaoExecucao, execucao_uuid)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao de materializacao nao encontrada.")
    resumo = _serializar_materializacao_execucao(execucao)
    return AnaliseMaterializacaoExecucaoDetalhe(**resumo.model_dump(), summary=execucao.summary or {})


@router.get(
    "/companhias/{codigo_cvm}",
    response_model=AnaliseManifestoResposta,
    summary="Manifesto Analitico da Companhia",
    description="Retorna contexto padrão, períodos disponíveis, qualidade e links para os blocos analíticos da companhia.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseManifesto",
)
def obter_analise_manifesto(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> AnaliseManifestoResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_manifesto(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)


@router.get(
    "/companhias/{codigo_cvm}/series",
    response_model=AnaliseSeriesResposta,
    summary="Series Analiticas Normalizadas",
    description="Retorna observações analíticas normalizadas por métrica, período, unidade, formulário, versão e evidência.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseSeries",
)
def obter_analise_series(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo a retornar quando `periodicidade=annual&base_periodo=fy`.", ge=1, le=20)] = 5,
) -> AnaliseSeriesResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_series(
        db,
        companhia,
        metricas=_parse_metricas(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        horizonte_anos=horizonte_anos,
    )


@router.get(
    "/companhias/{codigo_cvm}/comparacoes",
    response_model=AnaliseComparacoesResposta,
    summary="Comparacoes Analiticas Prontas",
    description="Retorna YoY, QoQ, CAGR, análise vertical e base 100, com motivo explícito quando o cálculo não estiver disponível.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseComparacoes",
)
def obter_analise_comparacoes(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo a considerar quando `periodicidade=annual&base_periodo=fy`.", ge=1, le=20)] = 5,
) -> AnaliseComparacoesResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_comparacoes(
        db,
        companhia,
        metricas=_parse_metricas(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        horizonte_anos=horizonte_anos,
    )


@router.get(
    "/companhias/{codigo_cvm}/qualidade",
    response_model=AnaliseQualidadeResposta,
    summary="Qualidade Analitica",
    description="Executa verificações de completude, comparabilidade, consistência e reapresentações no contexto analítico atual.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseQualidade",
)
def obter_analise_qualidade(
    codigo_cvm: int,
    db: DbSession,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade do diagnóstico: `annual` ou `quarterly`.")] = "annual",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> AnaliseQualidadeResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_qualidade(db, companhia, periodicidade=periodicidade, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)


@router.get(
    "/companhias/{codigo_cvm}/sinais",
    response_model=AnaliseSinaisResposta,
    summary="Sinais Deterministicos",
    description="Avalia regras determinísticas do backend e retorna threshold, observado e evidências para cada sinal disparado.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseSinais",
)
def obter_analise_sinais(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> AnaliseSinaisResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_sinais(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)


@router.get(
    "/companhias/{codigo_cvm}/eventos",
    response_model=AnaliseEventosResposta,
    summary="Timeline de Eventos Analiticos",
    description="Retorna timeline unificada de IPE, reapresentações financeiras, alterações de capital e negociações relevantes.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseEventos",
)
def obter_analise_eventos(codigo_cvm: int, db: DbSession) -> AnaliseEventosResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_eventos(db, companhia)


@router.get(
    "/companhias/{codigo_cvm}/governanca",
    response_model=AnaliseGovernancaResposta,
    summary="Governanca Analitica Temporal",
    description="Retorna observações temporais anuais de governança com recorte `as_of`.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseGovernanca",
)
def obter_analise_governanca(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário considerado.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo a retornar.", ge=1, le=20)] = 5,
) -> AnaliseGovernancaResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_governanca(db, companhia, as_of=date.fromisoformat(as_of) if as_of else None, horizonte_anos=horizonte_anos, scope=escopo)


@router.get(
    "/companhias/{codigo_cvm}/pessoas",
    response_model=AnalisePessoasResposta,
    summary="Pessoas Analitico Temporal",
    description="Retorna observações temporais anuais de pessoas e remuneração com recorte `as_of`.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnalisePessoas",
)
def obter_analise_pessoas(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário considerado.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo a retornar.", ge=1, le=20)] = 5,
) -> AnalisePessoasResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_pessoas(db, companhia, as_of=date.fromisoformat(as_of) if as_of else None, horizonte_anos=horizonte_anos, scope=escopo)


@router.get(
    "/companhias/{codigo_cvm}/brief",
    response_model=AnaliseBriefResposta,
    summary="Brief Analitico da Companhia",
    description="Retorna um pacote curado com trimestre atual, trimestre anterior, comparável anual e sinais principais.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseBrief",
)
def obter_analise_brief(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV opcional de métricas a priorizar no brief.")] = None,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário considerado.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    incluir_eventos: Annotated[bool, Query(description="Indica se o brief deve incluir os eventos recentes.")] = True,
) -> AnaliseBriefResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_brief(
        db,
        companhia,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        metricas=_parse_metricas(metricas),
        incluir_eventos=incluir_eventos,
    )


@router.get(
    "/companhias/{codigo_cvm}/restatements",
    response_model=AnaliseRestatementsResposta,
    summary="Historico de Reapresentacoes",
    description="Compara versões consecutivas de DFP e ITR e informa as contas alteradas e o impacto absoluto/relativo.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseRestatements",
)
def obter_analise_restatements(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> AnaliseRestatementsResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_restatements(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)
