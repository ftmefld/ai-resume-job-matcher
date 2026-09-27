import json
import os
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from app.services.matching_models import (
    RequirementMatch,
    SuggestionBatch,
)
from app.services.observability import (
    ObservabilityCollector,
    run_observed_call,
)


load_dotenv()


PROMPT_VERSION = "suggestion-v1"


class SuggestionGenerationError(Exception):
    pass


class SuggestionGenerationUnavailableError(Exception):
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
You are a career improvement assistant.

Your task is to generate practical recommendations based only on
identified gaps between a resume and a job description.

You must work across all professions and industries.

Never suggest that a candidate fabricate experience, skills,
education, licenses, certifications, achievements, or credentials.

Distinguish between:
- improving how existing experience is presented
- genuinely gaining missing experience, skills, education, or credentials

Recommendations must be specific to the identified job gaps.
"""


SUGGESTION_PROMPT = """
Generate practical recommendations for the candidate based on the
requirement assessments below.

Focus only on requirements with status "partial" or "missing".

RULES

- Return 3 to 5 suggestions when meaningful gaps exist.
- Do not give generic advice such as "improve your resume".
- Do not recommend adding a qualification unless the resume actually
  supports it.
- If relevant experience may already exist but is not clearly described,
  recommend clarifying or highlighting it.
- If a qualification is genuinely missing, recommend gaining it rather
  than pretending to have it.
- Prioritize must-have gaps over important gaps.
- Prioritize important gaps over preferred gaps.
- Keep each suggestion concise and actionable.
- Do not mention requirements that are already fully matched.

REQUIREMENT ASSESSMENTS
-----------------------
{gap_data}

RESUME
------
{resume_text}
"""


def _generate_suggestions(
    model_name: str,
    prompt: str,
) -> SuggestionBatch:

    client = _get_client()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SuggestionBatch,
            temperature=0.2,
        ),
    )

    if not response.text:
        raise SuggestionGenerationError(
            "Gemini returned an empty suggestion response."
        )

    return SuggestionBatch.model_validate_json(
        response.text
    )


def generate_gap_suggestions(
    resume_text: str,
    matches: List[RequirementMatch],
    observability: Optional[
        ObservabilityCollector
    ] = None,
) -> List[str]:

    gaps = [
        match
        for match in matches
        if match.status in {
            "partial",
            "missing",
        }
    ]

    if not gaps:
        return []

    gap_data = json.dumps(
        [
            {
                "requirement_id": gap.requirement_id,
                "requirement": gap.requirement,
                "category": gap.category,
                "importance": gap.importance,
                "status": gap.status,
                "evidence": gap.evidence,
                "rationale": gap.rationale,
            }
            for gap in gaps
        ],
        indent=2,
        ensure_ascii=False,
    )

    prompt = SUGGESTION_PROMPT.format(
        gap_data=gap_data,
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
        result = run_observed_call(
            observability,
            stage="suggestion_generation",
            prompt_version=PROMPT_VERSION,
            model=primary_model,
            is_fallback=False,
            call=lambda: _generate_suggestions(
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
            raise SuggestionGenerationError(
                f"Gemini request failed: {error}"
            ) from error

        if not fallback_model:
            raise SuggestionGenerationUnavailableError(
                "Suggestion generation is currently unavailable."
            ) from error

        try:
            result = run_observed_call(
                observability,
                stage="suggestion_generation",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_suggestions(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise SuggestionGenerationUnavailableError(
                "Both Gemini models are unavailable "
                "for suggestion generation."
            ) from fallback_error

    except httpx.HTTPError as error:

        if not fallback_model:
            raise SuggestionGenerationUnavailableError(
                "Suggestion generation is currently unavailable."
            ) from error

        try:
            result = run_observed_call(
                observability,
                stage="suggestion_generation",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_suggestions(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise SuggestionGenerationUnavailableError(
                "Both Gemini models are unavailable "
                "for suggestion generation."
            ) from fallback_error

    return result.suggestions


def build_fallback_suggestions(
    matches: List[RequirementMatch],
) -> List[str]:

    gaps = [
        match
        for match in matches
        if match.status in {
            "partial",
            "missing",
        }
    ]

    priority = {
        "must_have": 0,
        "important": 1,
        "preferred": 2,
    }

    gaps = sorted(
        gaps,
        key=lambda item: priority[
            item.importance
        ],
    )

    suggestions = []

    for gap in gaps[:3]:

        if gap.status == "partial":
            suggestions.append(
                (
                    "Strengthen or clarify the resume evidence for "
                    f"'{gap.requirement}' if additional relevant "
                    "experience is available."
                )
            )

        else:
            suggestions.append(
                (
                    "Consider gaining verifiable experience, training, "
                    "or credentials relevant to "
                    f"'{gap.requirement}', where appropriate."
                )
            )

    return suggestions