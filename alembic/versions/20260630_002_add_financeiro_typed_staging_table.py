"""add financeiro typed staging table

Revision ID: 20260630_002
Revises: 20260630_001
Create Date: 2026-06-30 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260630_002"
down_revision: str | None = "20260630_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_financeiro_stage_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_file_member_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1000), nullable=False),
        sa.Column("row_kind", sa.String(length=80), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=False),
        sa.Column("normalized_hash", sa.String(length=64), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("natural_key", sa.JSON(), nullable=True),
        sa.Column("tipo_formulario", sa.String(length=10), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=True),
        sa.Column("denominacao_companhia", sa.String(length=255), nullable=True),
        sa.Column("categoria_documento", sa.String(length=255), nullable=True),
        sa.Column("id_documento", sa.Integer(), nullable=True),
        sa.Column("data_recebimento", sa.Date(), nullable=True),
        sa.Column("link_documento", sa.String(length=1000), nullable=True),
        sa.Column("tipo_demonstracao", sa.String(length=80), nullable=True),
        sa.Column("escopo_demonstracao", sa.String(length=20), nullable=True),
        sa.Column("grupo_demonstracao", sa.String(length=255), nullable=True),
        sa.Column("moeda", sa.String(length=20), nullable=True),
        sa.Column("escala_moeda", sa.String(length=50), nullable=True),
        sa.Column("ordem_exercicio", sa.String(length=20), nullable=True),
        sa.Column("data_inicio_exercicio", sa.Date(), nullable=True),
        sa.Column("data_fim_exercicio", sa.Date(), nullable=True),
        sa.Column("codigo_conta", sa.String(length=40), nullable=True),
        sa.Column("coluna_df", sa.Text(), nullable=True),
        sa.Column("descricao_conta", sa.Text(), nullable=True),
        sa.Column("valor_conta", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("conta_fixa", sa.Boolean(), nullable=True),
        sa.Column("quantidade_acoes_ordinarias_capital_integralizado", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_preferenciais_capital_integralizado", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_total_acoes_capital_integralizado", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_ordinarias_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_preferenciais_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_total_acoes_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("tipo_relatorio_auditor", sa.String(length=255), nullable=True),
        sa.Column("tipo_parecer_declaracao", sa.String(length=255), nullable=True),
        sa.Column("numero_item_parecer_declaracao", sa.String(length=100), nullable=True),
        sa.Column("texto_parecer_declaracao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["ingestion_file_member_id"], ["ingestion_file_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ing_fin_stage_run_member_row_kind_line",
        "ingestion_financeiro_stage_rows",
        ["ingestion_run_id", "ingestion_file_member_id", "row_kind", "linha_origem"],
        unique=False,
    )
    op.create_index(
        "ix_ing_fin_stage_member_hash",
        "ingestion_financeiro_stage_rows",
        ["ingestion_file_member_id", "normalized_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_financeiro_stage_rows_ingestion_run_id"),
        "ingestion_financeiro_stage_rows",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_financeiro_stage_rows_ingestion_file_member_id"),
        "ingestion_financeiro_stage_rows",
        ["ingestion_file_member_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_row_kind"), "ingestion_financeiro_stage_rows", ["row_kind"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_arquivo_origem"), "ingestion_financeiro_stage_rows", ["arquivo_origem"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_ano_origem"), "ingestion_financeiro_stage_rows", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_normalized_hash"), "ingestion_financeiro_stage_rows", ["normalized_hash"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_companhia_id"), "ingestion_financeiro_stage_rows", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_tipo_formulario"), "ingestion_financeiro_stage_rows", ["tipo_formulario"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_cnpj_companhia"), "ingestion_financeiro_stage_rows", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_codigo_cvm"), "ingestion_financeiro_stage_rows", ["codigo_cvm"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_data_referencia"), "ingestion_financeiro_stage_rows", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_versao"), "ingestion_financeiro_stage_rows", ["versao"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_id_documento"), "ingestion_financeiro_stage_rows", ["id_documento"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_tipo_demonstracao"), "ingestion_financeiro_stage_rows", ["tipo_demonstracao"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_escopo_demonstracao"), "ingestion_financeiro_stage_rows", ["escopo_demonstracao"], unique=False)
    op.create_index(op.f("ix_ingestion_financeiro_stage_rows_codigo_conta"), "ingestion_financeiro_stage_rows", ["codigo_conta"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_codigo_conta"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_escopo_demonstracao"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_tipo_demonstracao"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_id_documento"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_versao"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_data_referencia"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_codigo_cvm"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_cnpj_companhia"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_tipo_formulario"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_companhia_id"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_normalized_hash"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_ano_origem"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_arquivo_origem"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_row_kind"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_ingestion_file_member_id"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index(op.f("ix_ingestion_financeiro_stage_rows_ingestion_run_id"), table_name="ingestion_financeiro_stage_rows")
    op.drop_index("ix_ing_fin_stage_member_hash", table_name="ingestion_financeiro_stage_rows")
    op.drop_index("ix_ing_fin_stage_run_member_row_kind_line", table_name="ingestion_financeiro_stage_rows")
    op.drop_table("ingestion_financeiro_stage_rows")
