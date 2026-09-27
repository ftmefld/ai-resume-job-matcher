from app.services.matcher_pipeline import (
    analyze_resume_v2,
)


job_description = """
Registered Nurse

Candidates must hold an active RN license.

At least five years of acute-care nursing experience is required.

BLS certification is required.

ICU experience is preferred.

Experience with Epic electronic health records is a plus.
"""


resume_text = """
Registered Nurse with active RN license.

Two years of clinical nursing experience in acute care.

BLS certified.

Experienced with patient monitoring, medication administration,
and clinical documentation.
"""


result = analyze_resume_v2(
    resume_text=resume_text,
    job_description=job_description,
)


print(
    result.model_dump_json(
        indent=2
    )
)