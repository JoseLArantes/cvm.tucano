from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.radar.classifier import classify_text
from app.radar.models import RadarFeed, RadarItem, RadarState
from app.radar.parser import extract_published_at, parse_channel_html
from app.radar.service import run_radar_collection
from app.radar.storage import LocalRadarPublisher, R2RadarPublisher
from app.worker.celery_app import celery_app, construir_beat_schedule

NOTICIAS_HTML = """
<html><body>
  <article>
    <a href="/cvm/pt-br/assuntos/noticias/cvm-publica-resolucao">CVM publica nova resolucao</a>
    <p>08/07/2026 A norma altera regras do mercado de capitais.</p>
  </article>
</body></html>
"""

NOVIDADES_HTML = """
<html><body>
  <main>
    <a href="/pages/novidades#layout-dfp">Atualizacao de layout DFP</a>
    <p>20/06/2026: Inclusao de coluna em arquivo CSV do portal de dados. (Aviso publicado em 12/06/2026.)</p>
  </main>
</body></html>
"""

NORMAS_HTML = """
<html><body>
  <ul>
    <li><a href="/cvm/pt-br/assuntos/normas/resolucoes/resolucao-cvm-999">Resolucao CVM 999</a></li>
    <li><a href="/cvm/pt-br/assuntos/normas/deliberacoes/deliberacao-1">Deliberacao CVM 1</a></li>
    <li><a href="/cvm/pt-br/assuntos/normas/pareceres-de-orientacao/parecer-1">Parecer de orientacao 1</a></li>
    <li><a href="/cvm/pt-br/assuntos/normas/audiencias-publicas/audiencia-1">Audiencia publica 1</a></li>
  </ul>
</body></html>
"""

NOTICIA_DETALHE_HTML = """
<html><body>
  <main>
    <p>Publicado em 03/07/2026 17h30</p>
    <h1>CVM publica nova resolucao</h1>
  </main>
</body></html>
"""

NORMAS_DOU_HTML = """
<html><body>
  <ul>
    <li>
      <a href="/legislacao/resolucoes/resol245.html">Resolucao CVM 245</a>
      01/07/2026 (Publicada no DOU de 03.07.2026)
    </li>
  </ul>
</body></html>
"""


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        url: str | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    settings.radar_cvm_storage_backend = "local"
    settings.storage_dir = str(tmp_path)
    settings.radar_cvm_storage_prefix = "radar-cvm/"
    settings.radar_cvm_enabled = True
    settings.radar_cvm_queue_name = "celery"
    settings.radar_cvm_noticias_enabled = True
    settings.radar_cvm_novidades_dados_enabled = True
    settings.radar_cvm_normas_enabled = True
    return settings


def test_settings_radar_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_CVM_ENABLED", raising=False)
    monkeypatch.delenv("RADAR_CVM_QUEUE_NAME", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.radar_cvm_enabled is False
    assert settings.radar_cvm_storage_backend == "r2"
    assert settings.radar_cvm_queue_name == "celery"
    assert settings.radar_cvm_noticias_enabled is True


def test_radar_schema_rejeita_campos_extras() -> None:
    with pytest.raises(ValidationError):
        RadarItem.model_validate(
            {
                "id": "x",
                "channel": "noticias",
                "kind": "noticia",
                "title": "Titulo",
                "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias/x",
                "captured_at": datetime.now(UTC),
                "tags": [],
                "relevance": "desconhecida",
                "signals": [],
                "source_hash": "sha256:x",
                "extra": "nao permitido",
            }
        )


def test_classificacao_deterministica() -> None:
    tags, relevance, signals = classify_text("Nova resolucao altera layout de arquivo CSV")
    assert "normativa" in tags
    assert "layout" in tags
    assert "dados_abertos" in tags
    assert relevance == "alta"
    assert signals


def test_classificacao_resolucoes() -> None:
    tags, relevance, signals = classify_text("qualquer texto", title="CVM altera Resolução")
    assert "resolução" in tags
    assert relevance == "media"

    tags, relevance, signals = classify_text("texto com resolucao 193", title="CVM altera resolucao 50")
    assert "50" in tags
    assert "193" in tags

    tags, relevance, signals = classify_text("texto aleatorio", title="titulo aleatorio")
    assert relevance == "normal"


def test_parser_extrai_publicado_em_com_data_brasileira_e_hora() -> None:
    published_at = extract_published_at("Publicado em 03/07/2026 17h30")
    assert published_at == datetime(2026, 7, 3, 17, 30, tzinfo=UTC)


def test_parsers_extraem_snapshots_html() -> None:
    noticias = parse_channel_html("noticias", "https://www.gov.br/cvm/pt-br/assuntos/noticias", NOTICIAS_HTML)
    novidades = parse_channel_html("novidades_dados", "https://dados.cvm.gov.br/pages/novidades", NOVIDADES_HTML)
    normas = parse_channel_html("normas", "https://www.gov.br/cvm/pt-br/assuntos/normas", NORMAS_HTML)
    assert [item.title for item in noticias] == ["CVM publica nova resolucao"]
    assert novidades[0].title == "Atualizacao de layout DFP"
    assert novidades[0].published_at == datetime(2026, 6, 20, tzinfo=UTC)
    assert len(normas) == 4
    assert {item.kind for item in normas} == {"norma", "consulta_publica"}


def test_parser_normas_prefere_data_de_publicacao_no_dou() -> None:
    normas = parse_channel_html("normas", "http://conteudo.cvm.gov.br/legislacao/resolucoes.html", NORMAS_DOU_HTML)
    assert normas[0].published_at == datetime(2026, 7, 3, tzinfo=UTC)


def test_run_radar_collection_enriquece_noticia_com_data_da_pagina(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if url == "https://www.gov.br/cvm/pt-br/assuntos/noticias":
            return FakeResponse(NOTICIAS_HTML)
        return FakeResponse(NOTICIA_DETALHE_HTML)

    monkeypatch.setattr("app.radar.service.httpx.get", fake_get)
    result = run_radar_collection(channels=["noticias"], settings=settings)

    assert result["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    assert feed.items[0].published_at == datetime(2026, 7, 3, 17, 30, tzinfo=UTC)


def test_run_radar_collection_publica_feed_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    responses = {
        "noticias": FakeResponse(NOTICIAS_HTML, headers={"etag": "noticias-etag"}),
        "novidades": FakeResponse(NOVIDADES_HTML, headers={"last-modified": "Wed, 08 Jul 2026 10:00:00 GMT"}),
        "normas": FakeResponse(NORMAS_HTML),
    }

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if "noticias" in url:
            return responses["noticias"]
        if "novidades" in url:
            return responses["novidades"]
        return responses["normas"]

    monkeypatch.setattr("app.radar.service.httpx.get", fake_get)
    result = run_radar_collection(settings=settings)

    assert result["published"] is True
    latest_path = tmp_path / "radar-cvm/latest.json"
    state_path = tmp_path / "radar-cvm/state.json"
    assert latest_path.exists()
    assert state_path.exists()
    feed = RadarFeed.model_validate_json(latest_path.read_bytes())
    assert feed.summary.total_items >= 6
    assert feed.summary.channels_failed == 0
    assert (tmp_path / "radar-cvm/latest.json.sha256").exists()


def test_run_radar_collection_preserva_snapshot_anterior_quando_canal_falha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("app.radar.service.httpx.get", lambda *_args, **_kwargs: FakeResponse(NOTICIAS_HTML))
    first = run_radar_collection(channels=["noticias"], settings=settings)
    assert first["published"] is True

    def failing_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise RuntimeError("fora do ar")

    monkeypatch.setattr("app.radar.service.httpx.get", failing_get)
    second = run_radar_collection(channels=["noticias"], settings=settings)

    assert second["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    assert feed.summary.channels_failed == 1
    assert feed.items


def test_run_radar_collection_nao_publica_primeira_execucao_totalmente_falha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("app.radar.service.httpx.get", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("x")))

    result = run_radar_collection(channels=["noticias"], settings=settings)

    assert result["published"] is False
    assert not (tmp_path / "radar-cvm/latest.json").exists()


def test_local_publisher_escreve_history_latest_e_sha(tmp_path: Path) -> None:
    publisher = LocalRadarPublisher(base_dir=str(tmp_path), prefix="radar-cvm/", cache_control="public")
    feed = _feed()
    result = publisher.publish(
        feed=feed,
        state=RadarState(),
        history_key="radar-cvm/history/2026/07/08/010203.json",
        latest_key="radar-cvm/latest.json",
        state_key="radar-cvm/state.json",
    )
    assert result["checksum_sha256"]
    assert (tmp_path / "radar-cvm/history/2026/07/08/010203.json").exists()
    assert (tmp_path / "radar-cvm/latest.json").exists()
    assert (tmp_path / "radar-cvm/latest.json.sha256").exists()


def test_r2_publisher_usa_put_object_com_cache_control(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def put_object(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: FakeClient()))
    publisher = R2RadarPublisher(
        endpoint_url="https://example.r2.cloudflarestorage.com",
        bucket="bucket",
        access_key_id="key",
        secret_access_key="secret",
        region="auto",
        prefix="radar-cvm/",
        cache_control="public, max-age=300",
    )
    publisher.publish(
        feed=_feed(),
        state=RadarState(),
        history_key="radar-cvm/history/2026/07/08/010203.json",
        latest_key="radar-cvm/latest.json",
        state_key="radar-cvm/state.json",
    )

    assert [call["Key"] for call in calls] == [
        "radar-cvm/history/2026/07/08/010203.json",
        "radar-cvm/latest.json",
        "radar-cvm/latest.json.sha256",
        "radar-cvm/state.json",
    ]
    assert all(call["CacheControl"] == "public, max-age=300" for call in calls)
    assert calls[0]["ContentType"] == "application/json; charset=utf-8"


def test_radar_beat_schedule_condicional(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "radar_cvm_enabled", False)
    schedule = construir_beat_schedule()
    assert "radar-noticias-periodico" not in schedule

    monkeypatch.setattr(settings, "radar_cvm_enabled", True)
    schedule = construir_beat_schedule()
    assert schedule["radar-noticias-periodico"]["task"] == "app.radar.tasks.run_radar_collection_task"
    assert schedule["radar-noticias-periodico"]["args"] == (["noticias"],)
    assert celery_app.conf.task_routes["app.radar.tasks.run_radar_collection_task"]["queue"] == settings.radar_cvm_queue_name


def _feed() -> RadarFeed:
    now = datetime.now(UTC)
    return RadarFeed.model_validate(
        {
            "schema_version": "1.0",
            "generated_at": now,
            "window": {"days": 90, "started_at": now - timedelta(days=90), "ended_at": now},
            "summary": {"total_items": 1, "channels_scanned": 1, "channels_failed": 0, "checksum_sha256": "x"},
            "channels": [
                {
                    "key": "noticias",
                    "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias",
                    "status": "success",
                    "last_success_at": now,
                    "items_count": 1,
                    "error": None,
                }
            ],
            "items": [
                {
                    "id": "noticias:2026-07-08:x",
                    "channel": "noticias",
                    "kind": "noticia",
                    "title": "Titulo",
                    "summary": None,
                    "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias/x",
                    "published_at": now,
                    "captured_at": now,
                    "tags": [],
                    "relevance": "desconhecida",
                    "signals": [],
                    "source_hash": "sha256:x",
                }
            ],
        }
    )
