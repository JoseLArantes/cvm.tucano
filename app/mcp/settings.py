from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    profile: str = Field(default="analyst", alias="MCP_PROFILE")
    token: str = Field(default="", alias="MCP_TOKEN")
    require_token: bool = Field(default=False, alias="MCP_REQUIRE_TOKEN")
    http_enabled: bool = Field(default=False, alias="MCP_HTTP_ENABLED")
    http_require_bearer: bool = Field(default=True, alias="MCP_HTTP_REQUIRE_BEARER")
    http_allowed_hosts: str = Field(default="localhost,127.0.0.1,127.0.0.1:*", alias="MCP_HTTP_ALLOWED_HOSTS")
    http_allowed_origins: str = Field(default="", alias="MCP_HTTP_ALLOWED_ORIGINS")
    max_rows: int = Field(default=50, ge=1, le=500, alias="MCP_MAX_ROWS")
    max_periods: int = Field(default=20, ge=1, le=80, alias="MCP_MAX_PERIODS")
    tool_timeout_seconds: int = Field(default=30, ge=1, le=300, alias="MCP_TOOL_TIMEOUT_SECONDS")
    include_raw_default: bool = Field(default=False, alias="MCP_INCLUDE_RAW_DEFAULT")

    @staticmethod
    def parse_csv_list(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return self.parse_csv_list(self.http_allowed_hosts)

    @property
    def allowed_origins(self) -> list[str]:
        return self.parse_csv_list(self.http_allowed_origins)


@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()
