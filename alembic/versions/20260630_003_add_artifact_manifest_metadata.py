"""add artifact manifest metadata

Revision ID: 20260630_003
Revises: 20260630_002
Create Date: 2026-06-30 23:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260630_003"
down_revision: str | None = "20260630_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_artifact_snapshots", sa.Column("storage_uri", sa.String(length=1000), nullable=True))
    op.add_column("source_artifact_snapshots", sa.Column("storage_role", sa.String(length=64), nullable=True))
    op.add_column(
        "source_artifact_snapshots",
        sa.Column("storage_content_type", sa.String(length=255), nullable=True),
    )
    op.add_column("source_artifact_snapshots", sa.Column("storage_size_bytes", sa.Integer(), nullable=True))

    op.add_column("source_member_snapshots", sa.Column("raw_artifact_uri", sa.String(length=1000), nullable=True))
    op.add_column(
        "source_member_snapshots",
        sa.Column("raw_artifact_content_type", sa.String(length=255), nullable=True),
    )
    op.add_column("source_member_snapshots", sa.Column("raw_artifact_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "source_member_snapshots",
        sa.Column("normalized_artifact_uri", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "source_member_snapshots",
        sa.Column("normalized_artifact_format", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "source_member_snapshots",
        sa.Column("normalized_artifact_content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "source_member_snapshots",
        sa.Column("normalized_artifact_size_bytes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_member_snapshots", "normalized_artifact_size_bytes")
    op.drop_column("source_member_snapshots", "normalized_artifact_content_sha256")
    op.drop_column("source_member_snapshots", "normalized_artifact_format")
    op.drop_column("source_member_snapshots", "normalized_artifact_uri")
    op.drop_column("source_member_snapshots", "raw_artifact_size_bytes")
    op.drop_column("source_member_snapshots", "raw_artifact_content_type")
    op.drop_column("source_member_snapshots", "raw_artifact_uri")

    op.drop_column("source_artifact_snapshots", "storage_size_bytes")
    op.drop_column("source_artifact_snapshots", "storage_content_type")
    op.drop_column("source_artifact_snapshots", "storage_role")
    op.drop_column("source_artifact_snapshots", "storage_uri")
