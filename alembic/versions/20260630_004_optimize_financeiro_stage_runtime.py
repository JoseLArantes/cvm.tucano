"""optimize financeiro typed staging runtime

Revision ID: 20260630_004
Revises: 20260630_003
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op

revision: str = "20260630_004"
down_revision: str | None = "20260630_003"
branch_labels: str | None = None
depends_on: str | None = None


_WIDE_INDEXES = (
    "ix_ingestion_financeiro_stage_rows_ano_origem",
    "ix_ingestion_financeiro_stage_rows_arquivo_origem",
    "ix_ingestion_financeiro_stage_rows_cnpj_companhia",
    "ix_ingestion_financeiro_stage_rows_codigo_conta",
    "ix_ingestion_financeiro_stage_rows_codigo_cvm",
    "ix_ingestion_financeiro_stage_rows_companhia_id",
    "ix_ingestion_financeiro_stage_rows_data_referencia",
    "ix_ingestion_financeiro_stage_rows_escopo_demonstracao",
    "ix_ingestion_financeiro_stage_rows_id_documento",
    "ix_ingestion_financeiro_stage_rows_normalized_hash",
    "ix_ingestion_financeiro_stage_rows_tipo_demonstracao",
    "ix_ingestion_financeiro_stage_rows_tipo_formulario",
    "ix_ingestion_financeiro_stage_rows_versao",
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgresql():
        return

    op.execute("ALTER TABLE ingestion_financeiro_stage_rows SET UNLOGGED")
    for index_name in _WIDE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")


def downgrade() -> None:
    if not _is_postgresql():
        return

    op.execute("ALTER TABLE ingestion_financeiro_stage_rows SET LOGGED")
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_ano_origem",
        "ingestion_financeiro_stage_rows",
        ["ano_origem"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_arquivo_origem",
        "ingestion_financeiro_stage_rows",
        ["arquivo_origem"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_cnpj_companhia",
        "ingestion_financeiro_stage_rows",
        ["cnpj_companhia"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_codigo_conta",
        "ingestion_financeiro_stage_rows",
        ["codigo_conta"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_codigo_cvm",
        "ingestion_financeiro_stage_rows",
        ["codigo_cvm"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_companhia_id",
        "ingestion_financeiro_stage_rows",
        ["companhia_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_data_referencia",
        "ingestion_financeiro_stage_rows",
        ["data_referencia"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_escopo_demonstracao",
        "ingestion_financeiro_stage_rows",
        ["escopo_demonstracao"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_id_documento",
        "ingestion_financeiro_stage_rows",
        ["id_documento"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_normalized_hash",
        "ingestion_financeiro_stage_rows",
        ["normalized_hash"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_tipo_demonstracao",
        "ingestion_financeiro_stage_rows",
        ["tipo_demonstracao"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_tipo_formulario",
        "ingestion_financeiro_stage_rows",
        ["tipo_formulario"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_financeiro_stage_rows_versao",
        "ingestion_financeiro_stage_rows",
        ["versao"],
        unique=False,
    )
