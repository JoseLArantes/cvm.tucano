"""fase1 fundacao

Revision ID: 0001_fase1_fundacao
Revises: 
Create Date: 2026-05-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_fase1_fundacao"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companhias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("denominacao_social", sa.String(length=255), nullable=True),
        sa.Column("denominacao_comercial", sa.String(length=255), nullable=True),
        sa.Column("situacao_registro", sa.String(length=255), nullable=True),
        sa.Column("data_registro", sa.Date(), nullable=True),
        sa.Column("data_constituicao", sa.Date(), nullable=True),
        sa.Column("data_cancelamento", sa.Date(), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_situacao", sa.Date(), nullable=True),
        sa.Column("setor_atividade", sa.String(length=255), nullable=True),
        sa.Column("tipo_mercado", sa.String(length=255), nullable=True),
        sa.Column("categoria_registro", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_categoria", sa.Date(), nullable=True),
        sa.Column("situacao_emissor", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_situacao_emissor", sa.Date(), nullable=True),
        sa.Column("controle_acionario", sa.String(length=255), nullable=True),
        sa.Column("endereco", sa.JSON(), nullable=False),
        sa.Column("responsavel", sa.JSON(), nullable=False),
        sa.Column("auditor", sa.String(length=255), nullable=True),
        sa.Column("cnpj_auditor", sa.String(length=14), nullable=True),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "sincronizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj_companhia"),
        sa.UniqueConstraint("codigo_cvm"),
    )
    op.create_index(op.f("ix_companhias_cnpj_companhia"), "companhias", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_companhias_codigo_cvm"), "companhias", ["codigo_cvm"], unique=False)

    op.create_table(
        "execucoes_sincronizacao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo_fonte", sa.String(length=50), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("arquivo", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("hash_arquivo", sa.String(length=64), nullable=True),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finalizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_linhas_lidas", sa.Integer(), nullable=False),
        sa.Column("total_inseridos", sa.Integer(), nullable=False),
        sa.Column("total_atualizados", sa.Integer(), nullable=False),
        sa.Column("total_inalterados", sa.Integer(), nullable=False),
        sa.Column("total_rejeitados", sa.Integer(), nullable=False),
        sa.Column("mensagem_erro", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execucoes_sincronizacao_hash_arquivo"),
        "execucoes_sincronizacao",
        ["hash_arquivo"],
        unique=False,
    )
    op.create_index(op.f("ix_execucoes_sincronizacao_ano"), "execucoes_sincronizacao", ["ano"], unique=False)
    op.create_index(
        op.f("ix_execucoes_sincronizacao_tipo_fonte"),
        "execucoes_sincronizacao",
        ["tipo_fonte"],
        unique=False,
    )

    op.create_table(
        "historico_alteracoes_campos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidade", sa.String(length=100), nullable=False),
        sa.Column("entidade_id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("campo", sa.String(length=100), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_novo", sa.Text(), nullable=True),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_historico_alteracoes_campos_companhia_id"),
        "historico_alteracoes_campos",
        ["companhia_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historico_alteracoes_campos_entidade"),
        "historico_alteracoes_campos",
        ["entidade"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historico_alteracoes_campos_entidade_id"),
        "historico_alteracoes_campos",
        ["entidade_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historico_alteracoes_campos_execucao_sincronizacao_id"),
        "historico_alteracoes_campos",
        ["execucao_sincronizacao_id"],
        unique=False,
    )

    op.create_table(
        "registros_quarentena",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=True),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("motivo", sa.String(length=255), nullable=False),
        sa.Column("dados_originais", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_registros_quarentena_execucao_sincronizacao_id"),
        "registros_quarentena",
        ["execucao_sincronizacao_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_registros_quarentena_execucao_sincronizacao_id"), table_name="registros_quarentena")
    op.drop_table("registros_quarentena")
    op.drop_index(
        op.f("ix_historico_alteracoes_campos_execucao_sincronizacao_id"),
        table_name="historico_alteracoes_campos",
    )
    op.drop_index(op.f("ix_historico_alteracoes_campos_entidade_id"), table_name="historico_alteracoes_campos")
    op.drop_index(op.f("ix_historico_alteracoes_campos_entidade"), table_name="historico_alteracoes_campos")
    op.drop_index(op.f("ix_historico_alteracoes_campos_companhia_id"), table_name="historico_alteracoes_campos")
    op.drop_table("historico_alteracoes_campos")
    op.drop_index(op.f("ix_execucoes_sincronizacao_tipo_fonte"), table_name="execucoes_sincronizacao")
    op.drop_index(op.f("ix_execucoes_sincronizacao_ano"), table_name="execucoes_sincronizacao")
    op.drop_index(op.f("ix_execucoes_sincronizacao_hash_arquivo"), table_name="execucoes_sincronizacao")
    op.drop_table("execucoes_sincronizacao")
    op.drop_index(op.f("ix_companhias_codigo_cvm"), table_name="companhias")
    op.drop_index(op.f("ix_companhias_cnpj_companhia"), table_name="companhias")
    op.drop_table("companhias")
