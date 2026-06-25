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
            "ANALISE_MATERIALIZACAO_QUEUE_NAME": "analise_materializacao",
            "ANALISE_MATERIALIZACAO_DEDUP_WINDOW_SECONDS": 120,
            "ANALISE_MATERIALIZACAO_GATE_ENABLED": False,
            "ANALISE_MATERIALIZACAO_GATE_POLL_SECONDS": 45,
            "ANALISE_MATERIALIZACAO_CHUNK_LEASE_SECONDS": 420,
            "ANALISE_MATERIALIZACAO_RECOVERY_SWEEP_SECONDS": 90,
            "ANALISE_MATERIALIZACAO_STALE_GRACE_SECONDS": 15,
            "ANALISE_MATERIALIZACAO_BLOCKING_SYNC_STATUSES": "em_execucao,agendada",
        }
    )
    assert settings.analise_materializacao_chunk_size == 40
    assert settings.analise_materializacao_max_active_campaigns == 3
    assert settings.analise_materializacao_queue_name == "analise_materializacao"
    assert settings.analise_materializacao_dedup_window_seconds == 120
    assert settings.analise_materializacao_gate_enabled is False
    assert settings.analise_materializacao_gate_poll_seconds == 45
    assert settings.analise_materializacao_chunk_lease_seconds == 420
    assert settings.analise_materializacao_recovery_sweep_seconds == 90
    assert settings.analise_materializacao_stale_grace_seconds == 15
    assert settings.parse_csv_set(settings.analise_materializacao_blocking_sync_statuses) == {"em_execucao", "agendada"}
