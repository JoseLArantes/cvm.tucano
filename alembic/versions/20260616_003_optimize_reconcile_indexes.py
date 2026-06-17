"""optimize_reconcile_indexes

Revision ID: 20260616_003
Revises: 20260616_002
Create Date: 2026-06-16 15:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_003"
down_revision: str | None = "20260616_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LINEAGE_COLUMNS = {"arquivo_origem", "ano_origem", "hash_origem"}


def _table_names_with_lineage(bind: sa.engine.Connection) -> list[str]:
    inspector = sa.inspect(bind)
    tables: list[str] = []
    for table_name in inspector.get_table_names(schema="public"):
        columns = {column["name"] for column in inspector.get_columns(table_name, schema="public")}
        if _LINEAGE_COLUMNS.issubset(columns):
            tables.append(table_name)
    return sorted(tables)


def upgrade() -> None:
    bind = op.get_bind()
    op.create_index(
        "ix_ingestion_reconcile_hashes_scope_hash",
        "ingestion_reconcile_hashes",
        [
            "ingestion_run_id",
            "ingestion_file_member_id",
            "target_table",
            "arquivo_origem",
            "ano_origem",
            "hash_origem",
        ],
        unique=False,
    )
    for table_name in _table_names_with_lineage(bind):
        if table_name == "ingestion_reconcile_hashes":
            continue
        op.execute(
            sa.text(
                f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_lineage_scope_hash" '
                f'ON "{table_name}" (arquivo_origem, ano_origem, hash_origem)'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in _table_names_with_lineage(bind):
        if table_name == "ingestion_reconcile_hashes":
            continue
        op.execute(sa.text(f'DROP INDEX IF EXISTS "ix_{table_name}_lineage_scope_hash"'))
    op.drop_index("ix_ingestion_reconcile_hashes_scope_hash", table_name="ingestion_reconcile_hashes")
