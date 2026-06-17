"""add data_inicio_exercicio to demonstracoes_financeiras unique key

Revision ID: 7b5c9d2e4f11
Revises: 6f2e9b7c1a4d
Create Date: 2026-06-12 18:50:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b5c9d2e4f11"
down_revision: str | None = "6f2e9b7c1a4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
            "data_inicio_exercicio",
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
            "coluna_df",
        ],
    )
