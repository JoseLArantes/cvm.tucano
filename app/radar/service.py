from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import AnyUrl

from app.core.config import Settings, get_settings
from app.radar.channels import CHANNELS, RadarChannelConfig
from app.radar.classifier import classify_text
from app.radar.models import (
    ParsedRadarItem,
    RadarChannel,
    RadarChannelStatus,
    RadarFeed,
    RadarItem,
    RadarState,
    RadarStateChannel,
    RadarSummary,
    RadarWindow,
)
from app.radar.parser import parse_channel_html
from app.radar.storage import LocalRadarPublisher, R2RadarPublisher, RadarPublisher
from app.radar.utils import canonical_url, sha256_bytes, slugify, source_hash, utc_now


def run_radar_collection(*, channels: list[str] | None = None, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    publisher = build_publisher(settings)
    previous_feed = publisher.load_latest_feed()
    state = publisher.load_state()
    now = utc_now()
    selected = set(channels or [])

    collected_channels: list[RadarChannel] = []
    collected_items: list[RadarItem] = []
    previous_by_channel = _previous_items_by_channel(previous_feed)
    previous_channels = {channel.key: channel for channel in previous_feed.channels} if previous_feed is not None else {}

    for channel in CHANNELS:
        if selected and channel.key not in selected:
            if channel.key in previous_channels:
                collected_channels.append(previous_channels[channel.key])
            continue
        if not bool(getattr(settings, channel.enabled_attr)):
            collected_channels.append(
                RadarChannel(key=channel.key, url=channel.url, status="disabled", last_success_at=None, items_count=0)
            )
            continue
        channel_result, parsed_items = _collect_channel(channel, state=state, settings=settings, captured_at=now)
        collected_channels.append(channel_result)
        if channel_result.status in {"success", "partial", "not_modified"}:
            collected_items.extend(_to_feed_items(parsed_items, captured_at=now, base_url=channel.url))
        elif channel.key in previous_by_channel:
            collected_items.extend(previous_by_channel[channel.key])

    feed = _build_feed(
        items=collected_items,
        channels=collected_channels,
        previous_feed=previous_feed,
        settings=settings,
        generated_at=now,
    )
    if feed is None:
        return {"status": "failed", "published": False, "reason": "all_channels_failed_without_previous_feed"}

    state_key = _key(settings.radar_cvm_storage_prefix, "state.json")
    history_key = _history_key(settings.radar_cvm_storage_prefix, now)
    latest_key = _key(settings.radar_cvm_storage_prefix, "latest.json")
    publish_result = publisher.publish(feed=feed, state=state, history_key=history_key, latest_key=latest_key, state_key=state_key)
    return {
        "status": "success",
        "published": True,
        "items": feed.summary.total_items,
        "channels_failed": feed.summary.channels_failed,
        **publish_result,
    }


def build_publisher(settings: Settings) -> RadarPublisher:
    if settings.radar_cvm_storage_backend == "local":
        return LocalRadarPublisher(
            base_dir=settings.storage_dir,
            prefix=settings.radar_cvm_storage_prefix,
            cache_control=settings.radar_cvm_cache_control,
        )
    if settings.radar_cvm_storage_backend == "r2":
        return R2RadarPublisher(
            endpoint_url=settings.radar_cvm_r2_endpoint_url,
            bucket=settings.radar_cvm_r2_bucket,
            access_key_id=settings.radar_cvm_r2_access_key_id,
            secret_access_key=settings.radar_cvm_r2_secret_access_key,
            region=settings.radar_cvm_r2_region,
            prefix=settings.radar_cvm_storage_prefix,
            cache_control=settings.radar_cvm_cache_control,
        )
    raise ValueError(f"Backend de storage invalido para Radar: {settings.radar_cvm_storage_backend}")


def _collect_channel(
    channel: RadarChannelConfig,
    *,
    state: RadarState,
    settings: Settings,
    captured_at: datetime,
) -> tuple[RadarChannel, list[ParsedRadarItem]]:
    headers = {"User-Agent": settings.radar_cvm_user_agent}
    previous = state.channels.get(channel.key)
    if previous is not None:
        if previous.etag:
            headers["If-None-Match"] = previous.etag
        if previous.last_modified:
            headers["If-Modified-Since"] = previous.last_modified
    try:
        response = httpx.get(channel.url, timeout=settings.radar_cvm_request_timeout_seconds, headers=headers)
    except Exception as exc:
        return _failed_channel(channel, previous, exc), []
    if response.status_code == 304:
        return (
            RadarChannel(
                key=channel.key,
                url=channel.url,
                status="not_modified",
                last_success_at=None if previous is None else previous.last_success_at,
                items_count=0,
            ),
            [],
        )
    if response.status_code >= 400:
        return _failed_channel(channel, previous, RuntimeError(f"HTTP {response.status_code}")), []

    parsed_items = parse_channel_html(channel.key, channel.url, response.text)
    status: RadarChannelStatus = "success" if parsed_items else "partial"
    state.channels[channel.key] = RadarStateChannel(
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        last_success_at=captured_at,
    )
    return (
        RadarChannel(
            key=channel.key,
            url=channel.url,
            status=status,
            last_success_at=captured_at,
            items_count=len(parsed_items),
            error=None if parsed_items else "parser_returned_no_items",
        ),
        parsed_items,
    )


def _failed_channel(
    channel: RadarChannelConfig,
    previous: RadarStateChannel | None,
    exc: Exception,
) -> RadarChannel:
    return RadarChannel(
        key=channel.key,
        url=channel.url,
        status="failed",
        last_success_at=None if previous is None else previous.last_success_at,
        items_count=0,
        error=f"{type(exc).__name__}: {exc}"[:500],
    )


def _to_feed_items(parsed_items: list[ParsedRadarItem], *, captured_at: datetime, base_url: str) -> list[RadarItem]:
    items: list[RadarItem] = []
    for parsed in parsed_items:
        canonical = canonical_url(base_url, parsed.url)
        tags, relevance, signals = classify_text(parsed.raw_text)
        date_part = (parsed.published_at or captured_at).date().isoformat()
        item_id = f"{parsed.channel}:{date_part}:{slugify(canonical)}"
        items.append(
            RadarItem(
                id=item_id,
                channel=parsed.channel,
                kind=parsed.kind,
                title=parsed.title,
                summary=None if parsed.summary is None else parsed.summary[:1000],
                url=AnyUrl(canonical),
                published_at=parsed.published_at,
                captured_at=captured_at,
                tags=tags,
                relevance=relevance,
                signals=signals,
                source_hash=source_hash(parsed.title, parsed.summary or "", canonical),
            )
        )
    return items


def _build_feed(
    *,
    items: list[RadarItem],
    channels: list[RadarChannel],
    previous_feed: RadarFeed | None,
    settings: Settings,
    generated_at: datetime,
) -> RadarFeed | None:
    failed_count = sum(1 for channel in channels if channel.status == "failed")
    if failed_count == len(channels) and previous_feed is None:
        return None

    if previous_feed is not None:
        items.extend(previous_feed.items)

    window_start = generated_at - timedelta(days=settings.radar_cvm_retention_days)
    deduped = _dedupe_items(items)
    filtered = [
        item
        for item in deduped
        if (item.published_at or item.captured_at).astimezone(UTC) >= window_start
    ][: settings.radar_cvm_max_items]

    summary = RadarSummary(
        total_items=len(filtered),
        channels_scanned=sum(1 for channel in channels if channel.status != "disabled"),
        channels_failed=failed_count,
        checksum_sha256="pending",
    )
    feed = RadarFeed(
        generated_at=generated_at,
        window=RadarWindow(days=settings.radar_cvm_retention_days, started_at=window_start, ended_at=generated_at),
        summary=summary,
        channels=channels,
        items=filtered,
    )
    content = feed.model_dump(mode="json")
    checksum = sha256_bytes(str(content).encode("utf-8"))
    return feed.model_copy(update={"summary": summary.model_copy(update={"checksum_sha256": checksum})})


def _dedupe_items(items: list[RadarItem]) -> list[RadarItem]:
    by_key: dict[str, RadarItem] = {}
    for item in sorted(items, key=lambda value: value.captured_at, reverse=True):
        key = str(item.url)
        if key not in by_key:
            by_key[key] = item
    return sorted(by_key.values(), key=lambda value: (value.published_at or value.captured_at), reverse=True)


def _previous_items_by_channel(feed: RadarFeed | None) -> dict[str, list[RadarItem]]:
    if feed is None:
        return {}
    result: dict[str, list[RadarItem]] = {}
    for item in feed.items:
        result.setdefault(item.channel, []).append(item)
    return result


def _key(prefix: str, suffix: str) -> str:
    return f"{prefix.strip('/')}/{suffix}"


def _history_key(prefix: str, now: datetime) -> str:
    return _key(prefix, f"history/{now:%Y/%m/%d/%H%M%S}.json")
