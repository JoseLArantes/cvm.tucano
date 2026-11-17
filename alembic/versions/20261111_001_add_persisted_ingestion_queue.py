"""add persisted admission queue and transactional outbox"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261111_001"
down_revision: str | None = "20261110_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_queue_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_queue_batches_requested_at", "ingestion_queue_batches", ["requested_at"], unique=False
    )
    op.create_index(
        "ix_ingestion_queue_batches_status", "ingestion_queue_batches", ["status"], unique=False
    )

    op.create_table(
        "ingestion_queue_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("task_args", sa.JSON(), nullable=False),
        sa.Column("task_kwargs", sa.JSON(), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reservation_token", sa.String(length=64), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("publish_attempts", sa.Integer(), nullable=False),
        sa.Column("publish_error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["ingestion_queue_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execucao_sincronizacao_id", name="uq_ingestion_queue_item_execution"),
        sa.UniqueConstraint("batch_id", "sequence", name="uq_ingestion_queue_item_batch_sequence"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        "ix_ingestion_queue_items_status_kind_queued",
        "ingestion_queue_items",
        ["status", "kind", "queued_at"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_queue_items_batch_sequence", "ingestion_queue_items", ["batch_id", "sequence"], unique=False
    )
    op.create_index(
        "ix_ingestion_queue_items_status", "ingestion_queue_items", ["status"], unique=False
    )
    op.create_index(
        "ix_ingestion_queue_items_reservation_token", "ingestion_queue_items", ["reservation_token"], unique=False
    )
    op.create_table(
        "ingestion_queue_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text("INSERT INTO ingestion_queue_control (id, revision) VALUES (1, 0)"))


def downgrade() -> None:
    op.drop_table("ingestion_queue_control")
    op.drop_index("ix_ingestion_queue_items_reservation_token", table_name="ingestion_queue_items")
    op.drop_index("ix_ingestion_queue_items_status", table_name="ingestion_queue_items")
    op.drop_index("ix_ingestion_queue_items_batch_sequence", table_name="ingestion_queue_items")
    op.drop_index("ix_ingestion_queue_items_status_kind_queued", table_name="ingestion_queue_items")
    op.drop_table("ingestion_queue_items")
    op.drop_index("ix_ingestion_queue_batches_status", table_name="ingestion_queue_batches")
    op.drop_index("ix_ingestion_queue_batches_requested_at", table_name="ingestion_queue_batches")
    op.drop_table("ingestion_queue_batches")
