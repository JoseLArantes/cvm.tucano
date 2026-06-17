"""drop ipe protocolo unique constraint

Revision ID: 4c5d6e7f8a9b
Revises: 3b4c5d6e7f8a
Create Date: 2026-06-14 13:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c5d6e7f8a9b"
down_revision: str | None = "3b4c5d6e7f8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_ipe_documentos_protocolo_versao", "ipe_documentos", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_ipe_documentos_protocolo_versao",
        "ipe_documentos",
        ["protocolo_entrega", "versao"],
    )
