import re
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Select, case, func, or_, select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.models.fca import FcaValorMobiliario
from app.schemas.companhia import CompanhiaResposta, ListaCompanhiasResposta
from app.schemas.comum import Paginacao
from app.services.normalizacao import normalizar_cnpj

router = APIRouter(prefix="/companhias")

_LOGO_BASE_URL = "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png"
_PADRAO_TICKER_LOGO = re.compile(r"^[A-Z]{4}\d{1,2}$")

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


def _ticker_serve_para_logo(codigo_negociacao: str | None) -> bool:
    if not codigo_negociacao:
        return False
    return bool(_PADRAO_TICKER_LOGO.fullmatch(codigo_negociacao.strip().upper()))


def _montar_logo_url_por_ticker(codigo_negociacao: str | None) -> str | None:
    if not _ticker_serve_para_logo(codigo_negociacao):
        return None
    assert codigo_negociacao is not None
    ticker = codigo_negociacao.strip().upper()
    return f"{_LOGO_BASE_URL}/{ticker[0]}/{ticker}.png"


def _obter_logo_urls_por_cnpj(db: DbSession, cnpjs: list[str]) -> dict[str, str | None]:
    if not cnpjs:
        return {}

    hoje = datetime.now().date()
    registros = (
        db.execute(
            select(FcaValorMobiliario)
            .where(FcaValorMobiliario.cnpj_companhia.in_(cnpjs))
            .where(FcaValorMobiliario.codigo_negociacao.is_not(None))
            .where(or_(FcaValorMobiliario.data_fim_listagem.is_(None), FcaValorMobiliario.data_fim_listagem >= hoje))
            .order_by(
                FcaValorMobiliario.cnpj_companhia.asc(),
                FcaValorMobiliario.data_referencia.desc(),
                FcaValorMobiliario.versao.desc(),
                FcaValorMobiliario.data_inicio_listagem.desc().nullslast(),
                FcaValorMobiliario.codigo_negociacao.asc(),
            )
        )
        .scalars()
        .all()
    )

    logo_por_cnpj: dict[str, str | None] = {cnpj: None for cnpj in cnpjs}

    for registro in registros:
        cnpj = registro.cnpj_companhia
        if logo_por_cnpj.get(cnpj) is not None:
            continue
        logo_url = _montar_logo_url_por_ticker(registro.codigo_negociacao)
        if logo_url is not None:
            logo_por_cnpj[cnpj] = logo_url

    return logo_por_cnpj


def _serializar_companhia(companhia: Companhia, logo_url: str | None) -> CompanhiaResposta:
    return CompanhiaResposta.model_validate(companhia).model_copy(update={"logo_url": logo_url})


@router.get(
    "",
    response_model=ListaCompanhiasResposta,
    summary="Listar Companhias",
    description="Retorna lista paginada de companhias abertas normalizadas. Permite filtragem por CNPJ, código CVM, nome e situação cadastral.",
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
    nome: Annotated[
        str | None,
        Query(
            description="Nome (razão social ou nome comercial) da companhia.",
            examples=["Petrobras"],
        ),
    ] = None,
    situacao_registro: Annotated[
        str | None,
        Query(
            description="Filtrar por situação do registro na CVM.",
            examples=["ATIVO", "SUSPENSO(A) - DECISAO ADM"],
        ),
    ] = None,
    ordenar: Annotated[
        str | None,
        Query(
            description="Ordenação dos resultados: ativa_nome, nome ou codigo_cvm.",
            examples=["ativa_nome", "nome", "codigo_cvm"],
        ),
    ] = "ativa_nome",
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

    if nome:
        busca = f"%{nome}%"
        filtro_nome = (Companhia.denominacao_social.ilike(busca)) | (Companhia.denominacao_comercial.ilike(busca))
        query = query.where(filtro_nome)
        query_total = query_total.where(filtro_nome)

    if situacao_registro:
        query = query.where(Companhia.situacao_registro == situacao_registro)
        query_total = query_total.where(Companhia.situacao_registro == situacao_registro)

    if ordenar == "ativa_nome":
        query = query.order_by(
            case((Companhia.situacao_registro == "ATIVO", 0), else_=1),
            Companhia.denominacao_social
        )
    elif ordenar == "nome":
        query = query.order_by(Companhia.denominacao_social)
    elif ordenar == "codigo_cvm":
        query = query.order_by(Companhia.codigo_cvm)
    else:
        query = query.order_by(Companhia.denominacao_social)

    total = db.scalar(query_total) or 0
    itens = (
        db.execute(
            query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)
        )
        .scalars()
        .all()
    )

    logos_por_cnpj = _obter_logo_urls_por_cnpj(db, [item.cnpj_companhia for item in itens if item.cnpj_companhia])

    return ListaCompanhiasResposta(
        dados=[_serializar_companhia(item, logos_por_cnpj.get(item.cnpj_companhia)) for item in itens],
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
    logo_url = _obter_logo_urls_por_cnpj(db, [companhia.cnpj_companhia]).get(companhia.cnpj_companhia)
    return _serializar_companhia(companhia, logo_url)


# --- EXISTING GET BY CNPJ ENDPOINT (CATCH-ALL) REGISTERED LAST ---

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
            description="CNPJ da companhia (aceita com ou sem pontuação).",
            examples=["08.773.135/0001-00", "08773135000100"],
        ),
    ],
    db: DbSession,
) -> CompanhiaResposta:
    try:
        cnpj = normalizar_cnpj(cnpj_companhia)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.") from exc
    companhia = db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    logo_url = _obter_logo_urls_por_cnpj(db, [companhia.cnpj_companhia]).get(companhia.cnpj_companhia)
    return _serializar_companhia(companhia, logo_url)
