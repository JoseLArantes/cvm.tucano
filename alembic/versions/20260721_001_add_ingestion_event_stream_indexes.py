"""add indexes for incremental ingestion event stream

Revision ID: 20260721_001
Revises: 20260720_001
Create Date: 2026-07-21 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_001"
down_revision: str | Sequence[str] | None = "20260720_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_ingestion_runs_updated_at", "ingestion_runs", ["updated_at"])
    op.create_index(
        "ix_ingestion_runs_tipo_fonte_ano_updated_at",
        "ingestion_runs",
        ["tipo_fonte", "ano", "updated_at"],
    )
    op.create_index("ix_ingestion_file_members_updated_at", "ingestion_file_members", ["updated_at"])
    op.create_index(
        "ix_analise_materializacao_campanhas_updated_at",
        "analise_materializacao_campanhas",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analise_materializacao_campanhas_updated_at", table_name="analise_materializacao_campanhas")
    op.drop_index("ix_ingestion_file_members_updated_at", table_name="ingestion_file_members")
    op.drop_index("ix_ingestion_runs_tipo_fonte_ano_updated_at", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_updated_at", table_name="ingestion_runs")
