"""add_phase5_ipe_table

Revision ID: 7ac2d7b2c9e1
Revises: 4f4a6d0d1a2b
Create Date: 2026-06-08 19:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7ac2d7b2c9e1"
down_revision: str | None = "4f4a6d0d1a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ipe_documentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(length=255), nullable=True),
        sa.Column("tipo", sa.String(length=255), nullable=True),
        sa.Column("especie", sa.String(length=255), nullable=True),
        sa.Column("assunto", sa.String(length=255), nullable=True),
        sa.Column("data_entrega", sa.Date(), nullable=False),
        sa.Column("tipo_apresentacao", sa.String(length=255), nullable=True),
        sa.Column("protocolo_entrega", sa.String(length=255), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("link_download", sa.String(length=1000), nullable=True),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocolo_entrega", "versao", name="uq_ipe_documentos_protocolo_versao"),
        sa.UniqueConstraint(
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "especie",
            "assunto",
            "data_entrega",
            "versao",
            name="uq_ipe_documentos_chave_alternativa",
        ),
    )
    for col in (
        "companhia_id",
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
        "ano_origem",
    ):
        op.create_index(op.f(f"ix_ipe_documentos_{col}"), "ipe_documentos", [col], unique=False)


def downgrade() -> None:
    for col in (
        "ano_origem",
        "versao",
        "protocolo_entrega",
        "data_entrega",
        "assunto",
        "especie",
        "tipo",
        "categoria",
        "data_referencia",
        "codigo_cvm",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_ipe_documentos_{col}"), table_name="ipe_documentos")
    op.drop_table("ipe_documentos")
