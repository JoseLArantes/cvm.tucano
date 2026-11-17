import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionQueueBatch(Base):
    __tablename__ = "ingestion_queue_batches"
    __table_args__ = (Index("ix_ingestion_queue_batches_requested_at", "requested_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requested_by: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="admin")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionQueueItem(Base):
    __tablename__ = "ingestion_queue_items"
    __table_args__ = (
        UniqueConstraint("execucao_sincronizacao_id", name="uq_ingestion_queue_item_execution"),
        UniqueConstraint("batch_id", "sequence", name="uq_ingestion_queue_item_batch_sequence"),
        Index("ix_ingestion_queue_items_status_kind_queued", "status", "kind", "queued_at"),
        Index("ix_ingestion_queue_items_batch_sequence", "batch_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_queue_batches.id", ondelete="CASCADE"), nullable=False
    )
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_args: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    task_kwargs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    reason_code: Mapped[str | None] = mapped_column(String(80))
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reservation_token: Mapped[str | None] = mapped_column(String(64), index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    publish_error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IngestionQueueControl(Base):
    __tablename__ = "ingestion_queue_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
