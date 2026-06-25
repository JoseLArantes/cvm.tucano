"""add_update_scan_runs

Revision ID: 20260621_001
Revises: f0be02acfa0a
Create Date: 2026-06-21 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260621_001"
down_revision: str | None = "f0be02acfa0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "update_scan_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_update_scan_runs_status"), "update_scan_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_update_scan_runs_status"), table_name="update_scan_runs")
    op.drop_table("update_scan_runs")
