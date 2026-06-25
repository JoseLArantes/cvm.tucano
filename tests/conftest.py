import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["TUCANO_CVM_TOKEN"] = "token-teste"

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import analise, companhia, fca, financeiro, fre, ingestion, sincronizacao, usuario  # noqa: F401
from app.worker.celery_app import celery_app

# Unit tests must not depend on an external Redis broker/backend.
celery_app.conf.broker_url = "memory://"
celery_app.conf.result_backend = "cache+memory://"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = local_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, headers={"Authorization": "Bearer token-teste"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()
