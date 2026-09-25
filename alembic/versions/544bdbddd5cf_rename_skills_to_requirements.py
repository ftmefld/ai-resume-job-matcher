"""rename skills to requirements

Revision ID: 544bdbddd5cf
Revises: c7affb1679dc
Create Date: 2026-09-25 18:39:50.283571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '544bdbddd5cf'
down_revision: Union[str, Sequence[str], None] = 'c7affb1679dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "analysis",
        "matched_skills",
        new_column_name="matched_requirements",
    )

    op.alter_column(
        "analysis",
        "missing_skills",
        new_column_name="missing_requirements",
    )


def downgrade() -> None:
    op.alter_column(
        "analysis",
        "matched_requirements",
        new_column_name="matched_skills",
    )

    op.alter_column(
        "analysis",
        "missing_requirements",
        new_column_name="missing_skills",
    )
