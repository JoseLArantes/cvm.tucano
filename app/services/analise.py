import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import DocumentoFinanceiro, DemonstracaoFinanceira, ComposicaoCapital, ParecerFinanceiro
from app.models.fre import (
    FreDocumento,
    FreCapitalSocial,
    FreRemuneracaoTotalOrgao,
    FreAdministradorMembroConselhoFiscal,
    FreAdministradorDeclaracaoGenero,
    FreRelacaoFamiliar,
    FreCapitalSocialAumento
)
from app.models.fca import FcaDocumento
from app.models.ipe import IpeDocumento
from app.models.vlmo import VlmoDocumento, VlmoConsolidado
from app.models.cgvn import CgvnDocumento, CgvnPratica

from app.schemas.analise import (
    OverviewAnaliseResposta,
    AlertaOverview,
    PeriodoFinanceiro,
    MetricaFinanceira,
    ReferenciaProveniencia,
    FinanceiroAnaliseResposta,
    DeltaComparativo,
    ComparativoAnaliseResposta,
    EventoLinhaTempo,
    PessoasRemuneracaoAno,
    PessoasRemuneracaoResposta,
    MercadoInsidersResposta
)


def obter_overview(db: Session, companhia: Companhia) -> OverviewAnaliseResposta:
    cnpj = companhia.cnpj_companhia
    
    # 1. Freshness
    freshness_dates = []
    for model in (DocumentoFinanceiro, FreDocumento, IpeDocumento, VlmoDocumento, CgvnDocumento, FcaDocumento):
        stmt = select(func.max(model.sincronizado_em)).where(model.cnpj_companhia == cnpj)
        dt = db.scalar(stmt)
        if dt:
            freshness_dates.append(dt)
    data_freshness = max(freshness_dates) if freshness_dates else companhia.sincronizado_em

    # 2. Coverage
    def query_years(model: type[Any], filters: Sequence[Any]) -> set[int]:
        stmt = select(func.extract('year', model.data_referencia).cast(Integer)).where(*filters).distinct()
        return set(db.scalars(stmt).all())

    dfp_years = query_years(DocumentoFinanceiro, [DocumentoFinanceiro.cnpj_companhia == cnpj, DocumentoFinanceiro.tipo_formulario == "DFP"])
    itr_years = query_years(DocumentoFinanceiro, [DocumentoFinanceiro.cnpj_companhia == cnpj, DocumentoFinanceiro.tipo_formulario == "ITR"])
    fre_years = query_years(FreDocumento, [FreDocumento.cnpj_companhia == cnpj])
    fca_years = query_years(FcaDocumento, [FcaDocumento.cnpj_companhia == cnpj])
    ipe_years = query_years(IpeDocumento, [IpeDocumento.cnpj_companhia == cnpj])
    vlmo_years = query_years(VlmoDocumento, [VlmoDocumento.cnpj_companhia == cnpj])
    cgvn_years = query_years(CgvnDocumento, [CgvnDocumento.cnpj_companhia == cnpj])

    all_years = set().union(dfp_years, itr_years, fre_years, fca_years, ipe_years, vlmo_years, cgvn_years)
    cobertura = {}
    for y in sorted(all_years):
        families = []
        if y in dfp_years: families.append("DFP")
        if y in itr_years: families.append("ITR")
        if y in fre_years: families.append("FRE")
        if y in fca_years: families.append("FCA")
        if y in ipe_years: families.append("IPE")
        if y in vlmo_years: families.append("VLMO")
        if y in cgvn_years: families.append("CGVN")
        cobertura[str(y)] = families

    # 3. Available periods
    dfp_dates = db.scalars(
        select(DocumentoFinanceiro.data_referencia)
        .where(DocumentoFinanceiro.cnpj_companhia == cnpj, DocumentoFinanceiro.tipo_formulario == "DFP")
        .distinct().order_by(DocumentoFinanceiro.data_referencia.desc())
    ).all()
    
    itr_dates = db.scalars(
        select(DocumentoFinanceiro.data_referencia)
        .where(DocumentoFinanceiro.cnpj_companhia == cnpj, DocumentoFinanceiro.tipo_formulario == "ITR")
        .distinct().order_by(DocumentoFinanceiro.data_referencia.desc())
    ).all()

    periodos_disponiveis = {
        "DFP": sorted(list(set(str(d.year) for d in dfp_dates)), reverse=True),
        "ITR": sorted(list(set(f"{d.year}-{(d.month - 1) // 3 + 1}T" for d in itr_dates)), reverse=True)
    }

    # 4. Alerts
    alertas = []
    if companhia.situacao_registro != "ATIVO":
        alertas.append(AlertaOverview(
            tipo="SITUACAO_REGISTRO",
            descricao=f"Situação do registro inativa ou suspensa na CVM: {companhia.situacao_registro}",
            severidade="CRITICAL" if companhia.situacao_registro in ("CANCELADO", "INATIVO") else "WARNING"
        ))

    if dfp_dates:
        latest_dfp_year = max(d.year for d in dfp_dates)
        current_year = datetime.now().year
        if current_year - latest_dfp_year > 1:
            alertas.append(AlertaOverview(
                tipo="ATRASO_FILING",
                descricao=f"Último formulário DFP entregue é referente a {latest_dfp_year} (atraso de entrega detectado)",
                severidade="WARNING"
            ))

    anos_comparacao_disponiveis = sorted(list(set(d.year for d in dfp_dates)))

    return OverviewAnaliseResposta(
        cnpj_companhia=cnpj,
        codigo_cvm=companhia.codigo_cvm or 0,
        denominacao_social=companhia.denominacao_social or "",
        situacao_registro=companhia.situacao_registro or "OUTROS",
        status_ativo=(companhia.situacao_registro == "ATIVO"),
        data_freshness=data_freshness,
        cobertura=cobertura,
        periodos_disponiveis=periodos_disponiveis,
        alertas=alertas,
        anos_comparacao_disponiveis=anos_comparacao_disponiveis
    )


def obter_financeiro(db: Session, companhia: Companhia, horizonte: str = "5a", periodicidade: str = "anual") -> FinanceiroAnaliseResposta:
    cnpj = companhia.cnpj_companhia

    # 1. Fetch latest version documents
    subquery = (
        select(
            DocumentoFinanceiro.cnpj_companhia,
            DocumentoFinanceiro.tipo_formulario,
            DocumentoFinanceiro.data_referencia,
            func.max(DocumentoFinanceiro.versao).label("max_versao")
        )
        .where(DocumentoFinanceiro.cnpj_companhia == cnpj)
        .group_by(
            DocumentoFinanceiro.cnpj_companhia,
            DocumentoFinanceiro.tipo_formulario,
            DocumentoFinanceiro.data_referencia
        )
        .subquery()
    )

    stmt = (
        select(DemonstracaoFinanceira, DocumentoFinanceiro.id_documento, DocumentoFinanceiro.link_documento, DocumentoFinanceiro.data_recebimento)
        .join(
            subquery,
            and_(
                DemonstracaoFinanceira.cnpj_companhia == subquery.c.cnpj_companhia,
                DemonstracaoFinanceira.tipo_formulario == subquery.c.tipo_formulario,
                DemonstracaoFinanceira.data_referencia == subquery.c.data_referencia,
                DemonstracaoFinanceira.versao == subquery.c.max_versao
            )
        )
        .join(
            DocumentoFinanceiro,
            and_(
                DocumentoFinanceiro.cnpj_companhia == DemonstracaoFinanceira.cnpj_companhia,
                DocumentoFinanceiro.tipo_formulario == DemonstracaoFinanceira.tipo_formulario,
                DocumentoFinanceiro.data_referencia == DemonstracaoFinanceira.data_referencia,
                DocumentoFinanceiro.versao == DemonstracaoFinanceira.versao
            )
        )
    )

    # Filter accounts of interest
    contas_mapeadas = {
        "ativo_total": ["1"],
        "ativo_circulante": ["1.01"],
        "caixa_equivalentes": ["1.01.01"],
        "passivo_total": ["2"],
        "passivo_circulante": ["2.01"],
        "patrimonio_liquido": ["2.03"],
        "receita_liquida": ["3.01"],
        "lucro_bruto": ["3.03"],
        "ebit": ["3.05"],
        "lucro_liquido": ["3.11", "3.09"],
        "fluxo_caixa_operacional": ["6.01.01", "6.01"]
    }
    
    todas_contas = []
    for c in contas_mapeadas.values():
        todas_contas.extend(c)

    stmt = stmt.where(DemonstracaoFinanceira.codigo_conta.in_(todas_contas))
    
    rows = db.execute(stmt).all()

    # Group by (tipo_formulario, data_referencia) and escopo
    periods_raw: dict[
        tuple[str, date],
        dict[str, list[tuple[DemonstracaoFinanceira, uuid.UUID, str | None, datetime | None]]],
    ] = {}
    for df_row, doc_id, link, data_recebimento in rows:
        key = (df_row.tipo_formulario, df_row.data_referencia)
        if key not in periods_raw:
            periods_raw[key] = {}
        esc = df_row.escopo_demonstracao
        if esc not in periods_raw[key]:
            periods_raw[key][esc] = []
        periods_raw[key][esc].append((df_row, doc_id, link, data_recebimento))

    # Apply consolidado priority and extract metrics
    periods_extracted: list[PeriodoFinanceiro] = []
    for (tf, dt_ref), escopos in periods_raw.items():
        # Filter periodicidade if requested
        if periodicidade == "anual" and tf != "DFP":
            continue
        if periodicidade == "trimestral" and tf != "ITR":
            continue

        chosen_esc = "consolidado" if "consolidado" in escopos else ("individual" if "individual" in escopos else None)
        if not chosen_esc:
            continue

        items = escopos[chosen_esc]
        metrics: dict[str, MetricaFinanceira] = {}

        for name, codes in contas_mapeadas.items():
            matched_item = None
            for it, doc_id, link, recv_date in items:
                if it.codigo_conta in codes:
                    matched_item = (it, doc_id, link, recv_date)
                    break
            
            if matched_item:
                it, doc_id, link, recv_date = matched_item
                val_norm = float(it.valor_conta) if it.valor_conta is not None else None
                val_orig = str(it.valor_conta) if it.valor_conta is not None else None
                prov = ReferenciaProveniencia(
                    fonte="CVM",
                    dataset=f"{it.tipo_formulario}/{it.grupo_demonstracao or 'DF'}",
                    documento_id=str(doc_id),
                    linha_id=str(it.id),
                    data_referencia=it.data_referencia,
                    data_entrega=recv_date,
                    link_download=link
                )
                metrics[name] = MetricaFinanceira(
                    valor_normalizado=val_norm,
                    valor_original=val_orig,
                    proveniencia=prov,
                    yoy=None,
                    qoq=None,
                    cagr=None
                )
            else:
                metrics[name] = MetricaFinanceira(
                    valor_normalizado=None,
                    valor_original=None,
                    proveniencia=None,
                    yoy=None,
                    qoq=None,
                    cagr=None
                )

        ano = dt_ref.year
        trimestre = (dt_ref.month - 1) // 3 + 1
        label = f"{ano}" if tf == "DFP" else f"{ano}-{trimestre}T"

        periods_extracted.append(
            PeriodoFinanceiro(
                periodo_label=label,
                ano=ano,
                trimestre=trimestre,
                periodo_tipo="ANUAL" if tf == "DFP" else "TRIMESTRAL",
                metrics=metrics,
            )
        )

    # Sort periods chronologically
    periods_extracted.sort(key=lambda period: (period.ano, period.trimestre))

    # Apply horizon filter
    if periods_extracted:
        latest_year = max(period.ano for period in periods_extracted)
        if horizonte == "5a":
            periods_extracted = [period for period in periods_extracted if period.ano >= latest_year - 4]
        elif horizonte == "10a":
            periods_extracted = [period for period in periods_extracted if period.ano >= latest_year - 9]

    # Calculate YoY, QoQ, CAGR
    # YoY/QoQ calculations require historical mapping
    annual_map = {period.ano: period for period in periods_extracted if period.periodo_tipo == "ANUAL"}
    quarterly_map = {
        (period.ano, period.trimestre): period
        for period in periods_extracted
        if period.periodo_tipo == "TRIMESTRAL"
    }

    for period in periods_extracted:
        is_annual = period.periodo_tipo == "ANUAL"
        for m_name in contas_mapeadas.keys():
            met = period.metrics[m_name]
            if met.valor_normalizado is None:
                continue

            # 1. YoY
            if is_annual:
                prev_p = annual_map.get(period.ano - 1)
                if prev_p:
                    prev_val = prev_p.metrics[m_name].valor_normalizado
                    if prev_val and prev_val != 0:
                        met.yoy = (met.valor_normalizado - prev_val) / abs(prev_val)
            else:
                prev_p = quarterly_map.get((period.ano - 1, period.trimestre))
                if prev_p:
                    prev_val = prev_p.metrics[m_name].valor_normalizado
                    if prev_val and prev_val != 0:
                        met.yoy = (met.valor_normalizado - prev_val) / abs(prev_val)

            # 2. QoQ (ITR only)
            if not is_annual:
                y_prev, q_prev = (
                    (period.ano, period.trimestre - 1)
                    if period.trimestre > 1
                    else (period.ano - 1, 4)
                )
                prev_p = quarterly_map.get((y_prev, q_prev))
                if not prev_p and q_prev == 4:
                    # Fallback to DFP of previous year
                    prev_p = annual_map.get(y_prev)
                
                if prev_p:
                    prev_val = prev_p.metrics[m_name].valor_normalizado
                    if prev_val and prev_val != 0:
                        met.qoq = (met.valor_normalizado - prev_val) / abs(prev_val)

            # 3. CAGR (DFP only)
            if is_annual:
                # Find oldest annual record for CAGR
                oldest_year = min((year for year in annual_map if year < period.ano), default=None)
                if oldest_year:
                    old_p = annual_map[oldest_year]
                    old_val = old_p.metrics[m_name].valor_normalizado
                    n_years = period.ano - oldest_year
                    if old_val and old_val > 0 and met.valor_normalizado > 0 and n_years > 0:
                        try:
                            met.cagr = (met.valor_normalizado / old_val) ** (1.0 / n_years) - 1.0
                        except Exception:
                            met.cagr = None

    return FinanceiroAnaliseResposta(
        cnpj_companhia=cnpj,
        codigo_cvm=companhia.codigo_cvm or 0,
        dados=periods_extracted
    )


def obter_comparativo(db: Session, companhia: Companhia, ano_base: int, ano_comparacao: int) -> ComparativoAnaliseResposta:
    cnpj = companhia.cnpj_companhia

    # Helper function to compute delta
    def compute_delta(val_base: float | None, val_comp: float | None) -> DeltaComparativo:
        if val_base is None or val_comp is None:
            return DeltaComparativo(valor_base=val_base, valor_comparacao=val_comp, delta_absoluto=None, delta_percentual=None)
        abs_delta = val_base - val_comp
        pct_delta = abs_delta / abs(val_comp) if val_comp != 0 else None
        return DeltaComparativo(
            valor_base=val_base,
            valor_comparacao=val_comp,
            delta_absoluto=abs_delta,
            delta_percentual=pct_delta
        )

    # 1. Financeiro deltas
    fin_base = obter_financeiro(db, companhia, horizonte="todos", periodicidade="anual")
    p_base = next((p for p in fin_base.dados if p.ano == ano_base), None)
    p_comp = next((p for p in fin_base.dados if p.ano == ano_comparacao), None)

    financeiro_deltas = {}
    for met_name in ["receita_liquida", "lucro_bruto", "ebit", "lucro_liquido", "ativo_total", "patrimonio_liquido"]:
        val_base = p_base.metrics[met_name].valor_normalizado if p_base and met_name in p_base.metrics else None
        val_comp = p_comp.metrics[met_name].valor_normalizado if p_comp and met_name in p_comp.metrics else None
        financeiro_deltas[met_name] = compute_delta(val_base, val_comp)

    # 2. Capital deltas
    def get_shares_for_year(ano: int) -> tuple[float | None, float | None]:
        stmt = (
            select(ComposicaoCapital)
            .where(ComposicaoCapital.cnpj_companhia == cnpj, ComposicaoCapital.tipo_formulario == "DFP", ComposicaoCapital.ano_origem == ano)
            .order_by(desc(ComposicaoCapital.versao))
            .limit(1)
        )
        cc = db.scalar(stmt)
        if cc:
            return (
                float(cc.quantidade_total_acoes_capital_integralizado) if cc.quantidade_total_acoes_capital_integralizado is not None else None,
                float(cc.quantidade_total_acoes_tesouraria) if cc.quantidade_total_acoes_tesouraria is not None else None
            )
        return None, None

    base_total, base_tes = get_shares_for_year(ano_base)
    comp_total, comp_tes = get_shares_for_year(ano_comparacao)

    capital_deltas = {
        "quantidade_total_acoes": compute_delta(base_total, comp_total),
        "quantidade_total_acoes_tesouraria": compute_delta(base_tes, comp_tes)
    }

    # 3. Governanca deltas
    def get_board_membros_for_year(ano: int) -> int:
        # Membros do Conselho
        stmt = (
            select(func.count(FreAdministradorMembroConselhoFiscal.id))
            .where(
                FreAdministradorMembroConselhoFiscal.cnpj_companhia == cnpj,
                FreAdministradorMembroConselhoFiscal.ano_origem == ano,
                FreAdministradorMembroConselhoFiscal.orgao_administracao.ilike("%Conselho%")
            )
        )
        return db.scalar(stmt) or 0

    base_board = float(get_board_membros_for_year(ano_base))
    comp_board = float(get_board_membros_for_year(ano_comparacao))
    governanca_deltas = {
        "membros_conselho": compute_delta(base_board, comp_board)
    }

    # 4. Pessoas deltas (remuneration and total members from FreRemuneracaoTotalOrgao)
    def get_people_stats_for_year(ano: int) -> tuple[float | None, float | None]:
        stmt = (
            select(func.sum(FreRemuneracaoTotalOrgao.numero_membros), func.sum(FreRemuneracaoTotalOrgao.total_remuneracao_orgao))
            .where(FreRemuneracaoTotalOrgao.cnpj_companhia == cnpj, FreRemuneracaoTotalOrgao.ano_origem == ano)
        )
        memb, rem = db.execute(stmt).first() or (None, None)
        return (float(memb) if memb else None, float(rem) if rem else None)

    base_membros, base_rem = get_people_stats_for_year(ano_base)
    comp_membros, comp_rem = get_people_stats_for_year(ano_comparacao)

    pessoas_deltas = {
        "membros_remunerados_total": compute_delta(base_membros, comp_membros),
        "remuneracao_total_orgaos": compute_delta(base_rem, comp_rem)
    }

    # 5. Mercado deltas (buy/sell totals from VlmoConsolidado)
    def get_market_volume_for_year(ano: int) -> tuple[float, float]:
        stmt_buy = (
            select(func.sum(VlmoConsolidado.volume))
            .where(VlmoConsolidado.cnpj_companhia == cnpj, VlmoConsolidado.ano_origem == ano, VlmoConsolidado.tipo_operacao == "COMPRA")
        )
        stmt_sell = (
            select(func.sum(VlmoConsolidado.volume))
            .where(VlmoConsolidado.cnpj_companhia == cnpj, VlmoConsolidado.ano_origem == ano, VlmoConsolidado.tipo_operacao == "VENDA")
        )
        buy = db.scalar(stmt_buy)
        sell = db.scalar(stmt_sell)
        return (float(buy) if buy else 0.0, float(sell) if sell else 0.0)

    base_buy, base_sell = get_market_volume_for_year(ano_base)
    comp_buy, comp_sell = get_market_volume_for_year(ano_comparacao)

    mercado_deltas = {
        "volume_compras_insiders": compute_delta(base_buy, comp_buy),
        "volume_vendas_insiders": compute_delta(base_sell, comp_sell)
    }

    # 6. Eventos IPE delta
    def get_ipe_count_for_year(ano: int) -> float:
        stmt = (
            select(func.count(IpeDocumento.id))
            .where(IpeDocumento.cnpj_companhia == cnpj, func.extract('year', IpeDocumento.data_entrega) == ano)
        )
        return float(db.scalar(stmt) or 0)

    base_ipe = get_ipe_count_for_year(ano_base)
    comp_ipe = get_ipe_count_for_year(ano_comparacao)
    eventos_ipe_delta = compute_delta(base_ipe, comp_ipe)

    return ComparativoAnaliseResposta(
        ano_base=ano_base,
        ano_comparacao=ano_comparacao,
        financeiro=financeiro_deltas,
        capital=capital_deltas,
        governanca=governanca_deltas,
        pessoas=pessoas_deltas,
        mercado=mercado_deltas,
        eventos_ipe=eventos_ipe_delta
    )


def obter_eventos(db: Session, companhia: Companhia) -> list[EventoLinhaTempo]:
    cnpj = companhia.cnpj_companhia
    eventos = []

    # 1. Fetch IPE documents
    ipe_docs = db.scalars(
        select(IpeDocumento)
        .where(IpeDocumento.cnpj_companhia == cnpj)
        .order_by(desc(IpeDocumento.data_entrega))
        .limit(200)
    ).all()

    for doc in ipe_docs:
        sev = "INFO"
        if doc.categoria in ("Fato Relevante", "Aviso aos Acionistas"):
            sev = "WARNING"
        
        eventos.append(EventoLinhaTempo(
            data_evento=doc.data_entrega,
            familia_evento="IPE",
            tipo_evento=doc.categoria or "Documento",
            severidade=sev,
            titulo=doc.assunto or doc.tipo or "Filing IPE",
            explicacao=f"Documento IPE cadastrado na categoria {doc.categoria}. Espécie: {doc.especie}.",
            link_documento=doc.link_download,
            periodo_afetado=str(doc.data_referencia.year) if doc.data_referencia else None
        ))

    # 2. Reapresentações de DFP/ITR (versao > 1)
    reapr_docs = db.scalars(
        select(DocumentoFinanceiro)
        .where(DocumentoFinanceiro.cnpj_companhia == cnpj, DocumentoFinanceiro.versao > 1)
        .order_by(desc(DocumentoFinanceiro.data_recebimento))
        .limit(100)
    ).all()

    for reapr_doc in reapr_docs:
        eventos.append(EventoLinhaTempo(
            data_evento=reapr_doc.data_recebimento or reapr_doc.data_referencia,
            familia_evento="FINANCEIRO",
            tipo_evento="Reapresentação Financeira",
            severidade="WARNING",
            titulo=f"Reapresentação de {reapr_doc.tipo_formulario} (Versão {reapr_doc.versao})",
            explicacao=f"A companhia reapresentou o formulário {reapr_doc.tipo_formulario} referente a {reapr_doc.data_referencia}.",
            link_documento=reapr_doc.link_documento,
            periodo_afetado=f"{reapr_doc.data_referencia.year}"
        ))

    # 3. Capital Increases (FreCapitalSocialAumento)
    capital_inc = db.scalars(
        select(FreCapitalSocialAumento)
        .where(FreCapitalSocialAumento.cnpj_companhia == cnpj)
        .order_by(desc(FreCapitalSocialAumento.data_deliberacao))
        .limit(50)
    ).all()

    for cap in capital_inc:
        eventos.append(EventoLinhaTempo(
            data_evento=cap.data_deliberacao or cap.data_referencia,
            familia_evento="FRE",
            tipo_evento="Aumento de Capital",
            severidade="INFO",
            titulo=f"Aumento de Capital: {cap.origem_aumento or 'Aumento'}",
            explicacao=f"Deliberado aumento de capital no valor de R$ {cap.valor_aumento:,.2f} com emissão de {cap.quantidade_total_acoes:,.0f} ações." if cap.valor_aumento else "Deliberado aumento de capital social.",
            link_documento=None,
            periodo_afetado=str(cap.ano_origem)
        ))

    # 4. Large Insider Trades (VlmoConsolidado > 100k BRL)
    trades = db.scalars(
        select(VlmoConsolidado)
        .where(VlmoConsolidado.cnpj_companhia == cnpj, VlmoConsolidado.volume > 100000)
        .order_by(desc(VlmoConsolidado.data_movimentacao))
        .limit(100)
    ).all()

    for tr in trades:
        eventos.append(EventoLinhaTempo(
            data_evento=tr.data_movimentacao or tr.data_referencia,
            familia_evento="VLMO",
            tipo_evento="Negociação Relevante de Insiders",
            severidade="INFO",
            titulo=f"Insiders: {tr.tipo_operacao} de {tr.tipo_ativo}",
            explicacao=f"O cargo {tr.tipo_cargo} realizou {tr.tipo_operacao} de {tr.quantidade:,.0f} unidades no volume de R$ {tr.volume:,.2f}.",
            link_documento=None,
            periodo_afetado=f"{tr.data_referencia.year}-{(tr.data_referencia.month - 1) // 3 + 1}T"
        ))

    # Sort events descending
    eventos.sort(key=lambda x: x.data_evento, reverse=True)
    return eventos


def obter_pessoas_remuneracao(db: Session, companhia: Companhia) -> list[PessoasRemuneracaoAno]:
    cnpj = companhia.cnpj_companhia

    # 1. Fetch available years from FreRemuneracaoTotalOrgao
    years = db.scalars(
        select(FreRemuneracaoTotalOrgao.ano_origem)
        .where(FreRemuneracaoTotalOrgao.cnpj_companhia == cnpj, FreRemuneracaoTotalOrgao.ano_origem != None)
        .distinct().order_by(desc(FreRemuneracaoTotalOrgao.ano_origem))
    ).all()

    valid_years = [year for year in years if year is not None]
    result: list[PessoasRemuneracaoAno] = []
    for y in sorted(valid_years):
        # 1. Fetch Board (Conselho) stats
        stmt_conselho = (
            select(func.sum(FreRemuneracaoTotalOrgao.numero_membros), func.sum(FreRemuneracaoTotalOrgao.total_remuneracao_orgao))
            .where(
                FreRemuneracaoTotalOrgao.cnpj_companhia == cnpj,
                FreRemuneracaoTotalOrgao.ano_origem == y,
                FreRemuneracaoTotalOrgao.orgao_administracao.ilike("%Conselho de Administração%")
            )
        )
        memb_c, rem_c = db.execute(stmt_conselho).first() or (0, 0.0)

        # 2. Fetch Executive (Diretoria) stats
        stmt_diretoria = (
            select(func.sum(FreRemuneracaoTotalOrgao.numero_membros), func.sum(FreRemuneracaoTotalOrgao.total_remuneracao_orgao))
            .where(
                FreRemuneracaoTotalOrgao.cnpj_companhia == cnpj,
                FreRemuneracaoTotalOrgao.ano_origem == y,
                FreRemuneracaoTotalOrgao.orgao_administracao.ilike("%Diretoria%")
            )
        )
        memb_d, rem_d = db.execute(stmt_diretoria).first() or (0, 0.0)

        # Proporcao Feminina
        stmt_gen_c = (
            select(func.sum(FreAdministradorDeclaracaoGenero.quantidade_feminino), func.sum(FreAdministradorDeclaracaoGenero.quantidade_masculino))
            .where(
                FreAdministradorDeclaracaoGenero.cnpj_companhia == cnpj,
                FreAdministradorDeclaracaoGenero.ano_origem == y,
                FreAdministradorDeclaracaoGenero.orgao_administracao.ilike("%Conselho de Administração%")
            )
        )
        fem_c, masc_c = db.execute(stmt_gen_c).first() or (0, 0)
        prop_c = float(fem_c) / (fem_c + masc_c) if (fem_c and masc_c and (fem_c + masc_c) > 0) else None

        stmt_gen_d = (
            select(func.sum(FreAdministradorDeclaracaoGenero.quantidade_feminino), func.sum(FreAdministradorDeclaracaoGenero.quantidade_masculino))
            .where(
                FreAdministradorDeclaracaoGenero.cnpj_companhia == cnpj,
                FreAdministradorDeclaracaoGenero.ano_origem == y,
                FreAdministradorDeclaracaoGenero.orgao_administracao.ilike("%Diretoria%")
            )
        )
        fem_d, masc_d = db.execute(stmt_gen_d).first() or (0, 0)
        prop_d = float(fem_d) / (fem_d + masc_d) if (fem_d and masc_d and (fem_d + masc_d) > 0) else None

        # Family Relations count
        stmt_rel = (
            select(func.count(FreRelacaoFamiliar.id))
            .where(FreRelacaoFamiliar.cnpj_companhia == cnpj, FreRelacaoFamiliar.ano_origem == y)
        )
        rel_count = db.scalar(stmt_rel) or 0

        # Calculations
        tot_c = float(rem_c) if rem_c else None
        num_c = int(memb_c) if memb_c else None
        avg_c = tot_c / num_c if tot_c and num_c else None

        tot_d = float(rem_d) if rem_d else None
        num_d = int(memb_d) if memb_d else None
        avg_d = tot_d / num_d if tot_d and num_d else None

        result.append(PessoasRemuneracaoAno(
            ano=y,
            total_remuneracao_conselho=tot_c,
            membros_conselho=num_c,
            remuneracao_media_conselho=avg_c,
            total_remuneracao_diretoria=tot_d,
            membros_diretoria=num_d,
            remuneracao_media_diretoria=avg_d,
            yoy_remuneracao_total=None,
            proporcao_feminino_conselho=prop_c,
            proporcao_feminino_diretoria=prop_d,
            relacoes_familiares_total=rel_count
        ))

    # Compute YoY on total remuneration
    for i in range(1, len(result)):
        tot_curr = (result[i].total_remuneracao_conselho or 0.0) + (result[i].total_remuneracao_diretoria or 0.0)
        tot_prev = (result[i-1].total_remuneracao_conselho or 0.0) + (result[i-1].total_remuneracao_diretoria or 0.0)
        if tot_prev > 0:
            result[i].yoy_remuneracao_total = (tot_curr - tot_prev) / tot_prev

    # Sort descending
    result.sort(key=lambda x: x.ano, reverse=True)
    return result


def obter_mercado_insiders(db: Session, companhia: Companhia) -> MercadoInsidersResposta:
    cnpj = companhia.cnpj_companhia

    # 1. Movimentacoes agrupadas por ano/mes
    stmt_mov = (
        select(
            func.extract('year', VlmoConsolidado.data_movimentacao).cast(Integer).label("ano"),
            func.extract('month', VlmoConsolidado.data_movimentacao).cast(Integer).label("mes"),
            VlmoConsolidado.tipo_operacao,
            func.sum(VlmoConsolidado.quantidade).label("total_quantidade"),
            func.sum(VlmoConsolidado.volume).label("total_volume")
        )
        .where(VlmoConsolidado.cnpj_companhia == cnpj)
        .group_by("ano", "mes", VlmoConsolidado.tipo_operacao)
        .order_by("ano", "mes")
    )
    
    mov_rows = db.execute(stmt_mov).all()
    movimentacoes: list[dict[str, Any]] = []
    for mov_row in mov_rows:
        if mov_row.ano is not None:
            movimentacoes.append({
                "ano": mov_row.ano,
                "mes": mov_row.mes,
                "tipo_operacao": mov_row.tipo_operacao,
                "total_quantidade": float(mov_row.total_quantidade) if mov_row.total_quantidade else 0.0,
                "total_volume": float(mov_row.total_volume) if mov_row.total_volume else 0.0
            })

    # 2. Concentracao por cargo (volume total)
    stmt_conc = (
        select(
            VlmoConsolidado.tipo_cargo,
            func.sum(VlmoConsolidado.volume)
        )
        .where(VlmoConsolidado.cnpj_companhia == cnpj)
        .group_by(VlmoConsolidado.tipo_cargo)
    )
    conc_rows = db.execute(stmt_conc).all()
    total_vol = sum(float(r[1]) for r in conc_rows if r[1] is not None)
    
    concentracao_cargo = {}
    if total_vol > 0:
        for cargo, vol in conc_rows:
            if cargo and vol:
                concentracao_cargo[cargo] = float(vol) / total_vol

    # 3. Tesouraria level from ComposicaoCapital
    stmt_tes = (
        select(
            ComposicaoCapital.ano_origem,
            func.max(ComposicaoCapital.quantidade_total_acoes_tesouraria).label("qt_tes"),
            func.max(ComposicaoCapital.quantidade_total_acoes_capital_integralizado).label("qt_total")
        )
        .where(ComposicaoCapital.cnpj_companhia == cnpj, ComposicaoCapital.tipo_formulario == "DFP")
        .group_by(ComposicaoCapital.ano_origem)
        .order_by(ComposicaoCapital.ano_origem)
    )
    tes_rows = db.execute(stmt_tes).all()
    tesouraria: list[dict[str, Any]] = []
    for tes_row in tes_rows:
        if tes_row.ano_origem is not None:
            pct = (
                float(tes_row.qt_tes) / float(tes_row.qt_total)
                if (tes_row.qt_tes and tes_row.qt_total and tes_row.qt_total > 0)
                else 0.0
            )
            tesouraria.append({
                "ano": tes_row.ano_origem,
                "quantidade_tesouraria": float(tes_row.qt_tes) if tes_row.qt_tes else 0.0,
                "quantidade_total": float(tes_row.qt_total) if tes_row.qt_total else 0.0,
                "percentual": pct
            })

    # 4. Capital increases/reductions
    stmt_cap_alt = (
        select(
            FreCapitalSocialAumento.ano_origem,
            FreCapitalSocialAumento.data_deliberacao,
            FreCapitalSocialAumento.valor_aumento,
            FreCapitalSocialAumento.origem_aumento
        )
        .where(FreCapitalSocialAumento.cnpj_companhia == cnpj)
        .order_by(FreCapitalSocialAumento.data_deliberacao)
    )
    cap_rows = db.execute(stmt_cap_alt).all()
    capital_alteracoes: list[dict[str, Any]] = []
    for cap_row in cap_rows:
        capital_alteracoes.append({
            "ano": cap_row.ano_origem,
            "data_deliberacao": cap_row.data_deliberacao,
            "valor_aumento": float(cap_row.valor_aumento) if cap_row.valor_aumento else 0.0,
            "origem_aumento": cap_row.origem_aumento
        })

    # 5. Governance practices count
    stmt_gov = (
        select(CgvnPratica.pratica_adotada, func.count(CgvnPratica.id))
        .where(CgvnPratica.cnpj_companhia == cnpj)
        .group_by(CgvnPratica.pratica_adotada)
    )
    gov_rows = db.execute(stmt_gov).all()
    governanca_resumo = {r.pratica_adotada: r[1] for r in gov_rows if r.pratica_adotada is not None}

    return MercadoInsidersResposta(
        cnpj_companhia=cnpj,
        codigo_cvm=companhia.codigo_cvm or 0,
        movimentacoes=movimentacoes,
        concentracao_cargo=concentracao_cargo,
        tesouraria=tesouraria,
        capital_alteracoes=capital_alteracoes,
        governanca_resumo=governanca_resumo
    )
