from app.services.requirement_extractor import (
    extract_job_requirements,
)


job_description = """
Registered Nurse

Candidates must hold an active RN license.

At least two years of acute-care nursing experience is required.

The nurse will monitor patients, administer medications, coordinate
with physicians, and maintain accurate clinical documentation.

BLS certification is required.

ICU experience is preferred.

Experience with Epic electronic health records is a plus.
"""


requirements = extract_job_requirements(
    job_description
)


for requirement in requirements:
    print()
    print(
        requirement.requirement_id,
        requirement.requirement,
    )
    print(
        "Category:",
        requirement.category,
    )
    print(
        "Importance:",
        requirement.importance,
    )
    print(
        "Source:",
        requirement.source_text,
    )