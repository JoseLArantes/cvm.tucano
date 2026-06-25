"""relax fre relacao subordinacao nome relacionado

Revision ID: 20260624_001
Revises: 20260623_004
Create Date: 2026-06-24 10:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260624_001"
down_revision: str | None = "20260623_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "fre_relacoes_subordinacao",
        "nome_pessoa_relacionada",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "fre_relacoes_subordinacao",
        "nome_pessoa_relacionada",
        existing_type=sa.Text(),
        nullable=False,
    )
