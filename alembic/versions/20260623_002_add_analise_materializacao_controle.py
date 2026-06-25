"""add_analise_materializacao_controle

Revision ID: 20260623_002
Revises: 20260623_001
Create Date: 2026-06-23 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260623_002"
down_revision: str | None = "20260623_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analise_materializacao_controle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO analise_materializacao_controle (id, mode, reason) VALUES (1, 'auto', NULL)"
        )
    )


def downgrade() -> None:
    op.drop_table("analise_materializacao_controle")
