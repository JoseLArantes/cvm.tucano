"""merge fca dri and financeiro heads

Revision ID: 8e9f0a1b2c3d
Revises: 1c2d3e4f5a6b, 7b5c9d2e4f11
Create Date: 2026-06-12 22:48:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "8e9f0a1b2c3d"
down_revision: tuple[str, str] = ("1c2d3e4f5a6b", "7b5c9d2e4f11")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
