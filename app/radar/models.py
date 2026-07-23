from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

RadarChannelKey = Literal["noticias", "novidades_dados", "normas", "atos_declaratorios"]
RadarItemKind = Literal["noticia", "novidade_dados", "norma", "ato_declaratorio", "consulta_publica", "outro"]
RadarRelevance = Literal["baixa", "media", "alta", "normal", "desconhecida"]
RadarChannelStatus = Literal["success", "not_modified", "partial", "failed", "disabled"]
RadarSourceType = Literal["sitemap", "rss", "index", "mutable_page"]
RadarSourceRole = Literal["primary", "fallback", "signal", "catalog"]
RadarDatePrecision = Literal["date", "datetime"]
RadarPublishedAtSource = Literal[
    "json_ld",
    "visible_label",
    "listing",
    "sitemap",
    "dou_text",
    "block_heading",
    "previous_verified",
]


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


class RadarSummaryV2(RadarSummary):
    sources_scanned: int = Field(ge=0)
    sources_failed: int = Field(ge=0)
    items_new: int = Field(ge=0)
    items_changed: int = Field(ge=0)
    items_without_published_at: int = Field(ge=0)


class RadarChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: RadarChannelKey
    url: str
    status: RadarChannelStatus
    last_success_at: datetime | None = None
    items_count: int = Field(default=0, ge=0)
    error: str | None = None


class RadarItem(BaseModel):
    """Contrato v1 mantido para consumidores legados."""

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


class RadarSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    channel: RadarChannelKey
    title: str
    url: str
    source_type: RadarSourceType
    role: RadarSourceRole
    status: RadarChannelStatus
    last_checked_at: datetime
    last_success_at: datetime | None = None
    last_changed_at: datetime | None = None
    content_hash: str | None = None
    discovered_count: int = Field(default=0, ge=0)
    error: str | None = None


class RadarItemV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_ids: list[str] = Field(min_length=1)
    channel: RadarChannelKey
    kind: RadarItemKind
    title: str
    summary: str | None = None
    url: AnyUrl
    published_at: datetime | None = None
    published_at_precision: RadarDatePrecision | None = None
    published_at_source: RadarPublishedAtSource | None = None
    updated_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    content_changed_at: datetime
    tags: list[str] = Field(default_factory=list)
    relevance: RadarRelevance
    signals: list[str] = Field(default_factory=list)
    content_hash: str


class RadarFeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    window: RadarWindow
    summary: RadarSummary
    channels: list[RadarChannel]
    items: list[RadarItem]


class RadarFeedV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = "2.0"
    generated_at: datetime
    window: RadarWindow
    summary: RadarSummaryV2
    channels: list[RadarChannel]
    sources: list[RadarSource]
    items: list[RadarItemV2]


class RadarStateChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    etag: str | None = None
    last_modified: str | None = None
    last_success_at: datetime | None = None


class RadarStateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    etag: str | None = None
    last_modified: str | None = None
    content_hash: str | None = None
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_changed_at: datetime | None = None
    discovered_count: int = Field(default=0, ge=0)
    consecutive_missing: int = Field(default=0, ge=0)
    last_error: str | None = None


class RadarState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_schema_version: Literal["2.0"] = "2.0"
    channels: dict[str, RadarStateChannel] = Field(default_factory=dict)
    sources: dict[str, RadarStateSource] = Field(default_factory=dict)
    items: dict[str, RadarItemV2] = Field(default_factory=dict)
    pending_items: dict[str, str] = Field(default_factory=dict)


class ParsedRadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: RadarChannelKey
    kind: RadarItemKind
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    published_at_precision: RadarDatePrecision | None = None
    published_at_source: RadarPublishedAtSource | None = None
    updated_at: datetime | None = None
    raw_text: str
    identity_key: str | None = None
    source_ids: list[str] = Field(default_factory=list)
