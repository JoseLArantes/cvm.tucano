import subprocess
import sys
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.mcp.adapters import (
    buscar_companhias_adapter,
    healthcheck_adapter,
    listar_metricas_analise_adapter,
    obter_coverage_companhia_adapter,
    obter_diagnostico_series_adapter,
    obter_disponibilidade_fre_dataset_adapter,
    obter_series_temporais_adapter,
)
from app.mcp.registry import READ_ONLY_TOOL_NAMES
from app.mcp.security import McpAuthError, mask_secrets, validate_analyst_access, validate_http_bearer
from app.mcp.server import create_server
from app.mcp.settings import McpSettings
from app.models.companhia import Companhia


def _settings(**overrides: object) -> McpSettings:
    base: dict[str, object] = {
        "profile": "analyst",
        "token": "",
        "require_token": False,
        "max_rows": 5,
        "max_periods": 5,
        "tool_timeout_seconds": 30,
        "include_raw_default": False,
    }
    base.update(overrides)
    return McpSettings.model_validate(base)


def _companhia(codigo_cvm: int = 9512) -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="33000167000101",
        codigo_cvm=codigo_cvm,
        denominacao_social="PETROLEO BRASILEIRO S.A. PETROBRAS",
        denominacao_comercial="PETROBRAS",
        situacao_registro="ATIVO",
        data_registro=date(1977, 7, 20),
        data_constituicao=date(1953, 10, 3),
        data_cancelamento=None,
        motivo_cancelamento=None,
        data_inicio_situacao=date(1977, 7, 20),
        setor_atividade="Petroleo",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(1977, 7, 20),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(1977, 7, 20),
        controle_acionario="ESTATAL",
        endereco={"municipio": "Rio de Janeiro"},
        responsavel={"nome_responsavel": "DRI"},
        auditor="Auditoria X",
        cnpj_auditor="10830108000165",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=1,
        hash_origem=f"companhia-{codigo_cvm}",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def test_mcp_healthcheck_lista_apenas_tools_read_only() -> None:
    payload = healthcheck_adapter(settings=_settings())

    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert payload["tools"] == list(READ_ONLY_TOOL_NAMES)
    assert not any("repair" in tool or "sync" in tool or "cancel" in tool for tool in payload["tools"])


def test_mcp_rejeita_perfil_nao_analyst_e_token_rest() -> None:
    with pytest.raises(McpAuthError):
        validate_analyst_access(_settings(profile="operator"))

    with pytest.raises(McpAuthError):
        validate_analyst_access(_settings(token="mcp-token", require_token=True), token="token-rest")


def test_mcp_http_bearer_usa_token_proprio() -> None:
    settings = _settings(token="mcp-token", http_enabled=True, http_require_bearer=True)

    validate_http_bearer(settings, "Bearer mcp-token")
    with pytest.raises(McpAuthError):
        validate_http_bearer(settings, "Bearer token-rest")


def test_mcp_http_server_usa_path_raiz_para_mount_em_mcp() -> None:
    server = create_server(_settings(), http=True)
    app = server.streamable_http_app()

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/" in route_paths
    assert "/mcp" not in route_paths


def test_mcp_http_server_configura_hosts_publicos_permitidos() -> None:
    settings = _settings(
        http_allowed_hosts="cvm.tucano.beakcloud.com,cvm.tucano.beakcloud.com:443",
        http_allowed_origins="https://cvm.tucano.beakcloud.com",
    )
    rejected_app = create_server(settings, http=True).streamable_http_app()
    accepted_app = create_server(settings, http=True).streamable_http_app()

    with TestClient(rejected_app, base_url="http://host-nao-autorizado") as client:
        rejected = client.post("/", json={"jsonrpc": "2.0"}, headers={"Accept": "application/json"})
    with TestClient(accepted_app, base_url="http://cvm.tucano.beakcloud.com") as client:
        accepted = client.post("/", json={"jsonrpc": "2.0"}, headers={"Accept": "application/json"})

    assert rejected.status_code == 421
    assert accepted.status_code != 421


def test_mcp_mascara_segredos_em_payloads() -> None:
    payload = mask_secrets(
        {
            "DATABASE_URL": "postgresql+psycopg://user:password@db:5432/cvm",
            "nested": {"token": "1234567890abcdef1234567890abcdef"},
        }
    )

    assert payload["DATABASE_URL"] == "postgresql+psycopg://***:***@db:5432/cvm"
    assert payload["nested"]["token"].startswith("1234...")


def test_mcp_buscar_companhias_reusa_service_compartilhado(db_session: Session) -> None:
    db_session.add(_companhia())
    db_session.commit()

    payload = buscar_companhias_adapter(
        db_session,
        settings=_settings(max_rows=1),
        nome="PETROBRAS",
        tamanho_pagina=100,
    )

    assert payload["ok"] is True
    assert payload["limits"]["applied_tamanho_pagina"] == 1
    assert payload["paginacao"]["total"] == 1
    assert payload["companhias"][0]["codigo_cvm"] == 9512
    assert "raw" not in payload


def test_mcp_metricas_analise_usa_catalogo_canonico() -> None:
    payload = listar_metricas_analise_adapter(settings=_settings())

    metric_ids = {item["id"] for item in payload["metricas"]}
    assert payload["ok"] is True
    assert "receita_liquida" in metric_ids
    assert "lucro_liquido" in metric_ids


def test_mcp_series_diagnostico_e_coverage_preservam_mesmos_filtros(db_session: Session) -> None:
    db_session.add(_companhia())
    db_session.commit()
    settings = _settings(max_periods=3)
    coverage = obter_coverage_companhia_adapter(
        db_session,
        settings=settings,
        codigo_cvm=9512,
        escopo="consolidated",
        periodicidade="annual",
        base_periodo="fy",
        horizonte_anos=3,
    )
    diagnostico = obter_diagnostico_series_adapter(
        db_session,
        settings=settings,
        codigo_cvm=9512,
        metricas="receita_liquida,lucro_liquido",
        escopo="consolidated",
        periodicidade="annual",
        base_periodo="fy",
        horizonte_anos=3,
    )
    series = obter_series_temporais_adapter(
        db_session,
        settings=settings,
        codigo_cvm=9512,
        metricas="receita_liquida,lucro_liquido",
        escopo="consolidated",
        periodicidade="annual",
        base_periodo="fy",
        horizonte_anos=3,
    )

    assert coverage["escopo"] == diagnostico["escopo"] == series["escopo"] == "consolidated"
    assert diagnostico["periodicidade"] == series["periodicidade"] == "annual"
    assert diagnostico["base_periodo"] == series["base_periodo"] == "fy"
    assert coverage["limits"]["applied_horizonte_anos"] == 3
    assert diagnostico["limits"]["applied_horizonte_anos"] == 3
    assert series["limits"]["applied_horizonte_anos"] == 3


def test_mcp_fre_disponibilidade_preserva_diagnostico_do_service(db_session: Session) -> None:
    payload = obter_disponibilidade_fre_dataset_adapter(
        db_session,
        settings=_settings(max_rows=2),
        ano=2025,
        datasets="auditores",
    )

    assert payload["ok"] is True
    assert payload["resumo"]["total"] == 1
    assert payload["dados"][0]["dataset"] == "auditores"
    assert "diagnosis_code" in payload["dados"][0]


def test_mcp_cli_help_e_smoke_test() -> None:
    help_result = subprocess.run(
        [sys.executable, "-m", "app.cli.mcp", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert "smoke-test" in help_result.stdout

    smoke_result = subprocess.run(
        [sys.executable, "-m", "app.cli.mcp", "smoke-test"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert smoke_result.returncode == 0
    assert '"status": "ok"' in smoke_result.stdout
    assert "healthcheck" in smoke_result.stdout
