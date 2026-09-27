from app.services.matching_models import (
    JobRequirement,
    RequirementAssessment,
    RequirementAssessmentBatch,
)

import app.services.evidence_matcher as matcher_module


RESUME_TEXT = """
Registered Nurse with active RN license.
Two years of clinical nursing experience in acute care.
Experienced with patient monitoring and medication administration.
"""


REQUIREMENTS = [
    JobRequirement(
        requirement_id="R001",
        requirement="Active RN license",
        category="license",
        importance="must_have",
        source_text=(
            "Candidates must hold an active RN license."
        ),
    ),
    JobRequirement(
        requirement_id="R002",
        requirement="5 years of clinical experience",
        category="experience",
        importance="important",
        source_text=(
            "Five years of clinical experience is required."
        ),
    ),
    JobRequirement(
        requirement_id="R003",
        requirement="ICU experience",
        category="experience",
        importance="preferred",
        source_text=(
            "ICU experience is preferred."
        ),
    ),
]


def fake_assessments(
    model_name,
    prompt,
):
    return RequirementAssessmentBatch(
        assessments=[
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence=[
                    (
                        "Registered Nurse with active "
                        "RN license."
                    )
                ],
                rationale=(
                    "The resume explicitly confirms "
                    "an active RN license."
                ),
            ),
            RequirementAssessment(
                requirement_id="R002",
                status="partial",
                evidence=[
                    (
                        "Two years of clinical nursing "
                        "experience in acute care."
                    )
                ],
                rationale=(
                    "The candidate has relevant experience "
                    "but fewer than five years."
                ),
            ),
            RequirementAssessment(
                requirement_id="R003",
                status="missing",
                evidence=[],
                rationale=(
                    "The resume does not mention ICU experience."
                ),
            ),
        ]
    )


def test_evidence_grounded_matching(
    monkeypatch,
):
    monkeypatch.setattr(
        matcher_module,
        "_generate_assessments",
        fake_assessments,
    )

    result = matcher_module.match_resume_to_requirements(
        resume_text=RESUME_TEXT,
        requirements=REQUIREMENTS,
    )

    assert len(result.matches) == 3

    assert result.matches[0].status == "matched"

    assert result.matches[1].status == "partial"

    assert result.matches[2].status == "missing"

    assert result.matches[0].evidence == [
        "Registered Nurse with active RN license."
    ]


def test_hallucinated_evidence_is_rejected(
    monkeypatch,
):
    def fake_hallucinated_assessments(
        model_name,
        prompt,
    ):
        return RequirementAssessmentBatch(
            assessments=[
                RequirementAssessment(
                    requirement_id="R001",
                    status="matched",
                    evidence=[
                        "Has ten years of RN experience."
                    ],
                    rationale="Candidate is experienced.",
                ),
                RequirementAssessment(
                    requirement_id="R002",
                    status="partial",
                    evidence=[
                        (
                            "Two years of clinical nursing "
                            "experience in acute care."
                        )
                    ],
                    rationale=(
                        "The candidate has partial experience."
                    ),
                ),
                RequirementAssessment(
                    requirement_id="R003",
                    status="missing",
                    evidence=[],
                    rationale="No ICU evidence.",
                ),
            ]
        )

    monkeypatch.setattr(
        matcher_module,
        "_generate_assessments",
        fake_hallucinated_assessments,
    )

    result = matcher_module.match_resume_to_requirements(
        resume_text=RESUME_TEXT,
        requirements=REQUIREMENTS,
    )

    first_match = result.matches[0]

    assert first_match.status == "missing"
    assert first_match.evidence == []


def test_empty_resume_is_rejected():

    try:
        matcher_module.match_resume_to_requirements(
            resume_text="   ",
            requirements=REQUIREMENTS,
        )

        assert False

    except ValueError as error:

        assert str(error) == (
            "Resume text cannot be empty."
        )