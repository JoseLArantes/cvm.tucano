from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionAttempt, IngestionRun
from app.services.ingestion.retry import (
    RetryableHttpStatus,
    RetryableIngestionError,
    TerminalIngestionError,
    classify_terminal_http_status,
    is_retryable_http_status,
)
from app.services.ingestion.staging import register_attempt


def _agora() -> datetime:
    return datetime.now(UTC)


def download_with_attempts(
    db: Session,
    *,
    url: str,
    ingestion_run: IngestionRun | None = None,
    task_id: str | None = None,
    downloader: Any | None = None,
    timeout: float = 300,
    attempt_number: int = 1,
    backoff_seconds: int = 60,
) -> tuple[bytes, IngestionAttempt]:
    downloader = downloader or (lambda: httpx.get(url, timeout=timeout))
    started_at = _agora()
    try:
        response = downloader()
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        attempt = register_attempt(
            db,
            ingestion_run=ingestion_run,
            task_id=task_id,
            operation="download",
            attempt_number=attempt_number,
            status="retryable_failure",
            error_type=type(exc).__name__,
            error_message=str(exc),
            next_retry_at=started_at + timedelta(seconds=backoff_seconds),
            started_at=started_at,
            finished_at=_agora(),
        )
        raise RetryableIngestionError(str(exc)) from exc

    if is_retryable_http_status(response.status_code):
        attempt = register_attempt(
            db,
            ingestion_run=ingestion_run,
            task_id=task_id,
            operation="download",
            attempt_number=attempt_number,
            status="retryable_failure",
            error_type="RetryableHttpStatus",
            error_message=f"HTTP {response.status_code}",
            next_retry_at=started_at + timedelta(seconds=backoff_seconds),
            started_at=started_at,
            finished_at=_agora(),
        )
        raise RetryableHttpStatus(status_code=response.status_code, url=url)

    if classify_terminal_http_status(response.status_code):
        attempt = register_attempt(
            db,
            ingestion_run=ingestion_run,
            task_id=task_id,
            operation="download",
            attempt_number=attempt_number,
            status="terminal_failure",
            error_type="TerminalHttpStatus",
            error_message=f"HTTP {response.status_code}",
            started_at=started_at,
            finished_at=_agora(),
        )
        raise TerminalIngestionError(f"http_status:{response.status_code}")

    response.raise_for_status()
    payload = response.content
    metadata = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content_length_bytes": len(payload),
        "etag": response.headers.get("etag"),
        "last_modified": response.headers.get("last-modified"),
        "http_status_code": response.status_code,
    }
    attempt = register_attempt(
        db,
        ingestion_run=ingestion_run,
        task_id=task_id,
        operation="download",
        attempt_number=attempt_number,
        status="success",
        started_at=started_at,
        finished_at=_agora(),
    )
    db.flush()
    attempt.error_message = str(metadata)
    return payload, attempt
