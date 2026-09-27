from time import perf_counter

from app.services.evidence_matcher import (
    RequirementMatchingError,
    RequirementMatchingUnavailableError,
    match_resume_to_requirements,
)
from app.services.matching_models import (
    FinalMatchResult,
    RequirementMatchingResult,
)
from app.services.observability import (
    ObservabilityCollector,
)
from app.services.requirement_extractor import (
    RequirementExtractionError,
    RequirementExtractionUnavailableError,
    extract_job_requirements,
)
from app.services.scoring import (
    build_final_match_result,
)
from app.services.suggestion_generator import (
    SuggestionGenerationUnavailableError,
    build_fallback_suggestions,
    generate_gap_suggestions,
)


PIPELINE_VERSION = "matcher-v2.1"


class NoJobRequirementsError(Exception):
    pass


class MatcherUnavailableError(Exception):
    pass


class MatcherAnalysisError(Exception):
    pass


def analyze_resume_v2(
    resume_text: str,
    job_description: str,
) -> FinalMatchResult:

    if not resume_text.strip():
        raise ValueError(
            "Resume text cannot be empty."
        )

    if not job_description.strip():
        raise ValueError(
            "Job description cannot be empty."
        )

    pipeline_start = perf_counter()

    observability = ObservabilityCollector(
        pipeline_version=PIPELINE_VERSION
    )

    try:
        requirements = extract_job_requirements(
            job_description,
            observability=observability,
        )

        if not requirements:
            raise NoJobRequirementsError(
                "No meaningful job requirements "
                "could be extracted."
            )

        matching_result = (
            match_resume_to_requirements(
                resume_text=resume_text,
                requirements=requirements,
                observability=observability,
            )
        )

    except (
        RequirementExtractionUnavailableError,
        RequirementMatchingUnavailableError,
    ) as error:

        raise MatcherUnavailableError(
            "The AI analysis service is "
            "temporarily unavailable."
        ) from error

    except (
        RequirementExtractionError,
        RequirementMatchingError,
    ) as error:

        raise MatcherAnalysisError(
            "The AI analysis could not produce "
            "a valid result."
        ) from error

    try:
        suggestions = generate_gap_suggestions(
            resume_text=resume_text,
            matches=matching_result.matches,
            observability=observability,
        )

    except SuggestionGenerationUnavailableError:

        suggestions = build_fallback_suggestions(
            matching_result.matches
        )

    matching_result_with_suggestions = (
        RequirementMatchingResult(
            matches=matching_result.matches,
            suggestions=suggestions,
        )
    )

    final_result = build_final_match_result(
        matching_result_with_suggestions
    )

    total_latency_ms = (
        perf_counter() - pipeline_start
    ) * 1000

    observability_result = (
        observability.build(
            total_latency_ms=(
                total_latency_ms
            )
        )
    )

    return final_result.model_copy(
        update={
            "observability": (
                observability_result
            )
        }
    )