from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.models.vlmo import VlmoConsolidado, VlmoDocumento
from app.schemas.comum import Paginacao
from app.schemas.vlmo import (
    ListaVlmoConsolidadoResposta,
    ListaVlmoDocumentosResposta,
    VlmoConsolidadoResposta,
    VlmoDocumentoResposta,
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
    Query(description="Data inicial de referência no formato ISO (YYYY-MM-DD).", examples=["2025-01-01"]),
]
ParametroDataFim = Annotated[
    date | None,
    Query(description="Data final de referência no formato ISO (YYYY-MM-DD).", examples=["2025-12-31"]),
]
ParametroDataMovimentacaoInicio = Annotated[
    date | None,
    Query(description="Data inicial de movimentação no formato ISO (YYYY-MM-DD).", examples=["2025-01-01"]),
]
ParametroDataMovimentacaoFim = Annotated[
    date | None,
    Query(description="Data final de movimentação no formato ISO (YYYY-MM-DD).", examples=["2025-12-31"]),
]
ParametroAnoOrigem = Annotated[int | None, Query(description="Ano do ZIP de origem.", examples=[2025])]
ParametroAnoInicio = Annotated[int | None, Query(description="Ano inicial do ZIP/dados de origem.", examples=[2010])]
ParametroAnoFim = Annotated[int | None, Query(description="Ano final do ZIP/dados de origem.", examples=[2020])]
ParametroVersao = Annotated[int | None, Query(description="Versão do documento VLMO.", examples=[1])]


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
    ano_origem: int | None,
    versao: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
) -> tuple[Select[Any], Select[Any]]:
    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(_col(modelo, "cnpj_companhia") == cnpj)
        query_total = query_total.where(_col(modelo, "cnpj_companhia") == cnpj)
    if codigo_cvm is not None and hasattr(modelo, "codigo_cvm"):
        query = query.where(_col(modelo, "codigo_cvm") == codigo_cvm)
        query_total = query_total.where(_col(modelo, "codigo_cvm") == codigo_cvm)
    if data_referencia_inicio is not None:
        query = query.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
        query_total = query_total.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
    if data_referencia_fim is not None:
        query = query.where(_col(modelo, "data_referencia") <= data_referencia_fim)
        query_total = query_total.where(_col(modelo, "data_referencia") <= data_referencia_fim)
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
    campo_padrao: str,
) -> Select[Any]:
    campo = ordenar_por or campo_padrao
    direcao_desc = campo.startswith("-")
    campo_limpo = campo[1:] if direcao_desc else campo
    if campo_limpo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo_limpo}")
    coluna = _col(modelo, campo_limpo)
    return query.order_by(coluna.desc() if direcao_desc else coluna.asc())


def _listar_generico(
    db: DbSession,
    *,
    modelo: type[Any],
    schema: type[Any],
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    ordenar_por: str | None,
    campo_padrao: str,
    campos_permitidos: set[str],
    filtros_adicionais: dict[str, Any] | None = None,
    data_movimentacao_inicio: date | None = None,
    data_movimentacao_fim: date | None = None,
) -> tuple[list[Any], int]:
    if codigo_cvm is not None and not cnpj_companhia:
        cnpj_resolvido = db.scalar(select(Companhia.cnpj_companhia).where(Companhia.codigo_cvm == codigo_cvm))
        if cnpj_resolvido:
            cnpj_companhia = cnpj_resolvido
        elif not hasattr(modelo, "codigo_cvm"):
            return [], 0

    query: Select[Any] = select(modelo)
    query_total = select(func.count()).select_from(modelo)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=modelo,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
    )
    if filtros_adicionais:
        for campo, valor in filtros_adicionais.items():
            if valor is None:
                continue
            query = query.where(_col(modelo, campo) == valor)
            query_total = query_total.where(_col(modelo, campo) == valor)
    if data_movimentacao_inicio is not None and hasattr(modelo, "data_movimentacao"):
        query = query.where(_col(modelo, "data_movimentacao") >= data_movimentacao_inicio)
        query_total = query_total.where(_col(modelo, "data_movimentacao") >= data_movimentacao_inicio)
    if data_movimentacao_fim is not None and hasattr(modelo, "data_movimentacao"):
        query = query.where(_col(modelo, "data_movimentacao") <= data_movimentacao_fim)
        query_total = query_total.where(_col(modelo, "data_movimentacao") <= data_movimentacao_fim)
    query = _aplicar_ordenacao(
        query,
        modelo=modelo,
        ordenar_por=ordenar_por,
        campos_permitidos=campos_permitidos,
        campo_padrao=campo_padrao,
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return [schema.model_validate(item) for item in itens], total


@router.get(
    "/vlmo/documentos",
    response_model=ListaVlmoDocumentosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar documentos VLMO",
    description=(
        "Retorna uma lista paginada de cabeçalhos de documentos de Valores Mobiliários "
        "Negociados e Detidos (VLMO) com base nos filtros informados."
    ),
)
def listar_documentos_vlmo(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    categoria: Annotated[str | None, Query(description="Filtrar por categoria do documento.")] = None,
    tipo: Annotated[str | None, Query(description="Filtrar por tipo do documento.")] = None,
    ordenar_por: Annotated[
        str | None,
        Query(
            description=("Campos: data_entrega, data_referencia, versao, cnpj_companhia, codigo_cvm, categoria, tipo.")
        ),
    ] = "-data_entrega",
) -> ListaVlmoDocumentosResposta:
    dados, total = _listar_generico(
        db,
        modelo=VlmoDocumento,
        schema=VlmoDocumentoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campo_padrao="-data_entrega",
        campos_permitidos={
            "data_entrega",
            "data_referencia",
            "versao",
            "cnpj_companhia",
            "codigo_cvm",
            "categoria",
            "tipo",
        },
        filtros_adicionais={"categoria": categoria, "tipo": tipo},
    )
    return ListaVlmoDocumentosResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/vlmo/consolidado",
    response_model=ListaVlmoConsolidadoResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar negociações consolidadas VLMO",
    description=(
        "Retorna posições consolidadas e movimentações detalhadas de valores mobiliários "
        "detidos por administradores, controladores e pessoas vinculadas (VLMO)."
    ),
)
def listar_consolidado_vlmo(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    data_movimentacao_inicio: ParametroDataMovimentacaoInicio = None,
    data_movimentacao_fim: ParametroDataMovimentacaoFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    tipo_empresa: Annotated[str | None, Query(description="Filtrar por tipo da empresa relacionada.")] = None,
    empresa: Annotated[str | None, Query(description="Filtrar por empresa relacionada.")] = None,
    tipo_cargo: Annotated[str | None, Query(description="Filtrar por tipo de cargo.")] = None,
    tipo_movimentacao: Annotated[str | None, Query(description="Filtrar por tipo de movimentação.")] = None,
    tipo_operacao: Annotated[str | None, Query(description="Filtrar por tipo de operação.")] = None,
    tipo_ativo: Annotated[str | None, Query(description="Filtrar por tipo de ativo.")] = None,
    caracteristica_valor_mobiliario: Annotated[
        str | None, Query(description="Filtrar por característica do valor mobiliário.")
    ] = None,
    intermediario: Annotated[str | None, Query(description="Filtrar por intermediário.")] = None,
    ordenar_por: Annotated[
        str | None,
        Query(
            description=(
                "Campos: data_referencia, data_movimentacao, versao, cnpj_companhia, "
                "tipo_ativo, tipo_operacao, tipo_movimentacao, empresa."
            )
        ),
    ] = "-data_movimentacao",
) -> ListaVlmoConsolidadoResposta:
    dados, total = _listar_generico(
        db,
        modelo=VlmoConsolidado,
        schema=VlmoConsolidadoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campo_padrao="-data_movimentacao",
        campos_permitidos={
            "data_referencia",
            "data_movimentacao",
            "versao",
            "cnpj_companhia",
            "tipo_ativo",
            "tipo_operacao",
            "tipo_movimentacao",
            "empresa",
        },
        filtros_adicionais={
            "tipo_empresa": tipo_empresa,
            "empresa": empresa,
            "tipo_cargo": tipo_cargo,
            "tipo_movimentacao": tipo_movimentacao,
            "tipo_operacao": tipo_operacao,
            "tipo_ativo": tipo_ativo,
            "caracteristica_valor_mobiliario": caracteristica_valor_mobiliario,
            "intermediario": intermediario,
        },
        data_movimentacao_inicio=data_movimentacao_inicio,
        data_movimentacao_fim=data_movimentacao_fim,
    )
    return ListaVlmoConsolidadoResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )
