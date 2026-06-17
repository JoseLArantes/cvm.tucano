from typing import Annotated, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Select, func, select, case

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.schemas.companhia import CompanhiaResposta, ListaCompanhiasResposta
from app.schemas.comum import Paginacao
from app.services.normalizacao import normalizar_cnpj

# Import analysis schemas and services
from app.schemas.analise import (
    OverviewAnaliseResposta,
    FinanceiroAnaliseResposta,
    ComparativoAnaliseResposta,
    EventoLinhaTempo,
    PessoasRemuneracaoResposta,
    MercadoInsidersResposta,
    AnaliseConsolidadaResposta
)
from app.services.analise import (
    obter_overview,
    obter_financeiro,
    obter_comparativo,
    obter_eventos,
    obter_pessoas_remuneracao,
    obter_mercado_insiders
)

router = APIRouter(prefix="/companhias")

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


# --- NEW ANALYSIS ENDPOINTS ---

@router.get(
    "/{codigo_cvm}/analise/overview",
    response_model=OverviewAnaliseResposta,
    summary="Visão Geral de Análise da Companhia",
    description="Retorna cobertura anual de dados, frescor das fontes e alertas cadastrais.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseOverview",
)
def obter_analise_overview_endpoint(codigo_cvm: int, db: DbSession) -> OverviewAnaliseResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return obter_overview(db, companhia)


@router.get(
    "/{codigo_cvm}/analise/financeiro",
    response_model=FinanceiroAnaliseResposta,
    summary="Análise Financeira com Proveniência",
    description="Retorna métricas financeiras anuais e trimestrais normalizadas com variação YoY/QoQ/CAGR e proveniência.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseFinanceiro",
)
def obter_analise_financeiro_endpoint(
    codigo_cvm: int,
    db: DbSession,
    horizonte: str = Query("5a", description="Horizonte de anos para análise (5a, 10a, todos)"),
    periodicidade: str = Query("anual", description="Tipo de formulários (anual, trimestral, todos)")
) -> FinanceiroAnaliseResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return obter_financeiro(db, companhia, horizonte=horizonte, periodicidade=periodicidade)


@router.get(
    "/{codigo_cvm}/analise/comparativo",
    response_model=ComparativoAnaliseResposta,
    summary="Análise Comparativa Anual",
    description="Compara o desempenho financeiro, composição de capital e governança entre dois anos específicos.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseComparativo",
)
def obter_analise_comparativo_endpoint(
    codigo_cvm: int,
    db: DbSession,
    ano_base: int = Query(..., description="Ano base da comparação"),
    ano_comparacao: int = Query(..., description="Ano a ser comparado")
) -> ComparativoAnaliseResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return obter_comparativo(db, companhia, ano_base=ano_base, ano_comparacao=ano_comparacao)


@router.get(
    "/{codigo_cvm}/analise/eventos",
    response_model=list[EventoLinhaTempo],
    summary="Timeline de Eventos da Companhia",
    description="Retorna uma linha do tempo unificada de fatos relevantes (IPE), reapresentações financeiras e grandes negociações.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseEventos",
)
def obter_analise_eventos_endpoint(codigo_cvm: int, db: DbSession) -> list[EventoLinhaTempo]:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return obter_eventos(db, companhia)


@router.get(
    "/{codigo_cvm}/analise/pessoas-remuneracao",
    response_model=PessoasRemuneracaoResposta,
    summary="Estrutura de Administração e Remuneração",
    description="Retorna estatísticas anuais de remuneração de órgãos, número de membros e diversidade de gênero.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnalisePessoasRemuneracao",
)
def obter_analise_pessoas_remuneracao_endpoint(codigo_cvm: int, db: DbSession) -> PessoasRemuneracaoResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    dados = obter_pessoas_remuneracao(db, companhia)
    return PessoasRemuneracaoResposta(cnpj_companhia=companhia.cnpj_companhia, codigo_cvm=codigo_cvm, dados=dados)


@router.get(
    "/{codigo_cvm}/analise/mercado-insiders",
    response_model=MercadoInsidersResposta,
    summary="Insider Trading e Inteligência de Mercado",
    description="Retorna movimentações de insiders, ações em tesouraria, alterações de capital social e governança.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseMercadoInsiders",
)
def obter_analise_mercado_insiders_endpoint(codigo_cvm: int, db: DbSession) -> MercadoInsidersResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return obter_mercado_insiders(db, companhia)


@router.get(
    "/{codigo_cvm}/analise",
    response_model=AnaliseConsolidadaResposta,
    summary="Análise Consolidada (Endpoint Estratégico)",
    description="Retorna todos os blocos de análise consolidados em um único payload estruturado.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterAnaliseConsolidada",
)
def obter_analise_consolidada_endpoint(
    codigo_cvm: int,
    db: DbSession,
    horizonte: str = Query("5a", description="Horizonte temporal de análise (5a, 10a, todos)"),
    periodicidade: str = Query("anual", description="Periodicidade das demonstrações (anual, trimestral, todos)"),
    ano_base: int = Query(2025, description="Ano base para comparação"),
    ano_comparacao: int = Query(2024, description="Ano de comparação")
) -> AnaliseConsolidadaResposta:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")

    overview = obter_overview(db, companhia)
    financeiro = obter_financeiro(db, companhia, horizonte=horizonte, periodicidade=periodicidade)
    # Handle comparativo errors or empty years gracefully
    try:
        comparativo = obter_comparativo(db, companhia, ano_base=ano_base, ano_comparacao=ano_comparacao)
    except Exception:
        comparativo = None

    eventos = obter_eventos(db, companhia)
    pessoas_rem = obter_pessoas_remuneracao(db, companhia)
    mercado = obter_mercado_insiders(db, companhia)

    # Serialize and return Consolidated Analysis
    return AnaliseConsolidadaResposta(
        companhia=CompanhiaResposta.model_validate(companhia).model_dump(),
        periodos_disponiveis=overview.periodos_disponiveis,
        cobertura=overview.cobertura,
        financeiro=financeiro.dados,
        eventos=eventos,
        governanca={
            "situacao_registro": companhia.situacao_registro,
            "categoria_registro": companhia.categoria_registro,
            "controle_acionario": companhia.controle_acionario,
            "tipo_mercado": companhia.tipo_mercado,
            "praticas_governanca_resumo": mercado.governanca_resumo
        },
        pessoas_remuneracao=pessoas_rem,
        mercado_insiders={
            "movimentacoes": mercado.movimentacoes,
            "concentracao_cargo": mercado.concentracao_cargo,
            "tesouraria": mercado.tesouraria,
            "capital_alteracoes": mercado.capital_alteracoes
        },
        proveniencia={
            "fontes_consultadas": ["DFP", "ITR", "FRE", "FCA", "IPE", "VLMO", "CGVN"],
            "data_geracao": datetime.now()
        }
    )


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
