from app.services.matching_models import (
    ExtractedRequirement,
    JobRequirementExtraction,
)

import app.services.requirement_extractor as extractor_module


def fake_extraction(
    model_name,
    prompt,
):
    return JobRequirementExtraction(
        job_title="Registered Nurse",
        requirements=[
            ExtractedRequirement(
                requirement="Active RN license",
                category="license",
                importance="must_have",
                source_text=(
                    "Candidates must hold an active RN license."
                ),
            ),
            ExtractedRequirement(
                requirement="2 years of clinical experience",
                category="experience",
                importance="important",
                source_text=(
                    "Two years of clinical experience is expected."
                ),
            ),
            ExtractedRequirement(
                requirement="ICU experience",
                category="experience",
                importance="preferred",
                source_text=(
                    "ICU experience is preferred."
                ),
            ),
        ],
    )


def test_extract_job_requirements(
    monkeypatch,
):
    monkeypatch.setattr(
        extractor_module,
        "_generate_extraction",
        fake_extraction,
    )

    requirements = (
        extractor_module.extract_job_requirements(
            """
            Candidates must hold an active RN license.
            Two years of clinical experience is expected.
            ICU experience is preferred.
            """
        )
    )

    assert len(requirements) == 3

    assert requirements[0].requirement_id == "R001"
    assert requirements[1].requirement_id == "R002"
    assert requirements[2].requirement_id == "R003"

    assert requirements[0].category == "license"

    assert (
        requirements[0].importance
        == "must_have"
    )

    assert (
        requirements[2].importance
        == "preferred"
    )


def test_empty_job_description_rejected():
    try:
        extractor_module.extract_job_requirements(
            "   "
        )

        assert False

    except ValueError as error:
        assert str(error) == (
            "Job description cannot be empty."
        )