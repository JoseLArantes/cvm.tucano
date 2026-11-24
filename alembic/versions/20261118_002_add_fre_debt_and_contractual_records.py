"""Promove quadros de dívida do FRE e cria registros contratuais versionados.

Revision ID: 20261118_002
Revises: 1c2d3e4f5a6b, 7b5c9d2e4f11, 20261118_001
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261118_002"
down_revision: str | Sequence[str] | None = ("1c2d3e4f5a6b", "7b5c9d2e4f11", "20261118_001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fre_endividamentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("data_inicio_exercicio_social", sa.Date(), nullable=True),
        sa.Column("data_fim_exercicio_social", sa.Date(), nullable=True),
        sa.Column("passivo", sa.Text(), nullable=True),
        sa.Column("indice_endividamento", sa.Text(), nullable=True),
        sa.Column("tipo_indice", sa.Text(), nullable=True),
        sa.Column("descricao_outro_indice", sa.Text(), nullable=True),
        sa.Column("row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cnpj_companhia",
            "id_documento",
            "versao",
            "data_referencia",
            "row_fingerprint",
            name="uq_fre_endividamentos_fingerprint",
        ),
    )
    op.create_index("ix_fre_endividamentos_companhia_id", "fre_endividamentos", ["companhia_id"])
    op.create_index("ix_fre_endividamentos_cnpj_companhia", "fre_endividamentos", ["cnpj_companhia"])
    op.create_index("ix_fre_endividamentos_data_referencia", "fre_endividamentos", ["data_referencia"])
    op.create_index("ix_fre_endividamentos_versao", "fre_endividamentos", ["versao"])
    op.create_index("ix_fre_endividamentos_id_documento", "fre_endividamentos", ["id_documento"])
    op.create_index("ix_fre_endividamentos_ano_origem", "fre_endividamentos", ["ano_origem"])
    op.create_index(
        "ix_fre_endividamentos_empresa_periodo",
        "fre_endividamentos",
        ["cnpj_companhia", "data_referencia", "versao"],
    )

    op.create_table(
        "fre_obrigacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("data_inicio_exercicio_social", sa.Date(), nullable=True),
        sa.Column("data_fim_exercicio_social", sa.Date(), nullable=True),
        sa.Column("tipo_obrigacao", sa.Text(), nullable=True),
        sa.Column("tipo_garantia", sa.Text(), nullable=True),
        sa.Column("descricao_outras_garantias", sa.Text(), nullable=True),
        sa.Column("divida_inferior_1_ano", sa.Text(), nullable=True),
        sa.Column("divida_1a3_anos", sa.Text(), nullable=True),
        sa.Column("divida_3a5_anos", sa.Text(), nullable=True),
        sa.Column("divida_superior_5_anos", sa.Text(), nullable=True),
        sa.Column("divida_total", sa.Text(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cnpj_companhia",
            "id_documento",
            "versao",
            "data_referencia",
            "row_fingerprint",
            name="uq_fre_obrigacoes_fingerprint",
        ),
    )
    op.create_index("ix_fre_obrigacoes_companhia_id", "fre_obrigacoes", ["companhia_id"])
    op.create_index("ix_fre_obrigacoes_cnpj_companhia", "fre_obrigacoes", ["cnpj_companhia"])
    op.create_index("ix_fre_obrigacoes_data_referencia", "fre_obrigacoes", ["data_referencia"])
    op.create_index("ix_fre_obrigacoes_versao", "fre_obrigacoes", ["versao"])
    op.create_index("ix_fre_obrigacoes_id_documento", "fre_obrigacoes", ["id_documento"])
    op.create_index("ix_fre_obrigacoes_ano_origem", "fre_obrigacoes", ["ano_origem"])
    op.create_index(
        "ix_fre_obrigacoes_empresa_periodo",
        "fre_obrigacoes",
        ["cnpj_companhia", "data_referencia", "versao"],
    )

    op.create_table(
        "obrigacoes_contratuais_registros",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("tipo_registro", sa.String(length=32), nullable=False),
        sa.Column("registro_id", sa.String(length=200), nullable=False),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("acordo_id", sa.String(length=200), nullable=True),
        sa.Column("disponivel_em", sa.Date(), nullable=False),
        sa.Column("efetivo_em", sa.Date(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evidencias", sa.JSON(), nullable=False),
        sa.Column("revisor_id", sa.String(length=200), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("registrado_por", sa.String(length=200), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["codigo_cvm"], ["companhias.codigo_cvm"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "codigo_cvm",
            "tipo_registro",
            "registro_id",
            "revisao",
            name="uq_obrigacao_contratual_revisao",
        ),
    )
    op.create_index("ix_obrigacoes_contratuais_registros_codigo_cvm", "obrigacoes_contratuais_registros", ["codigo_cvm"])
    op.create_index("ix_obrigacoes_contratuais_registros_tipo_registro", "obrigacoes_contratuais_registros", ["tipo_registro"])
    op.create_index("ix_obrigacoes_contratuais_registros_registro_id", "obrigacoes_contratuais_registros", ["registro_id"])
    op.create_index("ix_obrigacoes_contratuais_registros_acordo_id", "obrigacoes_contratuais_registros", ["acordo_id"])
    op.create_index("ix_obrigacoes_contratuais_registros_disponivel_em", "obrigacoes_contratuais_registros", ["disponivel_em"])
    op.create_index(
        "ix_obrigacao_contratual_corte",
        "obrigacoes_contratuais_registros",
        ["codigo_cvm", "disponivel_em", "tipo_registro"],
    )
    op.create_index(
        "ix_obrigacao_contratual_acordo",
        "obrigacoes_contratuais_registros",
        ["codigo_cvm", "acordo_id", "disponivel_em"],
    )


def downgrade() -> None:
    op.drop_index("ix_obrigacao_contratual_acordo", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacao_contratual_corte", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacoes_contratuais_registros_disponivel_em", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacoes_contratuais_registros_acordo_id", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacoes_contratuais_registros_registro_id", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacoes_contratuais_registros_tipo_registro", table_name="obrigacoes_contratuais_registros")
    op.drop_index("ix_obrigacoes_contratuais_registros_codigo_cvm", table_name="obrigacoes_contratuais_registros")
    op.drop_table("obrigacoes_contratuais_registros")

    op.drop_index("ix_fre_obrigacoes_empresa_periodo", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_ano_origem", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_id_documento", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_versao", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_data_referencia", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_cnpj_companhia", table_name="fre_obrigacoes")
    op.drop_index("ix_fre_obrigacoes_companhia_id", table_name="fre_obrigacoes")
    op.drop_table("fre_obrigacoes")

    op.drop_index("ix_fre_endividamentos_empresa_periodo", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_ano_origem", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_id_documento", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_versao", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_data_referencia", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_cnpj_companhia", table_name="fre_endividamentos")
    op.drop_index("ix_fre_endividamentos_companhia_id", table_name="fre_endividamentos")
    op.drop_table("fre_endividamentos")
