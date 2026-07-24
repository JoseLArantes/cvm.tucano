from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.cache import build_cache_key, cache
from app.core.config import get_settings
from app.models.companhia import Companhia
from app.schemas.analise import (
    AnaliseBasePeriodo,
    AnaliseBriefResposta,
    AnaliseComparacoesResposta,
    AnaliseCoverageResposta,
    AnaliseEscopo,
    AnaliseEventosResposta,
    AnaliseGovernancaResposta,
    AnaliseManifestoResposta,
    AnalisePeriodicidade,
    AnalisePessoasResposta,
    AnaliseQualidadeResposta,
    AnaliseRestatementsResposta,
    AnaliseSeriesDiagnosticoResposta,
    AnaliseSeriesResposta,
    AnaliseSinaisResposta,
)
from app.services.analise import (
    obter_brief,
    obter_comparacoes,
    obter_coverage,
    obter_eventos,
    obter_governanca,
    obter_manifesto,
    obter_pessoas,
    obter_qualidade,
    obter_restatements,
    obter_series,
    obter_series_diagnostico,
    obter_sinais,
)

router = APIRouter(prefix="/public/analise")

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

_RESPOSTAS_PUBLICAS: dict[int | str, dict[str, Any]] = {
    **_RESPOSTAS_PADRAO,
    403: {
        "description": "Acesso não autorizado para esta companhia pública.",
        "content": {"application/json": {"example": {"detail": "Acesso nao autorizado para esta companhia."}}},
    },
}


def _obter_companhia_por_codigo_cvm_or_404(db: DbSession, codigo_cvm: int) -> Companhia:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return companhia


def _parse_metricas(metricas: str | None) -> list[str] | None:
    if metricas is None:
        return None
    return [m.strip() for m in metricas.split(",") if m.strip()]


def verificar_companhia_publica(codigo_cvm: int) -> None:
    settings = get_settings()
    if codigo_cvm not in settings.public_companies_list:
        raise HTTPException(
            status_code=403,
            detail="Acesso nao autorizado para esta companhia."
        )


@router.get(
    "/companhias/{codigo_cvm}",
    response_model=AnaliseManifestoResposta,
    summary="Manifesto Analitico da Companhia (Publico)",
    description="Retorna contexto padrão, períodos disponíveis, qualidade e links para os blocos analíticos da companhia.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseManifestoPublico",
)
def obter_analise_manifesto_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {"escopo": escopo, "as_of": as_of}
    key = build_cache_key("manifesto", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_manifesto(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)
    
    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/coverage",
    response_model=AnaliseCoverageResposta,
    summary="Matriz de Cobertura Analitica da Companhia (Publico)",
    description="Retorna uma matriz autoritativa por período que cruza dado bruto promovido e execuções de materialização.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseCoveragePublico",
)
def obter_analise_coverage_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    periodicidade: Annotated[AnalisePeriodicidade | None, Query(description="Periodicidade opcional: `annual` ou `quarterly`.")] = None,
    base_periodo: Annotated[AnaliseBasePeriodo | None, Query(description="Base temporal opcional: `fy`, `quarter` ou `ytd`.")] = None,
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int | None, Query(description="Horizonte anual máximo.", ge=1, le=20)] = None,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "escopo": escopo,
        "periodicidade": periodicidade,
        "base_periodo": base_periodo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("coverage", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_coverage(
        db,
        companhia,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        horizonte_anos=horizonte_anos,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/series",
    response_model=AnaliseSeriesResposta,
    summary="Series Analiticas Normalizadas (Publico)",
    description="Retorna observações analíticas normalizadas por métrica, período, unidade, formulário, versão e evidência.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseSeriesPublico",
)
def obter_analise_series_publico(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo.", ge=1, le=20)] = 5,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "metricas": metricas,
        "periodicidade": periodicidade,
        "base_periodo": base_periodo,
        "escopo": escopo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("series", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_series(
        db,
        companhia,
        metricas=_parse_metricas(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        horizonte_anos=horizonte_anos,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/series/diagnostico",
    response_model=AnaliseSeriesDiagnosticoResposta,
    summary="Diagnostico de Lacunas das Series Analiticas (Publico)",
    description="Retorna candidatos, períodos retornados, rejeitados, contas ausentes para explicar lacunas nas séries.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseSeriesDiagnosticoPublico",
)
def obter_analise_series_diagnostico_publico(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo.", ge=1, le=20)] = 5,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "metricas": metricas,
        "periodicidade": periodicidade,
        "base_periodo": base_periodo,
        "escopo": escopo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("diagnostico", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_series_diagnostico(
        db,
        companhia,
        metricas=_parse_metricas(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        horizonte_anos=horizonte_anos,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/comparacoes",
    response_model=AnaliseComparacoesResposta,
    summary="Comparacoes Analiticas Prontas (Publico)",
    description="Retorna YoY, QoQ, CAGR, análise vertical e base 100.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseComparacoesPublico",
)
def obter_analise_comparacoes_publico(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV de métricas estáveis.")] = None,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade: `annual` ou `quarterly`.")] = "annual",
    base_periodo: Annotated[AnaliseBasePeriodo, Query(description="Base temporal: `fy`, `quarter` ou `ytd`.")] = "fy",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional em ISO 8601 (`AAAA-MM-DD`).")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo.", ge=1, le=20)] = 5,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "metricas": metricas,
        "periodicidade": periodicidade,
        "base_periodo": base_periodo,
        "escopo": escopo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("comparacoes", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_comparacoes(
        db,
        companhia,
        metricas=_parse_metricas(metricas),
        periodicidade=periodicidade,
        base_periodo=base_periodo,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        horizonte_anos=horizonte_anos,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/qualidade",
    response_model=AnaliseQualidadeResposta,
    summary="Qualidade Analitica (Publico)",
    description="Executa verificações de completude, comparabilidade, consistência no contexto analítico atual.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseQualidadePublico",
)
def obter_analise_qualidade_publico(
    codigo_cvm: int,
    db: DbSession,
    periodicidade: Annotated[AnalisePeriodicidade, Query(description="Periodicidade do diagnóstico.")] = "annual",
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional.")] = None,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "periodicidade": periodicidade,
        "escopo": escopo,
        "as_of": as_of,
    }
    key = build_cache_key("qualidade", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_qualidade(
        db,
        companhia,
        periodicidade=periodicidade,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/sinais",
    response_model=AnaliseSinaisResposta,
    summary="Sinais Deterministicos (Publico)",
    description="Avalia regras determinísticas do backend e retorna threshold, observado e evidências.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseSinaisPublico",
)
def obter_analise_sinais_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional.")] = None,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "escopo": escopo,
        "as_of": as_of,
    }
    key = build_cache_key("sinais", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_sinais(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/eventos",
    response_model=AnaliseEventosResposta,
    summary="Timeline de Eventos Analiticos (Publico)",
    description="Retorna timeline unificada de IPE, reapresentações financeiras, alterações de capital.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseEventosPublico",
)
def obter_analise_eventos_publico(
    codigo_cvm: int,
    db: DbSession,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    key = build_cache_key("eventos", codigo_cvm, {})

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_eventos(db, companhia)

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/governanca",
    response_model=AnaliseGovernancaResposta,
    summary="Governanca Analitica Temporal (Publico)",
    description="Retorna observações temporais anuais de governança.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseGovernancaPublico",
)
def obter_analise_governanca_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional.")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo.", ge=1, le=20)] = 5,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "escopo": escopo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("governanca", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_governanca(db, companhia, as_of=date.fromisoformat(as_of) if as_of else None, horizonte_anos=horizonte_anos, scope=escopo)

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/pessoas",
    response_model=AnalisePessoasResposta,
    summary="Pessoas Analitico Temporal (Publico)",
    description="Retorna observações temporais anuais de pessoas e remuneração.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnalisePessoasPublico",
)
def obter_analise_pessoas_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional.")] = None,
    horizonte_anos: Annotated[int, Query(description="Horizonte anual máximo.", ge=1, le=20)] = 5,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "escopo": escopo,
        "as_of": as_of,
        "horizonte_anos": horizonte_anos,
    }
    key = build_cache_key("pessoas", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_pessoas(db, companhia, as_of=date.fromisoformat(as_of) if as_of else None, horizonte_anos=horizonte_anos, scope=escopo)

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/brief",
    response_model=AnaliseBriefResposta,
    summary="Brief Analitico da Companhia (Publico)",
    description="Retorna um pacote curado com trimestre atual, anterior, comparável anual e sinais.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseBriefPublico",
)
def obter_analise_brief_publico(
    codigo_cvm: int,
    db: DbSession,
    metricas: Annotated[str | None, Query(description="Lista CSV opcional de métricas.")] = None,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional.")] = None,
    incluir_eventos: Annotated[bool, Query(description="Indica se deve incluir eventos recentes.")] = True,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "metricas": metricas,
        "escopo": escopo,
        "as_of": as_of,
        "incluir_eventos": incluir_eventos,
    }
    key = build_cache_key("brief", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_brief(
        db,
        companhia,
        scope=escopo,
        as_of=date.fromisoformat(as_of) if as_of else None,
        metricas=_parse_metricas(metricas),
        incluir_eventos=incluir_eventos,
    )

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result


@router.get(
    "/companhias/{codigo_cvm}/restatements",
    response_model=AnaliseRestatementsResposta,
    summary="Historico de Reapresentacoes (Publico)",
    description="Compara versões consecutivas de DFP/ITR e informa as contas alteradas.",
    responses=_RESPOSTAS_PUBLICAS,
    operation_id="obterAnaliseRestatementsPublico",
)
def obter_analise_restatements_publico(
    codigo_cvm: int,
    db: DbSession,
    escopo: Annotated[AnaliseEscopo, Query(description="Escopo societário: `consolidated` ou `individual`.")] = "consolidated",
    as_of: Annotated[str | None, Query(description="Data de corte informacional in ISO 8601.")] = None,
) -> Any:
    verificar_companhia_publica(codigo_cvm)
    params = {
        "escopo": escopo,
        "as_of": as_of,
    }
    key = build_cache_key("restatements", codigo_cvm, params)

    cached = cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    companhia = _obter_companhia_por_codigo_cvm_or_404(db, codigo_cvm)
    result = obter_restatements(db, companhia, scope=escopo, as_of=date.fromisoformat(as_of) if as_of else None)

    settings = get_settings()
    cache.set(key, result.model_dump_json(), settings.public_cache_ttl_seconds)
    return result
