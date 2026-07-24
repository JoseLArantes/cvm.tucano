import re
from collections.abc import Mapping
from typing import Any

from app.mcp.settings import McpSettings

_SECRET_KEYWORDS = ("token", "secret", "password", "senha", "database_url", "connection", "authorization")
_URL_WITH_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^:/@\s]+):(?P<password>[^@\s]+)@")


class McpAuthError(PermissionError):
    """Erro de autorizacao especifico do servidor MCP."""


def validate_analyst_access(settings: McpSettings, token: str | None = None) -> None:
    if settings.profile != "analyst":
        raise McpAuthError("Perfil MCP invalido. Apenas MCP_PROFILE=analyst e aceito neste corte.")

    supplied = (token or "").strip()
    configured = settings.token.strip()
    if settings.require_token:
        if not configured:
            raise McpAuthError("MCP_REQUIRE_TOKEN=true exige MCP_TOKEN configurado.")
        if supplied != configured:
            raise McpAuthError("Token MCP ausente ou invalido.")
        return

    if supplied and configured and supplied != configured:
        raise McpAuthError("Token MCP invalido.")


def validate_http_bearer(settings: McpSettings, authorization: str | None) -> None:
    if not settings.http_require_bearer:
        return
    configured = settings.token.strip()
    if not configured:
        raise McpAuthError("MCP_HTTP_REQUIRE_BEARER=true exige MCP_TOKEN configurado.")
    expected = f"Bearer {configured}"
    if (authorization or "").strip() != expected:
        raise McpAuthError("Bearer token MCP ausente ou invalido.")


def mask_secret(value: str) -> str:
    masked = _URL_WITH_CREDENTIALS.sub(r"\g<scheme>***:***@", value)
    if masked != value or "://" in value:
        return masked
    if len(value) >= 16:
        return f"{value[:4]}...{value[-4:]}"
    return "***"


def mask_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in _SECRET_KEYWORDS):
                result[key_text] = mask_secret(str(item))
            else:
                result[key_text] = mask_secrets(item)
        return result
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [mask_secrets(item) for item in value]
    if isinstance(value, str):
        return _URL_WITH_CREDENTIALS.sub(r"\g<scheme>***:***@", value)
    return value
