from app.services.matching_models import (
    RequirementMatch,
    SuggestionBatch,
)

import app.services.suggestion_generator as suggestion_module


MATCHES = [
    RequirementMatch(
        requirement_id="R001",
        requirement="Active RN license",
        category="license",
        importance="must_have",
        status="matched",
        evidence=[
            "Registered Nurse with active RN license."
        ],
        rationale="License is explicitly supported.",
    ),
    RequirementMatch(
        requirement_id="R002",
        requirement="5 years clinical experience",
        category="experience",
        importance="must_have",
        status="partial",
        evidence=[
            "Two years of clinical nursing experience."
        ],
        rationale=(
            "Relevant experience exists but the "
            "requested duration is not met."
        ),
    ),
    RequirementMatch(
        requirement_id="R003",
        requirement="ICU experience",
        category="experience",
        importance="preferred",
        status="missing",
        evidence=[],
        rationale="No ICU experience is supported.",
    ),
]


def fake_suggestions(
    model_name,
    prompt,
):
    return SuggestionBatch(
        suggestions=[
            (
                "Gain additional clinical experience to better "
                "meet roles requiring five years of practice."
            ),
            (
                "Consider gaining ICU experience if targeting "
                "critical-care nursing roles."
            ),
        ]
    )


def test_generate_gap_suggestions(
    monkeypatch,
):

    monkeypatch.setattr(
        suggestion_module,
        "_generate_suggestions",
        fake_suggestions,
    )

    suggestions = (
        suggestion_module.generate_gap_suggestions(
            resume_text=(
                "Registered Nurse with active RN license. "
                "Two years of clinical nursing experience."
            ),
            matches=MATCHES,
        )
    )

    assert len(suggestions) == 2

    assert "clinical experience" in (
        suggestions[0].lower()
    )


def test_no_gaps_returns_no_suggestions():

    matched_only = [
        MATCHES[0]
    ]

    suggestions = (
        suggestion_module.generate_gap_suggestions(
            resume_text=(
                "Registered Nurse with active RN license."
            ),
            matches=matched_only,
        )
    )

    assert suggestions == []


def test_fallback_suggestions():

    suggestions = (
        suggestion_module.build_fallback_suggestions(
            MATCHES
        )
    )

    assert len(suggestions) >= 1

    assert any(
        "5 years clinical experience" in suggestion
        for suggestion in suggestions
    )