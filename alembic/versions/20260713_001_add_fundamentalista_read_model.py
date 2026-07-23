"""add fundamentalista read model

Revision ID: 20260713_001
Revises: 20260701_001
Create Date: 2026-07-13 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_001"
down_revision: str | Sequence[str] | None = "20260701_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analise_fundamentalista_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.String(length=20), nullable=False),
        sa.Column("periodicidade", sa.String(length=20), nullable=False),
        sa.Column("base_periodo", sa.String(length=20), nullable=False),
        sa.Column("horizonte_anos", sa.Integer(), nullable=False),
        sa.Column("as_of_key", sa.String(length=10), nullable=False),
        sa.Column("include_key", sa.String(length=32), nullable=False),
        sa.Column("calculation_version", sa.String(length=20), nullable=False),
        sa.Column("report_version", sa.String(length=20), nullable=False),
        sa.Column("source_execution_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_execution_id"],
            ["analise_materializacao_execucoes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "codigo_cvm",
            "escopo",
            "periodicidade",
            "base_periodo",
            "horizonte_anos",
            "as_of_key",
            "include_key",
            "calculation_version",
            "report_version",
            name="uq_analise_fundamentalista_snapshot_contexto",
        ),
    )
    op.create_index(
        "ix_analise_fundamentalista_snapshots_lookup",
        "analise_fundamentalista_snapshots",
        [
            "codigo_cvm",
            "escopo",
            "periodicidade",
            "base_periodo",
            "horizonte_anos",
            "as_of_key",
            "include_key",
            "calculation_version",
        ],
        unique=False,
    )
    op.create_index(
        "ix_analise_fundamentalista_snapshots_execucao",
        "analise_fundamentalista_snapshots",
        ["source_execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_fundamentalista_snapshots_companhia_id"),
        "analise_fundamentalista_snapshots",
        ["companhia_id"],
        unique=False,
    )
    op.create_index(
        "ix_analise_contexto_revisions_current",
        "analise_contexto_revisions",
        ["codigo_cvm", "escopo", "calculation_version", "known_from"],
        unique=False,
        postgresql_where=sa.text("known_to IS NULL"),
        sqlite_where=sa.text("known_to IS NULL"),
    )
    op.create_index(
        "ix_analise_fato_revisions_current_lookup",
        "analise_fato_revisions",
        [
            "codigo_cvm",
            "escopo",
            "calculation_version",
            "periodicidade",
            "base_periodo",
            "metric_id",
            "fiscal_year",
            "quarter",
        ],
        unique=False,
        postgresql_where=sa.text("known_to IS NULL"),
        sqlite_where=sa.text("known_to IS NULL"),
    )
    op.create_index(
        "ix_documentos_financeiros_analise_lookup",
        "documentos_financeiros",
        ["cnpj_companhia", "tipo_formulario", "data_referencia", "versao"],
        unique=False,
    )
    op.create_index(
        "ix_demonstracoes_financeiras_analise_lookup",
        "demonstracoes_financeiras",
        ["cnpj_companhia", "escopo_demonstracao", "tipo_formulario", "data_referencia", "versao"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_demonstracoes_financeiras_analise_lookup", table_name="demonstracoes_financeiras")
    op.drop_index("ix_documentos_financeiros_analise_lookup", table_name="documentos_financeiros")
    op.drop_index("ix_analise_fato_revisions_current_lookup", table_name="analise_fato_revisions")
    op.drop_index("ix_analise_contexto_revisions_current", table_name="analise_contexto_revisions")
    op.drop_index(
        op.f("ix_analise_fundamentalista_snapshots_companhia_id"),
        table_name="analise_fundamentalista_snapshots",
    )
    op.drop_index(
        "ix_analise_fundamentalista_snapshots_execucao",
        table_name="analise_fundamentalista_snapshots",
    )
    op.drop_index(
        "ix_analise_fundamentalista_snapshots_lookup",
        table_name="analise_fundamentalista_snapshots",
    )
    op.drop_table("analise_fundamentalista_snapshots")
