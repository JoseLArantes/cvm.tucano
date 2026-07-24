"""add persisted ingestion-control contracts

Revision ID: 20260720_001
Revises: 20260715_001
Create Date: 2026-07-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_001"
down_revision: str | Sequence[str] | None = "20260715_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_dispatch_plans",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("token", sa.String(96), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False), sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("strategy", sa.String(32), nullable=False), sa.Column("force_reimport", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token"),
    )
    op.create_index("ix_ingestion_dispatch_plans_owner_expires", "ingestion_dispatch_plans", ["requested_by", "expires_at"])
    op.create_table(
        "ingestion_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False), sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False), sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("requested_by", "operation", "idempotency_key", name="uq_ingestion_idempotency_actor_operation_key"),
    )
    op.create_index("ix_ingestion_idempotency_expires", "ingestion_idempotency_records", ["expires_at"])
    op.create_table(
        "ingestion_operation_audits",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(64), nullable=False), sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False), sa.Column("reason", sa.Text(), nullable=True), sa.Column("consequence", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_operation_audits_scope_created", "ingestion_operation_audits", ["scope_type", "scope_id", "created_at"])
    for column in (
        sa.Column("current_execution_id", sa.Uuid(), nullable=True), sa.Column("current_run_id", sa.Uuid(), nullable=True),
        sa.Column("last_failed_run_id", sa.Uuid(), nullable=True), sa.Column("ingestion_task_id", sa.String(64), nullable=True),
        sa.Column("ingestion_result", sa.JSON(), nullable=True),
    ):
        op.add_column("pending_updates", column)
    op.create_foreign_key("fk_pending_updates_current_execution", "pending_updates", "execucoes_sincronizacao", ["current_execution_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_pending_updates_current_run", "pending_updates", "ingestion_runs", ["current_run_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_pending_updates_last_failed_run", "pending_updates", "ingestion_runs", ["last_failed_run_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_pending_updates_current_execution_id", "pending_updates", ["current_execution_id"])
    op.create_index("ix_pending_updates_current_run_id", "pending_updates", ["current_run_id"])
    op.create_index("ix_pending_updates_last_failed_run_id", "pending_updates", ["last_failed_run_id"])
    op.create_index("ix_pending_updates_ingestion_task_id", "pending_updates", ["ingestion_task_id"])


def downgrade() -> None:
    for name in ("ix_pending_updates_ingestion_task_id", "ix_pending_updates_last_failed_run_id", "ix_pending_updates_current_run_id", "ix_pending_updates_current_execution_id"):
        op.drop_index(name, table_name="pending_updates")
    for name in ("fk_pending_updates_last_failed_run", "fk_pending_updates_current_run", "fk_pending_updates_current_execution"):
        op.drop_constraint(name, "pending_updates", type_="foreignkey")
    for name in ("ingestion_result", "ingestion_task_id", "last_failed_run_id", "current_run_id", "current_execution_id"):
        op.drop_column("pending_updates", name)
    op.drop_index("ix_ingestion_operation_audits_scope_created", table_name="ingestion_operation_audits")
    op.drop_table("ingestion_operation_audits")
    op.drop_index("ix_ingestion_idempotency_expires", table_name="ingestion_idempotency_records")
    op.drop_table("ingestion_idempotency_records")
    op.drop_index("ix_ingestion_dispatch_plans_owner_expires", table_name="ingestion_dispatch_plans")
    op.drop_table("ingestion_dispatch_plans")
