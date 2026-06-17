"""fix_codigo_cvm_auditor_to_string

Revision ID: 20260616_001
Revises: e768d8885a52
Create Date: 2026-06-16 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_001"
down_revision: str | None = "e768d8885a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "fre_auditores",
        "codigo_cvm_auditor",
        existing_type=sa.Integer(),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "fca_auditores",
        "codigo_cvm_auditor",
        existing_type=sa.Integer(),
        type_=sa.String(20),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "fca_auditores",
        "codigo_cvm_auditor",
        existing_type=sa.String(20),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "fre_auditores",
        "codigo_cvm_auditor",
        existing_type=sa.String(20),
        type_=sa.Integer(),
        existing_nullable=True,
    )
