from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    resume_text: str = Field(
        sa_column=Column(Text)
    )

    job_description: str = Field(
        sa_column=Column(Text)
    )

    match_score: float

    score_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    requirement_matches: List[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    matched_requirements: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    partial_requirements: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    missing_requirements: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    suggestions: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    input_type: str = Field(
        default="text",
        max_length=20,
    )

    resume_filename: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    resume_file_type: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    observability: Optional[Dict] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )