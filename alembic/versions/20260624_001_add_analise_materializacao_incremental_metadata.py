"""add_analise_materializacao_incremental_metadata

Revision ID: 20260624_003
Revises: 20260624_002
Create Date: 2026-06-24 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260624_003"
down_revision: str | None = "20260624_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analise_materializacao_execucoes",
        sa.Column("materialization_mode", sa.String(length=20), nullable=False, server_default="full"),
    )
    op.add_column(
        "analise_materializacao_execucoes",
        sa.Column("invalidated_from", sa.Date(), nullable=True),
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_invalidated_from"),
        "analise_materializacao_execucoes",
        ["invalidated_from"],
        unique=False,
    )
    op.add_column(
        "analise_materializacao_campanha_itens",
        sa.Column("invalidated_from", sa.Date(), nullable=True),
    )
    op.create_index(
        op.f("ix_analise_materializacao_campanha_itens_invalidated_from"),
        "analise_materializacao_campanha_itens",
        ["invalidated_from"],
        unique=False,
    )
    op.alter_column("analise_materializacao_execucoes", "materialization_mode", server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analise_materializacao_campanha_itens_invalidated_from"),
        table_name="analise_materializacao_campanha_itens",
    )
    op.drop_column("analise_materializacao_campanha_itens", "invalidated_from")
    op.drop_index(
        op.f("ix_analise_materializacao_execucoes_invalidated_from"),
        table_name="analise_materializacao_execucoes",
    )
    op.drop_column("analise_materializacao_execucoes", "invalidated_from")
    op.drop_column("analise_materializacao_execucoes", "materialization_mode")
