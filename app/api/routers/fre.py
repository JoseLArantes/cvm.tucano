from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, PaginacaoQuery
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.schemas.comum import Paginacao
from app.schemas.fre import (
    FreAuditorResposta,
    FreCapitalSocialResposta,
    FreDocumentoResposta,
    FreEmpregadoPosicaoGeneroResposta,
    FrePosicaoAcionariaResposta,
    FreRemuneracaoTotalOrgaoResposta,
    ListaFreAuditoresResposta,
    ListaFreCapitalSocialResposta,
    ListaFreDocumentosResposta,
    ListaFreEmpregadoPosicaoGeneroResposta,
    ListaFrePosicaoAcionariaResposta,
    ListaFreRemuneracaoTotalOrgaoResposta,
)
from app.services.normalizacao import normalizar_cnpj

router = APIRouter()

_RESPOSTAS_PADRAO = {
    422: {
        "description": "Parâmetros inválidos (filtro, formato ou ordenação).",
        "content": {"application/json": {"example": {"detail": "Campo invalido para ordenacao: campo"}}},
    }
}

ParametroCnpj = Annotated[
    str | None,
    Query(description="CNPJ da companhia (com ou sem pontuação).", examples=["08.773.135/0001-00"]),
]
ParametroCodigoCvm = Annotated[int | None, Query(description="Código CVM da companhia.", examples=[25224])]
ParametroDataInicio = Annotated[
    date | None,
    Query(description="Data inicial de referência no formato ISO (YYYY-MM-DD).", examples=["2025-01-01"]),
]
ParametroDataFim = Annotated[
    date | None,
    Query(description="Data final de referência no formato ISO (YYYY-MM-DD).", examples=["2025-12-31"]),
]
ParametroAnoOrigem = Annotated[int | None, Query(description="Ano do ZIP de origem.", examples=[2025])]
ParametroVersao = Annotated[int | None, Query(description="Versão do documento FRE.", examples=[1])]
ParametroIdDocumento = Annotated[int | None, Query(description="ID do documento FRE.", examples=[12345])]


def _col(modelo: type[Any], campo: str) -> Any:
    return getattr(modelo, campo)


def _aplicar_filtros_base(
    query: Select[Any],
    query_total: Select[Any],
    *,
    modelo: type[Any],
    cnpj_companhia: str | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    id_documento: int | None,
) -> tuple[Select[Any], Select[Any]]:
    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(_col(modelo, "cnpj_companhia") == cnpj)
        query_total = query_total.where(_col(modelo, "cnpj_companhia") == cnpj)
    if data_referencia_inicio is not None:
        query = query.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
        query_total = query_total.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
    if data_referencia_fim is not None:
        query = query.where(_col(modelo, "data_referencia") <= data_referencia_fim)
        query_total = query_total.where(_col(modelo, "data_referencia") <= data_referencia_fim)
    if ano_origem is not None:
        query = query.where(_col(modelo, "ano_origem") == ano_origem)
        query_total = query_total.where(_col(modelo, "ano_origem") == ano_origem)
    if versao is not None:
        query = query.where(_col(modelo, "versao") == versao)
        query_total = query_total.where(_col(modelo, "versao") == versao)
    if id_documento is not None:
        query = query.where(_col(modelo, "id_documento") == id_documento)
        query_total = query_total.where(_col(modelo, "id_documento") == id_documento)
    return query, query_total


def _aplicar_ordenacao(
    query: Select[Any],
    *,
    modelo: type[Any],
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> Select[Any]:
    if not ordenar_por:
        return query
    desc = ordenar_por.startswith("-")
    campo = ordenar_por[1:] if desc else ordenar_por
    if campo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo}")
    coluna = _col(modelo, campo)
    return query.order_by(coluna.desc() if desc else coluna.asc())


@router.get(
    "/fre/documentos",
    response_model=ListaFreDocumentosResposta,
    summary="Listar Documentos FRE",
    description="Retorna documentos principais FRE (`fre_cia_aberta_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDocumentosFre",
)
def listar_documentos_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, codigo_cvm, id_documento."),
    ] = "-data_referencia",
) -> ListaFreDocumentosResposta:
    query: Select[Any] = select(FreDocumento)
    query_total = select(func.count()).select_from(FreDocumento)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=FreDocumento,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
    )
    if codigo_cvm is not None:
        query = query.where(FreDocumento.codigo_cvm == codigo_cvm)
        query_total = query_total.where(FreDocumento.codigo_cvm == codigo_cvm)
    query = _aplicar_ordenacao(
        query,
        modelo=FreDocumento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_cvm", "id_documento"},
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaFreDocumentosResposta(
        dados=[FreDocumentoResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


def _lista_fre_generica(
    db: Session,
    *,
    modelo: type[Any],
    schema: type[Any],
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    id_documento: int | None,
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> tuple[list[Any], int]:
    query: Select[Any] = select(modelo)
    query_total = select(func.count()).select_from(modelo)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=modelo,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
    )
    query = _aplicar_ordenacao(query, modelo=modelo, ordenar_por=ordenar_por, campos_permitidos=campos_permitidos)
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return [schema.model_validate(item) for item in itens], total


@router.get(
    "/fre/auditores",
    response_model=ListaFreAuditoresResposta,
    summary="Listar Auditores FRE",
    description="Retorna registros de auditores (`fre_cia_aberta_auditor_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAuditoresFre",
)
def listar_auditores_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, id_auditor."),
    ] = "-data_referencia",
) -> ListaFreAuditoresResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAuditor,
        schema=FreAuditorResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_auditor"},
    )
    return ListaFreAuditoresResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/capital-social",
    response_model=ListaFreCapitalSocialResposta,
    summary="Listar Capital Social FRE",
    description="Retorna registros de capital social (`fre_cia_aberta_capital_social_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCapitalSocialFre",
)
def listar_capital_social_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_capital_social.")
    ] = "-data_referencia",
) -> ListaFreCapitalSocialResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreCapitalSocial,
        schema=FreCapitalSocialResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_capital_social"},
    )
    return ListaFreCapitalSocialResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/posicao-acionaria",
    response_model=ListaFrePosicaoAcionariaResposta,
    summary="Listar Posição Acionária FRE",
    description="Retorna posição acionária (`fre_cia_aberta_posicao_acionaria_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPosicaoAcionariaFre",
)
def listar_posicao_acionaria_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, id_acionista."),
    ] = "-data_referencia",
) -> ListaFrePosicaoAcionariaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FrePosicaoAcionaria,
        schema=FrePosicaoAcionariaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_acionista"},
    )
    return ListaFrePosicaoAcionariaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/remuneracao/total-por-orgao",
    response_model=ListaFreRemuneracaoTotalOrgaoResposta,
    summary="Listar Remuneração Total por Órgão FRE",
    description=(
        "Retorna remuneração total por órgão de administração "
        "(`fre_cia_aberta_remuneracao_total_orgao_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRemuneracaoTotalOrgaoFre",
)
def listar_remuneracao_total_orgao_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreRemuneracaoTotalOrgaoResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRemuneracaoTotalOrgao,
        schema=FreRemuneracaoTotalOrgaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
    )
    return ListaFreRemuneracaoTotalOrgaoResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/posicao-genero",
    response_model=ListaFreEmpregadoPosicaoGeneroResposta,
    summary="Listar Empregados por Posição e Gênero FRE",
    description=(
        "Retorna distribuição de empregados por posição e gênero "
        "(`fre_cia_aberta_empregado_posicao_declaracao_genero_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPosicaoGeneroFre",
)
def listar_empregados_posicao_genero_fre(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, posicao.")]
    = "-data_referencia",
) -> ListaFreEmpregadoPosicaoGeneroResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPosicaoGenero,
        schema=FreEmpregadoPosicaoGeneroResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "posicao"},
    )
    return ListaFreEmpregadoPosicaoGeneroResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )
