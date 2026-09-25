"""add resume file metadata

Revision ID: c7affb1679dc
Revises: 
Create Date: 2026-09-25 13:29:31.750246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7affb1679dc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis",
        sa.Column(
            "input_type",
            sa.String(length=20),
            nullable=False,
            server_default="text",
        ),
    )

    op.add_column(
        "analysis",
        sa.Column(
            "resume_filename",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis",
        sa.Column(
            "resume_file_type",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.alter_column(
        "analysis",
        "input_type",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "analysis",
        "resume_file_type",
    )

    op.drop_column(
        "analysis",
        "resume_filename",
    )

    op.drop_column(
        "analysis",
        "input_type",
    )