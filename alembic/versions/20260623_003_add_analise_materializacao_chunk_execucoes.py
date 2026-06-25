"""add_analise_materializacao_chunk_execucoes

Revision ID: 20260623_003
Revises: 20260623_002
Create Date: 2026-06-23 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260623_003"
down_revision: str | None = "20260623_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analise_materializacao_chunk_execucoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campanha_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("success_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campanha_id"], ["analise_materializacao_campanhas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_materializacao_chunk_execucoes_campanha_status",
        "analise_materializacao_chunk_execucoes",
        ["campanha_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_analise_materializacao_chunk_execucoes_lease_expires_at",
        "analise_materializacao_chunk_execucoes",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_chunk_execucoes_campanha_id"),
        "analise_materializacao_chunk_execucoes",
        ["campanha_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_chunk_execucoes_status"),
        "analise_materializacao_chunk_execucoes",
        ["status"],
        unique=False,
    )

    op.add_column("analise_materializacao_campanha_itens", sa.Column("chunk_execucao_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_analise_materializacao_campanha_itens_chunk_execucao_id"),
        "analise_materializacao_campanha_itens",
        ["chunk_execucao_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_analise_materializacao_campanha_itens_chunk_execucao_id",
        "analise_materializacao_campanha_itens",
        "analise_materializacao_chunk_execucoes",
        ["chunk_execucao_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("analise_materializacao_execucoes", sa.Column("chunk_execucao_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_chunk_execucao_id"),
        "analise_materializacao_execucoes",
        ["chunk_execucao_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_analise_materializacao_execucoes_chunk_execucao_id",
        "analise_materializacao_execucoes",
        "analise_materializacao_chunk_execucoes",
        ["chunk_execucao_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_analise_materializacao_execucoes_chunk_execucao_id",
        "analise_materializacao_execucoes",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_analise_materializacao_execucoes_chunk_execucao_id"), table_name="analise_materializacao_execucoes")
    op.drop_column("analise_materializacao_execucoes", "chunk_execucao_id")

    op.drop_constraint(
        "fk_analise_materializacao_campanha_itens_chunk_execucao_id",
        "analise_materializacao_campanha_itens",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_analise_materializacao_campanha_itens_chunk_execucao_id"), table_name="analise_materializacao_campanha_itens")
    op.drop_column("analise_materializacao_campanha_itens", "chunk_execucao_id")

    op.drop_index(op.f("ix_analise_materializacao_chunk_execucoes_status"), table_name="analise_materializacao_chunk_execucoes")
    op.drop_index(op.f("ix_analise_materializacao_chunk_execucoes_campanha_id"), table_name="analise_materializacao_chunk_execucoes")
    op.drop_index(
        "ix_analise_materializacao_chunk_execucoes_lease_expires_at",
        table_name="analise_materializacao_chunk_execucoes",
    )
    op.drop_index(
        "ix_analise_materializacao_chunk_execucoes_campanha_status",
        table_name="analise_materializacao_chunk_execucoes",
    )
    op.drop_table("analise_materializacao_chunk_execucoes")
