from __future__ import annotations

from dataclasses import dataclass

from app.radar.models import RadarChannelKey, RadarSourceRole, RadarSourceType


@dataclass(frozen=True)
class RadarChannelConfig:
    key: RadarChannelKey
    url: str
    enabled_attr: str
    kind_hint: str


@dataclass(frozen=True)
class RadarSourceConfig:
    id: str
    channel: RadarChannelKey
    title: str
    url: str
    source_type: RadarSourceType
    role: RadarSourceRole


CHANNELS: tuple[RadarChannelConfig, ...] = (
    RadarChannelConfig(
        key="noticias",
        url="https://www.gov.br/cvm/pt-br/assuntos/noticias",
        enabled_attr="radar_cvm_noticias_enabled",
        kind_hint="noticia",
    ),
    RadarChannelConfig(
        key="novidades_dados",
        url="https://dados.cvm.gov.br/pages/novidades",
        enabled_attr="radar_cvm_novidades_dados_enabled",
        kind_hint="novidade_dados",
    ),
    RadarChannelConfig(
        key="normas",
        url="https://www.gov.br/cvm/pt-br/assuntos/normas",
        enabled_attr="radar_cvm_normas_enabled",
        kind_hint="norma",
    ),
)

NEWS_SITEMAP_URL = "https://www.gov.br/cvm/sitemap.xml"
NEWS_LISTING_URL = "https://www.gov.br/cvm/pt-br/assuntos/noticias"
DATA_NEWS_URL = "https://dados.cvm.gov.br/pages/novidades"
LEGISLATION_RSS_URL = "https://conteudo.cvm.gov.br/feed/legislacao.xml"
HEARINGS_RSS_URL = "https://conteudo.cvm.gov.br/feed/audiencias.xml"

NORMAS_SUBCHANNEL_URLS: tuple[str, ...] = (
    "https://conteudo.cvm.gov.br/legislacao/resolucoes.html",
    "https://conteudo.cvm.gov.br/legislacao/deliberacoes.html",
    "https://conteudo.cvm.gov.br/legislacao/pareceres-orientacao.html",
    "https://conteudo.cvm.gov.br/audiencias_publicas/index.html",
)

SOURCES: tuple[RadarSourceConfig, ...] = (
    RadarSourceConfig(
        id="noticias_sitemap",
        channel="noticias",
        title="Sitemap de notícias da CVM",
        url=NEWS_SITEMAP_URL,
        source_type="sitemap",
        role="primary",
    ),
    RadarSourceConfig(
        id="noticias_listagem",
        channel="noticias",
        title="Últimas notícias da CVM",
        url=NEWS_LISTING_URL,
        source_type="index",
        role="fallback",
    ),
    RadarSourceConfig(
        id="novidades_dados",
        channel="novidades_dados",
        title="Novidades do Portal de Dados Abertos CVM",
        url=DATA_NEWS_URL,
        source_type="mutable_page",
        role="primary",
    ),
    RadarSourceConfig(
        id="normas_resolucoes",
        channel="normas",
        title="Resoluções CVM",
        url=NORMAS_SUBCHANNEL_URLS[0],
        source_type="index",
        role="primary",
    ),
    RadarSourceConfig(
        id="normas_deliberacoes",
        channel="normas",
        title="Deliberações CVM",
        url=NORMAS_SUBCHANNEL_URLS[1],
        source_type="index",
        role="primary",
    ),
    RadarSourceConfig(
        id="normas_pareceres",
        channel="normas",
        title="Pareceres de Orientação CVM",
        url=NORMAS_SUBCHANNEL_URLS[2],
        source_type="index",
        role="primary",
    ),
    RadarSourceConfig(
        id="normas_audiencias",
        channel="normas",
        title="Audiências e Consultas Públicas CVM",
        url=NORMAS_SUBCHANNEL_URLS[3],
        source_type="index",
        role="primary",
    ),
    RadarSourceConfig(
        id="normas_legislacao_rss",
        channel="normas",
        title="Feed de legislação CVM",
        url=LEGISLATION_RSS_URL,
        source_type="rss",
        role="signal",
    ),
    RadarSourceConfig(
        id="normas_audiencias_rss",
        channel="normas",
        title="Feed de audiências públicas CVM",
        url=HEARINGS_RSS_URL,
        source_type="rss",
        role="signal",
    ),
)

SOURCE_BY_ID = {source.id: source for source in SOURCES}
