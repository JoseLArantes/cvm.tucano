import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
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
    codigo_isin: str = Field(description="Código ISIN da ação com 12 caracteres alfanuméricos.", examples=["BRPETRACNOR9"])
    cnpj_companhia: str = Field(description="CNPJ do emissor com 14 dígitos, sem pontuação; zeros à esquerda são preservados.", examples=["33000167000101"])


class ListaIsinResposta(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "dados": [
            {"codigo_isin": "BRPETRACNOR9", "cnpj_companhia": "33000167000101"},
            {"codigo_isin": "BRPETRACNPR6", "cnpj_companhia": "33000167000101"},
        ],
        "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 2},
    }})
    dados: list[IsinResposta] = Field(description="Vínculos ordenados por código ISIN.")
    paginacao: Paginacao = Field(description="Página, tamanho e total dos vínculos selecionados.")


class IsinAgendamento(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "execucao_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
        "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
        "lote_id": "5de6e344-42af-42c7-a2a2-6224f01a1ca8",
        "status": "agendada",
    }})
    execucao_id: uuid.UUID = Field(description="Identificador da execução para acompanhamento na API de ingestão.")
    id_tarefa: str = Field(description="Identificador da tarefa Celery.")
    lote_id: uuid.UUID = Field(description="Identificador do lote persistido da fila.")
    status: str = Field(description="Estado inicial da execução, `agendada`.")


@router.get(
    "/isin",
    response_model=ListaIsinResposta,
    summary="Consultar referência de ISINs de ações",
    operation_id="listarReferenciaIsin",
    description=(
        "Requer token bearer válido de usuário ou de sistema. Retorna os vínculos CNPJ–ISIN "
        "publicados pela última importação bem-sucedida dos arquivos de emissores e numeração. "
        "São incluídas ações elegíveis ativas com CNPJ válido e ISIN validado; um emissor pode ter vários ISINs. "
        "A referência é atualizada pela importação e pode diferir temporariamente de `codigos_isin` "
        "das respostas de companhias, atualizado após o CADASTRO. "
        "Os filtros opcionais são comparados exatamente, sem normalização, e combinados por AND. "
        "A ordenação é crescente por `codigo_isin`. A paginação começa em 1, usa 100 itens por padrão "
        "e aceita até 500. `total` conta todos os registros correspondentes, antes da paginação. "
        "Uma referência vazia, filtro sem correspondência ou página além do fim retorna `200` com `dados: []`."
    ),
    responses={401: {"description": "Token bearer ausente, inválido ou expirado."}},
)
def listar_isin(db: DbSession, pagina: int = Query(1, ge=1, description="Página iniciada em 1."),
                tamanho_pagina: int = Query(100, ge=1, le=500, description="Quantidade de registros por página, até 500."),
                cnpj_companhia: str | None = Query(None, description="CNPJ do emissor com 14 dígitos, sem pontuação.", examples=["33000167000101"]),
                codigo_isin: str | None = Query(None, description="Código ISIN de 12 caracteres.", examples=["BRPETRACNOR9"])) -> ListaIsinResposta:
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
             tags=["ingestion"], operation_id="dispararSincronizacaoIsin",
             summary="Importar referência de ISINs",
             description=("Requer token bearer de administrador ou token de sistema. Não recebe corpo nem parâmetros. "
                          "Registra uma execução e um lote na fila persistida, retornando `202` antes do processamento. "
                          "O worker lê as cópias completas `emissores/EMISSOR.txt` e `emissores/NUMERACA.TXT` do R2, "
                          "associa o código de emissor ao CNPJ e ao ISIN, filtra ações elegíveis ativas e valida CNPJ e ISIN. "
                          "A referência é reconciliada em transação: vínculos ausentes na nova cópia são removidos, "
                          "e uma falha preserva a referência anterior. Registros elegíveis sem CNPJ válido ou com ISIN inválido são contabilizados como rejeitados. "
                          "Uma importação equivalente termina com `sem_alteracao`. Arquivos indisponíveis, leiaute inválido, "
                          "conflitos de identidade ou ausência de vínculos válidos resultam em `falha`. "
                          "Use `GET /ingestion/sincronizacoes/{execucao_id}` para acompanhar status, contagens e erro. "
                          "Os estados incluem `agendada`, `em_execucao`, `sucesso`, `sem_alteracao` e `falha`. "
                          "A sincronização integral seguinte do CADASTRO atualiza `codigos_isin` das companhias; "
                          "uma referência vazia não altera o cadastro. "
                          "Uma solicitação concorrente responde `409` com o identificador da execução existente."),
             responses={401: {"description": "Token bearer ausente, inválido ou expirado."},
                        403: {"description": "Token de usuário válido sem permissão administrativa."},
                        409: {"description": "Já existe importação agendada ou em execução.",
                              "content": {"application/json": {"example": {"detail": {"execucao_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a"}}}}}})
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
