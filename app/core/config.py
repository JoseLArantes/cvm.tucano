import csv
import sys
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Aumentar o limite de tamanho do campo do parser de CSV para lidar com os longos campos de texto da CVM (ex: FRE)
def _setup_csv_limit() -> None:
    max_int = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_int)
            break
        except OverflowError:
            max_int = int(max_int / 10)


_setup_csv_limit()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://cvm:cvm@localhost:5432/cvm", alias="DATABASE_URL")
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
    anos_iniciais_fca: str = Field(default="", alias="ANOS_INICIAIS_FCA")
    anos_iniciais_ipe: str = Field(default="", alias="ANOS_INICIAIS_IPE")
    anos_iniciais_vlmo: str = Field(default="", alias="ANOS_INICIAIS_VLMO")
    anos_iniciais_cgvn: str = Field(default="", alias="ANOS_INICIAIS_CGVN")
    ingestion_promote_enabled: bool = Field(default=True, alias="INGESTION_PROMOTE_ENABLED")
    ingestion_provisional_company_enabled: bool = Field(
        default=False,
        alias="INGESTION_PROVISIONAL_COMPANY_ENABLED",
    )
    ingestion_max_retries: int = Field(default=5, ge=0, alias="INGESTION_MAX_RETRIES")
    ingestion_retry_backoff_max_seconds: int = Field(
        default=600,
        ge=1,
        alias="INGESTION_RETRY_BACKOFF_MAX_SECONDS",
    )
    ingestion_company_missing_max_ratio: float = Field(
        default=0.01,
        ge=0.0,
        alias="INGESTION_COMPANY_MISSING_MAX_RATIO",
    )
    celery_worker_max_tasks_per_child: int = Field(
        default=1,
        ge=1,
        alias="CELERY_WORKER_MAX_TASKS_PER_CHILD",
    )
    celery_worker_max_memory_per_child_kb: int = Field(
        default=1_500_000,
        ge=1,
        alias="CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB",
    )
    analise_materializacao_chunk_size: int = Field(
        default=25,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_CHUNK_SIZE",
    )
    analise_materializacao_max_active_campaigns: int = Field(
        default=1,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_MAX_ACTIVE_CAMPAIGNS",
    )
    analise_materializacao_max_active_chunks_per_campaign: int = Field(
        default=1,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_MAX_ACTIVE_CHUNKS_PER_CAMPAIGN",
    )
    analise_materializacao_queue_name: str = Field(
        default="analise_materializacao",
        alias="ANALISE_MATERIALIZACAO_QUEUE_NAME",
    )
    analise_materializacao_dedup_window_seconds: int = Field(
        default=0,
        ge=0,
        alias="ANALISE_MATERIALIZACAO_DEDUP_WINDOW_SECONDS",
    )
    analise_materializacao_gate_enabled: bool = Field(
        default=True,
        alias="ANALISE_MATERIALIZACAO_GATE_ENABLED",
    )
    analise_materializacao_gate_poll_seconds: int = Field(
        default=30,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_GATE_POLL_SECONDS",
    )
    analise_materializacao_chunk_lease_seconds: int = Field(
        default=300,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_CHUNK_LEASE_SECONDS",
    )
    analise_materializacao_recovery_sweep_seconds: int = Field(
        default=60,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_RECOVERY_SWEEP_SECONDS",
    )
    analise_materializacao_stale_grace_seconds: int = Field(
        default=60,
        ge=0,
        alias="ANALISE_MATERIALIZACAO_STALE_GRACE_SECONDS",
    )
    analise_materializacao_pending_recovery_enabled: bool = Field(
        default=True,
        alias="ANALISE_MATERIALIZACAO_PENDING_RECOVERY_ENABLED",
    )
    analise_materializacao_pending_recovery_sweep_seconds: int = Field(
        default=60,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_PENDING_RECOVERY_SWEEP_SECONDS",
    )
    analise_materializacao_pending_recovery_max_campaigns: int = Field(
        default=25,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS",
    )
    analise_materializacao_pending_recovery_max_requeues: int = Field(
        default=10,
        ge=1,
        alias="ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_REQUEUES",
    )
    analise_materializacao_pending_recovery_min_age_seconds: int = Field(
        default=120,
        ge=0,
        alias="ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MIN_AGE_SECONDS",
    )
    analise_materializacao_blocking_sync_statuses: str = Field(
        default="em_execucao",
        alias="ANALISE_MATERIALIZACAO_BLOCKING_SYNC_STATUSES",
    )
    ingestion_stage_batch_size: int = Field(default=5000, ge=1, alias="INGESTION_STAGE_BATCH_SIZE")
    ingestion_promote_batch_size: int = Field(default=5000, ge=1, alias="INGESTION_PROMOTE_BATCH_SIZE")
    ingestion_phase_stale_after_seconds: int = Field(
        default=1800,
        ge=1,
        alias="INGESTION_PHASE_STALE_AFTER_SECONDS",
    )
    ingestion_recovery_sweep_seconds: int = Field(
        default=60,
        ge=1,
        alias="INGESTION_RECOVERY_SWEEP_SECONDS",
    )
    ingestion_financeiro_typed_staging_enabled: bool = Field(
        default=True,
        alias="INGESTION_FINANCEIRO_TYPED_STAGING_ENABLED",
    )
    ingestion_financeiro_direct_path_enabled: bool = Field(
        default=True,
        alias="INGESTION_FINANCEIRO_DIRECT_PATH_ENABLED",
    )
    ingestion_max_active_members_per_parent: int = Field(
        default=2,
        ge=1,
        alias="INGESTION_MAX_ACTIVE_MEMBERS_PER_PARENT",
    )
    ingestion_queue_name: str = Field(default="ingestion", alias="INGESTION_QUEUE_NAME")
    ingestion_control_queue_name: str = Field(default="ingestion_control", alias="INGESTION_CONTROL_QUEUE_NAME")
    ingestion_normalized_artifact_format: Literal["typed_csv", "parquet"] = Field(
        default="typed_csv",
        alias="INGESTION_NORMALIZED_ARTIFACT_FORMAT",
    )
    ingestion_member_payload_db_fallback_enabled: bool = Field(
        default=False,
        alias="INGESTION_MEMBER_PAYLOAD_DB_FALLBACK_ENABLED",
    )
    storage_dir: str = Field(default="data/storage", alias="STORAGE_DIR")
    updates_service_enabled: bool = Field(default=True, alias="UPDATES_SERVICE_ENABLED")
    auto_trigger_updates: bool = Field(default=False, alias="AUTO_TRIGGER_UPDATES")
    auto_analyze_on_detect: bool = Field(default=True, alias="AUTO_ANALYZE_ON_DETECT")
    session_timeout_hours: int = Field(default=24, alias="SESSION_TIMEOUT_HOURS")
    temp_dir: str = Field(default="data/temp_updates", alias="TEMP_DIR")

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

    @staticmethod
    def parse_csv_set(valor: str) -> set[str]:
        if not valor.strip():
            return set()
        return {parte.strip() for parte in valor.split(",") if parte.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
