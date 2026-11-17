import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.ingestion import IngestionAttempt, IngestionFile
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.acquisition import download_with_attempts
from app.services.ingestion.recovery import assess_ingestion_run_recovery
from app.services.ingestion.retry import (
    DependencyNotReady,
    RetryableHttpStatus,
    RetryableIngestionError,
    TerminalIngestionError,
    classify_terminal_http_status,
    is_retryable_http_status,
)
from app.services.ingestion.staging import create_run


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


class _Response:
    def __init__(self, status_code: int, content: bytes = b"ok") -> None:
        self.status_code = status_code
        self.content = content
        self.headers: dict[str, str] = {"etag": "abc", "last-modified": "today"}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "erro", request=httpx.Request("GET", "https://example.test"), response=httpx.Response(self.status_code)
            )


def test_retry_classification() -> None:
    assert is_retryable_http_status(408) is True
    assert is_retryable_http_status(429) is True
    assert is_retryable_http_status(503) is True
    assert is_retryable_http_status(404) is False
    assert classify_terminal_http_status(404) is True
    assert classify_terminal_http_status(400) is True
    assert classify_terminal_http_status(429) is False


def test_download_with_attempts_timeout_registers_retryable_failure() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="dfp", ano=2025)
        with pytest.raises(RetryableIngestionError):
            download_with_attempts(
                session,
                url="https://example.test/timeout",
                ingestion_run=run,
                downloader=lambda: (_ for _ in ()).throw(httpx.TimeoutException("timeout")),
            )
        attempt = session.query(IngestionAttempt).one()
        assert attempt.status == "retryable_failure"
        assert attempt.next_retry_at is not None
    finally:
        session.close()


def test_download_with_attempts_503_registers_retryable_http_status() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="dfp", ano=2025)
        with pytest.raises(RetryableHttpStatus):
            download_with_attempts(
                session,
                url="https://example.test/503",
                ingestion_run=run,
                downloader=lambda: _Response(503),
            )
        attempt = session.query(IngestionAttempt).one()
        assert attempt.status == "retryable_failure"
        assert attempt.error_type == "RetryableHttpStatus"
    finally:
        session.close()


def test_download_with_attempts_404_registers_terminal_failure() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="dfp", ano=2025)
        with pytest.raises(TerminalIngestionError):
            download_with_attempts(
                session,
                url="https://example.test/404",
                ingestion_run=run,
                downloader=lambda: _Response(404),
            )
        attempt = session.query(IngestionAttempt).one()
        assert attempt.status == "terminal_failure"
    finally:
        session.close()


def test_download_with_attempts_success_returns_payload_and_metadata() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="dfp", ano=2025)
        payload, attempt = download_with_attempts(
            session,
            url="https://example.test/ok",
            ingestion_run=run,
            downloader=lambda: _Response(200, b"conteudo"),
        )
        assert payload == b"conteudo"
        assert attempt.status == "success"
        assert "sha256" in (attempt.error_message or "")
    finally:
        session.close()


def test_dependency_not_ready_is_retryable_exception() -> None:
    assert isinstance(DependencyNotReady("deps"), RetryableIngestionError)


def test_member_recovery_requires_a_persisted_parent_file() -> None:
    session = _session()
    try:
        parent = ExecucaoSincronizacao(
            tipo_fonte="itr",
            ano=2023,
            arquivo="itr_cia_aberta_2023.zip",
            url="https://dados.cvm.gov.br/itr_2023.zip",
            status="sucesso",
        )
        session.add(parent)
        session.flush()
        child = ExecucaoSincronizacao(
            parent_execucao_id=parent.id,
            tipo_fonte="itr",
            ano=2023,
            arquivo="itr_cia_aberta_DMPL_ind_2023.csv",
            url="https://dados.cvm.gov.br/itr_2023.zip",
            status="falha",
        )
        session.add(child)
        session.flush()
        run = create_run(
            session,
            tipo_fonte="itr",
            ano=2023,
            execucao_sincronizacao_id=child.id,
            status="falha",
            phase="complete",
        )
        session.commit()

        unavailable = assess_ingestion_run_recovery(session, run=run)
        assert unavailable.eligible is False
        assert unavailable.reason_code == "NO_RECOVERY_SOURCE"

        parent_run = create_run(
            session,
            tipo_fonte="itr",
            ano=2023,
            execucao_sincronizacao_id=parent.id,
            status="sucesso",
            phase="complete",
        )
        session.add(
            IngestionFile(
                ingestion_run_id=parent_run.id,
                source_url=parent.url,
                source_filename=parent.arquivo,
                content_sha256="a" * 64,
                content_length_bytes=1,
                is_zip=True,
            )
        )
        session.commit()

        available = assess_ingestion_run_recovery(session, run=run)
        assert available.eligible is True
        assert available.strategy == "rerun_member_execution"
        assert available.reason_code == "MEMBER_EXECUTION_AVAILABLE"
    finally:
        session.close()
