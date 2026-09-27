import json
import os
import re
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from app.services.matching_models import (
    JobRequirement,
    RequirementAssessmentBatch,
    RequirementMatch,
    RequirementMatchingResult,
)
from app.services.observability import (
    ObservabilityCollector,
    run_observed_call,
)


load_dotenv()


PROMPT_VERSION = "evidence-match-v1"


class RequirementMatchingError(Exception):
    pass


class RequirementMatchingUnavailableError(Exception):
    pass


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=api_key
    )


SYSTEM_INSTRUCTION = """
You are an evidence-grounded resume evaluation system.

Your task is to determine whether a candidate's resume provides
evidence for specific job requirements.

You must evaluate only the requirements provided to you.

Do not invent additional requirements.

Do not assume that the candidate has a skill, qualification,
credential, license, or experience unless it is supported by the
resume.

Every evidence item must be copied verbatim from the resume.

Do not paraphrase evidence.

A related skill does not automatically satisfy a requirement.

Evaluate each requirement independently.
"""


MATCHING_PROMPT = """
Evaluate the resume against each job requirement.

For every requirement, assign exactly one status:

matched:
The resume contains clear evidence that the candidate satisfies the
requirement.

partial:
The resume contains relevant evidence, but the requirement is only
partially satisfied.

Examples:
- The job requires 5 years of experience but the resume supports 2 years.
- The candidate has related experience but not the full requested scope.

missing:
The resume does not contain sufficient evidence for the requirement.

EVIDENCE RULES

- Evidence must be copied verbatim from the resume.
- Do not paraphrase evidence.
- Do not invent evidence.
- matched and partial assessments must include at least one evidence item.
- missing assessments must have an empty evidence list.
- Only use information present in the resume.
- Do not infer experience from education alone unless the requirement
  specifically concerns education.
- Do not infer one tool or skill from another related tool or skill.
- Evaluate every requirement exactly once.
- Preserve the provided requirement_id exactly.

JOB REQUIREMENTS
----------------
{requirements}

RESUME
------
{resume_text}
"""


def _generate_assessments(
    model_name: str,
    prompt: str,
) -> RequirementAssessmentBatch:

    client = _get_client()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RequirementAssessmentBatch,
            temperature=0.0,
        ),
    )

    if not response.text:
        raise RequirementMatchingError(
            "Gemini returned an empty matching response."
        )

    return RequirementAssessmentBatch.model_validate_json(
        response.text
    )


def _normalize_text(
    text: str,
) -> str:

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _evidence_exists_in_resume(
    evidence: str,
    resume_text: str,
) -> bool:

    normalized_evidence = _normalize_text(
        evidence
    )

    normalized_resume = _normalize_text(
        resume_text
    )

    if not normalized_evidence:
        return False

    return (
        normalized_evidence
        in normalized_resume
    )


def _build_validated_matches(
    requirements: List[JobRequirement],
    assessment_batch: RequirementAssessmentBatch,
    resume_text: str,
) -> List[RequirementMatch]:

    requirement_map = {
        requirement.requirement_id: requirement
        for requirement in requirements
    }

    assessments_by_id = {}

    for assessment in assessment_batch.assessments:

        if assessment.requirement_id not in requirement_map:
            raise RequirementMatchingError(
                "Gemini returned an unknown requirement ID: "
                f"{assessment.requirement_id}"
            )

        if assessment.requirement_id in assessments_by_id:
            raise RequirementMatchingError(
                "Gemini returned a duplicate requirement ID: "
                f"{assessment.requirement_id}"
            )

        assessments_by_id[
            assessment.requirement_id
        ] = assessment

    expected_ids = set(
        requirement_map.keys()
    )

    returned_ids = set(
        assessments_by_id.keys()
    )

    if expected_ids != returned_ids:
        missing_ids = (
            expected_ids - returned_ids
        )

        unexpected_ids = (
            returned_ids - expected_ids
        )

        raise RequirementMatchingError(
            "Gemini did not return the expected requirement set. "
            f"Missing IDs: {sorted(missing_ids)}. "
            f"Unexpected IDs: {sorted(unexpected_ids)}."
        )

    validated_matches = []

    for requirement in requirements:

        assessment = assessments_by_id[
            requirement.requirement_id
        ]

        valid_evidence = [
            evidence
            for evidence in assessment.evidence
            if _evidence_exists_in_resume(
                evidence,
                resume_text,
            )
        ]

        status = assessment.status
        rationale = assessment.rationale

        if status == "missing":
            valid_evidence = []

        elif not valid_evidence:
            status = "missing"

            rationale = (
                "The model did not provide verifiable evidence "
                "from the resume for this requirement."
            )

        validated_matches.append(
            RequirementMatch(
                requirement_id=(
                    requirement.requirement_id
                ),
                requirement=(
                    requirement.requirement
                ),
                category=(
                    requirement.category
                ),
                importance=(
                    requirement.importance
                ),
                status=status,
                evidence=valid_evidence,
                rationale=rationale,
            )
        )

    return validated_matches


def match_resume_to_requirements(
    resume_text: str,
    requirements: List[JobRequirement],
    observability: Optional[
        ObservabilityCollector
    ] = None,
) -> RequirementMatchingResult:

    if not resume_text.strip():
        raise ValueError(
            "Resume text cannot be empty."
        )

    if not requirements:
        raise ValueError(
            "At least one job requirement is required."
        )

    requirements_json = json.dumps(
        [
            requirement.model_dump()
            for requirement in requirements
        ],
        indent=2,
        ensure_ascii=False,
    )

    prompt = MATCHING_PROMPT.format(
        requirements=requirements_json,
        resume_text=resume_text,
    )

    primary_model = os.getenv(
        "GEMINI_PRIMARY_MODEL"
    )

    fallback_model = os.getenv(
        "GEMINI_FALLBACK_MODEL"
    )

    if not primary_model:
        raise RuntimeError(
            "GEMINI_PRIMARY_MODEL is not configured."
        )

    try:
        assessment_batch = run_observed_call(
            observability,
            stage="evidence_matching",
            prompt_version=PROMPT_VERSION,
            model=primary_model,
            is_fallback=False,
            call=lambda: _generate_assessments(
                primary_model,
                prompt,
            ),
        )

    except errors.APIError as error:

        if error.code not in {
            429,
            500,
            502,
            503,
            504,
        }:
            raise RequirementMatchingError(
                f"Gemini request failed: {error}"
            ) from error

        if not fallback_model:
            raise RequirementMatchingUnavailableError(
                "Primary Gemini model is unavailable and "
                "no fallback model is configured."
            ) from error

        try:
            assessment_batch = run_observed_call(
                observability,
                stage="evidence_matching",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_assessments(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise RequirementMatchingUnavailableError(
                "Both Gemini models are currently unavailable."
            ) from fallback_error

    except httpx.HTTPError as error:

        if not fallback_model:
            raise RequirementMatchingUnavailableError(
                "Gemini is currently unavailable."
            ) from error

        try:
            assessment_batch = run_observed_call(
                observability,
                stage="evidence_matching",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_assessments(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise RequirementMatchingUnavailableError(
                "Both Gemini models are currently unavailable."
            ) from fallback_error

    matches = _build_validated_matches(
        requirements=requirements,
        assessment_batch=assessment_batch,
        resume_text=resume_text,
    )

    return RequirementMatchingResult(
        matches=matches,
        suggestions=[],
    )