from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel

from app.mcp.security import mask_secrets


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(to_jsonable(item) for item in value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def limit_items(items: Sequence[Any], limit: int) -> tuple[list[Any], bool]:
    if len(items) <= limit:
        return [to_jsonable(item) for item in items], False
    return [to_jsonable(item) for item in items[:limit]], True


def response_envelope(
    *,
    tool: str,
    data: Mapping[str, Any],
    include_raw: bool,
    raw: BaseModel | Mapping[str, Any] | None = None,
    limits: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool": tool,
        "ok": True,
        **to_jsonable(dict(data)),
    }
    if limits is not None:
        payload["limits"] = to_jsonable(dict(limits))
    if include_raw and raw is not None:
        payload["raw"] = to_jsonable(raw)
    return cast(dict[str, Any], mask_secrets(payload))


def error_response(tool: str, exc: Exception) -> dict[str, Any]:
    return cast(dict[str, Any], mask_secrets(
        {
            "tool": tool,
            "ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
    ))
