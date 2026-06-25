"""add_analise_canonical_tables

Revision ID: 20260622_001
Revises: 20260621_001
Create Date: 2026-06-22 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260622_001"
down_revision: str | None = "20260621_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analise_materializacao_execucoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.String(length=20), nullable=False),
        sa.Column("calculation_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("coverage_complete", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_materializacao_execucoes_lookup",
        "analise_materializacao_execucoes",
        ["codigo_cvm", "escopo", "calculation_version", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_companhia_id"),
        "analise_materializacao_execucoes",
        ["companhia_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_codigo_cvm"),
        "analise_materializacao_execucoes",
        ["codigo_cvm"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_escopo"),
        "analise_materializacao_execucoes",
        ["escopo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_calculation_version"),
        "analise_materializacao_execucoes",
        ["calculation_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_status"),
        "analise_materializacao_execucoes",
        ["status"],
        unique=False,
    )

    op.create_table(
        "analise_contexto_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execucao_id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.String(length=20), nullable=False),
        sa.Column("calculation_version", sa.String(length=20), nullable=False),
        sa.Column("known_from", sa.Date(), nullable=False),
        sa.Column("known_to", sa.Date(), nullable=True),
        sa.Column("default_period_id", sa.String(length=32), nullable=False),
        sa.Column("periodos_disponiveis", sa.JSON(), nullable=False),
        sa.Column("qualidade", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["execucao_id"], ["analise_materializacao_execucoes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_contexto_revisions_lookup",
        "analise_contexto_revisions",
        ["codigo_cvm", "escopo", "calculation_version", "known_from", "known_to"],
        unique=False,
    )
    for column in ("execucao_id", "companhia_id", "codigo_cvm", "escopo", "calculation_version", "known_from", "known_to"):
        op.create_index(op.f(f"ix_analise_contexto_revisions_{column}"), "analise_contexto_revisions", [column], unique=False)

    op.create_table(
        "analise_fato_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execucao_id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.String(length=20), nullable=False),
        sa.Column("calculation_version", sa.String(length=20), nullable=False),
        sa.Column("periodicidade", sa.String(length=20), nullable=False),
        sa.Column("base_periodo", sa.String(length=20), nullable=False),
        sa.Column("metric_id", sa.String(length=64), nullable=False),
        sa.Column("period_id", sa.String(length=32), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("known_from", sa.Date(), nullable=False),
        sa.Column("known_to", sa.Date(), nullable=True),
        sa.Column("observation_payload", sa.JSON(), nullable=True),
        sa.Column("unavailable_payload", sa.JSON(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provenance_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["execucao_id"], ["analise_materializacao_execucoes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_fato_revisions_lookup",
        "analise_fato_revisions",
        ["codigo_cvm", "escopo", "calculation_version", "periodicidade", "base_periodo", "metric_id", "known_from", "known_to"],
        unique=False,
    )
    op.create_index(
        "ix_analise_fato_revisions_period",
        "analise_fato_revisions",
        ["codigo_cvm", "escopo", "calculation_version", "period_id"],
        unique=False,
    )
    for column in (
        "execucao_id",
        "companhia_id",
        "codigo_cvm",
        "escopo",
        "calculation_version",
        "known_from",
        "known_to",
    ):
        op.create_index(op.f(f"ix_analise_fato_revisions_{column}"), "analise_fato_revisions", [column], unique=False)


def downgrade() -> None:
    for column in (
        "known_to",
        "known_from",
        "calculation_version",
        "escopo",
        "codigo_cvm",
        "companhia_id",
        "execucao_id",
    ):
        op.drop_index(op.f(f"ix_analise_fato_revisions_{column}"), table_name="analise_fato_revisions")
    op.drop_index("ix_analise_fato_revisions_period", table_name="analise_fato_revisions")
    op.drop_index("ix_analise_fato_revisions_lookup", table_name="analise_fato_revisions")
    op.drop_table("analise_fato_revisions")

    for column in ("known_to", "known_from", "calculation_version", "escopo", "codigo_cvm", "companhia_id", "execucao_id"):
        op.drop_index(op.f(f"ix_analise_contexto_revisions_{column}"), table_name="analise_contexto_revisions")
    op.drop_index("ix_analise_contexto_revisions_lookup", table_name="analise_contexto_revisions")
    op.drop_table("analise_contexto_revisions")

    for column in ("status", "calculation_version", "escopo", "codigo_cvm", "companhia_id"):
        op.drop_index(op.f(f"ix_analise_materializacao_execucoes_{column}"), table_name="analise_materializacao_execucoes")
    op.drop_index("ix_analise_materializacao_execucoes_lookup", table_name="analise_materializacao_execucoes")
    op.drop_table("analise_materializacao_execucoes")
