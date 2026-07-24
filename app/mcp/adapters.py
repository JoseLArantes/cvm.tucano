from collections.abc import Sequence
from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.mcp.registry import READ_ONLY_TOOL_NAMES
from app.mcp.security import validate_analyst_access
from app.mcp.serialization import limit_items, response_envelope, to_jsonable
from app.mcp.settings import McpSettings
from app.models.companhia import Companhia
from app.schemas.analise import AnaliseBasePeriodo, AnaliseEscopo, AnalisePeriodicidade
from app.services.analise import (
    listar_metricas,
    obter_brief,
    obter_coverage,
    obter_series,
    obter_series_diagnostico,
)
from app.services.companhias import (
    listar_companhias,
    obter_companhia_modelo_por_codigo_cvm,
)
from app.services.fre_diagnostics import diagnosticar_disponibilidade_datasets_fre


def _effective_include_raw(value: bool | None, settings: McpSettings) -> bool:
    return settings.include_raw_default if value is None else value


def _parse_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _parse_csv_list(value: str | Sequence[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = [item.strip() for item in value.split(",") if item.strip()]
    else:
        parsed = [str(item).strip() for item in value if str(item).strip()]
    return parsed or None


def _limit_horizonte(horizonte_anos: int | None, settings: McpSettings) -> int:
    if horizonte_anos is None or horizonte_anos <= 0:
        return settings.max_periods
    return min(horizonte_anos, settings.max_periods)


def _load_companhia_or_raise(db: Session, codigo_cvm: int) -> Companhia:
    companhia = obter_companhia_modelo_por_codigo_cvm(db, codigo_cvm)
    if companhia is None:
        raise ValueError(f"Companhia nao encontrada para codigo_cvm={codigo_cvm}.")
    return companhia


def healthcheck_adapter(*, settings: McpSettings, token: str | None = None) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    return response_envelope(
        tool="healthcheck",
        include_raw=False,
        data={
            "status": "ok",
            "profile": settings.profile,
            "transport": "stdio",
            "read_only": True,
            "tools": list(READ_ONLY_TOOL_NAMES),
            "limits": {
                "max_rows": settings.max_rows,
                "max_periods": settings.max_periods,
                "tool_timeout_seconds": settings.tool_timeout_seconds,
            },
        },
    )


def buscar_companhias_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    cnpj_companhia: str | None = None,
    codigo_cvm: int | None = None,
    nome: str | None = None,
    situacao_registro: str | None = None,
    ordenar: str | None = "ativa_nome",
    pagina: int = 1,
    tamanho_pagina: int | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    effective_size = min(tamanho_pagina or settings.max_rows, settings.max_rows)
    raw = listar_companhias(
        db,
        pagina=pagina,
        tamanho_pagina=effective_size,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        nome=nome,
        situacao_registro=situacao_registro,
        ordenar=ordenar,
    )
    companhias = [
        {
            "codigo_cvm": item.codigo_cvm,
            "cnpj_companhia": item.cnpj_companhia,
            "denominacao_social": item.denominacao_social,
            "denominacao_comercial": item.denominacao_comercial,
            "situacao_registro": item.situacao_registro,
            "setor_atividade": item.setor_atividade,
            "logo_url": item.logo_url,
        }
        for item in raw.dados
    ]
    return response_envelope(
        tool="buscar_companhias",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "filters": {
                "cnpj_companhia": cnpj_companhia,
                "codigo_cvm": codigo_cvm,
                "nome": nome,
                "situacao_registro": situacao_registro,
                "ordenar": ordenar,
            },
            "paginacao": to_jsonable(raw.paginacao),
            "companhias": companhias,
        },
        limits={"max_rows": settings.max_rows, "applied_tamanho_pagina": effective_size},
    )


def listar_metricas_analise_adapter(
    *,
    settings: McpSettings,
    token: str | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    raw = listar_metricas()
    metricas = [
        {
            "id": item.id,
            "nome": item.nome,
            "type": item.type,
            "unit": item.unit,
            "formula": item.formula,
            "disponibilidades": item.disponibilidades,
            "limitations": item.limitations,
        }
        for item in raw.metricas
    ]
    return response_envelope(
        tool="listar_metricas_analise",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "calculation_version": raw.calculation_version,
            "metricas": metricas,
        },
    )


def obter_coverage_companhia_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    codigo_cvm: int,
    escopo: AnaliseEscopo = "consolidated",
    periodicidade: AnalisePeriodicidade | None = "annual",
    base_periodo: AnaliseBasePeriodo | None = "fy",
    as_of: str | date | None = None,
    horizonte_anos: int | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    companhia = _load_companhia_or_raise(db, codigo_cvm)
    effective_horizon = _limit_horizonte(horizonte_anos, settings)
    raw = obter_coverage(
        db,
        companhia,
        scope=escopo,
        as_of=_parse_date(as_of),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        horizonte_anos=effective_horizon,
    )
    periodos, truncated = limit_items(raw.periodos, settings.max_periods)
    return response_envelope(
        tool="obter_coverage_companhia",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "companhia": to_jsonable(raw.companhia),
            "escopo": raw.escopo,
            "as_of": raw.as_of,
            "resolution": to_jsonable(raw.resolution),
            "periodos": periodos,
            "truncated": truncated,
        },
        limits={"max_periods": settings.max_periods, "applied_horizonte_anos": effective_horizon},
    )


def obter_diagnostico_series_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    codigo_cvm: int,
    metricas: str | Sequence[str] | None = None,
    periodicidade: AnalisePeriodicidade = "annual",
    base_periodo: AnaliseBasePeriodo = "fy",
    escopo: AnaliseEscopo = "consolidated",
    as_of: str | date | None = None,
    horizonte_anos: int | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    companhia = _load_companhia_or_raise(db, codigo_cvm)
    effective_horizon = _limit_horizonte(horizonte_anos, settings)
    raw = obter_series_diagnostico(
        db,
        companhia,
        metricas=_parse_csv_list(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=_parse_date(as_of),
        horizonte_anos=effective_horizon,
    )
    rejected, rejected_truncated = limit_items(raw.rejected_periods, settings.max_periods)
    return response_envelope(
        tool="obter_diagnostico_series",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "companhia": to_jsonable(raw.companhia),
            "calculation_version": raw.calculation_version,
            "periodicidade": raw.periodicidade,
            "base_periodo": raw.base_periodo,
            "escopo": raw.escopo,
            "horizonte_anos": raw.horizonte_anos,
            "resolution": to_jsonable(raw.resolution),
            "requested_metrics": raw.requested_metrics,
            "candidate_periods": raw.candidate_periods[: settings.max_periods],
            "returned_periods": raw.returned_periods[: settings.max_periods],
            "rejected_periods": rejected,
            "unavailable_reasons": to_jsonable(raw.unavailable_reasons[: settings.max_rows]),
            "issues": to_jsonable(raw.issues[: settings.max_rows]),
            "truncated": rejected_truncated,
        },
        limits={"max_periods": settings.max_periods, "max_rows": settings.max_rows, "applied_horizonte_anos": effective_horizon},
    )


def obter_series_temporais_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    codigo_cvm: int,
    metricas: str | Sequence[str] | None = None,
    periodicidade: AnalisePeriodicidade = "annual",
    base_periodo: AnaliseBasePeriodo = "fy",
    escopo: AnaliseEscopo = "consolidated",
    as_of: str | date | None = None,
    horizonte_anos: int | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    companhia = _load_companhia_or_raise(db, codigo_cvm)
    effective_horizon = _limit_horizonte(horizonte_anos, settings)
    raw = obter_series(
        db,
        companhia,
        metricas=_parse_csv_list(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=_parse_date(as_of),
        horizonte_anos=effective_horizon,
    )
    observacoes, observations_truncated = limit_items(raw.observacoes, settings.max_rows)
    indisponibilidades, unavailable_truncated = limit_items(raw.indisponibilidades, settings.max_rows)
    return response_envelope(
        tool="obter_series_temporais",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "companhia": to_jsonable(raw.companhia),
            "calculation_version": raw.calculation_version,
            "periodicidade": raw.periodicidade,
            "base_periodo": raw.base_periodo,
            "escopo": raw.escopo,
            "horizonte_anos": raw.horizonte_anos,
            "metricas": raw.metricas,
            "resolution": to_jsonable(raw.resolution),
            "observacoes": observacoes,
            "indisponibilidades": indisponibilidades,
            "issues": to_jsonable(raw.issues[: settings.max_rows]),
            "truncated": observations_truncated or unavailable_truncated,
        },
        limits={"max_rows": settings.max_rows, "max_periods": settings.max_periods, "applied_horizonte_anos": effective_horizon},
    )


def obter_brief_companhia_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    codigo_cvm: int,
    escopo: AnaliseEscopo = "consolidated",
    as_of: str | date | None = None,
    metricas: str | Sequence[str] | None = None,
    incluir_eventos: bool = True,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    companhia = _load_companhia_or_raise(db, codigo_cvm)
    raw = obter_brief(
        db,
        companhia,
        scope=escopo,
        as_of=_parse_date(as_of),
        metricas=_parse_csv_list(metricas),
        incluir_eventos=incluir_eventos,
    )
    metricas_compactas, metricas_truncated = limit_items(raw.metricas, settings.max_rows)
    eventos, eventos_truncated = limit_items(raw.eventos, settings.max_rows)
    return response_envelope(
        tool="obter_brief_companhia",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "companhia": to_jsonable(raw.companhia),
            "calculation_version": raw.calculation_version,
            "as_of": raw.as_of,
            "escopo": raw.escopo,
            "periodos_referencia": to_jsonable(raw.periodos_referencia),
            "metricas": metricas_compactas,
            "comparacoes": to_jsonable(raw.comparacoes[: settings.max_rows]),
            "sinais": to_jsonable(raw.sinais[: settings.max_rows]),
            "qualidade": to_jsonable(raw.qualidade),
            "eventos": eventos,
            "issues": to_jsonable(raw.issues[: settings.max_rows]),
            "truncated": metricas_truncated or eventos_truncated,
        },
        limits={"max_rows": settings.max_rows},
    )


def obter_disponibilidade_fre_dataset_adapter(
    db: Session,
    *,
    settings: McpSettings,
    token: str | None = None,
    ano: int | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    datasets: str | Sequence[str] | None = None,
    include_raw: bool | None = None,
) -> dict[str, Any]:
    validate_analyst_access(settings, token)
    raw = diagnosticar_disponibilidade_datasets_fre(
        db,
        ano=ano,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        dataset=_parse_csv_list(datasets),
    )
    dados, truncated = limit_items(raw.dados, settings.max_rows)
    return response_envelope(
        tool="obter_disponibilidade_fre_dataset",
        include_raw=_effective_include_raw(include_raw, settings),
        raw=raw,
        data={
            "resumo": to_jsonable(raw.resumo),
            "dados": dados,
            "truncated": truncated,
        },
        limits={"max_rows": settings.max_rows},
    )


def normalize_escopo(value: str) -> AnaliseEscopo:
    if value not in {"consolidated", "individual"}:
        raise ValueError("escopo deve ser 'consolidated' ou 'individual'.")
    return cast(AnaliseEscopo, value)


def normalize_periodicidade(value: str) -> AnalisePeriodicidade:
    if value not in {"annual", "quarterly"}:
        raise ValueError("periodicidade deve ser 'annual' ou 'quarterly'.")
    return cast(AnalisePeriodicidade, value)


def normalize_base_periodo(value: str) -> AnaliseBasePeriodo:
    if value not in {"fy", "quarter", "ytd"}:
        raise ValueError("base_periodo deve ser 'fy', 'quarter' ou 'ytd'.")
    return cast(AnaliseBasePeriodo, value)
