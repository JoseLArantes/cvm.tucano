from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import AnyUrl, ValidationError

from app.core.config import Settings, get_settings
from app.radar.classifier import classify_text
from app.radar.models import RadarFeed, RadarFeedV2, RadarItem, RadarState
from app.radar.parser import (
    extract_published_at,
    parse_channel_html,
    parse_data_news_html,
    parse_news_detail_html,
    parse_news_sitemap,
    parse_norm_index_html,
    parse_rss_links,
)
from app.radar.service import run_radar_collection
from app.radar.storage import LocalRadarPublisher, R2RadarPublisher
from app.radar.tasks import run_radar_collection_task
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
  <main class="ckanext-pages-content">
    <h2>20/06/2026</h2>
    <p><a href="/pages/novidades#layout-dfp">Atualizacao de layout DFP</a></p>
    <p>20/06/2026: Inclusao de coluna em arquivo CSV do portal de dados. (Aviso publicado em 12/06/2026.)</p>
  </main>
</body></html>
"""

NORMAS_HTML = """
<html><body>
  <ul>
    <li><a href="/legislacao/resolucoes/resol999.html">Resolucao CVM 999</a> Publicada no DOU de 03.07.2026.</li>
    <li><a href="/audiencias_publicas/ap_sdm/2026/sdm0126.html">Audiencia publica 1</a> Publicada em 02/07/2026.</li>
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

NOTICIA_JSON_LD_HTML = """
<html><body>
  <script type="application/ld+json">
    {
      "@type": "NewsArticle",
      "headline": "CVM multa administradores",
      "datePublished": "2026-06-02T20:05:38-03:00",
      "dateModified": "2026-06-02T20:05:38-03:00"
    }
  </script>
  <span class="documentPublished">
    <span>Publicado em</span>
    <span class="value">02/06/2026 20h05</span>
  </span>
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
    settings.radar_cvm_requests_per_second = 10000
    return settings


def _radar_fixture(name: str) -> str:
    return (Path(__file__).parents[1] / "fixtures/radar" / name).read_text()


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
    assert published_at == datetime(2026, 7, 3, 20, 30, tzinfo=UTC)


def test_parser_extrai_publicado_em_de_html_do_govbr() -> None:
    html = """
    <span class="documentPublished">
      <span>Publicado em</span>
      <span class="value">10/06/2026 09h45</span>
    </span>
    """
    assert extract_published_at(html) == datetime(2026, 6, 10, 12, 45, tzinfo=UTC)


def test_parser_prefere_date_published_estruturado() -> None:
    assert extract_published_at(NOTICIA_JSON_LD_HTML) == datetime(2026, 6, 2, 23, 5, 38, tzinfo=UTC)


def test_parsers_extraem_snapshots_html() -> None:
    noticias = parse_channel_html("noticias", "https://www.gov.br/cvm/pt-br/assuntos/noticias", NOTICIAS_HTML)
    novidades = parse_channel_html("novidades_dados", "https://dados.cvm.gov.br/pages/novidades", NOVIDADES_HTML)
    normas = parse_channel_html("normas", "https://conteudo.cvm.gov.br/legislacao/resolucoes.html", NORMAS_HTML)
    assert [item.title for item in noticias] == ["CVM publica nova resolucao"]
    assert novidades[0].title == "Atualizacao de layout DFP"
    assert novidades[0].published_at == datetime(2026, 6, 12, tzinfo=UTC)
    assert len(normas) == 2
    assert {item.kind for item in normas} == {"norma", "consulta_publica"}


def test_parser_normas_prefere_data_de_publicacao_no_dou() -> None:
    normas = parse_channel_html("normas", "http://conteudo.cvm.gov.br/legislacao/resolucoes.html", NORMAS_DOU_HTML)
    assert normas[0].published_at == datetime(2026, 7, 3, tzinfo=UTC)


def test_sitemap_descarta_arquivo_anual_e_preserva_data_oficial() -> None:
    items = parse_news_sitemap(_radar_fixture("noticias_sitemap.xml"))

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 6, 26, 12, 18, tzinfo=UTC)
    assert "/noticias/2026" != str(items[0].url).removesuffix("/")


def test_detalhe_de_noticia_ignora_menu_e_rodape_no_conteudo_semantico() -> None:
    candidate = parse_news_sitemap(_radar_fixture("noticias_sitemap.xml"))[0]
    original = parse_news_detail_html(candidate, _radar_fixture("noticia_gafi.html"))
    changed_shell = parse_news_detail_html(
        candidate,
        _radar_fixture("noticia_gafi.html").replace("Alto-contraste", "Menu redesenhado").replace(
            "Conteúdo atualizado pelo menu em 23/07/2026",
            "Novo rodapé institucional em 24/07/2026",
        ),
    )

    assert original.raw_text == changed_shell.raw_text
    assert original.published_at == datetime(2026, 6, 26, 12, 18, tzinfo=UTC)


def test_novidades_dados_gera_blocos_distintos_na_mesma_url() -> None:
    items = parse_data_news_html(
        "https://dados.cvm.gov.br/pages/novidades",
        _radar_fixture("novidades_dados.html"),
    )

    assert len(items) == 2
    assert {item.url for item in items} == {"https://dados.cvm.gov.br/pages/novidades"}
    assert len({item.identity_key for item in items}) == 2
    assert items[0].published_at == datetime(2026, 6, 12, tzinfo=UTC)
    assert items[0].updated_at == datetime(2026, 6, 20, tzinfo=UTC)


def test_indice_e_rss_normativos_canonicalizam_documentos_individuais() -> None:
    items = parse_norm_index_html(
        "normas_resolucoes",
        "https://conteudo.cvm.gov.br/legislacao/resolucoes.html",
        _radar_fixture("resolucoes.html"),
    )
    rss_links = parse_rss_links(_radar_fixture("legislacao.xml"))

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 7, 3, tzinfo=UTC)
    assert rss_links == {"https://conteudo.cvm.gov.br/legislacao/resolucoes/resol245.html"}


def test_run_radar_collection_enriquece_noticia_com_data_da_pagina(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if url == "https://www.gov.br/cvm/pt-br/assuntos/noticias":
            return FakeResponse(NOTICIAS_HTML)
        return FakeResponse(NOTICIA_DETALHE_HTML)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    result = run_radar_collection(channels=["noticias"], settings=settings)

    assert result["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    assert feed.items[0].published_at == datetime(2026, 7, 3, 20, 30, tzinfo=UTC)


def test_run_radar_collection_corrige_noticia_antiga_sem_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    publisher = LocalRadarPublisher(base_dir=str(tmp_path), prefix="radar-cvm/", cache_control="public")
    now = datetime(2026, 7, 8, 23, 45, tzinfo=UTC)
    previous_feed = _feed().model_copy(
        update={
            "generated_at": now,
            "items": [
                _feed().items[0].model_copy(
                    update={
                        "id": "noticias:2026-07-08:noticia-antiga",
                        "title": "CVM multa administradores",
                        "url": AnyUrl("https://www.gov.br/cvm/pt-br/assuntos/noticias/2026/cvm-multa-administradores"),
                        "published_at": None,
                        "captured_at": now,
                    }
                )
            ],
        }
    )
    publisher.publish(
        feed=previous_feed,
        state=RadarState(),
        history_key="radar-cvm/history/2026/07/08/234500.json",
        latest_key="radar-cvm/latest.json",
        state_key="radar-cvm/state.json",
    )

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if url == "https://www.gov.br/cvm/pt-br/assuntos/noticias":
            return FakeResponse(NOTICIAS_HTML)
        if url == "https://www.gov.br/cvm/pt-br/assuntos/noticias/2026/cvm-multa-administradores":
            return FakeResponse(NOTICIA_JSON_LD_HTML)
        return FakeResponse(NOTICIA_DETALHE_HTML)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    result = run_radar_collection(channels=["noticias"], settings=settings)

    assert result["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    old_item = next(item for item in feed.items if item.title == "CVM multa administradores")
    assert old_item.published_at == datetime(2026, 6, 2, 23, 5, 38, tzinfo=UTC)
    assert old_item.id.startswith("noticias:")
    assert "2026-06-02" not in old_item.id


def test_run_radar_collection_coleta_normas_por_subcanais(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if "resolucoes" in url:
            return FakeResponse(NORMAS_DOU_HTML, url="http://conteudo.cvm.gov.br/legislacao/resolucoes.html")
        return FakeResponse("<html><body></body></html>", url=url)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    result = run_radar_collection(channels=["normas"], settings=settings)

    assert result["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    assert [item.title for item in feed.items] == ["Resolucao CVM 245"]
    assert feed.items[0].published_at == datetime(2026, 7, 3, tzinfo=UTC)


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

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    result = run_radar_collection(settings=settings)

    assert result["published"] is True
    latest_path = tmp_path / "radar-cvm/latest.json"
    state_path = tmp_path / "radar-cvm/v2/state.json"
    assert latest_path.exists()
    assert state_path.exists()
    assert (tmp_path / "radar-cvm/v2/latest.json").exists()
    feed = RadarFeed.model_validate_json(latest_path.read_bytes())
    assert feed.summary.total_items >= 4
    assert feed.summary.channels_failed == 0
    assert (tmp_path / "radar-cvm/latest.json.sha256").exists()


def test_run_radar_collection_preserva_snapshot_anterior_quando_canal_falha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("app.radar.service._http_get", lambda *_args, **_kwargs: FakeResponse(NOTICIAS_HTML))
    first = run_radar_collection(channels=["noticias"], settings=settings)
    assert first["published"] is True

    def failing_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise RuntimeError("fora do ar")

    monkeypatch.setattr("app.radar.service._http_get", failing_get)
    second = run_radar_collection(channels=["noticias"], settings=settings)

    assert second["published"] is True
    feed = RadarFeed.model_validate_json((tmp_path / "radar-cvm/latest.json").read_bytes())
    assert feed.summary.channels_failed == 1
    assert feed.items


def test_execucao_sem_mudanca_preserva_id_data_e_posicao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    sitemap = _radar_fixture("noticias_sitemap.xml")
    detail = _radar_fixture("noticia_gafi.html")
    instants = iter(
        [
            datetime(2026, 7, 23, 10, tzinfo=UTC),
            datetime(2026, 7, 23, 14, tzinfo=UTC),
        ]
    )

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if url.endswith("/sitemap.xml"):
            return FakeResponse(sitemap, url=url)
        if url.endswith("/assuntos/noticias"):
            return FakeResponse("<ul class='listagem-noticias-com-foto'></ul>", url=url)
        return FakeResponse(detail, url=url)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    monkeypatch.setattr("app.radar.service.utc_now", lambda: next(instants))
    first = run_radar_collection(channels=["noticias"], settings=settings)
    first_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())
    second = run_radar_collection(channels=["noticias"], settings=settings)
    second_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())

    assert first["items_new"] == 1
    assert second["items_new"] == 0
    assert second["items_changed"] == 0
    assert [item.id for item in second_feed.items] == [item.id for item in first_feed.items]
    assert second_feed.items[0].published_at == first_feed.items[0].published_at
    assert second_feed.items[0].first_seen_at == first_feed.items[0].first_seen_at
    assert second_feed.items[0].content_changed_at == first_feed.items[0].content_changed_at
    assert second_feed.items[0].last_seen_at > first_feed.items[0].last_seen_at


def test_mudanca_de_corpo_nao_promove_noticia_na_linha_do_tempo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    sitemap = _radar_fixture("noticias_sitemap.xml")
    detail = _radar_fixture("noticia_gafi.html")
    current_detail = {"html": detail}
    instants = iter(
        [
            datetime(2026, 7, 23, 10, tzinfo=UTC),
            datetime(2026, 7, 24, 10, tzinfo=UTC),
        ]
    )

    def fake_get(url: str, **_: Any) -> FakeResponse:
        if url.endswith("/sitemap.xml"):
            return FakeResponse(sitemap, url=url)
        if url.endswith("/assuntos/noticias"):
            return FakeResponse("<ul class='listagem-noticias-com-foto'></ul>", url=url)
        return FakeResponse(current_detail["html"], url=url)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    monkeypatch.setattr("app.radar.service.utc_now", lambda: next(instants))
    run_radar_collection(channels=["noticias"], settings=settings)
    first_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())
    current_detail["html"] = detail.replace(
        "O comunicado apresenta as jurisdições sob monitoramento.",
        "O comunicado apresenta uma lista revisada de jurisdições sob monitoramento.",
    )
    second = run_radar_collection(channels=["noticias"], settings=settings)
    second_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())

    assert second["items_changed"] == 1
    assert second_feed.items[0].id == first_feed.items[0].id
    assert second_feed.items[0].published_at == first_feed.items[0].published_at
    assert second_feed.items[0].first_seen_at == first_feed.items[0].first_seen_at
    assert second_feed.items[0].content_changed_at > first_feed.items[0].content_changed_at


def test_incremental_nao_substitui_hash_do_detalhe_por_hash_do_sitemap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    sitemap = _radar_fixture("noticias_sitemap.xml")
    detail = _radar_fixture("noticia_gafi.html").replace(
        '<p class="documentDescription">CVM divulga atualização do organismo internacional.</p>',
        "",
    )
    detail_calls = 0

    def fake_get(url: str, **_: Any) -> FakeResponse:
        nonlocal detail_calls
        if url.endswith("/sitemap.xml"):
            return FakeResponse(sitemap, url=url)
        if url.endswith("/assuntos/noticias"):
            return FakeResponse("<ul class='listagem-noticias-com-foto'></ul>", url=url)
        detail_calls += 1
        return FakeResponse(detail, url=url)

    monkeypatch.setattr("app.radar.service._http_get", fake_get)
    run_radar_collection(channels=["noticias"], mode="full", settings=settings)
    first_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())
    second = run_radar_collection(channels=["noticias"], mode="incremental", settings=settings)
    second_feed = RadarFeedV2.model_validate_json((tmp_path / "radar-cvm/v2/latest.json").read_bytes())

    assert detail_calls == 1
    assert second["items_changed"] == 0
    assert second_feed.items[0].content_hash == first_feed.items[0].content_hash
    assert second_feed.items[0].content_changed_at == first_feed.items[0].content_changed_at


def test_run_radar_collection_nao_publica_primeira_execucao_totalmente_falha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "app.radar.service._http_get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("x")),
    )

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
        "radar-cvm/state.json",
        "radar-cvm/latest.json.sha256",
        "radar-cvm/latest.json",
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
    assert schedule["radar-noticias-periodico"]["args"] == (["noticias"], "incremental")
    assert celery_app.conf.task_routes["app.radar.tasks.run_radar_collection_task"]["queue"] == settings.radar_cvm_queue_name


def test_celery_queues_possuem_exchange_e_routing_key_proprios() -> None:
    queues = {queue.name: queue for queue in celery_app.conf.task_queues}

    for queue_name, queue in queues.items():
        assert queue.exchange.name == queue_name
        assert queue.exchange.type == "direct"
        assert queue.routing_key == queue_name


def test_radar_task_nao_executa_sem_lock_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.radar.tasks.cache.acquire_lock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.radar.tasks.run_radar_collection",
        lambda **_kwargs: pytest.fail("a coleta não deve iniciar sem lock"),
    )

    result = run_radar_collection_task()

    assert result == {
        "status": "failed",
        "published": False,
        "reason": "collection_lock_unavailable",
    }


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
