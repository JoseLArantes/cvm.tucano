from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import and_, delete, insert, or_, select
from sqlalchemy.orm import Session, aliased, load_only

from app.models.ingestion import (
    IngestionAttempt,
    IngestionFile,
    IngestionFileMember,
    IngestionFileMemberPayload,
    IngestionRow,
    IngestionRowEvent,
    IngestionRun,
    QuarantineItem,
)
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.dedup import STATUSS_REAPROVEITAVEIS_EXECUCAO

DEFAULT_CSV_DELIMITER = ";"
DEFAULT_ROW_VALIDATION_STATUS = "pending"
DEFAULT_MEMBER_SCHEMA_STATUS = "ok"
_ROW_KINDS_WITH_LINE_FALLBACK = {"fre_relacao_familiar"}


def _agora() -> datetime:
    return datetime.now(UTC)


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strip_balancing_quotes(value: str) -> str:
    return value.strip('"')


def _read_csv_line(
    line: str,
    *,
    delimiter: str,
    quoting: Literal[0, 1, 2, 3, 4, 5] = csv.QUOTE_MINIMAL,
) -> list[str]:
    return next(csv.reader([line], delimiter=delimiter, quoting=quoting))


def _read_csv_rows_with_fallback(
    text: str,
    *,
    delimiter: str,
    row_kind: str | None = None,
) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    lines = text.splitlines()
    if not lines:
        return [], []
    header = _read_csv_line(lines[0], delimiter=delimiter)
    rows: list[tuple[int, dict[str, str]]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        parsed = _read_csv_line(line, delimiter=delimiter)
        if row_kind in _ROW_KINDS_WITH_LINE_FALLBACK and (
            len(parsed) != len(header) or line.count('"') % 2 == 1
        ):
            parsed = [
                _strip_balancing_quotes(value)
                for value in _read_csv_line(line, delimiter=delimiter, quoting=csv.QUOTE_NONE)
            ]
        row_dict = cast(dict[str, str], dict(zip(header, parsed, strict=False)))
        rows.append((line_number, row_dict))
    return header, rows


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
    row_kind: str | None = None,
) -> tuple[list[str], list[tuple[int, dict[str, str]]], str]:
    text, encoding = decode_csv_payload(payload)
    if row_kind in _ROW_KINDS_WITH_LINE_FALLBACK:
        header, rows = _read_csv_rows_with_fallback(text, delimiter=delimiter, row_kind=row_kind)
        return header, rows, encoding
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = list(reader.fieldnames or [])
    rows = [(line_number, row) for line_number, row in enumerate(reader, start=2)]
    return header, rows, encoding


def iter_csv_rows(
    payload: bytes,
    *,
    delimiter: str = DEFAULT_CSV_DELIMITER,
    row_kind: str | None = None,
) -> tuple[list[str], Iterator[tuple[int, dict[str, str]]], str]:
    text, encoding = decode_csv_payload(payload)
    if row_kind in _ROW_KINDS_WITH_LINE_FALLBACK:
        header, rows = _read_csv_rows_with_fallback(text, delimiter=delimiter, row_kind=row_kind)

        def _iter_fallback() -> Iterator[tuple[int, dict[str, str]]]:
            yield from rows

        return header, _iter_fallback(), encoding
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = list(reader.fieldnames or [])

    def _iter() -> Iterator[tuple[int, dict[str, str]]]:
        yield from enumerate(reader, start=2)

    return header, _iter(), encoding


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
    remote_probe: dict[str, Any] | None = None,
    change_summary: dict[str, Any] | None = None,
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
    if remote_probe is not None:
        run.remote_probe = remote_probe
    if change_summary is not None:
        run.change_summary = change_summary
    if finished_at is not None:
        run.finished_at = finished_at
    return run


def register_file(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    source_url: str,
    source_filename: str,
    payload: bytes | None = None,
    content_sha256: str | None = None,
    content_length_bytes: int | None = None,
    http_status_code: int | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    is_zip: bool = False,
    already_seen_success: bool = False,
) -> IngestionFile:
    sha = content_sha256 or (_sha256_hex(payload) if payload else "")
    length = content_length_bytes or (len(payload) if payload else 0)
    existing = db.scalar(
        select(IngestionFile).where(
            IngestionFile.source_url == source_url,
            IngestionFile.content_sha256 == sha,
        )
    )
    if existing is not None:
        existing_run = db.get(IngestionRun, existing.ingestion_run_id)
        if existing_run is not None and existing_run.status not in set(STATUSS_REAPROVEITAVEIS_EXECUCAO):
            member_ids_stmt = select(IngestionFileMember.id).where(IngestionFileMember.ingestion_file_id == existing.id)
            row_ids_stmt = select(IngestionRow.id).where(
                (IngestionRow.ingestion_run_id == existing_run.id) |
                (IngestionRow.ingestion_file_member_id.in_(member_ids_stmt))
            )
            db.execute(delete(QuarantineItem).where(QuarantineItem.ingestion_row_id.in_(row_ids_stmt)))
            db.execute(delete(QuarantineItem).where(QuarantineItem.ingestion_run_id == existing_run.id))
            db.execute(
                delete(IngestionRowEvent).where(
                    IngestionRowEvent.ingestion_row_id.in_(row_ids_stmt)
                )
            )
            db.execute(delete(IngestionRow).where(
                (IngestionRow.ingestion_run_id == existing_run.id) |
                (IngestionRow.ingestion_file_member_id.in_(member_ids_stmt))
            ))
            db.execute(delete(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == existing.id))
            db.execute(delete(IngestionAttempt).where(IngestionAttempt.ingestion_run_id == existing_run.id))
            db.execute(delete(IngestionFile).where(IngestionFile.id == existing.id))
            db.flush()

    ingestion_file = IngestionFile(
        ingestion_run_id=ingestion_run.id,
        source_url=source_url,
        source_filename=source_filename,
        content_sha256=sha,
        content_length_bytes=length,
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
    payload: bytes | None = None,
    member_sha256: str | None = None,
    member_size_bytes: int | None = None,
    header: list[str] | None,
    row_count: int,
    encoding: str | None,
    delimiter: str = DEFAULT_CSV_DELIMITER,
    schema_status: str = DEFAULT_MEMBER_SCHEMA_STATUS,
    schema_message: str | None = None,
) -> IngestionFileMember:
    sha256 = member_sha256 or (_sha256_hex(payload) if payload else "")
    size = member_size_bytes or (len(payload) if payload else 0)

    # Check if there is an existing member
    existing_member = db.scalar(
        select(IngestionFileMember)
        .where(IngestionFileMember.ingestion_file_id == ingestion_file.id)
        .where(IngestionFileMember.member_name == member_name)
    )
    if existing_member is not None:
        existing_member.member_sha256 = sha256
        existing_member.member_size_bytes = size
        existing_member.encoding = encoding
        existing_member.delimiter = delimiter
        existing_member.header = header
        existing_member.row_count = row_count
        existing_member.schema_status = schema_status
        existing_member.schema_message = schema_message

        # Clear any existing rows for this member to prevent UniqueViolation on retry
        row_ids_stmt = select(IngestionRow.id).where(
            IngestionRow.ingestion_file_member_id == existing_member.id
        )
        db.execute(delete(QuarantineItem).where(QuarantineItem.ingestion_row_id.in_(row_ids_stmt)))
        db.execute(delete(IngestionRowEvent).where(IngestionRowEvent.ingestion_row_id.in_(row_ids_stmt)))
        db.execute(delete(IngestionRow).where(IngestionRow.ingestion_file_member_id == existing_member.id))

        db.flush()
        return existing_member

    member = IngestionFileMember(
        ingestion_file_id=ingestion_file.id,
        member_name=member_name,
        member_sha256=sha256,
        member_size_bytes=size,
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


def save_member_payload(db: Session, execution_id: Any, payload: bytes) -> None:
    member_payload = db.scalar(
        select(IngestionFileMemberPayload).where(
            IngestionFileMemberPayload.id == execution_id
        )
    )
    if member_payload is None:
        member_payload = IngestionFileMemberPayload(
            id=execution_id,
            payload=payload
        )
        db.add(member_payload)
    else:
        member_payload.payload = payload
    db.flush()


def get_member_payload(db: Session, execution_id: Any) -> bytes:
    payload_obj = db.scalar(
        select(IngestionFileMemberPayload).where(
            IngestionFileMemberPayload.id == execution_id
        )
    )
    if payload_obj is None:
        raise ValueError(f"Payload not found for execution: {execution_id}")
    return payload_obj.payload


def delete_member_payload(db: Session, execution_id: Any) -> None:
    db.execute(
        delete(IngestionFileMemberPayload).where(
            IngestionFileMemberPayload.id == execution_id
        )
    )
    db.flush()


def member_has_successful_match(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    member_name: str,
    member_sha256: str,
    current_run_id: uuid.UUID,
) -> bool:
    return find_reusable_member_match(
        db,
        tipo_fonte=tipo_fonte,
        ano=ano,
        member_name=member_name,
        member_sha256=member_sha256,
        current_run_id=current_run_id,
    ) is not None


def find_reusable_member_match(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    member_name: str,
    member_sha256: str,
    current_run_id: uuid.UUID,
) -> dict[str, Any] | None:
    parent_execucao = aliased(ExecucaoSincronizacao)
    child_execucao = aliased(ExecucaoSincronizacao)
    existing_member = db.execute(
        select(IngestionFileMember)
        .add_columns(
            IngestionRun.status.label("parent_run_status"),
            parent_execucao.status.label("parent_execucao_status"),
            child_execucao.id.label("child_execucao_id"),
            child_execucao.status.label("child_execucao_status"),
        )
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
        .outerjoin(parent_execucao, parent_execucao.id == IngestionRun.execucao_sincronizacao_id)
        .outerjoin(
            child_execucao,
            and_(
                child_execucao.parent_execucao_id == parent_execucao.id,
                child_execucao.tipo_execucao == "arquivo_membro",
                child_execucao.arquivo == IngestionFileMember.member_name,
                child_execucao.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
            ),
        )
        .where(
            IngestionRun.tipo_fonte == tipo_fonte,
            IngestionRun.ano == ano,
            IngestionRun.id != current_run_id,
            IngestionFileMember.member_name == member_name,
            IngestionFileMember.member_sha256 == member_sha256,
            or_(
                IngestionRun.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
                child_execucao.id.is_not(None),
            ),
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    ).first()
    if existing_member is None:
        return None

    member, parent_run_status, parent_execucao_status, child_execucao_id, child_execucao_status = existing_member
    matched_via = (
        "parent_run"
        if parent_run_status in STATUSS_REAPROVEITAVEIS_EXECUCAO
        else "child_execution"
    )
    return {
        "member_id": str(member.id),
        "parent_run_status": parent_run_status,
        "parent_execucao_status": parent_execucao_status,
        "child_execucao_id": None if child_execucao_id is None else str(child_execucao_id),
        "child_execucao_status": child_execucao_status,
        "matched_via": matched_via,
        "reused_from_failed_parent": matched_via == "child_execution" and parent_execucao_status == "falha",
    }


def _build_ingestion_row_payload(
    *,
    ingestion_run: IngestionRun,
    ingestion_file_member: IngestionFileMember,
    arquivo_origem: str,
    ano_origem: int | None,
    row_kind: str,
    rows: list[tuple[int, dict[str, str]]],
    validation_status: str,
) -> list[dict[str, Any]]:
    return [
        {
            "id": uuid.uuid4(),
            "ingestion_run_id": ingestion_run.id,
            "ingestion_file_member_id": ingestion_file_member.id,
            "arquivo_origem": arquivo_origem,
            "ano_origem": ano_origem,
            "linha_origem": line_number,
            "raw_data": raw_data,
            "raw_hash": _sha256_hex(_serialize_json_bytes(raw_data)),
            "row_kind": row_kind,
            "validation_status": validation_status,
        }
        for line_number, raw_data in rows
    ]


def _should_use_postgres_copy(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _copy_rows_postgres(db: Session, *, payload: list[dict[str, Any]]) -> None:
    if not payload:
        return
    sa_connection = db.connection()
    proxied = sa_connection.connection
    raw_connection = getattr(proxied, "driver_connection", proxied)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", quotechar='"', lineterminator="\n")
    for item in payload:
        writer.writerow(
            [
                str(item["id"]),
                str(item["ingestion_run_id"]),
                str(item["ingestion_file_member_id"]),
                item["arquivo_origem"],
                "\\N" if item["ano_origem"] is None else item["ano_origem"],
                item["linha_origem"],
                _serialize_json_bytes(item["raw_data"]).decode("utf-8"),
                item["raw_hash"],
                item["row_kind"],
                item["validation_status"],
            ]
        )
    buffer.seek(0)
    copy_sql = """
        COPY ingestion_rows (
            id,
            ingestion_run_id,
            ingestion_file_member_id,
            arquivo_origem,
            ano_origem,
            linha_origem,
            raw_data,
            raw_hash,
            row_kind,
            validation_status
        )
        FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')
    """
    cursor = raw_connection.cursor()
    try:
        with cursor.copy(copy_sql) as copy:
            copy.write(buffer.getvalue())
    finally:
        cursor.close()


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
    fetch_inserted_rows: bool = True,
    use_copy: bool | None = None,
) -> list[IngestionRow]:
    if not rows:
        return []
    payload = _build_ingestion_row_payload(
        ingestion_run=ingestion_run,
        ingestion_file_member=ingestion_file_member,
        arquivo_origem=arquivo_origem,
        ano_origem=ano_origem,
        row_kind=row_kind,
        rows=rows,
        validation_status=validation_status,
    )
    should_use_copy = (
        _should_use_postgres_copy(db)
        if use_copy is None
        else (use_copy and _should_use_postgres_copy(db))
    )
    if should_use_copy:
        _copy_rows_postgres(db, payload=payload)
    else:
        db.execute(insert(IngestionRow), payload)
    db.flush()
    if not fetch_inserted_rows:
        return []
    return list(
        db.execute(
            select(IngestionRow)
            .where(IngestionRow.ingestion_file_member_id == ingestion_file_member.id)
            .order_by(IngestionRow.linha_origem.asc())
        ).scalars()
    )


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
    return event


def purge_member_success_rows(
    db: Session,
    *,
    ingestion_file_member_id: Any,
) -> int:
    db.flush()
    row_ids_stmt = (
        select(IngestionRow.id)
        .where(
            IngestionRow.ingestion_file_member_id == ingestion_file_member_id,
            ~IngestionRow.id.in_(select(QuarantineItem.ingestion_row_id)),
        )
    )
    db.execute(delete(IngestionRowEvent).where(IngestionRowEvent.ingestion_row_id.in_(row_ids_stmt)))
    deleted_rows = db.execute(
        delete(IngestionRow).where(
            IngestionRow.ingestion_file_member_id == ingestion_file_member_id,
            ~IngestionRow.id.in_(select(QuarantineItem.ingestion_row_id)),
        )
    )
    db.flush()
    rowcount = getattr(deleted_rows, "rowcount", None)
    return int(rowcount if rowcount is not None else 0)


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


def formatar_tamanho(bytes_qty: int) -> str:
    valor = float(bytes_qty)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if valor < 1024.0:
            return f"{valor:.2f} {unit}"
        valor /= 1024.0
    return f"{valor:.2f} PB"


def _log_file_analysis(member: IngestionFileMember) -> None:
    pass


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
    header, rows, encoding = read_staged_csv_rows(payload, delimiter=delimiter, row_kind=row_kind)
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
    _log_file_analysis(member)
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


def stage_csv_payload_streaming(
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
    chunk_size: int = 5_000,
    use_copy: bool | None = None,
) -> IngestionFileMember:
    header, row_iter, encoding = iter_csv_rows(payload, delimiter=delimiter, row_kind=row_kind)
    member = register_member(
        db,
        ingestion_file=ingestion_file,
        member_name=member_name,
        payload=payload,
        header=header,
        row_count=0,
        encoding=encoding,
        delimiter=delimiter,
    )
    total_rows = 0
    chunk: list[tuple[int, dict[str, str]]] = []
    for line_number, raw_data in row_iter:
        chunk.append((line_number, raw_data))
        total_rows += 1
        if len(chunk) >= chunk_size:
            insert_rows(
                db,
                ingestion_run=ingestion_run,
                ingestion_file_member=member,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                row_kind=row_kind,
                rows=chunk,
                fetch_inserted_rows=False,
                use_copy=use_copy,
            )
            chunk = []
    if chunk:
        insert_rows(
            db,
            ingestion_run=ingestion_run,
            ingestion_file_member=member,
            arquivo_origem=arquivo_origem,
            ano_origem=ano_origem,
            row_kind=row_kind,
            rows=chunk,
            fetch_inserted_rows=False,
            use_copy=use_copy,
        )
    member.row_count = total_rows
    _log_file_analysis(member)
    return member


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


def iter_staged_member_chunks(
    db: Session,
    *,
    member_id: Any,
    chunk_size: int,
) -> Iterator[list[IngestionRow]]:
    last_line: int | None = None
    while True:
        query = (
            select(IngestionRow)
            .options(
                load_only(
                    IngestionRow.id,
                    IngestionRow.ingestion_run_id,
                    IngestionRow.arquivo_origem,
                    IngestionRow.ano_origem,
                    IngestionRow.linha_origem,
                    IngestionRow.raw_data,
                    IngestionRow.row_kind,
                )
            )
            .where(IngestionRow.ingestion_file_member_id == member_id)
            .order_by(IngestionRow.linha_origem.asc())
            .limit(chunk_size)
        )
        if last_line is not None:
            query = query.where(IngestionRow.linha_origem > last_line)
        rows = list(db.execute(query).scalars())
        if not rows:
            break
        yield rows
        last_line = rows[-1].linha_origem
        for row in rows:
            db.expunge(row)


def iter_zip_csv_members(payload: bytes) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member_name in archive.namelist():
            if not member_name.endswith(".csv"):
                continue
            members.append((member_name, archive.read(member_name)))
    return members


def _serialize_json_bytes(payload: dict[str, Any]) -> bytes:

    # json.dumps with sort_keys=True fails if any dict key is None at any level.
    # Coerce all keys to strings recursively to avoid TypeError.
    def _stringify_keys(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): _stringify_keys(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_stringify_keys(item) for item in obj]
        return obj

    return json.dumps(_stringify_keys(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")


def read_staged_csv_rows_from_disk(
    file_path: str,
    encoding: str,
    *,
    delimiter: str = DEFAULT_CSV_DELIMITER,
) -> tuple[list[str], list[tuple[int, dict[str, str]]], str]:
    with open(file_path, encoding=encoding, errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        header = list(reader.fieldnames or [])
        rows = [(line_number, row) for line_number, row in enumerate(reader, start=2)]
    return header, rows, encoding


def iter_csv_rows_from_disk(
    file_path: str,
    encoding: str,
    *,
    delimiter: str = DEFAULT_CSV_DELIMITER,
) -> tuple[list[str], Iterator[tuple[int, dict[str, str]]], str]:
    f = open(file_path, encoding=encoding, errors="replace")
    try:
        reader = csv.DictReader(f, delimiter=delimiter)
        header = list(reader.fieldnames or [])
    except Exception:
        f.close()
        raise

    def _iter() -> Iterator[tuple[int, dict[str, str]]]:
        try:
            yield from enumerate(reader, start=2)
        finally:
            f.close()

    return header, _iter(), encoding


def stage_csv_payload_streaming_from_disk(
    db: Session,
    *,
    ingestion_run: IngestionRun,
    ingestion_file: IngestionFile,
    file_path: str,
    member_name: str,
    arquivo_origem: str,
    ano_origem: int | None,
    row_kind: str,
    member_sha256: str,
    member_size_bytes: int,
    encoding: str,
    delimiter: str = DEFAULT_CSV_DELIMITER,
    chunk_size: int = 5_000,
    use_copy: bool | None = None,
) -> IngestionFileMember:
    header, row_iter, encoding = iter_csv_rows_from_disk(file_path, encoding, delimiter=delimiter)
    member = register_member(
        db,
        ingestion_file=ingestion_file,
        member_name=member_name,
        member_sha256=member_sha256,
        member_size_bytes=member_size_bytes,
        header=header,
        row_count=0,
        encoding=encoding,
        delimiter=delimiter,
    )
    total_rows = 0
    chunk: list[tuple[int, dict[str, str]]] = []
    for line_number, raw_data in row_iter:
        chunk.append((line_number, raw_data))
        total_rows += 1
        if len(chunk) >= chunk_size:
            insert_rows(
                db,
                ingestion_run=ingestion_run,
                ingestion_file_member=member,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                row_kind=row_kind,
                rows=chunk,
                fetch_inserted_rows=False,
                use_copy=use_copy,
            )
            chunk = []
    if chunk:
        insert_rows(
            db,
            ingestion_run=ingestion_run,
            ingestion_file_member=member,
            arquivo_origem=arquivo_origem,
            ano_origem=ano_origem,
            row_kind=row_kind,
            rows=chunk,
            fetch_inserted_rows=False,
            use_copy=use_copy,
        )
    member.row_count = total_rows
    _log_file_analysis(member)
    return member


def safe_promote_chunk(
    db: Session,
    *,
    promote_func: Any,
    linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
    execucao_id: Any,
    contadores: dict[str, int],
    registrar_quarentena_fn: Any,
    **kwargs: Any,
) -> None:
    nested = None
    try:
        nested = db.begin_nested()
        chunk_contadores = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        promote_func(
            db,
            linhas_promovidas=linhas_promovidas,
            execucao_id=execucao_id,
            contadores=chunk_contadores,
            **kwargs,
        )
        nested.commit()
        for k, v in chunk_contadores.items():
            contadores[k] = contadores.get(k, 0) + v
    except Exception:
        if nested is not None:
            nested.rollback()
        
        from app.services.ingestion.quarantine import create_quarantine_item
        from app.services.ingestion.validation import invalid_result, write_validation_result
        
        for row, dados in linhas_promovidas:
            row_nested = None
            try:
                row_nested = db.begin_nested()
                row_contadores = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
                promote_func(
                    db,
                    linhas_promovidas=[(row, dados)],
                    execucao_id=execucao_id,
                    contadores=row_contadores,
                    **kwargs,
                )
                row_nested.commit()
                for k, v in row_contadores.items():
                    contadores[k] = contadores.get(k, 0) + v
            except Exception as row_exc:
                if row_nested is not None:
                    row_nested.rollback()
                
                result = invalid_result(
                    "normalizacao_invalida",
                    details={"erro": f"Erro de banco durante promocao: {row_exc}"},
                    repairable=False,
                )
                write_validation_result(db, ingestion_row=row, result=result)
                create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=execucao_id,
                    legacy_reason=f"erro_banco: {row_exc}",
                )
                registrar_quarentena_fn(
                    db,
                    execucao_id=execucao_id,
                    arquivo_origem=row.arquivo_origem,
                    ano_origem=row.ano_origem,
                    linha_origem=row.linha_origem,
                    motivo=f"normalizacao_invalida: erro_banco: {row_exc}",
                    dados_originais=row.raw_data,
                )
                contadores["rejeitados"] = contadores.get("rejeitados", 0) + 1
