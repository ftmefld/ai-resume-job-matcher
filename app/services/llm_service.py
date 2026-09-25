import logging
import os
from typing import List
import httpx

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field


load_dotenv()

logger = logging.getLogger(__name__)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

SYSTEM_INSTRUCTION = """
You are an experienced recruiter and resume evaluator who can assess
candidates across a wide range of industries and professions.

Your task is to evaluate how well a candidate's resume matches a specific
job description using only evidence contained in the resume and the job
description.

You must adapt your evaluation criteria to the profession and role being
evaluated.

For example, depending on the job, relevant criteria may include:
- professional or domain-specific skills
- relevant work experience
- responsibilities and achievements
- tools, software, equipment, or methodologies
- education
- licenses and certifications
- research or publications
- portfolio or project experience
- leadership or management experience
- communication or interpersonal skills
- language requirements
- regulatory or professional requirements
- other qualifications explicitly mentioned in the job description

Do not assume a candidate has a qualification, skill, certification,
license, or experience unless it is supported by the resume.

Do not infer skills merely because the candidate has a related skill.

Do not reward keyword repetition.

Distinguish carefully between:
- required qualifications
- preferred qualifications
- responsibilities
- general descriptive language

Ignore personal characteristics that should not affect job matching,
such as age, gender, race, ethnicity, religion, marital status,
or other protected characteristics.

Base the evaluation only on job-relevant evidence.
"""

ANALYSIS_PROMPT_TEMPLATE = """
Evaluate how well the candidate's resume matches the provided job
description.

First, identify the qualifications and expectations that are actually
present in the job description.

Consider the following categories only when they are relevant to the
specific job:

1. Required qualifications
   Examples may include mandatory skills, licenses, certifications,
   education, years of experience, language requirements, or other
   explicitly required qualifications.

2. Relevant experience and responsibilities
   Evaluate whether the candidate has performed work, projects, research,
   or responsibilities similar to those described in the job.

3. Domain-specific skills and knowledge
   Evaluate professional, technical, clinical, scientific, business,
   creative, operational, or other role-specific skills required by
   the position.

4. Tools, methods, technologies, or equipment
   Consider these only when they are relevant to the profession and
   explicitly mentioned or strongly implied by the job description.

5. Education, certifications, licenses, or professional credentials
   Evaluate these according to how important they are for this specific
   position.

6. Preferred qualifications
   These should improve the candidate's match but should generally have
   less influence than explicitly required qualifications.

7. Other job-relevant requirements
   Consider any other meaningful requirements that do not fit the
   categories above.

SCORING PRINCIPLES

- Base the score primarily on the requirements stated in the job
  description.
- Required qualifications should have more influence than preferred
  qualifications.
- Missing an explicitly mandatory requirement should significantly
  reduce the score.
- Do not penalize the candidate for skills or qualifications that are
  not requested by the employer.
- Do not award credit for qualifications that are not supported by
  evidence in the resume.
- A related skill does not automatically count as the requested skill.
- Relevant accomplishments and demonstrated experience are stronger
  evidence than keyword mentions alone.

Interpret the final match score approximately as:

90-100:
The resume provides strong evidence for nearly all major requirements.

75-89:
The candidate is a strong match but has some meaningful gaps.

60-74:
The candidate has relevant qualifications but several requirements are
missing or weakly supported.

40-59:
The candidate partially matches the role but important requirements
are missing.

0-39:
The resume provides limited evidence for many of the role's core
requirements.

MATCHED REQUIREMENTS

Include important job-relevant skills, qualifications, credentials,
or experiences that are supported by both the job description and
the resume.

MISSING REQUIREMENTS

Include important job requirements that are absent or not sufficiently
supported by the resume.

Do not list irrelevant or optional requirements as major missing requirements.

SUGGESTIONS

Provide 3 to 5 practical and specific suggestions.

Suggestions may recommend:
- making existing relevant experience more visible
- adding measurable achievements
- clarifying relevant responsibilities
- highlighting existing certifications or projects
- gaining genuinely missing requirements or qualifications

Never suggest that the candidate fabricate experience, education,
skills, licenses, certifications, or achievements.

RESUME
-------
{resume_text}

JOB DESCRIPTION
---------------
{job_description}
"""


class ResumeAnalysis(BaseModel):
    match_score: float = Field(
        ge=0,
        le=100,
    )

    matched_requirements: List[str] = Field(
        description=(
            "Important job requirements, qualifications, skills, "
            "credentials, or experiences that are supported by the resume."
        )
    )

    missing_requirements: List[str] = Field(
        description=(
            "Important job requirements that are absent or not "
            "sufficiently supported by the resume."
        )
    )

    suggestions: List[str] = Field(
        description=(
            "Specific and realistic suggestions for improving the "
            "candidate's fit or resume presentation."
        )
    )


class LLMUnavailableError(Exception):
    """Raised when the LLM service is temporarily unavailable."""
    pass


class LLMRequestError(Exception):
    """Raised when the LLM request cannot be completed."""
    pass


def generate_analysis(
    model_name: str,
    prompt: str,
) -> ResumeAnalysis:

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ResumeAnalysis,
            temperature=0.1,
        ),
    )

    if not response.text:
        raise LLMRequestError(
            "Gemini returned an empty response."
        )

    return ResumeAnalysis.model_validate_json(
        response.text
    )

def analyze_resume_with_llm(
    resume_text: str,
    job_description: str
) -> dict:

    primary_model = os.getenv(
        "GEMINI_PRIMARY_MODEL",
        "gemini-3.5-flash"
    )

    fallback_model = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.5-flash-lite"
    )

    force_primary_failure = (
        os.getenv(
            "FORCE_PRIMARY_FAILURE",
            "false"
        ).lower() == "true"
    )

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
    resume_text=resume_text,
    job_description=job_description,
)

    # --------------------------------------------------
    # Primary model
    # --------------------------------------------------

    if not force_primary_failure:
        try:
            logger.info(
                "Calling primary Gemini model: %s",
                primary_model,
            )

            result = generate_analysis(
                model_name=primary_model,
                prompt=prompt,
            )

            return result.model_dump()

        except errors.APIError as error:
            logger.warning(
                "Primary Gemini API error. "
                "Model=%s Code=%s Message=%s",
                primary_model,
                error.code,
                error.message,
            )

            # Errors that may be temporary
            if error.code not in {
                429,
                500,
                502,
                503,
                504,
            }:
                raise LLMRequestError(
                    f"Gemini request failed: {error.message}"
                ) from error

        except httpx.HTTPError as error:
            logger.warning(
                "Network error while calling primary Gemini model: %s",
                str(error),
            )

    else:
        logger.warning(
            "Primary Gemini model skipped for testing."
        )

    # --------------------------------------------------
    # Fallback model
    # --------------------------------------------------

    try:
        logger.info(
            "Calling fallback Gemini model: %s",
            fallback_model,
        )

        result = generate_analysis(
            model_name=fallback_model,
            prompt=prompt,
        )

        return result.model_dump()

    except errors.APIError as error:
        logger.error(
            "Fallback Gemini API error. "
            "Model=%s Code=%s Message=%s",
            fallback_model,
            error.code,
            error.message,
        )

        raise LLMUnavailableError(
            "AI analysis service is temporarily unavailable."
        ) from error

    except httpx.HTTPError as error:
        logger.error(
            "Network error while calling fallback Gemini model: %s",
            str(error),
        )

        raise LLMUnavailableError(
            "AI analysis service is temporarily unavailable."
        ) from error

    except Exception as error:
        logger.exception(
            "Unexpected error while generating AI analysis."
        )

        raise LLMRequestError(
            "Unexpected error while generating the analysis."
        ) from error