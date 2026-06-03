"""ingestion v2 identity

Revision ID: 0008_ingestion_v2_identity
Revises: 0007_ingestion_v2_staging
Create Date: 2026-06-03 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_ingestion_v2_identity"
down_revision: str | None = "0007_ingestion_v2_staging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companhias", sa.Column("tipo_emissor", sa.String(length=32), nullable=True))
    op.add_column("companhias", sa.Column("fonte_identidade_principal", sa.String(length=64), nullable=True))
    op.add_column("companhias", sa.Column("qualidade_identidade", sa.String(length=32), nullable=True))

    op.create_table(
        "companhia_registros_cvm",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=False),
        sa.Column("fonte_cadastro", sa.String(length=64), nullable=False),
        sa.Column("cnpj_companhia", sa.String(length=14), nullable=True),
        sa.Column("codigo_cvm", sa.Integer(), nullable=True),
        sa.Column("denominacao_social", sa.String(length=255), nullable=True),
        sa.Column("denominacao_comercial", sa.String(length=255), nullable=True),
        sa.Column("pais_origem", sa.String(length=100), nullable=True),
        sa.Column("situacao_registro", sa.String(length=255), nullable=True),
        sa.Column("data_registro", sa.Date(), nullable=True),
        sa.Column("data_constituicao", sa.Date(), nullable=True),
        sa.Column("data_cancelamento", sa.Date(), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_situacao", sa.Date(), nullable=True),
        sa.Column("setor_atividade", sa.String(length=255), nullable=True),
        sa.Column("categoria_registro", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_categoria", sa.Date(), nullable=True),
        sa.Column("situacao_emissor", sa.String(length=255), nullable=True),
        sa.Column("data_inicio_situacao_emissor", sa.Date(), nullable=True),
        sa.Column("controle_acionario", sa.String(length=255), nullable=True),
        sa.Column("endereco", sa.JSON(), nullable=True),
        sa.Column("responsavel", sa.JSON(), nullable=True),
        sa.Column("auditor", sa.String(length=255), nullable=True),
        sa.Column("cnpj_auditor", sa.String(length=14), nullable=True),
        sa.Column("source_ingestion_row_id", sa.Uuid(), nullable=True),
        sa.Column("hash_sem_mercado", sa.String(length=64), nullable=False),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["source_ingestion_row_id"], ["ingestion_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companhia_registros_cvm_cnpj_companhia"), "companhia_registros_cvm", ["cnpj_companhia"], unique=False)
    op.create_index(op.f("ix_companhia_registros_cvm_codigo_cvm"), "companhia_registros_cvm", ["codigo_cvm"], unique=False)
    op.create_index(op.f("ix_companhia_registros_cvm_companhia_id"), "companhia_registros_cvm", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_companhia_registros_cvm_fonte_cadastro"), "companhia_registros_cvm", ["fonte_cadastro"], unique=False)
    op.create_index(op.f("ix_companhia_registros_cvm_source_ingestion_row_id"), "companhia_registros_cvm", ["source_ingestion_row_id"], unique=False)

    op.create_table(
        "companhia_mercados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_registro_cvm_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_mercado", sa.String(length=255), nullable=True),
        sa.Column("source_ingestion_row_id", sa.Uuid(), nullable=True),
        sa.Column("arquivo_origem", sa.String(length=255), nullable=False),
        sa.Column("linha_origem", sa.Integer(), nullable=True),
        sa.Column("hash_origem", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_registro_cvm_id"], ["companhia_registros_cvm.id"]),
        sa.ForeignKeyConstraint(["source_ingestion_row_id"], ["ingestion_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companhia_mercados_companhia_registro_cvm_id"), "companhia_mercados", ["companhia_registro_cvm_id"], unique=False)
    op.create_index(op.f("ix_companhia_mercados_source_ingestion_row_id"), "companhia_mercados", ["source_ingestion_row_id"], unique=False)

    op.create_table(
        "companhia_identificadores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("valor", sa.String(length=255), nullable=False),
        sa.Column("valor_normalizado", sa.String(length=255), nullable=False),
        sa.Column("fonte", sa.String(length=64), nullable=False),
        sa.Column("confianca", sa.String(length=16), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_ingestion_row_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(["source_ingestion_row_id"], ["ingestion_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companhia_identificadores_companhia_id"), "companhia_identificadores", ["companhia_id"], unique=False)
    op.create_index(op.f("ix_companhia_identificadores_source_ingestion_row_id"), "companhia_identificadores", ["source_ingestion_row_id"], unique=False)
    op.create_index(op.f("ix_companhia_identificadores_tipo"), "companhia_identificadores", ["tipo"], unique=False)
    op.create_index(op.f("ix_companhia_identificadores_valor_normalizado"), "companhia_identificadores", ["valor_normalizado"], unique=False)
    op.create_index(
        "ix_companhia_identificadores_tipo_valor_normalizado",
        "companhia_identificadores",
        ["tipo", "valor_normalizado"],
        unique=False,
    )

    op.create_table(
        "repair_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("match_payload", sa.JSON(), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repair_rules_rule_type"), "repair_rules", ["rule_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_repair_rules_rule_type"), table_name="repair_rules")
    op.drop_table("repair_rules")

    op.drop_index("ix_companhia_identificadores_tipo_valor_normalizado", table_name="companhia_identificadores")
    op.drop_index(op.f("ix_companhia_identificadores_valor_normalizado"), table_name="companhia_identificadores")
    op.drop_index(op.f("ix_companhia_identificadores_tipo"), table_name="companhia_identificadores")
    op.drop_index(op.f("ix_companhia_identificadores_source_ingestion_row_id"), table_name="companhia_identificadores")
    op.drop_index(op.f("ix_companhia_identificadores_companhia_id"), table_name="companhia_identificadores")
    op.drop_table("companhia_identificadores")

    op.drop_index(op.f("ix_companhia_mercados_source_ingestion_row_id"), table_name="companhia_mercados")
    op.drop_index(op.f("ix_companhia_mercados_companhia_registro_cvm_id"), table_name="companhia_mercados")
    op.drop_table("companhia_mercados")

    op.drop_index(op.f("ix_companhia_registros_cvm_source_ingestion_row_id"), table_name="companhia_registros_cvm")
    op.drop_index(op.f("ix_companhia_registros_cvm_fonte_cadastro"), table_name="companhia_registros_cvm")
    op.drop_index(op.f("ix_companhia_registros_cvm_companhia_id"), table_name="companhia_registros_cvm")
    op.drop_index(op.f("ix_companhia_registros_cvm_codigo_cvm"), table_name="companhia_registros_cvm")
    op.drop_index(op.f("ix_companhia_registros_cvm_cnpj_companhia"), table_name="companhia_registros_cvm")
    op.drop_table("companhia_registros_cvm")

    op.drop_column("companhias", "qualidade_identidade")
    op.drop_column("companhias", "fonte_identidade_principal")
    op.drop_column("companhias", "tipo_emissor")
