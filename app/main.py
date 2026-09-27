from pathlib import Path
from typing import List

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from sqlmodel import Session

from app.config import settings

from app.db.crud import (
    create_analysis,
    get_analysis_by_id,
    get_recent_analyses,
)
from app.db.database import (
    get_session,
)
from app.db.models import (
    Analysis,
)

from app.schemas import (
    AnalysisHistoryResponse,
    JobMatchRequest,
    JobMatchResponse,
)

from app.services.matcher_pipeline import (
    MatcherAnalysisError,
    MatcherUnavailableError,
    NoJobRequirementsError,
    analyze_resume_v2,
)

from app.services.resume_parser import (
    extract_resume_text,
)


# =========================================================
# FastAPI application
# =========================================================

app = FastAPI(
    title=(
        "AI Resume Job Matcher API"
    ),
    description=(
        "Evidence-grounded AI service for "
        "comparing resumes against job "
        "descriptions."
    ),
    version=(
        settings.APP_VERSION
    ),
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        settings.CORS_ORIGINS
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Helpers
# =========================================================

def validate_text_input(
    value: str,
    field_name: str,
) -> str:
    """
    Validate required user-provided text.
    """

    cleaned_value = (
        value.strip()
        if value
        else ""
    )

    if not cleaned_value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} "
                "cannot be empty."
            ),
        )

    return cleaned_value


def run_resume_analysis(
    resume_text: str,
    job_description: str,
):
    """
    Run the AI matching pipeline and convert
    expected service errors into HTTP errors.
    """

    try:
        return analyze_resume_v2(
            resume_text=resume_text,
            job_description=(
                job_description
            ),
        )

    except NoJobRequirementsError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except MatcherUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except MatcherAnalysisError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error


def convert_analysis_to_response(
    analysis: Analysis,
) -> JobMatchResponse:
    """
    Convert a database Analysis record into
    the public API response format.
    """

    return JobMatchResponse(
        analysis_id=analysis.id,
        match_score=(
            analysis.match_score
        ),
        score_breakdown=(
            analysis.score_breakdown
        ),
        requirement_matches=(
            analysis.requirement_matches
        ),
        matched_requirements=(
            analysis.matched_requirements
        ),
        partial_requirements=(
            analysis.partial_requirements
        ),
        missing_requirements=(
            analysis.missing_requirements
        ),
        suggestions=(
            analysis.suggestions
        ),
        observability=(
            analysis.observability
        ),
    )


def convert_analysis_to_history(
    analysis: Analysis,
) -> AnalysisHistoryResponse:
    """
    Convert a database Analysis record into
    the history API response format.
    """

    return AnalysisHistoryResponse(
        analysis_id=analysis.id,
        resume_text=(
            analysis.resume_text
        ),
        job_description=(
            analysis.job_description
        ),
        match_score=(
            analysis.match_score
        ),
        score_breakdown=(
            analysis.score_breakdown
        ),
        requirement_matches=(
            analysis.requirement_matches
        ),
        matched_requirements=(
            analysis.matched_requirements
        ),
        partial_requirements=(
            analysis.partial_requirements
        ),
        missing_requirements=(
            analysis.missing_requirements
        ),
        suggestions=(
            analysis.suggestions
        ),
        input_type=(
            analysis.input_type
        ),
        resume_filename=(
            analysis.resume_filename
        ),
        resume_file_type=(
            analysis.resume_file_type
        ),
        created_at=(
            analysis.created_at
        ),
        observability=(
            analysis.observability
        ),
    )


# =========================================================
# System endpoints
# =========================================================

@app.get(
    "/",
    tags=["System"],
)
def root():
    return {
        "name": (
            settings.APP_NAME
        ),
        "version": (
            settings.APP_VERSION
        ),
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get(
    "/health",
    tags=["System"],
)
def health_check():
    return {
        "status": "healthy",
        "version": (
            settings.APP_VERSION
        ),
        "environment": (
            settings.ENVIRONMENT
        ),
    }


# =========================================================
# Text analysis
# =========================================================

@app.post(
    "/analyze",
    response_model=JobMatchResponse,
    tags=["Analysis"],
)
def analyze_text_resume(
    request: JobMatchRequest,
    session: Session = Depends(
        get_session
    ),
):
    resume_text = validate_text_input(
        request.resume_text,
        "Resume text",
    )

    job_description = (
        validate_text_input(
            request.job_description,
            "Job description",
        )
    )

    result = run_resume_analysis(
        resume_text=resume_text,
        job_description=(
            job_description
        ),
    )

    saved_analysis = create_analysis(
        session=session,
        resume_text=resume_text,
        job_description=(
            job_description
        ),
        analysis_result=(
            result.model_dump(
                mode="json"
            )
        ),
        input_type="text",
        resume_filename=None,
        resume_file_type=None,
    )

    return (
        convert_analysis_to_response(
            saved_analysis
        )
    )


# =========================================================
# File analysis
# =========================================================

@app.post(
    "/analyze-file",
    response_model=JobMatchResponse,
    tags=["Analysis"],
)
async def analyze_resume_file(
    job_description: str = Form(
        ...
    ),
    resume_file: UploadFile = File(
        ...
    ),
    session: Session = Depends(
        get_session
    ),
):
    job_description = (
        validate_text_input(
            job_description,
            "Job description",
        )
    )

    filename = (
        resume_file.filename
        or ""
    )

    if not filename:
        raise HTTPException(
            status_code=400,
            detail=(
                "Resume filename "
                "is missing."
            ),
        )

    file_extension = (
        Path(filename)
        .suffix
        .lower()
    )

    allowed_extensions = {
        ".pdf",
        ".docx",
    }

    if (
        file_extension
        not in allowed_extensions
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Only PDF and DOCX "
                "files are allowed."
            ),
        )

    # Read at most one byte beyond
    # the configured limit.
    file_bytes = await (
        resume_file.read(
            settings.MAX_UPLOAD_SIZE_BYTES
            + 1
        )
    )

    if (
        len(file_bytes)
        > settings.MAX_UPLOAD_SIZE_BYTES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Resume file exceeds "
                f"the maximum size of "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded resume "
                "is empty."
            ),
        )

    try:
        resume_text = (
            extract_resume_text(
                file_bytes=file_bytes,
                filename=filename,
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    resume_text = validate_text_input(
        resume_text,
        "Extracted resume text",
    )

    result = run_resume_analysis(
        resume_text=resume_text,
        job_description=(
            job_description
        ),
    )

    saved_analysis = create_analysis(
        session=session,
        resume_text=resume_text,
        job_description=(
            job_description
        ),
        analysis_result=(
            result.model_dump(
                mode="json"
            )
        ),
        input_type="file",
        resume_filename=filename,
        resume_file_type=(
            file_extension.lstrip(
                "."
            )
        ),
    )

    return (
        convert_analysis_to_response(
            saved_analysis
        )
    )


# =========================================================
# Analysis history
# =========================================================

@app.get(
    "/analyses",
    response_model=List[
        AnalysisHistoryResponse
    ],
    tags=["History"],
)
def list_analyses(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    session: Session = Depends(
        get_session
    ),
):
    analyses = (
        get_recent_analyses(
            session=session,
            limit=limit,
        )
    )

    return [
        convert_analysis_to_history(
            analysis
        )
        for analysis in analyses
    ]


@app.get(
    "/analyses/{analysis_id}",
    response_model=(
        AnalysisHistoryResponse
    ),
    tags=["History"],
)
def get_analysis(
    analysis_id: int,
    session: Session = Depends(
        get_session
    ),
):
    analysis = (
        get_analysis_by_id(
            session=session,
            analysis_id=(
                analysis_id
            ),
        )
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analysis not found."
            ),
        )

    return (
        convert_analysis_to_history(
            analysis
        )
    )