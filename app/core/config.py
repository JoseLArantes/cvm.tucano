from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://cvm:cvm@localhost:5432/cvm", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6389/0", alias="REDIS_URL")
    cvm_base_url: str = Field(default="https://dados.cvm.gov.br/dados", alias="CVM_BASE_URL")
    api_token: str = Field(
        default="trocar-token",
        validation_alias=AliasChoices("TUCANO_CVM_TOKEN", "ADMIN_TOKEN"),
    )
    access_token_ttl_minutes: int = Field(default=480, gt=0, alias="ACCESS_TOKEN_TTL_MINUTES")
    admin_token: str = Field(default="trocar-token", alias="ADMIN_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ambiente: str = Field(default="desenvolvimento", alias="AMBIENTE")
    enable_prometheus_metrics: bool = Field(default=False, alias="ENABLE_PROMETHEUS_METRICS")
    anos_iniciais_dfp: str = Field(default="", alias="ANOS_INICIAIS_DFP")
    anos_iniciais_itr: str = Field(default="", alias="ANOS_INICIAIS_ITR")
    anos_iniciais_fre: str = Field(default="", alias="ANOS_INICIAIS_FRE")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalizar_database_url(cls, valor: str) -> str:
        if valor.startswith("postgresql://"):
            return valor.replace("postgresql://", "postgresql+psycopg://", 1)
        return valor

    @staticmethod
    def parse_anos(valor: str) -> list[int]:
        if not valor.strip():
            return []
        return [int(parte.strip()) for parte in valor.split(",") if parte.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
