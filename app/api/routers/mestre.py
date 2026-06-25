from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.models.ipe import IpeDocumento
from app.schemas.companhia import CompanhiaResposta
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
from app.schemas.ipe import IpeDocumentoResposta, ListaIpeDocumentosResposta
from app.schemas.mestre import ConsultaCompanhiaMestreResposta
from app.services.financeiro_mapas import DEMONSTRACOES
from app.services.financeiro_valores import serializar_demonstracao_financeira
from app.services.normalizacao import normalizar_cnpj

router = APIRouter()


def _paginacao(total: int, limite: int) -> Paginacao:
    return Paginacao(pagina=1, tamanho_pagina=limite, total=total)


def _listar(
    db: Session,
    *,
    modelo: type[Any],
    schema: type[Any],
    limite: int,
    filtros: tuple[Any, ...],
    ordem: str = "data_referencia",
) -> tuple[list[Any], int]:
    query: Select[Any] = select(modelo).where(*filtros)
    query_total = select(func.count()).select_from(modelo).where(*filtros)
    coluna_ordem = getattr(modelo, ordem, None)
    if coluna_ordem is not None:
        query = query.order_by(coluna_ordem.desc())
    itens = db.execute(query.limit(limite)).scalars().all()
    total = db.scalar(query_total) or 0
    return [schema.model_validate(item) for item in itens], total


@router.get(
    "/companhias/mestre",
    response_model=ConsultaCompanhiaMestreResposta,
    summary="Consulta Mestre da Companhia",
    description=(
        "Dado um `cnpj_companhia` ou `codigo_cvm`, agrega a resposta de todos os grupos de endpoints "
        "de companhia, financeiro (DFP/ITR), FRE e IPE em um unico payload. "
        "Nas demonstrações financeiras DFP/ITR agregadas, `valor_conta` já é entregue ajustado por "
        "`escala_moeda`, enquanto `valor_conta_reportado` preserva o número bruto do CSV da CVM. "
        "Campos decimais retornam como strings decimais canônicas, sem separadores de milhares."
    ),
    responses={
        404: {
            "description": "Companhia nao encontrada.",
            "content": {"application/json": {"example": {"detail": "Companhia nao encontrada."}}},
        },
        422: {
            "description": "Filtro invalido.",
            "content": {"application/json": {"example": {"detail": "Informe cnpj_companhia ou codigo_cvm."}}},
        },
    },
    operation_id="consultarCompanhiaMestre",
)
def consultar_companhia_mestre(
    db: DbSession,
    cnpj_companhia: str | None = Query(
        default=None,
        description="CNPJ da companhia (com ou sem pontuacao).",
        examples=["08.773.135/0001-00"],
    ),
    codigo_cvm: int | None = Query(default=None, description="Codigo CVM da companhia.", examples=[25224]),
    limite_por_endpoint: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Numero maximo de itens retornados por endpoint agregado.",
        examples=[100],
    ),
) -> ConsultaCompanhiaMestreResposta:
    if cnpj_companhia is None and codigo_cvm is None:
        raise HTTPException(status_code=422, detail="Informe cnpj_companhia ou codigo_cvm.")

    query_companhia = select(Companhia)
    if cnpj_companhia is not None:
        query_companhia = query_companhia.where(Companhia.cnpj_companhia == normalizar_cnpj(cnpj_companhia))
    if codigo_cvm is not None:
        query_companhia = query_companhia.where(Companhia.codigo_cvm == codigo_cvm)

    companhia = db.scalar(query_companhia)
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")

    cnpj = companhia.cnpj_companhia
    codigo = companhia.codigo_cvm
    filtros_financeiro: tuple[Any, ...] = (DocumentoFinanceiro.cnpj_companhia == cnpj,)
    if codigo is not None:
        filtros_financeiro = filtros_financeiro + (DocumentoFinanceiro.codigo_cvm == codigo,)

    documentos_dfp_dados, documentos_dfp_total = _listar(
        db,
        modelo=DocumentoFinanceiro,
        schema=DocumentoFinanceiroResposta,
        limite=limite_por_endpoint,
        filtros=filtros_financeiro + (DocumentoFinanceiro.tipo_formulario == "DFP",),
    )
    documentos_itr_dados, documentos_itr_total = _listar(
        db,
        modelo=DocumentoFinanceiro,
        schema=DocumentoFinanceiroResposta,
        limite=limite_por_endpoint,
        filtros=filtros_financeiro + (DocumentoFinanceiro.tipo_formulario == "ITR",),
    )

    filtros_comp_dfp: tuple[Any, ...] = (
        ComposicaoCapital.cnpj_companhia == cnpj,
        ComposicaoCapital.tipo_formulario == "DFP",
    )
    filtros_comp_itr: tuple[Any, ...] = (
        ComposicaoCapital.cnpj_companhia == cnpj,
        ComposicaoCapital.tipo_formulario == "ITR",
    )
    if codigo is not None:
        filtros_comp_dfp = filtros_comp_dfp + (ComposicaoCapital.codigo_cvm == codigo,)
        filtros_comp_itr = filtros_comp_itr + (ComposicaoCapital.codigo_cvm == codigo,)
    composicao_dfp_dados, composicao_dfp_total = _listar(
        db,
        modelo=ComposicaoCapital,
        schema=ComposicaoCapitalResposta,
        limite=limite_por_endpoint,
        filtros=filtros_comp_dfp,
    )
    composicao_itr_dados, composicao_itr_total = _listar(
        db,
        modelo=ComposicaoCapital,
        schema=ComposicaoCapitalResposta,
        limite=limite_por_endpoint,
        filtros=filtros_comp_itr,
    )

    filtros_parecer_dfp: tuple[Any, ...] = (
        ParecerFinanceiro.cnpj_companhia == cnpj,
        ParecerFinanceiro.tipo_formulario == "DFP",
    )
    filtros_parecer_itr: tuple[Any, ...] = (
        ParecerFinanceiro.cnpj_companhia == cnpj,
        ParecerFinanceiro.tipo_formulario == "ITR",
    )
    if codigo is not None:
        filtros_parecer_dfp = filtros_parecer_dfp + (ParecerFinanceiro.codigo_cvm == codigo,)
        filtros_parecer_itr = filtros_parecer_itr + (ParecerFinanceiro.codigo_cvm == codigo,)
    pareceres_dfp_dados, pareceres_dfp_total = _listar(
        db,
        modelo=ParecerFinanceiro,
        schema=ParecerFinanceiroResposta,
        limite=limite_por_endpoint,
        filtros=filtros_parecer_dfp,
    )
    pareceres_itr_dados, pareceres_itr_total = _listar(
        db,
        modelo=ParecerFinanceiro,
        schema=ParecerFinanceiroResposta,
        limite=limite_por_endpoint,
        filtros=filtros_parecer_itr,
    )

    demonstracoes: dict[str, ListaDemonstracoesFinanceirasResposta] = {}
    for item in DEMONSTRACOES:
        for formulario in ("DFP", "ITR"):
            for escopo in ("consolidado", "individual"):
                filtros_demonstracao: tuple[Any, ...] = (
                    DemonstracaoFinanceira.cnpj_companhia == cnpj,
                    DemonstracaoFinanceira.tipo_formulario == formulario,
                    DemonstracaoFinanceira.tipo_demonstracao == item["tipo"],
                    DemonstracaoFinanceira.escopo_demonstracao == escopo,
                )
                if codigo is not None:
                    filtros_demonstracao = filtros_demonstracao + (DemonstracaoFinanceira.codigo_cvm == codigo,)
                total_demonstracao = (
                    db.scalar(select(func.count()).select_from(DemonstracaoFinanceira).where(*filtros_demonstracao)) or 0
                )
                itens_demonstracao = (
                    db.execute(
                        select(DemonstracaoFinanceira)
                        .where(*filtros_demonstracao)
                        .order_by(DemonstracaoFinanceira.data_referencia.desc())
                        .limit(limite_por_endpoint)
                    )
                    .scalars()
                    .all()
                )
                chave = f"{formulario.lower()}_{item['rota'].replace('-', '_')}_{escopo}"
                demonstracoes[chave] = ListaDemonstracoesFinanceirasResposta(
                    dados=[
                        DemonstracaoFinanceiraResposta.model_validate(serializar_demonstracao_financeira(item))
                        for item in itens_demonstracao
                    ],
                    paginacao=_paginacao(total_demonstracao, limite_por_endpoint),
                )

    filtros_fre_doc: tuple[Any, ...] = (FreDocumento.cnpj_companhia == cnpj,)
    if codigo is not None:
        filtros_fre_doc = filtros_fre_doc + (FreDocumento.codigo_cvm == codigo,)
    fre_documentos_dados, fre_documentos_total = _listar(
        db,
        modelo=FreDocumento,
        schema=FreDocumentoResposta,
        limite=limite_por_endpoint,
        filtros=filtros_fre_doc,
    )
    fre_auditores_dados, fre_auditores_total = _listar(
        db,
        modelo=FreAuditor,
        schema=FreAuditorResposta,
        limite=limite_por_endpoint,
        filtros=(FreAuditor.cnpj_companhia == cnpj,),
    )
    fre_capital_dados, fre_capital_total = _listar(
        db,
        modelo=FreCapitalSocial,
        schema=FreCapitalSocialResposta,
        limite=limite_por_endpoint,
        filtros=(FreCapitalSocial.cnpj_companhia == cnpj,),
    )
    fre_posicao_dados, fre_posicao_total = _listar(
        db,
        modelo=FrePosicaoAcionaria,
        schema=FrePosicaoAcionariaResposta,
        limite=limite_por_endpoint,
        filtros=(FrePosicaoAcionaria.cnpj_companhia == cnpj,),
    )
    fre_remuneracao_dados, fre_remuneracao_total = _listar(
        db,
        modelo=FreRemuneracaoTotalOrgao,
        schema=FreRemuneracaoTotalOrgaoResposta,
        limite=limite_por_endpoint,
        filtros=(FreRemuneracaoTotalOrgao.cnpj_companhia == cnpj,),
    )
    fre_empregados_dados, fre_empregados_total = _listar(
        db,
        modelo=FreEmpregadoPosicaoGenero,
        schema=FreEmpregadoPosicaoGeneroResposta,
        limite=limite_por_endpoint,
        filtros=(FreEmpregadoPosicaoGenero.cnpj_companhia == cnpj,),
    )
    ipe_filtros: tuple[Any, ...] = (IpeDocumento.cnpj_companhia == cnpj,)
    if codigo is not None:
        ipe_filtros = ipe_filtros + (IpeDocumento.codigo_cvm == codigo,)
    query_ipe = (
        select(IpeDocumento)
        .where(*ipe_filtros)
        .order_by(
            IpeDocumento.data_entrega.desc(),
            IpeDocumento.data_referencia.desc(),
        )
    )
    query_ipe_total = select(func.count()).select_from(IpeDocumento).where(*ipe_filtros)
    ipe_documentos_dados = [
        IpeDocumentoResposta.model_validate(item)
        for item in db.execute(query_ipe.limit(limite_por_endpoint)).scalars().all()
    ]
    ipe_documentos_total = db.scalar(query_ipe_total) or 0

    return ConsultaCompanhiaMestreResposta(
        companhia=CompanhiaResposta.model_validate(companhia),
        documentos_dfp=ListaDocumentosFinanceirosResposta(
            dados=documentos_dfp_dados,
            paginacao=_paginacao(documentos_dfp_total, limite_por_endpoint),
        ),
        documentos_itr=ListaDocumentosFinanceirosResposta(
            dados=documentos_itr_dados,
            paginacao=_paginacao(documentos_itr_total, limite_por_endpoint),
        ),
        composicao_capital_dfp=ListaComposicoesCapitalResposta(
            dados=composicao_dfp_dados,
            paginacao=_paginacao(composicao_dfp_total, limite_por_endpoint),
        ),
        composicao_capital_itr=ListaComposicoesCapitalResposta(
            dados=composicao_itr_dados,
            paginacao=_paginacao(composicao_itr_total, limite_por_endpoint),
        ),
        pareceres_dfp=ListaPareceresFinanceirosResposta(
            dados=pareceres_dfp_dados,
            paginacao=_paginacao(pareceres_dfp_total, limite_por_endpoint),
        ),
        pareceres_itr=ListaPareceresFinanceirosResposta(
            dados=pareceres_itr_dados,
            paginacao=_paginacao(pareceres_itr_total, limite_por_endpoint),
        ),
        demonstracoes=demonstracoes,
        fre_documentos=ListaFreDocumentosResposta(
            dados=fre_documentos_dados,
            paginacao=_paginacao(fre_documentos_total, limite_por_endpoint),
        ),
        fre_auditores=ListaFreAuditoresResposta(
            dados=fre_auditores_dados,
            paginacao=_paginacao(fre_auditores_total, limite_por_endpoint),
        ),
        fre_capital_social=ListaFreCapitalSocialResposta(
            dados=fre_capital_dados,
            paginacao=_paginacao(fre_capital_total, limite_por_endpoint),
        ),
        fre_posicao_acionaria=ListaFrePosicaoAcionariaResposta(
            dados=fre_posicao_dados,
            paginacao=_paginacao(fre_posicao_total, limite_por_endpoint),
        ),
        fre_remuneracao_total_orgao=ListaFreRemuneracaoTotalOrgaoResposta(
            dados=fre_remuneracao_dados,
            paginacao=_paginacao(fre_remuneracao_total, limite_por_endpoint),
        ),
        fre_empregados_posicao_genero=ListaFreEmpregadoPosicaoGeneroResposta(
            dados=fre_empregados_dados,
            paginacao=_paginacao(fre_empregados_total, limite_por_endpoint),
        ),
        ipe_documentos=ListaIpeDocumentosResposta(
            dados=ipe_documentos_dados,
            paginacao=_paginacao(ipe_documentos_total, limite_por_endpoint),
        ),
    )
