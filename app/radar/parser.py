from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from selectolax.lexbor import LexborHTMLParser, LexborNode

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
_UPDATED_PATTERNS = [
    re.compile(rf"\bAtualizad[oa]\s+em\s*{_BR_DATE_PATTERN}", re.IGNORECASE),
    re.compile(rf"\bRetificad[oa]\s+(?:no\s+DOU\s+de|em)\s*{_BR_DATE_PATTERN}", re.IGNORECASE),
]
_NEWS_PATH = re.compile(r"^/cvm/pt-br/assuntos/noticias/(?!anexos(?:/|$))")
_NORM_PATHS: tuple[tuple[re.Pattern[str], RadarItemKind], ...] = (
    (re.compile(r"^/legislacao/resolucoes/resol\d+\.html$", re.IGNORECASE), "norma"),
    (re.compile(r"^/legislacao/deliberacoes/(?:deli\d+/)?deli\d+\.html$", re.IGNORECASE), "norma"),
    (re.compile(r"^/legislacao/pareceres-orientacao/pare\d+\.html$", re.IGNORECASE), "norma"),
    (re.compile(r"^/audiencias_publicas/(?!index\.html$).+\.html$", re.IGNORECASE), "consulta_publica"),
)
_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def parse_channel_html(channel: RadarChannelKey, base_url: str, html: str) -> list[ParsedRadarItem]:
    """Compatibility entry point used by existing callers and tests."""
    if channel == "noticias":
        return parse_news_listing_html(base_url, html)
    if channel == "novidades_dados":
        return parse_data_news_html(base_url, html)
    if channel == "normas":
        return parse_norm_index_html("normas_legacy", base_url, html)
    return []


def parse_news_sitemap(xml: str) -> list[ParsedRadarItem]:
    root = ElementTree.fromstring(xml)
    sitemap_ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    news_ns = "{http://www.google.com/schemas/sitemap-news/0.9}"
    items: list[ParsedRadarItem] = []
    for node in root.findall(f"{sitemap_ns}url"):
        url = normalize_space(node.findtext(f"{sitemap_ns}loc") or "")
        news = node.find(f"{news_ns}news")
        if news is None or not _is_news_content_url(url):
            continue
        title = normalize_space(news.findtext(f"{news_ns}title") or "")
        date_value = normalize_space(news.findtext(f"{news_ns}publication_date") or "")
        published_at = _parse_datetime_value(date_value)
        if not title or published_at is None:
            continue
        items.append(
            ParsedRadarItem(
                channel="noticias",
                kind="noticia",
                title=title[:500],
                url=canonical_url(url, url),
                published_at=published_at,
                published_at_precision="date",
                published_at_source="sitemap",
                raw_text=title,
                identity_key=canonical_url(url, url),
                source_ids=["noticias_sitemap"],
            )
        )
    return items


def parse_news_listing_html(base_url: str, html: str) -> list[ParsedRadarItem]:
    parser = LexborHTMLParser(html)
    containers = parser.css(".listagem-noticias-com-foto > li .conteudo")
    if not containers:
        containers = parser.css("article")
    items: list[ParsedRadarItem] = []
    seen: set[str] = set()
    for container in containers:
        link = container.css_first("h2 a[href]") or container.css_first("a[href]")
        if link is None:
            continue
        url = canonical_url(base_url, link.attributes.get("href") or "")
        if not _is_news_content_url(url) or url in seen:
            continue
        title = normalize_space(link.text(deep=True) or "")
        if len(title) < 4:
            continue
        seen.add(url)
        text = normalize_space(container.text(deep=True) or "")
        published_at = _extract_date(text)
        summary = _listing_summary(text, title)
        items.append(
            ParsedRadarItem(
                channel="noticias",
                kind="noticia",
                title=title[:500],
                summary=summary,
                url=url,
                published_at=published_at,
                published_at_precision=None if published_at is None else "date",
                published_at_source=None if published_at is None else "listing",
                raw_text=text,
                identity_key=url,
                source_ids=["noticias_listagem"],
            )
        )
    return items


def parse_news_detail_html(candidate: ParsedRadarItem, html: str) -> ParsedRadarItem:
    parser = LexborHTMLParser(html)
    structured = _news_article_json_ld(parser)
    title = normalize_space(str(structured.get("headline") or ""))
    if not title:
        title_node = parser.css_first("h1.documentFirstHeading") or parser.css_first("h1")
        title = normalize_space(title_node.text(deep=True) or "") if title_node is not None else candidate.title
    description_node = parser.css_first(".documentDescription")
    summary = normalize_space(description_node.text(deep=True) or "") if description_node is not None else candidate.summary
    body_node = parser.css_first('[property="rnews:articleBody"]') or parser.css_first("#content-core")
    body = normalize_space(body_node.text(deep=True) or "") if body_node is not None else ""

    published_at = _parse_datetime_value(str(structured.get("datePublished") or ""))
    published_source = "json_ld" if published_at is not None else None
    precision = "datetime" if published_at is not None else None
    if published_at is None:
        published_at = extract_published_at(html)
        if published_at is not None:
            published_source = "visible_label"
            precision = "datetime" if _contains_time_label(html) else "date"
    if published_at is None:
        published_at = candidate.published_at
        published_source = candidate.published_at_source
        precision = candidate.published_at_precision

    updated_at = _parse_datetime_value(str(structured.get("dateModified") or "")) or extract_updated_at(html)
    raw_text = normalize_space(" ".join(part for part in (title, summary or "", body) if part))
    return candidate.model_copy(
        update={
            "title": title[:500] or candidate.title,
            "summary": (summary[:1000] if summary else None),
            "published_at": published_at,
            "published_at_precision": precision,
            "published_at_source": published_source,
            "updated_at": updated_at,
            "raw_text": raw_text or candidate.raw_text,
        }
    )


def parse_norm_index_html(source_id: str, base_url: str, html: str) -> list[ParsedRadarItem]:
    parser = LexborHTMLParser(html)
    items: list[ParsedRadarItem] = []
    seen: set[str] = set()
    for container in parser.css("li"):
        link = container.css_first("a[href]")
        if link is None:
            continue
        url = canonical_url(base_url, link.attributes.get("href") or "")
        kind = _norm_kind(url)
        if kind is None or url in seen:
            continue
        title = normalize_space(link.text(deep=True) or link.attributes.get("title") or "")
        if len(title) < 4:
            continue
        seen.add(url)
        text = normalize_space(container.text(deep=True) or "")
        published_at = extract_published_at(text)
        updated_at = extract_updated_at(text)
        summary = _listing_summary(text, title)
        items.append(
            ParsedRadarItem(
                channel="normas",
                kind=kind,
                title=title[:500],
                summary=summary,
                url=url,
                published_at=published_at,
                published_at_precision=None if published_at is None else "date",
                published_at_source=None if published_at is None else "dou_text",
                updated_at=updated_at,
                raw_text=text,
                identity_key=url,
                source_ids=[source_id],
            )
        )
    return items


def parse_data_news_html(base_url: str, html: str) -> list[ParsedRadarItem]:
    parser = LexborHTMLParser(html)
    content = parser.css_first(".ckanext-pages-content")
    if content is None:
        return []

    blocks: list[list[LexborNode]] = []
    current: list[LexborNode] = []
    node = content.child
    while node is not None:
        if node.tag == "hr":
            if current:
                blocks.append(current)
                current = []
        elif node.tag != "-text" and normalize_space(node.text(deep=True) or ""):
            current.append(node)
        node = node.next
    if current:
        blocks.append(current)

    items: list[ParsedRadarItem] = []
    for block in blocks:
        text = normalize_space(" ".join(node.text(deep=True) or "" for node in block))
        if not text:
            continue
        published_at = extract_published_at(text) or _extract_date(normalize_space(block[0].text(deep=True) or ""))
        if published_at is None:
            continue
        updated_at = extract_updated_at(text)
        links = [
            canonical_url(base_url, link.attributes.get("href") or "")
            for node in block
            for link in node.css("a[href]")
            if link.attributes.get("href")
        ]
        title = _data_news_title(block, text)
        identity_anchor = links[0] if links else normalize_space(text[:160]).lower()
        identity_key = f"{base_url}|{published_at.date().isoformat()}|{identity_anchor}"
        items.append(
            ParsedRadarItem(
                channel="novidades_dados",
                kind="novidade_dados",
                title=title[:500],
                summary=text[:1000],
                url=base_url,
                published_at=published_at,
                published_at_precision="date",
                published_at_source="visible_label" if "publicado em" in text.lower() else "block_heading",
                updated_at=updated_at,
                raw_text=text,
                identity_key=identity_key,
                source_ids=["novidades_dados"],
            )
        )
    return items


def parse_rss_links(xml: str) -> set[str]:
    root = ElementTree.fromstring(xml)
    result: set[str] = set()
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() != "link" or not node.text:
            continue
        url = canonical_url(node.text, node.text)
        if _norm_kind(url) is not None:
            result.add(url)
    return result


def extract_published_at(text: str) -> datetime | None:
    if "<" in text and ">" in text:
        structured = _extract_structured_date(text, keys={"datePublished", "dateCreated"})
        if structured is not None:
            return structured
    for candidate in _text_candidates(text):
        for pattern in _PUBLISHED_PATTERNS:
            match = pattern.search(candidate)
            if match:
                return _br_datetime_from_match(match)
    return None


def extract_updated_at(text: str) -> datetime | None:
    if "<" in text and ">" in text:
        structured = _extract_structured_date(text, keys={"dateModified"})
        if structured is not None:
            return structured
    matches: list[datetime] = []
    for candidate in _text_candidates(text):
        for pattern in _UPDATED_PATTERNS:
            matches.extend(_br_datetime_from_match(match) for match in pattern.finditer(candidate))
    return max(matches) if matches else None


def _extract_structured_date(html: str, *, keys: set[str]) -> datetime | None:
    parser = LexborHTMLParser(html)
    for value in _iter_json_values_from_parser(parser, keys=keys):
        parsed = _parse_datetime_value(value)
        if parsed is not None:
            return parsed
    return None


def _news_article_json_ld(parser: LexborHTMLParser) -> dict[str, object]:
    for script in parser.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text(deep=True) or "")
        except json.JSONDecodeError:
            continue
        article = _find_news_article(data)
        if article is not None:
            return article
    return {}


def _find_news_article(data: object) -> dict[str, object] | None:
    if isinstance(data, dict):
        article_type = data.get("@type")
        if article_type == "NewsArticle" or (
            isinstance(article_type, list) and "NewsArticle" in article_type
        ):
            return data
        for value in data.values():
            article = _find_news_article(value)
            if article is not None:
                return article
    elif isinstance(data, list):
        for value in data:
            article = _find_news_article(value)
            if article is not None:
                return article
    return None


def _iter_json_values_from_parser(parser: LexborHTMLParser, *, keys: set[str]) -> list[str]:
    values: list[str] = []
    for script in parser.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text(deep=True) or "")
        except json.JSONDecodeError:
            continue
        values.extend(_iter_json_values(data, keys=keys))
    return values


def _iter_json_values(data: object, *, keys: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and isinstance(value, str):
                values.append(value)
            elif isinstance(value, dict | list):
                values.extend(_iter_json_values(value, keys=keys))
    elif isinstance(data, list):
        for item in data:
            values.extend(_iter_json_values(item, keys=keys))
    return values


def _text_candidates(text: str) -> list[str]:
    candidates = [text]
    if "<" in text and ">" in text:
        without_comments = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
        candidates.append(normalize_space(re.sub(r"<[^>]+>", " ", without_comments)))
    return candidates


def _parse_datetime_value(value: str) -> datetime | None:
    cleaned = normalize_space(value)
    if not cleaned:
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    br_match = re.search(_BR_DATE_PATTERN, cleaned)
    return _br_datetime_from_match(br_match) if br_match else None


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
    year = int(year_text) + (2000 if len(year_text) == 2 else 0)
    parsed = datetime(
        year,
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour") or 0),
        int(match.group("minute") or 0),
    )
    if match.group("hour") is not None:
        return parsed.replace(tzinfo=_SAO_PAULO).astimezone(UTC)
    return parsed.replace(tzinfo=UTC)


def _is_news_content_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.netloc != "www.gov.br" or not _NEWS_PATH.match(parts.path):
        return False
    suffix = parts.path.removeprefix("/cvm/pt-br/assuntos/noticias/").strip("/")
    return bool(suffix and not re.fullmatch(r"\d{4}", suffix))


def _norm_kind(url: str) -> RadarItemKind | None:
    path = urlsplit(url).path
    for pattern, kind in _NORM_PATHS:
        if pattern.match(path):
            return kind
    return None


def _listing_summary(text: str, title: str) -> str | None:
    cleaned = normalize_space(text.replace(title, " ", 1))
    if not cleaned:
        return None
    cleaned = re.sub(r"^\d{1,2}/\d{1,2}/\d{2,4}\s*-\s*", "", cleaned)
    return cleaned[:1000] or None


def _data_news_title(block: list[LexborNode], text: str) -> str:
    for node in block:
        link = node.css_first("a[href]")
        if link is not None:
            candidate = normalize_space(link.text(deep=True) or "")
            if len(candidate) >= 12:
                return candidate
    without_date = re.sub(rf"^(?:De\s+)?{_BR_DATE_PATTERN}(?:\s+a\s+\d{{1,2}}/\d{{1,2}}/\d{{2,4}})?\s*:?\s*", "", text)
    first_sentence = re.split(r"(?<=[.!?])\s+", without_date, maxsplit=1)[0]
    return first_sentence[:500] or f"Novidade de {text[:40]}"


def _contains_time_label(html: str) -> bool:
    return bool(re.search(r"\d{1,2}(?:h|:)\d{2}", html))
