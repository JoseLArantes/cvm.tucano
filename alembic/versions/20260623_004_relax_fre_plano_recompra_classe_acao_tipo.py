"""relax fre plano recompra classe acao tipo

Revision ID: 20260623_004
Revises: 20260623_003
Create Date: 2026-06-23 16:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260623_004"
down_revision: str | None = "20260623_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fre_plano_recompra_classes_acoes",
        sa.Column("especie_acao", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_fre_plano_recompra_classes_acoes_especie_acao",
        "fre_plano_recompra_classes_acoes",
        ["especie_acao"],
        unique=False,
    )
    op.alter_column(
        "fre_plano_recompra_classes_acoes",
        "tipo_classe_acao_preferencial",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.drop_constraint(
        "uq_fre_plano_recompra_classes_chave_natural",
        "fre_plano_recompra_classes_acoes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_plano_recompra_classes_chave_natural",
        "fre_plano_recompra_classes_acoes",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_plano_recompra",
            "especie_acao",
            "tipo_classe_acao_preferencial",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_fre_plano_recompra_classes_chave_natural",
        "fre_plano_recompra_classes_acoes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_plano_recompra_classes_chave_natural",
        "fre_plano_recompra_classes_acoes",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_plano_recompra",
            "tipo_classe_acao_preferencial",
        ],
    )
    op.alter_column(
        "fre_plano_recompra_classes_acoes",
        "tipo_classe_acao_preferencial",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_index("ix_fre_plano_recompra_classes_acoes_especie_acao", table_name="fre_plano_recompra_classes_acoes")
    op.drop_column("fre_plano_recompra_classes_acoes", "especie_acao")
