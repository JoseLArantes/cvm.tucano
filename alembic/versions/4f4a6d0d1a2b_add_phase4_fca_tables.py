"""add_phase4_fca_tables

Revision ID: 4f4a6d0d1a2b
Revises: 857dd2fcee79
Create Date: 2026-06-08 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f4a6d0d1a2b"
down_revision: str | None = "857dd2fcee79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fca_documentos",
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
        sa.UniqueConstraint("id_documento", "versao", "data_referencia", name="uq_fca_documentos_chave_natural"),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "codigo_cvm",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
    ):
        op.create_index(op.f(f"ix_fca_documentos_{col}"), "fca_documentos", [col], unique=False)

    op.create_table(
        "fca_geral",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("data_nome_empresarial", sa.Date(), nullable=True),
        sa.Column("nome_empresarial_anterior", sa.String(length=255), nullable=True),
        sa.Column("data_constituicao", sa.Date(), nullable=True),
        sa.Column("data_registro_cvm", sa.Date(), nullable=True),
        sa.Column("categoria_registro_cvm", sa.String(length=100), nullable=True),
        sa.Column("data_categoria_registro_cvm", sa.Date(), nullable=True),
        sa.Column("situacao_registro_cvm", sa.String(length=100), nullable=True),
        sa.Column("data_situacao_registro_cvm", sa.Date(), nullable=True),
        sa.Column("pais_origem", sa.String(length=100), nullable=True),
        sa.Column("pais_custodia_valores_mobiliarios", sa.String(length=100), nullable=True),
        sa.Column("setor_atividade", sa.String(length=255), nullable=True),
        sa.Column("descricao_atividade", sa.Text(), nullable=True),
        sa.Column("situacao_emissor", sa.String(length=100), nullable=True),
        sa.Column("data_situacao_emissor", sa.Date(), nullable=True),
        sa.Column("especie_controle_acionario", sa.String(length=100), nullable=True),
        sa.Column("data_especie_controle_acionario", sa.Date(), nullable=True),
        sa.Column("dia_encerramento_exercicio_social", sa.Integer(), nullable=True),
        sa.Column("mes_encerramento_exercicio_social", sa.Integer(), nullable=True),
        sa.Column("data_alteracao_exercicio_social", sa.Date(), nullable=True),
        sa.Column("pagina_web", sa.String(length=1000), nullable=True),
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
            "id_documento", "versao", "data_referencia", "cnpj_companhia", name="uq_fca_geral_chave_natural"
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "codigo_cvm",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
    ):
        op.create_index(op.f(f"ix_fca_geral_{col}"), "fca_geral", [col], unique=False)

    op.create_table(
        "fca_enderecos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("tipo_endereco", sa.String(length=100), nullable=True),
        sa.Column("logradouro", sa.String(length=255), nullable=True),
        sa.Column("complemento", sa.String(length=255), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=True),
        sa.Column("cidade", sa.String(length=100), nullable=True),
        sa.Column("sigla_uf", sa.String(length=5), nullable=True),
        sa.Column("pais", sa.String(length=100), nullable=True),
        sa.Column("cep", sa.String(length=20), nullable=True),
        sa.Column("caixa_postal", sa.String(length=50), nullable=True),
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
            "tipo_endereco",
            "logradouro",
            "cep",
            name="uq_fca_enderecos_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
        "tipo_endereco",
        "pais",
    ):
        op.create_index(op.f(f"ix_fca_enderecos_{col}"), "fca_enderecos", [col], unique=False)

    op.create_table(
        "fca_dri",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("tipo_responsavel", sa.String(length=100), nullable=True),
        sa.Column("nome_dri", sa.String(length=255), nullable=True),
        sa.Column("cpf_responsavel", sa.String(length=20), nullable=True),
        sa.Column("tipo_endereco", sa.String(length=100), nullable=True),
        sa.Column("logradouro", sa.String(length=255), nullable=True),
        sa.Column("complemento", sa.String(length=255), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=True),
        sa.Column("cidade", sa.String(length=100), nullable=True),
        sa.Column("sigla_uf", sa.String(length=5), nullable=True),
        sa.Column("uf", sa.String(length=100), nullable=True),
        sa.Column("pais", sa.String(length=100), nullable=True),
        sa.Column("cep", sa.String(length=20), nullable=True),
        sa.Column("ddi_telefone", sa.String(length=10), nullable=True),
        sa.Column("ddd_telefone", sa.String(length=10), nullable=True),
        sa.Column("telefone", sa.String(length=50), nullable=True),
        sa.Column("ddi_fax", sa.String(length=10), nullable=True),
        sa.Column("ddd_fax", sa.String(length=10), nullable=True),
        sa.Column("fax", sa.String(length=50), nullable=True),
        sa.Column("email_dri", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_atuacao", sa.Date(), nullable=True),
        sa.Column("data_fim_atuacao", sa.Date(), nullable=True),
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
            "cpf_responsavel",
            "tipo_responsavel",
            name="uq_fca_dri_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
        "nome_dri",
        "email_dri",
    ):
        op.create_index(op.f(f"ix_fca_dri_{col}"), "fca_dri", [col], unique=False)

    op.create_table(
        "fca_auditores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("nome_auditor", sa.String(length=255), nullable=True),
        sa.Column("cpf_cnpj_auditor", sa.String(length=20), nullable=True),
        sa.Column("codigo_cvm_auditor", sa.Integer(), nullable=True),
        sa.Column("origem_auditor", sa.String(length=100), nullable=True),
        sa.Column("data_inicio_atuacao_auditor", sa.Date(), nullable=True),
        sa.Column("data_fim_atuacao_auditor", sa.Date(), nullable=True),
        sa.Column("responsavel_tecnico", sa.String(length=255), nullable=True),
        sa.Column("cpf_responsavel_tecnico", sa.String(length=20), nullable=True),
        sa.Column("data_inicio_atuacao_responsavel_tecnico", sa.Date(), nullable=True),
        sa.Column("data_fim_atuacao_responsavel_tecnico", sa.Date(), nullable=True),
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
            "cpf_cnpj_auditor",
            "codigo_cvm_auditor",
            name="uq_fca_auditores_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
        "nome_auditor",
        "codigo_cvm_auditor",
    ):
        op.create_index(op.f(f"ix_fca_auditores_{col}"), "fca_auditores", [col], unique=False)

    op.create_table(
        "fca_valores_mobiliarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("id_documento", sa.Integer(), nullable=False),
        sa.Column("nome_empresarial", sa.String(length=255), nullable=True),
        sa.Column("tipo_valor_mobiliario", sa.String(length=255), nullable=True),
        sa.Column("sigla_classe_acao_preferencial", sa.String(length=20), nullable=True),
        sa.Column("classe_acao_preferencial", sa.String(length=100), nullable=True),
        sa.Column("codigo_negociacao", sa.String(length=100), nullable=True),
        sa.Column("composicao_bdr_unit", sa.String(length=255), nullable=True),
        sa.Column("mercado", sa.String(length=100), nullable=True),
        sa.Column("sigla_entidade_administradora", sa.String(length=50), nullable=True),
        sa.Column("entidade_administradora", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_negociacao", sa.Date(), nullable=True),
        sa.Column("data_fim_negociacao", sa.Date(), nullable=True),
        sa.Column("segmento", sa.String(length=100), nullable=True),
        sa.Column("data_inicio_listagem", sa.Date(), nullable=True),
        sa.Column("data_fim_listagem", sa.Date(), nullable=True),
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
            "tipo_valor_mobiliario",
            "codigo_negociacao",
            "mercado",
            name="uq_fca_valores_mobiliarios_chave_natural",
        ),
    )
    for col in (
        "companhia_id",
        "cnpj_companhia",
        "data_referencia",
        "versao",
        "id_documento",
        "ano_origem",
        "tipo_valor_mobiliario",
    ):
        idx_col = "tipo_valor_mobiliario" if col == "tipo_valor_mobiliario" else col
        op.create_index(op.f(f"ix_fca_valores_mobiliarios_{idx_col}"), "fca_valores_mobiliarios", [col], unique=False)


def downgrade() -> None:
    for col in (
        "tipo_valor_mobiliario",
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_valores_mobiliarios_{col}"), table_name="fca_valores_mobiliarios")
    op.drop_table("fca_valores_mobiliarios")

    for col in (
        "codigo_cvm_auditor",
        "nome_auditor",
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_auditores_{col}"), table_name="fca_auditores")
    op.drop_table("fca_auditores")

    for col in (
        "email_dri",
        "nome_dri",
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_dri_{col}"), table_name="fca_dri")
    op.drop_table("fca_dri")

    for col in (
        "pais",
        "tipo_endereco",
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_enderecos_{col}"), table_name="fca_enderecos")
    op.drop_table("fca_enderecos")

    for col in (
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "codigo_cvm",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_geral_{col}"), table_name="fca_geral")
    op.drop_table("fca_geral")

    for col in (
        "ano_origem",
        "id_documento",
        "versao",
        "data_referencia",
        "codigo_cvm",
        "cnpj_companhia",
        "companhia_id",
    ):
        op.drop_index(op.f(f"ix_fca_documentos_{col}"), table_name="fca_documentos")
    op.drop_table("fca_documentos")
