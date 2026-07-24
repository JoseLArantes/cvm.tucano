"""add acknowledged artifact references

Revision ID: 20260715_001
Revises: 20260713_001
Create Date: 2026-07-15 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_001"
down_revision: str | Sequence[str] | None = "20260713_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "acknowledged_artifact_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pending_update_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("fonte", sa.String(length=50), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("resource_url", sa.String(length=1000), nullable=False),
        sa.Column("resource_key", sa.String(length=64), nullable=False),
        sa.Column("remote_etag", sa.String(length=255), nullable=True),
        sa.Column("remote_last_modified", sa.String(length=255), nullable=True),
        sa.Column("remote_content_length", sa.BigInteger(), nullable=True),
        sa.Column("artifact_content_sha256", sa.String(length=64), nullable=True),
        sa.Column("member_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("confirmation_method", sa.String(length=32), nullable=False),
        sa.Column("confirmed_by", sa.String(length=64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_ingestion_run_id"],
            ["ingestion_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pending_update_id"],
            ["pending_updates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pending_update_id",
            "resource_key",
            name="uq_acknowledged_artifact_reference_pending_resource",
        ),
    )
    op.create_index(
        op.f("ix_acknowledged_artifact_references_ano"),
        "acknowledged_artifact_references",
        ["ano"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acknowledged_artifact_references_baseline_ingestion_run_id"),
        "acknowledged_artifact_references",
        ["baseline_ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acknowledged_artifact_references_fonte"),
        "acknowledged_artifact_references",
        ["fonte"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acknowledged_artifact_references_pending_update_id"),
        "acknowledged_artifact_references",
        ["pending_update_id"],
        unique=False,
    )
    op.create_index(
        "ix_acknowledged_artifact_reference_scope_confirmed",
        "acknowledged_artifact_references",
        ["fonte", "ano", "confirmed_at"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            UPDATE pending_updates
            SET status = 'content_unchanged'
            WHERE status = 'ready_for_ingestion'
              AND change_summary IS NOT NULL
              AND COALESCE((change_summary ->> 'total_changes')::integer, -1) = 0
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            UPDATE pending_updates
            SET status = 'ready_for_ingestion'
            WHERE status IN ('content_unchanged', 'reference_updated')
            """
        )
    op.drop_index(
        "ix_acknowledged_artifact_reference_scope_confirmed",
        table_name="acknowledged_artifact_references",
    )
    op.drop_index(
        op.f("ix_acknowledged_artifact_references_pending_update_id"),
        table_name="acknowledged_artifact_references",
    )
    op.drop_index(
        op.f("ix_acknowledged_artifact_references_fonte"),
        table_name="acknowledged_artifact_references",
    )
    op.drop_index(
        op.f("ix_acknowledged_artifact_references_baseline_ingestion_run_id"),
        table_name="acknowledged_artifact_references",
    )
    op.drop_index(
        op.f("ix_acknowledged_artifact_references_ano"),
        table_name="acknowledged_artifact_references",
    )
    op.drop_table("acknowledged_artifact_references")
