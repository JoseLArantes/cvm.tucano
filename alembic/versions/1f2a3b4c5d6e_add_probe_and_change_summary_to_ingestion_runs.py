"""add_probe_and_change_summary_to_ingestion_runs

Revision ID: 1f2a3b4c5d6e
Revises: 2a4b6c8d0e1f
Create Date: 2026-06-13 12:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1f2a3b4c5d6e"
down_revision: str | None = "2a4b6c8d0e1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("remote_probe", sa.JSON(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("change_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_runs", "change_summary")
    op.drop_column("ingestion_runs", "remote_probe")
