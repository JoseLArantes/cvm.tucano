from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, Select, desc, func, select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.ipe import IpeDocumento
from app.schemas.comum import Paginacao
from app.schemas.ipe import (
    IpeDocumentoAgregado,
    IpeDocumentoResposta,
    ListaIpeDocumentosAgregadosResposta,
    ListaIpeDocumentosResposta,
)
from app.services.normalizacao import normalizar_cnpj

router = APIRouter()

_RESPOSTAS_PADRAO: dict[int | str, dict[str, Any]] = {
    422: {
        "description": "Parâmetros inválidos (filtro, formato ou ordenação).",
        "content": {"application/json": {"example": {"detail": "Campo invalido para ordenacao: campo"}}},
    }
}

ParametroCnpj = Annotated[
    str | None,
    Query(description="CNPJ da companhia (com ou sem pontuação).", examples=["00.000.000/0001-91"]),
]
ParametroCodigoCvm = Annotated[int | None, Query(description="Código CVM da companhia.", examples=[1023])]
ParametroDataInicio = Annotated[
    date | None,
    Query(description="Data inicial do evento no formato ISO (YYYY-MM-DD).", examples=["2025-01-01"]),
]
ParametroDataFim = Annotated[
    date | None,
    Query(description="Data final do evento no formato ISO (YYYY-MM-DD).", examples=["2025-12-31"]),
]
ParametroAnoOrigem = Annotated[int | None, Query(description="Ano do ZIP de origem.", examples=[2025])]
ParametroAnoInicio = Annotated[int | None, Query(description="Ano inicial do ZIP/dados de origem.", examples=[2010])]
ParametroAnoFim = Annotated[int | None, Query(description="Ano final do ZIP/dados de origem.", examples=[2020])]
ParametroVersao = Annotated[int | None, Query(description="Versão do documento IPE.", examples=[1])]


def _col(modelo: type[Any], campo: str) -> Any:
    return getattr(modelo, campo)


def _aplicar_filtros_base(
    query: Select[Any],
    query_total: Select[Any],
    *,
    modelo: type[Any],
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    data_entrega_inicio: date | None,
    data_entrega_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
) -> tuple[Select[Any], Select[Any]]:
    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(_col(modelo, "cnpj_companhia") == cnpj)
        query_total = query_total.where(_col(modelo, "cnpj_companhia") == cnpj)
    if codigo_cvm is not None:
        query = query.where(_col(modelo, "codigo_cvm") == codigo_cvm)
        query_total = query_total.where(_col(modelo, "codigo_cvm") == codigo_cvm)
    if data_referencia_inicio is not None:
        query = query.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
        query_total = query_total.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
    if data_referencia_fim is not None:
        query = query.where(_col(modelo, "data_referencia") <= data_referencia_fim)
        query_total = query_total.where(_col(modelo, "data_referencia") <= data_referencia_fim)
    if data_entrega_inicio is not None:
        query = query.where(_col(modelo, "data_entrega") >= data_entrega_inicio)
        query_total = query_total.where(_col(modelo, "data_entrega") >= data_entrega_inicio)
    if data_entrega_fim is not None:
        query = query.where(_col(modelo, "data_entrega") <= data_entrega_fim)
        query_total = query_total.where(_col(modelo, "data_entrega") <= data_entrega_fim)
    if ano_origem is not None:
        query = query.where(_col(modelo, "ano_origem") == ano_origem)
        query_total = query_total.where(_col(modelo, "ano_origem") == ano_origem)
    if ano_inicio is not None:
        query = query.where(_col(modelo, "ano_origem") >= ano_inicio)
        query_total = query_total.where(_col(modelo, "ano_origem") >= ano_inicio)
    if ano_fim is not None:
        query = query.where(_col(modelo, "ano_origem") <= ano_fim)
        query_total = query_total.where(_col(modelo, "ano_origem") <= ano_fim)
    if versao is not None:
        query = query.where(_col(modelo, "versao") == versao)
        query_total = query_total.where(_col(modelo, "versao") == versao)
    return query, query_total


def _aplicar_ordenacao(
    query: Select[Any],
    *,
    modelo: type[Any],
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> Select[Any]:
    campo = ordenar_por or "-data_entrega"
    direcao_desc = campo.startswith("-")
    campo_limpo = campo[1:] if direcao_desc else campo
    if campo_limpo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo_limpo}")
    coluna = _col(modelo, campo_limpo)
    return query.order_by(coluna.desc() if direcao_desc else coluna.asc())


def _lista_ipe_generica(
    db: DbSession,
    *,
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    data_entrega_inicio: date | None,
    data_entrega_fim: date | None,
    categoria: str | None,
    tipo: str | None,
    especie: str | None,
    assunto: str | None,
    ano_origem: int | None,
    versao: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    ordenar_por: str | None,
) -> tuple[list[IpeDocumentoResposta], int]:
    query: Select[Any] = select(IpeDocumento)
    query_total = select(func.count()).select_from(IpeDocumento)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=IpeDocumento,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        data_entrega_inicio=data_entrega_inicio,
        data_entrega_fim=data_entrega_fim,
        ano_origem=ano_origem,
        versao=versao,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
    )
    for campo, valor in {"categoria": categoria, "tipo": tipo, "especie": especie, "assunto": assunto}.items():
        if valor is not None:
            query = query.where(_col(IpeDocumento, campo) == valor)
            query_total = query_total.where(_col(IpeDocumento, campo) == valor)
    query = _aplicar_ordenacao(
        query,
        modelo=IpeDocumento,
        ordenar_por=ordenar_por,
        campos_permitidos={
            "data_entrega",
            "data_referencia",
            "versao",
            "cnpj_companhia",
            "codigo_cvm",
            "categoria",
            "tipo",
            "especie",
            "assunto",
            "protocolo_entrega",
        },
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return [IpeDocumentoResposta.model_validate(item) for item in itens], total


@router.get(
    "/ipe/documentos",
    response_model=ListaIpeDocumentosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar documentos IPE",
    description=(
        "Retorna uma lista paginada de Informações Periódicas e Eventuais (IPE) "
        "com base nos filtros de período, categoria, assunto, etc."
    ),
)
def listar_documentos_ipe(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    data_entrega_inicio: ParametroDataInicio = None,
    data_entrega_fim: ParametroDataFim = None,
    categoria: Annotated[str | None, Query(description="Filtrar por categoria do documento.")] = None,
    tipo: Annotated[str | None, Query(description="Filtrar por tipo do documento.")] = None,
    especie: Annotated[str | None, Query(description="Filtrar por espécie do documento.")] = None,
    assunto: Annotated[str | None, Query(description="Filtrar por assunto do documento.")] = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_entrega, data_referencia, versao, cnpj_companhia, codigo_cvm, categoria."),
    ] = "-data_entrega",
) -> ListaIpeDocumentosResposta:
    dados, total = _lista_ipe_generica(
        db,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        data_entrega_inicio=data_entrega_inicio,
        data_entrega_fim=data_entrega_fim,
        categoria=categoria,
        tipo=tipo,
        especie=especie,
        assunto=assunto,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
    )
    return ListaIpeDocumentosResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/ipe/documentos/agregados",
    response_model=ListaIpeDocumentosAgregadosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Obter agregados de documentos IPE",
    description="Retorna a contagem de documentos IPE agrupados por ano, categoria, tipo ou espécie.",
)
def obter_documentos_ipe_agregados(
    db: DbSession,
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    data_entrega_inicio: ParametroDataInicio = None,
    data_entrega_fim: ParametroDataFim = None,
    categoria: Annotated[str | None, Query(description="Filtrar por categoria do documento.")] = None,
    tipo: Annotated[str | None, Query(description="Filtrar por tipo do documento.")] = None,
    especie: Annotated[str | None, Query(description="Filtrar por espécie do documento.")] = None,
    assunto: Annotated[str | None, Query(description="Filtrar por assunto do documento.")] = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    agrupar_por: Annotated[
        str,
        Query(
            description="Campos para agrupamento separados por vírgula. Suporta: ano, categoria, tipo, especie.",
            examples=["ano,categoria", "categoria,tipo"],
        ),
    ] = "ano,categoria",
) -> ListaIpeDocumentosAgregadosResposta:
    query_total = select(func.count()).select_from(IpeDocumento)
    
    # We will reuse the filters function by creating dummy select queries
    dummy_q = select(IpeDocumento)
    dummy_q, query_total = _aplicar_filtros_base(
        dummy_q,
        query_total,
        modelo=IpeDocumento,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        data_entrega_inicio=data_entrega_inicio,
        data_entrega_fim=data_entrega_fim,
        ano_origem=ano_origem,
        versao=versao,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
    )
    
    # Reapply filters to match dummy_q
    for campo, valor in {"categoria": categoria, "tipo": tipo, "especie": especie, "assunto": assunto}.items():
        if valor is not None:
            dummy_q = dummy_q.where(_col(IpeDocumento, campo) == valor)

    # Parse groupings
    group_cols: list[Any] = []
    select_cols: list[Any] = []
    
    for field in agrupar_por.split(","):
        field = field.strip()
        if field == "ano":
            ano_col: Any = func.extract('year', IpeDocumento.data_referencia).cast(Integer).label("ano")
            group_cols.append(ano_col)
            select_cols.append(ano_col)
        elif field in ("categoria", "tipo", "especie", "assunto"):
            text_col: Any = getattr(IpeDocumento, field)
            group_cols.append(text_col)
            select_cols.append(text_col)
            
    if not group_cols:
        col: Any = IpeDocumento.categoria
        group_cols.append(col)
        select_cols.append(col)
        
    # Build final query based on filters applied to dummy_q
    final_query = select(*select_cols, func.count(IpeDocumento.id).label("total"))
    
    # Extract where clause from dummy_q
    if dummy_q._where_criteria:
        for criteria in dummy_q._where_criteria:
            final_query = final_query.where(criteria)
            
    final_query = final_query.group_by(*group_cols).order_by(desc("total"))
    
    rows = db.execute(final_query).all()
    
    dados: list[IpeDocumentoAgregado] = []
    for r in rows:
        r_dict = dict(r._mapping)
        dados.append(IpeDocumentoAgregado(**r_dict))
        
    return ListaIpeDocumentosAgregadosResposta(dados=dados)
