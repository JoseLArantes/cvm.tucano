"""add_phase6_vlmo_tables

Revision ID: 9f3c2b1a4d5e
Revises: 7ac2d7b2c9e1
Create Date: 2026-06-08 21:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f3c2b1a4d5e"
down_revision: str | None = "7ac2d7b2c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vlmo_documentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(length=255), nullable=True),
        sa.Column("tipo", sa.String(length=255), nullable=True),
        sa.Column("data_entrega", sa.Date(), nullable=False),
        sa.Column("tipo_apresentacao", sa.String(length=255), nullable=True),
        sa.Column("motivo_reapresentacao", sa.String(length=500), nullable=True),
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
        sa.UniqueConstraint("protocolo_entrega", "versao", name="uq_vlmo_documentos_protocolo_versao"),
        sa.UniqueConstraint(
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "data_entrega",
            "versao",
            name="uq_vlmo_documentos_chave_alternativa",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "codigo_cvm",
        "data_referencia",
        "categoria",
        "tipo",
        "data_entrega",
        "protocolo_entrega",
        "versao",
        "ano_origem",
    ):
        op.create_index(op.f(f"ix_vlmo_documentos_{col}"), "vlmo_documentos", [col], unique=False)

    op.create_table(
        "vlmo_consolidado",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=True),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("tipo_empresa", sa.String(length=50), nullable=True),
        sa.Column("empresa", sa.String(length=255), nullable=True),
        sa.Column("tipo_cargo", sa.String(length=100), nullable=True),
        sa.Column("tipo_movimentacao", sa.String(length=255), nullable=True),
        sa.Column("descricao_movimentacao", sa.String(length=255), nullable=True),
        sa.Column("tipo_operacao", sa.String(length=50), nullable=True),
        sa.Column("tipo_ativo", sa.String(length=255), nullable=True),
        sa.Column("caracteristica_valor_mobiliario", sa.String(length=100), nullable=True),
        sa.Column("intermediario", sa.String(length=100), nullable=True),
        sa.Column("data_movimentacao", sa.Date(), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=True),
        sa.Column("preco_unitario", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("volume", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("indice_ocorrencia", sa.Integer(), nullable=False),
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
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "linha_origem",
            name="uq_vlmo_consolidado_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "tipo_empresa",
        "empresa",
        "tipo_cargo",
        "tipo_movimentacao",
        "tipo_operacao",
        "tipo_ativo",
        "caracteristica_valor_mobiliario",
        "intermediario",
        "data_movimentacao",
        "indice_ocorrencia",
        "ano_origem",
    ):
        op.create_index(op.f(f"ix_vlmo_consolidado_{col}"), "vlmo_consolidado", [col], unique=False)


def downgrade() -> None:
    for col in (
        "ano_origem",
        "indice_ocorrencia",
        "data_movimentacao",
        "intermediario",
        "caracteristica_valor_mobiliario",
        "tipo_ativo",
        "tipo_operacao",
        "tipo_movimentacao",
        "tipo_cargo",
        "empresa",
        "tipo_empresa",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_vlmo_consolidado_{col}"), table_name="vlmo_consolidado")
    op.drop_table("vlmo_consolidado")

    for col in (
        "ano_origem",
        "versao",
        "protocolo_entrega",
        "data_entrega",
        "tipo",
        "categoria",
        "data_referencia",
        "codigo_cvm",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_vlmo_documentos_{col}"), table_name="vlmo_documentos")
    op.drop_table("vlmo_documentos")
