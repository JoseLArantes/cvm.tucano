from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Select, func, select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.schemas.companhia import CompanhiaResposta, ListaCompanhiasResposta
from app.schemas.comum import Paginacao
from app.services.normalizacao import normalizar_cnpj

router = APIRouter(prefix="/companhias")

_RESPOSTAS_PADRAO = {
    404: {
        "description": "Recurso não encontrado para os critérios informados.",
        "content": {"application/json": {"example": {"detail": "Companhia nao encontrada."}}},
    },
    422: {
        "description": "Parâmetro inválido.",
        "content": {"application/json": {"example": {"detail": "Campo invalido."}}},
    },
}


@router.get(
    "",
    response_model=ListaCompanhiasResposta,
    summary="Listar Companhias",
    description=(
        "Retorna lista paginada de companhias abertas normalizadas. "
        "Permite filtragem por CNPJ e código CVM."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCompanhias",
)
def listar_companhias(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: Annotated[
        str | None,
        Query(
            description="CNPJ da companhia (com ou sem pontuação).",
            examples=["08.773.135/0001-00", "08773135000100"],
        ),
    ] = None,
    codigo_cvm: Annotated[
        int | None,
        Query(
            description="Código CVM da companhia.",
            examples=[25224],
        ),
    ] = None,
) -> ListaCompanhiasResposta:
    query: Select[tuple[Companhia]] = select(Companhia)
    query_total = select(func.count()).select_from(Companhia)

    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(Companhia.cnpj_companhia == cnpj)
        query_total = query_total.where(Companhia.cnpj_companhia == cnpj)

    if codigo_cvm is not None:
        query = query.where(Companhia.codigo_cvm == codigo_cvm)
        query_total = query_total.where(Companhia.codigo_cvm == codigo_cvm)

    total = db.scalar(query_total) or 0
    itens = (
        db.execute(query.order_by(Companhia.denominacao_social).offset(paginacao.offset).limit(paginacao.tamanho_pagina))
        .scalars()
        .all()
    )

    return ListaCompanhiasResposta(
        dados=[CompanhiaResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(
            pagina=paginacao.pagina,
            tamanho_pagina=paginacao.tamanho_pagina,
            total=total,
        ),
    )


@router.get(
    "/codigo-cvm/{codigo_cvm}",
    response_model=CompanhiaResposta,
    summary="Obter Companhia por Código CVM",
    description="Retorna uma companhia específica a partir do código CVM.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterCompanhiaPorCodigoCvm",
)
def obter_companhia_por_codigo_cvm(
    codigo_cvm: Annotated[
        int,
        Path(
            description="Código CVM da companhia.",
            examples=[25224],
        ),
    ],
    db: DbSession,
) -> CompanhiaResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return CompanhiaResposta.model_validate(companhia)


@router.get(
    "/{cnpj_companhia:path}",
    response_model=CompanhiaResposta,
    summary="Obter Companhia por CNPJ",
    description="Retorna uma companhia específica a partir do CNPJ (formatado ou não).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterCompanhiaPorCnpj",
)
def obter_companhia_por_cnpj(
    cnpj_companhia: Annotated[
        str,
        Path(
            pattern=r"^[0-9./-]+$",
            description="CNPJ da companhia (aceita com ou sem pontuação).",
            examples=["08.773.135/0001-00", "08773135000100"],
        ),
    ],
    db: DbSession,
) -> CompanhiaResposta:
    cnpj = normalizar_cnpj(cnpj_companhia)
    companhia = db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return CompanhiaResposta.model_validate(companhia)
