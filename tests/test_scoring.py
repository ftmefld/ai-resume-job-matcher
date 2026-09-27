from app.services.matching_models import (
    RequirementMatch,
    RequirementMatchingResult,
)

from app.services.scoring import (
    build_final_match_result,
    calculate_match_score,
    calculate_score_breakdown,
)


def create_test_matches():
    return [
        RequirementMatch(
            requirement_id="R001",
            requirement="Active RN license",
            category="license",
            importance="must_have",
            status="matched",
            evidence=[
                "Registered Nurse with active RN license."
            ],
            rationale="The resume explicitly states an RN license.",
        ),
        RequirementMatch(
            requirement_id="R002",
            requirement="5 years clinical experience",
            category="experience",
            importance="important",
            status="partial",
            evidence=[
                "2 years of clinical nursing experience."
            ],
            rationale=(
                "The candidate has relevant clinical experience "
                "but does not meet the requested duration."
            ),
        ),
        RequirementMatch(
            requirement_id="R003",
            requirement="ICU experience",
            category="experience",
            importance="preferred",
            status="missing",
            evidence=[],
            rationale=(
                "No ICU experience is supported by the resume."
            ),
        ),
    ]


def test_calculate_match_score():
    matches = create_test_matches()

    score = calculate_match_score(matches)

    assert score == 66.7


def test_score_breakdown():
    matches = create_test_matches()

    breakdown = calculate_score_breakdown(
        matches
    )

    assert breakdown["license"] == 100.0
    assert breakdown["experience"] == 33.3


def test_build_final_match_result():
    matches = create_test_matches()

    matching_result = RequirementMatchingResult(
        matches=matches,
        suggestions=[
            "Gain additional clinical experience."
        ],
    )

    result = build_final_match_result(
        matching_result
    )

    assert result.match_score == 66.7

    assert result.matched_requirements == [
        "Active RN license"
    ]

    assert result.partial_requirements == [
        "5 years clinical experience"
    ]

    assert result.missing_requirements == [
        "ICU experience"
    ]