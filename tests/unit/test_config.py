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
