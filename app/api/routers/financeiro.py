from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, PaginacaoQuery
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.schemas.comum import Paginacao
from app.schemas.financeiro import (
    ComposicaoCapitalResposta,
    DemonstracaoFinanceiraResposta,
    DocumentoFinanceiroResposta,
    ListaComposicoesCapitalResposta,
    ListaDemonstracoesFinanceirasResposta,
    ListaDocumentosFinanceirosResposta,
    ListaPareceresFinanceirosResposta,
    ParecerFinanceiroResposta,
)
from app.services.financeiro_mapas import DEMONSTRACOES
from app.services.normalizacao import normalizar_cnpj

router = APIRouter()

ParametroCnpj = Annotated[
    str | None,
    Query(
        description="CNPJ da companhia (com ou sem pontuação).",
        examples=["08.773.135/0001-00", "08773135000100"],
    ),
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
ParametroVersao = Annotated[int | None, Query(description="Versão do formulário.", examples=[1, 2])]
ParametroCodigoConta = Annotated[str | None, Query(description="Código da conta contábil.", examples=["3.01"])]
ParametroIdDocumento = Annotated[int | None, Query(description="ID do documento CVM.", examples=[123456])]
ParametroOrdenacaoDocumentos = Annotated[
    str | None,
    Query(
        description=(
            "Campo de ordenação. Prefixe com '-' para ordem decrescente. "
            "Permitidos em documentos: data_referencia, versao, cnpj_companhia, "
            "codigo_cvm, data_recebimento, id_documento."
        ),
        examples=["-data_referencia", "versao"],
    ),
]
ParametroOrdenacaoDemonstracoes = Annotated[
    str | None,
    Query(
        description=(
            "Campo de ordenação. Prefixe com '-' para ordem decrescente. "
            "Permitidos em demonstrações: data_referencia, versao, cnpj_companhia, "
            "codigo_conta, valor_conta."
        ),
        examples=["-data_referencia", "codigo_conta"],
    ),
]
ParametroOrdenacaoComum = Annotated[
    str | None,
    Query(
        description=(
            "Campo de ordenação. Prefixe com '-' para ordem decrescente. "
            "Permitidos: data_referencia, versao, cnpj_companhia."
        ),
        examples=["-data_referencia", "cnpj_companhia"],
    ),
]

_RESPOSTAS_PADRAO = {
    422: {
        "description": "Parâmetros inválidos (filtro, formato ou ordenação).",
        "content": {"application/json": {"example": {"detail": "Campo invalido para ordenacao: campo"}}},
    }
}


def _col(modelo: type[Any], campo: str) -> Any:
    return getattr(modelo, campo)


def _aplicar_ordenacao(
    query: Select[Any],
    *,
    modelo: type[Any],
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> Select[Any]:
    if not ordenar_por:
        return query
    direcao_desc = ordenar_por.startswith("-")
    campo = ordenar_por[1:] if direcao_desc else ordenar_por
    if campo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo}")
    coluna = getattr(modelo, campo)
    return query.order_by(coluna.desc() if direcao_desc else coluna.asc())


def _filtrar_periodo(
    query: Select[Any],
    query_total: Select[Any],
    *,
    modelo: type[Any],
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
) -> tuple[Select[Any], Select[Any]]:
    if data_referencia_inicio is not None:
        query = query.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
        query_total = query_total.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
    if data_referencia_fim is not None:
        query = query.where(_col(modelo, "data_referencia") <= data_referencia_fim)
        query_total = query_total.where(_col(modelo, "data_referencia") <= data_referencia_fim)
    return query, query_total


def _filtrar_basico(
    query: Select[Any],
    query_total: Select[Any],
    *,
    modelo: type[Any],
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    ano_origem: int | None,
    versao: int | None,
) -> tuple[Select[Any], Select[Any]]:
    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(_col(modelo, "cnpj_companhia") == cnpj)
        query_total = query_total.where(_col(modelo, "cnpj_companhia") == cnpj)
    if codigo_cvm is not None:
        query = query.where(_col(modelo, "codigo_cvm") == codigo_cvm)
        query_total = query_total.where(_col(modelo, "codigo_cvm") == codigo_cvm)
    if ano_origem is not None:
        query = query.where(_col(modelo, "ano_origem") == ano_origem)
        query_total = query_total.where(_col(modelo, "ano_origem") == ano_origem)
    if versao is not None:
        query = query.where(_col(modelo, "versao") == versao)
        query_total = query_total.where(_col(modelo, "versao") == versao)
    return query, query_total


@router.get(
    "/dfp/documentos",
    response_model=ListaDocumentosFinanceirosResposta,
    summary="Listar Documentos DFP",
    description=(
        "Retorna os documentos principais DFP (`dfp_cia_aberta_{ano}.csv`) "
        "com paginação e filtros de companhia, período, versão e ID de documento."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDocumentosDfp",
)
def listar_documentos_dfp(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: ParametroOrdenacaoDocumentos = "-data_referencia",
) -> ListaDocumentosFinanceirosResposta:
    return _listar_documentos(
        db,
        tipo_formulario="DFP",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
    )


@router.get(
    "/itr/documentos",
    response_model=ListaDocumentosFinanceirosResposta,
    summary="Listar Documentos ITR",
    description=(
        "Retorna os documentos principais ITR (`itr_cia_aberta_{ano}.csv`) "
        "com paginação e filtros de companhia, período, versão e ID de documento."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDocumentosItr",
)
def listar_documentos_itr(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    id_documento: ParametroIdDocumento = None,
    ordenar_por: ParametroOrdenacaoDocumentos = "-data_referencia",
) -> ListaDocumentosFinanceirosResposta:
    return _listar_documentos(
        db,
        tipo_formulario="ITR",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
    )


def _listar_documentos(
    db: Session,
    *,
    tipo_formulario: str,
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    id_documento: int | None,
    ordenar_por: str | None,
) -> ListaDocumentosFinanceirosResposta:
    query: Select[Any] = select(DocumentoFinanceiro).where(DocumentoFinanceiro.tipo_formulario == tipo_formulario)
    query_total = select(func.count()).select_from(DocumentoFinanceiro).where(
        DocumentoFinanceiro.tipo_formulario == tipo_formulario
    )
    query, query_total = _filtrar_basico(
        query,
        query_total,
        modelo=DocumentoFinanceiro,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        ano_origem=ano_origem,
        versao=versao,
    )
    query, query_total = _filtrar_periodo(
        query,
        query_total,
        modelo=DocumentoFinanceiro,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
    )
    if id_documento is not None:
        query = query.where(DocumentoFinanceiro.id_documento == id_documento)
        query_total = query_total.where(DocumentoFinanceiro.id_documento == id_documento)
    query = _aplicar_ordenacao(
        query,
        modelo=DocumentoFinanceiro,
        ordenar_por=ordenar_por,
        campos_permitidos={
            "data_referencia",
            "versao",
            "cnpj_companhia",
            "codigo_cvm",
            "data_recebimento",
            "id_documento",
        },
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaDocumentosFinanceirosResposta(
        dados=[DocumentoFinanceiroResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


def _listar_demonstracoes(
    db: Session,
    *,
    tipo_formulario: str,
    tipo_demonstracao: str,
    escopo_demonstracao: str,
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    codigo_conta: str | None,
    ordenar_por: str | None,
) -> ListaDemonstracoesFinanceirasResposta:
    query: Select[Any] = select(DemonstracaoFinanceira).where(
        DemonstracaoFinanceira.tipo_formulario == tipo_formulario,
        DemonstracaoFinanceira.tipo_demonstracao == tipo_demonstracao,
        DemonstracaoFinanceira.escopo_demonstracao == escopo_demonstracao,
    )
    query_total = select(func.count()).select_from(DemonstracaoFinanceira).where(
        DemonstracaoFinanceira.tipo_formulario == tipo_formulario,
        DemonstracaoFinanceira.tipo_demonstracao == tipo_demonstracao,
        DemonstracaoFinanceira.escopo_demonstracao == escopo_demonstracao,
    )
    query, query_total = _filtrar_basico(
        query,
        query_total,
        modelo=DemonstracaoFinanceira,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        ano_origem=ano_origem,
        versao=versao,
    )
    query, query_total = _filtrar_periodo(
        query,
        query_total,
        modelo=DemonstracaoFinanceira,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
    )
    if codigo_conta:
        query = query.where(DemonstracaoFinanceira.codigo_conta == codigo_conta)
        query_total = query_total.where(DemonstracaoFinanceira.codigo_conta == codigo_conta)
    query = _aplicar_ordenacao(
        query,
        modelo=DemonstracaoFinanceira,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_conta", "valor_conta"},
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaDemonstracoesFinanceirasResposta(
        dados=[DemonstracaoFinanceiraResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/dfp/composicao-capital",
    response_model=ListaComposicoesCapitalResposta,
    summary="Listar Composição de Capital DFP",
    description=(
        "Retorna dados de composição de capital do DFP "
        "(`dfp_cia_aberta_composicao_capital_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarComposicaoCapitalDfp",
)
def listar_composicao_capital_dfp(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    ordenar_por: ParametroOrdenacaoComum = "-data_referencia",
) -> ListaComposicoesCapitalResposta:
    return _listar_composicao_capital(
        db,
        tipo_formulario="DFP",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        ordenar_por=ordenar_por,
    )


@router.get(
    "/itr/composicao-capital",
    response_model=ListaComposicoesCapitalResposta,
    summary="Listar Composição de Capital ITR",
    description=(
        "Retorna dados de composição de capital do ITR "
        "(`itr_cia_aberta_composicao_capital_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarComposicaoCapitalItr",
)
def listar_composicao_capital_itr(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    ordenar_por: ParametroOrdenacaoComum = "-data_referencia",
) -> ListaComposicoesCapitalResposta:
    return _listar_composicao_capital(
        db,
        tipo_formulario="ITR",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        ordenar_por=ordenar_por,
    )


def _listar_composicao_capital(
    db: Session,
    *,
    tipo_formulario: str,
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    ordenar_por: str | None,
) -> ListaComposicoesCapitalResposta:
    query: Select[Any] = select(ComposicaoCapital).where(ComposicaoCapital.tipo_formulario == tipo_formulario)
    query_total = select(func.count()).select_from(ComposicaoCapital).where(
        ComposicaoCapital.tipo_formulario == tipo_formulario
    )
    query, query_total = _filtrar_basico(
        query,
        query_total,
        modelo=ComposicaoCapital,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        ano_origem=ano_origem,
        versao=versao,
    )
    query, query_total = _filtrar_periodo(
        query,
        query_total,
        modelo=ComposicaoCapital,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
    )
    query = _aplicar_ordenacao(
        query,
        modelo=ComposicaoCapital,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia"},
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaComposicoesCapitalResposta(
        dados=[ComposicaoCapitalResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/dfp/pareceres",
    response_model=ListaPareceresFinanceirosResposta,
    summary="Listar Pareceres DFP",
    description=(
        "Retorna pareceres e declarações do DFP "
        "(`dfp_cia_aberta_parecer_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPareceresDfp",
)
def listar_pareceres_dfp(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    ordenar_por: ParametroOrdenacaoComum = "-data_referencia",
) -> ListaPareceresFinanceirosResposta:
    return _listar_pareceres(
        db,
        tipo_formulario="DFP",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        ordenar_por=ordenar_por,
    )


@router.get(
    "/itr/pareceres",
    response_model=ListaPareceresFinanceirosResposta,
    summary="Listar Pareceres ITR",
    description=(
        "Retorna pareceres e declarações do ITR "
        "(`itr_cia_aberta_parecer_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPareceresItr",
)
def listar_pareceres_itr(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    versao: ParametroVersao = None,
    ordenar_por: ParametroOrdenacaoComum = "-data_referencia",
) -> ListaPareceresFinanceirosResposta:
    return _listar_pareceres(
        db,
        tipo_formulario="ITR",
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        versao=versao,
        ordenar_por=ordenar_por,
    )


def _listar_pareceres(
    db: Session,
    *,
    tipo_formulario: str,
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    ordenar_por: str | None,
) -> ListaPareceresFinanceirosResposta:
    query: Select[Any] = select(ParecerFinanceiro).where(ParecerFinanceiro.tipo_formulario == tipo_formulario)
    query_total = select(func.count()).select_from(ParecerFinanceiro).where(
        ParecerFinanceiro.tipo_formulario == tipo_formulario
    )
    query, query_total = _filtrar_basico(
        query,
        query_total,
        modelo=ParecerFinanceiro,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        ano_origem=ano_origem,
        versao=versao,
    )
    query, query_total = _filtrar_periodo(
        query,
        query_total,
        modelo=ParecerFinanceiro,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
    )
    query = _aplicar_ordenacao(
        query,
        modelo=ParecerFinanceiro,
        ordenar_por=ordenar_por,
        campos_permitidos={
            "data_referencia",
            "versao",
            "cnpj_companhia",
            "numero_item_parecer_declaracao",
        },
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaPareceresFinanceirosResposta(
        dados=[ParecerFinanceiroResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


def _criar_endpoint_demonstracao(tipo_formulario: str, rota: str, tipo_demonstracao: str, escopo: str) -> None:
    caminho = f"/{tipo_formulario.lower()}/{rota}/{escopo}"
    response_model = ListaDemonstracoesFinanceirasResposta
    tipo_demonstracao_legivel = tipo_demonstracao.replace("_", " ")

    def endpoint(
        db: DbSession,
        paginacao: Annotated[PaginacaoQuery, Depends()],
        cnpj_companhia: ParametroCnpj = None,
        codigo_cvm: ParametroCodigoCvm = None,
        data_referencia_inicio: ParametroDataInicio = None,
        data_referencia_fim: ParametroDataFim = None,
        ano_origem: ParametroAnoOrigem = None,
        versao: ParametroVersao = None,
        codigo_conta: ParametroCodigoConta = None,
        ordenar_por: ParametroOrdenacaoDemonstracoes = "-data_referencia",
    ) -> ListaDemonstracoesFinanceirasResposta:
        return _listar_demonstracoes(
            db,
            tipo_formulario=tipo_formulario,
            tipo_demonstracao=tipo_demonstracao,
            escopo_demonstracao=escopo,
            paginacao=paginacao,
            cnpj_companhia=cnpj_companhia,
            codigo_cvm=codigo_cvm,
            data_referencia_inicio=data_referencia_inicio,
            data_referencia_fim=data_referencia_fim,
            ano_origem=ano_origem,
            versao=versao,
            codigo_conta=codigo_conta,
            ordenar_por=ordenar_por,
        )

    endpoint.__name__ = f"listar_{tipo_formulario.lower()}_{tipo_demonstracao}_{escopo}"
    router.get(
        caminho,
        response_model=response_model,
        summary=f"Listar {tipo_formulario} - {tipo_demonstracao_legivel} ({escopo})",
        description=(
            f"Retorna linhas da demonstração `{tipo_demonstracao}` no escopo `{escopo}` "
            f"para o formulário {tipo_formulario}. "
            "Suporta filtros por companhia, período, versão, ano de origem e código da conta."
        ),
        responses=_RESPOSTAS_PADRAO,
        operation_id=(
            f"listar{tipo_formulario.title()}{tipo_demonstracao.title().replace('_', '')}"
            f"{escopo.title()}"
        ),
    )(endpoint)


for item in DEMONSTRACOES:
    for escopo in ("consolidado", "individual"):
        _criar_endpoint_demonstracao(
            tipo_formulario="DFP",
            rota=item["rota"],
            tipo_demonstracao=item["tipo"],
            escopo=escopo,
        )
        _criar_endpoint_demonstracao(
            tipo_formulario="ITR",
            rota=item["rota"],
            tipo_demonstracao=item["tipo"],
            escopo=escopo,
        )
