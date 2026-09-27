from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.services.observability import (
    AnalysisObservability,
)


RequirementImportance = Literal[
    "must_have",
    "important",
    "preferred",
]

RequirementCategory = Literal[
    "experience",
    "education",
    "license",
    "certification",
    "skill",
    "tool",
    "domain_knowledge",
    "language",
    "responsibility",
    "other",
]

MatchStatus = Literal[
    "matched",
    "partial",
    "missing",
]


class ExtractedRequirement(BaseModel):
    requirement: str

    category: RequirementCategory

    importance: RequirementImportance

    source_text: str = Field(
        description=(
            "Short text from the job description that supports "
            "this requirement."
        )
    )


class JobRequirement(ExtractedRequirement):
    requirement_id: str


class JobRequirementExtraction(BaseModel):
    job_title: Optional[str] = None

    requirements: List[ExtractedRequirement]

class RequirementAssessment(BaseModel):
    requirement_id: str

    status: MatchStatus

    evidence: List[str] = Field(
        default_factory=list,
        description=(
            "Verbatim text snippets copied from the resume that "
            "support this assessment."
        ),
    )

    rationale: str = Field(
        description=(
            "Short explanation of why the requirement is "
            "matched, partial, or missing."
        )
    )


class RequirementAssessmentBatch(BaseModel):
    assessments: List[RequirementAssessment]

class RequirementMatch(BaseModel):
    requirement_id: str

    requirement: str

    category: RequirementCategory

    importance: RequirementImportance

    status: MatchStatus

    evidence: List[str] = Field(
        default_factory=list,
        description=(
            "Evidence from the resume supporting the match. "
            "Must be empty when no supporting evidence exists."
        ),
    )

    rationale: str = Field(
        description=(
            "Short explanation of why this requirement is "
            "matched, partially matched, or missing."
        )
    )


class RequirementMatchingResult(BaseModel):
    matches: List[RequirementMatch]

    suggestions: List[str] = Field(
        default_factory=list
    )


class FinalMatchResult(BaseModel):
    match_score: float = Field(
        ge=0,
        le=100,
    )

    score_breakdown: dict[str, float]

    requirement_matches: List[RequirementMatch]

    matched_requirements: List[str]

    partial_requirements: List[str]

    missing_requirements: List[str]

    suggestions: List[str]

    observability: Optional[
        AnalysisObservability
    ] = None


def assign_requirement_ids(
    extraction: JobRequirementExtraction,
) -> List[JobRequirement]:

    requirements = []

    for index, requirement in enumerate(
        extraction.requirements,
        start=1,
    ):
        requirements.append(
            JobRequirement(
                requirement_id=f"R{index:03d}",
                requirement=requirement.requirement,
                category=requirement.category,
                importance=requirement.importance,
                source_text=requirement.source_text,
            )
        )

    return requirements

class SuggestionBatch(BaseModel):
    suggestions: List[str] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Specific, evidence-based recommendations derived "
            "from partial or missing job requirements."
        ),
    )