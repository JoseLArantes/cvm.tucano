"""add ingestion performance indexes

Revision ID: 20260626_001
Revises: 20260625_002
Create Date: 2026-06-26 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260626_001"
down_revision: str | None = "20260625_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ingestion_runs_tipo_fonte_ano_status_started_at",
        "ingestion_runs",
        ["tipo_fonte", "ano", "status", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_source_artifact_snapshots_tipo_fonte_ano_ingestion_run_id",
        "source_artifact_snapshots",
        ["tipo_fonte", "ano", "ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_files_source_url_content_sha256",
        "ingestion_files",
        ["source_url", "content_sha256"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_file_members_ingestion_file_id_member_name",
        "ingestion_file_members",
        ["ingestion_file_id", "member_name"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_file_members_member_name_member_sha256_ingestion_file_id",
        "ingestion_file_members",
        ["member_name", "member_sha256", "ingestion_file_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_member_snapshots_artifact_snapshot_id_member_name",
        "source_member_snapshots",
        ["artifact_snapshot_id", "member_name"],
        unique=False,
    )
    op.create_index(
        "ix_source_delivery_snapshots_member_snapshot_id_identity_hash",
        "source_delivery_snapshots",
        ["member_snapshot_id", "identity_hash"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_rows_ingestion_file_member_id_linha_origem",
        "ingestion_rows",
        ["ingestion_file_member_id", "linha_origem"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_rows_ingestion_file_member_id_linha_origem",
        table_name="ingestion_rows",
    )
    op.drop_index(
        "ix_source_delivery_snapshots_member_snapshot_id_identity_hash",
        table_name="source_delivery_snapshots",
    )
    op.drop_index(
        "ix_source_member_snapshots_artifact_snapshot_id_member_name",
        table_name="source_member_snapshots",
    )
    op.drop_index(
        "ix_ingestion_file_members_member_name_member_sha256_ingestion_file_id",
        table_name="ingestion_file_members",
    )
    op.drop_index(
        "ix_ingestion_file_members_ingestion_file_id_member_name",
        table_name="ingestion_file_members",
    )
    op.drop_index(
        "ix_ingestion_files_source_url_content_sha256",
        table_name="ingestion_files",
    )
    op.drop_index(
        "ix_source_artifact_snapshots_tipo_fonte_ano_ingestion_run_id",
        table_name="source_artifact_snapshots",
    )
    op.drop_index(
        "ix_ingestion_runs_tipo_fonte_ano_status_started_at",
        table_name="ingestion_runs",
    )
