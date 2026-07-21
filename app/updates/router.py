import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select

from app.api.auth import AutenticacaoApi, autenticar_requisicao, exigir_admin_api
from app.api.deps import DbSession, PaginacaoQuery
from app.core.config import get_settings
from app.schemas.comum import Paginacao
from app.updates.models import PendingUpdate, PendingUpdateMember, UpdateScanRun, UpdateSession, UpdateSessionItem
from app.updates.schemas import (
    AcknowledgeArtifactReferenceResponseSchema,
    DiscardResponseSchema,
    PendingUpdateMemberSchema,
    PendingUpdateSchema,
    TriggerResponseSchema,
    UpdateScannerStatusSchema,
    UpdateScanRunQueuedSchema,
    UpdateScanRunSchema,
    UpdateScanRunsListSchema,
    UpdateSessionDetailSchema,
    UpdateSessionItemSchema,
    UpdateSessionSchema,
    UpdateSummarySchema,
)
from app.updates.service import (
    acknowledge_artifact_reference,
    add_session_item,
    create_scan_run,
    create_session,
    discard_update,
    get_latest_scan_run,
    get_scanner_status_snapshot,
    list_scan_runs,
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
        "Retorna a saúde da vigilância diária e aponta para a última execução persistida. "
        "`health_status=healthy` exige cobertura completa e conclusiva dentro da janela esperada; `degraded` indica "
        "checagens inconclusivas, erros ou fontes sem baseline; `stale` indica ausência de conclusão recente. "
        "`schedule_status` considera somente execuções agendadas e não é renovado por checagens manuais. "
        "Use `last_scan_run_id` para consultar o log por fonte/ano."
    ),
    response_description="Estado resumido do scanner com referência para a última execução persistida.",
)
def get_scanner_status(db: DbSession) -> dict[str, Any]:
    """
    Retorna metadados do estado operacional do scanner. 
    Ideal para painéis de monitoramento exibirem quando ocorreu a última checagem remota automatizada.
    """
    settings = get_settings()
    return get_scanner_status_snapshot(
        db,
        stale_after_hours=settings.updates_scanner_stale_after_hours,
        scanner_enabled=settings.updates_service_enabled,
        schedule_enabled=settings.updates_service_enabled and not settings.auto_trigger_updates,
    )


@router.post(
    "/scanner/run",
    response_model=UpdateScanRunQueuedSchema,
    dependencies=[Depends(exigir_admin_api)],
    summary="Executar Scanner de Atualizações",
    description=(
        "Dispara de forma assíncrona o job do scanner diário de todas as fontes CVM mapeadas e cria uma execução persistida de scanner. "
        "Os escopos anuais são derivados dos anos que possuem ingestão bem-sucedida; `ANOS_INICIAIS_*` não controla a cobertura do scanner. "
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
        "Execuções automáticas e manuais são persistidas mesmo quando nenhuma mudança é encontrada. "
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
    "/scanner/runs",
    response_model=UpdateScanRunsListSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Listar Execuções do Scanner",
    description=(
        "Lista as execuções automáticas e manuais do scanner, inclusive quando nenhuma atualização foi detectada. "
        "Cada execução informa cobertura, origem do disparo, contadores conclusivos/inconclusivos e uma checagem por fonte/ano."
    ),
    response_description="Histórico paginado das varreduras remotas do Updates Service.",
)
def list_scanner_runs(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filtra por `queued`, `running`, `completed` ou `failed`.",
            pattern="^(queued|running|completed|failed)$",
        ),
    ] = None,
) -> UpdateScanRunsListSchema:
    runs, total = list_scan_runs(
        db,
        status=status_filter,
        offset=paginacao.offset,
        limit=paginacao.tamanho_pagina,
    )
    return UpdateScanRunsListSchema(
        dados=[UpdateScanRunSchema.model_validate(run) for run in runs],
        paginacao=Paginacao(
            pagina=paginacao.pagina,
            tamanho_pagina=paginacao.tamanho_pagina,
            total=total,
        ),
    )


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
    response: Response,
    fonte: Annotated[str | None, Query(description="Filtrar pelo tipo da fonte (ex: 'dfp', 'itr', 'cadastro')")] = None,
    status: Annotated[str | None, Query(description="Filtrar pelo estado do ciclo de vida da atualização (ex: 'change_detected', 'ready_for_ingestion')")] = None,
    ano: int | None = None,
    recommended_action: str | None = None,
    detected_from: datetime | None = None,
    detected_to: datetime | None = None,
    pagina: int = Query(default=1, ge=1),
    tamanho_pagina: int = Query(default=100, ge=1, le=500),
    ordenar: str = "detection_timestamp:desc",
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
    if ano is not None:
        stmt = stmt.where(PendingUpdate.ano == ano)
    if detected_from is not None:
        stmt = stmt.where(PendingUpdate.detection_timestamp >= detected_from)
    if detected_to is not None:
        stmt = stmt.where(PendingUpdate.detection_timestamp <= detected_to)
    candidates = list(db.scalars(stmt).all())
    if recommended_action:
        candidates = [pending for pending in candidates if pending.recommended_action == recommended_action or pending.next_action == recommended_action]
    candidates.sort(key=lambda pending: pending.detection_timestamp, reverse=not ordenar.endswith(":asc"))
    response.headers["X-Total-Count"] = str(len(candidates))
    response.headers["X-Page"] = str(pagina)
    response.headers["X-Page-Size"] = str(tamanho_pagina)
    offset = (pagina - 1) * tamanho_pagina
    return candidates[offset : offset + tamanho_pagina]


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
    description=(
        "Dispara a análise SHA-256 dos members para uma atualização em `change_detected` ou repete a análise de "
        "um item `content_unchanged` quando for necessário reconstruir sua referência remota."
    ),
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
    
    if pending.status not in ("change_detected", "analysis_queued", "content_unchanged"):
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
    "/pending/{id}/acknowledge-reference",
    response_model=AcknowledgeArtifactReferenceResponseSchema,
    summary="Atualizar Referência Remota Sem Ingestão",
    description=(
        "Finaliza uma atualização cuja análise comprovou `total_changes=0` e equivalência SHA-256 de todos os members. "
        "Registra os headers remotos como referência reconhecida vinculada à ingestão canônica atual, sem enfileirar "
        "Celery e sem alterar a proveniência do `IngestionFile`. A referência deixa de ser aplicável quando uma nova "
        "ingestão bem-sucedida substitui o baseline canônico."
    ),
    response_description="Referências reconhecidas e confirmação explícita de que nenhuma ingestão foi disparada.",
)
def acknowledge_pending_update_reference(
    id: Annotated[uuid.UUID, Path(description="UUID da atualização com status `content_unchanged`")],
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession,
) -> dict[str, Any]:
    try:
        username = auth.usuario.username if auth.usuario else "system"
        pending, references = acknowledge_artifact_reference(db, id, user=username)
        return {
            "status": pending.status,
            "pending_update_id": pending.id,
            "ingestion_triggered": False,
            "acknowledged_references": references,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/pending/{id}/trigger",
    response_model=TriggerResponseSchema,
    summary="Disparar Ingestão Manual",
    description=(
        "Agenda ingestão somente para atualizações com conteúdo modificado e status `ready_for_ingestion`. "
        "Itens `content_unchanged` devem usar `/acknowledge-reference` e não geram tarefas Celery."
    ),
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
            "status": "ingestion_queued",
            "task_id": task_id,
            "pending_update_id": id
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/pending/{id}/retry-ingestion",
    response_model=TriggerResponseSchema,
    summary="Reenfileirar ingestao de atualizacao com falha",
    description="Aceita apenas atualizacoes em `ingestion_failed`; a resposta confirma enfileiramento, nao conclusao da ingestao.",
)
def retry_pending_update_ingestion(
    id: Annotated[uuid.UUID, Path(description="UUID da atualizacao com falha de ingestao")],
    auth: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
    db: DbSession,
) -> dict[str, Any]:
    pending = db.get(PendingUpdate, id)
    if pending is None:
        raise HTTPException(status_code=404, detail="PendingUpdate not found")
    if pending.status != "ingestion_failed":
        raise HTTPException(status_code=409, detail={"reason_code": "UPDATE_NOT_RETRYABLE"})
    pending.status = "ready_for_ingestion"
    db.commit()
    task_id = trigger_update(db, id, user=auth.usuario.username if auth.usuario else "system")
    return {"status": "ingestion_queued", "task_id": task_id, "pending_update_id": id}


@router.post(
    "/pending/{id}/discard",
    response_model=DiscardResponseSchema,
    dependencies=[Depends(autenticar_requisicao)],
    summary="Descartar Atualização",
    description=(
        "Marca a pendência como `discarded` sem reconhecer os metadados remotos como baseline. Se o artefato continuar "
        "diferente da referência canônica ou reconhecida, uma checagem futura pode detectá-lo novamente."
    ),
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
    description=(
        "Retorna contagens por fonte e status, itens prontos para ingestão e artefatos sem mudança de conteúdo "
        "aguardando atualização de referência."
    ),
    response_description="Sumário estatístico estruturado do serviço.",
)
def get_update_summary(db: DbSession) -> dict[str, Any]:
    """
    Estatísticas rápidas do serviço de atualizações de dados CVM. 
    Excelente para alimentar cards de sumário e dashboards no front-end.
    """
    stmt_all = select(PendingUpdate)
    all_updates = db.scalars(stmt_all).all()
    
    total_pending = sum(
        1
        for item in all_updates
        if item.status in (
            "change_detected",
            "analysis_queued",
            "analyzing",
            "ready_for_ingestion",
            "content_unchanged",
        )
    )
    ready_count = sum(1 for item in all_updates if item.status == "ready_for_ingestion")
    reference_update_count = sum(1 for item in all_updates if item.status == "content_unchanged")
    
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in all_updates:
        by_source[item.fonte] = by_source.get(item.fonte, 0) + 1
        by_status[item.status] = by_status.get(item.status, 0) + 1
        
    return {
        "total_pending": total_pending,
        "by_source": by_source,
        "by_status": by_status,
        "ready_count": ready_count,
        "reference_update_count": reference_update_count,
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
