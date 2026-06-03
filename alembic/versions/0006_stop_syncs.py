"""stop syncs

Revision ID: 0006_stop_syncs
Revises: 0005_grupo_demo_fin
Create Date: 2026-06-03 00:00:02.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_stop_syncs"
down_revision: str | None = "0005_grupo_demo_fin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("execucoes_sincronizacao", sa.Column("id_tarefa", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_execucoes_sincronizacao_id_tarefa"), "execucoes_sincronizacao", ["id_tarefa"])


def downgrade() -> None:
    op.drop_index(op.f("ix_execucoes_sincronizacao_id_tarefa"), table_name="execucoes_sincronizacao")
    op.drop_column("execucoes_sincronizacao", "id_tarefa")
