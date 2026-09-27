from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.services.matching_models import (
    MatchStatus,
    RequirementCategory,
    RequirementImportance,
)

from app.services.observability import (
    AnalysisObservability,
)


class JobMatchRequest(BaseModel):
    resume_text: str
    job_description: str


class RequirementMatchResponse(BaseModel):
    requirement_id: str
    requirement: str
    category: RequirementCategory
    importance: RequirementImportance
    status: MatchStatus
    evidence: List[str]
    rationale: str


class JobMatchResponse(BaseModel):
    analysis_id: Optional[int] = None

    match_score: float

    score_breakdown: Dict[str, float]

    requirement_matches: List[
        RequirementMatchResponse
    ]

    matched_requirements: List[str]
    partial_requirements: List[str]
    missing_requirements: List[str]

    suggestions: List[str]
    observability: Optional[AnalysisObservability] = None


class AnalysisHistoryResponse(BaseModel):
    analysis_id: int

    match_score: float

    score_breakdown: Dict[str, float]

    requirement_matches: List[
        RequirementMatchResponse
    ]

    matched_requirements: List[str]
    partial_requirements: List[str]
    missing_requirements: List[str]

    suggestions: List[str]

    resume_text: str
    job_description: str

    input_type: str
    resume_filename: Optional[str]
    resume_file_type: Optional[str]

    observability: Optional[
        AnalysisObservability
    ] = None

    created_at: datetime