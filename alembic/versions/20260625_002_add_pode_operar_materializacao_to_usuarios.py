"""add pode operar materializacao to usuarios

Revision ID: 20260625_002
Revises: 20260625_001
Create Date: 2026-06-25 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_002"
down_revision: str | None = "20260625_001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("pode_operar_materializacao", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("usuarios", "pode_operar_materializacao", server_default=None)


def downgrade() -> None:
    op.drop_column("usuarios", "pode_operar_materializacao")
