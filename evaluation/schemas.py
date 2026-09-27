from typing import List

from pydantic import BaseModel

from app.services.matching_models import (
    MatchStatus,
    RequirementCategory,
    RequirementImportance,
)


class GoldRequirement(BaseModel):
    requirement: str
    category: RequirementCategory
    importance: RequirementImportance
    expected_status: MatchStatus
    source_text: str


class EvaluationCase(BaseModel):
    case_id: str
    domain: str
    job_description: str
    resume_text: str
    gold_requirements: List[GoldRequirement]