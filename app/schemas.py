from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class JobMatchRequest(BaseModel):
    resume_text: str
    job_description: str


class JobMatchResponse(BaseModel):
    analysis_id: Optional[int] = None
    match_score: float
    matched_requirements: List[str]
    missing_requirements: List[str]
    suggestions: List[str]


class AnalysisHistoryResponse(BaseModel):
    analysis_id: int

    match_score: float
    matched_requirements: List[str]
    missing_requirements: List[str]
    suggestions: List[str]

    resume_text: str
    job_description: str

    input_type: str
    resume_filename: Optional[str]
    resume_file_type: Optional[str]

    created_at: datetime