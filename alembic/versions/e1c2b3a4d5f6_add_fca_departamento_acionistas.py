"""add_fca_departamento_acionistas

Revision ID: e1c2b3a4d5f6
Revises: a9a3e4b2d1f0
Create Date: 2026-06-11 13:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1c2b3a4d5f6"
down_revision: str | None = "a9a3e4b2d1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fca_departamentos_acionistas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("contato", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_contato", sa.Date(), nullable=True),
        sa.Column("data_fim_contato", sa.Date(), nullable=True),
        sa.Column("tipo_endereco", sa.String(length=100), nullable=True),
        sa.Column("logradouro", sa.String(length=255), nullable=True),
        sa.Column("complemento", sa.String(length=255), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=True),
        sa.Column("cidade", sa.String(length=100), nullable=True),
        sa.Column("sigla_uf", sa.String(length=5), nullable=True),
        sa.Column("pais", sa.String(length=100), nullable=True),
        sa.Column("cep", sa.String(length=20), nullable=True),
        sa.Column("ddi_telefone", sa.String(length=10), nullable=True),
        sa.Column("ddd_telefone", sa.String(length=10), nullable=True),
        sa.Column("telefone", sa.String(length=50), nullable=True),
        sa.Column("ddi_fax", sa.String(length=10), nullable=True),
        sa.Column("ddd_fax", sa.String(length=10), nullable=True),
        sa.Column("fax", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "contato",
            "email",
            "tipo_endereco",
            name="uq_fca_departamentos_acionistas_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
        "contato",
        "tipo_endereco",
        "sigla_uf",
        "pais",
        "email",
    ):
        op.create_index(op.f(f"ix_fca_departamentos_acionistas_{col}"), "fca_departamentos_acionistas", [col], unique=False)


def downgrade() -> None:
    for col in (
        "email",
        "pais",
        "sigla_uf",
        "tipo_endereco",
        "contato",
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_departamentos_acionistas_{col}"), table_name="fca_departamentos_acionistas")
    op.drop_table("fca_departamentos_acionistas")
