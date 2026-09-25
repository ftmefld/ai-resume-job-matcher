from io import BytesIO

from docx import Document

import app.main as main_module
from app.services.llm_service import LLMUnavailableError


FAKE_ANALYSIS = {
    "match_score": 75,
    "matched_requirements": [
        "Python",
        "FastAPI",
    ],
    "missing_requirements": [
        "Docker",
    ],
    "suggestions": [
        "Gain hands-on Docker experience."
    ],
}


def fake_analysis(
    resume_text: str,
    job_description: str,
):
    return FAKE_ANALYSIS


def create_test_docx() -> bytes:
    document = Document()

    document.add_paragraph(
        "AI Engineer with experience in Python, "
        "FastAPI, PyTorch, and machine learning."
    )

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy"
    }


def test_analyze_text_success(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "analyze_resume_match",
        fake_analysis,
    )

    payload = {
        "resume_text": (
            "I have experience with Python, "
            "FastAPI, and machine learning."
        ),
        "job_description": (
            "We need an AI engineer with Python, "
            "FastAPI, Docker, and AWS."
        ),
    }

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["match_score"] == 75
    assert "Python" in data["matched_requirements"]
    assert "Docker" in data["missing_requirements"]
    assert data["analysis_id"] is not None


def test_analysis_saved_to_database(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "analyze_resume_match",
        fake_analysis,
    )

    payload = {
        "resume_text": "Python FastAPI developer",
        "job_description": (
            "AI engineer with Python and Docker"
        ),
    }

    create_response = client.post(
        "/analyze",
        json=payload,
    )

    assert create_response.status_code == 200

    history_response = client.get(
        "/analyses"
    )

    assert history_response.status_code == 200

    analyses = history_response.json()

    assert len(analyses) == 1
    assert analyses[0]["input_type"] == "text"
    assert analyses[0]["match_score"] == 75


def test_empty_resume_rejected(client):
    payload = {
        "resume_text": "   ",
        "job_description": (
            "AI engineer with Python"
        ),
    }

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Resume text cannot be empty."
    )


def test_invalid_resume_file_rejected(client):
    files = {
        "resume_file": (
            "resume.txt",
            b"Python developer",
            "text/plain",
        )
    }

    data = {
        "job_description": (
            "AI Engineer with Python"
        )
    }

    response = client.post(
        "/analyze-file",
        files=files,
        data=data,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only PDF and DOCX files are supported."
    )


def test_docx_upload_success(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "analyze_resume_match",
        fake_analysis,
    )

    docx_bytes = create_test_docx()

    files = {
        "resume_file": (
            "test_resume.docx",
            docx_bytes,
            (
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
        )
    }

    data = {
        "job_description": (
            "AI engineer with Python, "
            "FastAPI, Docker, and AWS"
        )
    }

    response = client.post(
        "/analyze-file",
        files=files,
        data=data,
    )

    assert response.status_code == 200

    analysis_id = response.json()[
        "analysis_id"
    ]

    history_response = client.get(
        f"/analyses/{analysis_id}"
    )

    assert history_response.status_code == 200

    saved_analysis = history_response.json()

    assert saved_analysis[
        "input_type"
    ] == "file"

    assert saved_analysis[
        "resume_filename"
    ] == "test_resume.docx"

    assert saved_analysis[
        "resume_file_type"
    ] == "docx"


def test_llm_failure_returns_503(
    client,
    monkeypatch,
):
    def failing_analysis(
        resume_text: str,
        job_description: str,
    ):
        raise LLMUnavailableError(
            "Gemini unavailable"
        )

    monkeypatch.setattr(
        main_module,
        "analyze_resume_match",
        failing_analysis,
    )

    payload = {
        "resume_text": (
            "Python AI Engineer"
        ),
        "job_description": (
            "AI engineer with Python"
        ),
    }

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "AI analysis service is temporarily "
        "unavailable. Please try again later."
    )


def test_llm_failure_not_saved(
    client,
    monkeypatch,
):
    def failing_analysis(
        resume_text: str,
        job_description: str,
    ):
        raise LLMUnavailableError(
            "Gemini unavailable"
        )

    monkeypatch.setattr(
        main_module,
        "analyze_resume_match",
        failing_analysis,
    )

    payload = {
        "resume_text": "Python AI Engineer",
        "job_description": (
            "AI engineer with Python"
        ),
    }

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 503

    history_response = client.get(
        "/analyses"
    )

    analyses = history_response.json()

    assert analyses == []