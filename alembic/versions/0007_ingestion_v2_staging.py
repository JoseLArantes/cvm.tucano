"""ingestion v2 staging

Revision ID: 0007_ingestion_v2_staging
Revises: 0006_stop_syncs
Create Date: 2026-06-03 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_ingestion_v2_staging"
down_revision: str | None = "0006_stop_syncs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=True),
        sa.Column("tipo_fonte", sa.String(length=50), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("requested_by_task_id", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("quality_summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_runs_ano"), "ingestion_runs", ["ano"], unique=False)
    op.create_index(
        op.f("ix_ingestion_runs_execucao_sincronizacao_id"),
        "ingestion_runs",
        ["execucao_sincronizacao_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_runs_requested_by_task_id"),
        "ingestion_runs",
        ["requested_by_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ingestion_runs_status"), "ingestion_runs", ["status"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_tipo_fonte"), "ingestion_runs", ["tipo_fonte"], unique=False)

    op.create_table(
        "ingestion_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_length_bytes", sa.Integer(), nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_modified", sa.String(length=255), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_zip", sa.Boolean(), nullable=False),
        sa.Column("already_seen_success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_url",
            "content_sha256",
            name="uq_ingestion_files_source_url_content_sha256",
        ),
    )
    op.create_index(op.f("ix_ingestion_files_content_sha256"), "ingestion_files", ["content_sha256"], unique=False)
    op.create_index(op.f("ix_ingestion_files_ingestion_run_id"), "ingestion_files", ["ingestion_run_id"], unique=False)
    op.create_index(op.f("ix_ingestion_files_source_filename"), "ingestion_files", ["source_filename"], unique=False)

    op.create_table(
        "ingestion_file_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_file_id", sa.Uuid(), nullable=False),
        sa.Column("member_name", sa.String(length=255), nullable=False),
        sa.Column("member_sha256", sa.String(length=64), nullable=False),
        sa.Column("member_size_bytes", sa.Integer(), nullable=False),
        sa.Column("encoding", sa.String(length=32), nullable=True),
        sa.Column("delimiter", sa.String(length=8), nullable=False),
        sa.Column("header", sa.JSON(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("schema_status", sa.String(length=32), nullable=False),
        sa.Column("schema_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_file_id"], ["ingestion_files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_file_id",
            "member_name",
            name="uq_ingestion_file_members_ingestion_file_id_member_name",
        ),
    )
    op.create_index(
        op.f("ix_ingestion_file_members_ingestion_file_id"),
        "ingestion_file_members",
        ["ingestion_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_file_members_member_name"), "ingestion_file_members", ["member_name"], unique=False
    )
    op.create_index(
        op.f("ix_ingestion_file_members_member_sha256"), "ingestion_file_members", ["member_sha256"], unique=False
    )

    op.create_table(
        "ingestion_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_file_member_id", sa.Uuid(), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=True),
        sa.Column("normalized_hash", sa.String(length=64), nullable=True),
        sa.Column("row_kind", sa.String(length=80), nullable=False),
        sa.Column("natural_key", sa.JSON(), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("validation_reason_code", sa.String(length=64), nullable=True),
        sa.Column("validation_details", sa.JSON(), nullable=True),
        sa.Column("resolved_companhia_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_method", sa.String(length=64), nullable=True),
        sa.Column("resolution_confidence", sa.String(length=32), nullable=True),
        sa.Column("promoted_entity", sa.String(length=120), nullable=True),
        sa.Column("promoted_entity_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_file_member_id"], ["ingestion_file_members.id"]),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.ForeignKeyConstraint(["resolved_companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_file_member_id",
            "linha_origem",
            name="uq_ingestion_rows_ingestion_file_member_id_linha_origem",
        ),
    )
    op.create_index(op.f("ix_ingestion_rows_ano_origem"), "ingestion_rows", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_ingestion_rows_arquivo_origem"), "ingestion_rows", ["arquivo_origem"], unique=False)
    op.create_index(
        op.f("ix_ingestion_rows_ingestion_file_member_id"), "ingestion_rows", ["ingestion_file_member_id"], unique=False
    )
    op.create_index(op.f("ix_ingestion_rows_ingestion_run_id"), "ingestion_rows", ["ingestion_run_id"], unique=False)
    op.create_index(
        op.f("ix_ingestion_rows_promoted_entity_id"), "ingestion_rows", ["promoted_entity_id"], unique=False
    )
    op.create_index(op.f("ix_ingestion_rows_raw_hash"), "ingestion_rows", ["raw_hash"], unique=False)
    op.create_index(
        op.f("ix_ingestion_rows_resolved_companhia_id"), "ingestion_rows", ["resolved_companhia_id"], unique=False
    )
    op.create_index(op.f("ix_ingestion_rows_row_kind"), "ingestion_rows", ["row_kind"], unique=False)
    op.create_index(
        op.f("ix_ingestion_rows_validation_reason_code"),
        "ingestion_rows",
        ["validation_reason_code"],
        unique=False,
    )
    op.create_index(op.f("ix_ingestion_rows_validation_status"), "ingestion_rows", ["validation_status"], unique=False)

    op.create_table(
        "ingestion_row_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_row_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_row_id"], ["ingestion_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_row_events_ingestion_row_id"),
        "ingestion_row_events",
        ["ingestion_row_id"],
        unique=False,
    )

    op.create_table(
        "ingestion_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_attempts_ingestion_run_id"),
        "ingestion_attempts",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ingestion_attempts_task_id"), "ingestion_attempts", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_attempts_task_id"), table_name="ingestion_attempts")
    op.drop_index(op.f("ix_ingestion_attempts_ingestion_run_id"), table_name="ingestion_attempts")
    op.drop_table("ingestion_attempts")

    op.drop_index(op.f("ix_ingestion_row_events_ingestion_row_id"), table_name="ingestion_row_events")
    op.drop_table("ingestion_row_events")

    op.drop_index(op.f("ix_ingestion_rows_validation_status"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_validation_reason_code"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_row_kind"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_resolved_companhia_id"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_raw_hash"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_promoted_entity_id"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_ingestion_run_id"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_ingestion_file_member_id"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_arquivo_origem"), table_name="ingestion_rows")
    op.drop_index(op.f("ix_ingestion_rows_ano_origem"), table_name="ingestion_rows")
    op.drop_table("ingestion_rows")

    op.drop_index(op.f("ix_ingestion_file_members_member_sha256"), table_name="ingestion_file_members")
    op.drop_index(op.f("ix_ingestion_file_members_member_name"), table_name="ingestion_file_members")
    op.drop_index(op.f("ix_ingestion_file_members_ingestion_file_id"), table_name="ingestion_file_members")
    op.drop_table("ingestion_file_members")

    op.drop_index(op.f("ix_ingestion_files_source_filename"), table_name="ingestion_files")
    op.drop_index(op.f("ix_ingestion_files_ingestion_run_id"), table_name="ingestion_files")
    op.drop_index(op.f("ix_ingestion_files_content_sha256"), table_name="ingestion_files")
    op.drop_table("ingestion_files")

    op.drop_index(op.f("ix_ingestion_runs_tipo_fonte"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_status"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_requested_by_task_id"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_execucao_sincronizacao_id"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_ano"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
