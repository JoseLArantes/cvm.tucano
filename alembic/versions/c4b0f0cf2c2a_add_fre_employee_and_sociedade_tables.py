"""add_fre_employee_and_sociedade_tables

Revision ID: c4b0f0cf2c2a
Revises: 9337421f6958
Create Date: 2026-06-11 16:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4b0f0cf2c2a"
down_revision: str | None = "9337421f6958"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fre_participacoes_sociedades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("id_sociedade", sa.Integer(), nullable=False),
        sa.Column("razao_social", sa.Text(), nullable=True),
        sa.Column("cnpj", sa.String(length=14), nullable=True),
        sa.Column("tipo_sociedade", sa.Text(), nullable=True),
        sa.Column("descricao_atividades", sa.Text(), nullable=True),
        sa.Column("pais_sede", sa.Text(), nullable=True),
        sa.Column("uf_sede", sa.String(length=5), nullable=True),
        sa.Column("municipio_sede", sa.Text(), nullable=True),
        sa.Column("participacao_emissor", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("possui_registro_cvm", sa.Boolean(), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("razao_aquisicao_manutencao", sa.Text(), nullable=True),
        sa.Column("data_valor_mercado", sa.Date(), nullable=True),
        sa.Column("data_valor_contabil", sa.Date(), nullable=True),
        sa.Column("valor_mercado", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("valor_contabil", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
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
            "id_sociedade",
            name="uq_fre_participacoes_sociedades_chave_natural",
        ),
    )
    op.create_index(op.f("ix_fre_participacoes_sociedades_ano_origem"), "fre_participacoes_sociedades", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_cnpj_companhia"), "fre_participacoes_sociedades", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_codigo_cvm"), "fre_participacoes_sociedades", ["codigo_cvm"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_companhia_id"), "fre_participacoes_sociedades", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_data_referencia"), "fre_participacoes_sociedades", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_id_documento"), "fre_participacoes_sociedades", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_id_sociedade"), "fre_participacoes_sociedades", ["id_sociedade"], unique=False)
    op.create_index(op.f("ix_fre_participacoes_sociedades_versao"), "fre_participacoes_sociedades", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_posicao_local",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("posicao", sa.Text(), nullable=False),
        sa.Column("quantidade_norte", sa.Integer(), nullable=True),
        sa.Column("quantidade_nordeste", sa.Integer(), nullable=True),
        sa.Column("quantidade_centro_oeste", sa.Integer(), nullable=True),
        sa.Column("quantidade_sudeste", sa.Integer(), nullable=True),
        sa.Column("quantidade_sul", sa.Integer(), nullable=True),
        sa.Column("quantidade_exterior", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao", name="uq_fre_empregados_posicao_local_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_posicao_local_ano_origem"), "fre_empregados_posicao_local", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_cnpj_companhia"), "fre_empregados_posicao_local", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_companhia_id"), "fre_empregados_posicao_local", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_data_referencia"), "fre_empregados_posicao_local", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_id_documento"), "fre_empregados_posicao_local", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_posicao"), "fre_empregados_posicao_local", ["posicao"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_local_versao"), "fre_empregados_posicao_local", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_posicao_faixa_etaria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("posicao", sa.Text(), nullable=False),
        sa.Column("quantidade_ate_30_anos", sa.Integer(), nullable=True),
        sa.Column("quantidade_30_a_50_anos", sa.Integer(), nullable=True),
        sa.Column("quantidade_acima_50_anos", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao", name="uq_fre_empregados_posicao_faixa_etaria_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_ano_origem"), "fre_empregados_posicao_faixa_etaria", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_cnpj_companhia"), "fre_empregados_posicao_faixa_etaria", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_companhia_id"), "fre_empregados_posicao_faixa_etaria", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_data_referencia"), "fre_empregados_posicao_faixa_etaria", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_id_documento"), "fre_empregados_posicao_faixa_etaria", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_posicao"), "fre_empregados_posicao_faixa_etaria", ["posicao"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_faixa_etaria_versao"), "fre_empregados_posicao_faixa_etaria", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_posicao_declaracao_raca",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("posicao", sa.Text(), nullable=False),
        sa.Column("quantidade_amarelo", sa.Integer(), nullable=True),
        sa.Column("quantidade_branco", sa.Integer(), nullable=True),
        sa.Column("quantidade_preto", sa.Integer(), nullable=True),
        sa.Column("quantidade_pardo", sa.Integer(), nullable=True),
        sa.Column("quantidade_indigena", sa.Integer(), nullable=True),
        sa.Column("quantidade_outros", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "posicao", name="uq_fre_empregados_posicao_declaracao_raca_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_ano_origem"), "fre_empregados_posicao_declaracao_raca", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_cnpj_companhia"), "fre_empregados_posicao_declaracao_raca", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_companhia_id"), "fre_empregados_posicao_declaracao_raca", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_data_referencia"), "fre_empregados_posicao_declaracao_raca", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_id_documento"), "fre_empregados_posicao_declaracao_raca", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_posicao"), "fre_empregados_posicao_declaracao_raca", ["posicao"], unique=False)
    op.create_index(op.f("ix_fre_empregados_posicao_declaracao_raca_versao"), "fre_empregados_posicao_declaracao_raca", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_pcd",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("codigo_posicao", sa.Integer(), nullable=True),
        sa.Column("posicao", sa.Text(), nullable=False),
        sa.Column("quantidade_pcd", sa.Integer(), nullable=True),
        sa.Column("quantidade_nao_pcd", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "codigo_posicao", "posicao", name="uq_fre_empregados_pcd_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_pcd_ano_origem"), "fre_empregados_pcd", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_cnpj_companhia"), "fre_empregados_pcd", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_codigo_posicao"), "fre_empregados_pcd", ["codigo_posicao"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_companhia_id"), "fre_empregados_pcd", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_data_referencia"), "fre_empregados_pcd", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_id_documento"), "fre_empregados_pcd", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_posicao"), "fre_empregados_pcd", ["posicao"], unique=False)
    op.create_index(op.f("ix_fre_empregados_pcd_versao"), "fre_empregados_pcd", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_local_faixa_etaria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("local", sa.Text(), nullable=False),
        sa.Column("quantidade_ate_30_anos", sa.Integer(), nullable=True),
        sa.Column("quantidade_30_a_50_anos", sa.Integer(), nullable=True),
        sa.Column("quantidade_acima_50_anos", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "local", name="uq_fre_empregados_local_faixa_etaria_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_ano_origem"), "fre_empregados_local_faixa_etaria", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_cnpj_companhia"), "fre_empregados_local_faixa_etaria", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_companhia_id"), "fre_empregados_local_faixa_etaria", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_data_referencia"), "fre_empregados_local_faixa_etaria", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_id_documento"), "fre_empregados_local_faixa_etaria", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_local"), "fre_empregados_local_faixa_etaria", ["local"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_faixa_etaria_versao"), "fre_empregados_local_faixa_etaria", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_local_declaracao_raca",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("local", sa.Text(), nullable=False),
        sa.Column("quantidade_amarelo", sa.Integer(), nullable=True),
        sa.Column("quantidade_branco", sa.Integer(), nullable=True),
        sa.Column("quantidade_preto", sa.Integer(), nullable=True),
        sa.Column("quantidade_pardo", sa.Integer(), nullable=True),
        sa.Column("quantidade_indigena", sa.Integer(), nullable=True),
        sa.Column("quantidade_outros", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "local", name="uq_fre_empregados_local_declaracao_raca_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_ano_origem"), "fre_empregados_local_declaracao_raca", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_cnpj_companhia"), "fre_empregados_local_declaracao_raca", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_companhia_id"), "fre_empregados_local_declaracao_raca", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_data_referencia"), "fre_empregados_local_declaracao_raca", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_id_documento"), "fre_empregados_local_declaracao_raca", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_local"), "fre_empregados_local_declaracao_raca", ["local"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_raca_versao"), "fre_empregados_local_declaracao_raca", ["versao"], unique=False)

    op.create_table(
        "fre_empregados_local_declaracao_genero",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.Text(), nullable=True),
        sa.Column("local", sa.Text(), nullable=False),
        sa.Column("quantidade_feminino", sa.Integer(), nullable=True),
        sa.Column("quantidade_masculino", sa.Integer(), nullable=True),
        sa.Column("quantidade_nao_binario", sa.Integer(), nullable=True),
        sa.Column("quantidade_outros", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
        sa.Column("arquivo_origem", sa.Text(), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", "cnpj_companhia", "local", name="uq_fre_empregados_local_declaracao_genero_chave_natural"),
    )
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_ano_origem"), "fre_empregados_local_declaracao_genero", ["ano_origem"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_cnpj_companhia"), "fre_empregados_local_declaracao_genero", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_companhia_id"), "fre_empregados_local_declaracao_genero", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_data_referencia"), "fre_empregados_local_declaracao_genero", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_id_documento"), "fre_empregados_local_declaracao_genero", ["id_documento"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_local"), "fre_empregados_local_declaracao_genero", ["local"], unique=False)
    op.create_index(op.f("ix_fre_empregados_local_declaracao_genero_versao"), "fre_empregados_local_declaracao_genero", ["versao"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_versao"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_local"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_id_documento"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_data_referencia"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_companhia_id"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_cnpj_companhia"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_genero_ano_origem"), table_name="fre_empregados_local_declaracao_genero")
    op.drop_table("fre_empregados_local_declaracao_genero")

    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_versao"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_local"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_id_documento"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_data_referencia"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_companhia_id"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_cnpj_companhia"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_local_declaracao_raca_ano_origem"), table_name="fre_empregados_local_declaracao_raca")
    op.drop_table("fre_empregados_local_declaracao_raca")

    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_versao"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_local"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_id_documento"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_data_referencia"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_companhia_id"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_cnpj_companhia"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_local_faixa_etaria_ano_origem"), table_name="fre_empregados_local_faixa_etaria")
    op.drop_table("fre_empregados_local_faixa_etaria")

    op.drop_index(op.f("ix_fre_empregados_pcd_versao"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_posicao"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_id_documento"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_data_referencia"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_companhia_id"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_codigo_posicao"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_cnpj_companhia"), table_name="fre_empregados_pcd")
    op.drop_index(op.f("ix_fre_empregados_pcd_ano_origem"), table_name="fre_empregados_pcd")
    op.drop_table("fre_empregados_pcd")

    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_versao"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_posicao"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_id_documento"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_data_referencia"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_companhia_id"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_cnpj_companhia"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_index(op.f("ix_fre_empregados_posicao_declaracao_raca_ano_origem"), table_name="fre_empregados_posicao_declaracao_raca")
    op.drop_table("fre_empregados_posicao_declaracao_raca")

    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_versao"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_posicao"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_id_documento"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_data_referencia"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_companhia_id"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_cnpj_companhia"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_index(op.f("ix_fre_empregados_posicao_faixa_etaria_ano_origem"), table_name="fre_empregados_posicao_faixa_etaria")
    op.drop_table("fre_empregados_posicao_faixa_etaria")

    op.drop_index(op.f("ix_fre_empregados_posicao_local_versao"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_posicao"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_id_documento"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_data_referencia"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_companhia_id"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_cnpj_companhia"), table_name="fre_empregados_posicao_local")
    op.drop_index(op.f("ix_fre_empregados_posicao_local_ano_origem"), table_name="fre_empregados_posicao_local")
    op.drop_table("fre_empregados_posicao_local")

    op.drop_index(op.f("ix_fre_participacoes_sociedades_versao"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_id_sociedade"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_id_documento"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_data_referencia"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_companhia_id"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_codigo_cvm"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_cnpj_companhia"), table_name="fre_participacoes_sociedades")
    op.drop_index(op.f("ix_fre_participacoes_sociedades_ano_origem"), table_name="fre_participacoes_sociedades")
    op.drop_table("fre_participacoes_sociedades")
