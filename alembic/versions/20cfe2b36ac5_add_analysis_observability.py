"""add analysis observability

Revision ID: 20cfe2b36ac5
Revises: 37128ff561a0
Create Date: 2026-09-26 13:03:20.997689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20cfe2b36ac5'
down_revision: Union[str, Sequence[str], None] = '37128ff561a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis",
        sa.Column(
            "observability",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "analysis",
        "observability",
    )