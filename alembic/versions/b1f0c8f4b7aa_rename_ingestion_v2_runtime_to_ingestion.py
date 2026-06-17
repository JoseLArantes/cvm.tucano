"""rename ingestion runtime from v2 to ingestion

Revision ID: b1f0c8f4b7aa
Revises: dddfeda1b4b7
Create Date: 2026-06-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1f0c8f4b7aa"
down_revision: str | None = "dddfeda1b4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    op.rename_table("quarantine_items_v2", "quarantine_items")

    for old_name, new_name in (
        ("ix_quarantine_items_v2_arquivo_origem", "ix_quarantine_items_arquivo_origem"),
        ("ix_quarantine_items_v2_ano_origem", "ix_quarantine_items_ano_origem"),
        ("ix_quarantine_items_v2_execucao_sincronizacao_id", "ix_quarantine_items_execucao_sincronizacao_id"),
        ("ix_quarantine_items_v2_ingestion_row_id", "ix_quarantine_items_ingestion_row_id"),
        ("ix_quarantine_items_v2_ingestion_run_id", "ix_quarantine_items_ingestion_run_id"),
        ("ix_quarantine_items_v2_motivo_codigo", "ix_quarantine_items_motivo_codigo"),
        ("ix_quarantine_items_v2_row_kind", "ix_quarantine_items_row_kind"),
        ("ix_quarantine_items_v2_status", "ix_quarantine_items_status"),
        ("uq_quarantine_items_v2_ingestion_row_id", "uq_quarantine_items_ingestion_row_id"),
    ):
        bind.execute(sa.text(f'ALTER INDEX IF EXISTS "{old_name}" RENAME TO "{new_name}"'))

    bind.execute(
        sa.text(
            """
            UPDATE execucoes_sincronizacao
            SET tipo_fonte = 'cadastro'
            WHERE tipo_fonte = 'cadastro_v2'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE execucoes_sincronizacao
            SET tipo_fonte = 'cadastro_v2'
            WHERE tipo_fonte = 'cadastro'
            AND arquivo IN ('cad_cia_aberta.csv', 'cad_cia_estrang.csv')
            """
        )
    )

    op.rename_table("quarantine_items", "quarantine_items_v2")

    for old_name, new_name in (
        ("ix_quarantine_items_arquivo_origem", "ix_quarantine_items_v2_arquivo_origem"),
        ("ix_quarantine_items_ano_origem", "ix_quarantine_items_v2_ano_origem"),
        ("ix_quarantine_items_execucao_sincronizacao_id", "ix_quarantine_items_v2_execucao_sincronizacao_id"),
        ("ix_quarantine_items_ingestion_row_id", "ix_quarantine_items_v2_ingestion_row_id"),
        ("ix_quarantine_items_ingestion_run_id", "ix_quarantine_items_v2_ingestion_run_id"),
        ("ix_quarantine_items_motivo_codigo", "ix_quarantine_items_v2_motivo_codigo"),
        ("ix_quarantine_items_row_kind", "ix_quarantine_items_v2_row_kind"),
        ("ix_quarantine_items_status", "ix_quarantine_items_v2_status"),
        ("uq_quarantine_items_ingestion_row_id", "uq_quarantine_items_v2_ingestion_row_id"),
    ):
        bind.execute(sa.text(f'ALTER INDEX IF EXISTS "{old_name}" RENAME TO "{new_name}"'))
