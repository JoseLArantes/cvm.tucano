from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast

from sqlalchemy import and_, delete, desc, func, insert, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import get_settings
from app.models.analise import (
    AnaliseContextoRevision,
    AnaliseFatoRevision,
    AnaliseMaterializacaoCampanha,
    AnaliseMaterializacaoCampanhaItem,
    AnaliseMaterializacaoChunkExecucao,
    AnaliseMaterializacaoControle,
    AnaliseMaterializacaoExecucao,
)
from app.models.cgvn import CgvnDocumento, CgvnPratica
from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.fre import FreCapitalSocialAumento, FreEmpregadoPosicaoGenero, FreRemuneracaoTotalOrgao
from app.models.ingestion import IngestionRun
from app.models.ipe import IpeDocumento
from app.models.sincronizacao import ExecucaoSincronizacao
from app.models.vlmo import VlmoConsolidado
from app.schemas.analise import (
    AnaliseBasePeriodo,
    AnaliseBriefReferencias,
    AnaliseBriefResposta,
    AnaliseCompanhiaResumo,
    AnaliseComparables,
    AnaliseComparacaoItem,
    AnaliseComparacoesResposta,
    AnaliseComparisonKind,
    AnaliseComparisonUnit,
    AnaliseContextoPadrao,
    AnaliseEscopo,
    AnaliseEvento,
    AnaliseEventosResposta,
    AnaliseEvidenceItem,
    AnaliseForm,
    AnaliseGovernancaResposta,
    AnaliseIssue,
    AnaliseLinkSet,
    AnaliseManifestoResposta,
    AnaliseMetricaCatalogoItem,
    AnaliseMetricasCatalogoResposta,
    AnaliseMetricType,
    AnaliseNaturezaPeriodo,
    AnalisePeriodicidade,
    AnalisePeriodoDisponivel,
    AnalisePessoasResposta,
    AnaliseProvenienciaItem,
    AnaliseQualidadeResposta,
    AnaliseQualidadeResumo,
    AnaliseResolutionMetadata,
    AnaliseRestatementContaAlterada,
    AnaliseRestatementItem,
    AnaliseRestatementsResposta,
    AnaliseSeriesObservation,
    AnaliseSeriesResposta,
    AnaliseSeriesUnavailable,
    AnaliseSignal,
    AnaliseSinaisResposta,
    AnaliseTemporalObservation,
    AnaliseUnit,
    AnaliseValueSource,
)
from app.services.financeiro_valores import valor_conta_ajustado

CALCULATION_VERSION: Literal["2026.2"] = "2026.2"
_settings = get_settings()
DB_SCOPE_TO_API: dict[str, AnaliseEscopo] = {"consolidado": "consolidated", "individual": "individual"}
API_SCOPE_TO_DB: dict[AnaliseEscopo, str] = {"consolidated": "consolidado", "individual": "individual"}
FORM_FLOW_PRIORITY = ("ITR", "DFP")
_MATERIALIZACAO_ACTIVE_CAMPAIGN_STATUSES = {"pending", "running"}
_MATERIALIZACAO_ACTIVE_ITEM_STATUSES = {"pending", "running"}
_MATERIALIZACAO_ACTIVE_CHUNK_STATUSES = {"queued", "running"}
_MATERIALIZACAO_TERMINAL_CHUNK_STATUSES = {"success", "failed", "stale", "cancelled"}


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    nome: str
    metric_type: AnaliseMetricType
    unit: AnaliseUnit
    period_nature: AnaliseNaturezaPeriodo
    candidate_accounts: tuple[str, ...] = ()
    formula: str | None = None
    direction: Literal["higher_is_better", "lower_is_better", "contextual"] = "contextual"
    strategy: str = ""
    bases: tuple[AnaliseBasePeriodo, ...] = ("fy",)
    vertical_denominator_metric_id: str | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterializacaoGateBlocker:
    source_type: str
    execution_id: str | None
    run_id: str | None
    year: int | None
    status: str
    phase: str | None
    started_at: datetime | None


@dataclass(frozen=True)
class MaterializacaoGateState:
    status: Literal["green", "red"]
    reason_code: str
    gate_enabled: bool
    manual_control: Literal["auto", "paused"]
    manual_reason: str | None
    blocking_ingestions: int
    pending_ingestions: int
    next_check_at: datetime | None
    blockers: tuple[MaterializacaoGateBlocker, ...]


@dataclass(frozen=True)
class MaterializacaoRecuperacaoResultado:
    recovered_chunks: int
    recovered_items: int
    affected_campaigns: tuple[str, ...]
    chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class MaterializacaoReativacaoClassificacao:
    reason_code: str
    recoverable: bool
    active_chunk_id: str | None
    stale_chunk_count: int
    running_execution_count: int
    age_seconds: int | None


@dataclass(frozen=True)
class MaterializacaoReativacaoResultado:
    status: str
    reason_code: str
    affected_campaigns: tuple[str, ...]
    requeued_campaigns: tuple[str, ...]
    recovered_chunks: int
    recovered_items: int
    dispatcher_enqueued: bool
    triggered_at: datetime


@dataclass(frozen=True)
class MaterializacaoReativacaoSweepResultado:
    status: str
    reason_code: str
    affected_campaigns: tuple[str, ...]
    requeued_campaigns: tuple[str, ...]
    recovered_chunks: int
    recovered_items: int
    dispatcher_enqueued: bool
    triggered_at: datetime
    scanned_campaigns: int
    recoverable_campaigns: int


@dataclass
class ResolvedFact:
    metric_id: str
    period_id: str
    fiscal_year: int
    quarter: int | None
    period_nature: AnaliseNaturezaPeriodo
    period_basis: AnaliseBasePeriodo
    start_date: date | None
    end_date: date
    value: Decimal
    unit: AnaliseUnit
    scope: AnaliseEscopo
    form: AnaliseForm
    version: int | None
    restated: bool
    value_source: AnaliseValueSource
    comparables: AnaliseComparables
    provenance: list[AnaliseProvenienciaItem]


@dataclass
class ContextData:
    companhia: Companhia
    rows: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]
    documents: list[DocumentoFinanceiro]
    qualidade: AnaliseQualidadeResumo
    periodos_disponiveis: list[AnalisePeriodoDisponivel]
    issues: list[AnaliseIssue]


METRIC_SPECS: dict[str, MetricSpec] = {
    "receita_liquida": MetricSpec(
        metric_id="receita_liquida",
        nome="Receita líquida",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("3.01",),
        direction="higher_is_better",
        strategy="Seleciona a conta 3.01 do exercício corrente (`ordem_exercicio=ÚLTIMO`) e deriva fluxo trimestral isolado quando necessário.",
        bases=("fy", "quarter", "ytd"),
        limitations=("ITR pode trazer acumulado e trimestre isolado simultaneamente; o backend preserva essa distinção.",),
    ),
    "lucro_bruto": MetricSpec(
        metric_id="lucro_bruto",
        nome="Lucro bruto",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("3.03",),
        direction="higher_is_better",
        strategy="Seleciona a conta 3.03 corrente e deriva trimestres quando necessário.",
        bases=("fy", "quarter", "ytd"),
    ),
    "ebit": MetricSpec(
        metric_id="ebit",
        nome="EBIT",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("3.05",),
        direction="higher_is_better",
        strategy="Seleciona a conta 3.05 corrente e deriva trimestres quando necessário.",
        bases=("fy", "quarter", "ytd"),
    ),
    "lucro_liquido": MetricSpec(
        metric_id="lucro_liquido",
        nome="Lucro líquido",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("3.11", "3.09"),
        direction="higher_is_better",
        strategy="Tenta 3.11 antes de 3.09 e usa somente o exercício corrente.",
        bases=("fy", "quarter", "ytd"),
    ),
    "caixa_operacional": MetricSpec(
        metric_id="caixa_operacional",
        nome="Caixa gerado nas operações",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("6.01.01", "6.01"),
        direction="higher_is_better",
        strategy="Usa o fluxo de caixa operacional do exercício corrente, preferindo a rubrica mais específica.",
        bases=("fy", "quarter", "ytd"),
    ),
    "depreciacao_amortizacao": MetricSpec(
        metric_id="depreciacao_amortizacao",
        nome="Depreciação e amortização",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("6.01.01.02", "6.01.01.03", "6.01.01.04"),
        direction="contextual",
        strategy="Soma rubricas de depreciação e amortização do fluxo operacional quando disponíveis.",
        bases=("fy", "quarter", "ytd"),
        limitations=("A disponibilidade depende da abertura do fluxo de caixa na companhia emissora.",),
    ),
    "capex": MetricSpec(
        metric_id="capex",
        nome="CAPEX",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        candidate_accounts=("6.02.01", "6.02.02", "6.02"),
        direction="lower_is_better",
        strategy="Agrega desembolsos de investimento associados a CAPEX a partir do fluxo de caixa de investimentos.",
        bases=("fy", "quarter", "ytd"),
        limitations=("Pode incluir componentes de investimento não puramente orgânicos, conforme a abertura publicada pela companhia.",),
    ),
    "ativo_total": MetricSpec(
        metric_id="ativo_total",
        nome="Ativo total",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("1",),
        direction="higher_is_better",
        strategy="Seleciona o saldo do ativo total na data de referência do período.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "ativo_circulante": MetricSpec(
        metric_id="ativo_circulante",
        nome="Ativo circulante",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("1.01",),
        direction="higher_is_better",
        strategy="Seleciona o saldo do ativo circulante na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "caixa_equivalentes": MetricSpec(
        metric_id="caixa_equivalentes",
        nome="Caixa e equivalentes de caixa",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("1.01.01",),
        direction="higher_is_better",
        strategy="Seleciona o saldo de caixa e equivalentes na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "passivo_total": MetricSpec(
        metric_id="passivo_total",
        nome="Passivo total",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("2",),
        direction="lower_is_better",
        strategy="Seleciona o saldo do passivo total na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "divida_bruta": MetricSpec(
        metric_id="divida_bruta",
        nome="Dívida bruta",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("2.01.04", "2.02.01"),
        direction="lower_is_better",
        strategy="Soma passivos financeiros de curto e longo prazo na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "passivo_circulante": MetricSpec(
        metric_id="passivo_circulante",
        nome="Passivo circulante",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("2.01",),
        direction="lower_is_better",
        strategy="Seleciona o saldo do passivo circulante na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "patrimonio_liquido": MetricSpec(
        metric_id="patrimonio_liquido",
        nome="Patrimônio líquido",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        candidate_accounts=("2.03",),
        direction="higher_is_better",
        strategy="Seleciona o saldo do patrimônio líquido na data de referência.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "margem_liquida": MetricSpec(
        metric_id="margem_liquida",
        nome="Margem líquida",
        metric_type="ratio",
        unit="ratio",
        period_nature="duration",
        formula="lucro_liquido / receita_liquida",
        direction="contextual",
        strategy="Calculada pela divisão de lucro líquido por receita líquida no mesmo período.",
        bases=("fy", "quarter", "ytd"),
        vertical_denominator_metric_id=None,
        limitations=("Retornada como razão decimal canônica com `unit=ratio`.",),
    ),
    "ebitda": MetricSpec(
        metric_id="ebitda",
        nome="EBITDA",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        formula="ebit + depreciacao_amortizacao",
        direction="higher_is_better",
        strategy="Calculado como EBIT somado à depreciação e amortização no mesmo período.",
        bases=("fy", "quarter", "ytd"),
    ),
    "caixa_livre": MetricSpec(
        metric_id="caixa_livre",
        nome="Caixa livre",
        metric_type="flow",
        unit="BRL",
        period_nature="duration",
        formula="caixa_operacional - capex",
        direction="higher_is_better",
        strategy="Calculado como caixa operacional menos CAPEX.",
        bases=("fy", "quarter", "ytd"),
    ),
    "divida_liquida": MetricSpec(
        metric_id="divida_liquida",
        nome="Dívida líquida",
        metric_type="stock",
        unit="BRL",
        period_nature="instant",
        formula="divida_bruta - caixa_equivalentes",
        direction="lower_is_better",
        strategy="Calculada como dívida bruta menos caixa e equivalentes.",
        bases=("fy", "quarter"),
        vertical_denominator_metric_id="ativo_total",
    ),
    "alavancagem": MetricSpec(
        metric_id="alavancagem",
        nome="Alavancagem",
        metric_type="ratio",
        unit="ratio",
        period_nature="duration",
        formula="divida_liquida / ebitda",
        direction="lower_is_better",
        strategy="Calculada como dívida líquida dividida por EBITDA anual.",
        bases=("fy",),
        limitations=("Nesta etapa não é anualizada para trimestres nem convertida em TTM.",),
    ),
    "conversao_lucro_caixa": MetricSpec(
        metric_id="conversao_lucro_caixa",
        nome="Conversão lucro-caixa",
        metric_type="ratio",
        unit="ratio",
        period_nature="duration",
        formula="caixa_operacional / lucro_liquido",
        direction="higher_is_better",
        strategy="Calculada como caixa operacional dividido por lucro líquido anual.",
        bases=("fy",),
        limitations=("Nesta etapa é publicada apenas para períodos anuais.",),
    ),
    "liquidez_corrente": MetricSpec(
        metric_id="liquidez_corrente",
        nome="Liquidez corrente",
        metric_type="ratio",
        unit="ratio",
        period_nature="instant",
        formula="ativo_circulante / passivo_circulante",
        direction="higher_is_better",
        strategy="Calculada pela divisão de ativo circulante por passivo circulante na mesma data.",
        bases=("fy", "quarter"),
        limitations=("Retornada como razão decimal canônica com `unit=ratio`.",),
    ),
}

METRIC_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "margem_liquida": ("lucro_liquido", "receita_liquida"),
    "ebitda": ("ebit", "depreciacao_amortizacao"),
    "caixa_livre": ("caixa_operacional", "capex"),
    "divida_liquida": ("divida_bruta", "caixa_equivalentes"),
    "alavancagem": ("divida_liquida", "ebitda"),
    "conversao_lucro_caixa": ("caixa_operacional", "lucro_liquido"),
    "liquidez_corrente": ("ativo_circulante", "passivo_circulante"),
}


def _expand_metric_dependencies(metric_ids: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def visit(metric_id: str) -> None:
        if metric_id in seen:
            return
        seen.add(metric_id)
        for dependency in METRIC_DEPENDENCIES.get(metric_id, ()):
            visit(dependency)
        expanded.append(metric_id)

    for metric_id in metric_ids:
        visit(metric_id)
    return expanded


def _companhia_resumo(companhia: Companhia) -> AnaliseCompanhiaResumo:
    return AnaliseCompanhiaResumo(
        codigo_cvm=companhia.codigo_cvm or 0,
        cnpj_companhia=companhia.cnpj_companhia,
        denominacao_social=companhia.denominacao_social or "",
        situacao_registro=companhia.situacao_registro,
    )


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _stable_event_id(family: str, *parts: object) -> str:
    normalized = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(f"{family}|{normalized}".encode()).hexdigest()[:24]
    return f"{family.lower()}_{digest}"


def _quarter_start(year: int, quarter: int) -> date:
    month = (quarter - 1) * 3 + 1
    return date(year, month, 1)


def _quarter_end(year: int, quarter: int) -> date:
    return date(year, quarter * 3, 31 if quarter in (1, 4) else 30)


def _quarter_from_date(value: date) -> int:
    return (value.month - 1) // 3 + 1


def _period_id_for(periodicidade: AnalisePeriodicidade, base_periodo: AnaliseBasePeriodo, year: int, quarter: int | None) -> str:
    if periodicidade == "annual":
        return f"FY{year}"
    if base_periodo == "ytd":
        assert quarter is not None
        return f"{year}-YTDQ{quarter}"
    assert quarter is not None
    return f"{year}-Q{quarter}"


def _document_known_on_or_before(as_of: date) -> ColumnElement[bool]:
    return or_(
        and_(DocumentoFinanceiro.data_recebimento.is_not(None), DocumentoFinanceiro.data_recebimento <= as_of),
        and_(DocumentoFinanceiro.data_recebimento.is_(None), DocumentoFinanceiro.data_referencia <= as_of),
    )


def _row_current_exercise(row: DemonstracaoFinanceira) -> bool:
    return row.ordem_exercicio == "ÚLTIMO"


def _row_matches_scope(row: DemonstracaoFinanceira, scope: AnaliseEscopo) -> bool:
    return DB_SCOPE_TO_API.get(row.escopo_demonstracao) == scope


def _row_value(row: DemonstracaoFinanceira) -> Decimal | None:
    if row.valor_conta is None:
        return None
    return valor_conta_ajustado(row.valor_conta, row.escala_moeda)


def _provenance_for(row: DemonstracaoFinanceira, doc: DocumentoFinanceiro, form: AnaliseForm | None = None) -> AnaliseProvenienciaItem:
    return AnaliseProvenienciaItem(
        source="CVM",
        dataset="demonstracoes_financeiras",
        form=form or row.tipo_formulario,  # type: ignore[arg-type]
        document_id=doc.id_documento,
        row_id=str(row.id),
        version=row.versao,
        account_code=row.codigo_conta,
        statement_type=row.tipo_demonstracao,
        order=row.ordem_exercicio,
        start_date=row.data_inicio_exercicio,
        end_date=row.data_fim_exercicio or row.data_referencia,
        filed_at=doc.data_recebimento,
        link_download=doc.link_documento,
    )


def _resolved_from_row(
    *,
    metric_id: str,
    spec: MetricSpec,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    row: DemonstracaoFinanceira,
    doc: DocumentoFinanceiro,
    scope: AnaliseEscopo,
    value_source: AnaliseValueSource = "reported",
    provenance: list[AnaliseProvenienciaItem] | None = None,
    form: AnaliseForm | None = None,
    value: Decimal | None = None,
) -> ResolvedFact | None:
    final_value = value if value is not None else _row_value(row)
    if final_value is None:
        return None
    quarter = None if periodicidade == "annual" else _quarter_from_date(row.data_referencia)
    period_id = _period_id_for(periodicidade, base_periodo, row.data_referencia.year, quarter)
    return ResolvedFact(
        metric_id=metric_id,
        period_id=period_id,
        fiscal_year=row.data_referencia.year,
        quarter=quarter,
        period_nature=spec.period_nature,
        period_basis=base_periodo,
        start_date=row.data_inicio_exercicio if spec.period_nature == "duration" else None,
        end_date=row.data_fim_exercicio or row.data_referencia,
        value=final_value,
        unit=spec.unit,
        scope=scope,
        form=form or row.tipo_formulario,  # type: ignore[arg-type]
        version=row.versao,
        restated=row.versao > 1,
        value_source=value_source,
        comparables=AnaliseComparables(
            yoy_period_id=_period_id_for(periodicidade, base_periodo, row.data_referencia.year - 1, quarter),
            qoq_period_id=(
                None
                if periodicidade == "annual" or base_periodo == "ytd"
                else _period_id_for(
                    "quarterly",
                    "quarter",
                    row.data_referencia.year if quarter and quarter > 1 else row.data_referencia.year - 1,
                    (quarter - 1) if quarter and quarter > 1 else 4,
                )
            ),
        ),
        provenance=provenance or [_provenance_for(row, doc, form=form)],
    )


def _latest_document_subquery(cnpj: str, as_of: date | None) -> Any:
    stmt = (
        select(
            DocumentoFinanceiro.cnpj_companhia,
            DocumentoFinanceiro.tipo_formulario,
            DocumentoFinanceiro.data_referencia,
            func.max(DocumentoFinanceiro.versao).label("max_versao"),
        )
        .where(DocumentoFinanceiro.cnpj_companhia == cnpj)
    )
    if as_of is not None:
        stmt = stmt.where(_document_known_on_or_before(as_of))
    return stmt.group_by(
        DocumentoFinanceiro.cnpj_companhia,
        DocumentoFinanceiro.tipo_formulario,
        DocumentoFinanceiro.data_referencia,
    ).subquery()


def _load_context(db: Session, companhia: Companhia, scope: AnaliseEscopo, as_of: date | None) -> ContextData:
    doc_sq = _latest_document_subquery(companhia.cnpj_companhia, as_of)
    rows = [
        (row, doc)
        for row, doc in db.execute(
        select(DemonstracaoFinanceira, DocumentoFinanceiro)
        .join(
            doc_sq,
            and_(
                DemonstracaoFinanceira.cnpj_companhia == doc_sq.c.cnpj_companhia,
                DemonstracaoFinanceira.tipo_formulario == doc_sq.c.tipo_formulario,
                DemonstracaoFinanceira.data_referencia == doc_sq.c.data_referencia,
                DemonstracaoFinanceira.versao == doc_sq.c.max_versao,
            ),
        )
        .join(
            DocumentoFinanceiro,
            and_(
                DocumentoFinanceiro.cnpj_companhia == DemonstracaoFinanceira.cnpj_companhia,
                DocumentoFinanceiro.tipo_formulario == DemonstracaoFinanceira.tipo_formulario,
                DocumentoFinanceiro.data_referencia == DemonstracaoFinanceira.data_referencia,
                DocumentoFinanceiro.versao == DemonstracaoFinanceira.versao,
            ),
        )
        .where(DemonstracaoFinanceira.cnpj_companhia == companhia.cnpj_companhia)
        .where(DemonstracaoFinanceira.escopo_demonstracao == API_SCOPE_TO_DB[scope])
        .where(DemonstracaoFinanceira.valor_conta.is_not(None))
        .order_by(
            DemonstracaoFinanceira.tipo_formulario,
            DemonstracaoFinanceira.data_referencia,
            DemonstracaoFinanceira.tipo_demonstracao,
            DemonstracaoFinanceira.codigo_conta,
        )
        ).all()
    ]

    documents_stmt = select(DocumentoFinanceiro).where(DocumentoFinanceiro.cnpj_companhia == companhia.cnpj_companhia)
    if as_of is not None:
        documents_stmt = documents_stmt.where(_document_known_on_or_before(as_of))
    documents = list(
        db.scalars(
            documents_stmt.order_by(
                DocumentoFinanceiro.tipo_formulario,
                DocumentoFinanceiro.data_referencia,
                DocumentoFinanceiro.versao,
            )
        ).all()
    )

    periodos_disponiveis = _available_periods(rows, scope)
    qualidade = _build_quality(db, companhia, rows, documents, scope, periodos_disponiveis)
    return ContextData(companhia=companhia, rows=rows, documents=documents, qualidade=qualidade, periodos_disponiveis=periodos_disponiveis, issues=list(qualidade.issues))


def _available_periods(rows: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]], scope: AnaliseEscopo) -> list[AnalisePeriodoDisponivel]:
    seen: set[tuple[str, str, date]] = set()
    periodos: list[AnalisePeriodoDisponivel] = []
    annual_by_year: dict[int, tuple[DemonstracaoFinanceira, DocumentoFinanceiro]] = {}
    itr_by_quarter: dict[tuple[int, int], list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]] = defaultdict(list)

    for row, doc in rows:
        if not _row_current_exercise(row):
            continue
        if row.tipo_formulario == "DFP":
            annual_by_year[row.data_referencia.year] = (row, doc)
        elif row.tipo_formulario == "ITR":
            itr_by_quarter[(row.data_referencia.year, _quarter_from_date(row.data_referencia))].append((row, doc))

    for year, (row, _) in sorted(annual_by_year.items()):
        key = ("annual", "fy", row.data_referencia)
        if key not in seen:
            seen.add(key)
            periodos.append(
                AnalisePeriodoDisponivel(
                    period_id=f"FY{year}",
                    fiscal_year=year,
                    quarter=None,
                    periodicidade="annual",
                    base_periodo="fy",
                    period_nature="duration",
                    start_date=date(year, 1, 1),
                    end_date=row.data_fim_exercicio or row.data_referencia,
                    form="DFP",
                    scope=scope,
                    restated=row.versao > 1,
                )
            )
            periodos.append(
                AnalisePeriodoDisponivel(
                    period_id=f"{year}-Q4",
                    fiscal_year=year,
                    quarter=4,
                    periodicidade="quarterly",
                    base_periodo="quarter",
                    period_nature="duration",
                    start_date=date(year, 10, 1),
                    end_date=row.data_fim_exercicio or row.data_referencia,
                    form="DERIVED",
                    scope=scope,
                    restated=row.versao > 1,
                )
            )

    for (year, quarter), bucket in sorted(itr_by_quarter.items()):
        row = bucket[0][0]
        periodos.append(
            AnalisePeriodoDisponivel(
                period_id=f"{year}-Q{quarter}",
                fiscal_year=year,
                quarter=quarter,
                periodicidade="quarterly",
                base_periodo="quarter",
                period_nature="duration",
                start_date=_quarter_start(year, quarter),
                end_date=row.data_referencia,
                form="ITR",
                scope=scope,
                restated=row.versao > 1,
            )
        )
        periodos.append(
            AnalisePeriodoDisponivel(
                period_id=f"{year}-YTDQ{quarter}",
                fiscal_year=year,
                quarter=quarter,
                periodicidade="quarterly",
                base_periodo="ytd",
                period_nature="duration",
                start_date=date(year, 1, 1),
                end_date=row.data_referencia,
                form="ITR",
                scope=scope,
                restated=row.versao > 1,
            )
        )

    periodos.sort(key=lambda item: (item.fiscal_year, item.quarter or 0, item.periodicidade, item.base_periodo))
    return periodos


def _build_quality(
    db: Session,
    companhia: Companhia,
    rows: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]],
    documents: list[DocumentoFinanceiro],
    scope: AnaliseEscopo,
    periodos_disponiveis: list[AnalisePeriodoDisponivel],
) -> AnaliseQualidadeResumo:
    issues: list[AnaliseIssue] = []
    by_doc_period: dict[tuple[str, int, int | None], int] = defaultdict(int)
    itr_quarters_by_year: dict[int, set[int]] = defaultdict(set)

    for row, _ in rows:
        if row.tipo_formulario == "DFP" and row.ordem_exercicio != "ÚLTIMO":
            issues.append(
                AnaliseIssue(
                    code="NON_CURRENT_EXERCISE_PRESENT",
                    severity="warning",
                    message="Foram encontradas linhas comparativas no mesmo documento; a resolução atual usa somente `ordem_exercicio=ÚLTIMO`.",
                    affected_period_ids=[f"FY{row.data_referencia.year}"],
                )
            )
        if row.tipo_formulario == "ITR":
            itr_quarters_by_year[row.data_referencia.year].add(_quarter_from_date(row.data_referencia))
        by_doc_period[(row.tipo_formulario, row.data_referencia.year, _quarter_from_date(row.data_referencia) if row.tipo_formulario == "ITR" else None)] += 1

    for year, quarters in sorted(itr_quarters_by_year.items()):
        expected = {1, 2, 3}
        missing = sorted(expected - quarters)
        if missing:
            issues.append(
                AnaliseIssue(
                    code="MISSING_ITR_QUARTER",
                    severity="warning",
                    message=f"Faltam ITRs para os trimestres {missing} do exercício {year}.",
                    affected_period_ids=[f"{year}-Q{quarter}" for quarter in missing],
                )
            )

    restatements = sum(1 for doc in documents if doc.versao > 1)

    parecer_issue = db.scalar(
        select(func.count(ParecerFinanceiro.id)).where(
            ParecerFinanceiro.cnpj_companhia == companhia.cnpj_companhia,
            or_(
                ParecerFinanceiro.tipo_parecer_declaracao.ilike("%ressalva%"),
                ParecerFinanceiro.texto_parecer_declaracao.ilike("%ressalva%"),
            ),
        )
    ) or 0
    if parecer_issue:
        issues.append(
            AnaliseIssue(
                code="AUDITOR_WITH_QUALIFICATION",
                severity="warning",
                message="Foram encontrados pareceres com menção a ressalva.",
                affected_period_ids=[],
            )
        )

    completude: Literal["complete", "partial", "missing"]
    if periodos_disponiveis:
        completude = "complete" if not any(issue.code == "MISSING_ITR_QUARTER" for issue in issues) else "partial"
    else:
        completude = "missing"

    comparabilidade: Literal["complete", "partial", "missing"]
    if not periodos_disponiveis:
        comparabilidade = "missing"
    elif any(issue.code in {"MISSING_ITR_QUARTER"} for issue in issues):
        comparabilidade = "partial"
    else:
        comparabilidade = "complete"

    consistencia: Literal["complete", "partial", "missing"]
    consistencia = "partial" if restatements or parecer_issue else "complete"

    return AnaliseQualidadeResumo(
        completude=completude,
        comparabilidade=comparabilidade,
        consistencia=consistencia,
        restatements=restatements,
        issues=_dedupe_issues(issues),
        checked_at=datetime.now(UTC),
        ruleset_version=CALCULATION_VERSION,
    )


def _dedupe_issues(issues: list[AnaliseIssue]) -> list[AnaliseIssue]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduped: list[AnaliseIssue] = []
    for issue in issues:
        key = (issue.code, issue.message, tuple(issue.affected_period_ids))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _dedupe_unavailable(items: list[AnaliseSeriesUnavailable]) -> list[AnaliseSeriesUnavailable]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[AnaliseSeriesUnavailable] = []
    for item in items:
        key = (item.metric_id, item.period_id, item.reason_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _filter_metric_ids(metricas: list[str] | None) -> list[str]:
    if not metricas:
        return list(METRIC_SPECS.keys())
    return [metric_id for metric_id in metricas if metric_id in METRIC_SPECS]


def _index_rows_by_account(rows: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]) -> dict[str, list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]]:
    index: dict[str, list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]] = defaultdict(list)
    for row, doc in rows:
        if row.codigo_conta:
            index[row.codigo_conta].append((row, doc))
    return index


def _pick_annual_row(bucket: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]], year: int) -> tuple[DemonstracaoFinanceira, DocumentoFinanceiro] | None:
    current = [
        item
        for item in bucket
        if item[0].tipo_formulario == "DFP"
        and item[0].data_referencia.year == year
        and _row_current_exercise(item[0])
    ]
    if not current:
        return None
    current.sort(key=lambda item: (item[0].versao, item[1].data_recebimento or item[0].data_referencia), reverse=True)
    return current[0]


def _pick_itr_direct_row(bucket: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]], year: int, quarter: int) -> tuple[DemonstracaoFinanceira, DocumentoFinanceiro] | None:
    start = _quarter_start(year, quarter)
    end = _quarter_end(year, quarter)
    candidates = [
        item
        for item in bucket
        if item[0].tipo_formulario == "ITR"
        and item[0].data_referencia.year == year
        and _quarter_from_date(item[0].data_referencia) == quarter
        and _row_current_exercise(item[0])
        and item[0].data_inicio_exercicio == start
        and (item[0].data_fim_exercicio or item[0].data_referencia) == end
    ]
    candidates.sort(key=lambda item: item[0].versao, reverse=True)
    return candidates[0] if candidates else None


def _pick_itr_ytd_row(bucket: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]], year: int, quarter: int) -> tuple[DemonstracaoFinanceira, DocumentoFinanceiro] | None:
    end = _quarter_end(year, quarter)
    candidates = [
        item
        for item in bucket
        if item[0].tipo_formulario == "ITR"
        and item[0].data_referencia.year == year
        and _quarter_from_date(item[0].data_referencia) == quarter
        and _row_current_exercise(item[0])
        and item[0].data_inicio_exercicio == date(year, 1, 1)
        and (item[0].data_fim_exercicio or item[0].data_referencia) == end
    ]
    candidates.sort(key=lambda item: item[0].versao, reverse=True)
    return candidates[0] if candidates else None


def _pick_stock_quarter_row(bucket: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]], year: int, quarter: int) -> tuple[DemonstracaoFinanceira, DocumentoFinanceiro] | None:
    end = _quarter_end(year, quarter)
    form = "DFP" if quarter == 4 else "ITR"
    candidates = [
        item
        for item in bucket
        if item[0].tipo_formulario == form
        and item[0].data_referencia.year == year
        and (item[0].data_fim_exercicio or item[0].data_referencia) == end
        and _row_current_exercise(item[0])
    ]
    candidates.sort(key=lambda item: item[0].versao, reverse=True)
    return candidates[0] if candidates else None


def _pick_rows_by_prefix(
    rows_by_account: dict[str, list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]],
    prefixes: tuple[str, ...],
) -> list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]:
    matches: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]] = []
    for account_code, bucket in rows_by_account.items():
        if any(account_code == prefix or account_code.startswith(f"{prefix}.") for prefix in prefixes):
            matches.extend(bucket)
    return matches


def _pick_account_rows_for_period(
    bucket: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]],
    spec: MetricSpec,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    year: int,
    quarter: int | None,
) -> list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]:
    picked_rows: list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]] = []
    account_codes: set[str] = set()
    for row, doc in bucket:
        if row.codigo_conta in account_codes:
            continue
        chosen: tuple[DemonstracaoFinanceira, DocumentoFinanceiro] | None = None
        if periodicidade == "annual":
            chosen = _pick_annual_row([(row, doc)], year)
        else:
            assert quarter is not None
            if spec.metric_type == "stock":
                chosen = _pick_stock_quarter_row([(row, doc)], year, quarter)
            elif base_periodo == "ytd":
                chosen = _pick_itr_ytd_row([(row, doc)], year, quarter)
                if chosen is None and quarter == 4:
                    chosen = _pick_annual_row([(row, doc)], year)
            else:
                chosen = _pick_itr_direct_row([(row, doc)], year, quarter)
                if chosen is None and quarter == 1:
                    chosen = _pick_itr_ytd_row([(row, doc)], year, quarter)
                elif chosen is None and quarter in (2, 3):
                    continue
                elif chosen is None and quarter == 4:
                    continue
        if chosen is not None and chosen[0].codigo_conta:
            account_codes.add(chosen[0].codigo_conta)
            picked_rows.append(chosen)
    return picked_rows


def _resolve_aggregated_metric_for_period(
    rows_by_account: dict[str, list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]],
    spec: MetricSpec,
    scope: AnaliseEscopo,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    year: int,
    quarter: int | None,
    *,
    absolute_result: bool = False,
) -> ResolvedFact | None:
    bucket = _pick_rows_by_prefix(rows_by_account, spec.candidate_accounts)
    if not bucket:
        return None
    if periodicidade == "quarterly" and base_periodo == "quarter" and quarter in (2, 3, 4):
        return None
    picked_rows = _pick_account_rows_for_period(bucket, spec, periodicidade, base_periodo, year, quarter)
    if not picked_rows:
        return None
    values: list[Decimal] = []
    provenance: list[AnaliseProvenienciaItem] = []
    for row, doc in picked_rows:
        row_value = _row_value(row)
        if row_value is None:
            continue
        values.append(abs(row_value) if absolute_result else row_value)
        provenance.append(_provenance_for(row, doc))
    if not values:
        return None
    row, doc = picked_rows[0]
    return _resolved_from_row(
        metric_id=spec.metric_id,
        spec=spec,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        row=row,
        doc=doc,
        scope=scope,
        value=sum(values, Decimal("0")),
        provenance=provenance,
        form=row.tipo_formulario,  # type: ignore[arg-type]
    )


def _resolve_base_metric_for_period(
    rows_by_account: dict[str, list[tuple[DemonstracaoFinanceira, DocumentoFinanceiro]]],
    spec: MetricSpec,
    scope: AnaliseEscopo,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    year: int,
    quarter: int | None,
) -> ResolvedFact | None:
    for account_code in spec.candidate_accounts:
        bucket = rows_by_account.get(account_code, [])
        if periodicidade == "annual":
            picked = _pick_annual_row(bucket, year)
            if picked:
                row, doc = picked
                return _resolved_from_row(
                    metric_id=spec.metric_id,
                    spec=spec,
                    periodicidade="annual",
                    base_periodo="fy",
                    row=row,
                    doc=doc,
                    scope=scope,
                )
            continue

        assert quarter is not None
        if spec.metric_type == "stock":
            picked = _pick_stock_quarter_row(bucket, year, quarter)
            if picked:
                row, doc = picked
                return _resolved_from_row(
                    metric_id=spec.metric_id,
                    spec=spec,
                    periodicidade="quarterly",
                    base_periodo="quarter",
                    row=row,
                    doc=doc,
                    scope=scope,
                )
            continue

        if base_periodo == "ytd":
            picked = _pick_itr_ytd_row(bucket, year, quarter)
            if picked:
                row, doc = picked
                return _resolved_from_row(
                    metric_id=spec.metric_id,
                    spec=spec,
                    periodicidade="quarterly",
                    base_periodo="ytd",
                    row=row,
                    doc=doc,
                    scope=scope,
                )
            if quarter == 4:
                picked = _pick_annual_row(bucket, year)
                if picked:
                    row, doc = picked
                    return _resolved_from_row(
                        metric_id=spec.metric_id,
                        spec=spec,
                        periodicidade="quarterly",
                        base_periodo="ytd",
                        row=row,
                        doc=doc,
                        scope=scope,
                        form="DFP",
                    )
            continue

        direct = _pick_itr_direct_row(bucket, year, quarter)
        if direct:
            row, doc = direct
            return _resolved_from_row(
                metric_id=spec.metric_id,
                spec=spec,
                periodicidade="quarterly",
                base_periodo="quarter",
                row=row,
                doc=doc,
                scope=scope,
            )

        if quarter == 1:
            ytd = _pick_itr_ytd_row(bucket, year, quarter)
            if ytd:
                row, doc = ytd
                return _resolved_from_row(
                    metric_id=spec.metric_id,
                    spec=spec,
                    periodicidade="quarterly",
                    base_periodo="quarter",
                    row=row,
                    doc=doc,
                    scope=scope,
                )
            continue

        if quarter in (2, 3):
            current_ytd = _pick_itr_ytd_row(bucket, year, quarter)
            previous_ytd = _pick_itr_ytd_row(bucket, year, quarter - 1)
            if current_ytd and previous_ytd:
                row_curr, doc_curr = current_ytd
                row_prev, doc_prev = previous_ytd
                value_curr = _row_value(row_curr)
                value_prev = _row_value(row_prev)
                if value_curr is not None and value_prev is not None:
                    return _resolved_from_row(
                        metric_id=spec.metric_id,
                        spec=spec,
                        periodicidade="quarterly",
                        base_periodo="quarter",
                        row=row_curr,
                        doc=doc_curr,
                        scope=scope,
                        value_source="derived_from_ytd_delta",
                        provenance=[_provenance_for(row_curr, doc_curr), _provenance_for(row_prev, doc_prev)],
                        form="DERIVED",
                        value=value_curr - value_prev,
                    )
            continue

        if quarter == 4:
            annual = _pick_annual_row(bucket, year)
            q3_ytd = _pick_itr_ytd_row(bucket, year, 3)
            if annual and q3_ytd:
                row_annual, doc_annual = annual
                row_q3, doc_q3 = q3_ytd
                annual_value = _row_value(row_annual)
                q3_value = _row_value(row_q3)
                if annual_value is not None and q3_value is not None:
                    return _resolved_from_row(
                        metric_id=spec.metric_id,
                        spec=spec,
                        periodicidade="quarterly",
                        base_periodo="quarter",
                        row=row_annual,
                        doc=doc_annual,
                        scope=scope,
                        value_source="derived_from_dfp_minus_ytd",
                        provenance=[_provenance_for(row_annual, doc_annual, form="DFP"), _provenance_for(row_q3, doc_q3, form="ITR")],
                        form="DERIVED",
                        value=annual_value - q3_value,
                    )
    return None


def _candidate_periods(
    context: ContextData,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    horizonte_anos: int | None = None,
) -> list[tuple[int, int | None]]:
    periods = []
    for item in context.periodos_disponiveis:
        if item.periodicidade != periodicidade:
            continue
        if item.base_periodo != base_periodo:
            continue
        periods.append((item.fiscal_year, item.quarter))
    deduped = sorted(set(periods))
    if periodicidade == "annual" and base_periodo == "fy" and horizonte_anos is not None and horizonte_anos > 0:
        deduped = deduped[-horizonte_anos:]
    return deduped


def _resolve_series_facts(
    context: ContextData,
    metric_ids: list[str],
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    scope: AnaliseEscopo,
    horizonte_anos: int | None = None,
) -> tuple[list[ResolvedFact], list[AnaliseSeriesUnavailable], list[AnaliseIssue]]:
    requested_metric_ids = list(metric_ids)
    metric_ids = _expand_metric_dependencies(metric_ids)
    rows_by_account = _index_rows_by_account(context.rows)
    issues = list(context.issues)
    facts_by_metric_period: dict[tuple[str, str], ResolvedFact] = {}
    unavailable: list[AnaliseSeriesUnavailable] = []

    for year, quarter in _candidate_periods(context, periodicidade, base_periodo, horizonte_anos):
        for metric_id in metric_ids:
            spec = METRIC_SPECS[metric_id]
            if base_periodo not in spec.bases:
                unavailable.append(
                    AnaliseSeriesUnavailable(
                        metric_id=metric_id,
                        period_id=_period_id_for(periodicidade, base_periodo, year, quarter),
                        status="unavailable",
                        reason_code="METRIC_BASE_NOT_SUPPORTED",
                        message=f"A métrica `{metric_id}` não suporta a base temporal `{base_periodo}`.",
                        missing=[base_periodo],
                    )
                )
                continue

            if spec.formula:
                continue

            if metric_id == "divida_bruta":
                resolved = _resolve_aggregated_metric_for_period(
                    rows_by_account,
                    spec,
                    scope,
                    periodicidade,
                    base_periodo,
                    year,
                    quarter,
                )
                period_id = _period_id_for(periodicidade, base_periodo, year, quarter)
                if resolved is None:
                    unavailable.append(
                        AnaliseSeriesUnavailable(
                            metric_id=metric_id,
                            period_id=period_id,
                            status="unavailable",
                            reason_code="MISSING_SOURCE_FACT",
                            message=f"Não há fato corrente suficiente para resolver `{metric_id}` em `{period_id}`.",
                            missing=list(spec.candidate_accounts),
                        )
                    )
                    continue
                facts_by_metric_period[(metric_id, period_id)] = resolved
                continue

            if metric_id in {"capex", "depreciacao_amortizacao"}:
                resolved = _resolve_aggregated_metric_for_period(
                    rows_by_account,
                    spec,
                    scope,
                    periodicidade,
                    base_periodo,
                    year,
                    quarter,
                    absolute_result=(metric_id == "capex"),
                )
                period_id = _period_id_for(periodicidade, base_periodo, year, quarter)
                if resolved is None:
                    unavailable.append(
                        AnaliseSeriesUnavailable(
                            metric_id=metric_id,
                            period_id=period_id,
                            status="unavailable",
                            reason_code="MISSING_SOURCE_FACT",
                            message=f"Não há fato corrente suficiente para resolver `{metric_id}` em `{period_id}`.",
                            missing=list(spec.candidate_accounts),
                        )
                    )
                    continue
                facts_by_metric_period[(metric_id, period_id)] = resolved
                continue

            resolved = _resolve_base_metric_for_period(rows_by_account, spec, scope, periodicidade, base_periodo, year, quarter)
            period_id = _period_id_for(periodicidade, base_periodo, year, quarter)
            if resolved is None:
                unavailable.append(
                    AnaliseSeriesUnavailable(
                        metric_id=metric_id,
                        period_id=period_id,
                        status="unavailable",
                        reason_code="MISSING_SOURCE_FACT",
                        message=f"Não há fato corrente suficiente para resolver `{metric_id}` em `{period_id}`.",
                        missing=list(spec.candidate_accounts) or [metric_id],
                    )
                )
                continue
            facts_by_metric_period[(metric_id, period_id)] = resolved

    derived_metric_ids = [metric_id for metric_id in metric_ids if METRIC_SPECS[metric_id].formula]
    for year, quarter in _candidate_periods(context, periodicidade, base_periodo, horizonte_anos):
        period_id = _period_id_for(periodicidade, base_periodo, year, quarter)
        for metric_id in derived_metric_ids:
            spec = METRIC_SPECS[metric_id]
            if metric_id == "margem_liquida":
                lucro = facts_by_metric_period.get(("lucro_liquido", period_id))
                receita = facts_by_metric_period.get(("receita_liquida", period_id))
                if lucro and receita:
                    ratio = _safe_div(lucro.value, receita.value)
                    if ratio is not None:
                        facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                            metric_id=metric_id,
                            period_id=period_id,
                            fiscal_year=year,
                            quarter=quarter,
                            period_nature=spec.period_nature,
                            period_basis=base_periodo,
                            start_date=receita.start_date,
                            end_date=receita.end_date,
                            value=ratio,
                            unit=spec.unit,
                            scope=scope,
                            form="DERIVED",
                            version=max(filter(None, [lucro.version, receita.version]), default=None),
                            restated=lucro.restated or receita.restated,
                            value_source="derived_from_formula",
                            comparables=AnaliseComparables(
                                yoy_period_id=receita.comparables.yoy_period_id,
                                qoq_period_id=receita.comparables.qoq_period_id,
                            ),
                            provenance=[*lucro.provenance, *receita.provenance],
                        )
                        continue
                unavailable.append(
                    AnaliseSeriesUnavailable(
                        metric_id=metric_id,
                        period_id=period_id,
                        status="unavailable",
                        reason_code="MISSING_FORMULA_COMPONENT",
                        message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.",
                        missing=["lucro_liquido", "receita_liquida"],
                    )
                )
            elif metric_id == "ebitda":
                ebit = facts_by_metric_period.get(("ebit", period_id))
                dep = facts_by_metric_period.get(("depreciacao_amortizacao", period_id))
                if ebit and dep:
                    facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                        metric_id=metric_id,
                        period_id=period_id,
                        fiscal_year=year,
                        quarter=quarter,
                        period_nature=spec.period_nature,
                        period_basis=base_periodo,
                        start_date=ebit.start_date,
                        end_date=ebit.end_date,
                        value=ebit.value + dep.value,
                        unit=spec.unit,
                        scope=scope,
                        form="DERIVED",
                        version=max(filter(None, [ebit.version, dep.version]), default=None),
                        restated=ebit.restated or dep.restated,
                        value_source="derived_from_formula",
                        comparables=AnaliseComparables(yoy_period_id=ebit.comparables.yoy_period_id, qoq_period_id=ebit.comparables.qoq_period_id),
                        provenance=[*ebit.provenance, *dep.provenance],
                    )
                    continue
                unavailable.append(
                    AnaliseSeriesUnavailable(metric_id=metric_id, period_id=period_id, status="unavailable", reason_code="MISSING_FORMULA_COMPONENT", message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.", missing=["ebit", "depreciacao_amortizacao"])
                )
            elif metric_id == "caixa_livre":
                caixa = facts_by_metric_period.get(("caixa_operacional", period_id))
                capex = facts_by_metric_period.get(("capex", period_id))
                if caixa and capex:
                    facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                        metric_id=metric_id,
                        period_id=period_id,
                        fiscal_year=year,
                        quarter=quarter,
                        period_nature=spec.period_nature,
                        period_basis=base_periodo,
                        start_date=caixa.start_date,
                        end_date=caixa.end_date,
                        value=caixa.value - capex.value,
                        unit=spec.unit,
                        scope=scope,
                        form="DERIVED",
                        version=max(filter(None, [caixa.version, capex.version]), default=None),
                        restated=caixa.restated or capex.restated,
                        value_source="derived_from_formula",
                        comparables=AnaliseComparables(yoy_period_id=caixa.comparables.yoy_period_id, qoq_period_id=caixa.comparables.qoq_period_id),
                        provenance=[*caixa.provenance, *capex.provenance],
                    )
                    continue
                unavailable.append(
                    AnaliseSeriesUnavailable(metric_id=metric_id, period_id=period_id, status="unavailable", reason_code="MISSING_FORMULA_COMPONENT", message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.", missing=["caixa_operacional", "capex"])
                )
            elif metric_id == "divida_liquida":
                bruta = facts_by_metric_period.get(("divida_bruta", period_id))
                caixa = facts_by_metric_period.get(("caixa_equivalentes", period_id))
                if bruta and caixa:
                    facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                        metric_id=metric_id,
                        period_id=period_id,
                        fiscal_year=year,
                        quarter=quarter,
                        period_nature=spec.period_nature,
                        period_basis=base_periodo,
                        start_date=None,
                        end_date=bruta.end_date,
                        value=bruta.value - caixa.value,
                        unit=spec.unit,
                        scope=scope,
                        form="DERIVED",
                        version=max(filter(None, [bruta.version, caixa.version]), default=None),
                        restated=bruta.restated or caixa.restated,
                        value_source="derived_from_formula",
                        comparables=AnaliseComparables(yoy_period_id=bruta.comparables.yoy_period_id, qoq_period_id=bruta.comparables.qoq_period_id),
                        provenance=[*bruta.provenance, *caixa.provenance],
                    )
                    continue
                unavailable.append(
                    AnaliseSeriesUnavailable(metric_id=metric_id, period_id=period_id, status="unavailable", reason_code="MISSING_FORMULA_COMPONENT", message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.", missing=["divida_bruta", "caixa_equivalentes"])
                )
            elif metric_id == "alavancagem":
                divida = facts_by_metric_period.get(("divida_liquida", period_id))
                ebitda = facts_by_metric_period.get(("ebitda", period_id))
                if divida and ebitda:
                    ratio = _safe_div(divida.value, ebitda.value)
                    if ratio is not None:
                        facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                            metric_id=metric_id,
                            period_id=period_id,
                            fiscal_year=year,
                            quarter=quarter,
                            period_nature=spec.period_nature,
                            period_basis=base_periodo,
                            start_date=None,
                            end_date=divida.end_date,
                            value=ratio,
                            unit=spec.unit,
                            scope=scope,
                            form="DERIVED",
                            version=max(filter(None, [divida.version, ebitda.version]), default=None),
                            restated=divida.restated or ebitda.restated,
                            value_source="derived_from_formula",
                            comparables=AnaliseComparables(yoy_period_id=divida.comparables.yoy_period_id, qoq_period_id=divida.comparables.qoq_period_id),
                            provenance=[*divida.provenance, *ebitda.provenance],
                        )
                        continue
                unavailable.append(
                    AnaliseSeriesUnavailable(metric_id=metric_id, period_id=period_id, status="unavailable", reason_code="MISSING_FORMULA_COMPONENT", message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.", missing=["divida_liquida", "ebitda"])
                )
            elif metric_id == "conversao_lucro_caixa":
                caixa = facts_by_metric_period.get(("caixa_operacional", period_id))
                lucro = facts_by_metric_period.get(("lucro_liquido", period_id))
                if caixa and lucro:
                    ratio = _safe_div(caixa.value, lucro.value)
                    if ratio is not None:
                        facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                            metric_id=metric_id,
                            period_id=period_id,
                            fiscal_year=year,
                            quarter=quarter,
                            period_nature=spec.period_nature,
                            period_basis=base_periodo,
                            start_date=caixa.start_date,
                            end_date=caixa.end_date,
                            value=ratio,
                            unit=spec.unit,
                            scope=scope,
                            form="DERIVED",
                            version=max(filter(None, [caixa.version, lucro.version]), default=None),
                            restated=caixa.restated or lucro.restated,
                            value_source="derived_from_formula",
                            comparables=AnaliseComparables(yoy_period_id=caixa.comparables.yoy_period_id, qoq_period_id=caixa.comparables.qoq_period_id),
                            provenance=[*caixa.provenance, *lucro.provenance],
                        )
                        continue
                unavailable.append(
                    AnaliseSeriesUnavailable(metric_id=metric_id, period_id=period_id, status="unavailable", reason_code="MISSING_FORMULA_COMPONENT", message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.", missing=["caixa_operacional", "lucro_liquido"])
                )
            elif metric_id == "liquidez_corrente":
                ativo = facts_by_metric_period.get(("ativo_circulante", period_id))
                passivo = facts_by_metric_period.get(("passivo_circulante", period_id))
                if ativo and passivo:
                    ratio = _safe_div(ativo.value, passivo.value)
                    if ratio is not None:
                        facts_by_metric_period[(metric_id, period_id)] = ResolvedFact(
                            metric_id=metric_id,
                            period_id=period_id,
                            fiscal_year=year,
                            quarter=quarter,
                            period_nature=spec.period_nature,
                            period_basis=base_periodo,
                            start_date=None,
                            end_date=ativo.end_date,
                            value=ratio,
                            unit=spec.unit,
                            scope=scope,
                            form="DERIVED",
                            version=max(filter(None, [ativo.version, passivo.version]), default=None),
                            restated=ativo.restated or passivo.restated,
                            value_source="derived_from_formula",
                            comparables=AnaliseComparables(
                                yoy_period_id=ativo.comparables.yoy_period_id,
                                qoq_period_id=ativo.comparables.qoq_period_id,
                            ),
                            provenance=[*ativo.provenance, *passivo.provenance],
                        )
                        continue
                unavailable.append(
                    AnaliseSeriesUnavailable(
                        metric_id=metric_id,
                        period_id=period_id,
                        status="unavailable",
                        reason_code="MISSING_FORMULA_COMPONENT",
                        message=f"Não foi possível calcular `{metric_id}` porque faltam componentes da fórmula.",
                        missing=["ativo_circulante", "passivo_circulante"],
                    )
                )

    facts = sorted(
        [item for item in facts_by_metric_period.values() if item.metric_id in requested_metric_ids],
        key=lambda item: (item.fiscal_year, item.quarter or 0, item.metric_id),
    )
    filtered_unavailable = _dedupe_unavailable([item for item in unavailable if item.metric_id in requested_metric_ids])
    return facts, filtered_unavailable, _dedupe_issues(issues)


def _observation_from_fact(fact: ResolvedFact) -> AnaliseSeriesObservation:
    return AnaliseSeriesObservation(
        metric_id=fact.metric_id,
        period_id=fact.period_id,
        fiscal_year=fact.fiscal_year,
        quarter=fact.quarter,
        period_nature=fact.period_nature,
        period_basis=fact.period_basis,
        start_date=fact.start_date,
        end_date=fact.end_date,
        value=fact.value,
        unit=fact.unit,
        scope=fact.scope,
        form=fact.form,
        version=fact.version,
        restated=fact.restated,
        value_source=fact.value_source,
        comparables=fact.comparables,
        provenance=fact.provenance,
    )


def listar_metricas() -> AnaliseMetricasCatalogoResposta:
    return AnaliseMetricasCatalogoResposta(
        calculation_version=CALCULATION_VERSION,
        metricas=[
            AnaliseMetricaCatalogoItem(
                id=spec.metric_id,
                nome=spec.nome,
                type=spec.metric_type,
                unit=spec.unit,
                formula=spec.formula,
                direction=spec.direction,
                contas_cvm_candidatas=list(spec.candidate_accounts),
                estrategia_resolucao=spec.strategy,
                disponibilidades=list(spec.bases),
                period_nature=spec.period_nature,
                vertical_denominator_metric_id=spec.vertical_denominator_metric_id,
                limitations=list(spec.limitations),
                calculation_version=CALCULATION_VERSION,
            )
            for spec in METRIC_SPECS.values()
        ],
    )


def _links_analise(companhia: Companhia) -> AnaliseLinkSet:
    return AnaliseLinkSet(
        series=f"/analise/companhias/{companhia.codigo_cvm}/series",
        comparacoes=f"/analise/companhias/{companhia.codigo_cvm}/comparacoes",
        qualidade=f"/analise/companhias/{companhia.codigo_cvm}/qualidade",
        sinais=f"/analise/companhias/{companhia.codigo_cvm}/sinais",
        eventos=f"/analise/companhias/{companhia.codigo_cvm}/eventos",
        restatements=f"/analise/companhias/{companhia.codigo_cvm}/restatements",
        governanca=f"/analise/companhias/{companhia.codigo_cvm}/governanca",
        pessoas=f"/analise/companhias/{companhia.codigo_cvm}/pessoas",
        brief=f"/analise/companhias/{companhia.codigo_cvm}/brief",
    )


def _runtime_resolution(as_of: date | None) -> AnaliseResolutionMetadata:
    return AnaliseResolutionMetadata(
        mode="runtime_fallback",
        materialization_execution_id=None,
        materialized_at=None,
        as_of=as_of,
    )


def _canonical_resolution(execucao: AnaliseMaterializacaoExecucao, as_of: date | None) -> AnaliseResolutionMetadata:
    return AnaliseResolutionMetadata(
        mode="canonical",
        materialization_execution_id=str(execucao.id),
        materialized_at=execucao.finished_at,
        as_of=as_of,
    )


def _jsonable_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return json.loads(value.model_dump_json())
    if isinstance(value, list):
        return [_jsonable_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable_payload(item) for key, item in value.items()}
    return value


def _payload_fingerprint(value: Any) -> str:
    serialized = json.dumps(_jsonable_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _companhia_tem_registro_cancelado(companhia: Companhia) -> bool:
    return (companhia.situacao_registro or "").strip().upper() == "CANCELADA"


def _default_period_id(periodos: list[AnalisePeriodoDisponivel]) -> str:
    annual_periods = [periodo for periodo in periodos if periodo.periodicidade == "annual" and periodo.base_periodo == "fy"]
    return annual_periods[-1].period_id if annual_periods else "FY0"


def _latest_successful_materialization(
    db: Session,
    companhia: Companhia,
    scope: AnaliseEscopo,
) -> AnaliseMaterializacaoExecucao | None:
    return db.scalar(
        select(AnaliseMaterializacaoExecucao)
        .where(
            AnaliseMaterializacaoExecucao.codigo_cvm == companhia.codigo_cvm,
            AnaliseMaterializacaoExecucao.escopo == scope,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
            AnaliseMaterializacaoExecucao.status == "success",
            AnaliseMaterializacaoExecucao.coverage_complete.is_(True),
        )
        .order_by(AnaliseMaterializacaoExecucao.finished_at.desc(), AnaliseMaterializacaoExecucao.created_at.desc())
        .limit(1)
    )


def _context_revision_for_as_of(
    db: Session,
    companhia: Companhia,
    scope: AnaliseEscopo,
    as_of: date | None,
) -> tuple[AnaliseMaterializacaoExecucao, AnaliseContextoRevision] | None:
    execucao = _latest_successful_materialization(db, companhia, scope)
    if execucao is None:
        return None
    stmt = (
        select(AnaliseContextoRevision)
        .where(
            AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
            AnaliseContextoRevision.escopo == scope,
            AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
        )
    )
    if as_of is None:
        stmt = stmt.where(AnaliseContextoRevision.known_to.is_(None))
    else:
        stmt = stmt.where(
            AnaliseContextoRevision.known_from <= as_of,
            or_(AnaliseContextoRevision.known_to.is_(None), AnaliseContextoRevision.known_to > as_of),
        )
    stmt = stmt.order_by(AnaliseContextoRevision.known_from.desc()).limit(1)
    revision = db.scalar(stmt)
    if revision is None:
        return None
    return execucao, revision


def _series_from_canonical(
    db: Session,
    companhia: Companhia,
    *,
    metricas: list[str] | None,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    scope: AnaliseEscopo,
    as_of: date | None,
) -> AnaliseSeriesResposta | None:
    context_pair = _context_revision_for_as_of(db, companhia, scope, as_of)
    if context_pair is None:
        return None
    execucao, context_revision = context_pair
    metric_ids = _filter_metric_ids(metricas)
    stmt = (
        select(AnaliseFatoRevision)
        .where(
            AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
            AnaliseFatoRevision.escopo == scope,
            AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
            AnaliseFatoRevision.periodicidade == periodicidade,
            AnaliseFatoRevision.base_periodo == base_periodo,
            AnaliseFatoRevision.metric_id.in_(metric_ids),
        )
    )
    if as_of is None:
        stmt = stmt.where(AnaliseFatoRevision.known_to.is_(None))
    else:
        stmt = stmt.where(
            AnaliseFatoRevision.known_from <= as_of,
            or_(AnaliseFatoRevision.known_to.is_(None), AnaliseFatoRevision.known_to > as_of),
        )
    revisions = db.scalars(stmt.order_by(AnaliseFatoRevision.fiscal_year, AnaliseFatoRevision.quarter, AnaliseFatoRevision.metric_id)).all()
    if not revisions:
        return None

    observacoes: list[AnaliseSeriesObservation] = []
    indisponibilidades: list[AnaliseSeriesUnavailable] = []
    for revision in revisions:
        if revision.status == "available" and revision.observation_payload is not None:
            observacoes.append(AnaliseSeriesObservation.model_validate(revision.observation_payload))
        elif revision.status == "unavailable" and revision.unavailable_payload is not None:
            indisponibilidades.append(AnaliseSeriesUnavailable.model_validate(revision.unavailable_payload))

    return AnaliseSeriesResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        escopo=scope,
        metricas=metric_ids,
        resolution=_canonical_resolution(execucao, as_of),
        observacoes=observacoes,
        indisponibilidades=indisponibilidades,
        issues=[AnaliseIssue.model_validate(item) for item in context_revision.issues],
    )


def _obter_manifesto_runtime(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseManifestoResposta:
    context = _load_context(db, companhia, scope, as_of)
    annual_periods = [periodo for periodo in context.periodos_disponiveis if periodo.periodicidade == "annual" and periodo.base_periodo == "fy"]
    latest_period = annual_periods[-1].period_id if annual_periods else "FY0"
    return AnaliseManifestoResposta(
        companhia=_companhia_resumo(companhia),
        contexto_padrao=AnaliseContextoPadrao(periodo_id=latest_period, periodicidade="annual", escopo=scope),
        periodos_disponiveis=context.periodos_disponiveis,
        qualidade=context.qualidade,
        calculation_version=CALCULATION_VERSION,
        resolution=_runtime_resolution(as_of),
        links=_links_analise(companhia),
    )


def obter_manifesto(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseManifestoResposta:
    context_pair = _context_revision_for_as_of(db, companhia, scope, as_of)
    if context_pair is None:
        return _obter_manifesto_runtime(db, companhia, scope=scope, as_of=as_of)
    execucao, revision = context_pair
    periodos = [AnalisePeriodoDisponivel.model_validate(item) for item in revision.periodos_disponiveis]
    return AnaliseManifestoResposta(
        companhia=_companhia_resumo(companhia),
        contexto_padrao=AnaliseContextoPadrao(
            periodo_id=revision.default_period_id,
            periodicidade="annual",
            escopo=scope,
        ),
        periodos_disponiveis=periodos,
        qualidade=AnaliseQualidadeResumo.model_validate(revision.qualidade),
        calculation_version=CALCULATION_VERSION,
        resolution=_canonical_resolution(execucao, as_of),
        links=_links_analise(companhia),
    )


def _obter_series_runtime(
    db: Session,
    companhia: Companhia,
    *,
    metricas: list[str] | None,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
    horizonte_anos: int | None = None,
) -> AnaliseSeriesResposta:
    context = _load_context(db, companhia, scope, as_of)
    metric_ids = _filter_metric_ids(metricas)
    facts, unavailable, issues = _resolve_series_facts(context, metric_ids, periodicidade, base_periodo, scope, horizonte_anos)
    return AnaliseSeriesResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        escopo=scope,
        horizonte_anos=horizonte_anos if periodicidade == "annual" and base_periodo == "fy" else None,
        metricas=metric_ids,
        resolution=_runtime_resolution(as_of),
        observacoes=[_observation_from_fact(fact) for fact in facts],
        indisponibilidades=unavailable,
        issues=issues,
    )


def obter_series(
    db: Session,
    companhia: Companhia,
    *,
    metricas: list[str] | None,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
    horizonte_anos: int | None = None,
) -> AnaliseSeriesResposta:
    canonical = _series_from_canonical(
        db,
        companhia,
        metricas=metricas,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=scope,
        as_of=as_of,
    )
    if canonical is not None:
        if periodicidade == "annual" and base_periodo == "fy" and horizonte_anos is not None and horizonte_anos > 0:
            allowed_period_ids = {
                obs.period_id
                for obs in sorted(canonical.observacoes, key=lambda item: item.fiscal_year)[-horizonte_anos:]
            }
            canonical.observacoes = [obs for obs in canonical.observacoes if obs.period_id in allowed_period_ids]
            canonical.indisponibilidades = [item for item in canonical.indisponibilidades if item.period_id in allowed_period_ids]
            canonical.horizonte_anos = horizonte_anos
        return canonical
    return _obter_series_runtime(
        db,
        companhia,
        metricas=metricas,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=scope,
        as_of=as_of,
        horizonte_anos=horizonte_anos,
    )


def _fact_map(series: AnaliseSeriesResposta) -> dict[tuple[str, str], AnaliseSeriesObservation]:
    return {(obs.metric_id, obs.period_id): obs for obs in series.observacoes}


def _comparison_unavailable(
    metric_id: str,
    period_id: str,
    kind: AnaliseComparisonKind,
    metric_unit: AnaliseUnit,
    comparison_unit: AnaliseComparisonUnit | None,
    reason: str,
    note: str,
) -> AnaliseComparacaoItem:
    return AnaliseComparacaoItem(
        metric_id=metric_id,
        period_id=period_id,
        comparison_kind=kind,
        status="unavailable",
        reason_code=reason,
        current_value=None,
        comparable_period_id=None,
        comparable_metric_id=None,
        comparable_value=None,
        absolute_change=None,
        relative_change=None,
        percentage_point_change=None,
        base100_value=None,
        metric_unit=metric_unit,
        comparison_unit=comparison_unit,
        evidence=[AnaliseEvidenceItem(note=note)],
    )


def _build_comparison_item(
    current: AnaliseSeriesObservation,
    comparable: AnaliseSeriesObservation | None,
    kind: AnaliseComparisonKind,
    spec: MetricSpec,
) -> AnaliseComparacaoItem:
    current_value = current.value
    if comparable is None:
        return _comparison_unavailable(
            current.metric_id,
            current.period_id,
            kind,
            current.unit,
            "ratio" if kind in {"YoY", "QoQ", "CAGR", "VERTICAL"} else None,
            "MISSING_COMPARABLE_PERIOD",
            "O período comparável não está disponível na série resolvida.",
        )

    absolute_change = current_value - comparable.value
    relative_change = _safe_div(absolute_change, abs(comparable.value))
    percentage_point_change = None
    if spec.metric_type == "ratio":
        percentage_point_change = absolute_change * Decimal("100")

    return AnaliseComparacaoItem(
        metric_id=current.metric_id,
        period_id=current.period_id,
        comparison_kind=kind,
        status="available",
        reason_code=None,
        current_value=current_value,
        comparable_period_id=comparable.period_id,
        comparable_metric_id=None,
        comparable_value=comparable.value,
        absolute_change=absolute_change,
        relative_change=relative_change,
        percentage_point_change=percentage_point_change,
        base100_value=None,
        metric_unit=current.unit,
        comparison_unit="percentage_point" if spec.metric_type == "ratio" and percentage_point_change is not None else "ratio",
        evidence=[
            AnaliseEvidenceItem(metric_id=current.metric_id, period_id=current.period_id, value=current_value, unit=current.unit, note="Valor atual."),
            AnaliseEvidenceItem(metric_id=comparable.metric_id, period_id=comparable.period_id, value=comparable.value, unit=comparable.unit, note="Valor comparável."),
        ],
    )


def obter_comparacoes(
    db: Session,
    companhia: Companhia,
    *,
    metricas: list[str] | None,
    periodicidade: AnalisePeriodicidade,
    base_periodo: AnaliseBasePeriodo,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
    horizonte_anos: int | None = None,
) -> AnaliseComparacoesResposta:
    series = obter_series(
        db,
        companhia,
        metricas=metricas,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=scope,
        as_of=as_of,
        horizonte_anos=horizonte_anos,
    )
    fact_map = _fact_map(series)
    items: list[AnaliseComparacaoItem] = []

    for obs in series.observacoes:
        spec = METRIC_SPECS[obs.metric_id]
        yoy = fact_map.get((obs.metric_id, obs.comparables.yoy_period_id)) if obs.comparables.yoy_period_id else None
        items.append(_build_comparison_item(obs, yoy, "YoY", spec))

        if periodicidade == "quarterly" and base_periodo == "quarter":
            qoq = fact_map.get((obs.metric_id, obs.comparables.qoq_period_id)) if obs.comparables.qoq_period_id else None
            items.append(_build_comparison_item(obs, qoq, "QoQ", spec))
        elif periodicidade == "quarterly" and base_periodo == "ytd" and spec.metric_type == "flow":
            items.append(
                _comparison_unavailable(
                    obs.metric_id,
                    obs.period_id,
                    "QoQ",
                    obs.unit,
                    None,
                    "QOQ_NOT_SUPPORTED_FOR_YTD_FLOW",
                    "QoQ não é calculado sobre acumulados YTD de métricas de fluxo.",
                )
            )

        denominator_id = spec.vertical_denominator_metric_id
        if denominator_id and denominator_id != obs.metric_id:
            denominator = fact_map.get((denominator_id, obs.period_id))
            if denominator is None:
                items.append(
                    _comparison_unavailable(
                        obs.metric_id,
                        obs.period_id,
                        "VERTICAL",
                        obs.unit,
                        None,
                        "MISSING_VERTICAL_DENOMINATOR",
                        "Faltou a métrica denominadora para análise vertical.",
                    )
                )
            else:
                vertical_value = _safe_div(obs.value, denominator.value)
                if vertical_value is not None:
                    items.append(
                        AnaliseComparacaoItem(
                            metric_id=obs.metric_id,
                            period_id=obs.period_id,
                            comparison_kind="VERTICAL",
                            status="available",
                            reason_code=None,
                            current_value=obs.value,
                            comparable_period_id=obs.period_id,
                            comparable_metric_id=denominator_id,
                            comparable_value=denominator.value,
                            absolute_change=None,
                            relative_change=vertical_value,
                            percentage_point_change=(vertical_value * Decimal("100")) if spec.metric_type == "ratio" else None,
                            base100_value=None,
                            metric_unit=obs.unit,
                            comparison_unit="percentage_point" if spec.metric_type == "ratio" else "ratio",
                            evidence=[
                                AnaliseEvidenceItem(metric_id=obs.metric_id, period_id=obs.period_id, value=obs.value, unit=obs.unit, note="Numerador da análise vertical."),
                                AnaliseEvidenceItem(metric_id=denominator_id, period_id=obs.period_id, value=denominator.value, unit=denominator.unit, note="Denominador da análise vertical."),
                            ],
                        )
                    )

        metric_periods = [candidate for candidate in series.observacoes if candidate.metric_id == obs.metric_id]
        metric_periods.sort(key=lambda candidate: (candidate.fiscal_year, candidate.quarter or 0))
        base_obs = metric_periods[0] if metric_periods else None
        if base_obs is not None:
            index_value = _safe_div(obs.value, base_obs.value)
            if index_value is not None:
                items.append(
                    AnaliseComparacaoItem(
                        metric_id=obs.metric_id,
                        period_id=obs.period_id,
                        comparison_kind="BASE100",
                        status="available",
                        reason_code=None,
                        current_value=obs.value,
                        comparable_period_id=base_obs.period_id,
                        comparable_metric_id=None,
                        comparable_value=base_obs.value,
                        absolute_change=obs.value - base_obs.value,
                        relative_change=_safe_div(obs.value - base_obs.value, abs(base_obs.value)),
                        percentage_point_change=((obs.value - base_obs.value) * Decimal("100")) if spec.metric_type == "ratio" else None,
                        base100_value=index_value * Decimal("100"),
                        metric_unit=obs.unit,
                        comparison_unit="index",
                        evidence=[
                            AnaliseEvidenceItem(metric_id=obs.metric_id, period_id=base_obs.period_id, value=base_obs.value, unit=base_obs.unit, note="Base do índice 100."),
                        ],
                    )
                )

        if periodicidade == "annual":
            annuals = [candidate for candidate in series.observacoes if candidate.metric_id == obs.metric_id and candidate.period_id.startswith("FY")]
            annuals.sort(key=lambda candidate: candidate.fiscal_year)
            oldest = next((candidate for candidate in annuals if candidate.fiscal_year < obs.fiscal_year), None)
            if oldest is None:
                items.append(
                    _comparison_unavailable(
                            obs.metric_id,
                            obs.period_id,
                            "CAGR",
                            obs.unit,
                            None,
                            "INSUFFICIENT_HISTORY_FOR_CAGR",
                            "É necessário pelo menos um período anual anterior para calcular CAGR.",
                        )
                )
            else:
                years = obs.fiscal_year - oldest.fiscal_year
                if years > 0 and oldest.value > 0 and obs.value > 0:
                    cagr = (obs.value / oldest.value) ** (Decimal("1") / Decimal(years)) - Decimal("1")
                    items.append(
                        AnaliseComparacaoItem(
                            metric_id=obs.metric_id,
                            period_id=obs.period_id,
                            comparison_kind="CAGR",
                            status="available",
                            reason_code=None,
                            current_value=obs.value,
                            comparable_period_id=oldest.period_id,
                            comparable_metric_id=None,
                            comparable_value=oldest.value,
                            absolute_change=obs.value - oldest.value,
                            relative_change=cagr,
                            percentage_point_change=cagr * Decimal("100") if spec.metric_type == "ratio" else None,
                            base100_value=None,
                            metric_unit=obs.unit,
                            comparison_unit="percentage_point" if spec.metric_type == "ratio" else "ratio",
                            evidence=[
                                AnaliseEvidenceItem(metric_id=obs.metric_id, period_id=oldest.period_id, value=oldest.value, unit=oldest.unit, note="Período base do CAGR."),
                            ],
                        )
                    )
                else:
                    items.append(
                        _comparison_unavailable(
                            obs.metric_id,
                            obs.period_id,
                            "CAGR",
                            obs.unit,
                            None,
                            "INVALID_VALUES_FOR_CAGR",
                            "CAGR exige valores positivos e histórico anual comparável.",
                        )
                    )

    return AnaliseComparacoesResposta(
        companhia=series.companhia,
        calculation_version=CALCULATION_VERSION,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        escopo=scope,
        horizonte_anos=series.horizonte_anos,
        metricas=series.metricas,
        resolution=series.resolution,
        comparacoes=items,
        issues=series.issues,
    )


def _obter_qualidade_runtime(
    db: Session,
    companhia: Companhia,
    *,
    periodicidade: AnalisePeriodicidade,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseQualidadeResposta:
    context = _load_context(db, companhia, scope, as_of)
    return AnaliseQualidadeResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        periodicidade=periodicidade,
        escopo=scope,
        resolution=_runtime_resolution(as_of),
        qualidade=context.qualidade,
    )


def obter_qualidade(
    db: Session,
    companhia: Companhia,
    *,
    periodicidade: AnalisePeriodicidade,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseQualidadeResposta:
    context_pair = _context_revision_for_as_of(db, companhia, scope, as_of)
    if context_pair is None:
        return _obter_qualidade_runtime(db, companhia, periodicidade=periodicidade, scope=scope, as_of=as_of)
    execucao, revision = context_pair
    return AnaliseQualidadeResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        periodicidade=periodicidade,
        escopo=scope,
        resolution=_canonical_resolution(execucao, as_of),
        qualidade=AnaliseQualidadeResumo.model_validate(revision.qualidade),
    )


def _series_value(series: AnaliseSeriesResposta, metric_id: str, period_id: str) -> Decimal | None:
    for obs in series.observacoes:
        if obs.metric_id == metric_id and obs.period_id == period_id:
            return obs.value
    return None


def _latest_period_id(series: AnaliseSeriesResposta) -> str | None:
    if not series.observacoes:
        return None
    ordered = sorted(series.observacoes, key=lambda obs: (obs.fiscal_year, obs.quarter or 0))
    return ordered[-1].period_id


def _remuneracao_yoy(db: Session, companhia: Companhia) -> tuple[int | None, Decimal | None]:
    rows = db.execute(
        select(
            FreRemuneracaoTotalOrgao.ano_origem,
            func.sum(FreRemuneracaoTotalOrgao.total_remuneracao_orgao),
        )
        .where(FreRemuneracaoTotalOrgao.cnpj_companhia == companhia.cnpj_companhia)
        .group_by(FreRemuneracaoTotalOrgao.ano_origem)
        .order_by(FreRemuneracaoTotalOrgao.ano_origem)
    ).all()
    if len(rows) < 2:
        return None, None
    current_year, current_total = rows[-1]
    _, previous_total = rows[-2]
    if current_year is None or current_total is None or previous_total in (None, 0):
        return None, None
    return int(current_year), (Decimal(current_total) - Decimal(previous_total)) / abs(Decimal(previous_total))


def obter_sinais(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseSinaisResposta:
    annual = obter_series(db, companhia, metricas=["receita_liquida", "lucro_liquido", "caixa_operacional", "margem_liquida", "liquidez_corrente"], periodicidade="annual", base_periodo="fy", scope=scope, as_of=as_of)
    quarterly = obter_series(db, companhia, metricas=["margem_liquida"], periodicidade="quarterly", base_periodo="quarter", scope=scope, as_of=as_of)
    restatements = obter_restatements(db, companhia, scope=scope, as_of=as_of)

    signals: list[AnaliseSignal] = []

    latest_quarter_id = _latest_period_id(quarterly)
    if latest_quarter_id:
        current_margin = _series_value(quarterly, "margem_liquida", latest_quarter_id)
        obs = next((item for item in quarterly.observacoes if item.metric_id == "margem_liquida" and item.period_id == latest_quarter_id), None)
        if current_margin is not None and obs and obs.comparables.yoy_period_id:
            prior_margin = _series_value(quarterly, "margem_liquida", obs.comparables.yoy_period_id)
            if prior_margin is not None:
                delta_pp = (current_margin - prior_margin) * Decimal("100")
                if delta_pp <= Decimal("-2"):
                    signals.append(
                        AnaliseSignal(
                            rule_id="FIN_MARGIN_COMPRESSION",
                            rule_version="1.2",
                            severity="watch",
                            period_id=latest_quarter_id,
                            title="Compressão de margem líquida",
                            explanation=f"Redução de {delta_pp} pontos percentuais contra o período comparável.",
                            threshold=Decimal("2"),
                            observed=delta_pp,
                            unit="percentage_point",
                            evidence=[
                                AnaliseEvidenceItem(metric_id="margem_liquida", period_id=latest_quarter_id, value=current_margin, unit="ratio", note="Margem líquida atual."),
                                AnaliseEvidenceItem(metric_id="margem_liquida", period_id=obs.comparables.yoy_period_id, value=prior_margin, unit="ratio", note="Margem líquida comparável."),
                            ],
                        )
                    )

    latest_annual_id = _latest_period_id(annual)
    if latest_annual_id:
        lucro = _series_value(annual, "lucro_liquido", latest_annual_id)
        caixa = _series_value(annual, "caixa_operacional", latest_annual_id)
        if lucro is not None and caixa is not None and lucro > 0 > caixa:
            signals.append(
                AnaliseSignal(
                    rule_id="FIN_PROFIT_CASH_DIVERGENCE",
                    rule_version="1.0",
                    severity="warning",
                    period_id=latest_annual_id,
                    title="Lucro positivo com caixa operacional negativo",
                    explanation="O lucro líquido reportado é positivo enquanto o caixa operacional do período é negativo.",
                    threshold=Decimal("0"),
                    observed=caixa,
                    unit="BRL",
                    evidence=[
                        AnaliseEvidenceItem(metric_id="lucro_liquido", period_id=latest_annual_id, value=lucro, unit="BRL", note="Lucro líquido do período."),
                        AnaliseEvidenceItem(metric_id="caixa_operacional", period_id=latest_annual_id, value=caixa, unit="BRL", note="Caixa operacional do período."),
                    ],
                )
            )
        liquidez = _series_value(annual, "liquidez_corrente", latest_annual_id)
        if liquidez is not None and liquidez < Decimal("1"):
            signals.append(
                AnaliseSignal(
                    rule_id="FIN_LOW_CURRENT_RATIO",
                    rule_version="1.0",
                    severity="warning",
                    period_id=latest_annual_id,
                    title="Liquidez corrente inferior a 1,0",
                    explanation="O ativo circulante é inferior ao passivo circulante no período mais recente.",
                    threshold=Decimal("1"),
                    observed=liquidez,
                    unit="ratio",
                    evidence=[AnaliseEvidenceItem(metric_id="liquidez_corrente", period_id=latest_annual_id, value=liquidez, unit="ratio", note="Liquidez corrente calculada.")],
                )
            )

    if restatements.restatements:
        latest = sorted(restatements.restatements, key=lambda item: (item.restated_at or date.min, item.current_version), reverse=True)[0]
        signals.append(
            AnaliseSignal(
                rule_id="FIN_RESTATEMENT",
                rule_version="1.0",
                severity="watch",
                period_id=latest.period_id,
                title="Reapresentação detectada",
                explanation=f"O formulário {latest.form} do período {latest.period_id} foi reapresentado para a versão {latest.current_version}.",
                threshold=None,
                observed=Decimal(len(latest.changed_accounts)),
                unit="count",
                evidence=[AnaliseEvidenceItem(period_id=latest.period_id, value=Decimal(len(latest.changed_accounts)), unit="count", note="Quantidade de contas alteradas entre versões consecutivas.")],
            )
        )

    year, remun_yoy = _remuneracao_yoy(db, companhia)
    if year and remun_yoy is not None and remun_yoy >= Decimal("0.5"):
        signals.append(
            AnaliseSignal(
                rule_id="REMUNERATION_GROWTH_ABNORMAL",
                rule_version="1.0",
                severity="watch",
                period_id=f"FY{year}",
                title="Crescimento anormal de remuneração",
                explanation="A remuneração agregada dos órgãos cresceu mais de 50% contra o exercício anterior.",
                threshold=Decimal("0.5"),
                observed=remun_yoy,
                unit="ratio",
                evidence=[AnaliseEvidenceItem(period_id=f"FY{year}", value=remun_yoy, unit="ratio", note="Variação anual da remuneração agregada.")],
            )
        )

    return AnaliseSinaisResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        resolution=annual.resolution if annual.resolution.mode == quarterly.resolution.mode else _runtime_resolution(as_of),
        sinais=signals,
        issues=_dedupe_issues([*annual.issues, *quarterly.issues, *restatements.issues]),
    )


def obter_eventos(db: Session, companhia: Companhia) -> AnaliseEventosResposta:
    events: list[AnaliseEvento] = []

    ipe_docs = db.scalars(
        select(IpeDocumento)
        .where(IpeDocumento.cnpj_companhia == companhia.cnpj_companhia)
        .order_by(desc(IpeDocumento.data_entrega))
        .limit(100)
    ).all()
    for ipe_doc in ipe_docs:
        occurred_at = ipe_doc.data_entrega or ipe_doc.data_referencia
        if occurred_at is None:
            continue
        period_id = None
        if ipe_doc.data_referencia:
            quarter = _quarter_from_date(ipe_doc.data_referencia)
            period_id = f"{ipe_doc.data_referencia.year}-Q{quarter}"
        events.append(
            AnaliseEvento(
                event_id=_stable_event_id("IPE", ipe_doc.id, ipe_doc.id_documento if hasattr(ipe_doc, "id_documento") else None, occurred_at, ipe_doc.assunto, ipe_doc.tipo),
                occurred_at=occurred_at,
                family="IPE",
                event_type=ipe_doc.categoria or ipe_doc.tipo or "Documento IPE",
                severity="warning" if ipe_doc.categoria in {"Fato Relevante", "Aviso aos Acionistas"} else "info",
                title=ipe_doc.assunto or ipe_doc.tipo or "Documento IPE",
                explanation=f"Documento IPE classificado como {ipe_doc.categoria or ipe_doc.tipo}.",
                period_id=period_id,
                link_documento=ipe_doc.link_download,
            )
        )

    financeiro_docs = db.scalars(
        select(DocumentoFinanceiro)
        .where(DocumentoFinanceiro.cnpj_companhia == companhia.cnpj_companhia, DocumentoFinanceiro.versao > 1)
        .order_by(desc(DocumentoFinanceiro.data_recebimento))
        .limit(50)
    ).all()
    for fin_doc in financeiro_docs:
        events.append(
            AnaliseEvento(
                event_id=_stable_event_id("FINANCEIRO", fin_doc.tipo_formulario, fin_doc.id_documento, fin_doc.data_referencia, fin_doc.versao),
                occurred_at=fin_doc.data_recebimento or fin_doc.data_referencia,
                family="FINANCEIRO",
                event_type="Reapresentação",
                severity="warning",
                title=f"Reapresentação de {fin_doc.tipo_formulario}",
                explanation=f"Versão {fin_doc.versao} do formulário {fin_doc.tipo_formulario} referente a {fin_doc.data_referencia.isoformat()}.",
                period_id=(
                    f"FY{fin_doc.data_referencia.year}"
                    if fin_doc.tipo_formulario == "DFP"
                    else f"{fin_doc.data_referencia.year}-Q{_quarter_from_date(fin_doc.data_referencia)}"
                ),
                link_documento=fin_doc.link_documento,
            )
        )

    aumentos = db.scalars(
        select(FreCapitalSocialAumento)
        .where(FreCapitalSocialAumento.cnpj_companhia == companhia.cnpj_companhia)
        .order_by(desc(FreCapitalSocialAumento.data_deliberacao))
        .limit(50)
    ).all()
    for aumento in aumentos:
        occurred_at = aumento.data_deliberacao or aumento.data_referencia
        if occurred_at is None:
            continue
        events.append(
            AnaliseEvento(
                event_id=_stable_event_id("FRE", "capital", aumento.id_documento, aumento.data_deliberacao, aumento.origem_aumento, aumento.linha_origem),
                occurred_at=occurred_at,
                family="FRE",
                event_type="Capital",
                severity="info",
                title="Alteração de capital social",
                explanation=f"Aumento deliberado com origem `{aumento.origem_aumento or 'não informada'}`.",
                period_id=f"FY{aumento.ano_origem}" if aumento.ano_origem else None,
                link_documento=None,
            )
        )

    trades = db.scalars(
        select(VlmoConsolidado)
        .where(VlmoConsolidado.cnpj_companhia == companhia.cnpj_companhia, VlmoConsolidado.volume > 100000)
        .order_by(desc(VlmoConsolidado.data_movimentacao))
        .limit(100)
    ).all()
    for trade in trades:
        occurred_at = trade.data_movimentacao or trade.data_referencia
        if occurred_at is None:
            continue
        quarter = _quarter_from_date(trade.data_referencia)
        events.append(
            AnaliseEvento(
                event_id=_stable_event_id("VLMO", trade.id, trade.data_movimentacao, trade.indice_ocorrencia, trade.tipo_operacao, trade.volume),
                occurred_at=occurred_at,
                family="VLMO",
                event_type="Negociação relevante",
                severity="info",
                title=f"{trade.tipo_operacao} relevante por insiders",
                explanation=f"{trade.tipo_cargo or 'Insider'} realizou {trade.tipo_operacao} com volume superior a R$ 100 mil.",
                period_id=f"{trade.data_referencia.year}-Q{quarter}",
                link_documento=None,
            )
        )

    events.sort(key=lambda item: item.occurred_at, reverse=True)
    return AnaliseEventosResposta(companhia=_companhia_resumo(companhia), eventos=events)


def _latest_rows_by_year(items: Sequence[Any], year_getter: Any, version_getter: Any, as_of_getter: Any) -> list[Any]:
    by_year: dict[int, Any] = {}
    for item in items:
        year = year_getter(item)
        existing = by_year.get(year)
        if existing is None:
            by_year[year] = item
            continue
        existing_sort = (version_getter(existing), as_of_getter(existing))
        current_sort = (version_getter(item), as_of_getter(item))
        if current_sort > existing_sort:
            by_year[year] = item
    return [by_year[year] for year in sorted(by_year)]


def obter_governanca(
    db: Session,
    companhia: Companhia,
    *,
    as_of: date | None = None,
    horizonte_anos: int = 5,
    scope: AnaliseEscopo = "consolidated",
) -> AnaliseGovernancaResposta:
    docs_stmt = select(CgvnDocumento).where(CgvnDocumento.cnpj_companhia == companhia.cnpj_companhia)
    if as_of is not None:
        docs_stmt = docs_stmt.where(CgvnDocumento.data_entrega <= as_of)
    docs = db.scalars(docs_stmt.order_by(CgvnDocumento.data_referencia, CgvnDocumento.versao)).all()
    latest_docs = _latest_rows_by_year(docs, lambda item: item.data_referencia.year, lambda item: item.versao, lambda item: item.data_entrega)
    latest_docs = latest_docs[-horizonte_anos:]
    observations: list[AnaliseTemporalObservation] = []
    issues: list[AnaliseIssue] = []

    for doc in latest_docs:
        praticas = db.scalars(
            select(CgvnPratica).where(
                CgvnPratica.cnpj_companhia == companhia.cnpj_companhia,
                CgvnPratica.data_referencia == doc.data_referencia,
                CgvnPratica.versao == doc.versao,
            )
        ).all()
        total = len(praticas)
        adotadas = sum(1 for item in praticas if (item.pratica_adotada or "").strip().upper() in {"SIM", "S", "ADOTADA"})
        explicadas = sum(1 for item in praticas if item.explicacao)
        period_id = f"FY{doc.data_referencia.year}"
        if total == 0:
            issues.append(
                AnaliseIssue(code="MISSING_CGVN_PRACTICES", severity="warning", message=f"Não há práticas CGVN materializáveis para {period_id}.", affected_period_ids=[period_id])
            )
            continue
        observations.append(
            AnaliseTemporalObservation(
                metric_id="governanca_praticas_adotadas_ratio",
                period_id=period_id,
                fiscal_year=doc.data_referencia.year,
                start_date=doc.data_inicio_exercicio_social or date(doc.data_referencia.year, 1, 1),
                end_date=doc.data_fim_exercicio_social or doc.data_referencia,
                value=Decimal(adotadas) / Decimal(total),
                unit="ratio",
                source_dataset="cgvn_praticas",
                document_id=doc.id_documento,
                version=doc.versao,
                restated=doc.versao > 1,
                details={"total_praticas": total, "praticas_adotadas": adotadas},
            )
        )
        observations.append(
            AnaliseTemporalObservation(
                metric_id="governanca_praticas_com_explicacao",
                period_id=period_id,
                fiscal_year=doc.data_referencia.year,
                start_date=doc.data_inicio_exercicio_social or date(doc.data_referencia.year, 1, 1),
                end_date=doc.data_fim_exercicio_social or doc.data_referencia,
                value=Decimal(explicadas),
                unit="count",
                source_dataset="cgvn_praticas",
                document_id=doc.id_documento,
                version=doc.versao,
                restated=doc.versao > 1,
                details={"total_praticas": total},
            )
        )

    return AnaliseGovernancaResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        as_of=as_of,
        horizonte_anos=horizonte_anos,
        resolution=_runtime_resolution(as_of),
        observacoes=observations,
        issues=_dedupe_issues(issues),
    )


def obter_pessoas(
    db: Session,
    companhia: Companhia,
    *,
    as_of: date | None = None,
    horizonte_anos: int = 5,
    scope: AnaliseEscopo = "consolidated",
) -> AnalisePessoasResposta:
    remuneracoes_stmt = select(FreRemuneracaoTotalOrgao).where(FreRemuneracaoTotalOrgao.cnpj_companhia == companhia.cnpj_companhia)
    if as_of is not None:
        remuneracoes_stmt = remuneracoes_stmt.where(FreRemuneracaoTotalOrgao.data_referencia <= as_of)
    remuneracoes = db.scalars(remuneracoes_stmt.order_by(FreRemuneracaoTotalOrgao.data_referencia, FreRemuneracaoTotalOrgao.versao)).all()
    empregados_stmt = select(FreEmpregadoPosicaoGenero).where(FreEmpregadoPosicaoGenero.cnpj_companhia == companhia.cnpj_companhia)
    if as_of is not None:
        empregados_stmt = empregados_stmt.where(FreEmpregadoPosicaoGenero.data_referencia <= as_of)
    empregados = db.scalars(empregados_stmt.order_by(FreEmpregadoPosicaoGenero.data_referencia, FreEmpregadoPosicaoGenero.versao)).all()

    latest_remuneracoes = _latest_rows_by_year(remuneracoes, lambda item: item.data_referencia.year, lambda item: item.versao, lambda item: item.data_referencia)[-horizonte_anos:]
    latest_empregados = _latest_rows_by_year(empregados, lambda item: item.data_referencia.year, lambda item: item.versao, lambda item: item.data_referencia)[-horizonte_anos:]

    observations: list[AnaliseTemporalObservation] = []
    for item in latest_remuneracoes:
        value = item.total_remuneracao or item.total_remuneracao_orgao
        if value is None:
            continue
        observations.append(
            AnaliseTemporalObservation(
                metric_id="pessoas_remuneracao_total_orgao",
                period_id=f"FY{item.data_referencia.year}",
                fiscal_year=item.data_referencia.year,
                start_date=item.data_inicio_exercicio_social or date(item.data_referencia.year, 1, 1),
                end_date=item.data_fim_exercicio_social or item.data_referencia,
                value=value,
                unit="BRL",
                source_dataset="fre_remuneracao_total_orgao",
                document_id=item.id_documento,
                version=item.versao,
                restated=item.versao > 1,
                details={"orgao_administracao": item.orgao_administracao, "numero_membros": item.numero_membros},
            )
        )
    for item in latest_empregados:
        total = sum(
            valor or 0
            for valor in (
                item.quantidade_feminino,
                item.quantidade_masculino,
                item.quantidade_nao_binario,
                item.quantidade_outros,
                item.quantidade_sem_resposta,
            )
        )
        observations.append(
            AnaliseTemporalObservation(
                metric_id="pessoas_empregados_total",
                period_id=f"FY{item.data_referencia.year}",
                fiscal_year=item.data_referencia.year,
                start_date=date(item.data_referencia.year, 1, 1),
                end_date=item.data_referencia,
                value=Decimal(total),
                unit="count",
                source_dataset="fre_empregado_posicao_genero",
                document_id=item.id_documento,
                version=item.versao,
                restated=item.versao > 1,
                details={"posicao": item.posicao, "feminino": item.quantidade_feminino, "masculino": item.quantidade_masculino},
            )
        )

    observations.sort(key=lambda item: (item.fiscal_year, item.metric_id, str(item.details)))
    return AnalisePessoasResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        as_of=as_of,
        horizonte_anos=horizonte_anos,
        resolution=_runtime_resolution(as_of),
        observacoes=observations,
        issues=[],
    )


def obter_brief(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
    metricas: list[str] | None = None,
    incluir_eventos: bool = True,
) -> AnaliseBriefResposta:
    quarterly = obter_series(db, companhia, metricas=metricas, periodicidade="quarterly", base_periodo="quarter", scope=scope, as_of=as_of)
    annual = obter_series(db, companhia, metricas=metricas, periodicidade="annual", base_periodo="fy", scope=scope, as_of=as_of, horizonte_anos=2)
    quarterly_comparacoes = obter_comparacoes(db, companhia, metricas=metricas, periodicidade="quarterly", base_periodo="quarter", scope=scope, as_of=as_of)
    annual_comparacoes = obter_comparacoes(db, companhia, metricas=metricas, periodicidade="annual", base_periodo="fy", scope=scope, as_of=as_of, horizonte_anos=2)
    sinais = obter_sinais(db, companhia, scope=scope, as_of=as_of)
    qualidade = obter_qualidade(db, companhia, periodicidade="annual", scope=scope, as_of=as_of)
    eventos = obter_eventos(db, companhia).eventos if incluir_eventos else []

    q_periods = sorted({(obs.fiscal_year, obs.quarter, obs.period_id) for obs in quarterly.observacoes if obs.quarter is not None})
    fy_periods = sorted({(obs.fiscal_year, obs.period_id) for obs in annual.observacoes})
    quarter_current = q_periods[-1][2] if q_periods else None
    quarter_previous = q_periods[-2][2] if len(q_periods) > 1 else None
    quarter_yoy = None
    if q_periods:
        year, quarter, _ = q_periods[-1]
        quarter_yoy = f"{year - 1}-Q{quarter}"
    fy_current = fy_periods[-1][1] if fy_periods else None
    fy_previous = fy_periods[-2][1] if len(fy_periods) > 1 else None

    relevant_periods = {item for item in {quarter_current, quarter_previous, quarter_yoy, fy_current, fy_previous} if item is not None}
    metric_obs = [obs for obs in [*quarterly.observacoes, *annual.observacoes] if obs.period_id in relevant_periods]
    comparacoes = [
        item
        for item in [*quarterly_comparacoes.comparacoes, *annual_comparacoes.comparacoes]
        if item.period_id in relevant_periods
    ]

    return AnaliseBriefResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        as_of=as_of,
        escopo=scope,
        periodos_referencia=AnaliseBriefReferencias(
            quarter_current=quarter_current,
            quarter_previous=quarter_previous,
            quarter_yoy=quarter_yoy,
            fy_current=fy_current,
            fy_previous=fy_previous,
        ),
        metricas=metric_obs,
        comparacoes=comparacoes,
        sinais=sinais.sinais,
        qualidade=qualidade.qualidade,
        eventos=eventos[:10],
        issues=_dedupe_issues([*quarterly.issues, *annual.issues, *quarterly_comparacoes.issues, *annual_comparacoes.issues, *sinais.issues]),
    )


def obter_restatements(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    as_of: date | None = None,
) -> AnaliseRestatementsResposta:
    docs_stmt = select(DocumentoFinanceiro).where(DocumentoFinanceiro.cnpj_companhia == companhia.cnpj_companhia)
    if as_of is not None:
        docs_stmt = docs_stmt.where(_document_known_on_or_before(as_of))
    documents = db.scalars(
        docs_stmt.order_by(DocumentoFinanceiro.tipo_formulario, DocumentoFinanceiro.data_referencia, DocumentoFinanceiro.versao)
    ).all()
    by_key: dict[tuple[str, date], list[DocumentoFinanceiro]] = defaultdict(list)
    for doc in documents:
        by_key[(doc.tipo_formulario, doc.data_referencia)].append(doc)

    items: list[AnaliseRestatementItem] = []
    issues: list[AnaliseIssue] = []

    for (form, data_referencia), versions in sorted(by_key.items()):
        versions.sort(key=lambda item: item.versao)
        if len(versions) < 2:
            continue
        for previous_doc, current_doc in zip(versions, versions[1:], strict=False):
            previous_rows = db.scalars(
                select(DemonstracaoFinanceira).where(
                    DemonstracaoFinanceira.cnpj_companhia == companhia.cnpj_companhia,
                    DemonstracaoFinanceira.tipo_formulario == form,
                    DemonstracaoFinanceira.data_referencia == data_referencia,
                    DemonstracaoFinanceira.versao == previous_doc.versao,
                    DemonstracaoFinanceira.escopo_demonstracao == API_SCOPE_TO_DB[scope],
                )
            ).all()
            current_rows = db.scalars(
                select(DemonstracaoFinanceira).where(
                    DemonstracaoFinanceira.cnpj_companhia == companhia.cnpj_companhia,
                    DemonstracaoFinanceira.tipo_formulario == form,
                    DemonstracaoFinanceira.data_referencia == data_referencia,
                    DemonstracaoFinanceira.versao == current_doc.versao,
                    DemonstracaoFinanceira.escopo_demonstracao == API_SCOPE_TO_DB[scope],
                )
            ).all()

            def key_fn(row: DemonstracaoFinanceira) -> tuple[str | None, str | None, str | None, date | None, date | None, str | None, str]:
                return (
                    row.tipo_demonstracao,
                    row.grupo_demonstracao,
                    row.ordem_exercicio,
                    row.data_inicio_exercicio,
                    row.data_fim_exercicio,
                    row.codigo_conta,
                    row.coluna_df,
                )
            previous_map = {key_fn(row): row for row in previous_rows}
            current_map = {key_fn(row): row for row in current_rows}
            changed_accounts: list[AnaliseRestatementContaAlterada] = []
            for natural_key in sorted(set(previous_map) | set(current_map)):
                before = previous_map.get(natural_key)
                after = current_map.get(natural_key)
                before_value = _row_value(before) if before else None
                after_value = _row_value(after) if after else None
                if before_value == after_value:
                    continue
                absolute_change = None
                relative_change = None
                if before_value is not None and after_value is not None:
                    absolute_change = after_value - before_value
                    relative_change = _safe_div(absolute_change, abs(before_value)) if before_value != 0 else None
                reference_row = after or before
                if reference_row is None:
                    continue
                changed_accounts.append(
                    AnaliseRestatementContaAlterada(
                        account_code=reference_row.codigo_conta or "",
                        statement_type=reference_row.tipo_demonstracao,
                        order=reference_row.ordem_exercicio,
                        start_date=reference_row.data_inicio_exercicio,
                        end_date=reference_row.data_fim_exercicio or reference_row.data_referencia,
                        before_value=before_value,
                        after_value=after_value,
                        absolute_change=absolute_change,
                        relative_change=relative_change,
                    )
                )
            if not changed_accounts:
                issues.append(
                    AnaliseIssue(
                        code="RESTATEMENT_WITHOUT_VALUE_CHANGE",
                        severity="info",
                        message=f"A reapresentação de {form} em {data_referencia.isoformat()} não alterou valores das linhas no escopo selecionado.",
                        affected_period_ids=[],
                    )
                )
                continue
            period_id = f"FY{data_referencia.year}" if form == "DFP" else f"{data_referencia.year}-Q{_quarter_from_date(data_referencia)}"
            items.append(
                AnaliseRestatementItem(
                    form=form,  # type: ignore[arg-type]
                    period_id=period_id,
                    previous_version=previous_doc.versao,
                    current_version=current_doc.versao,
                    restated_at=current_doc.data_recebimento,
                    document_link=current_doc.link_documento,
                    changed_accounts=changed_accounts,
                )
            )

    return AnaliseRestatementsResposta(
        companhia=_companhia_resumo(companhia),
        calculation_version=CALCULATION_VERSION,
        restatements=items,
        issues=_dedupe_issues(issues),
    )


_SERIES_PROFILES: tuple[tuple[AnalisePeriodicidade, AnaliseBasePeriodo], ...] = (
    ("annual", "fy"),
    ("quarterly", "quarter"),
    ("quarterly", "ytd"),
)


def _knowledge_dates_for_materialization(
    db: Session,
    companhia: Companhia,
    *,
    invalidated_from: date | None = None,
) -> list[date]:
    documents = db.scalars(
        select(DocumentoFinanceiro)
        .where(
            DocumentoFinanceiro.cnpj_companhia == companhia.cnpj_companhia,
            DocumentoFinanceiro.tipo_formulario.in_(("DFP", "ITR")),
        )
        .order_by(DocumentoFinanceiro.data_referencia, DocumentoFinanceiro.versao)
    ).all()
    dates = {document.data_recebimento or document.data_referencia for document in documents}
    ordered = sorted(item for item in dates if item is not None)
    if invalidated_from is None:
        return ordered
    return [item for item in ordered if item >= invalidated_from]


def _knowledge_date_bounds_for_execucao(
    *,
    knowledge_dates: list[date],
    invalidated_from: date | None,
) -> tuple[str, date | None]:
    if invalidated_from is None:
        return "full", None
    if not knowledge_dates or invalidated_from <= knowledge_dates[0]:
        return "full", None
    return "incremental", invalidated_from


def _context_snapshot_payload(
    db: Session,
    companhia: Companhia,
    scope: AnaliseEscopo,
    as_of: date,
) -> dict[str, Any]:
    context = _load_context(db, companhia, scope, as_of)
    periodos = [_jsonable_payload(item) for item in context.periodos_disponiveis]
    qualidade = _jsonable_payload(context.qualidade)
    issues = [_jsonable_payload(item) for item in context.issues]
    payload = {
        "default_period_id": _default_period_id(context.periodos_disponiveis),
        "periodos_disponiveis": periodos,
        "qualidade": qualidade,
        "issues": issues,
    }
    payload["fingerprint"] = _payload_fingerprint(payload)
    return payload


def _series_snapshot_payloads(
    db: Session,
    companhia: Companhia,
    scope: AnaliseEscopo,
    as_of: date,
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    snapshots: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for periodicidade, base_periodo in _SERIES_PROFILES:
        response = _obter_series_runtime(
            db,
            companhia,
            metricas=None,
            periodicidade=periodicidade,
            base_periodo=base_periodo,
            scope=scope,
            as_of=as_of,
        )
        for observation in response.observacoes:
            key = (periodicidade, base_periodo, observation.metric_id, observation.period_id)
            payload = _jsonable_payload(observation)
            snapshots[key] = {
                "status": "available",
                "metric_id": observation.metric_id,
                "period_id": observation.period_id,
                "fiscal_year": observation.fiscal_year,
                "quarter": observation.quarter,
                "periodicidade": periodicidade,
                "base_periodo": base_periodo,
                "observation_payload": payload,
                "unavailable_payload": None,
                "fingerprint": _payload_fingerprint(payload),
                "provenance_hash": _payload_fingerprint(payload.get("provenance", [])),
            }
        for unavailable in response.indisponibilidades:
            key = (periodicidade, base_periodo, unavailable.metric_id, unavailable.period_id)
            payload = _jsonable_payload(unavailable)
            period_tokens = unavailable.period_id.replace("FY", "").replace("YTDQ", "-").replace("-Q", "-").split("-")
            snapshots[key] = {
                "status": "unavailable",
                "metric_id": unavailable.metric_id,
                "period_id": unavailable.period_id,
                "fiscal_year": int(period_tokens[0]),
                "quarter": int(period_tokens[-1]) if len(period_tokens) > 1 and period_tokens[-1].isdigit() else None,
                "periodicidade": periodicidade,
                "base_periodo": base_periodo,
                "observation_payload": None,
                "unavailable_payload": payload,
                "fingerprint": _payload_fingerprint(payload),
                "provenance_hash": None,
            }
    return snapshots


def _row_contexto_revision_payload(
    execucao: AnaliseMaterializacaoExecucao,
    companhia: Companhia,
    scope: AnaliseEscopo,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "execucao_id": execucao.id,
        "companhia_id": companhia.id,
        "codigo_cvm": companhia.codigo_cvm,
        "escopo": scope,
        "calculation_version": CALCULATION_VERSION,
        "known_from": payload["known_from"],
        "known_to": payload["known_to"],
        "default_period_id": payload["default_period_id"],
        "periodos_disponiveis": payload["periodos_disponiveis"],
        "qualidade": payload["qualidade"],
        "issues": payload["issues"],
        "fingerprint": payload["fingerprint"],
    }


def _row_fato_revision_payload(
    execucao: AnaliseMaterializacaoExecucao,
    companhia: Companhia,
    scope: AnaliseEscopo,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "execucao_id": execucao.id,
        "companhia_id": companhia.id,
        "codigo_cvm": companhia.codigo_cvm,
        "escopo": scope,
        "calculation_version": CALCULATION_VERSION,
        "periodicidade": payload["periodicidade"],
        "base_periodo": payload["base_periodo"],
        "metric_id": payload["metric_id"],
        "period_id": payload["period_id"],
        "fiscal_year": payload["fiscal_year"],
        "quarter": payload["quarter"],
        "status": payload["status"],
        "known_from": payload["known_from"],
        "known_to": payload["known_to"],
        "observation_payload": payload["observation_payload"],
        "unavailable_payload": payload["unavailable_payload"],
        "fingerprint": payload["fingerprint"],
        "provenance_hash": payload["provenance_hash"],
    }


def _invalidated_from_por_codigo_cvm(
    db: Session,
    *,
    codigos_cvm: Sequence[int],
    source_execucao_id: str | None,
) -> dict[int, date]:
    if not source_execucao_id or not codigos_cvm:
        return {}
    execucao = db.get(ExecucaoSincronizacao, uuid.UUID(source_execucao_id))
    if execucao is None or execucao.ano is None or execucao.tipo_fonte not in {"dfp", "itr"}:
        return {}
    rows = db.execute(
        select(
            DocumentoFinanceiro.codigo_cvm,
            func.min(func.coalesce(DocumentoFinanceiro.data_recebimento, DocumentoFinanceiro.data_referencia)),
        )
        .where(
            DocumentoFinanceiro.codigo_cvm.in_(sorted(set(codigos_cvm))),
            DocumentoFinanceiro.ano_origem == execucao.ano,
            DocumentoFinanceiro.tipo_formulario == execucao.tipo_fonte.upper(),
        )
        .group_by(DocumentoFinanceiro.codigo_cvm)
    ).all()
    return {
        int(codigo_cvm): invalidated_from
        for codigo_cvm, invalidated_from in rows
        if codigo_cvm is not None and invalidated_from is not None
    }


def _recalcular_materializacao_campanha(db: Session, campanha: AnaliseMaterializacaoCampanha) -> AnaliseMaterializacaoCampanha:
    counts = {
        status: count
        for status, count in db.execute(
            select(AnaliseMaterializacaoCampanhaItem.status, func.count(AnaliseMaterializacaoCampanhaItem.id))
            .where(AnaliseMaterializacaoCampanhaItem.campanha_id == campanha.id)
            .group_by(AnaliseMaterializacaoCampanhaItem.status)
        ).all()
    }
    campanha.total_items = sum(int(value) for value in counts.values())
    campanha.pending_items = int(counts.get("pending", 0))
    campanha.running_items = int(counts.get("running", 0))
    campanha.success_items = int(counts.get("success", 0))
    campanha.failed_items = int(counts.get("failed", 0))
    campanha.skipped_items = int(counts.get("skipped", 0))
    chunk_counts = {
        status: count
        for status, count in db.execute(
            select(AnaliseMaterializacaoChunkExecucao.status, func.count(AnaliseMaterializacaoChunkExecucao.id))
            .where(AnaliseMaterializacaoChunkExecucao.campanha_id == campanha.id)
            .group_by(AnaliseMaterializacaoChunkExecucao.status)
        ).all()
    }
    queued_chunks = int(chunk_counts.get("queued", 0))
    active_chunks = queued_chunks + int(chunk_counts.get("running", 0))
    stale_chunks = len(obter_chunks_stale_ativos(db, campanha_id=campanha.id))
    processed_items = campanha.success_items + campanha.failed_items + campanha.skipped_items
    progress_ratio = (processed_items / campanha.total_items) if campanha.total_items > 0 else None
    campanha.summary = {
        **(campanha.summary or {}),
        "counts": {
            "total_items": campanha.total_items,
            "pending_items": campanha.pending_items,
            "running_items": campanha.running_items,
            "success_items": campanha.success_items,
            "failed_items": campanha.failed_items,
            "skipped_items": campanha.skipped_items,
            "processed_items": processed_items,
            "progress_ratio": progress_ratio,
            "queued_chunks": queued_chunks,
            "active_chunks": active_chunks,
            "stale_chunks": stale_chunks,
        },
    }
    if campanha.total_items == 0:
        campanha.status = "success"
        if campanha.started_at is None:
            campanha.started_at = datetime.now(UTC)
        campanha.finished_at = datetime.now(UTC)
    elif active_chunks > 0:
        campanha.status = "running"
        if campanha.started_at is None:
            campanha.started_at = datetime.now(UTC)
        campanha.finished_at = None
    elif campanha.pending_items > 0:
        campanha.status = "pending"
        if campanha.started_at is not None or processed_items > 0:
            campanha.finished_at = None
    elif campanha.failed_items > 0:
        campanha.status = "partial" if (campanha.success_items + campanha.skipped_items) > 0 else "failed"
        campanha.finished_at = datetime.now(UTC)
    else:
        campanha.status = "success"
        campanha.finished_at = datetime.now(UTC)
    campanha.updated_at = datetime.now(UTC)
    db.flush()
    return campanha


def obter_controle_materializacao(db: Session) -> AnaliseMaterializacaoControle:
    controle = db.get(AnaliseMaterializacaoControle, 1)
    if controle is None:
        controle = AnaliseMaterializacaoControle(id=1, mode="auto")
        db.add(controle)
        db.commit()
        db.refresh(controle)
    return controle


def pausar_controle_materializacao(
    db: Session,
    *,
    reason: str | None = None,
) -> AnaliseMaterializacaoControle:
    controle = obter_controle_materializacao(db)
    controle.mode = "paused"
    controle.reason = reason
    controle.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(controle)
    return controle


def retomar_controle_materializacao(db: Session) -> AnaliseMaterializacaoControle:
    controle = obter_controle_materializacao(db)
    controle.mode = "auto"
    controle.reason = None
    controle.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(controle)
    return controle


def _registrar_recovery_state_campanha(
    campanha: AnaliseMaterializacaoCampanha,
    *,
    recovery_state: str,
    reason_code: str,
    action: str,
    checked_at: datetime,
) -> None:
    campanha.summary = {
        **(campanha.summary or {}),
        "recovery_state": recovery_state,
        "last_recovery_check_at": checked_at.isoformat(),
        "last_recovery_action": action,
        "last_recovery_reason_code": reason_code,
    }
    campanha.updated_at = checked_at


def _timestamp_iso_em_summary(summary: dict[str, Any] | None, key: str) -> datetime | None:
    if not isinstance(summary, dict):
        return None
    raw_value = summary.get(key)
    if not isinstance(raw_value, str):
        return None
    try:
        return _coerce_utc_datetime(datetime.fromisoformat(raw_value))
    except ValueError:
        return None


def campanha_tem_requeue_em_transito(
    campanha: AnaliseMaterializacaoCampanha,
    *,
    now: datetime | None = None,
) -> bool:
    summary = campanha.summary if isinstance(campanha.summary, dict) else None
    if not isinstance(summary, dict):
        return False
    if summary.get("recovery_state") != "requeued":
        return False
    action = summary.get("last_recovery_action")
    if action not in {"requeued", "recovered_and_requeued", "worker_recovered_and_requeued"}:
        return False
    checked_at = _timestamp_iso_em_summary(summary, "last_recovery_check_at")
    if checked_at is None:
        return False
    reference_time = now or datetime.now(UTC)
    grace_seconds = max(
        _settings.analise_materializacao_pending_recovery_min_age_seconds,
        _settings.analise_materializacao_recovery_sweep_seconds,
    )
    return (reference_time - checked_at).total_seconds() < grace_seconds


def _persistir_summary_recuperacao_pendente_controle(
    db: Session,
    *,
    summary: dict[str, Any],
    reference_time: datetime,
) -> None:
    controle = obter_controle_materializacao(db)
    controle.summary = {
        **(controle.summary or {}),
        "pending_recovery": {
            **summary,
            "triggered_at": reference_time.isoformat(),
        },
    }
    controle.updated_at = reference_time
    db.commit()


def classificar_recuperacao_materializacao_campanha(
    db: Session,
    campanha: AnaliseMaterializacaoCampanha,
    *,
    now: datetime | None = None,
) -> MaterializacaoReativacaoClassificacao:
    reference_time = now or datetime.now(UTC)
    active_chunk = obter_chunk_ativo_campanha(db, campanha.id)
    stale_chunk_count = len(obter_chunks_stale_ativos(db, campanha_id=campanha.id))
    running_execution_count = int(
        db.scalar(
            select(func.count(AnaliseMaterializacaoExecucao.id)).where(
                AnaliseMaterializacaoExecucao.campanha_id == campanha.id,
                AnaliseMaterializacaoExecucao.status == "running",
            )
        )
        or 0
    )
    created_at = _coerce_utc_datetime(campanha.created_at)
    age_seconds = max(0, int((reference_time - created_at).total_seconds())) if created_at else None
    wait_reason = (campanha.summary or {}).get("wait_reason") if isinstance(campanha.summary, dict) else None

    if campanha.pending_items <= 0:
        return MaterializacaoReativacaoClassificacao(
            reason_code="NO_PENDING_ITEMS",
            recoverable=False,
            active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )
    if stale_chunk_count > 0:
        return MaterializacaoReativacaoClassificacao(
            reason_code="STALE_CHUNK",
            recoverable=True,
            active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )
    if campanha.status != "pending":
        return MaterializacaoReativacaoClassificacao(
            reason_code="NOT_PENDING",
            recoverable=False,
            active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )
    if active_chunk is not None or campanha.running_items > 0 or running_execution_count > 0:
        return MaterializacaoReativacaoClassificacao(
            reason_code="CHUNK_IN_PROGRESS",
            recoverable=False,
            active_chunk_id=str(active_chunk.id) if active_chunk is not None else None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )

    gate = obter_estado_gate_materializacao(db)
    if gate.status == "red":
        return MaterializacaoReativacaoClassificacao(
            reason_code="WAITING_FOR_GATE",
            recoverable=False,
            active_chunk_id=None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )

    running_campaigns = int(
        db.scalar(
            select(func.count(AnaliseMaterializacaoCampanha.id)).where(
                AnaliseMaterializacaoCampanha.status == "running",
                AnaliseMaterializacaoCampanha.id != campanha.id,
            )
        )
        or 0
    )
    if running_campaigns >= _settings.analise_materializacao_max_active_campaigns or wait_reason == "MAX_ACTIVE_CAMPAIGNS_REACHED":
        return MaterializacaoReativacaoClassificacao(
            reason_code="WAITING_FOR_SLOT",
            recoverable=False,
            active_chunk_id=None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )

    if wait_reason in {"INGESTION_ACTIVE", "MANUAL_PAUSE"}:
        return MaterializacaoReativacaoClassificacao(
            reason_code="WAITING_FOR_GATE",
            recoverable=False,
            active_chunk_id=None,
            stale_chunk_count=stale_chunk_count,
            running_execution_count=running_execution_count,
            age_seconds=age_seconds,
        )

    return MaterializacaoReativacaoClassificacao(
        reason_code="PENDING_UNDISPATCHED",
        recoverable=True,
        active_chunk_id=None,
        stale_chunk_count=stale_chunk_count,
        running_execution_count=running_execution_count,
        age_seconds=age_seconds,
    )


def reativar_materializacao_campanha(
    db: Session,
    campanha_id: uuid.UUID,
) -> MaterializacaoReativacaoResultado:
    reference_time = datetime.now(UTC)
    campanha = db.get(AnaliseMaterializacaoCampanha, campanha_id)
    if campanha is None:
        return MaterializacaoReativacaoResultado(
            status="rejected",
            reason_code="CAMPAIGN_NOT_FOUND",
            affected_campaigns=(),
            requeued_campaigns=(),
            recovered_chunks=0,
            recovered_items=0,
            dispatcher_enqueued=False,
            triggered_at=reference_time,
        )

    classificacao = classificar_recuperacao_materializacao_campanha(
        db,
        campanha,
        now=reference_time,
    )

    if classificacao.reason_code == "STALE_CHUNK":
        recuperacao = recuperar_chunks_materializacao_stale(db, campanha_id=campanha.id)
        campanha = db.get(AnaliseMaterializacaoCampanha, campanha.id)
        if campanha is not None:
            _registrar_recovery_state_campanha(
                campanha,
                recovery_state="requeued",
                reason_code="STALE_CHUNK",
                action="recovered_and_requeued",
                checked_at=reference_time,
            )
            db.commit()
        return MaterializacaoReativacaoResultado(
            status="recovered",
            reason_code="STALE_CHUNK",
            affected_campaigns=recuperacao.affected_campaigns,
            requeued_campaigns=recuperacao.affected_campaigns,
            recovered_chunks=recuperacao.recovered_chunks,
            recovered_items=recuperacao.recovered_items,
            dispatcher_enqueued=bool(recuperacao.affected_campaigns),
            triggered_at=reference_time,
        )

    if classificacao.reason_code == "PENDING_UNDISPATCHED":
        campanha = db.get(AnaliseMaterializacaoCampanha, campanha.id)
        if campanha is not None:
            _registrar_recovery_state_campanha(
                campanha,
                recovery_state="requeued",
                reason_code="PENDING_UNDISPATCHED",
                action="requeued",
                checked_at=reference_time,
            )
            db.commit()
        return MaterializacaoReativacaoResultado(
            status="triggered",
            reason_code="PENDING_UNDISPATCHED",
            affected_campaigns=(str(campanha_id),),
            requeued_campaigns=(str(campanha_id),),
            recovered_chunks=0,
            recovered_items=0,
            dispatcher_enqueued=True,
            triggered_at=reference_time,
        )

    campanha = db.get(AnaliseMaterializacaoCampanha, campanha.id)
    if campanha is not None:
        _registrar_recovery_state_campanha(
            campanha,
            recovery_state="blocked" if classificacao.reason_code in {"WAITING_FOR_GATE", "WAITING_FOR_SLOT", "CHUNK_IN_PROGRESS"} else "noop",
            reason_code=classificacao.reason_code,
            action="noop",
            checked_at=reference_time,
        )
        db.commit()
    return MaterializacaoReativacaoResultado(
        status="noop",
        reason_code=classificacao.reason_code,
        affected_campaigns=(str(campanha_id),),
        requeued_campaigns=(),
        recovered_chunks=0,
        recovered_items=0,
        dispatcher_enqueued=False,
        triggered_at=reference_time,
    )


def recuperar_materializacao_pendente(
    db: Session,
    *,
    max_campaigns: int | None = None,
    max_requeues: int | None = None,
    min_age_seconds: int | None = None,
) -> MaterializacaoReativacaoSweepResultado:
    reference_time = datetime.now(UTC)
    if not _settings.analise_materializacao_pending_recovery_enabled:
        summary = {
            "status": "noop",
            "reason_code": "PENDING_RECOVERY_DISABLED",
            "affected_campaigns": [],
            "requeued_campaigns": [],
            "recovered_chunks": 0,
            "recovered_items": 0,
            "dispatcher_enqueued": False,
            "scanned_campaigns": 0,
            "recoverable_campaigns": 0,
        }
        _persistir_summary_recuperacao_pendente_controle(db, summary=summary, reference_time=reference_time)
        return MaterializacaoReativacaoSweepResultado(
            status="noop",
            reason_code="PENDING_RECOVERY_DISABLED",
            affected_campaigns=(),
            requeued_campaigns=(),
            recovered_chunks=0,
            recovered_items=0,
            dispatcher_enqueued=False,
            triggered_at=reference_time,
            scanned_campaigns=0,
            recoverable_campaigns=0,
        )

    limit = max_campaigns or _settings.analise_materializacao_pending_recovery_max_campaigns
    requeue_limit = max_requeues or _settings.analise_materializacao_pending_recovery_max_requeues
    threshold = (
        _settings.analise_materializacao_pending_recovery_min_age_seconds
        if min_age_seconds is None
        else min_age_seconds
    )
    pending_campaigns = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanha)
            .where(AnaliseMaterializacaoCampanha.status == "pending")
            .order_by(AnaliseMaterializacaoCampanha.created_at.asc())
            .limit(limit)
        ).all()
    )
    affected_campaigns: list[str] = []
    requeued_campaigns: list[str] = []
    recovered_chunks = 0
    recovered_items = 0
    recoverable_campaigns = 0

    for campanha in pending_campaigns:
        if len(requeued_campaigns) >= requeue_limit:
            break
        classificacao = classificar_recuperacao_materializacao_campanha(
            db,
            campanha,
            now=reference_time,
        )
        if classificacao.reason_code == "STALE_CHUNK" or (
            classificacao.reason_code == "PENDING_UNDISPATCHED"
            and (classificacao.age_seconds or 0) >= threshold
        ):
            recoverable_campaigns += 1
        if classificacao.reason_code == "PENDING_UNDISPATCHED" and (classificacao.age_seconds or 0) < threshold:
            _registrar_recovery_state_campanha(
                campanha,
                recovery_state="pending_threshold",
                reason_code="PENDING_UNDISPATCHED",
                action="sweep_threshold_skip",
                checked_at=reference_time,
            )
            continue
        if classificacao.reason_code not in {"PENDING_UNDISPATCHED", "STALE_CHUNK"}:
            _registrar_recovery_state_campanha(
                campanha,
                recovery_state="blocked" if classificacao.reason_code in {"WAITING_FOR_GATE", "WAITING_FOR_SLOT", "CHUNK_IN_PROGRESS"} else "noop",
                reason_code=classificacao.reason_code,
                action="sweep_noop",
                checked_at=reference_time,
            )
            continue
        resultado = reativar_materializacao_campanha(
            db,
            campanha.id,
        )
        affected_campaigns.extend(resultado.affected_campaigns)
        requeued_campaigns.extend(resultado.requeued_campaigns)
        recovered_chunks += resultado.recovered_chunks
        recovered_items += resultado.recovered_items

    db.commit()
    affected_unique = tuple(sorted(set(affected_campaigns)))
    requeued_unique = tuple(sorted(set(requeued_campaigns)))
    status = "recovered" if recovered_chunks > 0 else ("triggered" if requeued_unique else "noop")
    reason_code = "STALE_CHUNK" if recovered_chunks > 0 else ("PENDING_UNDISPATCHED" if requeued_unique else "NO_PENDING_ITEMS")
    summary = {
        "status": status,
        "reason_code": reason_code,
        "affected_campaigns": list(affected_unique),
        "requeued_campaigns": list(requeued_unique),
        "recovered_chunks": recovered_chunks,
        "recovered_items": recovered_items,
        "dispatcher_enqueued": bool(requeued_unique),
        "scanned_campaigns": len(pending_campaigns),
        "recoverable_campaigns": recoverable_campaigns,
    }
    _persistir_summary_recuperacao_pendente_controle(db, summary=summary, reference_time=reference_time)
    return MaterializacaoReativacaoSweepResultado(
        status=status,
        reason_code=reason_code,
        affected_campaigns=affected_unique,
        requeued_campaigns=requeued_unique,
        recovered_chunks=recovered_chunks,
        recovered_items=recovered_items,
        dispatcher_enqueued=bool(requeued_unique),
        triggered_at=reference_time,
        scanned_campaigns=len(pending_campaigns),
        recoverable_campaigns=recoverable_campaigns,
    )


def obter_estado_gate_materializacao(db: Session) -> MaterializacaoGateState:
    controle = obter_controle_materializacao(db)
    if not _settings.analise_materializacao_gate_enabled:
        return MaterializacaoGateState(
            status="green",
            reason_code="GATE_DISABLED",
            gate_enabled=False,
            manual_control=cast(Literal["auto", "paused"], controle.mode),
            manual_reason=controle.reason,
            blocking_ingestions=0,
            pending_ingestions=0,
            next_check_at=None,
            blockers=(),
        )

    if controle.mode == "paused":
        return MaterializacaoGateState(
            status="red",
            reason_code="MANUAL_PAUSE",
            gate_enabled=True,
            manual_control="paused",
            manual_reason=controle.reason,
            blocking_ingestions=0,
            pending_ingestions=0,
            next_check_at=datetime.now(UTC) + timedelta(seconds=_settings.analise_materializacao_gate_poll_seconds),
            blockers=(),
        )

    blocking_statuses = _settings.parse_csv_set(_settings.analise_materializacao_blocking_sync_statuses)
    blocker_rows = db.execute(
        select(
            ExecucaoSincronizacao.tipo_fonte,
            ExecucaoSincronizacao.id,
            IngestionRun.id,
            ExecucaoSincronizacao.ano,
            ExecucaoSincronizacao.status,
            IngestionRun.phase,
            func.coalesce(IngestionRun.started_at, ExecucaoSincronizacao.iniciada_em),
        )
        .select_from(ExecucaoSincronizacao)
        .outerjoin(IngestionRun, IngestionRun.execucao_sincronizacao_id == ExecucaoSincronizacao.id)
        .where(ExecucaoSincronizacao.status.in_(blocking_statuses))
        .order_by(func.coalesce(IngestionRun.started_at, ExecucaoSincronizacao.iniciada_em).asc())
        .limit(10)
    ).all()
    blocking_ingestions = int(
        db.scalar(
            select(func.count(ExecucaoSincronizacao.id)).where(ExecucaoSincronizacao.status.in_(blocking_statuses))
        )
        or 0
    )
    pending_ingestions = int(
        db.scalar(
            select(func.count(ExecucaoSincronizacao.id)).where(ExecucaoSincronizacao.status == "aguardando_ingestao")
        )
        or 0
    )
    blockers = tuple(
        MaterializacaoGateBlocker(
            source_type=row[0],
            execution_id=str(row[1]) if row[1] is not None else None,
            run_id=str(row[2]) if row[2] is not None else None,
            year=row[3],
            status=row[4],
            phase=row[5],
            started_at=row[6],
        )
        for row in blocker_rows
    )
    if blocking_ingestions > 0:
        return MaterializacaoGateState(
            status="red",
            reason_code="INGESTION_ACTIVE",
            gate_enabled=True,
            manual_control="auto",
            manual_reason=controle.reason,
            blocking_ingestions=blocking_ingestions,
            pending_ingestions=pending_ingestions,
            next_check_at=datetime.now(UTC) + timedelta(seconds=_settings.analise_materializacao_gate_poll_seconds),
            blockers=blockers,
        )
    return MaterializacaoGateState(
        status="green",
        reason_code="NO_BLOCKERS",
        gate_enabled=True,
        manual_control="auto",
        manual_reason=controle.reason,
        blocking_ingestions=0,
        pending_ingestions=pending_ingestions,
        next_check_at=None,
        blockers=blockers,
    )


def _lease_expires_at_from(now: datetime) -> datetime:
    return now + timedelta(seconds=_settings.analise_materializacao_chunk_lease_seconds)


def _stale_cutoff(now: datetime | None = None) -> datetime:
    reference = now or datetime.now(UTC)
    return reference - timedelta(seconds=_settings.analise_materializacao_stale_grace_seconds)


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def listar_chunks_campanha(
    db: Session,
    campanha_id: uuid.UUID,
    *,
    statuses: set[str] | None = None,
) -> list[AnaliseMaterializacaoChunkExecucao]:
    stmt = (
        select(AnaliseMaterializacaoChunkExecucao)
        .where(AnaliseMaterializacaoChunkExecucao.campanha_id == campanha_id)
        .order_by(AnaliseMaterializacaoChunkExecucao.created_at.desc())
    )
    if statuses:
        stmt = stmt.where(AnaliseMaterializacaoChunkExecucao.status.in_(statuses))
    return list(db.scalars(stmt).all())


def obter_chunk_ativo_campanha(
    db: Session,
    campanha_id: uuid.UUID,
) -> AnaliseMaterializacaoChunkExecucao | None:
    now = datetime.now(UTC)
    return db.scalar(
        select(AnaliseMaterializacaoChunkExecucao)
        .where(
            AnaliseMaterializacaoChunkExecucao.campanha_id == campanha_id,
            AnaliseMaterializacaoChunkExecucao.status.in_(_MATERIALIZACAO_ACTIVE_CHUNK_STATUSES),
            or_(
                AnaliseMaterializacaoChunkExecucao.lease_expires_at.is_(None),
                AnaliseMaterializacaoChunkExecucao.lease_expires_at >= now,
            ),
        )
        .order_by(AnaliseMaterializacaoChunkExecucao.created_at.desc())
        .limit(1)
    )


def listar_chunks_ativos_campanha(
    db: Session,
    campanha_id: uuid.UUID,
    *,
    limit: int | None = None,
) -> list[AnaliseMaterializacaoChunkExecucao]:
    now = datetime.now(UTC)
    stmt = (
        select(AnaliseMaterializacaoChunkExecucao)
        .where(
            AnaliseMaterializacaoChunkExecucao.campanha_id == campanha_id,
            AnaliseMaterializacaoChunkExecucao.status.in_(("queued", "running")),
            or_(
                AnaliseMaterializacaoChunkExecucao.lease_expires_at.is_(None),
                AnaliseMaterializacaoChunkExecucao.lease_expires_at >= now,
            ),
        )
        .order_by(AnaliseMaterializacaoChunkExecucao.created_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def contar_chunks_ativos_campanha(db: Session, campanha_id: uuid.UUID) -> int:
    return len(listar_chunks_ativos_campanha(db, campanha_id))


def contar_chunks_stale_campanha(db: Session, campanha_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(AnaliseMaterializacaoChunkExecucao.id)).where(
                AnaliseMaterializacaoChunkExecucao.campanha_id == campanha_id,
                AnaliseMaterializacaoChunkExecucao.status == "stale",
            )
        )
        or 0
    )



def obter_chunks_stale_ativos(
    db: Session,
    *,
    campanha_id: uuid.UUID | None = None,
    chunk_execucao_id: uuid.UUID | None = None,
    limit: int | None = None,
) -> list[AnaliseMaterializacaoChunkExecucao]:
    stmt = select(AnaliseMaterializacaoChunkExecucao).where(
        AnaliseMaterializacaoChunkExecucao.status.in_(("queued", "running")),
        AnaliseMaterializacaoChunkExecucao.lease_expires_at.is_not(None),
        AnaliseMaterializacaoChunkExecucao.lease_expires_at < _stale_cutoff(),
    )
    if campanha_id is not None:
        stmt = stmt.where(AnaliseMaterializacaoChunkExecucao.campanha_id == campanha_id)
    if chunk_execucao_id is not None:
        stmt = stmt.where(AnaliseMaterializacaoChunkExecucao.id == chunk_execucao_id)
    stmt = stmt.order_by(AnaliseMaterializacaoChunkExecucao.lease_expires_at.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def criar_materializacao_campanha(
    db: Session,
    *,
    codigos_cvm: Sequence[int],
    source: str,
    source_execucao_id: str | None = None,
    chunk_size: int | None = None,
    incluir_canceladas: bool = False,
) -> AnaliseMaterializacaoCampanha:
    invalidated_from_por_codigo = _invalidated_from_por_codigo_cvm(
        db,
        codigos_cvm=codigos_cvm,
        source_execucao_id=source_execucao_id,
    )
    campanha = AnaliseMaterializacaoCampanha(
        source=source,
        source_execucao_id=uuid.UUID(source_execucao_id) if source_execucao_id else None,
        status="pending",
        chunk_size=chunk_size or _settings.analise_materializacao_chunk_size,
        summary={},
    )
    db.add(campanha)
    db.flush()

    companhias = {
        item.codigo_cvm: item
        for item in db.scalars(select(Companhia).where(Companhia.codigo_cvm.in_(sorted(set(codigos_cvm))))).all()
        if item.codigo_cvm is not None
    }
    codigos_cancelados = {
        codigo_cvm
        for codigo_cvm, companhia in companhias.items()
        if codigo_cvm is not None and not incluir_canceladas and _companhia_tem_registro_cancelado(companhia)
    }
    campanha.summary = {
        **(campanha.summary or {}),
        "selection": {
            "requested_codigo_cvm_count": len(set(codigos_cvm)),
            "eligible_codigo_cvm_count": len(set(codigos_cvm)) - len(codigos_cancelados),
            "excluded_cancelled_codigo_cvm_count": len(codigos_cancelados),
            "incluir_canceladas": incluir_canceladas,
        },
    }
    itens: list[AnaliseMaterializacaoCampanhaItem] = []
    ordem = 0
    for codigo_cvm in sorted(set(codigos_cvm)):
        if codigo_cvm in codigos_cancelados:
            continue
        companhia = companhias.get(codigo_cvm)
        for escopo in ("consolidated", "individual"):
            ordem += 1
            active_item = db.scalar(
                select(AnaliseMaterializacaoCampanhaItem.id)
                .join(
                    AnaliseMaterializacaoCampanha,
                    AnaliseMaterializacaoCampanha.id == AnaliseMaterializacaoCampanhaItem.campanha_id,
                )
                .where(
                    AnaliseMaterializacaoCampanhaItem.codigo_cvm == codigo_cvm,
                    AnaliseMaterializacaoCampanhaItem.escopo == escopo,
                    AnaliseMaterializacaoCampanhaItem.status.in_(_MATERIALIZACAO_ACTIVE_ITEM_STATUSES),
                    AnaliseMaterializacaoCampanha.status.in_(_MATERIALIZACAO_ACTIVE_CAMPAIGN_STATUSES),
                )
                .limit(1)
            )
            if active_item is not None:
                itens.append(
                    AnaliseMaterializacaoCampanhaItem(
                        campanha_id=campanha.id,
                        codigo_cvm=codigo_cvm,
                        companhia_id=companhia.id if companhia is not None else None,
                        escopo=escopo,
                        status="skipped",
                        ordem=ordem,
                        attempts=0,
                        invalidated_from=invalidated_from_por_codigo.get(codigo_cvm),
                        reason="ALREADY_COVERED_BY_ACTIVE_CAMPAIGN",
                        last_error=f"Ja existe trabalho ativo para codigo_cvm={codigo_cvm} escopo={escopo}.",
                        finished_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                continue
            itens.append(
                AnaliseMaterializacaoCampanhaItem(
                    campanha_id=campanha.id,
                    codigo_cvm=codigo_cvm,
                    companhia_id=companhia.id if companhia is not None else None,
                    escopo=escopo,
                    status="pending",
                    ordem=ordem,
                    attempts=0,
                    invalidated_from=invalidated_from_por_codigo.get(codigo_cvm),
                    updated_at=datetime.now(UTC),
                )
            )
    db.add_all(itens)
    db.flush()
    _recalcular_materializacao_campanha(db, campanha)
    db.commit()
    db.refresh(campanha)
    return campanha


def claim_materializacao_campanha_chunk(
    db: Session,
    campanha_id: uuid.UUID,
    *,
    chunk_size: int,
) -> tuple[AnaliseMaterializacaoChunkExecucao, list[AnaliseMaterializacaoCampanhaItem]] | None:
    claimed = claim_materializacao_campanha_chunks(
        db,
        campanha_id,
        chunk_size=chunk_size,
        max_chunks=1,
    )
    if not claimed:
        return None
    return claimed[0]


def claim_materializacao_campanha_chunks(
    db: Session,
    campanha_id: uuid.UUID,
    *,
    chunk_size: int,
    max_chunks: int,
) -> list[tuple[AnaliseMaterializacaoChunkExecucao, list[AnaliseMaterializacaoCampanhaItem]]]:
    if max_chunks <= 0:
        return []
    now = datetime.now(UTC)
    campanha = db.scalar(
        select(AnaliseMaterializacaoCampanha)
        .where(AnaliseMaterializacaoCampanha.id == campanha_id)
        .with_for_update()
    )
    if campanha is None:
        return []
    available_chunk_slots = max(0, max_chunks - contar_chunks_ativos_campanha(db, campanha_id))
    if available_chunk_slots <= 0:
        return []
    claimed_chunks: list[tuple[AnaliseMaterializacaoChunkExecucao, list[AnaliseMaterializacaoCampanhaItem]]] = []
    for _ in range(available_chunk_slots):
        item_ids = list(
            db.scalars(
                select(AnaliseMaterializacaoCampanhaItem.id)
                .where(
                    AnaliseMaterializacaoCampanhaItem.campanha_id == campanha_id,
                    AnaliseMaterializacaoCampanhaItem.status == "pending",
                )
                .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
                .limit(chunk_size)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not item_ids:
            break
        items = list(
            db.scalars(
                select(AnaliseMaterializacaoCampanhaItem)
                .where(AnaliseMaterializacaoCampanhaItem.id.in_(item_ids))
                .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
            ).all()
        )
        chunk = AnaliseMaterializacaoChunkExecucao(
            campanha_id=campanha_id,
            status="queued",
            lease_expires_at=_lease_expires_at_from(now),
            heartbeat_at=now,
            item_count=len(items),
            processed_items=0,
            success_items=0,
            failed_items=0,
            summary={},
            updated_at=now,
        )
        db.add(chunk)
        db.flush()
        for item in items:
            item.status = "running"
            item.enqueued_at = now
            item.chunk_execucao_id = chunk.id
            item.reason = None
            item.updated_at = now
        db.flush()
        claimed_chunks.append((chunk, items))

    if not claimed_chunks:
        return []
    campanha.started_at = campanha.started_at or now
    campanha.updated_at = now
    campanha.status = "running"
    db.flush()
    _recalcular_materializacao_campanha(db, campanha)
    db.flush()
    db.commit()
    for chunk, _items in claimed_chunks:
        db.refresh(chunk)
    return claimed_chunks


def renovar_chunk_execucao_lease(
    db: Session,
    chunk: AnaliseMaterializacaoChunkExecucao,
    *,
    lease_owner: str | None = None,
) -> AnaliseMaterializacaoChunkExecucao:
    now = datetime.now(UTC)
    if lease_owner is not None:
        chunk.lease_owner = lease_owner
    chunk.heartbeat_at = now
    chunk.lease_expires_at = _lease_expires_at_from(now)
    chunk.updated_at = now
    db.flush()
    return chunk


def iniciar_chunk_execucao(
    db: Session,
    chunk: AnaliseMaterializacaoChunkExecucao,
    *,
    lease_owner: str | None,
) -> AnaliseMaterializacaoChunkExecucao:
    chunk.status = "running"
    chunk.started_at = chunk.started_at or datetime.now(UTC)
    renovar_chunk_execucao_lease(db, chunk, lease_owner=lease_owner)
    db.commit()
    db.refresh(chunk)
    return chunk


def registrar_progresso_chunk_execucao(
    db: Session,
    chunk: AnaliseMaterializacaoChunkExecucao,
    *,
    lease_owner: str | None,
    processed_items: int,
    success_items: int,
    failed_items: int,
) -> AnaliseMaterializacaoChunkExecucao:
    chunk.processed_items = processed_items
    chunk.success_items = success_items
    chunk.failed_items = failed_items
    chunk.summary = {
        **(chunk.summary or {}),
        "processed_items": processed_items,
        "success_items": success_items,
        "failed_items": failed_items,
    }
    renovar_chunk_execucao_lease(db, chunk, lease_owner=lease_owner)
    db.commit()
    db.refresh(chunk)
    return chunk


def finalizar_chunk_execucao(
    db: Session,
    chunk: AnaliseMaterializacaoChunkExecucao,
    *,
    status: Literal["success", "failed", "stale", "cancelled"],
    processed_items: int,
    success_items: int,
    failed_items: int,
    summary: dict[str, Any] | None = None,
) -> AnaliseMaterializacaoChunkExecucao:
    finished_at = datetime.now(UTC)
    chunk.status = status
    chunk.processed_items = processed_items
    chunk.success_items = success_items
    chunk.failed_items = failed_items
    chunk.finished_at = finished_at
    chunk.updated_at = finished_at
    chunk.heartbeat_at = finished_at
    chunk.lease_expires_at = finished_at
    chunk.summary = {
        **(chunk.summary or {}),
        **(summary or {}),
        "processed_items": processed_items,
        "success_items": success_items,
        "failed_items": failed_items,
    }
    db.commit()
    db.refresh(chunk)
    return chunk


def reverter_itens_materializacao_para_pending(
    db: Session,
    item_ids: Sequence[uuid.UUID],
    *,
    reason: str,
) -> list[AnaliseMaterializacaoCampanhaItem]:
    if not item_ids:
        return []
    items = list(
        db.scalars(
            select(AnaliseMaterializacaoCampanhaItem)
            .where(AnaliseMaterializacaoCampanhaItem.id.in_(list(item_ids)))
            .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
        ).all()
    )
    now = datetime.now(UTC)
    campanhas_afetadas: set[uuid.UUID] = set()
    for item in items:
        item.status = "pending"
        item.reason = reason
        item.last_error = None
        item.updated_at = now
        item.enqueued_at = None
        item.chunk_execucao_id = None
        campanhas_afetadas.add(item.campanha_id)
    for campanha_id in campanhas_afetadas:
        campanha = db.get(AnaliseMaterializacaoCampanha, campanha_id)
        if campanha is not None:
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": reason,
                "wait_retry_scheduled_in_seconds": _settings.analise_materializacao_gate_poll_seconds,
            }
            _recalcular_materializacao_campanha(db, campanha)
    db.commit()
    return items


def recuperar_chunks_materializacao_stale(
    db: Session,
    *,
    campanha_id: uuid.UUID | None = None,
    chunk_execucao_id: uuid.UUID | None = None,
) -> MaterializacaoRecuperacaoResultado:
    chunks = obter_chunks_stale_ativos(
        db,
        campanha_id=campanha_id,
        chunk_execucao_id=chunk_execucao_id,
    )

    recovered_items = 0
    affected_campaigns: set[str] = set()
    chunk_ids: list[str] = []
    now = datetime.now(UTC)

    for chunk in chunks:
        chunk_ids.append(str(chunk.id))
        affected_campaigns.add(str(chunk.campanha_id))
        items = list(
            db.scalars(
                select(AnaliseMaterializacaoCampanhaItem)
                .where(AnaliseMaterializacaoCampanhaItem.chunk_execucao_id == chunk.id)
                .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
            ).all()
        )
        running_items = [item for item in items if item.status == "running"]
        running_item_ids = [item.id for item in running_items]
        if running_item_ids:
            recovered_items += len(
                reverter_itens_materializacao_para_pending(
                    db,
                    running_item_ids,
                    reason="STALE_CHUNK_RECOVERED",
                )
            )
            running_execucoes = list(
                db.scalars(
                    select(AnaliseMaterializacaoExecucao).where(
                        AnaliseMaterializacaoExecucao.campanha_item_id.in_(running_item_ids),
                        AnaliseMaterializacaoExecucao.status == "running",
                    )
                ).all()
            )
            for execucao in running_execucoes:
                execucao.status = "failed"
                execucao.coverage_complete = False
                execucao.finished_at = now
                execucao.updated_at = now
                execucao.summary = {
                    **(execucao.summary or {}),
                    "error": "stale_chunk_recovered",
                }
            db.commit()
        finalizar_chunk_execucao(
            db,
            chunk,
            status="stale",
            processed_items=chunk.processed_items,
            success_items=chunk.success_items,
            failed_items=chunk.failed_items,
            summary={"reason": "STALE_CHUNK_RECOVERED"},
        )
        campanha = db.get(AnaliseMaterializacaoCampanha, chunk.campanha_id)
        if campanha is not None:
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": "STALE_CHUNK_RECOVERED",
                "wait_retry_scheduled_in_seconds": _settings.analise_materializacao_recovery_sweep_seconds,
            }
            _recalcular_materializacao_campanha(db, campanha)
            db.commit()

    # 2. Check for campaigns stuck in running status but having no active chunks
    if chunk_execucao_id is None:
        stmt_camps = select(AnaliseMaterializacaoCampanha).where(
            AnaliseMaterializacaoCampanha.status == "running"
        )
        if campanha_id is not None:
            stmt_camps = stmt_camps.where(AnaliseMaterializacaoCampanha.id == campanha_id)
        
        running_camps = list(db.scalars(stmt_camps).all())
        for camp in running_camps:
            stmt_active_chunks = select(AnaliseMaterializacaoChunkExecucao).where(
                AnaliseMaterializacaoChunkExecucao.campanha_id == camp.id,
                AnaliseMaterializacaoChunkExecucao.status.in_(["running", "queued"])
            )
            active_chunk_count = db.scalar(select(func.count()).select_from(stmt_active_chunks.subquery())) or 0
            
            if active_chunk_count == 0:
                affected_campaigns.add(str(camp.id))
                
                # Check for running items that are stuck (no active chunks)
                stmt_running_items = select(AnaliseMaterializacaoCampanhaItem).where(
                    AnaliseMaterializacaoCampanhaItem.campanha_id == camp.id,
                    AnaliseMaterializacaoCampanhaItem.status == "running"
                )
                stuck_items = list(db.scalars(stmt_running_items).all())
                
                if stuck_items:
                    stuck_item_ids = [item.id for item in stuck_items]
                    recovered_items += len(
                        reverter_itens_materializacao_para_pending(
                            db,
                            stuck_item_ids,
                            reason="STUCK_ITEM_RECOVERED",
                        )
                    )
                    running_execucoes = list(
                        db.scalars(
                            select(AnaliseMaterializacaoExecucao).where(
                                AnaliseMaterializacaoExecucao.campanha_item_id.in_(stuck_item_ids),
                                AnaliseMaterializacaoExecucao.status == "running",
                            )
                        ).all()
                    )
                    for execucao in running_execucoes:
                        execucao.status = "failed"
                        execucao.coverage_complete = False
                        execucao.finished_at = now
                        execucao.updated_at = now
                        execucao.summary = {
                            **(execucao.summary or {}),
                            "error": "stuck_item_recovered",
                        }
                    db.commit()
                
                camp.summary = {
                    **(camp.summary or {}),
                    "wait_reason": "STUCK_CAMPAIGN_RECOVERED",
                    "wait_retry_scheduled_in_seconds": _settings.analise_materializacao_recovery_sweep_seconds,
                }
                _recalcular_materializacao_campanha(db, camp)
                db.commit()

    return MaterializacaoRecuperacaoResultado(
        recovered_chunks=len(chunk_ids),
        recovered_items=recovered_items,
        affected_campaigns=tuple(sorted(affected_campaigns)),
        chunk_ids=tuple(chunk_ids),
    )


def registrar_resultado_materializacao_campanha_item(
    db: Session,
    item: AnaliseMaterializacaoCampanhaItem,
    *,
    status: Literal["success", "failed"],
    materializacao_execucao_id: uuid.UUID | None = None,
    last_error: str | None = None,
) -> AnaliseMaterializacaoCampanhaItem:
    item.status = status
    item.materializacao_execucao_id = materializacao_execucao_id
    item.last_error = last_error
    item.finished_at = datetime.now(UTC)
    item.updated_at = item.finished_at
    campanha = db.get(AnaliseMaterializacaoCampanha, item.campanha_id)
    if campanha is not None:
        _recalcular_materializacao_campanha(db, campanha)
    db.commit()
    db.refresh(item)
    return item


def materializar_analise_companhia(
    db: Session,
    companhia: Companhia,
    *,
    scope: AnaliseEscopo = "consolidated",
    source: str = "manual",
    invalidated_from: date | None = None,
    incluir_canceladas: bool = False,
    campanha_id: uuid.UUID | None = None,
    campanha_item_id: uuid.UUID | None = None,
    chunk_execucao_id: uuid.UUID | None = None,
    queue_name: str | None = None,
    position_in_chunk: int | None = None,
) -> AnaliseMaterializacaoExecucao:
    def atualizar_execucao_progresso(
        *,
        processed_knowledge_dates: int,
        total_knowledge_dates: int,
        current_known_from: date | None,
        context_revisions: int,
        fact_revisions: int,
    ) -> None:
        progress_ratio = (processed_knowledge_dates / total_knowledge_dates) if total_knowledge_dates > 0 else None
        execucao.summary = {
            **(execucao.summary or {}),
            "progress": {
                "total_knowledge_dates": total_knowledge_dates,
                "processed_knowledge_dates": processed_knowledge_dates,
                "current_known_from": current_known_from.isoformat() if current_known_from is not None else None,
                "progress_ratio": progress_ratio,
                "context_revisions": context_revisions,
                "fact_revisions": fact_revisions,
            },
        }
        execucao.updated_at = datetime.now(UTC)
        db.commit()

    if _companhia_tem_registro_cancelado(companhia) and not incluir_canceladas:
        started_at = datetime.now(UTC)
        execucao = AnaliseMaterializacaoExecucao(
            companhia_id=companhia.id,
            codigo_cvm=companhia.codigo_cvm,
            escopo=scope,
            calculation_version=CALCULATION_VERSION,
            status="success",
            coverage_complete=False,
            source=source,
            materialization_mode="full",
            invalidated_from=None,
            campanha_id=campanha_id,
            campanha_item_id=campanha_item_id,
            chunk_execucao_id=chunk_execucao_id,
            queue_name=queue_name,
            position_in_chunk=position_in_chunk,
            summary={
                "mode": "full",
                "invalidated_from": None,
                "knowledge_dates": 0,
                "window_total_knowledge_dates": 0,
                "window_processed_knowledge_dates": 0,
                "context_revisions": 0,
                "fact_revisions": 0,
                "inserted_context_revisions": 0,
                "inserted_fact_revisions": 0,
                "closed_context_revisions": 0,
                "closed_fact_revisions": 0,
                "deleted_future_context_revisions": 0,
                "deleted_future_fact_revisions": 0,
                "skipped_reason": "COMPANHIA_CANCELADA",
                "company_status": companhia.situacao_registro,
                "incluir_canceladas": False,
                "progress": {
                    "total_knowledge_dates": 0,
                    "processed_knowledge_dates": 0,
                    "current_known_from": None,
                    "progress_ratio": None,
                    "context_revisions": 0,
                    "fact_revisions": 0,
                },
            },
            started_at=started_at,
            finished_at=started_at,
            updated_at=started_at,
        )
        db.add(execucao)
        db.commit()
        db.refresh(execucao)
        return execucao

    all_knowledge_dates = _knowledge_dates_for_materialization(db, companhia)
    materialization_mode, effective_invalidated_from = _knowledge_date_bounds_for_execucao(
        knowledge_dates=all_knowledge_dates,
        invalidated_from=invalidated_from,
    )
    latest_execucao = _latest_successful_materialization(db, companhia, scope)
    if latest_execucao is None:
        materialization_mode = "full"
        effective_invalidated_from = None

    execution_knowledge_dates = (
        all_knowledge_dates
        if materialization_mode == "full"
        else [item for item in all_knowledge_dates if item >= cast(date, effective_invalidated_from)]
    )

    started_at = datetime.now(UTC)
    execucao = AnaliseMaterializacaoExecucao(
        companhia_id=companhia.id,
        codigo_cvm=companhia.codigo_cvm,
        escopo=scope,
        calculation_version=CALCULATION_VERSION,
        status="running",
        coverage_complete=False,
        source=source,
        materialization_mode=materialization_mode,
        invalidated_from=effective_invalidated_from,
        campanha_id=campanha_id,
        campanha_item_id=campanha_item_id,
        chunk_execucao_id=chunk_execucao_id,
        queue_name=queue_name,
        position_in_chunk=position_in_chunk,
        summary={},
        started_at=started_at,
        updated_at=started_at,
    )
    db.add(execucao)
    db.flush()

    try:
        if not all_knowledge_dates:
            execucao.status = "success"
            execucao.coverage_complete = False
            execucao.finished_at = datetime.now(UTC)
            execucao.updated_at = execucao.finished_at
            execucao.summary = {
                "mode": materialization_mode,
                "invalidated_from": effective_invalidated_from.isoformat() if effective_invalidated_from is not None else None,
                "knowledge_dates": 0,
                "window_total_knowledge_dates": 0,
                "window_processed_knowledge_dates": 0,
                "context_revisions": 0,
                "fact_revisions": 0,
                "inserted_context_revisions": 0,
                "inserted_fact_revisions": 0,
                "closed_context_revisions": 0,
                "closed_fact_revisions": 0,
                "deleted_future_context_revisions": 0,
                "deleted_future_fact_revisions": 0,
                "progress": {
                    "total_knowledge_dates": 0,
                    "processed_knowledge_dates": 0,
                    "current_known_from": None,
                    "progress_ratio": None,
                    "context_revisions": 0,
                    "fact_revisions": 0,
                },
            }
            db.commit()
            db.refresh(execucao)
            return execucao

        context_revisions_payloads: list[dict[str, Any]] = []
        current_context: dict[str, Any] | None = None
        current_context_start: date | None = None

        fact_revisions_payloads: list[dict[str, Any]] = []
        active_facts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        active_fact_starts: dict[tuple[str, str, str, str], date] = {}

        total_knowledge_dates = len(execution_knowledge_dates)
        atualizar_execucao_progresso(
            processed_knowledge_dates=0,
            total_knowledge_dates=total_knowledge_dates,
            current_known_from=None,
            context_revisions=0,
            fact_revisions=0,
        )

        for index, known_from in enumerate(execution_knowledge_dates, start=1):
            context_payload = _context_snapshot_payload(db, companhia, scope, known_from)
            if current_context is None:
                current_context = context_payload
                current_context_start = known_from
            elif current_context["fingerprint"] != context_payload["fingerprint"]:
                context_revisions_payloads.append(
                    {
                        **current_context,
                        "known_from": current_context_start,
                        "known_to": known_from,
                    }
                )
                current_context = context_payload
                current_context_start = known_from

            current_snapshot = _series_snapshot_payloads(db, companhia, scope, known_from)
            snapshot_keys = set(current_snapshot)

            for key in list(active_facts):
                if key not in snapshot_keys:
                    fact_revisions_payloads.append(
                        {
                            **active_facts[key],
                            "known_from": active_fact_starts[key],
                            "known_to": known_from,
                        }
                    )
                    del active_facts[key]
                    del active_fact_starts[key]

            for key, payload in current_snapshot.items():
                if key not in active_facts:
                    active_facts[key] = payload
                    active_fact_starts[key] = known_from
                    continue
                if active_facts[key]["fingerprint"] != payload["fingerprint"]:
                    fact_revisions_payloads.append(
                        {
                            **active_facts[key],
                            "known_from": active_fact_starts[key],
                            "known_to": known_from,
                        }
                    )
                    active_facts[key] = payload
                    active_fact_starts[key] = known_from

            atualizar_execucao_progresso(
                processed_knowledge_dates=index,
                total_knowledge_dates=total_knowledge_dates,
                current_known_from=known_from,
                context_revisions=len(context_revisions_payloads),
                fact_revisions=len(fact_revisions_payloads),
            )

        if current_context is not None and current_context_start is not None:
            context_revisions_payloads.append(
                {
                    **current_context,
                    "known_from": current_context_start,
                    "known_to": None,
                }
            )

        for key, payload in active_facts.items():
            fact_revisions_payloads.append(
                {
                    **payload,
                    "known_from": active_fact_starts[key],
                    "known_to": None,
                }
            )

        closed_context_revisions = 0
        closed_fact_revisions = 0
        deleted_future_context_revisions = 0
        deleted_future_fact_revisions = 0

        if materialization_mode == "full":
            deleted_future_context_revisions = int(
                db.scalar(
                    select(func.count(AnaliseContextoRevision.id)).where(
                        AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseContextoRevision.escopo == scope,
                        AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
                    )
                )
                or 0
            )
            deleted_future_fact_revisions = int(
                db.scalar(
                    select(func.count(AnaliseFatoRevision.id)).where(
                        AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseFatoRevision.escopo == scope,
                        AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
                    )
                )
                or 0
            )
            db.execute(
                delete(AnaliseContextoRevision).where(
                    AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
                    AnaliseContextoRevision.escopo == scope,
                    AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
                )
            )
            db.execute(
                delete(AnaliseFatoRevision).where(
                    AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
                    AnaliseFatoRevision.escopo == scope,
                    AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
                )
            )
        else:
            assert effective_invalidated_from is not None
            context_rows_to_close = list(
                db.scalars(
                    select(AnaliseContextoRevision).where(
                        AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseContextoRevision.escopo == scope,
                        AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
                        AnaliseContextoRevision.known_from < effective_invalidated_from,
                        or_(
                            AnaliseContextoRevision.known_to.is_(None),
                            AnaliseContextoRevision.known_to > effective_invalidated_from,
                        ),
                    )
                ).all()
            )
            for context_row in context_rows_to_close:
                context_row.known_to = effective_invalidated_from
                closed_context_revisions += 1

            fact_rows_to_close = list(
                db.scalars(
                    select(AnaliseFatoRevision).where(
                        AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseFatoRevision.escopo == scope,
                        AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
                        AnaliseFatoRevision.known_from < effective_invalidated_from,
                        or_(
                            AnaliseFatoRevision.known_to.is_(None),
                            AnaliseFatoRevision.known_to > effective_invalidated_from,
                        ),
                    )
                ).all()
            )
            for fact_row in fact_rows_to_close:
                fact_row.known_to = effective_invalidated_from
                closed_fact_revisions += 1

            deleted_future_context_revisions = int(
                db.scalar(
                    select(func.count(AnaliseContextoRevision.id)).where(
                        AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseContextoRevision.escopo == scope,
                        AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
                        AnaliseContextoRevision.known_from >= effective_invalidated_from,
                    )
                )
                or 0
            )
            deleted_future_fact_revisions = int(
                db.scalar(
                    select(func.count(AnaliseFatoRevision.id)).where(
                        AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
                        AnaliseFatoRevision.escopo == scope,
                        AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
                        AnaliseFatoRevision.known_from >= effective_invalidated_from,
                    )
                )
                or 0
            )
            db.execute(
                delete(AnaliseContextoRevision).where(
                    AnaliseContextoRevision.codigo_cvm == companhia.codigo_cvm,
                    AnaliseContextoRevision.escopo == scope,
                    AnaliseContextoRevision.calculation_version == CALCULATION_VERSION,
                    AnaliseContextoRevision.known_from >= effective_invalidated_from,
                )
            )
            db.execute(
                delete(AnaliseFatoRevision).where(
                    AnaliseFatoRevision.codigo_cvm == companhia.codigo_cvm,
                    AnaliseFatoRevision.escopo == scope,
                    AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
                    AnaliseFatoRevision.known_from >= effective_invalidated_from,
                )
            )

        if context_revisions_payloads:
            db.execute(
                insert(AnaliseContextoRevision),
                [_row_contexto_revision_payload(execucao, companhia, scope, payload) for payload in context_revisions_payloads],
            )
        if fact_revisions_payloads:
            db.execute(
                insert(AnaliseFatoRevision),
                [_row_fato_revision_payload(execucao, companhia, scope, payload) for payload in fact_revisions_payloads],
            )

        execucao.status = "success"
        execucao.coverage_complete = True
        execucao.finished_at = datetime.now(UTC)
        execucao.updated_at = execucao.finished_at
        execucao.summary = {
            "mode": materialization_mode,
            "invalidated_from": effective_invalidated_from.isoformat() if effective_invalidated_from is not None else None,
            "knowledge_dates": len(all_knowledge_dates),
            "window_total_knowledge_dates": len(execution_knowledge_dates),
            "window_processed_knowledge_dates": len(execution_knowledge_dates),
            "context_revisions": len(context_revisions_payloads),
            "fact_revisions": len(fact_revisions_payloads),
            "inserted_context_revisions": len(context_revisions_payloads),
            "inserted_fact_revisions": len(fact_revisions_payloads),
            "closed_context_revisions": closed_context_revisions,
            "closed_fact_revisions": closed_fact_revisions,
            "deleted_future_context_revisions": deleted_future_context_revisions,
            "deleted_future_fact_revisions": deleted_future_fact_revisions,
            "progress": {
                "total_knowledge_dates": len(execution_knowledge_dates),
                "processed_knowledge_dates": len(execution_knowledge_dates),
                "current_known_from": execution_knowledge_dates[-1].isoformat() if execution_knowledge_dates else None,
                "progress_ratio": 1.0 if execution_knowledge_dates else None,
                "context_revisions": len(context_revisions_payloads),
                "fact_revisions": len(fact_revisions_payloads),
            },
        }
        db.commit()
        db.refresh(execucao)
        return execucao
    except Exception:
        execucao.status = "failed"
        execucao.coverage_complete = False
        execucao.finished_at = datetime.now(UTC)
        execucao.updated_at = execucao.finished_at
        execucao.summary = {
            **(execucao.summary or {}),
            "error": "materialization_failed",
        }
        db.commit()
        raise
