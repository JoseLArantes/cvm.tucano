"""ampliar grupo demonstracao financeiro

Revision ID: 0005_grupo_demo_fin
Revises: 0004_usuarios
Create Date: 2026-06-03 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_grupo_demo_fin"
down_revision: str | None = "0004_usuarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "demonstracoes_financeiras",
        "grupo_demonstracao",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "demonstracoes_financeiras",
        "grupo_demonstracao",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
