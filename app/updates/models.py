import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingUpdate(Base):
    __tablename__ = "pending_updates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fonte: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="change_detected")
    detection_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_probe_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probe_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    probe_last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    probe_content_length: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    artifact_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    change_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    change_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_successful_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    current_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_failed_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ingestion_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ingestion_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def content_changed(self) -> bool | None:
        total_changes = (self.change_summary or {}).get("total_changes")
        if isinstance(total_changes, int):
            return total_changes > 0
        return None

    @property
    def recommended_action(self) -> str:
        if self.status in {"change_detected", "analysis_failed"}:
            return "analyze"
        if self.status in {"analysis_queued", "analyzing"}:
            return "wait"
        if self.status == "ready_for_ingestion":
            return "ingest"
        if self.status == "content_unchanged":
            return "update_reference"
        return "none"

    @property
    def retryable(self) -> bool:
        if self.status != "ingestion_failed":
            return False
        result = self.ingestion_result or {}
        return result.get("retryable") is True

    @property
    def next_action(self) -> str:
        if self.status == "ingestion_failed":
            return "retry_ingestion" if self.retryable else "inspect_error"
        return self.recommended_action


class UpdateScanRun(Base):
    __tablename__ = "update_scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AcknowledgedArtifactReference(Base):
    __tablename__ = "acknowledged_artifact_references"
    __table_args__ = (
        UniqueConstraint(
            "pending_update_id",
            "resource_key",
            name="uq_acknowledged_artifact_reference_pending_resource",
        ),
        Index(
            "ix_acknowledged_artifact_reference_scope_confirmed",
            "fonte",
            "ano",
            "confirmed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pending_update_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pending_updates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baseline_ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fonte: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    resource_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_content_length: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    artifact_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    member_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmation_method: Mapped[str] = mapped_column(String(32), nullable=False, default="member_sha256")
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PendingUpdateMember(Base):
    __tablename__ = "pending_update_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pending_update_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pending_updates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    member_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    previous_member_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_member_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_header_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_header_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_category: Mapped[str] = mapped_column(String(32), nullable=False)
    change_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    row_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_analysis")


class UpdateSession(Base):
    __tablename__ = "update_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class UpdateSessionItem(Base):
    __tablename__ = "update_session_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("update_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pending_update_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pending_updates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
