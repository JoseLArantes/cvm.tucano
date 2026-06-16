from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionAttempt, IngestionFile, IngestionRun
from app.services.ingestion.dedup import STATUSS_REAPROVEITAVEIS_EXECUCAO
from app.services.ingestion.retry import (
    RetryableHttpStatus,
    RetryableIngestionError,
    TerminalIngestionError,
    classify_terminal_http_status,
    is_retryable_http_status,
)
from app.services.ingestion.staging import register_attempt

_DATASET_SLUG_BY_FONTE: dict[str, str] = {
    "cadastro": "cia_aberta-cad",
    "dfp": "cia_aberta-doc-dfp",
    "itr": "cia_aberta-doc-itr",
    "fre": "cia_aberta-doc-fre",
    "fca": "cia_aberta-doc-fca",
    "ipe": "cia_aberta-doc-ipe",
    "vlmo": "cia_aberta-doc-vlmo",
    "cgvn": "cia_aberta-doc-cgvn",
}


def _agora() -> datetime:
    return datetime.now(UTC)


def _normalize_header_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dataset_url_for_fonte(fonte: str) -> str | None:
    slug = _DATASET_SLUG_BY_FONTE.get(fonte)
    if slug is None:
        return None
    return f"https://dados.cvm.gov.br/dataset/{slug}"


def _latest_successful_reference(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    current_run_id: Any,
) -> tuple[IngestionRun | None, IngestionFile | None]:
    previous_run = db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano == ano,
            IngestionRun.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
            IngestionRun.id != current_run_id,
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    if previous_run is None:
        return None, None
    previous_file = db.scalar(
        select(IngestionFile)
        .where(IngestionFile.ingestion_run_id == previous_run.id)
        .order_by(IngestionFile.downloaded_at.desc())
        .limit(1)
    )
    return previous_run, previous_file


def _fetch_ckan_package_metadata(dataset_url: str, *, timeout: float) -> dict[str, Any] | None:
    slug = dataset_url.rstrip("/").rsplit("/", 1)[-1]
    api_url = f"https://dados.cvm.gov.br/api/3/action/package_show?id={slug}"
    try:
        response = httpx.get(api_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    if not payload.get("success"):
        return None
    result = payload.get("result") or {}
    return {
        "dataset_url": dataset_url,
        "api_url": api_url,
        "package_metadata_modified": result.get("metadata_modified"),
    }


def _head_remote_resource(source_url: str, *, timeout: float) -> dict[str, Any]:
    try:
        response = httpx.head(source_url, timeout=timeout, follow_redirects=True)
    except Exception as exc:
        return {
            "source_url": source_url,
            "probe_sources": ["head"],
            "head_error": type(exc).__name__,
            "head_error_message": str(exc),
        }

    return {
        "source_url": source_url,
        "probe_sources": ["head"],
        "resource_etag": _normalize_header_value(response.headers.get("etag")),
        "resource_last_modified": _normalize_header_value(response.headers.get("last-modified")),
        "resource_content_length": _normalize_header_value(response.headers.get("content-length")),
        "resource_http_status_code": response.status_code,
    }


def probe_remote_source(
    db: Session,
    *,
    run: IngestionRun,
    tipo_fonte: str,
    ano: int | None,
    source_url: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    dataset_url = _dataset_url_for_fonte(tipo_fonte)
    probe: dict[str, Any] = {
        "dataset_url": dataset_url,
        "resource_url": source_url,
        "probe_sources": [],
        "decision": "unknown",
        "decision_reason": "metadata_indisponivel",
        "confidence": "unknown",
        "download_required": True,
    }

    if dataset_url is not None:
        ckan_payload = _fetch_ckan_package_metadata(dataset_url, timeout=timeout)
        if ckan_payload is not None:
            probe.update(ckan_payload)
            probe["probe_sources"] = list(dict.fromkeys([*probe["probe_sources"], "ckan"]))

    head_payload = _head_remote_resource(source_url, timeout=timeout)
    for key, value in head_payload.items():
        if key == "probe_sources":
            probe["probe_sources"] = list(dict.fromkeys([*probe["probe_sources"], *value]))
            continue
        probe[key] = value

    previous_run, previous_file = _latest_successful_reference(
        db,
        tipo_fonte=tipo_fonte,
        ano=ano,
        current_run_id=run.id,
    )
    previous_probe = previous_run.remote_probe if previous_run is not None and previous_run.remote_probe else {}
    previous_reference = {
        "resource_etag": previous_file.etag if previous_file is not None else None,
        "resource_last_modified": previous_file.last_modified if previous_file is not None else None,
        "resource_content_length": (
            str(previous_file.content_length_bytes) if previous_file is not None and previous_file.content_length_bytes else None
        ),
        "package_metadata_modified": previous_probe.get("package_metadata_modified"),
    }
    probe["previous_reference"] = previous_reference

    def _same(field: str) -> bool:
        current_value = probe.get(field)
        previous_value = previous_reference.get(field)
        return current_value is not None and previous_value is not None and current_value == previous_value

    def _different(field: str) -> bool:
        current_value = probe.get(field)
        previous_value = previous_reference.get(field)
        return current_value is not None and previous_value is not None and current_value != previous_value

    if previous_run is None:
        probe["decision"] = "changed"
        probe["decision_reason"] = "sem_referencia_anterior"
        probe["confidence"] = "unknown"
        probe["download_required"] = True
    elif _different("resource_etag"):
        probe["decision"] = "changed"
        probe["decision_reason"] = "metadata_changed:resource_etag"
        probe["confidence"] = "strong"
        probe["download_required"] = True
    elif _same("resource_etag"):
        probe["decision"] = "unchanged"
        probe["decision_reason"] = "metadata_matched:resource_etag"
        probe["confidence"] = "strong"
        probe["download_required"] = False
    elif _different("resource_last_modified") or _different("resource_content_length"):
        changed_fields = [
            field
            for field in ("resource_last_modified", "resource_content_length")
            if _different(field)
        ]
        probe["decision"] = "changed"
        probe["decision_reason"] = f"metadata_changed:{','.join(changed_fields)}"
        probe["confidence"] = "medium"
        probe["download_required"] = True
    elif _same("resource_last_modified") and _same("resource_content_length"):
        probe["decision"] = "unchanged"
        probe["decision_reason"] = "metadata_matched:resource_last_modified,resource_content_length"
        probe["confidence"] = "medium"
        probe["download_required"] = False
    elif _different("package_metadata_modified"):
        probe["decision"] = "changed"
        probe["decision_reason"] = "metadata_changed:package_metadata_modified"
        probe["confidence"] = "weak"
        probe["download_required"] = True
    elif _same("package_metadata_modified"):
        probe["decision"] = "unknown"
        probe["decision_reason"] = "metadata_matched_weak:package_metadata_modified"
        probe["confidence"] = "weak"
        probe["download_required"] = True
    else:
        probe["decision"] = "unknown"
        probe["decision_reason"] = "metadados_inconclusivos"
        probe["confidence"] = "unknown"
        probe["download_required"] = True

    return probe


def annotate_probe_with_sha_confirmation(
    probe: dict[str, Any] | None,
    *,
    current_sha256: str,
    previous_sha256: str | None,
) -> dict[str, Any]:
    payload = dict(probe or {})
    if previous_sha256 is None:
        payload["sha_confirmation_result"] = "sem_referencia_anterior"
        return payload
    payload["sha_confirmation_result"] = "equal" if current_sha256 == previous_sha256 else "different"
    if current_sha256 == previous_sha256:
        payload["download_required"] = True
    return payload


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
        register_attempt(
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
        register_attempt(
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
        register_attempt(
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
