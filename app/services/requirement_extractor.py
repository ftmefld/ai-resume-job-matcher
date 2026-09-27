import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from app.services.matching_models import (
    JobRequirement,
    JobRequirementExtraction,
    assign_requirement_ids,
)
from app.services.observability import (
    ObservabilityCollector,
    run_observed_call,
)


load_dotenv()


PROMPT_VERSION = "req-extract-v3"


class RequirementExtractionError(Exception):
    pass


class RequirementExtractionUnavailableError(Exception):
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
You are a conservative structured job-requirement extraction system.

Your task is to extract candidate screening requirements from a job
description.

You must work across all industries and professions.

A candidate screening requirement is something the employer uses to
describe what a candidate should already possess, know, have experienced,
be qualified for, or be able to do.

IMPORTANT:
Do NOT extract every sentence describing the job.

Job descriptions frequently contain:
- routine job duties
- team structure
- company information
- benefits
- schedules
- travel expectations
- workplace conditions
- general collaboration statements
- descriptions of what the employee will do after being hired

These are NOT automatically candidate requirements.

Extract a responsibility only when the job description clearly presents
the ability or prior experience as something expected from the candidate.

For example:

"Candidates should have experience managing digital campaigns."

is a candidate requirement.

But:

"The employee will attend weekly marketing meetings."

is only a job duty and should NOT be extracted.

Do not infer qualifications that are not explicitly supported by the job
description.

Do not add requirements simply because they are common in the profession.

Every extracted requirement must have direct textual support in
source_text.

When uncertain whether something is a true candidate screening
requirement or merely a job description detail, DO NOT extract it.
"""


REQUIREMENT_EXTRACTION_PROMPT = """
Extract the candidate screening requirements from the job description.

Be conservative.

The goal is NOT to summarize the job description.

The goal is to identify qualifications, experience, knowledge,
credentials, skills, tools, and clearly stated candidate capabilities
that could reasonably be checked against a resume.

==================================================
STEP 1 — DECIDE WHETHER TO EXTRACT
==================================================

Before extracting an item, ask:

"Could I reasonably compare this statement against information in a
candidate's resume?"

Extract it only if the answer is yes.

Good candidate requirements include:

- required or preferred education
- licenses
- certifications
- years or types of experience
- technical or professional skills
- named tools or platforms
- domain knowledge
- language proficiency
- clearly stated candidate capabilities
- responsibilities for which the employer explicitly asks the candidate
  to have experience or ability


Do NOT extract an item merely because it appears in the job description.

Do NOT extract:

- company descriptions
- salary or compensation
- benefits
- work culture
- equal opportunity language
- generic descriptions of the team
- general statements about collaboration
- routine future duties with no candidate qualification attached
- schedule information
- weekend or holiday requirements
- hybrid or remote arrangements
- travel statements
- reporting relationships
- descriptions of what the company provides
- statements that describe the position rather than a candidate
  qualification


Example:

"The engineer will review pull requests and document services."

Do NOT automatically extract these as candidate requirements.


But:

"Candidates should have experience reviewing production code."

IS a candidate requirement.


==================================================
STEP 2 — ONE REQUIREMENT PER CONCEPT
==================================================

Each extracted requirement must represent one meaningful candidate
criterion.

Do not create multiple requirements from the same underlying criterion.

Example:

"Strong experience with Docker containers"

should normally produce ONE requirement, not:

- Docker
- containers
- Docker experience
- containerization experience


Preserve alternatives.

Example:

"Experience with PyTorch or TensorFlow is required"

should remain one alternative requirement rather than two mandatory
requirements.


Preserve combined qualifications when the alternatives matter.

Example:

"Master's degree or equivalent professional experience"

must not become:

"Master's degree required"

because equivalent experience is also allowed.


==================================================
STEP 3 — IMPORTANCE
==================================================

Use exactly one of:

must_have
important
preferred


must_have:
Use only when mandatory language is explicit.

Examples:

- required
- must
- mandatory
- candidates must
- applicants must
- minimum requirement
- required to


Example:

"At least three years of experience is required."

→ must_have


important:
Use when the employer clearly expects the qualification but does not
make it mandatory.

Examples:

- should have
- should understand
- important
- expected to
- comfortable with
- strong knowledge
- demonstrated ability


Example:

"Candidates should have at least three years of experience."

→ important

The phrase "at least three years" does NOT by itself make the requirement
mandatory.


preferred:
Use when the employer explicitly marks the requirement as lower priority.

Examples:

- preferred
- a plus
- nice to have
- desired
- advantageous
- helpful but not required


When uncertain between must_have and important, choose important.

Never determine importance from your own opinion about how valuable the
requirement is.


==================================================
STEP 4 — CATEGORY
==================================================

Use exactly one of:

experience
education
license
certification
skill
tool
domain_knowledge
language
responsibility
other


Use this decision order.


1. EDUCATION

Use education for formal academic qualifications.

Examples:

- Bachelor's degree
- Master's degree
- PhD
- degree in Civil Engineering


2. LICENSE

Use license for legal or professional authorization to practice or
perform regulated work.

Examples:

- RN license
- pharmacist license
- PE license
- driver's license


3. CERTIFICATION

Use certification for formal professional credentials that are not
practice licenses.

Examples:

- BLS
- ACLS
- PMP
- AWS certification
- EIT certification
- Six Sigma Green Belt


4. LANGUAGE

Use language for natural-language proficiency.

Examples:

- fluent English
- Spanish proficiency


5. TOOL

Use tool when the requirement centers on a named software product,
framework, application, platform, system, development technology,
equipment, or operational technology.

Examples:

- Docker
- FastAPI
- Kubernetes
- AutoCAD
- SolidWorks
- Excel
- Salesforce
- Google Analytics
- REDCap
- Epic
- MLflow
- Minitab
- Tableau

"Experience with Docker"
is still categorized as tool because Docker is the main concept.

Do not classify something as experience merely because the phrase
contains the word "experience."


6. EXPERIENCE

Use experience when the central concept is prior professional exposure,
duration, or work in a specific environment.

Examples:

- 5 years of accounting experience
- ICU experience
- public accounting experience
- manufacturing engineering experience
- clinical research experience

If a number of years or a professional environment is the primary
qualification, experience is usually appropriate.


7. DOMAIN_KNOWLEDGE

Use domain_knowledge for knowledge of regulations, standards,
professional frameworks, bodies of knowledge, or subject-matter rules.

Examples:

- U.S. GAAP
- NEC
- ISO 13485
- HIPAA
- GCP
- building codes
- employment law
- NPDES requirements


8. RESPONSIBILITY

Use responsibility only when the requirement concerns the candidate's
ability or prior experience performing a concrete professional activity.

Examples:

- managing digital campaigns
- obtaining informed consent
- preparing SEC filings
- developing home-exercise programs
- leading CAPA investigations

Do NOT use responsibility simply because the job description says the
employee will perform an activity.

The activity must be presented as a candidate expectation.


9. SKILL

Use skill for a practical ability that is not better represented by a
named tool, credential, experience requirement, or domain standard.

Examples:

- Python programming
- SQL querying
- SEO
- statistical analysis
- financial modeling
- communication
- negotiation
- data analysis
- project management
- root-cause analysis

Programming languages such as Python, Java, and SQL should normally be
skill when the employer is asking for programming ability.

A named framework or software product such as FastAPI, Docker, Tableau,
or Salesforce should normally be tool.


10. OTHER

Use other only when none of the above categories reasonably apply.


==================================================
STEP 5 — PRESERVE THE EMPLOYER'S MEANING
==================================================

Preserve:

- numerical thresholds
- required years of experience
- degree alternatives
- credential status such as active/current
- proficiency levels
- alternative technologies
- required professional environments


Example:

"At least four years of accounting experience"

must not become:

"Accounting experience"


Example:

"PyTorch or TensorFlow"

must not become two separate mandatory requirements.


Example:

"Master's degree or equivalent professional experience"

must preserve both pathways.


==================================================
STEP 6 — SOURCE GROUNDING
==================================================

Every requirement must contain source_text.

source_text must be a short span copied directly from the job
description that supports the requirement.

The extracted requirement must not contain stronger claims than its
source_text.


==================================================
FINAL CONSERVATIVE CHECK
==================================================

Before returning each requirement, ask:

1. Is this something I could check against a resume?

2. Is it explicitly supported by the job description?

3. Is it truly a candidate requirement rather than merely a future job
   duty?

4. Did I accidentally duplicate another requirement?

5. Did I preserve alternatives and numerical constraints?

6. Did I preserve the employer's actual importance language?

7. Did I choose the category based on the central concept?

8. If the concept is a named software/platform/framework/equipment,
   should it be tool?

9. If the concept is years or type of prior work, should it be
   experience?

10. If the concept is a regulation or professional standard, should it
    be domain_knowledge?

If there is meaningful doubt that an item is a candidate screening
requirement, omit it.

Return an empty requirements list if no meaningful candidate screening
requirements are present.


==================================================
JOB DESCRIPTION
==================================================

{job_description}
"""

def _generate_extraction(
    model_name: str,
    prompt: str,
) -> JobRequirementExtraction:

    client = _get_client()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=JobRequirementExtraction,
            temperature=0.0,
        ),
    )

    if not response.text:
        raise RequirementExtractionError(
            "Gemini returned an empty requirement extraction."
        )

    return JobRequirementExtraction.model_validate_json(
        response.text
    )


def extract_job_requirements(
    job_description: str,
    observability: Optional[
        ObservabilityCollector
    ] = None,
) -> list[JobRequirement]:

    if not job_description.strip():
        raise ValueError(
            "Job description cannot be empty."
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

    prompt = REQUIREMENT_EXTRACTION_PROMPT.format(
        job_description=job_description
    )

    try:
        extraction = run_observed_call(
            observability,
            stage="requirement_extraction",
            prompt_version=PROMPT_VERSION,
            model=primary_model,
            is_fallback=False,
            call=lambda: _generate_extraction(
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
            raise RequirementExtractionError(
                f"Gemini request failed: {error}"
            ) from error

        if not fallback_model:
            raise RequirementExtractionUnavailableError(
                "Primary Gemini model is unavailable and "
                "no fallback model is configured."
            ) from error

        try:
            extraction = run_observed_call(
                observability,
                stage="requirement_extraction",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_extraction(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise RequirementExtractionUnavailableError(
                "Both Gemini models are currently unavailable."
            ) from fallback_error

    except httpx.HTTPError as error:

        if not fallback_model:
            raise RequirementExtractionUnavailableError(
                "Gemini is currently unavailable."
            ) from error

        try:
            extraction = run_observed_call(
                observability,
                stage="requirement_extraction",
                prompt_version=PROMPT_VERSION,
                model=fallback_model,
                is_fallback=True,
                call=lambda: _generate_extraction(
                    fallback_model,
                    prompt,
                ),
            )

        except (
            errors.APIError,
            httpx.HTTPError,
        ) as fallback_error:

            raise RequirementExtractionUnavailableError(
                "Both Gemini models are currently unavailable."
            ) from fallback_error

    return assign_requirement_ids(
        extraction
    )