from collections import defaultdict
from typing import Dict, List

from app.services.matching_models import RequirementMatch


IMPORTANCE_WEIGHTS = {
    "must_have": 3.0,
    "important": 2.0,
    "preferred": 1.0,
}


STATUS_VALUES = {
    "matched": 1.0,
    "partial": 0.5,
    "missing": 0.0,
}


def calculate_match_score(
    matches: List[RequirementMatch],
) -> float:

    if not matches:
        return 0.0

    earned_score = 0.0
    maximum_score = 0.0

    for match in matches:
        importance_weight = IMPORTANCE_WEIGHTS[
            match.importance
        ]

        status_value = STATUS_VALUES[
            match.status
        ]

        earned_score += (
            importance_weight * status_value
        )

        maximum_score += importance_weight

    if maximum_score == 0:
        return 0.0

    final_score = (
        earned_score / maximum_score
    ) * 100

    return round(final_score, 1)


def calculate_score_breakdown(
    matches: List[RequirementMatch],
) -> Dict[str, float]:

    category_earned = defaultdict(float)
    category_maximum = defaultdict(float)

    for match in matches:
        importance_weight = IMPORTANCE_WEIGHTS[
            match.importance
        ]

        status_value = STATUS_VALUES[
            match.status
        ]

        category_earned[match.category] += (
            importance_weight * status_value
        )

        category_maximum[match.category] += (
            importance_weight
        )

    breakdown = {}

    for category in category_maximum:
        score = (
            category_earned[category]
            / category_maximum[category]
        ) * 100

        breakdown[category] = round(score, 1)

    return breakdown

from app.services.matching_models import (
    FinalMatchResult,
    RequirementMatchingResult,
)


def build_final_match_result(
    matching_result: RequirementMatchingResult,
) -> FinalMatchResult:

    matches = matching_result.matches

    match_score = calculate_match_score(
        matches
    )

    score_breakdown = calculate_score_breakdown(
        matches
    )

    matched_requirements = [
        match.requirement
        for match in matches
        if match.status == "matched"
    ]

    partial_requirements = [
        match.requirement
        for match in matches
        if match.status == "partial"
    ]

    missing_requirements = [
        match.requirement
        for match in matches
        if match.status == "missing"
    ]

    return FinalMatchResult(
        match_score=match_score,
        score_breakdown=score_breakdown,
        requirement_matches=matches,
        matched_requirements=matched_requirements,
        partial_requirements=partial_requirements,
        missing_requirements=missing_requirements,
        suggestions=matching_result.suggestions,
    )