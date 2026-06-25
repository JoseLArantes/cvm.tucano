import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select

from app.api.auth import AutenticacaoApi, autenticar_requisicao, exigir_admin_api
from app.api.deps import DbSession
from app.services.normalizacao import datetime_para_string_br
from app.updates.models import PendingUpdate, PendingUpdateMember, UpdateScanRun, UpdateSession, UpdateSessionItem
from app.updates.schemas import (
    DiscardResponseSchema,
    PendingUpdateMemberSchema,
    PendingUpdateSchema,
    TriggerResponseSchema,
    UpdateScannerStatusSchema,
    UpdateScanRunQueuedSchema,
    UpdateScanRunSchema,
    UpdateSessionDetailSchema,
    UpdateSessionItemSchema,
    UpdateSessionSchema,
    UpdateSummarySchema,
)
from app.updates.service import (
    add_session_item,
    create_scan_run,
    create_session,
    discard_update,
    get_latest_scan_run,
    remove_session_item,
    trigger_session,
    trigger_update,
)
from app.updates.tasks import run_daily_scanner_task, run_deep_analysis_task

router = APIRouter()


# --- 1. Scanner & Detection ---

@router.get(
    "/scanner/status",
    response_model=UpdateScannerStatusSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Obter status do Scanner",
    description=(
        "Retorna o estado operacional resumido do scanner e aponta para a última execução persistida. "
        "Use `last_scan_run_id` para navegar até o resumo detalhado da execução mais recente, que informa quais artefatos ficaram inalterados, "
        "quais avançaram para análise por arquivo interno e quais members mudaram."
    ),
    response_description="Estado resumido do scanner com referência para a última execução persistida.",
)
def get_scanner_status(db: DbSession) -> dict[str, Any]:
    """
    Retorna metadados do estado operacional do scanner. 
    Ideal para painéis de monitoramento exibirem quando ocorreu a última checagem remota automatizada.
    """
    stmt = select(func.max(PendingUpdate.last_probe_timestamp))
    last_run = db.scalar(stmt)
    latest_scan = get_latest_scan_run(db)
    return {
        "status": "idle",
        "last_run": datetime_para_string_br(last_run) if last_run else None,
        "last_scan_run_id": str(latest_scan.id) if latest_scan is not None else None,
        "last_scan_status": latest_scan.status if latest_scan is not None else None,
        "last_scan_finished_at": (
            datetime_para_string_br(latest_scan.finished_at) if latest_scan and latest_scan.finished_at else None
        ),
    }


@router.post(
    "/scanner/run",
    response_model=UpdateScanRunQueuedSchema,
    dependencies=[Depends(exigir_admin_api)],
    summary="Executar Scanner de Atualizações",
    description=(
        "Dispara de forma assíncrona o job do scanner diário de todas as fontes CVM mapeadas e cria uma execução persistida de scanner. "
        "A execução consolidará um resumo completo por fonte/ano, incluindo artefatos sem alteração, artefatos alterados e, quando houver mudança confirmada, "
        "o detalhamento dos arquivos internos alterados e inalterados."
    ),
    response_description="Confirmação de enfileiramento, ID da tarefa Celery e UUID persistido da execução de scanner.",
)
def trigger_scanner(db: DbSession) -> dict[str, Any]:
    """
    Aciona o worker Celery para varrer os servidores da CVM em busca de novos arquivos ZIP ou CSV de cadastro.
    O scanner sempre grava uma execução persistida (`scan_run`) com resumo por fonte/ano.
    Quando um artefato é considerado inalterado, o resumo registra que a análise parou no artefato.
    Quando um artefato mudou, o scanner aprofunda a análise e registra members alterados e inalterados no resumo.
    """
    scan_run = create_scan_run(db)
    task = run_daily_scanner_task.delay(str(scan_run.id))
    return {
        "status": "queued",
        "task_id": task.id,
        "scan_run_id": scan_run.id,
        "message": "Scanner task has been queued in the background."
    }


@router.get(
    "/scanner/runs/latest",
    response_model=UpdateScanRunSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Obter Última Execução de Scanner",
    description=(
        "Retorna a execução mais recente do scanner com o resumo consolidado do que foi efetivamente analisado. "
        "Use esta rota para mostrar ao operador quais artefatos pararam no check de ZIP/CSV e quais avançaram para análise por arquivo interno."
    ),
    response_description="Execução mais recente do scanner, incluindo resumo detalhado.",
)
def get_latest_scanner_run(db: DbSession) -> UpdateScanRun:
    scan_run = get_latest_scan_run(db)
    if scan_run is None:
        raise HTTPException(status_code=404, detail="No scanner run found")
    return scan_run


@router.get(
    "/scanner/runs/{id}",
    response_model=UpdateScanRunSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Detalhar Execução de Scanner",
    description=(
        "Retorna o resumo detalhado de uma execução de scanner específica. "
        "O campo `summary.items` mostra, para cada fonte/ano analisado, a decisão do artefato (`changed`, `unchanged`, `unknown`, `error`) "
        "e, quando houve mudança confirmada, a classificação de cada arquivo interno como alterado ou inalterado."
    ),
    response_description="Execução de scanner identificada pelo UUID, com resumo detalhado.",
)
def get_scanner_run(
    id: Annotated[uuid.UUID, Path(description="UUID da execução de scanner a ser consultada")],
    db: DbSession,
) -> UpdateScanRun:
    scan_run = db.get(UpdateScanRun, id)
    if scan_run is None:
        raise HTTPException(status_code=404, detail="UpdateScanRun not found")
    return scan_run


@router.get(
    "/scanner/history",
    response_model=list[PendingUpdateSchema],
    dependencies=[Depends(autenticar_requisicao)],
    summary="Listar Histórico de Detecções",
    description="Retorna as últimas 50 atualizações detectadas (ativas ou finalizadas), ordenadas da mais recente para a mais antiga.",
    response_description="Lista de schemas de atualizações pendentes.",
)
def get_scanner_history(db: DbSession) -> list[PendingUpdate]:
    """
    Permite auditar o histórico de alterações publicadas nos servidores da CVM que foram capturadas pelo Tucano CVM.
    """
    stmt = (
        select(PendingUpdate)
        .order_by(PendingUpdate.detection_timestamp.desc())
        .limit(50)
    )
    return list(db.scalars(stmt).all())


# --- 2. Pending Updates ---

@router.get(
    "/pending",
    response_model=list[PendingUpdateSchema],
    dependencies=[Depends(autenticar_requisicao)],
    summary="Listar Atualizações Pendentes",
    description="Retorna a lista de todas as atualizações pendentes registradas no banco de dados, com suporte a filtros por tipo de fonte e status.",
    response_description="Lista filtrada de atualizações pendentes.",
)
def list_pending_updates(
    db: DbSession,
    fonte: Annotated[str | None, Query(description="Filtrar pelo tipo da fonte (ex: 'dfp', 'itr', 'cadastro')")] = None,
    status: Annotated[str | None, Query(description="Filtrar pelo estado do ciclo de vida da atualização (ex: 'change_detected', 'ready_for_ingestion')")] = None,
) -> list[PendingUpdate]:
    """
    Retorna o catálogo de pendências de dados descobertas.
    Filtre por `status=ready_for_ingestion` para encontrar o lote pronto para disparo físico de ingestão.
    """
    stmt = select(PendingUpdate)
    if fonte:
        stmt = stmt.where(PendingUpdate.fonte == fonte)
    if status:
        stmt = stmt.where(PendingUpdate.status == status)
    stmt = stmt.order_by(PendingUpdate.detection_timestamp.desc())
    return list(db.scalars(stmt).all())


@router.get(
    "/pending/{id}",
    response_model=PendingUpdateSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Detalhar Atualização Pendente",
    description="Retorna os metadados detalhados de uma atualização pendente identificada pelo seu UUID.",
    response_description="Metadados da atualização pendente correspondente.",
)
def get_pending_update(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente a ser detalhada")],
    db: DbSession
) -> PendingUpdate:
    """
    Retorna os detalhes de uma pendência específica, incluindo a URL de origem remota, hashes capturados no probe e o sumário consolidado de mudanças.
    """
    pending = db.get(PendingUpdate, id)
    if pending is None:
        raise HTTPException(status_code=404, detail="PendingUpdate not found")
    return pending


@router.get(
    "/pending/{id}/members",
    response_model=list[PendingUpdateMemberSchema],
    dependencies=[Depends(autenticar_requisicao)],
    summary="Listar Membros e Diffs Detalhados",
    description="Retorna o relatório granular das tabelas CSV membros contidas dentro do ZIP anual, apontando quais foram adicionadas, modificadas ou removidas.",
    response_description="Coleção de dados detalhando a análise membro a membro.",
)
def list_pending_update_members(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente raiz")],
    db: DbSession
) -> list[PendingUpdateMember]:
    """
    Fornece o detalhamento de arquivos membros. Permite que o operador audite o impacto exato antes de aprovar e disparar a ingestão
    (ex: descobrir se houve mudança estrutural de colunas ou variação acentuada de número de linhas).
    """
    pending = db.get(PendingUpdate, id)
    if pending is None:
        raise HTTPException(status_code=404, detail="PendingUpdate not found")
    
    stmt = select(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == id).order_by(PendingUpdateMember.member_name.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "/pending/{id}/analyze",
    response_model=dict[str, Any],
    dependencies=[Depends(autenticar_requisicao)],
    summary="Forçar Análise Profunda",
    description="Dispara manualmente a tarefa de análise profunda (Deep Analysis) de membros para uma atualização pendente no status change_detected.",
    response_description="Confirmação e ID da tarefa Celery enfileirada.",
)
def trigger_update_analysis(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente a ser analisada")],
    db: DbSession
) -> dict[str, Any]:
    """
    Enfileira a extração de membros e cálculo de diffs estruturais em background.
    Caso a análise profunda já tenha sido executada ou esteja rodando, o status atual é retornado sem alteração.
    """
    pending = db.get(PendingUpdate, id)
    if pending is None:
        raise HTTPException(status_code=404, detail="PendingUpdate not found")
    
    if pending.status not in ("change_detected", "analysis_queued"):
        return {
            "status": pending.status,
            "message": f"Update is in status '{pending.status}', analysis not required or already running."
        }
    
    pending.status = "analysis_queued"
    db.commit()
    
    task = run_deep_analysis_task.delay(str(id))
    return {
        "status": "queued",
        "task_id": task.id,
        "message": "Deep analysis task has been queued."
    }


@router.post(
    "/pending/{id}/trigger",
    response_model=TriggerResponseSchema,
    summary="Disparar Ingestão Manual",
    description="Aprova a atualização pendente especificada e agenda sua ingestão física no banco de dados. Bypassa sondagens adicionais e atualiza o status para triggered.",
    response_description="Dados de identificação do trigger e Celery Task ID da execução física.",
)
def trigger_pending_update(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente a ser disparada")],
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession
) -> dict[str, Any]:
    """
    Aprova formalmente a importação de uma atualização pendente.
    Bypassa etapas de aquisição e sonda de hash e injeta os dados do ZIP diretamente no pipeline de importação em background.
    """
    try:
        username = auth.usuario.username if auth.usuario else "system"
        task_id = trigger_update(db, id, user=username)
        return {
            "status": "triggered",
            "task_id": task_id,
            "pending_update_id": id
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/pending/{id}/discard",
    response_model=DiscardResponseSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Descartar Atualização",
    description="Marca a atualização pendente selecionada como descartada (discarded), invalidando-a para ingestões futuras e liberando a trava operacional da fonte.",
    response_description="Confirmação de descarte contendo o UUID correspondente.",
)
def discard_pending_update(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente a ser descartada")],
    db: DbSession
) -> dict[str, Any]:
    """
    Sinaliza que a alteração de dados remota não deve ser ingesta no Tucano CVM.
    Libera a fonte/ano para que novas detecções do scanner criem futuros registros pendentes.
    """
    try:
        discard_update(db, id)
        return {
            "status": "discarded",
            "pending_update_id": id
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/pending/trigger-all",
    response_model=list[TriggerResponseSchema],
    summary="Disparar Todas as Atualizações Prontas",
    description="Aprova e executa a ingestão física de todas as atualizações no estado ready_for_ingestion em lote.",
    response_description="Coleção de confirmações contendo os IDs das atualizações disparadas e seus Celery Task IDs.",
)
def trigger_all_ready_updates(
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession
) -> list[dict[str, Any]]:
    """
    Facilita ações bulk do operador. Varre o banco, localiza todas as atualizações analisadas e aprovadas, enfileirando os respectivos fluxos físicos.
    """
    username = auth.usuario.username if auth.usuario else "system"
    stmt = select(PendingUpdate).where(PendingUpdate.status == "ready_for_ingestion")
    ready = db.scalars(stmt).all()
    
    triggered = []
    for item in ready:
        try:
            tid = trigger_update(db, item.id, user=username)
            triggered.append({
                "status": "triggered",
                "task_id": tid,
                "pending_update_id": item.id
            })
        except Exception:
            continue
            
    return triggered


# --- 3. Update Sessions ---

@router.post(
    "/session",
    response_model=UpdateSessionSchema,
    summary="Criar Sessão de Seleção (Lote)",
    description="Cria uma nova sessão temporária (com token de chave e validade padrão de 24h) para que o operador monte um carrinho/lote de atualizações a serem aprovadas de forma coesa.",
    response_description="Metadados da sessão de aprovação de lote.",
)
def create_update_session(
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession
) -> UpdateSession:
    """
    Inicia uma sessão de backoffice para gerenciamento de lotes.
    Chaves geradas são expiradas após 24 horas (SESSION_TIMEOUT_HOURS).
    """
    username = auth.usuario.username if auth.usuario else "system"
    sess = create_session(db, user_id=username)
    return sess


@router.get(
    "/session/{session_key}",
    response_model=UpdateSessionDetailSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Visualizar Detalhes da Sessão",
    description="Retorna os metadados de uma sessão de atualização e a lista de itens agregados a ela.",
    response_description="Detalhamento da sessão de aprovação.",
)
def get_update_session(
    session_key: Annotated[str, Path(description="Chave token da sessão activa")],
    db: DbSession
) -> UpdateSessionDetailSchema:
    """
    Retorna o lote de itens atualmente selecionados na sessão do operador.
    """
    stmt_sess = select(UpdateSession).where(UpdateSession.session_key == session_key)
    sess = db.scalar(stmt_sess)
    if sess is None:
        raise HTTPException(status_code=404, detail="UpdateSession not found")
        
    stmt_items = select(UpdateSessionItem).where(UpdateSessionItem.session_id == sess.id)
    items = db.scalars(stmt_items).all()
    
    detail = UpdateSessionDetailSchema(
        id=sess.id,
        session_key=sess.session_key,
        user_id=sess.user_id,
        created_at=sess.created_at,
        expires_at=sess.expires_at,
        status=sess.status,
        items=[UpdateSessionItemSchema.model_validate(i) for i in items]
    )
    return detail


@router.post(
    "/session/{session_key}/items",
    response_model=UpdateSessionItemSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Adicionar Item ao Lote",
    description="Adiciona uma atualização pendente específica ao carrinho/lote lógico de uma sessão ativa.",
    response_description="Confirmação de inclusão do item na sessão.",
)
def add_update_session_item(
    session_key: Annotated[str, Path(description="Chave token da sessão ativa")],
    pending_update_id: Annotated[uuid.UUID, Query(description="UUID da atualização pendente a incluir")],
    db: DbSession
) -> UpdateSessionItem:
    """
    Agrega uma pendência à sessão do operador.
    Impede inclusões caso a sessão correspondente tenha expirado.
    """
    try:
        item = add_session_item(db, session_key, pending_update_id)
        return item
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/session/{session_key}/items/{pending_update_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Remover Item do Lote",
    description="Remove uma atualização pendente específica do carrinho/lote de uma sessão ativa.",
)
def remove_update_session_item(
    session_key: Annotated[str, Path(description="Chave token da sessão ativa")],
    pending_update_id: Annotated[uuid.UUID, Path(description="UUID da atualização pendente a remover")],
    db: DbSession
) -> None:
    """
    Retira uma pendência do lote da sessão ativa.
    """
    try:
        remove_session_item(db, session_key, pending_update_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/session/{session_key}/trigger",
    response_model=list[str],
    summary="Disparar Ingestão do Lote (Trigger Sessão)",
    description="Executa a ingestão física de todas as atualizações que foram selecionadas na sessão de aprovação de lote. Retorna a lista de IDs de tarefas Celery agendadas.",
    response_description="Coleção de Celery Task IDs das ingestões disparadas.",
)
def trigger_update_session(
    session_key: Annotated[str, Path(description="Chave token da sessão ativa a disparar")],
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession
) -> list[str]:
    """
    Realiza o processamento simultâneo do carrinho de pendências da sessão.
    Todos os itens elegíveis têm seus status atualizados e as tarefas Celery de Fase 1/Fase 2 de importação são criadas de forma assíncrona.
    """
    try:
        username = auth.usuario.username if auth.usuario else "system"
        task_ids = trigger_session(db, session_key, user=username)
        return task_ids
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/session/{session_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Expirar/Encerrar Sessão",
    description="Marca a sessão ativa de aprovação de lote como encerrada/expirada.",
)
def delete_update_session(
    session_key: Annotated[str, Path(description="Chave token da sessão a expirar")],
    db: DbSession
) -> None:
    """
    Invalida a sessão do operador imediatamente.
    """
    stmt_sess = select(UpdateSession).where(UpdateSession.session_key == session_key)
    sess = db.scalar(stmt_sess)
    if sess is not None:
        sess.status = "expired"
        db.commit()


# --- 4. Bulk Operations & Summary ---

@router.get(
    "/summary",
    response_model=UpdateSummarySchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Obter Sumário de Atualizações",
    description="Retorna estatísticas operacionais de atualizações pendentes (contagem por tipo de fonte, status e total de itens prontos para ingestão).",
    response_description="Sumário estatístico estruturado do serviço.",
)
def get_update_summary(db: DbSession) -> dict[str, Any]:
    """
    Estatísticas rápidas do serviço de atualizações de dados CVM. 
    Excelente para alimentar cards de sumário e dashboards no front-end.
    """
    stmt_all = select(PendingUpdate)
    all_updates = db.scalars(stmt_all).all()
    
    total_pending = sum(1 for item in all_updates if item.status in ("change_detected", "analysis_queued", "analyzing", "ready_for_ingestion"))
    ready_count = sum(1 for item in all_updates if item.status == "ready_for_ingestion")
    
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in all_updates:
        by_source[item.fonte] = by_source.get(item.fonte, 0) + 1
        by_status[item.status] = by_status.get(item.status, 0) + 1
        
    return {
        "total_pending": total_pending,
        "by_source": by_source,
        "by_status": by_status,
        "ready_count": ready_count
    }


@router.post(
    "/refresh-all",
    response_model=UpdateScanRunQueuedSchema,
    dependencies=[Depends(exigir_admin_api)],
    summary="Forçar Atualização Geral",
    description=(
        "Força a execução imediata do scanner diário em background e cria uma execução persistida de scanner, "
        "equivalente ao fluxo de `/updates/scanner/run`. "
        "Use este atalho quando quiser iniciar uma nova varredura completa e acompanhar o resumo por `scan_run_id`."
    ),
    response_description="Confirmação de agendamento do scanner e UUID persistido da execução de scan.",
)
def refresh_all_sources(db: DbSession) -> dict[str, Any]:
    """
    Garante sincronismo sob demanda com os servidores da CVM. Requer permissão administrativa.
    """
    scan_run = create_scan_run(db)
    task = run_daily_scanner_task.delay(str(scan_run.id))
    return {
        "status": "queued",
        "task_id": task.id,
        "scan_run_id": scan_run.id,
        "message": "Scanner task forced and queued in the background."
    }
