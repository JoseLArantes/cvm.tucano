"""add summary to analise materializacao controle

Revision ID: 20260625_001
Revises: 20260624_003
Create Date: 2026-06-25 13:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_001"
down_revision: str | None = "20260624_003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analise_materializacao_controle", sa.Column("summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analise_materializacao_controle", "summary")
