"""add materialization execution reconciliation

Revision ID: 20260723_001
Revises: 20260721_001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_001"
down_revision: str | None = "20260721_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analise_materializacao_execucoes",
        sa.Column("task_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_task_id"),
        "analise_materializacao_execucoes",
        ["task_id"],
        unique=False,
    )
    op.create_table(
        "analise_materializacao_reconciliacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execucao_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reconciled_by", sa.String(length=128), nullable=False),
        sa.Column("reason_code", sa.String(length=96), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execucao_id"],
            ["analise_materializacao_execucoes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analise_materializacao_reconciliacoes_execucao_id"),
        "analise_materializacao_reconciliacoes",
        ["execucao_id"],
        unique=False,
    )
    op.create_index(
        "ix_analise_materializacao_reconciliacoes_execucao_created",
        "analise_materializacao_reconciliacoes",
        ["execucao_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analise_materializacao_reconciliacoes_execucao_created",
        table_name="analise_materializacao_reconciliacoes",
    )
    op.drop_index(
        op.f("ix_analise_materializacao_reconciliacoes_execucao_id"),
        table_name="analise_materializacao_reconciliacoes",
    )
    op.drop_table("analise_materializacao_reconciliacoes")
    op.drop_index(
        op.f("ix_analise_materializacao_execucoes_task_id"),
        table_name="analise_materializacao_execucoes",
    )
    op.drop_column("analise_materializacao_execucoes", "task_id")
