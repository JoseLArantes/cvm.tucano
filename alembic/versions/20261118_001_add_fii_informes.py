"""Add normalized storage for the annual CVM FII monthly reports."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261118_001"
down_revision: str | None = "20261111_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fii_informes_gerais",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(255)),
        sa.Column("codigo_isin", sa.String(32)),
        sa.Column("segmento_atuacao", sa.String(255)),
        sa.Column("publico_alvo", sa.String(100)),
        sa.Column("mandato", sa.String(255)),
        sa.Column("tipo_gestao", sa.String(100)),
        sa.Column("prazo_duracao", sa.String(100)),
        sa.Column("data_funcionamento", sa.Date()),
        sa.Column("data_prazo_duracao", sa.Date()),
        sa.Column("quantidade_cotas_emitidas", sa.Numeric(50, 30)),
        sa.Column("fundo_exclusivo", sa.Boolean()),
        sa.Column("cotistas_vinculo_familiar", sa.Boolean()),
        sa.Column("mercado_negociacao_bolsa", sa.Boolean()),
        sa.Column("nome_administrador", sa.String(255)),
        sa.Column("cnpj_administrador", sa.String(18)),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("linha_origem", sa.Integer(), nullable=False),
        sa.Column("hash_origem", sa.String(64), nullable=False),
        sa.Column("arquivo_origem", sa.String(255), nullable=False),
        sa.Column("ano_origem", sa.Integer(), nullable=False),
        sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=False),
        sa.Column("consta_no_snapshot_atual", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("alterado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj", "tipo", "data_referencia", "versao", name="uq_fii_informes_gerais_chave"),
    )
    for name, column in (
        ("ix_fii_informes_gerais_cnpj", "cnpj"), ("ix_fii_informes_gerais_tipo", "tipo"),
        ("ix_fii_informes_gerais_data_referencia", "data_referencia"), ("ix_fii_informes_gerais_versao", "versao"),
        ("ix_fii_informes_gerais_nome", "nome"), ("ix_fii_informes_gerais_codigo_isin", "codigo_isin"),
        ("ix_fii_informes_gerais_segmento_atuacao", "segmento_atuacao"),
        ("ix_fii_informes_gerais_mercado_negociacao_bolsa", "mercado_negociacao_bolsa"),
        ("ix_fii_informes_gerais_cnpj_administrador", "cnpj_administrador"),
        ("ix_fii_informes_gerais_ano_origem", "ano_origem"),
        ("ix_fii_informes_gerais_execucao_sincronizacao_id", "execucao_sincronizacao_id"),
    ):
        op.create_index(name, "fii_informes_gerais", [column])
    op.create_index("ix_fii_informes_gerais_catalogo", "fii_informes_gerais", ["nome", "cnpj", "tipo"])
    op.create_index("ix_fii_informes_gerais_atual", "fii_informes_gerais", ["consta_no_snapshot_atual", "data_referencia"])

    for table_name, metric_columns, unique_name in (
        (
            "fii_informes_complementos",
            [
                sa.Column("valor_ativo", sa.Numeric(50, 30)), sa.Column("patrimonio_liquido", sa.Numeric(50, 30)),
                sa.Column("cotas_emitidas", sa.Numeric(50, 30)), sa.Column("valor_patrimonial_cotas", sa.Numeric(50, 30)),
                sa.Column("total_numero_cotistas", sa.Integer()),
                sa.Column("percentual_rentabilidade_efetiva_mes", sa.Numeric(50, 30)),
                sa.Column("percentual_rentabilidade_patrimonial_mes", sa.Numeric(50, 30)),
                sa.Column("percentual_dividend_yield_mes", sa.Numeric(50, 30)),
                sa.Column("percentual_amortizacao_cotas_mes", sa.Numeric(50, 30)),
            ],
            "uq_fii_complementos_variante",
        ),
        (
            "fii_informes_ativos_passivos",
            [
                sa.Column("total_necessidades_liquidez", sa.Numeric(50, 30)),
                sa.Column("disponibilidades", sa.Numeric(50, 30)), sa.Column("total_investido", sa.Numeric(50, 30)),
                sa.Column("direitos_bens_imoveis", sa.Numeric(50, 30)), sa.Column("valores_receber", sa.Numeric(50, 30)),
                sa.Column("total_passivo", sa.Numeric(50, 30)),
            ],
            "uq_fii_ativos_passivos_variante",
        ),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("cnpj", sa.String(14), nullable=False), sa.Column("tipo", sa.String(10)),
            sa.Column("data_referencia", sa.Date(), nullable=False), sa.Column("versao", sa.Integer(), nullable=False),
            *metric_columns,
            sa.Column("status_atribuicao", sa.String(20), nullable=False),
            sa.Column("ocorrencias", sa.Integer(), nullable=False), sa.Column("dados", sa.JSON(), nullable=False),
            sa.Column("linha_origem", sa.Integer(), nullable=False), sa.Column("hash_variante", sa.String(64), nullable=False),
            sa.Column("hash_origem", sa.String(64), nullable=False), sa.Column("arquivo_origem", sa.String(255), nullable=False),
            sa.Column("ano_origem", sa.Integer(), nullable=False), sa.Column("execucao_sincronizacao_id", sa.Uuid(), nullable=False),
            sa.Column("consta_no_snapshot_atual", sa.Boolean(), nullable=False),
            sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["execucao_sincronizacao_id"], ["execucoes_sincronizacao.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("cnpj", "tipo", "data_referencia", "versao", "hash_variante", name=unique_name),
        )
        for column in ("cnpj", "tipo", "data_referencia", "versao", "execucao_sincronizacao_id"):
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])
        index_name = "ix_fii_complementos_fundo" if table_name == "fii_informes_complementos" else "ix_fii_ativos_passivos_fundo"
        op.create_index(index_name, table_name, ["cnpj", "tipo", "data_referencia"])
        if table_name == "fii_informes_complementos":
            op.create_index("ix_fii_informes_complementos_patrimonio_liquido", table_name, ["patrimonio_liquido"])


def downgrade() -> None:
    op.drop_table("fii_informes_ativos_passivos")
    op.drop_table("fii_informes_complementos")
    op.drop_table("fii_informes_gerais")
