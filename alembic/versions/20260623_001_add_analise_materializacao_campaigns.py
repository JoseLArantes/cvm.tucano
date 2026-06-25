"""add_analise_materializacao_campaigns

Revision ID: 20260623_001
Revises: 20260622_001
Create Date: 2026-06-23 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260623_001"
down_revision: str | None = "20260622_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analise_materializacao_campanhas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_execucao_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("pending_items", sa.Integer(), nullable=False),
        sa.Column("running_items", sa.Integer(), nullable=False),
        sa.Column("success_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("skipped_items", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_execucao_id"], ["execucoes_sincronizacao.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_materializacao_campanhas_status",
        "analise_materializacao_campanhas",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_analise_materializacao_campanhas_source_execucao_id",
        "analise_materializacao_campanhas",
        ["source_execucao_id"],
        unique=False,
    )

    op.add_column("analise_materializacao_execucoes", sa.Column("campanha_id", sa.Uuid(), nullable=True))
    op.add_column("analise_materializacao_execucoes", sa.Column("campanha_item_id", sa.Uuid(), nullable=True))
    op.add_column("analise_materializacao_execucoes", sa.Column("queue_name", sa.String(length=64), nullable=True))
    op.add_column("analise_materializacao_execucoes", sa.Column("position_in_chunk", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_campanha_id"),
        "analise_materializacao_execucoes",
        ["campanha_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analise_materializacao_execucoes_campanha_item_id"),
        "analise_materializacao_execucoes",
        ["campanha_item_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_analise_materializacao_execucoes_campanha_id",
        "analise_materializacao_execucoes",
        "analise_materializacao_campanhas",
        ["campanha_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "analise_materializacao_campanha_itens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campanha_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_cvm", sa.Integer(), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), nullable=True),
        sa.Column("escopo", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("materializacao_execucao_id", sa.Uuid(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campanha_id"], ["analise_materializacao_campanhas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["companhia_id"], ["companhias.id"]),
        sa.ForeignKeyConstraint(
            ["materializacao_execucao_id"],
            ["analise_materializacao_execucoes.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analise_materializacao_campanha_itens_lookup",
        "analise_materializacao_campanha_itens",
        ["codigo_cvm", "escopo", "status"],
        unique=False,
    )
    op.create_index(
        "ix_analise_materializacao_campanha_itens_campanha_status",
        "analise_materializacao_campanha_itens",
        ["campanha_id", "status"],
        unique=False,
    )
    for column in ("campanha_id", "codigo_cvm", "companhia_id", "escopo", "status", "materializacao_execucao_id"):
        op.create_index(
            op.f(f"ix_analise_materializacao_campanha_itens_{column}"),
            "analise_materializacao_campanha_itens",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("materializacao_execucao_id", "status", "escopo", "companhia_id", "codigo_cvm", "campanha_id"):
        op.drop_index(
            op.f(f"ix_analise_materializacao_campanha_itens_{column}"),
            table_name="analise_materializacao_campanha_itens",
        )
    op.drop_index(
        "ix_analise_materializacao_campanha_itens_campanha_status",
        table_name="analise_materializacao_campanha_itens",
    )
    op.drop_index("ix_analise_materializacao_campanha_itens_lookup", table_name="analise_materializacao_campanha_itens")
    op.drop_table("analise_materializacao_campanha_itens")

    op.drop_constraint("fk_analise_materializacao_execucoes_campanha_id", "analise_materializacao_execucoes", type_="foreignkey")
    op.drop_index(op.f("ix_analise_materializacao_execucoes_campanha_item_id"), table_name="analise_materializacao_execucoes")
    op.drop_index(op.f("ix_analise_materializacao_execucoes_campanha_id"), table_name="analise_materializacao_execucoes")
    op.drop_column("analise_materializacao_execucoes", "position_in_chunk")
    op.drop_column("analise_materializacao_execucoes", "queue_name")
    op.drop_column("analise_materializacao_execucoes", "campanha_item_id")
    op.drop_column("analise_materializacao_execucoes", "campanha_id")

    op.drop_index(
        "ix_analise_materializacao_campanhas_source_execucao_id",
        table_name="analise_materializacao_campanhas",
    )
    op.drop_index("ix_analise_materializacao_campanhas_status", table_name="analise_materializacao_campanhas")
    op.drop_table("analise_materializacao_campanhas")
