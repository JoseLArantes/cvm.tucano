"""optimize demonstracoes storage and indexes

Revision ID: 20261103_001
Revises: 20260723_001
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261103_001"
down_revision: str | None = "20260723_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REDUNDANT_INDEXES = [
    "ix_demonstracoes_financeiras_lineage_scope_hash",
    "ix_demonstracoes_financeiras_tipo_formulario",
    "ix_demonstracoes_financeiras_tipo_demonstracao",
    "ix_demonstracoes_financeiras_escopo_demonstracao",
    "ix_demonstracoes_financeiras_cnpj_companhia",
    "ix_demonstracoes_financeiras_codigo_cvm",
    "ix_demonstracoes_financeiras_data_referencia",
    "ix_demonstracoes_financeiras_versao",
    "ix_demonstracoes_financeiras_codigo_conta",
    "ix_demonstracoes_financeiras_ano_origem",
]


def upgrade() -> None:
    # 1. Add chave_negocio to demonstracoes_financeiras
    op.add_column(
        "demonstracoes_financeiras",
        sa.Column("chave_negocio", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_demonstracoes_financeiras_chave_negocio",
        "demonstracoes_financeiras",
        ["chave_negocio"],
    )

    # 2. Drop wide natural key unique constraint
    op.drop_constraint(
        "uq_demonstracoes_financeiras_chave_natural",
        "demonstracoes_financeiras",
        type_="unique",
    )

    # 3. Drop redundant single-column indexes
    for idx_name in _REDUNDANT_INDEXES:
        try:
            op.drop_index(idx_name, table_name="demonstracoes_financeiras")
        except Exception:
            pass

    # 4. Create optimized composite lookup indexes
    op.create_index(
        "ix_demonstracoes_financeiras_analise_cvm_lookup",
        "demonstracoes_financeiras",
        ["codigo_cvm", "escopo_demonstracao", "tipo_formulario", "data_referencia", "versao"],
        unique=False,
    )
    op.create_index(
        "ix_demonstracoes_financeiras_router_filter",
        "demonstracoes_financeiras",
        ["tipo_formulario", "tipo_demonstracao", "escopo_demonstracao", "ano_origem", "data_referencia"],
        unique=False,
    )

    # 5. Add chave_negocio to ingestion_financeiro_stage_rows
    op.add_column(
        "ingestion_financeiro_stage_rows",
        sa.Column("chave_negocio", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_ing_fin_stage_chave_negocio",
        "ingestion_financeiro_stage_rows",
        ["chave_negocio"],
        unique=False,
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE ingestion_financeiro_stage_rows SET UNLOGGED")


def downgrade() -> None:
    op.drop_index("ix_ing_fin_stage_chave_negocio", table_name="ingestion_financeiro_stage_rows")
    op.drop_column("ingestion_financeiro_stage_rows", "chave_negocio")

    op.drop_index("ix_demonstracoes_financeiras_router_filter", table_name="demonstracoes_financeiras")
    op.drop_index("ix_demonstracoes_financeiras_analise_cvm_lookup", table_name="demonstracoes_financeiras")

    for idx_name in _REDUNDANT_INDEXES:
        col = idx_name.replace("ix_demonstracoes_financeiras_", "")
        if col == "lineage_scope_hash":
            op.create_index(idx_name, "demonstracoes_financeiras", ["arquivo_origem", "ano_origem", "hash_origem"])
        else:
            op.create_index(idx_name, "demonstracoes_financeiras", [col])

    op.create_unique_constraint(
        "uq_demonstracoes_financeiras_chave_natural",
        "demonstracoes_financeiras",
        [
            "tipo_formulario",
            "tipo_demonstracao",
            "escopo_demonstracao",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "grupo_demonstracao",
            "ordem_exercicio",
            "data_inicio_exercicio",
            "data_fim_exercicio",
            "codigo_conta",
            "coluna_df",
        ],
    )

    op.drop_constraint(
        "uq_demonstracoes_financeiras_chave_negocio",
        "demonstracoes_financeiras",
        type_="unique",
    )
    op.drop_column("demonstracoes_financeiras", "chave_negocio")
