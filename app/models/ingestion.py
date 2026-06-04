import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execucao_sincronizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True
    )
    tipo_fonte: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    ano: Mapped[int | None] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    quality_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionFile(Base):
    __tablename__ = "ingestion_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), index=True, nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content_length_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_zip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    already_seen_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionFileMember(Base):
    __tablename__ = "ingestion_file_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_files.id"), index=True, nullable=False
    )
    member_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    member_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    member_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    encoding: Mapped[str | None] = mapped_column(String(32))
    delimiter: Mapped[str] = mapped_column(String(8), nullable=False)
    header: Mapped[list[str] | None] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    schema_status: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionRow(Base):
    __tablename__ = "ingestion_rows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), index=True, nullable=False
    )
    ingestion_file_member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_file_members.id"), index=True, nullable=False
    )
    arquivo_origem: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    normalized_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    normalized_hash: Mapped[str | None] = mapped_column(String(64))
    row_kind: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    natural_key: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    validation_reason_code: Mapped[str | None] = mapped_column(String(64), index=True)
    validation_details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resolved_companhia_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("companhias.id"), index=True
    )
    resolution_method: Mapped[str | None] = mapped_column(String(64))
    resolution_confidence: Mapped[str | None] = mapped_column(String(32))
    promoted_entity: Mapped[str | None] = mapped_column(String(120))
    promoted_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionRowEvent(Base):
    __tablename__ = "ingestion_row_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_row_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_rows.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionAttempt(Base):
    __tablename__ = "ingestion_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuarantineItemV2(Base):
    __tablename__ = "quarantine_items_v2"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), index=True
    )
    ingestion_row_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_rows.id"), index=True, nullable=False, unique=True
    )
    execucao_sincronizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True
    )
    arquivo_origem: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    row_kind: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    motivo_codigo: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severidade: Mapped[str] = mapped_column(String(16), nullable=False)
    reparavel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diagnostico: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ultima_tentativa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tentativas_reprocessamento: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvido_por: Mapped[str | None] = mapped_column(String(120))
    ultimo_erro: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
