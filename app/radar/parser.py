from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from selectolax.lexbor import LexborHTMLParser

from app.radar.channels import NORMAS_SUBCHANNEL_URLS
from app.radar.models import ParsedRadarItem, RadarChannelKey, RadarItemKind
from app.radar.utils import canonical_url, normalize_space

_BR_DATE_PATTERN = (
    r"(?P<day>\d{1,2})[/.](?P<month>\d{1,2})[/.](?P<year>\d{2,4})"
    r"(?:\s+(?P<hour>\d{1,2})(?:h|:)(?P<minute>\d{2}))?"
)
_PUBLISHED_PATTERNS = [
    re.compile(rf"\bPublicad[oa]\s+em\s*{_BR_DATE_PATTERN}", re.IGNORECASE),
    re.compile(rf"\bPublicad[oa]\s+no\s+DOU\s+de\s*{_BR_DATE_PATTERN}", re.IGNORECASE),
    re.compile(rf"\bAviso\s+publicado\s+em\s*{_BR_DATE_PATTERN}", re.IGNORECASE),
]


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
        published_at = _extract_date(container_text, prefer_labeled=channel == "normas")
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
    base_parts = urlsplit(base_url)
    url_parts = urlsplit(url)
    if base_parts.netloc == "conteudo.cvm.gov.br" and url_parts.netloc == base_parts.netloc:
        return url_parts.path.startswith(("/legislacao/", "/audiencias_publicas/"))
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


def extract_published_at(text: str) -> datetime | None:
    candidates = [text]
    if "<" in text and ">" in text:
        without_comments = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
        candidates.append(normalize_space(re.sub(r"<[^>]+>", " ", without_comments)))
    for candidate in candidates:
        for pattern in _PUBLISHED_PATTERNS:
            match = pattern.search(candidate)
            if match:
                return _br_datetime_from_match(match)
    return None


def _extract_date(text: str, *, prefer_labeled: bool = False) -> datetime | None:
    if prefer_labeled:
        published = extract_published_at(text)
        if published is not None:
            return published

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

    br_match = re.search(_BR_DATE_PATTERN, text)
    if br_match:
        return _br_datetime_from_match(br_match)

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _br_datetime_from_match(match: re.Match[str]) -> datetime:
    year_text = match.group("year")
    year = int(year_text)
    if len(year_text) == 2:
        year += 2000
    return datetime(
        year,
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour") or 0),
        int(match.group("minute") or 0),
        tzinfo=UTC,
    )
