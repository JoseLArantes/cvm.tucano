"""add_ingestion_lifecycle_snapshots

Revision ID: 20260616_002
Revises: 20260616_001
Create Date: 2026-06-16 00:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_002"
down_revision: str | None = "20260616_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_artifact_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_fonte", sa.String(length=50), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("resource_url", sa.String(length=1000), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("remote_etag", sa.String(length=255), nullable=True),
        sa.Column("remote_last_modified", sa.String(length=255), nullable=True),
        sa.Column("remote_content_length", sa.String(length=255), nullable=True),
        sa.Column("package_metadata_modified", sa.String(length=255), nullable=True),
        sa.Column("probe_sources", sa.JSON(), nullable=True),
        sa.Column("probe_decision", sa.String(length=32), nullable=True),
        sa.Column("probe_decision_reason", sa.Text(), nullable=True),
        sa.Column("probe_confidence", sa.String(length=32), nullable=True),
        sa.Column("download_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sha_confirmation_result", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_source_artifact_snapshots_ano"), "source_artifact_snapshots", ["ano"], unique=False)
    op.create_index(
        op.f("ix_source_artifact_snapshots_content_sha256"),
        "source_artifact_snapshots",
        ["content_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_artifact_snapshots_ingestion_run_id"),
        "source_artifact_snapshots",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_artifact_snapshots_probe_decision"),
        "source_artifact_snapshots",
        ["probe_decision"],
        unique=False,
    )
    op.create_index(op.f("ix_source_artifact_snapshots_status"), "source_artifact_snapshots", ["status"], unique=False)
    op.create_index(
        op.f("ix_source_artifact_snapshots_tipo_fonte"),
        "source_artifact_snapshots",
        ["tipo_fonte"],
        unique=False,
    )

    op.create_table(
        "source_member_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_file_member_id", sa.Uuid(), nullable=True),
        sa.Column("member_name", sa.String(length=255), nullable=False),
        sa.Column("member_sha256", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("header_hash", sa.String(length=64), nullable=True),
        sa.Column("header", sa.JSON(), nullable=True),
        sa.Column("row_kind", sa.String(length=80), nullable=True),
        sa.Column("destino_promovido", sa.String(length=120), nullable=True),
        sa.Column("required_member", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("schema_status", sa.String(length=32), nullable=False),
        sa.Column("schema_message", sa.Text(), nullable=True),
        sa.Column("delivery_index_role", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_snapshot_id"], ["source_artifact_snapshots.id"]),
        sa.ForeignKeyConstraint(["ingestion_file_member_id"], ["ingestion_file_members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_member_snapshots_artifact_snapshot_id"),
        "source_member_snapshots",
        ["artifact_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_member_snapshots_ingestion_file_member_id"),
        "source_member_snapshots",
        ["ingestion_file_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_member_snapshots_lifecycle_status"),
        "source_member_snapshots",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_member_snapshots_member_name"),
        "source_member_snapshots",
        ["member_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_member_snapshots_member_sha256"),
        "source_member_snapshots",
        ["member_sha256"],
        unique=False,
    )
    op.create_index(op.f("ix_source_member_snapshots_row_kind"), "source_member_snapshots", ["row_kind"], unique=False)

    op.create_table(
        "source_delivery_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("member_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_file_member_id", sa.Uuid(), nullable=True),
        sa.Column("member_name", sa.String(length=255), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=32), nullable=True),
        sa.Column("codigo_cvm", sa.String(length=32), nullable=True),
        sa.Column("id_documento", sa.String(length=64), nullable=True),
        sa.Column("protocolo_entrega", sa.String(length=128), nullable=True),
        sa.Column("data_referencia", sa.String(length=32), nullable=True),
        sa.Column("data_entrega", sa.String(length=32), nullable=True),
        sa.Column("versao", sa.String(length=32), nullable=True),
        sa.Column("raw_identity", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_snapshot_id"], ["source_artifact_snapshots.id"]),
        sa.ForeignKeyConstraint(["ingestion_file_member_id"], ["ingestion_file_members.id"]),
        sa.ForeignKeyConstraint(["member_snapshot_id"], ["source_member_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_artifact_snapshot_id"),
        "source_delivery_snapshots",
        ["artifact_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_cnpj_companhia"),
        "source_delivery_snapshots",
        ["cnpj_companhia"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_codigo_cvm"),
        "source_delivery_snapshots",
        ["codigo_cvm"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_id_documento"),
        "source_delivery_snapshots",
        ["id_documento"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_identity_hash"),
        "source_delivery_snapshots",
        ["identity_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_ingestion_file_member_id"),
        "source_delivery_snapshots",
        ["ingestion_file_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_member_name"),
        "source_delivery_snapshots",
        ["member_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_member_snapshot_id"),
        "source_delivery_snapshots",
        ["member_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_delivery_snapshots_protocolo_entrega"),
        "source_delivery_snapshots",
        ["protocolo_entrega"],
        unique=False,
    )
    op.create_index(op.f("ix_source_delivery_snapshots_status"), "source_delivery_snapshots", ["status"], unique=False)
    op.create_index(op.f("ix_source_delivery_snapshots_versao"), "source_delivery_snapshots", ["versao"], unique=False)

    op.create_table(
        "ingestion_reconcile_hashes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_file_member_id", sa.Uuid(), nullable=True),
        sa.Column("target_table", sa.String(length=120), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_file_member_id"], ["ingestion_file_members.id"]),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_ano_origem"),
        "ingestion_reconcile_hashes",
        ["ano_origem"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_arquivo_origem"),
        "ingestion_reconcile_hashes",
        ["arquivo_origem"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_hash_origem"),
        "ingestion_reconcile_hashes",
        ["hash_origem"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_ingestion_file_member_id"),
        "ingestion_reconcile_hashes",
        ["ingestion_file_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_ingestion_run_id"),
        "ingestion_reconcile_hashes",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_reconcile_hashes_target_table"),
        "ingestion_reconcile_hashes",
        ["target_table"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_reconcile_hashes_target_table"), table_name="ingestion_reconcile_hashes")
    op.drop_index(op.f("ix_ingestion_reconcile_hashes_ingestion_run_id"), table_name="ingestion_reconcile_hashes")
    op.drop_index(
        op.f("ix_ingestion_reconcile_hashes_ingestion_file_member_id"), table_name="ingestion_reconcile_hashes"
    )
    op.drop_index(op.f("ix_ingestion_reconcile_hashes_hash_origem"), table_name="ingestion_reconcile_hashes")
    op.drop_index(op.f("ix_ingestion_reconcile_hashes_arquivo_origem"), table_name="ingestion_reconcile_hashes")
    op.drop_index(op.f("ix_ingestion_reconcile_hashes_ano_origem"), table_name="ingestion_reconcile_hashes")
    op.drop_table("ingestion_reconcile_hashes")

    op.drop_index(op.f("ix_source_delivery_snapshots_versao"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_status"), table_name="source_delivery_snapshots")
    op.drop_index(
        op.f("ix_source_delivery_snapshots_protocolo_entrega"), table_name="source_delivery_snapshots"
    )
    op.drop_index(op.f("ix_source_delivery_snapshots_member_snapshot_id"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_member_name"), table_name="source_delivery_snapshots")
    op.drop_index(
        op.f("ix_source_delivery_snapshots_ingestion_file_member_id"), table_name="source_delivery_snapshots"
    )
    op.drop_index(op.f("ix_source_delivery_snapshots_identity_hash"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_id_documento"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_codigo_cvm"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_cnpj_companhia"), table_name="source_delivery_snapshots")
    op.drop_index(op.f("ix_source_delivery_snapshots_artifact_snapshot_id"), table_name="source_delivery_snapshots")
    op.drop_table("source_delivery_snapshots")

    op.drop_index(op.f("ix_source_member_snapshots_row_kind"), table_name="source_member_snapshots")
    op.drop_index(op.f("ix_source_member_snapshots_member_sha256"), table_name="source_member_snapshots")
    op.drop_index(op.f("ix_source_member_snapshots_member_name"), table_name="source_member_snapshots")
    op.drop_index(op.f("ix_source_member_snapshots_lifecycle_status"), table_name="source_member_snapshots")
    op.drop_index(
        op.f("ix_source_member_snapshots_ingestion_file_member_id"), table_name="source_member_snapshots"
    )
    op.drop_index(op.f("ix_source_member_snapshots_artifact_snapshot_id"), table_name="source_member_snapshots")
    op.drop_table("source_member_snapshots")

    op.drop_index(op.f("ix_source_artifact_snapshots_tipo_fonte"), table_name="source_artifact_snapshots")
    op.drop_index(op.f("ix_source_artifact_snapshots_status"), table_name="source_artifact_snapshots")
    op.drop_index(op.f("ix_source_artifact_snapshots_probe_decision"), table_name="source_artifact_snapshots")
    op.drop_index(
        op.f("ix_source_artifact_snapshots_ingestion_run_id"), table_name="source_artifact_snapshots"
    )
    op.drop_index(op.f("ix_source_artifact_snapshots_content_sha256"), table_name="source_artifact_snapshots")
    op.drop_index(op.f("ix_source_artifact_snapshots_ano"), table_name="source_artifact_snapshots")
    op.drop_table("source_artifact_snapshots")
