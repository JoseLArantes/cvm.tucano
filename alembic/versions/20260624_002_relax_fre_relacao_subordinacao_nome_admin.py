"""relax fre relacao subordinacao nome administrador

Revision ID: 20260624_002
Revises: 20260624_001
Create Date: 2026-06-24 10:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260624_002"
down_revision: str | None = "20260624_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "fre_relacoes_subordinacao",
        "nome_administrador",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "fre_relacoes_subordinacao",
        "nome_administrador",
        existing_type=sa.Text(),
        nullable=False,
    )
