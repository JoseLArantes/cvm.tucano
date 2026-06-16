"""widen FRE numeric columns

Revision ID: 3b4c5d6e7f8a
Revises: 1f2a3b4c5d6e
Create Date: 2026-06-13 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b4c5d6e7f8a"
down_revision: str | None = "1f2a3b4c5d6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FRE_NUMERIC_COLUMNS: tuple[tuple[str, str], ...] = (
    ("fre_acoes_entregues", "preco_medio_ponderado_aquisicao"),
    ("fre_acoes_entregues", "preco_medio_ponderado_mercado"),
    ("fre_acoes_entregues", "valor_diferenca_aquisicao_mercado"),
    ("fre_administradores_membros_conselho_fiscal", "percentual_participacao_reunioes"),
    ("fre_auditores", "remuneracao_auditor"),
    ("fre_capital_social", "valor_capital"),
    ("fre_capital_social_aumento_classes_acoes", "quantidade_acoes"),
    ("fre_capital_social_aumentos", "valor_aumento"),
    ("fre_capital_social_aumentos", "quantidade_acoes_ordinarias"),
    ("fre_capital_social_aumentos", "quantidade_acoes_preferenciais"),
    ("fre_capital_social_aumentos", "quantidade_total_acoes"),
    ("fre_capital_social_desdobramento_classes_acoes", "quantidade_acoes"),
    ("fre_capital_social_desdobramentos", "proporcao_acoes_novas"),
    ("fre_capital_social_desdobramentos", "proporcao_acoes_antigas"),
    ("fre_capital_social_desdobramentos", "quantidade_acoes_ordinarias"),
    ("fre_capital_social_desdobramentos", "quantidade_acoes_preferenciais"),
    ("fre_capital_social_desdobramentos", "quantidade_total_acoes"),
    ("fre_capital_social_reducao_classes_acoes", "quantidade_acoes"),
    ("fre_capital_social_reducoes", "valor_reducao"),
    ("fre_capital_social_reducoes", "quantidade_acoes_ordinarias"),
    ("fre_capital_social_reducoes", "quantidade_acoes_preferenciais"),
    ("fre_capital_social_reducoes", "quantidade_total_acoes"),
    ("fre_membros_comites", "percentual_participacao_reunioes"),
    ("fre_participacoes_sociedades", "valor_mercado"),
    ("fre_participacoes_sociedades", "valor_contabil"),
    ("fre_plano_recompra_classes_acoes", "quantidade_acoes_adquiridas"),
    ("fre_planos_recompra", "quantidade_total_ordinarias_adquiridas"),
    ("fre_planos_recompra", "quantidade_total_preferenciais_adquiridas"),
    ("fre_remuneracoes_acoes", "preco_medio_ponderado_opcoes_em_aberto"),
    ("fre_remuneracoes_acoes", "preco_medio_ponderado_opcoes_exercidas"),
    ("fre_remuneracoes_acoes", "preco_medio_ponderado_opcoes_perdidas"),
    ("fre_remuneracoes_maximas_minimas_medias", "valor_maior_remuneracao"),
    ("fre_remuneracoes_maximas_minimas_medias", "valor_medio_remuneracao"),
    ("fre_remuneracoes_maximas_minimas_medias", "valor_menor_remuneracao"),
    ("fre_remuneracoes_totais_orgaos", "total_remuneracao"),
    ("fre_remuneracoes_totais_orgaos", "total_remuneracao_orgao"),
    ("fre_remuneracoes_totais_orgaos", "salario"),
    ("fre_remuneracoes_totais_orgaos", "beneficios_diretos_indiretos"),
    ("fre_remuneracoes_totais_orgaos", "participacoes_comites"),
    ("fre_remuneracoes_totais_orgaos", "outros_valores_fixos"),
    ("fre_remuneracoes_totais_orgaos", "bonus"),
    ("fre_remuneracoes_totais_orgaos", "participacao_resultados"),
    ("fre_remuneracoes_totais_orgaos", "participacao_reunioes"),
    ("fre_remuneracoes_totais_orgaos", "outros_valores_variaveis"),
    ("fre_remuneracoes_totais_orgaos", "comissoes"),
    ("fre_remuneracoes_totais_orgaos", "pos_emprego"),
    ("fre_remuneracoes_totais_orgaos", "cessacao_cargo"),
    ("fre_remuneracoes_totais_orgaos", "baseada_acoes"),
    ("fre_remuneracoes_variaveis", "bonus_valor_minimo"),
    ("fre_remuneracoes_variaveis", "bonus_valor_maximo"),
    ("fre_remuneracoes_variaveis", "bonus_valor_metas_atingidas"),
    ("fre_remuneracoes_variaveis", "bonus_valor_efetivo"),
    ("fre_remuneracoes_variaveis", "participacao_valor_minimo"),
    ("fre_remuneracoes_variaveis", "participacao_valor_maximo"),
    ("fre_remuneracoes_variaveis", "participacao_valor_metas_atingidas"),
    ("fre_remuneracoes_variaveis", "participacao_valor_efetivo"),
    ("fre_titulares_valores_mobiliarios", "quantidade_valores_mobiliarios"),
    ("fre_titulares_valores_mobiliarios", "percentual_classe"),
    ("fre_transacoes_partes_relacionadas", "montante_envolvido"),
    ("fre_transacoes_partes_relacionadas", "saldo_existente"),
    ("fre_transacoes_partes_relacionadas", "montante_interesse_parte_relacionada"),
    ("fre_transacoes_partes_relacionadas", "taxa_juros"),
    ("fre_valores_mobiliarios_tesouraria_movimentacoes", "quantidade_movimentada"),
    ("fre_valores_mobiliarios_tesouraria_ultimos_exercicios", "quantidade_acoes_tesouraria"),
    ("fre_volumes_valores_mobiliarios", "volume_negociacao"),
)


def upgrade() -> None:
    for table_name, column_name in FRE_NUMERIC_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.Numeric(precision=30, scale=10),
            type_=sa.Numeric(precision=38, scale=10),
            existing_nullable=True,
        )


def downgrade() -> None:
    for table_name, column_name in reversed(FRE_NUMERIC_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.Numeric(precision=38, scale=10),
            type_=sa.Numeric(precision=30, scale=10),
            existing_nullable=True,
        )
