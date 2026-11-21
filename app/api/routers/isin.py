import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.auth import exigir_admin_api
from app.api.deps import DbSession
from app.models.isin import ReferenciaIsin
from app.models.sincronizacao import ExecucaoSincronizacao
from app.schemas.comum import Paginacao
from app.services.ingestion.queue import _control_lock, adicionar_execucao_a_fila, criar_lote
from app.services.ingestion.scheduling import criar_execucao_sincronizacao_agendada
from app.worker.tasks import despachar_fila_ingestao_task, sincronizar_isin_task

router = APIRouter()


class IsinResposta(BaseModel):
    codigo_isin: str = Field(description="Código ISIN da ação.")
    cnpj_companhia: str = Field(description="CNPJ do emissor com 14 dígitos.")


class ListaIsinResposta(BaseModel):
    dados: list[IsinResposta]
    paginacao: Paginacao


class IsinAgendamento(BaseModel):
    execucao_id: uuid.UUID
    id_tarefa: str
    lote_id: uuid.UUID
    status: str


@router.get("/isin", response_model=ListaIsinResposta, summary="Consultar referência de ISINs")
def listar_isin(db: DbSession, pagina: int = Query(1, ge=1), tamanho_pagina: int = Query(100, ge=1, le=500),
                cnpj_companhia: str | None = None, codigo_isin: str | None = None) -> ListaIsinResposta:
    query = select(ReferenciaIsin)
    if cnpj_companhia is not None:
        query = query.where(ReferenciaIsin.cnpj_companhia == cnpj_companhia)
    if codigo_isin is not None:
        query = query.where(ReferenciaIsin.codigo_isin == codigo_isin)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(ReferenciaIsin.codigo_isin).offset((pagina - 1) * tamanho_pagina).limit(tamanho_pagina)).all()
    return ListaIsinResposta(dados=[IsinResposta(codigo_isin=r.codigo_isin, cnpj_companhia=r.cnpj_companhia) for r in rows],
                             paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total))


@router.post("/ingestion/sincronizacoes/isin", status_code=202, response_model=IsinAgendamento,
             summary="Importar referência de ISINs", description="Agenda a leitura dos arquivos completos EMISSOR e NUMERACA no R2. Requer permissão administrativa.")
def agendar_isin(db: DbSession, _: Annotated[None, Depends(exigir_admin_api)]) -> IsinAgendamento:
    _control_lock(db)
    existente = db.scalar(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.tipo_fonte == "isin", ExecucaoSincronizacao.status.in_(("agendada", "em_execucao", "aguardando_ingestao"))).limit(1))
    if existente is not None:
        raise HTTPException(status_code=409, detail={"execucao_id": str(existente.id)})
    task_id = str(uuid.uuid4())
    execucao = criar_execucao_sincronizacao_agendada(db, tipo_fonte="isin", ano=None, task_id=task_id)
    batch = criar_lote(db, source="admin", metadata={"requested_scope": "isin"})
    db.add(execucao)
    db.flush()
    adicionar_execucao_a_fila(db, batch=batch, execucao=execucao, task_name=sincronizar_isin_task.name,
                             kwargs={"execucao_id": str(execucao.id)}, kind="simple")
    db.commit()
    try:
        despachar_fila_ingestao_task.delay()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Falha ao sinalizar fila de ISIN")
    return IsinAgendamento(execucao_id=execucao.id, id_tarefa=task_id, lote_id=batch.id, status="agendada")
