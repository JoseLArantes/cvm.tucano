"""widen demonstracoes valor_conta

Revision ID: 2a4b6c8d0e1f
Revises: 8e9f0a1b2c3d
Create Date: 2026-06-13 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a4b6c8d0e1f"
down_revision: str | None = "8e9f0a1b2c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "demonstracoes_financeiras",
        "valor_conta",
        existing_type=sa.Numeric(precision=30, scale=10),
        type_=sa.Numeric(precision=38, scale=10),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "demonstracoes_financeiras",
        "valor_conta",
        existing_type=sa.Numeric(precision=38, scale=10),
        type_=sa.Numeric(precision=30, scale=10),
        existing_nullable=True,
    )
