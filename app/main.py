from typing import List

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlmodel import Session

from app.db.crud import (
    create_analysis,
    get_analysis_by_id,
    get_recent_analyses,
)
from app.db.database import get_session
from app.db.models import Analysis
from app.schemas import (
    AnalysisHistoryResponse,
    JobMatchRequest,
    JobMatchResponse,
)
from app.services.analyzer import analyze_resume_match
from app.services.llm_service import (
    LLMRequestError,
    LLMUnavailableError,
)
from app.services.resume_parser import extract_resume_text


# Maximum uploaded resume size: 5 MB
MAX_FILE_SIZE = 5 * 1024 * 1024


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="AI Resume Job Matcher",
    description=(
        "An AI-powered API that compares resumes "
        "with job descriptions using Gemini and "
        "stores results in PostgreSQL."
    ),
    version="0.5.0",
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def run_resume_analysis(
    resume_text: str,
    job_description: str,
):
    """
    Runs the Gemini resume analysis and converts
    LLM errors into clean HTTP responses.
    """

    try:
        return analyze_resume_match(
            resume_text=resume_text,
            job_description=job_description,
        )

    except LLMUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI analysis service is temporarily unavailable. "
                "Please try again later."
            ),
        )

    except LLMRequestError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        )


def convert_analysis_to_response(
    analysis: Analysis,
) -> AnalysisHistoryResponse:
    """
    Converts a PostgreSQL Analysis object
    into the API response format.
    """

    return AnalysisHistoryResponse(
        analysis_id=analysis.id,
        match_score=analysis.match_score,
        matched_requirements=analysis.matched_requirements,
        missing_requirements=analysis.missing_requirements,
        suggestions=analysis.suggestions,
        resume_text=analysis.resume_text,
        job_description=analysis.job_description,
        input_type=analysis.input_type,
        resume_filename=analysis.resume_filename,
        resume_file_type=analysis.resume_file_type,
        created_at=analysis.created_at,
    )


# ---------------------------------------------------------
# Basic endpoints
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "AI Resume Job Matcher API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# ---------------------------------------------------------
# Analyze pasted resume text
# ---------------------------------------------------------

@app.post(
    "/analyze",
    response_model=JobMatchResponse,
)
def analyze_job_match(
    request: JobMatchRequest,
    session: Session = Depends(get_session),
):

    # Validate resume text
    if not request.resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Resume text cannot be empty.",
        )

    # Validate job description
    if not request.job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description cannot be empty.",
        )

    # Gemini analysis
    result = run_resume_analysis(
        resume_text=request.resume_text,
        job_description=request.job_description,
    )

    # Save successful analysis in PostgreSQL
    saved_analysis = create_analysis(
        session=session,
        resume_text=request.resume_text,
        job_description=request.job_description,
        analysis_result=result,
        input_type="text",
    )

    return JobMatchResponse(
        analysis_id=saved_analysis.id,
        match_score=saved_analysis.match_score,
        matched_requirements=saved_analysis.matched_requirements,
        missing_requirements=saved_analysis.missing_requirements,
        suggestions=saved_analysis.suggestions,
    )


# ---------------------------------------------------------
# Analyze uploaded PDF or DOCX resume
# ---------------------------------------------------------

@app.post(
    "/analyze-file",
    response_model=JobMatchResponse,
)
async def analyze_resume_file(
    job_description: str = Form(...),
    resume_file: UploadFile = File(...),
    session: Session = Depends(get_session),
):

    # Get filename
    filename = resume_file.filename or ""

    # Only PDF and DOCX files are supported
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported.",
        )

    # Extract the extension:
    # resume.PDF -> pdf
    # resume.docx -> docx
    file_type = filename.rsplit(".", 1)[-1].lower()

    # Validate job description
    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description cannot be empty.",
        )

    # Read uploaded file into memory
    file_bytes = await resume_file.read()

    # Reject empty files
    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # Maximum file size validation
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum allowed size is 5 MB.",
        )

    # Extract resume text from PDF or DOCX
    try:
        resume_text = extract_resume_text(
            file_bytes=file_bytes,
            filename=filename,
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the resume file: {str(error)}",
        )

    # Make sure some text was actually extracted
    if not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "No readable text was found in the resume. "
                "The file may be scanned or image-based."
            ),
        )

    # Gemini analysis
    result = run_resume_analysis(
        resume_text=resume_text,
        job_description=job_description,
    )

    # Save successful analysis and file metadata
    saved_analysis = create_analysis(
        session=session,
        resume_text=resume_text,
        job_description=job_description,
        analysis_result=result,
        input_type="file",
        resume_filename=filename,
        resume_file_type=file_type,
    )

    return JobMatchResponse(
        analysis_id=saved_analysis.id,
        match_score=saved_analysis.match_score,
        matched_requirements=saved_analysis.matched_requirements,
        missing_requirements=saved_analysis.missing_requirements,
        suggestions=saved_analysis.suggestions,
    )


# ---------------------------------------------------------
# Analysis history
# ---------------------------------------------------------

@app.get(
    "/analyses",
    response_model=List[AnalysisHistoryResponse],
)
def get_all_recent_analyses(
    session: Session = Depends(get_session),
):

    analyses = get_recent_analyses(
        session=session,
        limit=10,
    )

    return [
        convert_analysis_to_response(analysis)
        for analysis in analyses
    ]


@app.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisHistoryResponse,
)
def get_single_analysis(
    analysis_id: int,
    session: Session = Depends(get_session),
):

    analysis = get_analysis_by_id(
        session=session,
        analysis_id=analysis_id,
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found.",
        )

    return convert_analysis_to_response(analysis)