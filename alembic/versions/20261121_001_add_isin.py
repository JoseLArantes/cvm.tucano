"""Adiciona referência de ISIN e projeção cadastral."""

import sqlalchemy as sa

from alembic import op

revision = "20261121_001"
down_revision = "20261118_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referencias_isin",
        sa.Column("codigo_isin", sa.String(12), primary_key=True),
        sa.Column("cnpj_companhia", sa.String(14), nullable=False),
    )
    op.create_index("ix_referencias_isin_cnpj_companhia", "referencias_isin", ["cnpj_companhia"])
    op.add_column("companhias", sa.Column("codigos_isin", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("companhias", "codigos_isin")
    op.drop_index("ix_referencias_isin_cnpj_companhia", table_name="referencias_isin")
    op.drop_table("referencias_isin")
