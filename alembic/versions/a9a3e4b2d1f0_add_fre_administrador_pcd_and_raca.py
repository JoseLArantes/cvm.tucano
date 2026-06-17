"""add_fre_administrador_pcd_and_raca

Revision ID: a9a3e4b2d1f0
Revises: c4b0f0cf2c2a
Create Date: 2026-06-11 16:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9a3e4b2d1f0"
down_revision: Union[str, None] = "c4b0f0cf2c2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fre_administradores_declaracao_raca",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("orgao_administracao", sa.Text(), nullable=False),
        sa.Column("quantidade_amarelo", sa.Integer(), nullable=True),
        sa.Column("quantidade_branco", sa.Integer(), nullable=True),
        sa.Column("quantidade_preto", sa.Integer(), nullable=True),
        sa.Column("quantidade_pardo", sa.Integer(), nullable=True),
        sa.Column("quantidade_indigena", sa.Integer(), nullable=True),
        sa.Column("quantidade_outros", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("nao_aplicavel", sa.Boolean(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "orgao_administracao", name="uq_fre_adm_dec_raca_chave_natural"),
    )
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_ano_origem"), "fre_administradores_declaracao_raca", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_cnpj_companhia"), "fre_administradores_declaracao_raca", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_companhia_id"), "fre_administradores_declaracao_raca", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_data_referencia"), "fre_administradores_declaracao_raca", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_id_documento"), "fre_administradores_declaracao_raca", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_orgao_administracao"), "fre_administradores_declaracao_raca", ["orgao_administracao"], unique=False)
    op.create_index(op.f("ix_fre_administradores_declaracao_raca_versao"), "fre_administradores_declaracao_raca", ["versao"], unique=False)

    op.create_table(
        "fre_administradores_pcd",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("orgao_administracao", sa.Text(), nullable=False),
        sa.Column("quantidade_pcd", sa.Integer(), nullable=True),
        sa.Column("quantidade_nao_pcd", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("nao_aplicavel", sa.Boolean(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "orgao_administracao", name="uq_fre_adm_pcd_chave_natural"),
    )
    op.create_index(op.f("ix_fre_administradores_pcd_ano_origem"), "fre_administradores_pcd", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_cnpj_companhia"), "fre_administradores_pcd", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_companhia_id"), "fre_administradores_pcd", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_data_referencia"), "fre_administradores_pcd", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_id_documento"), "fre_administradores_pcd", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_orgao_administracao"), "fre_administradores_pcd", ["orgao_administracao"], unique=False)
    op.create_index(op.f("ix_fre_administradores_pcd_versao"), "fre_administradores_pcd", ["versao"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fre_administradores_pcd_versao"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_orgao_administracao"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_id_documento"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_data_referencia"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_companhia_id"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_cnpj_companhia"), table_name="fre_administradores_pcd")
    op.drop_index(op.f("ix_fre_administradores_pcd_ano_origem"), table_name="fre_administradores_pcd")
    op.drop_table("fre_administradores_pcd")

    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_versao"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_orgao_administracao"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_id_documento"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_data_referencia"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_companhia_id"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_cnpj_companhia"), table_name="fre_administradores_declaracao_raca")
    op.drop_index(op.f("ix_fre_administradores_declaracao_raca_ano_origem"), table_name="fre_administradores_declaracao_raca")
    op.drop_table("fre_administradores_declaracao_raca")
