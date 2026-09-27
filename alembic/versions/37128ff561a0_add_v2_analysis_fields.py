"""add v2 analysis fields

Revision ID: 37128ff561a0
Revises: 544bdbddd5cf
Create Date: 2026-09-26 12:26:13.951349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37128ff561a0'
down_revision: Union[str, Sequence[str], None] = '544bdbddd5cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column(
        "analysis",
        sa.Column(
            "score_breakdown",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'{}'::json"
            ),
        ),
    )

    op.add_column(
        "analysis",
        sa.Column(
            "requirement_matches",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'[]'::json"
            ),
        ),
    )

    op.add_column(
        "analysis",
        sa.Column(
            "partial_requirements",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'[]'::json"
            ),
        ),
    )

    op.alter_column(
        "analysis",
        "score_breakdown",
        server_default=None,
    )

    op.alter_column(
        "analysis",
        "requirement_matches",
        server_default=None,
    )

    op.alter_column(
        "analysis",
        "partial_requirements",
        server_default=None,
    )


def downgrade() -> None:

    op.drop_column(
        "analysis",
        "partial_requirements",
    )

    op.drop_column(
        "analysis",
        "requirement_matches",
    )

    op.drop_column(
        "analysis",
        "score_breakdown",
    )
