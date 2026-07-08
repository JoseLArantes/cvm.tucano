from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_url(base_url: str, url: str) -> str:
    resolved = urljoin(base_url, url.strip())
    parts = urlsplit(resolved)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", "", ""))


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "item"


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def source_hash(*parts: str) -> str:
    raw = "\n".join(parts).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
