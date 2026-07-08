from __future__ import annotations

from dataclasses import dataclass

from app.radar.models import RadarChannelKey


@dataclass(frozen=True)
class RadarChannelConfig:
    key: RadarChannelKey
    url: str
    enabled_attr: str
    kind_hint: str


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

NORMAS_SUBCHANNEL_URLS: tuple[str, ...] = (
    "https://www.gov.br/cvm/pt-br/assuntos/normas/resolucoes",
    "https://www.gov.br/cvm/pt-br/assuntos/normas/deliberacoes",
    "https://www.gov.br/cvm/pt-br/assuntos/normas/pareceres-de-orientacao",
    "https://www.gov.br/cvm/pt-br/assuntos/normas/audiencias-publicas",
)
