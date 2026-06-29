"""add ingestion operational state tables

Revision ID: 20260630_001
Revises: 20260626_002
Create Date: 2026-06-30 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260630_001"
down_revision: str | None = "20260626_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_phase_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=True),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("input_artifact_uri", sa.String(length=1000), nullable=True),
        sa.Column("output_artifact_uri", sa.String(length=1000), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_phase_executions_run_phase_attempt",
        "ingestion_phase_executions",
        ["ingestion_run_id", "phase", "attempt"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_phase_executions_status_heartbeat_at",
        "ingestion_phase_executions",
        ["status", "heartbeat_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_phase_executions_ingestion_run_id"),
        "ingestion_phase_executions",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_phase_executions_execucao_sincronizacao_id"),
        "ingestion_phase_executions",
        ["execucao_sincronizacao_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ingestion_phase_executions_phase"), "ingestion_phase_executions", ["phase"], unique=False)
    op.create_index(op.f("ix_ingestion_phase_executions_status"), "ingestion_phase_executions", ["status"], unique=False)
    op.create_index(op.f("ix_ingestion_phase_executions_task_id"), "ingestion_phase_executions", ["task_id"], unique=False)

    op.create_table(
        "ingestion_cancellation_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("terminate_immediately", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("propagated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected_task_ids", sa.JSON(), nullable=True),
        sa.Column("affected_execution_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_cancellation_requests_scope_type_scope_id",
        "ingestion_cancellation_requests",
        ["scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_cancellation_requests_execucao_sincronizacao_id"),
        "ingestion_cancellation_requests",
        ["execucao_sincronizacao_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_cancellation_requests_ingestion_run_id"),
        "ingestion_cancellation_requests",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_cancellation_requests_scope_id"),
        "ingestion_cancellation_requests",
        ["scope_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_cancellation_requests_scope_type"),
        "ingestion_cancellation_requests",
        ["scope_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_cancellation_requests_status"),
        "ingestion_cancellation_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_cancellation_requests_status"), table_name="ingestion_cancellation_requests")
    op.drop_index(op.f("ix_ingestion_cancellation_requests_scope_type"), table_name="ingestion_cancellation_requests")
    op.drop_index(op.f("ix_ingestion_cancellation_requests_scope_id"), table_name="ingestion_cancellation_requests")
    op.drop_index(
        op.f("ix_ingestion_cancellation_requests_ingestion_run_id"),
        table_name="ingestion_cancellation_requests",
    )
    op.drop_index(
        op.f("ix_ingestion_cancellation_requests_execucao_sincronizacao_id"),
        table_name="ingestion_cancellation_requests",
    )
    op.drop_index(
        "ix_ingestion_cancellation_requests_scope_type_scope_id",
        table_name="ingestion_cancellation_requests",
    )
    op.drop_table("ingestion_cancellation_requests")

    op.drop_index(op.f("ix_ingestion_phase_executions_task_id"), table_name="ingestion_phase_executions")
    op.drop_index(op.f("ix_ingestion_phase_executions_status"), table_name="ingestion_phase_executions")
    op.drop_index(op.f("ix_ingestion_phase_executions_phase"), table_name="ingestion_phase_executions")
    op.drop_index(
        op.f("ix_ingestion_phase_executions_execucao_sincronizacao_id"),
        table_name="ingestion_phase_executions",
    )
    op.drop_index(op.f("ix_ingestion_phase_executions_ingestion_run_id"), table_name="ingestion_phase_executions")
    op.drop_index("ix_ingestion_phase_executions_status_heartbeat_at", table_name="ingestion_phase_executions")
    op.drop_index("ix_ingestion_phase_executions_run_phase_attempt", table_name="ingestion_phase_executions")
    op.drop_table("ingestion_phase_executions")
