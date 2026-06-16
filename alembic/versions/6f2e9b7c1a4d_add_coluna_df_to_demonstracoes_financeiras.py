"""add coluna_df to demonstracoes_financeiras

Revision ID: 6f2e9b7c1a4d
Revises: e1c2b3a4d5f6
Create Date: 2026-06-12 16:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f2e9b7c1a4d"
down_revision: str | None = "e1c2b3a4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "demonstracoes_financeiras",
        sa.Column("coluna_df", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.drop_constraint(
        "uq_demonstracoes_financeiras_chave_natural",
        "demonstracoes_financeiras",
        type_="unique",
    )
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
            "data_fim_exercicio",
            "codigo_conta",
            "coluna_df",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_demonstracoes_financeiras_chave_natural",
        "demonstracoes_financeiras",
        type_="unique",
    )
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
            "data_fim_exercicio",
            "codigo_conta",
        ],
    )
    op.drop_column("demonstracoes_financeiras", "coluna_df")
