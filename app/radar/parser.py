from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from selectolax.lexbor import LexborHTMLParser

from app.radar.channels import NORMAS_SUBCHANNEL_URLS
from app.radar.models import ParsedRadarItem, RadarChannelKey, RadarItemKind
from app.radar.utils import canonical_url, normalize_space


def parse_channel_html(channel: RadarChannelKey, base_url: str, html: str) -> list[ParsedRadarItem]:
    if channel == "noticias":
        return _parse_generic_listing(channel, "noticia", base_url, html)
    if channel == "novidades_dados":
        return _parse_generic_listing(channel, "novidade_dados", base_url, html)
    if channel == "normas":
        return _parse_normas(base_url, html)
    return []


def _parse_normas(base_url: str, html: str) -> list[ParsedRadarItem]:
    items = _parse_generic_listing("normas", "norma", base_url, html)
    return [
        item.model_copy(update={"kind": _kind_for_norma(item)})
        for item in items
        if any(str(item.url).startswith(url) for url in NORMAS_SUBCHANNEL_URLS) or item.url == base_url
    ] or items


def _kind_for_norma(item: ParsedRadarItem) -> RadarItemKind:
    text = f"{item.title} {item.url}".lower()
    if "audiencia" in text or "audiência" in text or "consulta" in text:
        return "consulta_publica"
    return "norma"


def _parse_generic_listing(
    channel: RadarChannelKey,
    kind: RadarItemKind,
    base_url: str,
    html: str,
) -> list[ParsedRadarItem]:
    parser = LexborHTMLParser(html)
    seen: set[str] = set()
    items: list[ParsedRadarItem] = []

    for link in parser.css("a[href]"):
        title = normalize_space(link.text(deep=True) or "")
        href = link.attributes.get("href", "")
        if not title or len(title) < 4 or not href:
            continue
        url = canonical_url(base_url, href)
        if not _is_relevant_url(base_url, url) or url in seen:
            continue
        seen.add(url)

        container_text = _nearest_text(link)
        summary = _summary_from_text(container_text, title)
        published_at = _extract_date(container_text)
        raw_text = normalize_space(f"{title} {summary or ''} {container_text}")
        items.append(
            ParsedRadarItem(
                channel=channel,
                kind=kind,
                title=title[:500],
                summary=summary,
                url=url,
                published_at=published_at,
                raw_text=raw_text,
            )
        )

    return items


def _is_relevant_url(base_url: str, url: str) -> bool:
    return url.startswith(base_url.rstrip("/"))


def _nearest_text(node: object) -> str:
    current = node
    for _ in range(4):
        text = normalize_space(current.text(deep=True) or "")  # type: ignore[attr-defined]
        if len(text) > 40:
            return text
        parent = getattr(current, "parent", None)
        if parent is None:
            break
        current = parent
    return normalize_space(node.text(deep=True) or "")  # type: ignore[attr-defined]


def _summary_from_text(text: str, title: str) -> str | None:
    cleaned = normalize_space(text.replace(title, " ", 1))
    if not cleaned:
        return None
    return cleaned[:1000]


def _extract_date(text: str) -> datetime | None:
    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?", text)
    if iso_match:
        year, month, day, hour, minute, second = iso_match.groups()
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            tzinfo=UTC,
        )

    br_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})(?:\s+(\d{1,2}):(\d{2}))?", text)
    if br_match:
        day, month, year, hour, minute = br_match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), tzinfo=UTC)

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
