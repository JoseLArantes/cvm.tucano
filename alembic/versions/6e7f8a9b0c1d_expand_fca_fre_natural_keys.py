"""expand fca and fre natural keys

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-06-15 02:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e7f8a9b0c1d"
down_revision: str | None = "5d6e7f8a9b0c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_fca_dri_chave_natural", "fca_dri", type_="unique")
    op.create_unique_constraint(
        "uq_fca_dri_chave_natural",
        "fca_dri",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_responsavel",
            "tipo_responsavel",
            "data_inicio_atuacao",
            "tipo_endereco",
            "logradouro",
            "cep",
            "telefone",
            "email_dri",
        ],
    )

    op.drop_constraint("uq_fca_auditores_chave_natural", "fca_auditores", type_="unique")
    op.create_unique_constraint(
        "uq_fca_auditores_chave_natural",
        "fca_auditores",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_cnpj_auditor",
            "codigo_cvm_auditor",
            "data_inicio_atuacao_auditor",
            "data_fim_atuacao_auditor",
            "responsavel_tecnico",
            "cpf_responsavel_tecnico",
            "data_inicio_atuacao_responsavel_tecnico",
        ],
    )

    op.drop_constraint("uq_fca_valores_mobiliarios_chave_natural", "fca_valores_mobiliarios", type_="unique")
    op.create_unique_constraint(
        "uq_fca_valores_mobiliarios_chave_natural",
        "fca_valores_mobiliarios",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "tipo_valor_mobiliario",
            "codigo_negociacao",
            "mercado",
            "sigla_classe_acao_preferencial",
            "classe_acao_preferencial",
            "composicao_bdr_unit",
            "data_inicio_negociacao",
            "data_fim_negociacao",
            "data_inicio_listagem",
            "data_fim_listagem",
        ],
    )

    op.drop_constraint(
        "uq_fre_posicoes_acionarias_classes_acoes_chave_natural",
        "fre_posicoes_acionarias_classes_acoes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_posicoes_acionarias_classes_acoes_chave_natural",
        "fre_posicoes_acionarias_classes_acoes",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_acionista",
            "tipo_classe_acao_preferencial",
            "quantidade_acoes",
            "percentual_acoes",
        ],
    )

    op.drop_constraint(
        "uq_fre_admin_memb_cons_fisc_chave_natural",
        "fre_administradores_membros_conselho_fiscal",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_admin_memb_cons_fisc_chave_natural",
        "fre_administradores_membros_conselho_fiscal",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "orgao_administracao",
            "data_eleicao",
            "data_posse",
        ],
    )

    op.drop_constraint("uq_fre_membros_comites_chave_natural", "fre_membros_comites", type_="unique")
    op.create_unique_constraint(
        "uq_fre_membros_comites_chave_natural",
        "fre_membros_comites",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "tipo_comite",
            "descricao_outros_comites",
        ],
    )

    op.drop_constraint("uq_fre_relacoes_familiares_chave_natural", "fre_relacoes_familiares", type_="unique")
    op.create_unique_constraint(
        "uq_fre_relacoes_familiares_chave_natural",
        "fre_relacoes_familiares",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_parentesco",
            "cnpj_emissor_pessoa_relacionada",
            "nome_emissor_pessoa_relacionada",
            "cargo_Pessoa_relacionada",
        ],
    )

    op.drop_constraint(
        "uq_fre_relacoes_subordinacao_chave_natural",
        "fre_relacoes_subordinacao",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_relacoes_subordinacao_chave_natural",
        "fre_relacoes_subordinacao",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_relacao",
        ],
    )

    op.drop_constraint(
        "uq_fre_transacoes_partes_relac_chave_natural",
        "fre_transacoes_partes_relacionadas",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_transacoes_partes_relac_chave_natural",
        "fre_transacoes_partes_relacionadas",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "parte_relacionada",
            "documento_parte_relacionada",
            "relacao_emissor",
            "data_transacao",
            "montante_envolvido",
            "saldo_existente",
            "montante_interesse_parte_relacionada",
            "posicao_contratual_emissor",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_fre_transacoes_partes_relac_chave_natural", "fre_transacoes_partes_relacionadas", type_="unique")
    op.create_unique_constraint(
        "uq_fre_transacoes_partes_relac_chave_natural",
        "fre_transacoes_partes_relacionadas",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "parte_relacionada",
            "relacao_emissor",
            "data_transacao",
        ],
    )

    op.drop_constraint("uq_fre_relacoes_subordinacao_chave_natural", "fre_relacoes_subordinacao", type_="unique")
    op.create_unique_constraint(
        "uq_fre_relacoes_subordinacao_chave_natural",
        "fre_relacoes_subordinacao",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_relacao",
        ],
    )

    op.drop_constraint("uq_fre_relacoes_familiares_chave_natural", "fre_relacoes_familiares", type_="unique")
    op.create_unique_constraint(
        "uq_fre_relacoes_familiares_chave_natural",
        "fre_relacoes_familiares",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_parentesco",
        ],
    )

    op.drop_constraint("uq_fre_membros_comites_chave_natural", "fre_membros_comites", type_="unique")
    op.create_unique_constraint(
        "uq_fre_membros_comites_chave_natural",
        "fre_membros_comites",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "tipo_comite",
        ],
    )

    op.drop_constraint("uq_fre_admin_memb_cons_fisc_chave_natural", "fre_administradores_membros_conselho_fiscal", type_="unique")
    op.create_unique_constraint(
        "uq_fre_admin_memb_cons_fisc_chave_natural",
        "fre_administradores_membros_conselho_fiscal",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "orgao_administracao",
        ],
    )

    op.drop_constraint(
        "uq_fre_posicoes_acionarias_classes_acoes_chave_natural",
        "fre_posicoes_acionarias_classes_acoes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_fre_posicoes_acionarias_classes_acoes_chave_natural",
        "fre_posicoes_acionarias_classes_acoes",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_acionista",
            "tipo_classe_acao_preferencial",
        ],
    )

    op.drop_constraint("uq_fca_valores_mobiliarios_chave_natural", "fca_valores_mobiliarios", type_="unique")
    op.create_unique_constraint(
        "uq_fca_valores_mobiliarios_chave_natural",
        "fca_valores_mobiliarios",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "tipo_valor_mobiliario",
            "codigo_negociacao",
            "mercado",
        ],
    )

    op.drop_constraint("uq_fca_auditores_chave_natural", "fca_auditores", type_="unique")
    op.create_unique_constraint(
        "uq_fca_auditores_chave_natural",
        "fca_auditores",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_cnpj_auditor",
            "codigo_cvm_auditor",
        ],
    )

    op.drop_constraint("uq_fca_dri_chave_natural", "fca_dri", type_="unique")
    op.create_unique_constraint(
        "uq_fca_dri_chave_natural",
        "fca_dri",
        [
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_responsavel",
            "tipo_responsavel",
            "data_inicio_atuacao",
        ],
    )
