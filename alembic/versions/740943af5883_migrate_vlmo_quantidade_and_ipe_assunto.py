"""migrate_vlmo_quantidade_and_ipe_assunto

Revision ID: 740943af5883
Revises: 4ecc5fa20efb
Create Date: 2026-06-08 22:12:16.962703
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "740943af5883"
down_revision: str | None = "4ecc5fa20efb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ipe_documentos",
        "assunto",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
    op.alter_column(
        "vlmo_consolidado",
        "quantidade",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "vlmo_consolidado",
        "quantidade",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=True,
    )
    op.alter_column(
        "ipe_documentos",
        "assunto",
        existing_type=sa.String(length=1000),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
