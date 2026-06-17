"""add data_inicio_atuacao to fca_dri unique key

Revision ID: 1c2d3e4f5a6b
Revises: e1c2b3a4d5f6
Create Date: 2026-06-12 22:40:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: str | None = "e1c2b3a4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_fca_dri_chave_natural", "fca_dri", type_="unique")
    op.create_unique_constraint(
        "uq_fca_dri_chave_natural",
        "fca_dri",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_responsavel",
            "tipo_responsavel",
            "data_inicio_atuacao",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_fca_dri_chave_natural", "fca_dri", type_="unique")
    op.create_unique_constraint(
        "uq_fca_dri_chave_natural",
        "fca_dri",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_responsavel",
            "tipo_responsavel",
        ],
    )
