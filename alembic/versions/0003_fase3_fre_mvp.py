"""fase3 fre mvp

Revision ID: 0003_fase3_fre_mvp
Revises: 0002_fase2_dfp_itr
Create Date: 2026-05-30 00:00:02.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_fase3_fre_mvp"
down_revision: str | None = "0002_fase2_dfp_itr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fre_documentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
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
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", name="uq_fre_documentos_chave_natural"),
    )
    op.create_index(op.f("ix_fre_documentos_ano_origem"), "fre_documentos", ["ano_origem"])
    op.create_index(op.f("ix_fre_documentos_cnpj_companhia"), "fre_documentos", ["cnpj_companhia"])
    op.create_index(op.f("ix_fre_documentos_codigo_cvm"), "fre_documentos", ["codigo_cvm"])
    op.create_index(op.f("ix_fre_documentos_companhia_id"), "fre_documentos", ["companhia_id"])
    op.create_index(op.f("ix_fre_documentos_data_referencia"), "fre_documentos", ["data_referencia"])
    op.create_index(op.f("ix_fre_documentos_id_documento"), "fre_documentos", ["id_documento"])
    op.create_index(op.f("ix_fre_documentos_versao"), "fre_documentos", ["versao"])

    op.create_table(
        "fre_auditores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("id_auditor", sa.Integer(), nullable=False),
        sa.Column("auditor", sa.String(length=255), nullable=True),
        sa.Column("cpf_auditor", sa.String(length=20), nullable=True),
        sa.Column("cnpj_auditor", sa.String(length=14), nullable=True),
        sa.Column("codigo_cvm_auditor", sa.Integer(), nullable=True),
        sa.Column("tipo_origem_auditor", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_contratacao", sa.Date(), nullable=True),
        sa.Column("data_fim_contratacao", sa.Date(), nullable=True),
        sa.Column("data_inicio_prestacao_servico", sa.Date(), nullable=True),
        sa.Column("servico_contratado", sa.Text(), nullable=True),
        sa.Column("remuneracao_auditor", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("justificativa_substituicao", sa.Text(), nullable=True),
        sa.Column("razao_apresentada", sa.Text(), nullable=True),
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
            "id_auditor",
            name="uq_fre_auditores_chave_natural",
        ),
    )
    op.create_index(op.f("ix_fre_auditores_ano_origem"), "fre_auditores", ["ano_origem"])
    op.create_index(op.f("ix_fre_auditores_cnpj_companhia"), "fre_auditores", ["cnpj_companhia"])
    op.create_index(op.f("ix_fre_auditores_companhia_id"), "fre_auditores", ["companhia_id"])
    op.create_index(op.f("ix_fre_auditores_data_referencia"), "fre_auditores", ["data_referencia"])
    op.create_index(op.f("ix_fre_auditores_id_auditor"), "fre_auditores", ["id_auditor"])
    op.create_index(op.f("ix_fre_auditores_id_documento"), "fre_auditores", ["id_documento"])
    op.create_index(op.f("ix_fre_auditores_versao"), "fre_auditores", ["versao"])

    op.create_table(
        "fre_capital_social",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("id_capital_social", sa.Integer(), nullable=False),
        sa.Column("tipo_capital", sa.String(length=255), nullable=True),
        sa.Column("data_autorizacao_aprovacao", sa.Date(), nullable=True),
        sa.Column("valor_capital", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("prazo_integralizacao", sa.String(length=255), nullable=True),
        sa.Column("quantidade_acoes_ordinarias", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_acoes_preferenciais", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("quantidade_total_acoes", sa.Numeric(precision=30, scale=6), nullable=True),
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
            "id_capital_social",
            name="uq_fre_capital_social_chave_natural",
        ),
    )
    op.create_index(op.f("ix_fre_capital_social_ano_origem"), "fre_capital_social", ["ano_origem"])
    op.create_index(op.f("ix_fre_capital_social_cnpj_companhia"), "fre_capital_social", ["cnpj_companhia"])
    op.create_index(op.f("ix_fre_capital_social_companhia_id"), "fre_capital_social", ["companhia_id"])
    op.create_index(op.f("ix_fre_capital_social_data_referencia"), "fre_capital_social", ["data_referencia"])
    op.create_index(op.f("ix_fre_capital_social_id_capital_social"), "fre_capital_social", ["id_capital_social"])
    op.create_index(op.f("ix_fre_capital_social_id_documento"), "fre_capital_social", ["id_documento"])
    op.create_index(op.f("ix_fre_capital_social_versao"), "fre_capital_social", ["versao"])

    op.create_table(
        "fre_posicoes_acionarias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("id_acionista", sa.Integer(), nullable=False),
        sa.Column("acionista", sa.String(length=255), nullable=True),
        sa.Column("tipo_pessoa_acionista", sa.String(length=100), nullable=True),
        sa.Column("cpf_cnpj_acionista", sa.String(length=20), nullable=True),
        sa.Column("id_acionista_relacionado", sa.Integer(), nullable=True),
        sa.Column("acionista_relacionado", sa.String(length=255), nullable=True),
        sa.Column("tipo_pessoa_acionista_relacionado", sa.String(length=100), nullable=True),
        sa.Column("cpf_cnpj_acionista_relacionado", sa.String(length=20), nullable=True),
        sa.Column("quantidade_acao_ordinaria_circulacao", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("percentual_acao_ordinaria_circulacao", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("quantidade_acao_preferencial_circulacao", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("percentual_acao_preferencial_circulacao", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("quantidade_total_acoes_circulacao", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("percentual_total_acoes_circulacao", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("nacionalidade", sa.String(length=100), nullable=True),
        sa.Column("sigla_uf", sa.String(length=5), nullable=True),
        sa.Column("residente_exterior", sa.Boolean(), nullable=True),
        sa.Column("representante_legal", sa.String(length=255), nullable=True),
        sa.Column("tipo_pessoa_representante_legal", sa.String(length=100), nullable=True),
        sa.Column("cpf_cnpj_representante_legal", sa.String(length=20), nullable=True),
        sa.Column("data_composicao_capital_social", sa.Date(), nullable=True),
        sa.Column("data_ultima_alteracao", sa.Date(), nullable=True),
        sa.Column("acionista_controlador", sa.Boolean(), nullable=True),
        sa.Column("participante_acordo_acionistas", sa.Boolean(), nullable=True),
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
            "id_acionista",
            name="uq_fre_posicoes_acionarias_chave_natural",
        ),
    )
    op.create_index(op.f("ix_fre_posicoes_acionarias_ano_origem"), "fre_posicoes_acionarias", ["ano_origem"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_cnpj_companhia"), "fre_posicoes_acionarias", ["cnpj_companhia"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_companhia_id"), "fre_posicoes_acionarias", ["companhia_id"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_data_referencia"), "fre_posicoes_acionarias", ["data_referencia"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_id_acionista"), "fre_posicoes_acionarias", ["id_acionista"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_id_documento"), "fre_posicoes_acionarias", ["id_documento"])
    op.create_index(op.f("ix_fre_posicoes_acionarias_versao"), "fre_posicoes_acionarias", ["versao"])

    op.create_table(
        "fre_remuneracoes_totais_orgaos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_exercicio_social", sa.Date(), nullable=True),
        sa.Column("data_fim_exercicio_social", sa.Date(), nullable=True),
        sa.Column("total_remuneracao", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("orgao_administracao", sa.String(length=255), nullable=True),
        sa.Column("numero_membros", sa.Integer(), nullable=True),
        sa.Column("total_remuneracao_orgao", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("numero_membros_remunerados", sa.Integer(), nullable=True),
        sa.Column("salario", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("beneficios_diretos_indiretos", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("participacoes_comites", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("outros_valores_fixos", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("descricao_outros_remuneracoes_fixas", sa.Text(), nullable=True),
        sa.Column("bonus", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("participacao_resultados", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("participacao_reunioes", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("outros_valores_variaveis", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("comissoes", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("descricao_outros_remuneracoes_variaveis", sa.Text(), nullable=True),
        sa.Column("pos_emprego", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("cessacao_cargo", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("baseada_acoes", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
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
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_remuneracoes_totais_orgaos_chave_natural",
        ),
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_ano_origem"),
        "fre_remuneracoes_totais_orgaos",
        ["ano_origem"],
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_cnpj_companhia"),
        "fre_remuneracoes_totais_orgaos",
        ["cnpj_companhia"],
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_companhia_id"),
        "fre_remuneracoes_totais_orgaos",
        ["companhia_id"],
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_data_referencia"),
        "fre_remuneracoes_totais_orgaos",
        ["data_referencia"],
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_id_documento"),
        "fre_remuneracoes_totais_orgaos",
        ["id_documento"],
    )
    op.create_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_versao"),
        "fre_remuneracoes_totais_orgaos",
        ["versao"],
    )

    op.create_table(
        "fre_empregados_posicao_genero",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_companhia", sa.String(length=255), nullable=True),
        sa.Column("posicao", sa.String(length=255), nullable=False),
        sa.Column("quantidade_feminino", sa.Integer(), nullable=True),
        sa.Column("quantidade_masculino", sa.Integer(), nullable=True),
        sa.Column("quantidade_nao_binario", sa.Integer(), nullable=True),
        sa.Column("quantidade_outros", sa.Integer(), nullable=True),
        sa.Column("quantidade_sem_resposta", sa.Integer(), nullable=True),
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
            "posicao",
            name="uq_fre_empregados_posicao_genero_chave_natural",
        ),
    )
    op.create_index(
        op.f("ix_fre_empregados_posicao_genero_ano_origem"),
        "fre_empregados_posicao_genero",
        ["ano_origem"],
    )
    op.create_index(
        op.f("ix_fre_empregados_posicao_genero_cnpj_companhia"),
        "fre_empregados_posicao_genero",
        ["cnpj_companhia"],
    )
    op.create_index(
        op.f("ix_fre_empregados_posicao_genero_companhia_id"),
        "fre_empregados_posicao_genero",
        ["companhia_id"],
    )
    op.create_index(
        op.f("ix_fre_empregados_posicao_genero_data_referencia"),
        "fre_empregados_posicao_genero",
        ["data_referencia"],
    )
    op.create_index(
        op.f("ix_fre_empregados_posicao_genero_id_documento"),
        "fre_empregados_posicao_genero",
        ["id_documento"],
    )
    op.create_index(op.f("ix_fre_empregados_posicao_genero_posicao"), "fre_empregados_posicao_genero", ["posicao"])
    op.create_index(op.f("ix_fre_empregados_posicao_genero_versao"), "fre_empregados_posicao_genero", ["versao"])


def downgrade() -> None:
    op.drop_index(op.f("ix_fre_empregados_posicao_genero_versao"), table_name="fre_empregados_posicao_genero")
    op.drop_index(op.f("ix_fre_empregados_posicao_genero_posicao"), table_name="fre_empregados_posicao_genero")
    op.drop_index(
        op.f("ix_fre_empregados_posicao_genero_id_documento"),
        table_name="fre_empregados_posicao_genero",
    )
    op.drop_index(
        op.f("ix_fre_empregados_posicao_genero_data_referencia"),
        table_name="fre_empregados_posicao_genero",
    )
    op.drop_index(
        op.f("ix_fre_empregados_posicao_genero_companhia_id"),
        table_name="fre_empregados_posicao_genero",
    )
    op.drop_index(
        op.f("ix_fre_empregados_posicao_genero_cnpj_companhia"),
        table_name="fre_empregados_posicao_genero",
    )
    op.drop_index(
        op.f("ix_fre_empregados_posicao_genero_ano_origem"),
        table_name="fre_empregados_posicao_genero",
    )
    op.drop_table("fre_empregados_posicao_genero")

    op.drop_index(op.f("ix_fre_remuneracoes_totais_orgaos_versao"), table_name="fre_remuneracoes_totais_orgaos")
    op.drop_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_id_documento"),
        table_name="fre_remuneracoes_totais_orgaos",
    )
    op.drop_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_data_referencia"),
        table_name="fre_remuneracoes_totais_orgaos",
    )
    op.drop_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_companhia_id"),
        table_name="fre_remuneracoes_totais_orgaos",
    )
    op.drop_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_cnpj_companhia"),
        table_name="fre_remuneracoes_totais_orgaos",
    )
    op.drop_index(
        op.f("ix_fre_remuneracoes_totais_orgaos_ano_origem"),
        table_name="fre_remuneracoes_totais_orgaos",
    )
    op.drop_table("fre_remuneracoes_totais_orgaos")

    op.drop_index(op.f("ix_fre_posicoes_acionarias_versao"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_id_documento"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_id_acionista"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_data_referencia"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_companhia_id"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_cnpj_companhia"), table_name="fre_posicoes_acionarias")
    op.drop_index(op.f("ix_fre_posicoes_acionarias_ano_origem"), table_name="fre_posicoes_acionarias")
    op.drop_table("fre_posicoes_acionarias")

    op.drop_index(op.f("ix_fre_capital_social_versao"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_id_documento"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_id_capital_social"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_data_referencia"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_companhia_id"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_cnpj_companhia"), table_name="fre_capital_social")
    op.drop_index(op.f("ix_fre_capital_social_ano_origem"), table_name="fre_capital_social")
    op.drop_table("fre_capital_social")

    op.drop_index(op.f("ix_fre_auditores_versao"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_id_documento"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_id_auditor"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_data_referencia"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_companhia_id"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_cnpj_companhia"), table_name="fre_auditores")
    op.drop_index(op.f("ix_fre_auditores_ano_origem"), table_name="fre_auditores")
    op.drop_table("fre_auditores")

    op.drop_index(op.f("ix_fre_documentos_versao"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_id_documento"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_data_referencia"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_companhia_id"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_codigo_cvm"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_cnpj_companhia"), table_name="fre_documentos")
    op.drop_index(op.f("ix_fre_documentos_ano_origem"), table_name="fre_documentos")
    op.drop_table("fre_documentos")
