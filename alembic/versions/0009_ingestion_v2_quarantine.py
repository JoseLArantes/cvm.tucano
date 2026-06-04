"""ingestion v2 quarantine

Revision ID: 0009_ingestion_v2_quarantine
Revises: 0008_ingestion_v2_identity
Create Date: 2026-06-04 00:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_ingestion_v2_quarantine"
down_revision: str | None = "0008_ingestion_v2_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quarantine_items_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_row_id", sa.Uuid(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=True),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("row_kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("motivo_codigo", sa.String(length=64), nullable=False),
        sa.Column("severidade", sa.String(length=16), nullable=False),
        sa.Column("reparavel", sa.Boolean(), nullable=False),
        sa.Column("diagnostico", sa.JSON(), nullable=True),
        sa.Column("ultima_tentativa_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tentativas_reprocessamento", sa.Integer(), nullable=False),
        sa.Column("resolvido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolvido_por", sa.String(length=120), nullable=True),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
        sa.ForeignKeyConstraint(["ingestion_row_id"], ["ingestion_rows.id"]),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingestion_row_id", name="uq_quarantine_items_v2_ingestion_row_id"),
    )
    op.create_index(op.f("ix_quarantine_items_v2_arquivo_origem"), "quarantine_items_v2", ["arquivo_origem"], unique=False)
    op.create_index(op.f("ix_quarantine_items_v2_ano_origem"), "quarantine_items_v2", ["ano_origem"], unique=False)
    op.create_index(
        op.f("ix_quarantine_items_v2_execucao_sincronizacao_id"),
        "quarantine_items_v2",
        ["execucao_sincronizacao_id"],
        unique=False,
    )
    op.create_index(op.f("ix_quarantine_items_v2_ingestion_row_id"), "quarantine_items_v2", ["ingestion_row_id"], unique=False)
    op.create_index(op.f("ix_quarantine_items_v2_ingestion_run_id"), "quarantine_items_v2", ["ingestion_run_id"], unique=False)
    op.create_index(op.f("ix_quarantine_items_v2_motivo_codigo"), "quarantine_items_v2", ["motivo_codigo"], unique=False)
    op.create_index(op.f("ix_quarantine_items_v2_row_kind"), "quarantine_items_v2", ["row_kind"], unique=False)
    op.create_index(op.f("ix_quarantine_items_v2_status"), "quarantine_items_v2", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quarantine_items_v2_status"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_row_kind"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_motivo_codigo"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_ingestion_run_id"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_ingestion_row_id"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_execucao_sincronizacao_id"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_ano_origem"), table_name="quarantine_items_v2")
    op.drop_index(op.f("ix_quarantine_items_v2_arquivo_origem"), table_name="quarantine_items_v2")
    op.drop_table("quarantine_items_v2")
