from app.core.config import Settings


def test_normaliza_database_url_postgresql_para_psycopg() -> None:
    settings = Settings(DATABASE_URL="postgresql://usuario:senha@db:5432/cvm")
    assert settings.database_url == "postgresql+psycopg://usuario:senha@db:5432/cvm"


def test_preserva_database_url_ja_normalizada() -> None:
    settings = Settings(DATABASE_URL="postgresql+psycopg://usuario:senha@db:5432/cvm")
    assert settings.database_url == "postgresql+psycopg://usuario:senha@db:5432/cvm"


def test_configura_ttl_token_por_alias() -> None:
    settings = Settings.model_validate({"ACCESS_TOKEN_TTL_MINUTES": 30})
    assert settings.access_token_ttl_minutes == 30


def test_configura_pool_e_entrega_fundamentalista() -> None:
    settings = Settings.model_validate(
        {
            "DB_POOL_SIZE": 3,
            "DB_MAX_OVERFLOW": 1,
            "DB_POOL_TIMEOUT_SECONDS": 4,
            "DB_POOL_RECYCLE_SECONDS": 900,
            "ANALISE_FUNDAMENTALISTA_SNAPSHOT_ENABLED": True,
            "ANALISE_FUNDAMENTALISTA_PREWARM_ENABLED": True,
            "ANALISE_FUNDAMENTALISTA_CACHE_ENABLED": True,
            "ANALISE_FUNDAMENTALISTA_CACHE_TTL_SECONDS": 3600,
            "ANALISE_FUNDAMENTALISTA_RUNTIME_CACHE_TTL_SECONDS": 30,
            "ANALISE_FUNDAMENTALISTA_CACHE_LOCK_SECONDS": 90,
            "ANALISE_FUNDAMENTALISTA_CACHE_WAIT_SECONDS": 8,
            "ANALISE_FUNDAMENTALISTA_HTTP_CACHE_MAX_AGE_SECONDS": 45,
        }
    )

    assert settings.database_pool_size == 3
    assert settings.database_max_overflow == 1
    assert settings.database_pool_timeout_seconds == 4
    assert settings.database_pool_recycle_seconds == 900
    assert settings.analise_fundamentalista_snapshot_enabled is True
    assert settings.analise_fundamentalista_prewarm_enabled is True
    assert settings.analise_fundamentalista_cache_enabled is True
    assert settings.analise_fundamentalista_cache_ttl_seconds == 3600
    assert settings.analise_fundamentalista_runtime_cache_ttl_seconds == 30
    assert settings.analise_fundamentalista_cache_lock_seconds == 90
    assert settings.analise_fundamentalista_cache_wait_seconds == 8
    assert settings.analise_fundamentalista_http_cache_max_age_seconds == 45


def test_configura_cors_origins_por_alias() -> None:
    settings = Settings.model_validate(
        {
            "BACKEND_CORS_ORIGINS": "http://localhost:3000, http://localhost:5173,https://app.tucano.local",
        }
    )

    assert settings.backend_cors_origins == "http://localhost:3000, http://localhost:5173,https://app.tucano.local"
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.tucano.local",
    ]


def test_cors_origins_vazio_desabilita_middleware() -> None:
    settings = Settings.model_validate({})

    assert settings.backend_cors_origins == ""
    assert settings.cors_origins == []


def test_configura_reciclagem_de_worker_celery() -> None:
    settings = Settings.model_validate(
        {
            "CELERY_WORKER_MAX_TASKS_PER_CHILD": 2,
            "CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB": 900000,
        }
    )
    assert settings.celery_worker_max_tasks_per_child == 2
    assert settings.celery_worker_max_memory_per_child_kb == 900000


def test_configura_materializacao_analitica() -> None:
    settings = Settings.model_validate(
        {
            "ANALISE_MATERIALIZACAO_CHUNK_SIZE": 40,
            "ANALISE_MATERIALIZACAO_MAX_ACTIVE_CAMPAIGNS": 3,
            "ANALISE_MATERIALIZACAO_MAX_ACTIVE_CHUNKS_PER_CAMPAIGN": 2,
            "ANALISE_MATERIALIZACAO_QUEUE_NAME": "analise_materializacao",
            "ANALISE_MATERIALIZACAO_DEDUP_WINDOW_SECONDS": 120,
            "ANALISE_MATERIALIZACAO_GATE_ENABLED": False,
            "ANALISE_MATERIALIZACAO_GATE_POLL_SECONDS": 45,
            "ANALISE_MATERIALIZACAO_CHUNK_LEASE_SECONDS": 420,
            "ANALISE_MATERIALIZACAO_RECOVERY_SWEEP_SECONDS": 90,
            "ANALISE_MATERIALIZACAO_STALE_GRACE_SECONDS": 15,
            "ANALISE_MATERIALIZACAO_PENDING_RECOVERY_ENABLED": True,
            "ANALISE_MATERIALIZACAO_PENDING_RECOVERY_SWEEP_SECONDS": 75,
            "ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS": 12,
            "ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_REQUEUES": 6,
            "ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MIN_AGE_SECONDS": 180,
            "ANALISE_MATERIALIZACAO_BLOCKING_SYNC_STATUSES": "em_execucao",
            "INGESTION_RECOVERY_SWEEP_SECONDS": 75,
        }
    )
    assert settings.analise_materializacao_chunk_size == 40
    assert settings.analise_materializacao_max_active_campaigns == 3
    assert settings.analise_materializacao_max_active_chunks_per_campaign == 2
    assert settings.analise_materializacao_queue_name == "analise_materializacao"
    assert settings.analise_materializacao_dedup_window_seconds == 120
    assert settings.analise_materializacao_gate_enabled is False
    assert settings.analise_materializacao_gate_poll_seconds == 45
    assert settings.analise_materializacao_chunk_lease_seconds == 420
    assert settings.analise_materializacao_recovery_sweep_seconds == 90
    assert settings.analise_materializacao_stale_grace_seconds == 15
    assert settings.analise_materializacao_pending_recovery_enabled is True
    assert settings.analise_materializacao_pending_recovery_sweep_seconds == 75
    assert settings.analise_materializacao_pending_recovery_max_campaigns == 12
    assert settings.analise_materializacao_pending_recovery_max_requeues == 6
    assert settings.analise_materializacao_pending_recovery_min_age_seconds == 180
    assert settings.parse_csv_set(settings.analise_materializacao_blocking_sync_statuses) == {"em_execucao"}
    assert settings.ingestion_recovery_sweep_seconds == 75
