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
