"""track manual sector taxonomy imports

Revision ID: 20261110_001
Revises: 20261109_001
Create Date: 2026-11-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261110_001"
down_revision: str | None = "20261109_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "setor_taxonomia_importacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomia", sa.String(length=64), nullable=False),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("caminho_artefato", sa.String(length=1000), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("data_atualizacao_fonte", sa.Date(), nullable=True),
        sa.Column("importado_por", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("versao_taxonomia", sa.Integer(), nullable=True),
        sa.Column("resumo", sa.JSON(), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("importada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["taxonomia"], ["setor_taxonomias.codigo"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_setor_taxonomia_importacoes_taxonomia",
        "setor_taxonomia_importacoes",
        ["taxonomia"],
    )
    op.create_index(
        "ix_setor_taxonomia_importacoes_status",
        "setor_taxonomia_importacoes",
        ["status"],
    )
    op.create_index(
        "ix_setor_taxonomia_importacoes_taxonomia_importada",
        "setor_taxonomia_importacoes",
        ["taxonomia", "importada_em"],
    )
    op.create_index(
        "ix_setor_taxonomia_importacoes_checksum",
        "setor_taxonomia_importacoes",
        ["checksum_sha256"],
    )
    op.execute(
        sa.text(
            "UPDATE setor_taxonomias SET fonte = :fonte "
            "WHERE codigo = 'b3' AND versao_atual IS NULL"
        ).bindparams(fonte="ClassifSetorial.xlsx (importação manual pendente)")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE setor_taxonomias SET fonte = :fonte "
            "WHERE codigo = 'b3' AND versao_atual IS NULL "
            "AND fonte = 'ClassifSetorial.xlsx (importação manual pendente)'"
        ).bindparams(fonte="Fonte oficial autorizada pendente")
    )
    op.drop_index("ix_setor_taxonomia_importacoes_checksum", table_name="setor_taxonomia_importacoes")
    op.drop_index("ix_setor_taxonomia_importacoes_taxonomia_importada", table_name="setor_taxonomia_importacoes")
    op.drop_index("ix_setor_taxonomia_importacoes_status", table_name="setor_taxonomia_importacoes")
    op.drop_index("ix_setor_taxonomia_importacoes_taxonomia", table_name="setor_taxonomia_importacoes")
    op.drop_table("setor_taxonomia_importacoes")
