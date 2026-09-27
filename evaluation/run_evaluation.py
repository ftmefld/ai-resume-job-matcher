import argparse
import json

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.services.evidence_matcher import (
    match_resume_to_requirements,
)
from app.services.matching_models import (
    JobRequirement,
    RequirementMatch,
)
from app.services.observability import (
    ObservabilityCollector,
)
from app.services.requirement_extractor import (
    extract_job_requirements,
)
from app.services.scoring import (
    calculate_match_score,
)

from evaluation.metrics import (
    evaluate_matching,
    evaluate_requirement_extraction,
)
from evaluation.schemas import (
    EvaluationCase,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).parent

DATA_DIR = (
    BASE_DIR
    / "data"
)

REPORTS_DIR = (
    BASE_DIR
    / "reports"
)


DATASET_FILES = {
    "pilot": DATA_DIR / "pilot.jsonl",
    "dev": DATA_DIR / "dev.jsonl",
    "test": DATA_DIR / "test.jsonl",
}


# ---------------------------------------------------------
# Command-line arguments
# ---------------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the resume matcher "
            "evaluation benchmark."
        )
    )

    parser.add_argument(
        "--dataset",
        choices=[
            "pilot",
            "dev",
            "test",
        ],
        default="dev",
        help=(
            "Dataset to evaluate. "
            "Choices: pilot, dev, test. "
            "Default: dev."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------
# Load benchmark
# ---------------------------------------------------------

def load_benchmark(
    dataset_name: str,
):
    benchmark_path = (
        DATASET_FILES[
            dataset_name
        ]
    )

    if not benchmark_path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: "
            f"{benchmark_path}"
        )

    cases = []

    with benchmark_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):

            if not line.strip():
                continue

            try:
                data = json.loads(
                    line
                )

                case = (
                    EvaluationCase.model_validate(
                        data
                    )
                )

                cases.append(
                    case
                )

            except Exception as error:
                raise ValueError(
                    f"Invalid benchmark data "
                    f"in {benchmark_path.name} "
                    f"at line {line_number}: "
                    f"{error}"
                ) from error

    return cases


# ---------------------------------------------------------
# Convert gold requirements into JobRequirements
# ---------------------------------------------------------

def build_gold_requirements(
    case: EvaluationCase,
):
    requirements = []

    for index, gold in enumerate(
        case.gold_requirements,
        start=1,
    ):

        requirements.append(
            JobRequirement(
                requirement_id=(
                    f"R{index:03d}"
                ),
                requirement=(
                    gold.requirement
                ),
                category=(
                    gold.category
                ),
                importance=(
                    gold.importance
                ),
                source_text=(
                    gold.source_text
                ),
            )
        )

    return requirements


# ---------------------------------------------------------
# Calculate ideal gold score
# ---------------------------------------------------------

def calculate_gold_score(
    case: EvaluationCase,
) -> float:

    matches = []

    for index, gold in enumerate(
        case.gold_requirements,
        start=1,
    ):

        matches.append(
            RequirementMatch(
                requirement_id=(
                    f"R{index:03d}"
                ),
                requirement=(
                    gold.requirement
                ),
                category=(
                    gold.category
                ),
                importance=(
                    gold.importance
                ),
                status=(
                    gold.expected_status
                ),
                evidence=[],
                rationale=(
                    "Gold benchmark label."
                ),
            )
        )

    return calculate_match_score(
        matches
    )


# ---------------------------------------------------------
# Evaluate one benchmark case
# ---------------------------------------------------------

def evaluate_case(
    case: EvaluationCase,
):

    print()
    print(
        f"Evaluating {case.case_id} "
        f"({case.domain})..."
    )

    start_time = perf_counter()

    collector = (
        ObservabilityCollector(
            pipeline_version=(
                "evaluation-v2"
            )
        )
    )

    # -----------------------------------------------------
    # Stage 1:
    # Evaluate requirement extraction
    # -----------------------------------------------------

    predicted_requirements = (
        extract_job_requirements(
            case.job_description,
            observability=collector,
        )
    )

    extraction_metrics = (
        evaluate_requirement_extraction(
            predicted=(
                predicted_requirements
            ),
            gold=(
                case.gold_requirements
            ),
        )
    )

    # -----------------------------------------------------
    # Stage 2:
    # Evaluate evidence matching independently
    #
    # IMPORTANT:
    # We use GOLD requirements here instead of
    # predicted requirements.
    #
    # This prevents extraction errors from affecting
    # evidence-matching evaluation.
    # -----------------------------------------------------

    gold_requirements = (
        build_gold_requirements(
            case
        )
    )

    matching_result = (
        match_resume_to_requirements(
            resume_text=(
                case.resume_text
            ),
            requirements=(
                gold_requirements
            ),
            observability=collector,
        )
    )

    matching_metrics = (
        evaluate_matching(
            predicted_matches=(
                matching_result.matches
            ),
            gold=(
                case.gold_requirements
            ),
            resume_text=(
                case.resume_text
            ),
        )
    )

    # -----------------------------------------------------
    # Stage 3:
    # Score evaluation
    # -----------------------------------------------------

    predicted_score = (
        calculate_match_score(
            matching_result.matches
        )
    )

    gold_score = (
        calculate_gold_score(
            case
        )
    )

    score_error = abs(
        predicted_score
        - gold_score
    )

    # -----------------------------------------------------
    # Observability
    # -----------------------------------------------------

    total_latency_ms = (
        perf_counter()
        - start_time
    ) * 1000

    observability = (
        collector.build(
            total_latency_ms=(
                total_latency_ms
            )
        )
    )

    # -----------------------------------------------------
    # Build case result
    # -----------------------------------------------------

    return {
        "case_id": (
            case.case_id
        ),

        "domain": (
            case.domain
        ),

        "extraction": (
            extraction_metrics
        ),

        "matching": (
            matching_metrics
        ),

        "gold_score": (
            gold_score
        ),

        "predicted_score": (
            predicted_score
        ),

        "score_absolute_error": (
            round(
                score_error,
                2,
            )
        ),

        "predicted_requirements": [
            requirement.model_dump()
            for requirement
            in predicted_requirements
        ],

        "predicted_matches": [
            match.model_dump()
            for match
            in matching_result.matches
        ],

        "observability": (
            observability.model_dump()
        ),
    }


# ---------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------

def build_summary(
    results,
    total_cases,
    failures,
):
    completed_cases = len(
        results
    )

    failed_cases = len(
        failures
    )

    completion_rate = (
        completed_cases
        / total_cases
        if total_cases
        else 0.0
    )

    # If every case failed,
    # quality metrics cannot be calculated.
    if not results:
        return {
            "total_cases": (
                total_cases
            ),
            "completed_cases": 0,
            "failed_cases": (
                failed_cases
            ),
            "completion_rate": (
                0.0
            ),
        }

    # -----------------------------------------------------
    # Requirement extraction counts
    # -----------------------------------------------------

    predicted_total = sum(
        result[
            "extraction"
        ][
            "predicted_count"
        ]
        for result in results
    )

    gold_total = sum(
        result[
            "extraction"
        ][
            "gold_count"
        ]
        for result in results
    )

    extracted_matched_total = sum(
        result[
            "extraction"
        ][
            "matched_count"
        ]
        for result in results
    )

    category_correct = sum(
        result[
            "extraction"
        ][
            "category_correct"
        ]
        for result in results
    )

    importance_correct = sum(
        result[
            "extraction"
        ][
            "importance_correct"
        ]
        for result in results
    )

    # -----------------------------------------------------
    # Matching counts
    # -----------------------------------------------------

    status_correct = sum(
        result[
            "matching"
        ][
            "status_correct"
        ]
        for result in results
    )

    status_total = sum(
        result[
            "matching"
        ][
            "status_total"
        ]
        for result in results
    )

    evidence_total = sum(
        result[
            "matching"
        ][
            "evidence_total"
        ]
        for result in results
    )

    evidence_grounded = sum(
        result[
            "matching"
        ][
            "evidence_grounded"
        ]
        for result in results
    )

    hallucinated_evidence = sum(
        result[
            "matching"
        ].get(
            "hallucinated_evidence",
            0,
        )
        for result in results
    )

    # -----------------------------------------------------
    # Extraction metrics
    # -----------------------------------------------------

    extraction_precision = (
        extracted_matched_total
        / predicted_total
        if predicted_total
        else 0.0
    )

    extraction_recall = (
        extracted_matched_total
        / gold_total
        if gold_total
        else 0.0
    )

    category_accuracy = (
        category_correct
        / extracted_matched_total
        if extracted_matched_total
        else 0.0
    )

    importance_accuracy = (
        importance_correct
        / extracted_matched_total
        if extracted_matched_total
        else 0.0
    )

    # -----------------------------------------------------
    # Matching metrics
    # -----------------------------------------------------

    status_accuracy = (
        status_correct
        / status_total
        if status_total
        else 0.0
    )

    evidence_grounding_rate = (
        evidence_grounded
        / evidence_total
        if evidence_total
        else 1.0
    )

    evidence_hallucination_rate = (
        hallucinated_evidence
        / evidence_total
        if evidence_total
        else 0.0
    )

    # -----------------------------------------------------
    # Score metrics
    # -----------------------------------------------------

    score_mae = mean(
        result[
            "score_absolute_error"
        ]
        for result in results
    )

    # -----------------------------------------------------
    # Latency
    # -----------------------------------------------------

    latencies = [
        result[
            "observability"
        ][
            "total_latency_ms"
        ]
        for result in results
    ]

    average_latency_ms = mean(
        latencies
    )

    sorted_latencies = sorted(
        latencies
    )

    p95_index = max(
        0,
        int(
            0.95
            * len(
                sorted_latencies
            )
        )
        - 1,
    )

    p95_latency_ms = (
        sorted_latencies[
            p95_index
        ]
    )

    # -----------------------------------------------------
    # Fallback metrics
    # -----------------------------------------------------

    fallback_cases = sum(
        1
        for result in results
        if result[
            "observability"
        ][
            "fallback_used"
        ]
    )

    fallback_rate = (
        fallback_cases
        / completed_cases
        if completed_cases
        else 0.0
    )

    # -----------------------------------------------------
    # LLM call reliability metrics
    # -----------------------------------------------------

    all_calls = []

    for result in results:
        all_calls.extend(
            result[
                "observability"
            ][
                "calls"
            ]
        )

    total_llm_calls = len(
        all_calls
    )

    successful_llm_calls = sum(
        1
        for call in all_calls
        if call["status"]
        == "success"
    )

    failed_llm_calls = sum(
        1
        for call in all_calls
        if call["status"]
        == "error"
    )

    primary_calls = [
        call
        for call in all_calls
        if not call[
            "is_fallback"
        ]
    ]

    successful_primary_calls = sum(
        1
        for call in primary_calls
        if call["status"]
        == "success"
    )

    primary_success_rate = (
        successful_primary_calls
        / len(primary_calls)
        if primary_calls
        else 0.0
    )

    fallback_calls = [
        call
        for call in all_calls
        if call[
            "is_fallback"
        ]
    ]

    successful_fallback_calls = sum(
        1
        for call in fallback_calls
        if call["status"]
        == "success"
    )

    fallback_recovery_rate = (
        successful_fallback_calls
        / len(fallback_calls)
        if fallback_calls
        else 1.0
    )

    llm_call_success_rate = (
        successful_llm_calls
        / total_llm_calls
        if total_llm_calls
        else 0.0
    )

    # -----------------------------------------------------
    # Final summary
    # -----------------------------------------------------

    return {
        "total_cases": (
            total_cases
        ),

        "completed_cases": (
            completed_cases
        ),

        "failed_cases": (
            failed_cases
        ),

        "completion_rate": round(
            completion_rate,
            4,
        ),

        "requirement_extraction_precision": round(
            extraction_precision,
            4,
        ),

        "requirement_extraction_recall": round(
            extraction_recall,
            4,
        ),

        "category_accuracy": round(
            category_accuracy,
            4,
        ),

        "importance_accuracy": round(
            importance_accuracy,
            4,
        ),

        "match_status_accuracy": round(
            status_accuracy,
            4,
        ),

        "evidence_grounding_rate": round(
            evidence_grounding_rate,
            4,
        ),

        "evidence_hallucination_rate": round(
            evidence_hallucination_rate,
            4,
        ),

        "score_mae": round(
            score_mae,
            2,
        ),

        "average_latency_ms": round(
            average_latency_ms,
            2,
        ),

        "p95_latency_ms": round(
            p95_latency_ms,
            2,
        ),

        "fallback_rate": round(
            fallback_rate,
            4,
        ),

        "total_llm_calls": (
            total_llm_calls
        ),

        "failed_llm_calls": (
            failed_llm_calls
        ),

        "llm_call_success_rate": round(
            llm_call_success_rate,
            4,
        ),

        "primary_model_success_rate": round(
            primary_success_rate,
            4,
        ),

        "fallback_recovery_rate": round(
            fallback_recovery_rate,
            4,
        ),
    }


# ---------------------------------------------------------
# Per-domain summary
# ---------------------------------------------------------

def build_domain_summaries(
    results,
):
    domains = sorted(
        {
            result["domain"]
            for result in results
        }
    )

    summaries = {}

    for domain in domains:

        domain_results = [
            result
            for result in results
            if result[
                "domain"
            ] == domain
        ]

        domain_failures = []

        summaries[
            domain
        ] = build_summary(
            results=(
                domain_results
            ),
            total_cases=len(
                domain_results
            ),
            failures=(
                domain_failures
            ),
        )

    return summaries


# ---------------------------------------------------------
# Save report
# ---------------------------------------------------------

def save_report(
    dataset_name,
    summary,
    domain_summaries,
    results,
    failures,
):
    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    path = (
        REPORTS_DIR
        / (
            f"{dataset_name}_"
            f"evaluation_"
            f"{timestamp}.json"
        )
    )

    report = {
        "created_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "dataset": (
            dataset_name
        ),

        "summary": (
            summary
        ),

        "domain_summaries": (
            domain_summaries
        ),

        "cases": (
            results
        ),

        "failures": (
            failures
        ),
    }

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return path


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    args = parse_arguments()

    dataset_name = (
        args.dataset
    )

    # A reminder that the test set should
    # remain untouched during prompt tuning.
    if dataset_name == "test":
        print()
        print(
            "WARNING: You are running the "
            "untouched TEST benchmark."
        )
        print(
            "Do not tune the prompt based "
            "on these results."
        )
        print()

    cases = load_benchmark(
        dataset_name
    )

    print(
        f"Dataset: {dataset_name}"
    )

    print(
        f"Loaded {len(cases)} "
        "evaluation cases."
    )

    results = []
    failures = []

    for case in cases:

        try:
            result = evaluate_case(
                case
            )

            results.append(
                result
            )

        except Exception as error:

            failure = {
                "case_id": (
                    case.case_id
                ),
                "domain": (
                    case.domain
                ),
                "error_type": (
                    type(
                        error
                    ).__name__
                ),
                "error_message": (
                    str(
                        error
                    )
                ),
            }

            failures.append(
                failure
            )

            print(
                f"FAILED "
                f"{case.case_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    summary = build_summary(
        results=results,
        total_cases=len(
            cases
        ),
        failures=failures,
    )

    domain_summaries = (
        build_domain_summaries(
            results
        )
        if results
        else {}
    )

    path = save_report(
        dataset_name=(
            dataset_name
        ),
        summary=(
            summary
        ),
        domain_summaries=(
            domain_summaries
        ),
        results=(
            results
        ),
        failures=(
            failures
        ),
    )

    # -----------------------------------------------------
    # Print overall summary
    # -----------------------------------------------------

    print()
    print(
        "=" * 60
    )
    print(
        "EVALUATION SUMMARY"
    )
    print(
        "=" * 60
    )

    print(
        f"dataset: "
        f"{dataset_name}"
    )

    for key, value in (
        summary.items()
    ):
        print(
            f"{key}: {value}"
        )

        # -----------------------------------------------------
    # Print domain summaries
    # -----------------------------------------------------

    if domain_summaries:

        print()
        print("=" * 60)
        print("DOMAIN SUMMARY")
        print("=" * 60)

        for domain, domain_summary in domain_summaries.items():

            print()
            print(f"[{domain}]")

            precision = domain_summary.get(
                "requirement_extraction_precision"
            )

            recall = domain_summary.get(
                "requirement_extraction_recall"
            )

            category_accuracy = domain_summary.get(
                "category_accuracy"
            )

            importance_accuracy = domain_summary.get(
                "importance_accuracy"
            )

            match_status_accuracy = domain_summary.get(
                "match_status_accuracy"
            )

            print(
                f"precision: {precision}"
            )

            print(
                f"recall: {recall}"
            )

            print(
                f"category_accuracy: "
                f"{category_accuracy}"
            )

            print(
                f"importance_accuracy: "
                f"{importance_accuracy}"
            )

            print(
                f"match_status_accuracy: "
                f"{match_status_accuracy}"
            )

    # -----------------------------------------------------
    # Print failures
    # -----------------------------------------------------

    if failures:

        print()
        print(
            "=" * 60
        )
        print(
            "FAILED CASES"
        )
        print(
            "=" * 60
        )

        for failure in failures:

            print(
                f"{failure['case_id']} "
                f"({failure['domain']}): "
                f"{failure['error_type']} "
                f"- "
                f"{failure['error_message']}"
            )

    print()
    print(
        f"Report saved to: "
        f"{path}"
    )


if __name__ == "__main__":
    main()