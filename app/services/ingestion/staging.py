from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.ingestion import (
    IngestionAttempt,
    IngestionFile,
    IngestionFileMember,
    IngestionRow,
    IngestionRowEvent,
    IngestionRun,
)

DEFAULT_CSV_DELIMITER = ";"
DEFAULT_ROW_VALIDATION_STATUS = "pending"
DEFAULT_MEMBER_SCHEMA_STATUS = "ok"


def _agora() -> datetime:
    return datetime.now(UTC)


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_csv_payload(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def read_staged_csv_rows(
    payload: bytes,
    *,
    delimiter: str = DEFAULT_CSV_DELIMITER,
) -> tuple[list[str], list[tuple[int, dict[str, str]]], str]:
    text, encoding = decode_csv_payload(payload)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = list(reader.fieldnames or [])
    rows = [(line_number, row) for line_number, row in enumerate(reader, start=2)]
    return header, rows, encoding


def create_run(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    status: str = "em_execucao",
    phase: str = "acquire",
    execucao_sincronizacao_id: Any = None,
    requested_by_task_id: str | None = None,
    message: str | None = None,
    quality_summary: dict[str, Any] | None = None,
) -> IngestionRun:
    run = IngestionRun(
        execucao_sincronizacao_id=execucao_sincronizacao_id,
        tipo_fonte=tipo_fonte,
        ano=ano,
        status=status,
        phase=phase,
        requested_by_task_id=requested_by_task_id,
        message=message,
        quality_summary=quality_summary,
    )
    db.add(run)
    db.flush()
    return run


def update_run_state(
    run: IngestionRun,
    *,
    status: str | None = None,
    phase: str | None = None,
    message: str | None = None,
    quality_summary: dict[str, Any] | None = None,
    finished_at: datetime | None = None,
) -> IngestionRun:
    if status is not None:
        run.status = status
    if phase is not None:
        run.phase = phase
    if message is not None:
        run.message = message
    if quality_summary is not None:
        run.quality_summary = quality_summary
    if finished_at is not None:
        run.finished_at = finished_at
    return run


def register_file(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    source_url: str,
    source_filename: str,
    payload: bytes,
    http_status_code: int | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    is_zip: bool = False,
    already_seen_success: bool = False,
) -> IngestionFile:
    ingestion_file = IngestionFile(
        ingestion_run_id=ingestion_run.id,
        source_url=source_url,
        source_filename=source_filename,
        content_sha256=_sha256_hex(payload),
        content_length_bytes=len(payload),
        http_status_code=http_status_code,
        etag=etag,
        last_modified=last_modified,
        is_zip=is_zip,
        already_seen_success=already_seen_success,
    )
    db.add(ingestion_file)
    db.flush()
    return ingestion_file


def register_member(
    db: Session,
    *,
    ingestion_file: IngestionFile,
    member_name: str,
    payload: bytes,
    header: list[str] | None,
    row_count: int,
    encoding: str | None,
    delimiter: str = DEFAULT_CSV_DELIMITER,
    schema_status: str = DEFAULT_MEMBER_SCHEMA_STATUS,
    schema_message: str | None = None,
) -> IngestionFileMember:
    member = IngestionFileMember(
        ingestion_file_id=ingestion_file.id,
        member_name=member_name,
        member_sha256=_sha256_hex(payload),
        member_size_bytes=len(payload),
        encoding=encoding,
        delimiter=delimiter,
        header=header,
        row_count=row_count,
        schema_status=schema_status,
        schema_message=schema_message,
    )
    db.add(member)
    db.flush()
    return member


def insert_rows(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    ingestion_file_member: IngestionFileMember,
    arquivo_origem: str,
    ano_origem: int | None,
    row_kind: str,
    rows: list[tuple[int, dict[str, str]]],
    validation_status: str = DEFAULT_ROW_VALIDATION_STATUS,
) -> list[IngestionRow]:
    inserted_rows: list[IngestionRow] = []
    for line_number, raw_data in rows:
        inserted_rows.append(
            IngestionRow(
                ingestion_run_id=ingestion_run.id,
                ingestion_file_member_id=ingestion_file_member.id,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                linha_origem=line_number,
                raw_data=raw_data,
                raw_hash=_sha256_hex(_serialize_json_bytes(raw_data)),
                row_kind=row_kind,
                validation_status=validation_status,
            )
        )
    db.add_all(inserted_rows)
    db.flush()
    return inserted_rows


def update_row_validation(
    row: IngestionRow,
    *,
    validation_status: str,
    validation_reason_code: str | None = None,
    validation_details: dict[str, Any] | None = None,
    normalized_data: dict[str, Any] | None = None,
    normalized_hash: str | None = None,
    natural_key: dict[str, Any] | None = None,
) -> IngestionRow:
    row.validation_status = validation_status
    row.validation_reason_code = validation_reason_code
    row.validation_details = validation_details
    row.normalized_data = normalized_data
    row.normalized_hash = normalized_hash
    row.natural_key = natural_key
    return row


def register_row_event(
    db: Session,
    *,
    ingestion_row: IngestionRow,
    event_type: str,
    event_payload: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> IngestionRowEvent:
    event = IngestionRowEvent(
        ingestion_row_id=ingestion_row.id,
        event_type=event_type,
        event_payload=event_payload,
        created_by=created_by,
    )
    db.add(event)
    db.flush()
    return event


def register_attempt(
    db: Session,
    *,
    operation: str,
    attempt_number: int,
    status: str,
    ingestion_run: IngestionRun | None = None,
    task_id: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    next_retry_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IngestionAttempt:
    attempt = IngestionAttempt(
        ingestion_run_id=ingestion_run.id if ingestion_run is not None else None,
        task_id=task_id,
        operation=operation,
        attempt_number=attempt_number,
        status=status,
        error_type=error_type,
        error_message=error_message,
        next_retry_at=next_retry_at,
        started_at=started_at or _agora(),
        finished_at=finished_at,
    )
    db.add(attempt)
    db.flush()
    return attempt


def stage_csv_payload(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    ingestion_file: IngestionFile,
    payload: bytes,
    member_name: str,
    arquivo_origem: str,
    ano_origem: int | None,
    row_kind: str,
    delimiter: str = DEFAULT_CSV_DELIMITER,
) -> tuple[IngestionFileMember, list[IngestionRow]]:
    header, rows, encoding = read_staged_csv_rows(payload, delimiter=delimiter)
    member = register_member(
        db,
        ingestion_file=ingestion_file,
        member_name=member_name,
        payload=payload,
        header=header,
        row_count=len(rows),
        encoding=encoding,
        delimiter=delimiter,
    )
    inserted_rows = insert_rows(
        db,
        ingestion_run=ingestion_run,
        ingestion_file_member=member,
        arquivo_origem=arquivo_origem,
        ano_origem=ano_origem,
        row_kind=row_kind,
        rows=rows,
    )
    return member, inserted_rows


def stage_zip_payload(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    ingestion_file: IngestionFile,
    payload: bytes,
    ano_origem: int | None,
    row_kind_by_member: dict[str, str],
    delimiter: str = DEFAULT_CSV_DELIMITER,
) -> list[tuple[IngestionFileMember, list[IngestionRow]]]:
    staged_members: list[tuple[IngestionFileMember, list[IngestionRow]]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member_name in archive.namelist():
            if not member_name.endswith(".csv"):
                continue
            member_payload = archive.read(member_name)
            staged_members.append(
                stage_csv_payload(
                    db,
                    ingestion_run=ingestion_run,
                    ingestion_file=ingestion_file,
                    payload=member_payload,
                    member_name=member_name,
                    arquivo_origem=member_name,
                    ano_origem=ano_origem,
                    row_kind=row_kind_by_member.get(member_name, "desconhecido"),
                    delimiter=delimiter,
                )
            )
    return staged_members


def _serialize_json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
