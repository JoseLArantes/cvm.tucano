# mypy: ignore-errors
from typing import Any

from app.mcp.adapters import (
    buscar_companhias_adapter,
    healthcheck_adapter,
    listar_metricas_analise_adapter,
    normalize_base_periodo,
    normalize_escopo,
    normalize_periodicidade,
    obter_brief_companhia_adapter,
    obter_coverage_companhia_adapter,
    obter_diagnostico_series_adapter,
    obter_disponibilidade_fre_dataset_adapter,
    obter_series_temporais_adapter,
)
from app.mcp.db import mcp_db_session
from app.mcp.serialization import error_response
from app.mcp.settings import McpSettings, get_mcp_settings


def _with_db(handler: Any, tool: str, **kwargs: Any) -> dict[str, Any]:
    try:
        with mcp_db_session() as db:
            return handler(db, **kwargs)
    except Exception as exc:
        return error_response(tool, exc)


def _without_db(handler: Any, tool: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return handler(**kwargs)
    except Exception as exc:
        return error_response(tool, exc)


def register_tools(server: Any, settings: McpSettings) -> None:
    @server.tool()
    def healthcheck(token: str | None = None) -> dict[str, Any]:
        """Verifica o servidor MCP analitico read-only e lista ferramentas disponiveis."""
        return _without_db(healthcheck_adapter, "healthcheck", settings=settings, token=token)

    @server.tool()
    def buscar_companhias(
        cnpj_companhia: str | None = None,
        codigo_cvm: int | None = None,
        nome: str | None = None,
        situacao_registro: str | None = None,
        ordenar: str | None = "ativa_nome",
        pagina: int = 1,
        tamanho_pagina: int | None = None,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Busca companhias abertas usando os mesmos filtros do service de companhias."""
        return _with_db(
            buscar_companhias_adapter,
            "buscar_companhias",
            settings=settings,
            token=token,
            cnpj_companhia=cnpj_companhia,
            codigo_cvm=codigo_cvm,
            nome=nome,
            situacao_registro=situacao_registro,
            ordenar=ordenar,
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
            include_raw=include_raw,
        )

    @server.tool()
    def listar_metricas_analise(
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Lista o catalogo canonico de metricas analiticas."""
        return _without_db(
            listar_metricas_analise_adapter,
            "listar_metricas_analise",
            settings=settings,
            token=token,
            include_raw=include_raw,
        )

    @server.tool()
    def obter_coverage_companhia(
        codigo_cvm: int,
        escopo: str = "consolidated",
        periodicidade: str | None = "annual",
        base_periodo: str | None = "fy",
        as_of: str | None = None,
        horizonte_anos: int | None = None,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Retorna matriz compacta de cobertura canonica por periodo da companhia."""
        try:
            normalized_periodicidade = normalize_periodicidade(periodicidade) if periodicidade is not None else None
            normalized_base_periodo = normalize_base_periodo(base_periodo) if base_periodo is not None else None
            normalized_escopo = normalize_escopo(escopo)
        except Exception as exc:
            return error_response("obter_coverage_companhia", exc)
        return _with_db(
            obter_coverage_companhia_adapter,
            "obter_coverage_companhia",
            settings=settings,
            token=token,
            codigo_cvm=codigo_cvm,
            escopo=normalized_escopo,
            periodicidade=normalized_periodicidade,
            base_periodo=normalized_base_periodo,
            as_of=as_of,
            horizonte_anos=horizonte_anos,
            include_raw=include_raw,
        )

    @server.tool()
    def obter_diagnostico_series(
        codigo_cvm: int,
        metricas: str | None = None,
        periodicidade: str = "annual",
        base_periodo: str = "fy",
        escopo: str = "consolidated",
        as_of: str | None = None,
        horizonte_anos: int | None = None,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Explica lacunas de series por periodo, metrica, camada e remediacao."""
        try:
            normalized_periodicidade = normalize_periodicidade(periodicidade)
            normalized_base_periodo = normalize_base_periodo(base_periodo)
            normalized_escopo = normalize_escopo(escopo)
        except Exception as exc:
            return error_response("obter_diagnostico_series", exc)
        return _with_db(
            obter_diagnostico_series_adapter,
            "obter_diagnostico_series",
            settings=settings,
            token=token,
            codigo_cvm=codigo_cvm,
            metricas=metricas,
            periodicidade=normalized_periodicidade,
            base_periodo=normalized_base_periodo,
            escopo=normalized_escopo,
            as_of=as_of,
            horizonte_anos=horizonte_anos,
            include_raw=include_raw,
        )

    @server.tool()
    def obter_series_temporais(
        codigo_cvm: int,
        metricas: str | None = None,
        periodicidade: str = "annual",
        base_periodo: str = "fy",
        escopo: str = "consolidated",
        as_of: str | None = None,
        horizonte_anos: int | None = None,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Retorna observacoes canonicas de series temporais ja compactadas para LLM."""
        try:
            normalized_periodicidade = normalize_periodicidade(periodicidade)
            normalized_base_periodo = normalize_base_periodo(base_periodo)
            normalized_escopo = normalize_escopo(escopo)
        except Exception as exc:
            return error_response("obter_series_temporais", exc)
        return _with_db(
            obter_series_temporais_adapter,
            "obter_series_temporais",
            settings=settings,
            token=token,
            codigo_cvm=codigo_cvm,
            metricas=metricas,
            periodicidade=normalized_periodicidade,
            base_periodo=normalized_base_periodo,
            escopo=normalized_escopo,
            as_of=as_of,
            horizonte_anos=horizonte_anos,
            include_raw=include_raw,
        )

    @server.tool()
    def obter_brief_companhia(
        codigo_cvm: int,
        escopo: str = "consolidated",
        as_of: str | None = None,
        metricas: str | None = None,
        incluir_eventos: bool = True,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Retorna brief financeiro deterministico da companhia."""
        try:
            normalized_escopo = normalize_escopo(escopo)
        except Exception as exc:
            return error_response("obter_brief_companhia", exc)
        return _with_db(
            obter_brief_companhia_adapter,
            "obter_brief_companhia",
            settings=settings,
            token=token,
            codigo_cvm=codigo_cvm,
            escopo=normalized_escopo,
            as_of=as_of,
            metricas=metricas,
            incluir_eventos=incluir_eventos,
            include_raw=include_raw,
        )

    @server.tool()
    def obter_disponibilidade_fre_dataset(
        ano: int | None = None,
        ano_inicio: int | None = None,
        ano_fim: int | None = None,
        datasets: str | None = None,
        include_raw: bool | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Diagnostica disponibilidade de datasets FRE com os mesmos codigos do REST."""
        return _with_db(
            obter_disponibilidade_fre_dataset_adapter,
            "obter_disponibilidade_fre_dataset",
            settings=settings,
            token=token,
            ano=ano,
            ano_inicio=ano_inicio,
            ano_fim=ano_fim,
            datasets=datasets,
            include_raw=include_raw,
        )


def create_server(settings: McpSettings | None = None, *, http: bool = False) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Dependencia MCP ausente. Instale as dependencias do projeto antes de iniciar o servidor.") from exc

    resolved_settings = settings or get_mcp_settings()
    if http:
        server = FastMCP(
            "Tucano CVM MCP Analitico Read-Only",
            streamable_http_path="/",
            stateless_http=True,
        )
    else:
        server = FastMCP("Tucano CVM MCP Analitico Read-Only")
    register_tools(server, resolved_settings)
    return server


def run_stdio(settings: McpSettings | None = None) -> None:
    server = create_server(settings)
    server.run(transport="stdio")
