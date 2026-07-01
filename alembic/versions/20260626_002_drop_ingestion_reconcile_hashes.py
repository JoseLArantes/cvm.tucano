"""drop ingestion_reconcile_hashes

Revision ID: 20260626_002
Revises: 20260626_001
Create Date: 2026-06-26 14:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260626_002"
down_revision: str | Sequence[str] | None = "20260626_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ingestion_reconcile_hashes" not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes("ingestion_reconcile_hashes")}
    for index_name in (
        "ix_ingestion_reconcile_hashes_scope_hash",
        "ix_ingestion_reconcile_hashes_ano_origem",
        "ix_ingestion_reconcile_hashes_arquivo_origem",
        "ix_ingestion_reconcile_hashes_hash_origem",
        "ix_ingestion_reconcile_hashes_ingestion_file_member_id",
        "ix_ingestion_reconcile_hashes_ingestion_run_id",
        "ix_ingestion_reconcile_hashes_target_table",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="ingestion_reconcile_hashes")
    op.drop_table("ingestion_reconcile_hashes")


def downgrade() -> None:
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
        "ix_ingestion_reconcile_hashes_scope_hash",
        "ingestion_reconcile_hashes",
        ["ingestion_run_id", "ingestion_file_member_id", "target_table", "arquivo_origem", "ano_origem", "hash_origem"],
        unique=False,
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
