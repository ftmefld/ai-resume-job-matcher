from typing import Dict, List, Optional

from sqlmodel import Session, select

from app.db.models import Analysis


def create_analysis(
    session: Session,
    resume_text: str,
    job_description: str,
    analysis_result: Dict,
    input_type: str = "text",
    resume_filename: Optional[str] = None,
    resume_file_type: Optional[str] = None,
) -> Analysis:

    analysis = Analysis(
        resume_text=resume_text,
        job_description=job_description,

        match_score=float(
            analysis_result.get(
                "match_score",
                0,
            )
        ),

        score_breakdown=analysis_result.get(
            "score_breakdown",
            {},
        ),

        requirement_matches=analysis_result.get(
            "requirement_matches",
            [],
        ),

        matched_requirements=analysis_result.get(
            "matched_requirements",
            [],
        ),

        partial_requirements=analysis_result.get(
            "partial_requirements",
            [],
        ),

        missing_requirements=analysis_result.get(
            "missing_requirements",
            [],
        ),

        suggestions=analysis_result.get(
            "suggestions",
            [],
        ),

        observability=analysis_result.get(
            "observability",
            None
        ),

        input_type=input_type,
        resume_filename=resume_filename,
        resume_file_type=resume_file_type,
    )

    session.add(analysis)
    session.commit()
    session.refresh(analysis)

    return analysis


def get_analysis_by_id(
    session: Session,
    analysis_id: int,
) -> Optional[Analysis]:

    return session.get(
        Analysis,
        analysis_id,
    )


def get_recent_analyses(
    session: Session,
    limit: int = 10,
) -> List[Analysis]:

    statement = (
        select(Analysis)
        .order_by(
            Analysis.created_at.desc()
        )
        .limit(limit)
    )

    results = session.exec(
        statement
    )

    return list(
        results.all()
    )