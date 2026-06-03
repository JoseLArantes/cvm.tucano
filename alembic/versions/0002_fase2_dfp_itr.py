"""fase2 dfp itr

Revision ID: 0002_fase2_dfp_itr
Revises: 0001_fase1_fundacao
Create Date: 2026-05-30 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_fase2_dfp_itr"
down_revision: str | None = "0001_fase1_fundacao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documentos_financeiros",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("tipo_formulario", sa.String(length=10), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("denominacao_companhia", sa.String(length=255), nullable=True),
        sa.Column("categoria_documento", sa.String(length=255), nullable=True),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("data_recebimento", sa.Date(), nullable=True),
        sa.Column("link_documento", sa.String(length=1000), nullable=True),
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
            "tipo_formulario",
            "id_documento",
            "versao",
            "data_referencia",
            name="uq_documentos_financeiros_chave_natural",
        ),
    )
    op.create_index(op.f("ix_documentos_financeiros_ano_origem"), "documentos_financeiros", ["ano_origem"])
    op.create_index(op.f("ix_documentos_financeiros_cnpj_companhia"), "documentos_financeiros", ["cnpj_companhia"])
    op.create_index(op.f("ix_documentos_financeiros_codigo_cvm"), "documentos_financeiros", ["codigo_cvm"])
    op.create_index(op.f("ix_documentos_financeiros_companhia_id"), "documentos_financeiros", ["companhia_id"])
    op.create_index(op.f("ix_documentos_financeiros_data_referencia"), "documentos_financeiros", ["data_referencia"])
    op.create_index(op.f("ix_documentos_financeiros_id_documento"), "documentos_financeiros", ["id_documento"])
    op.create_index(op.f("ix_documentos_financeiros_tipo_formulario"), "documentos_financeiros", ["tipo_formulario"])
    op.create_index(op.f("ix_documentos_financeiros_versao"), "documentos_financeiros", ["versao"])

    op.create_table(
        "demonstracoes_financeiras",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("tipo_formulario", sa.String(length=10), nullable=False),
        sa.Column("tipo_demonstracao", sa.String(length=80), nullable=False),
        sa.Column("escopo_demonstracao", sa.String(length=20), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("denominacao_companhia", sa.String(length=255), nullable=True),
        sa.Column("grupo_demonstracao", sa.String(length=50), nullable=True),
        sa.Column("moeda", sa.String(length=20), nullable=True),
        sa.Column("escala_moeda", sa.String(length=50), nullable=True),
        sa.Column("ordem_exercicio", sa.String(length=20), nullable=True),
        sa.Column("data_inicio_exercicio", sa.Date(), nullable=True),
        sa.Column("data_fim_exercicio", sa.Date(), nullable=True),
        sa.Column("codigo_conta", sa.String(length=40), nullable=True),
        sa.Column("descricao_conta", sa.Text(), nullable=True),
        sa.Column("valor_conta", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("conta_fixa", sa.Boolean(), nullable=True),
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
            "tipo_formulario",
            "tipo_demonstracao",
            "escopo_demonstracao",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "grupo_demonstracao",
            "ordem_exercicio",
            "data_fim_exercicio",
            "codigo_conta",
            name="uq_demonstracoes_financeiras_chave_natural",
        ),
    )
    op.create_index(op.f("ix_demonstracoes_financeiras_ano_origem"), "demonstracoes_financeiras", ["ano_origem"])
    op.create_index(
        op.f("ix_demonstracoes_financeiras_cnpj_companhia"),
        "demonstracoes_financeiras",
        ["cnpj_companhia"],
    )
    op.create_index(op.f("ix_demonstracoes_financeiras_codigo_conta"), "demonstracoes_financeiras", ["codigo_conta"])
    op.create_index(op.f("ix_demonstracoes_financeiras_codigo_cvm"), "demonstracoes_financeiras", ["codigo_cvm"])
    op.create_index(op.f("ix_demonstracoes_financeiras_companhia_id"), "demonstracoes_financeiras", ["companhia_id"])
    op.create_index(
        op.f("ix_demonstracoes_financeiras_data_referencia"),
        "demonstracoes_financeiras",
        ["data_referencia"],
    )
    op.create_index(
        op.f("ix_demonstracoes_financeiras_escopo_demonstracao"),
        "demonstracoes_financeiras",
        ["escopo_demonstracao"],
    )
    op.create_index(
        op.f("ix_demonstracoes_financeiras_tipo_demonstracao"),
        "demonstracoes_financeiras",
        ["tipo_demonstracao"],
    )
    op.create_index(
        op.f("ix_demonstracoes_financeiras_tipo_formulario"),
        "demonstracoes_financeiras",
        ["tipo_formulario"],
    )
    op.create_index(op.f("ix_demonstracoes_financeiras_versao"), "demonstracoes_financeiras", ["versao"])

    op.create_table(
        "composicoes_capital",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("tipo_formulario", sa.String(length=10), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("denominacao_companhia", sa.String(length=255), nullable=True),
        sa.Column(
            "quantidade_acoes_ordinarias_capital_integralizado",
            sa.Numeric(precision=30, scale=6),
            nullable=True,
        ),
        sa.Column(
            "quantidade_acoes_preferenciais_capital_integralizado",
            sa.Numeric(precision=30, scale=6),
            nullable=True,
        ),
        sa.Column("quantidade_total_acoes_capital_integralizado", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_ordinarias_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_preferenciais_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_total_acoes_tesouraria", sa.Numeric(precision=30, scale=6), nullable=True),
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
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            name="uq_composicoes_capital_chave_natural",
        ),
    )
    op.create_index(op.f("ix_composicoes_capital_ano_origem"), "composicoes_capital", ["ano_origem"])
    op.create_index(op.f("ix_composicoes_capital_cnpj_companhia"), "composicoes_capital", ["cnpj_companhia"])
    op.create_index(op.f("ix_composicoes_capital_codigo_cvm"), "composicoes_capital", ["codigo_cvm"])
    op.create_index(op.f("ix_composicoes_capital_companhia_id"), "composicoes_capital", ["companhia_id"])
    op.create_index(op.f("ix_composicoes_capital_data_referencia"), "composicoes_capital", ["data_referencia"])
    op.create_index(op.f("ix_composicoes_capital_tipo_formulario"), "composicoes_capital", ["tipo_formulario"])
    op.create_index(op.f("ix_composicoes_capital_versao"), "composicoes_capital", ["versao"])

    op.create_table(
        "pareceres_financeiros",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("tipo_formulario", sa.String(length=10), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("denominacao_companhia", sa.String(length=255), nullable=True),
        sa.Column("tipo_relatorio_auditor", sa.String(length=255), nullable=True),
        sa.Column("tipo_parecer_declaracao", sa.String(length=255), nullable=True),
        sa.Column("numero_item_parecer_declaracao", sa.String(length=100), nullable=True),
        sa.Column("texto_parecer_declaracao", sa.Text(), nullable=True),
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
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "tipo_relatorio_auditor",
            "tipo_parecer_declaracao",
            "numero_item_parecer_declaracao",
            name="uq_pareceres_financeiros_chave_natural",
        ),
    )
    op.create_index(op.f("ix_pareceres_financeiros_ano_origem"), "pareceres_financeiros", ["ano_origem"])
    op.create_index(op.f("ix_pareceres_financeiros_cnpj_companhia"), "pareceres_financeiros", ["cnpj_companhia"])
    op.create_index(op.f("ix_pareceres_financeiros_codigo_cvm"), "pareceres_financeiros", ["codigo_cvm"])
    op.create_index(op.f("ix_pareceres_financeiros_companhia_id"), "pareceres_financeiros", ["companhia_id"])
    op.create_index(op.f("ix_pareceres_financeiros_data_referencia"), "pareceres_financeiros", ["data_referencia"])
    op.create_index(op.f("ix_pareceres_financeiros_tipo_formulario"), "pareceres_financeiros", ["tipo_formulario"])
    op.create_index(op.f("ix_pareceres_financeiros_versao"), "pareceres_financeiros", ["versao"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pareceres_financeiros_versao"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_tipo_formulario"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_data_referencia"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_companhia_id"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_codigo_cvm"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_cnpj_companhia"), table_name="pareceres_financeiros")
    op.drop_index(op.f("ix_pareceres_financeiros_ano_origem"), table_name="pareceres_financeiros")
    op.drop_table("pareceres_financeiros")

    op.drop_index(op.f("ix_composicoes_capital_versao"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_tipo_formulario"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_data_referencia"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_companhia_id"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_codigo_cvm"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_cnpj_companhia"), table_name="composicoes_capital")
    op.drop_index(op.f("ix_composicoes_capital_ano_origem"), table_name="composicoes_capital")
    op.drop_table("composicoes_capital")

    op.drop_index(op.f("ix_demonstracoes_financeiras_versao"), table_name="demonstracoes_financeiras")
    op.drop_index(
        op.f("ix_demonstracoes_financeiras_tipo_formulario"),
        table_name="demonstracoes_financeiras",
    )
    op.drop_index(
        op.f("ix_demonstracoes_financeiras_tipo_demonstracao"),
        table_name="demonstracoes_financeiras",
    )
    op.drop_index(
        op.f("ix_demonstracoes_financeiras_escopo_demonstracao"),
        table_name="demonstracoes_financeiras",
    )
    op.drop_index(
        op.f("ix_demonstracoes_financeiras_data_referencia"),
        table_name="demonstracoes_financeiras",
    )
    op.drop_index(op.f("ix_demonstracoes_financeiras_companhia_id"), table_name="demonstracoes_financeiras")
    op.drop_index(op.f("ix_demonstracoes_financeiras_codigo_cvm"), table_name="demonstracoes_financeiras")
    op.drop_index(op.f("ix_demonstracoes_financeiras_codigo_conta"), table_name="demonstracoes_financeiras")
    op.drop_index(op.f("ix_demonstracoes_financeiras_cnpj_companhia"), table_name="demonstracoes_financeiras")
    op.drop_index(op.f("ix_demonstracoes_financeiras_ano_origem"), table_name="demonstracoes_financeiras")
    op.drop_table("demonstracoes_financeiras")

    op.drop_index(op.f("ix_documentos_financeiros_versao"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_tipo_formulario"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_id_documento"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_data_referencia"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_companhia_id"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_codigo_cvm"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_cnpj_companhia"), table_name="documentos_financeiros")
    op.drop_index(op.f("ix_documentos_financeiros_ano_origem"), table_name="documentos_financeiros")
    op.drop_table("documentos_financeiros")
