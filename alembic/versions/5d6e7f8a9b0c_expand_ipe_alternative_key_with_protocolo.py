"""expand ipe alternative key with protocolo

Revision ID: 5d6e7f8a9b0c
Revises: 4c5d6e7f8a9b
Create Date: 2026-06-15 02:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d6e7f8a9b0c"
down_revision: str | None = "4c5d6e7f8a9b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_ipe_documentos_chave_alternativa", "ipe_documentos", type_="unique")
    op.create_unique_constraint(
        "uq_ipe_documentos_chave_alternativa",
        "ipe_documentos",
        [
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "especie",
            "assunto",
            "data_entrega",
            "protocolo_entrega",
            "versao",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ipe_documentos_chave_alternativa", "ipe_documentos", type_="unique")
    op.create_unique_constraint(
        "uq_ipe_documentos_chave_alternativa",
        "ipe_documentos",
        [
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "especie",
            "assunto",
            "data_entrega",
            "versao",
        ],
    )
