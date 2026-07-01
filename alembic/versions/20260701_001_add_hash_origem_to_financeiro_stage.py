"""add hash_origem to financeiro typed staging

Revision ID: 20260701_001
Revises: 20260630_004
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260701_001"
down_revision: str | None = "20260630_004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_financeiro_stage_rows",
        sa.Column("hash_origem", sa.String(length=64), nullable=True),
    )
    op.execute("UPDATE ingestion_financeiro_stage_rows SET hash_origem = normalized_hash WHERE hash_origem IS NULL")
    op.alter_column("ingestion_financeiro_stage_rows", "hash_origem", nullable=False)
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_hash_origem",
        "ingestion_financeiro_stage_rows",
        ["hash_origem"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_financeiro_stage_rows_hash_origem", table_name="ingestion_financeiro_stage_rows")
    op.drop_column("ingestion_financeiro_stage_rows", "hash_origem")
