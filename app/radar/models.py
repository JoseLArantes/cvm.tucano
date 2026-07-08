from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

RadarChannelKey = Literal["noticias", "novidades_dados", "normas", "atos_declaratorios"]
RadarItemKind = Literal["noticia", "novidade_dados", "norma", "ato_declaratorio", "consulta_publica", "outro"]
RadarRelevance = Literal["baixa", "media", "alta", "normal", "desconhecida"]
RadarChannelStatus = Literal["success", "not_modified", "partial", "failed", "disabled"]


class RadarWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(ge=1)
    started_at: datetime
    ended_at: datetime


class RadarSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int = Field(ge=0)
    channels_scanned: int = Field(ge=0)
    channels_failed: int = Field(ge=0)
    checksum_sha256: str


class RadarChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: RadarChannelKey
    url: str
    status: RadarChannelStatus
    last_success_at: datetime | None = None
    items_count: int = Field(default=0, ge=0)
    error: str | None = None


class RadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    channel: RadarChannelKey
    kind: RadarItemKind
    title: str
    summary: str | None = None
    url: AnyUrl
    published_at: datetime | None = None
    captured_at: datetime
    tags: list[str] = Field(default_factory=list)
    relevance: RadarRelevance
    signals: list[str] = Field(default_factory=list)
    source_hash: str


class RadarFeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    window: RadarWindow
    summary: RadarSummary
    channels: list[RadarChannel]
    items: list[RadarItem]


class RadarStateChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    etag: str | None = None
    last_modified: str | None = None
    last_success_at: datetime | None = None


class RadarState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: dict[str, RadarStateChannel] = Field(default_factory=dict)


class ParsedRadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: RadarChannelKey
    kind: RadarItemKind
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    raw_text: str
