import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index(
            "ix_ingestion_runs_tipo_fonte_ano_status_started_at",
            "tipo_fonte",
            "ano",
            "status",
            "started_at",
        ),
    )

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
    remote_probe: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    change_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionPhaseExecution(Base):
    __tablename__ = "ingestion_phase_executions"
    __table_args__ = (
        Index(
            "ix_ingestion_phase_executions_run_phase_attempt",
            "ingestion_run_id",
            "phase",
            "attempt",
        ),
        Index(
            "ix_ingestion_phase_executions_status_heartbeat_at",
            "status",
            "heartbeat_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    execucao_sincronizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id", ondelete="SET NULL"), index=True
    )
    phase: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean)
    input_artifact_uri: Mapped[str | None] = mapped_column(String(1000))
    output_artifact_uri: Mapped[str | None] = mapped_column(String(1000))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionCancellationRequest(Base):
    __tablename__ = "ingestion_cancellation_requests"
    __table_args__ = (
        Index(
            "ix_ingestion_cancellation_requests_scope_type_scope_id",
            "scope_type",
            "scope_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scope_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    execucao_sincronizacao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id", ondelete="SET NULL"), index=True
    )
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), index=True
    )
    requested_by: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text)
    terminate_immediately: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    propagated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    affected_task_ids: Mapped[list[str] | None] = mapped_column(JSON)
    affected_execution_ids: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SourceArtifactSnapshot(Base):
    __tablename__ = "source_artifact_snapshots"
    __table_args__ = (
        Index(
            "ix_source_artifact_snapshots_tipo_fonte_ano_ingestion_run_id",
            "tipo_fonte",
            "ano",
            "ingestion_run_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), index=True, nullable=False
    )
    tipo_fonte: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    ano: Mapped[int | None] = mapped_column(Integer, index=True)
    resource_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    remote_etag: Mapped[str | None] = mapped_column(String(255))
    remote_last_modified: Mapped[str | None] = mapped_column(String(255))
    remote_content_length: Mapped[str | None] = mapped_column(String(255))
    package_metadata_modified: Mapped[str | None] = mapped_column(String(255))
    probe_sources: Mapped[list[str] | None] = mapped_column(JSON)
    probe_decision: Mapped[str | None] = mapped_column(String(32), index=True)
    probe_decision_reason: Mapped[str | None] = mapped_column(Text)
    probe_confidence: Mapped[str | None] = mapped_column(String(32))
    download_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sha_confirmation_result: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionFile(Base):
    __tablename__ = "ingestion_files"
    __table_args__ = (
        Index(
            "ix_ingestion_files_source_url_content_sha256",
            "source_url",
            "content_sha256",
        ),
    )

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
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_zip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    already_seen_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionFileMember(Base):
    __tablename__ = "ingestion_file_members"
    __table_args__ = (
        Index(
            "ix_ingestion_file_members_ingestion_file_id_member_name",
            "ingestion_file_id",
            "member_name",
        ),
        Index(
            "ix_ing_file_members_name_sha_file_id",
            "member_name",
            "member_sha256",
            "ingestion_file_id",
        ),
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SourceMemberSnapshot(Base):
    __tablename__ = "source_member_snapshots"
    __table_args__ = (
        Index(
            "ix_source_member_snapshots_artifact_snapshot_id_member_name",
            "artifact_snapshot_id",
            "member_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    artifact_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("source_artifact_snapshots.id"), index=True, nullable=False
    )
    ingestion_file_member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_file_members.id"), index=True
    )
    member_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    member_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    header_hash: Mapped[str | None] = mapped_column(String(64))
    header: Mapped[list[str] | None] = mapped_column(JSON)
    row_kind: Mapped[str | None] = mapped_column(String(80), index=True)
    destino_promovido: Mapped[str | None] = mapped_column(String(120))
    required_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schema_status: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_message: Mapped[str | None] = mapped_column(Text)
    delivery_index_role: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SourceDeliverySnapshot(Base):
    __tablename__ = "source_delivery_snapshots"
    __table_args__ = (
        Index(
            "ix_source_delivery_snapshots_member_snapshot_id_identity_hash",
            "member_snapshot_id",
            "identity_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    artifact_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("source_artifact_snapshots.id"), index=True, nullable=False
    )
    member_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("source_member_snapshots.id"), index=True
    )
    ingestion_file_member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_file_members.id"), index=True
    )
    member_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(32), index=True)
    codigo_cvm: Mapped[str | None] = mapped_column(String(32), index=True)
    id_documento: Mapped[str | None] = mapped_column(String(64), index=True)
    protocolo_entrega: Mapped[str | None] = mapped_column(String(128), index=True)
    data_referencia: Mapped[str | None] = mapped_column(String(32))
    data_entrega: Mapped[str | None] = mapped_column(String(32))
    versao: Mapped[str | None] = mapped_column(String(32))
    raw_identity: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionRow(Base):
    __tablename__ = "ingestion_rows"
    __table_args__ = (
        Index(
            "ix_ingestion_rows_ingestion_file_member_id_linha_origem",
            "ingestion_file_member_id",
            "linha_origem",
        ),
    )

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
    resolved_companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    resolution_method: Mapped[str | None] = mapped_column(String(64))
    resolution_confidence: Mapped[str | None] = mapped_column(String(32))
    promoted_entity: Mapped[str | None] = mapped_column(String(120))
    promoted_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IngestionAttempt(Base):
    __tablename__ = "ingestion_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ingestion_runs.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuarantineItem(Base):
    __tablename__ = "quarantine_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ingestion_runs.id"), index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionFileMemberPayload(Base):
    __tablename__ = "ingestion_file_member_payloads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id", ondelete="CASCADE"), primary_key=True
    )
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
