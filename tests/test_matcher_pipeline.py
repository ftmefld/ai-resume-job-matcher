from app.services.matching_models import (
    JobRequirement,
    RequirementMatch,
    RequirementMatchingResult,
)

import app.services.matcher_pipeline as pipeline_module


def fake_requirements(
    job_description,
    observability=None,
):
    return [
        JobRequirement(
            requirement_id="R001",
            requirement="Python",
            category="skill",
            importance="important",
            source_text="Python experience required.",
        ),
        JobRequirement(
            requirement_id="R002",
            requirement="Docker",
            category="tool",
            importance="important",
            source_text="Docker experience preferred.",
        ),
    ]


def fake_matching(
    resume_text,
    requirements,
    observability=None,
):
    return RequirementMatchingResult(
        matches=[
            RequirementMatch(
                requirement_id="R001",
                requirement="Python",
                category="skill",
                importance="important",
                status="matched",
                evidence=[
                    "Developed applications using Python."
                ],
                rationale=(
                    "Python is explicitly supported."
                ),
            ),
            RequirementMatch(
                requirement_id="R002",
                requirement="Docker",
                category="tool",
                importance="important",
                status="missing",
                evidence=[],
                rationale=(
                    "Docker is not supported by the resume."
                ),
            ),
        ],
        suggestions=[],
    )


def fake_gap_suggestions(
    resume_text,
    matches,
    observability=None,
):
    return [
        "Gain hands-on Docker experience."
    ]


def test_full_v2_pipeline(
    monkeypatch,
):

    monkeypatch.setattr(
        pipeline_module,
        "extract_job_requirements",
        fake_requirements,
    )

    monkeypatch.setattr(
        pipeline_module,
        "match_resume_to_requirements",
        fake_matching,
    )

    monkeypatch.setattr(
        pipeline_module,
        "generate_gap_suggestions",
        fake_gap_suggestions,
    )

    result = pipeline_module.analyze_resume_v2(
        resume_text=(
            "Developed applications using Python."
        ),
        job_description=(
            "Python experience required. "
            "Docker experience preferred."
        ),
    )

    assert result.match_score == 50.0

    assert result.matched_requirements == [
        "Python"
    ]

    assert result.missing_requirements == [
        "Docker"
    ]

    assert result.suggestions == [
        "Gain hands-on Docker experience."
    ]