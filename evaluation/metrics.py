import re
from difflib import SequenceMatcher
from typing import List, Tuple

from app.services.matching_models import (
    JobRequirement,
    RequirementMatch,
)

from evaluation.schemas import (
    GoldRequirement,
)


def normalize_text(
    text: str,
) -> str:
    """
    Normalize text before comparing requirements
    or validating evidence.
    """

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def requirement_similarity(
    first: str,
    second: str,
) -> float:
    """
    Calculate semantic-ish lexical similarity
    between two requirement descriptions.

    We combine:
    - sequence similarity
    - Jaccard token similarity
    - token overlap

    and keep the highest score.
    """

    first_normalized = normalize_text(
        first
    )

    second_normalized = normalize_text(
        second
    )

    sequence_score = SequenceMatcher(
        None,
        first_normalized,
        second_normalized,
    ).ratio()

    first_tokens = set(
        first_normalized.split()
    )

    second_tokens = set(
        second_normalized.split()
    )

    if (
        not first_tokens
        or not second_tokens
    ):
        return sequence_score

    intersection = len(
        first_tokens
        & second_tokens
    )

    union = len(
        first_tokens
        | second_tokens
    )

    jaccard_score = (
        intersection / union
        if union
        else 0.0
    )

    overlap_score = (
        intersection
        / min(
            len(first_tokens),
            len(second_tokens),
        )
    )

    return max(
        sequence_score,
        jaccard_score,
        overlap_score,
    )


def match_extracted_requirements(
    predicted: List[JobRequirement],
    gold: List[GoldRequirement],
    threshold: float = 0.55,
) -> List[Tuple[int, int, float]]:
    """
    Match predicted requirements to gold requirements.

    Each predicted requirement can match at most
    one gold requirement, and vice versa.

    Returns tuples:

    (
        predicted_index,
        gold_index,
        similarity_score
    )
    """

    candidates = []

    for (
        predicted_index,
        predicted_item,
    ) in enumerate(
        predicted
    ):

        for (
            gold_index,
            gold_item,
        ) in enumerate(
            gold
        ):

            score = requirement_similarity(
                predicted_item.requirement,
                gold_item.requirement,
            )

            if score >= threshold:
                candidates.append(
                    (
                        predicted_index,
                        gold_index,
                        score,
                    )
                )

    # Highest similarity matches first
    candidates.sort(
        key=lambda item: item[2],
        reverse=True,
    )

    used_predictions = set()
    used_gold = set()

    matches = []

    for (
        predicted_index,
        gold_index,
        score,
    ) in candidates:

        if (
            predicted_index
            in used_predictions
        ):
            continue

        if (
            gold_index
            in used_gold
        ):
            continue

        used_predictions.add(
            predicted_index
        )

        used_gold.add(
            gold_index
        )

        matches.append(
            (
                predicted_index,
                gold_index,
                score,
            )
        )

    return matches


def evaluate_requirement_extraction(
    predicted: List[JobRequirement],
    gold: List[GoldRequirement],
) -> dict:
    """
    Evaluate requirement extraction.

    Measures:
    - number of predicted requirements
    - number of gold requirements
    - matched requirements
    - category correctness
    - importance correctness

    Also records detailed extraction errors.
    """

    matched_pairs = (
        match_extracted_requirements(
            predicted,
            gold,
        )
    )

    matched_count = len(
        matched_pairs
    )

    category_correct = 0
    importance_correct = 0

    category_errors = []
    importance_errors = []

    matched_prediction_indexes = set()
    matched_gold_indexes = set()

    matched_requirements = []

    for (
        predicted_index,
        gold_index,
        similarity_score,
    ) in matched_pairs:

        matched_prediction_indexes.add(
            predicted_index
        )

        matched_gold_indexes.add(
            gold_index
        )

        predicted_item = predicted[
            predicted_index
        ]

        gold_item = gold[
            gold_index
        ]

        matched_requirements.append(
            {
                "gold_requirement": (
                    gold_item.requirement
                ),
                "predicted_requirement": (
                    predicted_item.requirement
                ),
                "similarity": round(
                    similarity_score,
                    4,
                ),
            }
        )

        # Category evaluation
        if (
            predicted_item.category
            == gold_item.category
        ):
            category_correct += 1

        else:
            category_errors.append(
                {
                    "gold_requirement": (
                        gold_item.requirement
                    ),
                    "predicted_requirement": (
                        predicted_item.requirement
                    ),
                    "expected_category": (
                        gold_item.category
                    ),
                    "predicted_category": (
                        predicted_item.category
                    ),
                    "similarity": round(
                        similarity_score,
                        4,
                    ),
                }
            )

        # Importance evaluation
        if (
            predicted_item.importance
            == gold_item.importance
        ):
            importance_correct += 1

        else:
            importance_errors.append(
                {
                    "gold_requirement": (
                        gold_item.requirement
                    ),
                    "predicted_requirement": (
                        predicted_item.requirement
                    ),
                    "expected_importance": (
                        gold_item.importance
                    ),
                    "predicted_importance": (
                        predicted_item.importance
                    ),
                    "similarity": round(
                        similarity_score,
                        4,
                    ),
                }
            )

    # Predicted requirements with no gold match
    unsupported_requirements = []

    for index, item in enumerate(
        predicted
    ):
        if (
            index
            not in matched_prediction_indexes
        ):
            unsupported_requirements.append(
                {
                    "requirement": (
                        item.requirement
                    ),
                    "category": (
                        item.category
                    ),
                    "importance": (
                        item.importance
                    ),
                    "source_text": (
                        item.source_text
                    ),
                }
            )

    # Gold requirements the model missed
    missed_requirements = []

    for index, item in enumerate(
        gold
    ):
        if (
            index
            not in matched_gold_indexes
        ):
            missed_requirements.append(
                {
                    "requirement": (
                        item.requirement
                    ),
                    "category": (
                        item.category
                    ),
                    "importance": (
                        item.importance
                    ),
                }
            )

    return {
        "predicted_count": len(
            predicted
        ),

        "gold_count": len(
            gold
        ),

        "matched_count": (
            matched_count
        ),

        "category_correct": (
            category_correct
        ),

        "importance_correct": (
            importance_correct
        ),

        "matched_requirements": (
            matched_requirements
        ),

        "category_errors": (
            category_errors
        ),

        "importance_errors": (
            importance_errors
        ),

        "unsupported_requirements": (
            unsupported_requirements
        ),

        "missed_requirements": (
            missed_requirements
        ),
    }


def evaluate_matching(
    predicted_matches: List[
        RequirementMatch
    ],
    gold: List[
        GoldRequirement
    ],
    resume_text: str,
) -> dict:
    """
    Evaluate evidence-grounded matching.

    This stage assumes the matcher receives
    gold requirements with IDs R001, R002, ...

    Measures:
    - match status accuracy
    - evidence grounding
    - detailed status errors
    """

    status_correct = 0

    total = len(
        gold
    )

    gold_by_id = {
        f"R{index:03d}": gold_requirement
        for index, gold_requirement
        in enumerate(
            gold,
            start=1,
        )
    }

    evidence_total = 0
    evidence_grounded = 0

    status_errors = []

    normalized_resume = normalize_text(
        resume_text
    )

    for match in predicted_matches:

        gold_requirement = (
            gold_by_id.get(
                match.requirement_id
            )
        )

        if gold_requirement is None:
            continue

        # Status evaluation
        if (
            match.status
            == gold_requirement.expected_status
        ):
            status_correct += 1

        else:
            status_errors.append(
                {
                    "requirement_id": (
                        match.requirement_id
                    ),
                    "requirement": (
                        gold_requirement.requirement
                    ),
                    "expected_status": (
                        gold_requirement.expected_status
                    ),
                    "predicted_status": (
                        match.status
                    ),
                    "evidence": (
                        match.evidence
                    ),
                    "rationale": (
                        match.rationale
                    ),
                }
            )

        # Evidence grounding evaluation
        for evidence in match.evidence:

            evidence_total += 1

            normalized_evidence = (
                normalize_text(
                    evidence
                )
            )

            if (
                normalized_evidence
                and normalized_evidence
                in normalized_resume
            ):
                evidence_grounded += 1

    hallucinated_evidence = (
        evidence_total
        - evidence_grounded
    )

    return {
        "status_correct": (
            status_correct
        ),

        "status_total": (
            total
        ),

        "status_errors": (
            status_errors
        ),

        "evidence_total": (
            evidence_total
        ),

        "evidence_grounded": (
            evidence_grounded
        ),

        "hallucinated_evidence": (
            hallucinated_evidence
        ),
    }