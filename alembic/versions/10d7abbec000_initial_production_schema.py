"""initial production schema

Revision ID: 10d7abbec000
Revises: 
Create Date: 2026-09-27 23:49:03.881671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10d7abbec000'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "resume_text",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "job_description",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "match_score",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "score_breakdown",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "requirement_matches",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "matched_requirements",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "partial_requirements",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "missing_requirements",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "suggestions",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "input_type",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "resume_filename",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "resume_file_type",
            sa.String(length=20),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "observability",
            sa.JSON(),
            nullable=True,
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),
    )


def downgrade() -> None:
    op.drop_table(
        "analysis"
    )