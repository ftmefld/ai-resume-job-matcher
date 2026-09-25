from typing import Dict

from app.services.llm_service import analyze_resume_with_llm


def analyze_resume_match(resume_text: str, job_description: str) -> Dict:
    return analyze_resume_with_llm(
        resume_text=resume_text,
        job_description=job_description
    )