from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select

from app.api.auth import exigir_admin_api, exigir_operador_materializacao_api
from app.api.deps import DbSession, PaginacaoQuery
from app.core.config import get_settings
from app.models.analise import (
    AnaliseContextoRevision,
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
    AnaliseCoverageResposta,
    AnaliseEscopo,
    AnaliseEventosResposta,
    AnaliseGovernancaResposta,
    AnaliseManifestoResposta,
    AnaliseMaterializacaoAnoStatus,
    AnaliseMaterializacaoCampanhaItemPreview,
    AnaliseMaterializacaoCampanhaResumo,
    AnaliseMaterializacaoChunkExecucaoPreview,
    AnaliseMaterializacaoChunkExecucaoResumo,
    AnaliseMaterializacaoCompanhiaStatusResposta,
    AnaliseMaterializacaoControleResposta,
    AnaliseMaterializacaoExecucaoDetalhe,
    AnaliseMaterializacaoExecucaoResumo,
    AnaliseMaterializacaoExecucoesListaResposta,
    AnaliseMaterializacaoExecucoesResumo,
    AnaliseMaterializacaoFilaSnapshot,
    AnaliseMaterializacaoGateSnapshot,
    AnaliseMaterializacaoIngestionBlocker,
    AnaliseMaterializacaoMonitoramentoResposta,
    AnaliseMaterializacaoPeriodoStatus,
    AnaliseMaterializacaoProgress,
    AnaliseMaterializacaoReativacaoResposta,
    AnaliseMaterializacaoReativacaoSweepResposta,
    AnaliseMaterializacaoRecuperacaoResposta,
    AnaliseMetricasCatalogoResposta,
    AnalisePeriodicidade,
    AnalisePessoasResposta,
    AnaliseQualidadeResposta,
    AnaliseRestatementsResposta,
    AnaliseSeriesDiagnosticoResposta,
    AnaliseSeriesResposta,
    AnaliseSinaisResposta,
)
from app.schemas.comum import Paginacao
from app.services.analise import (
    CALCULATION_VERSION,
    campanha_tem_requeue_em_transito,
    contar_chunks_stale_campanha,
    listar_chunks_ativos_campanha,
    listar_metricas,
    obter_brief,
    obter_chunk_ativo_campanha,
    obter_chunks_stale_ativos,
    obter_comparacoes,
    obter_controle_materializacao,
    obter_coverage,
    obter_estado_gate_materializacao,
    obter_eventos,
    obter_governanca,
    obter_manifesto,
    obter_pessoas,
    obter_qualidade,
    obter_restatements,
    obter_series,
    obter_series_diagnostico,
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

_RESPOSTAS_ADMIN_OPERACAO_MATERIALIZACAO: dict[int | str, dict[str, Any]] = {
    **_RESPOSTAS_PADRAO,
    401: {
        "description": "Token ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    },
    403: {
        "description": "Permissao administrativa requerida.",
        "content": {"application/json": {"example": {"detail": "Permissao administrativa requerida."}}},
    },
}

_DESCRICAO_RECUPERAR_STALE_GERAL = (
    "Executa a recuperacao administrativa imediata de chunks stale em toda a fila de materializacao. "
    "Use este endpoint quando o operador administrativo precisar forcar a limpeza tecnica de chunks com lease "
    "expirado sem depender da classificacao por campanha. A operacao devolve itens inacabados para `pending`, "
    "marca as execucoes de chunk recuperadas como `stale` e reenfileira as campanhas afetadas. "
    "Este endpoint e de baixo nivel e existe para operacao administrativa; para usuarios delegados e fluxos de UI, "
    "prefira `POST /analise/materializacoes/recuperacao/trigger` ou "
    "`POST /analise/materializacoes/campanhas/{campanha_id}/reativar`."
)

_DESCRICAO_RECUPERAR_STALE_CAMPANHA = (
    "Executa a mesma recuperacao administrativa de chunks stale, mas limitada a uma campanha especifica. "
    "Use quando o operador administrativo ja sabe qual campanha esta afetada e precisa limpar apenas esse escopo. "
    "O endpoint nao reclassifica o estado logico da campanha alem da recuperacao tecnica do chunk. "
    "Para o fluxo operacional suportado para API users, prefira `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`."
)

_DESCRICAO_REATIVAR_CAMPANHA = (
    "Classifica uma campanha pendente da materializacao analitica e executa a reativacao operacional suportada "
    "para API users. Use este endpoint quando a UI ja conhece a `campanha_id` e quer tentar destravar apenas uma "
    "campanha especifica. O endpoint e idempotente do ponto de vista operacional: ele pode recuperar chunks stale "
    "ativos, reenfileirar uma campanha `PENDING_UNDISPATCHED` ou devolver `noop` com motivo objetivo quando a "
    "campanha estiver bloqueada por gate, slot, chunk vivo ou ausencia real de trabalho pendente. "
    "Quando a reativacao gera reenfileiramento, o backend registra a campanha como `requeued` e o monitoramento "
    "deixa de contabiliza-la em `recoverable_pending_campaigns` durante a janela curta de propagacao do retry."
)

_DESCRICAO_TRIGGER_RECUPERACAO = (
    "Executa um sweep operacional limitado sobre campanhas pendentes para self-healing delegado. Use este "
    "endpoint quando a UI nao sabe qual campanha esta presa, ou quando o operador quer pedir ao backend para "
    "varrer um lote limitado de campanhas `pending` e recuperar apenas as elegiveis naquele instante. "
    "O sweep respeita gate, concorrencia e limites configurados de batch; ele nao faz bypass de protecoes nem "
    "requeue irrestrito. O resultado traz contadores agregados e a lista das campanhas afetadas para auditoria."
)


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


def _stale_chunk_monitor_ids_subquery() -> Any:
    return (
        select(AnaliseMaterializacaoChunkExecucao.id)
        .join(
            AnaliseMaterializacaoCampanhaItem,
            AnaliseMaterializacaoCampanhaItem.chunk_execucao_id == AnaliseMaterializacaoChunkExecucao.id,
        )
        .join(
            AnaliseMaterializacaoCampanha,
            AnaliseMaterializacaoCampanha.id == AnaliseMaterializacaoChunkExecucao.campanha_id,
        )
        .where(
            AnaliseMaterializacaoChunkExecucao.status == "stale",
            AnaliseMaterializacaoCampanha.status.in_(("pending", "running")),
            AnaliseMaterializacaoCampanhaItem.status.in_(("pending", "running")),
        )
        .group_by(AnaliseMaterializacaoChunkExecucao.id)
        .subquery()
    )


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
    active_chunks = listar_chunks_ativos_campanha(db, campanha.id, limit=5)
    active_chunk = active_chunks[0] if active_chunks else None
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
        active_chunks=len(active_chunks),
        active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
        active_chunk_lease_expires_at=active_chunk.lease_expires_at if active_chunk is not None else None,
        active_chunk_ids_preview=[str(chunk.id) for chunk in active_chunks],
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


def _materializacao_ano_status_from_execucao(
    *,
    ano: int,
    escopo: AnaliseEscopo,
    execucao: AnaliseMaterializacaoExecucao,
) -> AnaliseMaterializacaoAnoStatus:
    return AnaliseMaterializacaoAnoStatus(
        ano=ano,
        status=execucao.status,
        escopo=escopo,
        coverage_complete=execucao.coverage_complete,
        materialized_at=execucao.finished_at if execucao.status == "success" else None,
        started_at=execucao.started_at,
        finished_at=execucao.finished_at,
        updated_at=execucao.updated_at,
        execution_id=str(execucao.id),
        materialization_execution_id=str(execucao.id),
        calculation_version=execucao.calculation_version,
        source=execucao.source,
        materialization_mode=execucao.materialization_mode,
        message=None,
    )


def _materializacao_ano_status_from_item(
    *,
    ano: int,
    escopo: AnaliseEscopo,
    item: AnaliseMaterializacaoCampanhaItem,
) -> AnaliseMaterializacaoAnoStatus:
    status = "queued" if item.status == "pending" and item.chunk_execucao_id is not None else item.status
    return AnaliseMaterializacaoAnoStatus(
        ano=ano,
        status=status,
        escopo=escopo,
        coverage_complete=None,
        materialized_at=None,
        started_at=item.started_at,
        finished_at=item.finished_at,
        updated_at=item.updated_at,
        execution_id=str(item.materializacao_execucao_id) if item.materializacao_execucao_id is not None else None,
        materialization_execution_id=str(item.materializacao_execucao_id) if item.materializacao_execucao_id is not None else None,
        calculation_version=CALCULATION_VERSION,
        source=None,
        materialization_mode="incremental" if item.invalidated_from is not None else "full",
        message=item.last_error,
    )


def _anos_from_context_revision(revision: AnaliseContextoRevision | None) -> list[int]:
    if revision is None:
        return []
    anos: set[int] = set()
    for periodo in revision.periodos_disponiveis or []:
        if not isinstance(periodo, dict):
            continue
        if periodo.get("periodicidade") != "annual" or periodo.get("base_periodo") != "fy":
            continue
        fiscal_year = periodo.get("fiscal_year")
        if isinstance(fiscal_year, int):
            anos.add(fiscal_year)
    return sorted(anos, reverse=True)


def _datetime_sort_key(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


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
        "fluxo de recuperação de pendências. A inspeção Celery é tolerante a timeout/falha e a detecção detalhada "
        "de campanhas pendentes recuperáveis é limitada por `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS`."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="monitorarMaterializacoesAnaliticas",
)
def monitorar_materializacoes_analiticas(db: DbSession) -> AnaliseMaterializacaoMonitoramentoResposta:
    inspect = celery_app.control.inspect(timeout=0.5)
    try:
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
    except Exception:
        active = {}
        reserved = {}
        scheduled = {}

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
    stale_chunk_monitor_ids = _stale_chunk_monitor_ids_subquery()
    chunk_counts = db.execute(
        select(
            func.sum(case((AnaliseMaterializacaoChunkExecucao.status == "queued", 1), else_=0)),
            func.sum(case((AnaliseMaterializacaoChunkExecucao.status == "running", 1), else_=0)),
            select(func.count()).select_from(stale_chunk_monitor_ids).scalar_subquery(),
        )
    ).one()
    queued_chunks, running_chunks, stale_chunks = chunk_counts
    pending_summaries = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanha.summary).where(AnaliseMaterializacaoCampanha.status == "pending")
        ).all()
    )
    waiting_for_gate_campaigns = sum(
        1
        for summary in pending_summaries
        if isinstance(summary, dict) and summary.get("wait_reason") in {"INGESTION_ACTIVE", "MANUAL_PAUSE"}
    )
    recovering_campaigns = sum(
        1
        for summary in pending_summaries
        if isinstance(summary, dict) and summary.get("wait_reason") in {"STALE_CHUNK_RECOVERED", "STALE_CHUNK_DETECTED"}
    )
    pending_campaign_rows = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanha)
            .where(AnaliseMaterializacaoCampanha.status == "pending")
            .order_by(AnaliseMaterializacaoCampanha.created_at.asc())
            .limit(_settings.analise_materializacao_pending_recovery_max_campaigns)
        ).all()
    )
    recoverable_campaign_ids: list[str] = []
    undispatched_campaigns: list[AnaliseMaterializacaoCampanha] = []
    for campanha in pending_campaign_rows:
        active_chunk = obter_chunk_ativo_campanha(db, campanha.id)
        stale_chunk_count = len(obter_chunks_stale_ativos(db, campanha_id=campanha.id))
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
        if campanha_tem_requeue_em_transito(campanha, now=now):
            continue
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
                AnaliseMaterializacaoCampanhaItem.chunk_execucao_id.in_(select(stale_chunk_monitor_ids.c.id))
            )
        )
        or 0
    )
    stale_chunk_preview = list(
        db.scalars(
            select(AnaliseMaterializacaoChunkExecucao)
            .where(AnaliseMaterializacaoChunkExecucao.id.in_(select(stale_chunk_monitor_ids.c.id)))
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
    description=(
        "Retorna o estado atual do gate de admissão da materialização analítica e o modo manual persistido. "
        "No modo automático, execuções de ingestão em `agendada`, `em_execucao` ou `aguardando_ingestao` mantêm o gate vermelho por `INGESTION_ACTIVE`; estados finais não bloqueiam."
    ),
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
    description=(
        "Remove a pausa manual e devolve o gate ao modo automático baseado no estado de ingestão. "
        "Se ainda houver execução em `agendada`, `em_execucao` ou `aguardando_ingestao`, o gate continua vermelho por `INGESTION_ACTIVE`."
    ),
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
    description=_DESCRICAO_RECUPERAR_STALE_GERAL,
    responses=_RESPOSTAS_ADMIN_OPERACAO_MATERIALIZACAO,
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
    description=_DESCRICAO_RECUPERAR_STALE_CAMPANHA,
    responses=_RESPOSTAS_ADMIN_OPERACAO_MATERIALIZACAO,
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
        f"{_DESCRICAO_REATIVAR_CAMPANHA} "
        "A chamada exige token de sistema, usuario admin ou usuario com `pode_operar_materializacao=true`. "
        "A resposta sempre traz `status`, `reason_code`, `affected_campaigns`, `requeued_campaigns`, "
        "`recovered_chunks`, `recovered_items`, `dispatcher_enqueued` e `triggered_at`, permitindo que o cliente "
        "diferencie retry efetivo de `noop` operacional."
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
        f"{_DESCRICAO_TRIGGER_RECUPERACAO} "
        "A chamada exige token de sistema, usuario admin ou usuario com `pode_operar_materializacao=true`. "
        "O sweep recupera apenas `STALE_CHUNK` ativos e reenfileira apenas `PENDING_UNDISPATCHED` maduros o "
        "suficiente para reativacao automatica."
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
    "/materializacoes/companhias/{codigo_cvm}/status",
    response_model=AnaliseMaterializacaoCompanhiaStatusResposta,
    summary="Consultar Status de Materializacao por Companhia",
    description=(
        "Retorna um snapshot de leitura rapida para a materializacao analitica de uma companhia em um escopo. "
        "O endpoint combina a revisao canonica atual, a ultima execucao de materializacao e eventual item ativo "
        "ou pendente de campanha. A lista `anos` representa os anos fiscais anuais FY presentes na revisao canonica "
        "corrente; quando ainda nao existe revisao canonica, o backend retorna o ano inferido da janela ativa ou "
        "da ultima execucao, se disponivel. Os aliases `dados`, `periodos`, `materializacoes` e `status_por_ano` "
        "existem para consumidores desacoplados que renderizam status por ano sem depender da listagem operacional."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="consultarStatusMaterializacaoCompanhia",
)
def consultar_status_materializacao_companhia(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societario consultado.")] = "consolidated",
) -> AnaliseMaterializacaoCompanhiaStatusResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    latest_execucao = db.scalar(
        select(AnaliseMaterializacaoExecucao)
        .where(
            AnaliseMaterializacaoExecucao.codigo_cvm == companhia.codigo_cvm,
            AnaliseMaterializacaoExecucao.escopo == escopo,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
        )
        .order_by(
            AnaliseMaterializacaoExecucao.updated_at.desc().nullslast(),
            AnaliseMaterializacaoExecucao.started_at.desc().nullslast(),
            AnaliseMaterializacaoExecucao.created_at.desc(),
        )
        .limit(1)
    )
    latest_success = db.scalar(
        select(AnaliseMaterializacaoExecucao)
        .where(
            AnaliseMaterializacaoExecucao.codigo_cvm == companhia.codigo_cvm,
            AnaliseMaterializacaoExecucao.escopo == escopo,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
            AnaliseMaterializacaoExecucao.status == "success",
        )
        .order_by(
            AnaliseMaterializacaoExecucao.finished_at.desc().nullslast(),
            AnaliseMaterializacaoExecucao.updated_at.desc().nullslast(),
            AnaliseMaterializacaoExecucao.created_at.desc(),
        )
        .limit(1)
    )
    active_item = db.scalar(
        select(AnaliseMaterializacaoCampanhaItem)
        .join(
            AnaliseMaterializacaoCampanha,
            AnaliseMaterializacaoCampanha.id == AnaliseMaterializacaoCampanhaItem.campanha_id,
        )
        .where(
            AnaliseMaterializacaoCampanhaItem.codigo_cvm == companhia.codigo_cvm,
            AnaliseMaterializacaoCampanhaItem.escopo == escopo,
            AnaliseMaterializacaoCampanhaItem.status.in_(("pending", "running")),
            AnaliseMaterializacaoCampanha.status.in_(("pending", "running")),
        )
        .order_by(
            case((AnaliseMaterializacaoCampanhaItem.status == "running", 0), else_=1),
            AnaliseMaterializacaoCampanhaItem.updated_at.desc(),
            AnaliseMaterializacaoCampanhaItem.created_at.desc(),
        )
        .limit(1)
    )
    revision = db.scalar(
        select(AnaliseContextoRevision)
        .where(
            AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
            AnaliseContextoRevision.escopo == escopo,
            AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
            AnaliseContextoRevision.known_to.is_(None),
        )
        .order_by(AnaliseContextoRevision.known_from.desc(), AnaliseContextoRevision.created_at.desc())
        .limit(1)
    )
    coverage = obter_coverage(db, companhia, scope=escopo)
    coverage_by_period = {item.period_id: item for item in coverage.periodos}
    periodos_detalhe = [
        AnaliseMaterializacaoPeriodoStatus(
            period_id=item.period_id,
            ano=item.ano,
            periodicidade=item.periodicidade,
            base_periodo=item.base_periodo,
            escopo=item.escopo,
            has_context_revision=item.has_canonical_context,
            has_fact_revision=bool(item.metrics_available or item.metrics_unavailable),
            metrics_count=len(item.metrics_available),
            unavailable_count=len(item.metrics_unavailable),
            coverage_complete=latest_execucao.coverage_complete if latest_execucao is not None else None,
        )
        for item in coverage.periodos
    ]

    anos = _anos_from_context_revision(revision)
    execucao_base = latest_success or latest_execucao
    anos_set = set(anos)
    if active_item is not None and active_item.invalidated_from is not None:
        anos_set.add(active_item.invalidated_from.year)
    if execucao_base is not None and execucao_base.invalidated_from is not None:
        anos_set.add(execucao_base.invalidated_from.year)
    anos = sorted(anos_set, reverse=True)

    statuses: list[AnaliseMaterializacaoAnoStatus] = []
    for ano in anos:
        if active_item is not None and active_item.invalidated_from is not None and ano >= active_item.invalidated_from.year:
            status_item = _materializacao_ano_status_from_item(ano=ano, escopo=escopo, item=active_item)
            coverage_item = coverage_by_period.get(f"FY{ano}")
            if coverage_item is not None:
                status_item.period_id = coverage_item.period_id
                status_item.has_context_revision = coverage_item.has_canonical_context
                status_item.has_fact_revision = bool(coverage_item.metrics_available or coverage_item.metrics_unavailable)
                status_item.metrics_count = len(coverage_item.metrics_available)
                status_item.unavailable_count = len(coverage_item.metrics_unavailable)
            statuses.append(status_item)
        elif execucao_base is not None:
            status_item = _materializacao_ano_status_from_execucao(ano=ano, escopo=escopo, execucao=execucao_base)
            coverage_item = coverage_by_period.get(f"FY{ano}")
            if coverage_item is not None:
                status_item.period_id = coverage_item.period_id
                status_item.has_context_revision = coverage_item.has_canonical_context
                status_item.has_fact_revision = bool(coverage_item.metrics_available or coverage_item.metrics_unavailable)
                status_item.metrics_count = len(coverage_item.metrics_available)
                status_item.unavailable_count = len(coverage_item.metrics_unavailable)
            statuses.append(status_item)
        else:
            coverage_item = coverage_by_period.get(f"FY{ano}")
            statuses.append(
                AnaliseMaterializacaoAnoStatus(
                    ano=ano,
                    period_id=coverage_item.period_id if coverage_item is not None else f"FY{ano}",
                    status="missing",
                    escopo=escopo,
                    has_context_revision=coverage_item.has_canonical_context if coverage_item is not None else False,
                    has_fact_revision=bool(coverage_item.metrics_available or coverage_item.metrics_unavailable) if coverage_item is not None else False,
                    metrics_count=len(coverage_item.metrics_available) if coverage_item is not None else 0,
                    unavailable_count=len(coverage_item.metrics_unavailable) if coverage_item is not None else 0,
                    coverage_complete=None,
                    calculation_version=CALCULATION_VERSION,
                )
            )

    if active_item is not None:
        status = "queued" if active_item.status == "pending" and active_item.chunk_execucao_id is not None else active_item.status
    elif latest_execucao is not None:
        status = latest_execucao.status
    elif revision is not None:
        status = "success"
    else:
        status = "missing"

    updated_candidates = [
        latest_execucao.updated_at if latest_execucao is not None else None,
        active_item.updated_at if active_item is not None else None,
        revision.created_at if revision is not None else None,
    ]
    updated_at = max((item for item in updated_candidates if item is not None), key=_datetime_sort_key, default=None)
    status_por_ano = {str(item.ano): item for item in statuses}
    return AnaliseMaterializacaoCompanhiaStatusResposta(
        codigo_cvm=companhia.codigo_cvm or codigo_cvm,
        escopo=escopo,
        status=status,
        coverage_complete=latest_execucao.coverage_complete if latest_execucao is not None else None,
        latest_execution=_serializar_materializacao_execucao(latest_execucao) if latest_execucao is not None else None,
        active_item=_serializar_item_preview(active_item) if active_item is not None else None,
        anos=statuses,
        periodos_detalhe=periodos_detalhe,
        dados=statuses,
        periodos=statuses,
        materializacoes=statuses,
        status_por_ano=status_por_ano,
        generated_at=datetime.now(UTC),
        updated_at=updated_at,
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
    "/companhias/{codigo_cvm}/coverage",
    response_model=AnaliseCoverageResposta,
    summary="Matriz de Cobertura Analitica da Companhia",
    description=(
        "Retorna uma matriz autoritativa por período que cruza dado bruto promovido, contexto canônico, fatos "
        "canônicos e última execução de materialização. Use para explicar lacunas como períodos que existem no "
        "DFP/ITR bruto, mas ainda não geraram série canônica para as métricas do gráfico."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseCoverage",
)
def obter_analise_coverage(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> AnaliseCoverageResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_coverage(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)


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
    "/companhias/{codigo_cvm}/series/diagnostico",
    response_model=AnaliseSeriesDiagnosticoResposta,
    summary="Diagnostico de Lacunas das Series Analiticas",
    description=(
        "Usa os mesmos filtros de `/analise/companhias/{codigo_cvm}/series`, mas retorna candidatos, períodos "
        "retornados, períodos rejeitados, contas ausentes, formulários ausentes, mismatch de escopo e mismatch "
        "de materialização. O objetivo é explicar por que um gráfico não possui pontos suficientes."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseSeriesDiagnostico",
)
def obter_analise_series_diagnostico(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo a diagnosticar quando `periodicidade=annual&base_periodo=fy`.", ge=1, le=20)] = 5,
) -> AnaliseSeriesDiagnosticoResposta:
    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    return obter_series_diagnostico(
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
