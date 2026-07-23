from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import AnyUrl

from app.core.config import Settings, get_settings
from app.radar.channels import CHANNELS, SOURCE_BY_ID, SOURCES, RadarSourceConfig
from app.radar.classifier import classify_text
from app.radar.models import (
    ParsedRadarItem,
    RadarChannel,
    RadarFeed,
    RadarFeedV2,
    RadarItem,
    RadarItemV2,
    RadarSource,
    RadarState,
    RadarStateSource,
    RadarSummary,
    RadarSummaryV2,
    RadarWindow,
)
from app.radar.parser import (
    parse_data_news_html,
    parse_news_detail_html,
    parse_news_listing_html,
    parse_news_sitemap,
    parse_norm_index_html,
    parse_rss_links,
)
from app.radar.storage import LocalRadarPublisher, R2RadarPublisher, RadarPublisher
from app.radar.utils import canonical_url, json_bytes, source_hash, stable_id, utc_now

logger = logging.getLogger(__name__)
CollectionMode = Literal["incremental", "full"]
_DATE_SOURCE_PRIORITY = {
    None: 0,
    "sitemap": 1,
    "listing": 2,
    "block_heading": 2,
    "previous_verified": 3,
    "visible_label": 4,
    "dou_text": 4,
    "json_ld": 5,
}
_LAST_REQUEST_AT: dict[str, float] = {}
_HTTP_CLIENT: httpx.Client | None = None


def run_radar_collection(
    *,
    channels: list[str] | None = None,
    mode: CollectionMode = "full",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    publisher = build_publisher(settings)
    state = publisher.load_state()
    previous_v2 = publisher.load_latest_feed_v2()
    previous_v1 = publisher.load_latest_feed()
    now = utc_now()
    selected = set(channels or [channel.key for channel in CHANNELS])

    if not state.items:
        _bootstrap_state_from_v1(state, publisher=publisher, latest=previous_v1, now=now)

    observations: list[ParsedRadarItem] = []
    source_results: dict[str, RadarSource] = {}
    channel_errors: dict[str, list[str]] = {}

    for channel in CHANNELS:
        if channel.key not in selected or not bool(getattr(settings, channel.enabled_attr)):
            continue
        try:
            if channel.key == "noticias":
                parsed, sources, errors = _collect_news(state=state, settings=settings, now=now, mode=mode)
            elif channel.key == "novidades_dados":
                parsed, sources, errors = _collect_data_news(state=state, settings=settings, now=now)
            elif channel.key == "normas":
                parsed, sources, errors = _collect_norms(state=state, settings=settings, now=now)
            else:
                parsed, sources, errors = [], [], []
        except Exception as exc:
            logger.exception("Falha inesperada no canal do Radar", extra={"radar_channel": channel.key})
            parsed, sources, errors = [], [], [f"{type(exc).__name__}: {exc}"]
        observations.extend(parsed)
        source_results.update({source.id: source for source in sources})
        channel_errors[channel.key] = errors

    items_new, items_changed = _reconcile_items(state, observations=observations, now=now)
    window_start = now - timedelta(days=settings.radar_cvm_retention_days)
    retained = [
        item
        for item in state.items.values()
        if (item.published_at or item.first_seen_at).astimezone(UTC) >= window_start
        and canonical_url(str(item.url), str(item.url)) not in state.pending_items
    ]
    retained.sort(key=lambda item: (item.published_at or item.first_seen_at, item.id), reverse=True)
    retained = retained[: settings.radar_cvm_max_items]
    retained_ids = {item.id for item in retained}
    state.items = {
        item_id: item
        for item_id, item in state.items.items()
        if item_id in retained_ids or item.last_seen_at >= now - timedelta(days=settings.radar_cvm_retention_days * 2)
    }

    sources = _merge_sources(previous_v2, source_results, selected=selected)
    channels_result = _build_channels(
        retained,
        sources,
        selected=selected,
        channel_errors=channel_errors,
        previous_v2=previous_v2,
        settings=settings,
    )
    selected_channels = [channel for channel in channels_result if channel.key in selected and channel.status != "disabled"]
    if selected_channels and all(channel.status == "failed" for channel in selected_channels) and not retained:
        return {"status": "failed", "published": False, "reason": "all_channels_failed_without_previous_feed"}

    feed_v2 = _build_feed_v2(
        items=retained,
        sources=sources,
        channels=channels_result,
        generated_at=now,
        window_start=window_start,
        retention_days=settings.radar_cvm_retention_days,
        items_new=items_new,
        items_changed=items_changed,
    )
    feed_v1 = _project_v1(feed_v2)
    history_key = _key(settings.radar_cvm_storage_prefix, f"v2/history/{now:%Y/%m/%d/%H%M%S}.json")
    publish_result = publisher.publish_v2(
        feed_v2=feed_v2,
        feed_v1=feed_v1,
        state=state,
        history_key_v2=history_key,
    )
    logger.info(
        "Coleta do Radar concluida",
        extra={
            "radar_mode": mode,
            "radar_items": len(retained),
            "radar_items_new": items_new,
            "radar_items_changed": items_changed,
            "radar_sources_failed": feed_v2.summary.sources_failed,
        },
    )
    return {
        "status": "success",
        "published": True,
        "schema_version": "2.0",
        "items": len(retained),
        "items_new": items_new,
        "items_changed": items_changed,
        "channels_failed": feed_v2.summary.channels_failed,
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


def _collect_news(
    *,
    state: RadarState,
    settings: Settings,
    now: datetime,
    mode: CollectionMode,
) -> tuple[list[ParsedRadarItem], list[RadarSource], list[str]]:
    errors: list[str] = []
    source_results: list[RadarSource] = []
    candidates: dict[str, ParsedRadarItem] = {}

    sitemap_config = SOURCE_BY_ID["noticias_sitemap"]
    sitemap_response, sitemap_error = _fetch_source(sitemap_config, state=state, settings=settings)
    if sitemap_response is not None and sitemap_response.status_code == 304:
        source_results.append(_not_modified_source(sitemap_config, state=state, now=now))
    elif sitemap_response is not None:
        try:
            sitemap_items = parse_news_sitemap(sitemap_response.text)
            source_results.append(
                _successful_source(
                    sitemap_config,
                    state=state,
                    now=now,
                    response=sitemap_response,
                    semantic_hash=_semantic_items_hash(sitemap_items),
                    count=len(sitemap_items),
                )
            )
            candidates.update({item.identity_key or item.url: item for item in sitemap_items})
        except Exception as exc:
            sitemap_error = f"parser: {type(exc).__name__}: {exc}"
    if sitemap_error:
        errors.append(f"{sitemap_config.id}: {sitemap_error}")
        source_results.append(_failed_source(sitemap_config, state=state, now=now, error=sitemap_error))

    listing_config = SOURCE_BY_ID["noticias_listagem"]
    listing_response, listing_error = _fetch_source(listing_config, state=state, settings=settings)
    if listing_response is not None and listing_response.status_code == 304:
        source_results.append(_not_modified_source(listing_config, state=state, now=now))
    elif listing_response is not None:
        try:
            listing_items = parse_news_listing_html(str(listing_response.url or listing_config.url), listing_response.text)
            source_results.append(
                _successful_source(
                    listing_config,
                    state=state,
                    now=now,
                    response=listing_response,
                    semantic_hash=_semantic_items_hash(listing_items),
                    count=len(listing_items),
                )
            )
            for listing_item in listing_items:
                key = listing_item.identity_key or listing_item.url
                existing = candidates.get(key)
                if existing is None:
                    candidates[key] = listing_item
                    continue
                candidates[key] = existing.model_copy(
                    update={
                        "summary": listing_item.summary or existing.summary,
                        "raw_text": listing_item.raw_text or existing.raw_text,
                        "source_ids": sorted(set(existing.source_ids + listing_item.source_ids)),
                    }
                )
        except Exception as exc:
            listing_error = f"parser: {type(exc).__name__}: {exc}"
    if listing_error:
        errors.append(f"{listing_config.id}: {listing_error}")
        source_results.append(_failed_source(listing_config, state=state, now=now, error=listing_error))

    if mode == "full":
        cutoff = now - timedelta(days=settings.radar_cvm_retention_days)
        for previous in state.items.values():
            timeline_at = previous.published_at or previous.first_seen_at
            if previous.channel != "noticias" or timeline_at.astimezone(UTC) < cutoff:
                continue
            canonical = canonical_url(str(previous.url), str(previous.url))
            if _is_index_or_navigation_url(canonical, previous.title):
                continue
            candidates.setdefault(
                canonical,
                ParsedRadarItem(
                    channel=previous.channel,
                    kind=previous.kind,
                    title=previous.title,
                    summary=previous.summary,
                    url=canonical,
                    published_at=previous.published_at,
                    published_at_precision=previous.published_at_precision,
                    published_at_source=previous.published_at_source,
                    updated_at=previous.updated_at,
                    raw_text=" ".join(filter(None, (previous.title, previous.summary))),
                    identity_key=canonical,
                    source_ids=previous.source_ids,
                ),
            )

    observations: list[ParsedRadarItem] = []
    for candidate in candidates.values():
        pending_key = candidate.identity_key or candidate.url
        item_id = stable_id(candidate.channel, pending_key)
        prior_item = state.items.get(item_id)
        should_fetch_detail = mode == "full" or prior_item is None or candidate.published_at is None
        if not should_fetch_detail:
            assert prior_item is not None
            if candidate.published_at_source not in {None, "previous_verified"}:
                state.pending_items.pop(pending_key, None)
            elif pending_key in state.pending_items:
                continue
            published_at, precision, published_source = _best_publication_date(prior_item, candidate)
            state.items[item_id] = prior_item.model_copy(
                update={
                    "source_ids": sorted(set(prior_item.source_ids + candidate.source_ids)),
                    "published_at": published_at,
                    "published_at_precision": precision,
                    "published_at_source": published_source,
                    "last_seen_at": now,
                }
            )
            continue
        response, error = _fetch_url(candidate.url, settings=settings)
        if response is None:
            if prior_item is None:
                errors.append(f"detail:{candidate.url}: {error}")
            enriched = candidate
        else:
            try:
                enriched = parse_news_detail_html(candidate, response.text)
            except Exception as exc:
                errors.append(f"detail:{candidate.url}: parser: {type(exc).__name__}: {exc}")
                enriched = candidate
        publication_confirmed = enriched.published_at_source not in {None, "previous_verified"}
        if not publication_confirmed and pending_key in state.pending_items:
            continue
        if enriched.published_at is None and (prior_item is None or prior_item.published_at is None):
            state.pending_items[pending_key] = "missing_official_publication_date"
            continue
        state.pending_items.pop(pending_key, None)
        observations.append(enriched)
    return observations, source_results, errors


def _collect_data_news(
    *, state: RadarState, settings: Settings, now: datetime
) -> tuple[list[ParsedRadarItem], list[RadarSource], list[str]]:
    config = SOURCE_BY_ID["novidades_dados"]
    response, error = _fetch_source(config, state=state, settings=settings)
    if response is None:
        return [], [_failed_source(config, state=state, now=now, error=error or "fetch_failed")], [error or "fetch_failed"]
    if response.status_code == 304:
        return [], [_not_modified_source(config, state=state, now=now)], []
    try:
        items = parse_data_news_html(str(response.url or config.url), response.text)
    except Exception as exc:
        error = f"parser: {type(exc).__name__}: {exc}"
        return [], [_failed_source(config, state=state, now=now, error=error)], [error]
    source = _successful_source(
        config,
        state=state,
        now=now,
        response=response,
        semantic_hash=_semantic_items_hash(items),
        count=len(items),
    )
    return items, [source], ([] if items else ["novidades_dados: parser_returned_no_items"])


def _collect_norms(
    *, state: RadarState, settings: Settings, now: datetime
) -> tuple[list[ParsedRadarItem], list[RadarSource], list[str]]:
    observations: list[ParsedRadarItem] = []
    source_results: list[RadarSource] = []
    errors: list[str] = []
    for config in (source for source in SOURCES if source.channel == "normas"):
        response, error = _fetch_source(config, state=state, settings=settings)
        if response is None:
            errors.append(f"{config.id}: {error}")
            source_results.append(_failed_source(config, state=state, now=now, error=error or "fetch_failed"))
            continue
        if response.status_code == 304:
            source_results.append(_not_modified_source(config, state=state, now=now))
            continue
        try:
            if config.source_type == "rss":
                links = parse_rss_links(response.text)
                semantic_hash = source_hash(*sorted(links))
                count = len(links)
                parsed: list[ParsedRadarItem] = []
            else:
                parsed = parse_norm_index_html(config.id, str(response.url or config.url), response.text)
                semantic_hash = _semantic_items_hash(parsed)
                count = len(parsed)
                observations.extend(parsed)
            source_results.append(
                _successful_source(
                    config,
                    state=state,
                    now=now,
                    response=response,
                    semantic_hash=semantic_hash,
                    count=count,
                )
            )
        except Exception as exc:
            error = f"parser: {type(exc).__name__}: {exc}"
            errors.append(f"{config.id}: {error}")
            source_results.append(_failed_source(config, state=state, now=now, error=error))
    return observations, source_results, errors


def _fetch_source(
    config: RadarSourceConfig, *, state: RadarState, settings: Settings
) -> tuple[Any | None, str | None]:
    previous = state.sources.get(config.id)
    headers = {"User-Agent": settings.radar_cvm_user_agent}
    if previous is not None:
        if previous.etag:
            headers["If-None-Match"] = previous.etag
        if previous.last_modified:
            headers["If-Modified-Since"] = previous.last_modified
    return _fetch_url(config.url, settings=settings, headers=headers)


def _fetch_url(
    url: str,
    *,
    settings: Settings,
    headers: dict[str, str] | None = None,
) -> tuple[Any | None, str | None]:
    request_headers = {"User-Agent": settings.radar_cvm_user_agent, **(headers or {})}
    last_error: str | None = None
    for attempt in range(3):
        _throttle_host(url, settings.radar_cvm_requests_per_second)
        try:
            response = _http_get(
                url,
                timeout=settings.radar_cvm_request_timeout_seconds,
                headers=request_headers,
                follow_redirects=True,
            )
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                return response, None
            last_error = f"HTTP {response.status_code}"
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            retry_after = response.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                time.sleep(min(float(retry_after), 10.0))
        if attempt < 2:
            time.sleep(float(2**attempt))
    return None, last_error


def _http_get(url: str, **kwargs: Any) -> httpx.Response:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(follow_redirects=True)
    return _HTTP_CLIENT.get(url, **kwargs)


def _throttle_host(url: str, requests_per_second: float) -> None:
    host = urlsplit(url).netloc.lower()
    interval = 1.0 / max(requests_per_second, 0.1)
    last_request_at = _LAST_REQUEST_AT.get(host)
    now = time.monotonic()
    if last_request_at is not None:
        time.sleep(max(0.0, interval - (now - last_request_at)))
    _LAST_REQUEST_AT[host] = time.monotonic()


def _successful_source(
    config: RadarSourceConfig,
    *,
    state: RadarState,
    now: datetime,
    response: Any,
    semantic_hash: str,
    count: int,
) -> RadarSource:
    previous = state.sources.get(config.id)
    changed_at = now if previous is None or previous.content_hash != semantic_hash else previous.last_changed_at
    if previous is not None and previous.discovered_count >= 4 and count < previous.discovered_count / 2:
        error = f"discovered_count_drop:{previous.discovered_count}->{count}"
        state.sources[config.id] = previous.model_copy(
            update={
                "etag": response.headers.get("etag") or previous.etag,
                "last_modified": response.headers.get("last-modified") or previous.last_modified,
                "last_checked_at": now,
                "last_error": error,
            }
        )
        return RadarSource(
            id=config.id,
            channel=config.channel,
            title=config.title,
            url=config.url,
            source_type=config.source_type,
            role=config.role,
            status="partial",
            last_checked_at=now,
            last_success_at=previous.last_success_at,
            last_changed_at=previous.last_changed_at,
            content_hash=previous.content_hash,
            discovered_count=previous.discovered_count,
            error=error,
        )
    state.sources[config.id] = RadarStateSource(
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        content_hash=semantic_hash,
        last_checked_at=now,
        last_success_at=now,
        last_changed_at=changed_at,
        discovered_count=count,
        last_error=None,
    )
    return RadarSource(
        id=config.id,
        channel=config.channel,
        title=config.title,
        url=config.url,
        source_type=config.source_type,
        role=config.role,
        status="success",
        last_checked_at=now,
        last_success_at=now,
        last_changed_at=changed_at,
        content_hash=semantic_hash,
        discovered_count=count,
        error=None,
    )


def _not_modified_source(config: RadarSourceConfig, *, state: RadarState, now: datetime) -> RadarSource:
    previous = state.sources.get(config.id)
    if previous is None:
        return _failed_source(config, state=state, now=now, error="not_modified_without_previous_state")
    state.sources[config.id] = previous.model_copy(update={"last_checked_at": now, "last_error": None})
    for item_id, item in state.items.items():
        if config.id in item.source_ids:
            state.items[item_id] = item.model_copy(update={"last_seen_at": now})
    return RadarSource(
        id=config.id,
        channel=config.channel,
        title=config.title,
        url=config.url,
        source_type=config.source_type,
        role=config.role,
        status="not_modified",
        last_checked_at=now,
        last_success_at=previous.last_success_at,
        last_changed_at=previous.last_changed_at,
        content_hash=previous.content_hash,
        discovered_count=previous.discovered_count,
    )


def _failed_source(
    config: RadarSourceConfig, *, state: RadarState, now: datetime, error: str
) -> RadarSource:
    previous = state.sources.get(config.id)
    if previous is not None:
        state.sources[config.id] = previous.model_copy(update={"last_checked_at": now, "last_error": error[:500]})
    return RadarSource(
        id=config.id,
        channel=config.channel,
        title=config.title,
        url=config.url,
        source_type=config.source_type,
        role=config.role,
        status="failed",
        last_checked_at=now,
        last_success_at=None if previous is None else previous.last_success_at,
        last_changed_at=None if previous is None else previous.last_changed_at,
        content_hash=None if previous is None else previous.content_hash,
        discovered_count=0 if previous is None else previous.discovered_count,
        error=error[:500],
    )


def _reconcile_items(
    state: RadarState, *, observations: list[ParsedRadarItem], now: datetime
) -> tuple[int, int]:
    items_new = 0
    items_changed = 0
    seen_observation_ids: set[str] = set()
    for parsed in observations:
        canonical = canonical_url(parsed.url, parsed.url)
        identity_key = parsed.identity_key or canonical
        item_id = stable_id(parsed.channel, identity_key)
        if item_id in seen_observation_ids:
            existing_observation = state.items.get(item_id)
            if existing_observation is not None:
                merged_sources = sorted(set(existing_observation.source_ids + parsed.source_ids))
                state.items[item_id] = existing_observation.model_copy(update={"source_ids": merged_sources})
            continue
        seen_observation_ids.add(item_id)
        previous = state.items.get(item_id)
        tags, relevance, signals = classify_text(parsed.raw_text, title=parsed.title)
        content_hash = source_hash(parsed.title, parsed.summary or "", parsed.raw_text, canonical)
        if previous is None:
            state.items[item_id] = RadarItemV2(
                id=item_id,
                source_ids=parsed.source_ids or ["legacy"],
                channel=parsed.channel,
                kind=parsed.kind,
                title=parsed.title,
                summary=parsed.summary,
                url=AnyUrl(canonical),
                published_at=parsed.published_at,
                published_at_precision=parsed.published_at_precision,
                published_at_source=parsed.published_at_source,
                updated_at=parsed.updated_at,
                first_seen_at=now,
                last_seen_at=now,
                content_changed_at=now,
                tags=tags,
                relevance=relevance,
                signals=signals,
                content_hash=content_hash,
            )
            items_new += 1
            continue

        published_at, precision, published_source = _best_publication_date(previous, parsed)
        source_ids = sorted(set(previous.source_ids + parsed.source_ids))
        incomplete_discovery = parsed.channel == "noticias" and parsed.summary is None and previous.summary is not None
        if incomplete_discovery:
            state.items[item_id] = previous.model_copy(
                update={
                    "source_ids": source_ids,
                    "published_at": published_at,
                    "published_at_precision": precision,
                    "published_at_source": published_source,
                    "last_seen_at": now,
                    "updated_at": _latest_datetime(previous.updated_at, parsed.updated_at),
                }
            )
            continue

        changed = previous.content_hash != content_hash
        state.items[item_id] = previous.model_copy(
            update={
                "source_ids": source_ids,
                "kind": parsed.kind,
                "title": parsed.title,
                "summary": parsed.summary,
                "url": AnyUrl(canonical),
                "published_at": published_at,
                "published_at_precision": precision,
                "published_at_source": published_source,
                "updated_at": _latest_datetime(previous.updated_at, parsed.updated_at),
                "last_seen_at": now,
                "content_changed_at": now if changed else previous.content_changed_at,
                "tags": tags,
                "relevance": relevance,
                "signals": signals,
                "content_hash": content_hash,
            }
        )
        if changed:
            items_changed += 1
    return items_new, items_changed


def _best_publication_date(
    previous: RadarItemV2, parsed: ParsedRadarItem
) -> tuple[datetime | None, str | None, str | None]:
    if parsed.published_at is None:
        return previous.published_at, previous.published_at_precision, previous.published_at_source
    previous_priority = _DATE_SOURCE_PRIORITY.get(previous.published_at_source, 0)
    parsed_priority = _DATE_SOURCE_PRIORITY.get(parsed.published_at_source, 0)
    same_authoritative_source = (
        parsed.published_at_source == previous.published_at_source
        and parsed.published_at_source in {"json_ld", "visible_label", "dou_text"}
    )
    if previous.published_at is None or parsed_priority > previous_priority or same_authoritative_source:
        return parsed.published_at, parsed.published_at_precision, parsed.published_at_source
    return previous.published_at, previous.published_at_precision, previous.published_at_source


def _bootstrap_state_from_v1(
    state: RadarState,
    *,
    publisher: RadarPublisher,
    latest: RadarFeed | None,
    now: datetime,
) -> None:
    feeds = publisher.load_history_feeds()
    if latest is not None:
        feeds.append(latest)
    for feed in feeds:
        for legacy in feed.items:
            canonical = canonical_url(str(legacy.url), str(legacy.url))
            if _is_index_or_navigation_url(canonical, legacy.title):
                continue
            item_id = stable_id(legacy.channel, canonical)
            previous = state.items.get(item_id)
            first_seen = legacy.captured_at if previous is None else min(previous.first_seen_at, legacy.captured_at)
            published_at = legacy.published_at or (None if previous is None else previous.published_at)
            tags = legacy.tags if previous is None else previous.tags
            relevance = legacy.relevance if previous is None else previous.relevance
            signals = legacy.signals if previous is None else previous.signals
            state.items[item_id] = RadarItemV2(
                id=item_id,
                source_ids=["legacy_history"],
                channel=legacy.channel,
                kind=legacy.kind,
                title=legacy.title,
                summary=legacy.summary,
                url=AnyUrl(canonical),
                published_at=published_at,
                published_at_precision=None if published_at is None else "datetime",
                published_at_source=None if published_at is None else "previous_verified",
                first_seen_at=first_seen,
                last_seen_at=max(legacy.captured_at, previous.last_seen_at if previous else legacy.captured_at),
                content_changed_at=previous.content_changed_at if previous else first_seen,
                tags=tags,
                relevance=relevance,
                signals=signals,
                content_hash=legacy.source_hash,
            )
            if legacy.channel == "noticias":
                state.pending_items[canonical] = "legacy_requires_official_confirmation"
    if not feeds:
        logger.info("Estado v2 do Radar iniciado sem historico", extra={"radar_started_at": now.isoformat()})


def _merge_sources(
    previous: RadarFeedV2 | None,
    current: dict[str, RadarSource],
    *,
    selected: set[str],
) -> list[RadarSource]:
    result = dict(current)
    if previous is not None:
        for source in previous.sources:
            if source.channel not in selected:
                result.setdefault(source.id, source)
    return sorted(result.values(), key=lambda source: (source.channel, source.id))


def _build_channels(
    items: list[RadarItemV2],
    sources: list[RadarSource],
    *,
    selected: set[str],
    channel_errors: dict[str, list[str]],
    previous_v2: RadarFeedV2 | None,
    settings: Settings,
) -> list[RadarChannel]:
    previous_channels = {channel.key: channel for channel in previous_v2.channels} if previous_v2 else {}
    result: list[RadarChannel] = []
    for config in CHANNELS:
        enabled = bool(getattr(settings, config.enabled_attr))
        if not enabled:
            result.append(RadarChannel(key=config.key, url=config.url, status="disabled", items_count=0))
            continue
        if config.key not in selected and config.key in previous_channels:
            result.append(previous_channels[config.key])
            continue
        channel_sources = [source for source in sources if source.channel == config.key]
        failed = [source for source in channel_sources if source.status == "failed"]
        partial = [source for source in channel_sources if source.status == "partial"]
        status: Literal["success", "not_modified", "partial", "failed"]
        if channel_sources and len(failed) == len(channel_sources):
            status = "failed"
        elif failed or partial or channel_errors.get(config.key):
            status = "partial"
        elif channel_sources and all(source.status == "not_modified" for source in channel_sources):
            status = "not_modified"
        else:
            status = "success"
        successes = [source.last_success_at for source in channel_sources if source.last_success_at is not None]
        errors = channel_errors.get(config.key, [])
        result.append(
            RadarChannel(
                key=config.key,
                url=config.url,
                status=status,
                last_success_at=max(successes) if successes else None,
                items_count=sum(1 for item in items if item.channel == config.key),
                error="; ".join(errors)[:500] or None,
            )
        )
    return result


def _build_feed_v2(
    *,
    items: list[RadarItemV2],
    sources: list[RadarSource],
    channels: list[RadarChannel],
    generated_at: datetime,
    window_start: datetime,
    retention_days: int,
    items_new: int,
    items_changed: int,
) -> RadarFeedV2:
    summary = RadarSummaryV2(
        total_items=len(items),
        channels_scanned=sum(channel.status != "disabled" for channel in channels),
        channels_failed=sum(channel.status == "failed" for channel in channels),
        sources_scanned=len(sources),
        sources_failed=sum(source.status == "failed" for source in sources),
        items_new=items_new,
        items_changed=items_changed,
        items_without_published_at=sum(item.published_at is None for item in items),
        checksum_sha256="pending",
    )
    feed = RadarFeedV2(
        generated_at=generated_at,
        window=RadarWindow(days=retention_days, started_at=window_start, ended_at=generated_at),
        summary=summary,
        channels=channels,
        sources=sources,
        items=items,
    )
    checksum = source_hash(json_bytes(feed.model_dump(mode="json")).decode("utf-8")).removeprefix("sha256:")
    return feed.model_copy(update={"summary": summary.model_copy(update={"checksum_sha256": checksum})})


def _project_v1(feed: RadarFeedV2) -> RadarFeed:
    items = [
        RadarItem(
            id=item.id,
            channel=item.channel,
            kind=item.kind,
            title=item.title,
            summary=item.summary,
            url=item.url,
            published_at=item.published_at,
            captured_at=item.first_seen_at,
            tags=item.tags,
            relevance=item.relevance,
            signals=item.signals,
            source_hash=item.content_hash,
        )
        for item in feed.items
    ]
    summary = RadarSummary(
        total_items=len(items),
        channels_scanned=feed.summary.channels_scanned,
        channels_failed=feed.summary.channels_failed,
        checksum_sha256="pending",
    )
    projected = RadarFeed(
        generated_at=feed.generated_at,
        window=feed.window,
        summary=summary,
        channels=feed.channels,
        items=items,
    )
    checksum = source_hash(json_bytes(projected.model_dump(mode="json")).decode("utf-8")).removeprefix("sha256:")
    return projected.model_copy(update={"summary": summary.model_copy(update={"checksum_sha256": checksum})})


def _semantic_items_hash(items: list[ParsedRadarItem]) -> str:
    parts = sorted(
        f"{item.identity_key or item.url}|{source_hash(item.title, item.summary or '', item.raw_text)}"
        for item in items
    )
    return source_hash(*parts)


def _is_index_or_navigation_url(url: str, title: str) -> bool:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    exact_indexes = {
        "/cvm/pt-br/assuntos/noticias",
        "/cvm/pt-br/assuntos/normas",
        "/legislacao/resolucoes.html",
        "/legislacao/deliberacoes.html",
        "/legislacao/pareceres-orientacao.html",
        "/audiencias_publicas/index.html",
    }
    return (
        path in exact_indexes
        or bool(re.fullmatch(r"/cvm/pt-br/assuntos/noticias/\d{4}", path))
        or title.lower() in {"alto-contraste", "ir para o conteúdo 1"}
    )


def _latest_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _key(prefix: str, suffix: str) -> str:
    return f"{prefix.strip('/')}/{suffix}"
