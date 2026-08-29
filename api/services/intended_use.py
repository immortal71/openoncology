"""
The intended-use statement, declared once.

Every output this system produces is research output. `docs/REGULATORY_FRAMEWORK.md`
section 3 lists the clinical validation gates and none of them is met, so no
result here has been shown to be fit to inform a treatment decision. That is a
property of every response, not of one section inside some of them, and this
module exists so it can only be written down in one place.

It was not one place before. `patient_summary.DISCLAIMER` carried it for the
patient letter, `oncologist_report.ONCOLOGIST_DISCLAIMER` for the clinician
report, `pdf_export` had its own strings, and the results API had none of its
own: the only disclaimer in that payload was nested inside `patient_summary`,
which is generated inside a `try` and set to None when it fails. A caller
reading `plain_language_summary` after that failure got drug names, an
actionability flag and per-mutation OncoKB levels with nothing anywhere in the
response saying what the system is.

The FHIR export carried nothing at all, which is the path that matters most:
it exists to be ingested by an EMR, where a DiagnosticReport is indistinguishable
from one a validated laboratory produced.
"""

# Machine-readable, stable. Consumers should branch on this rather than parse
# prose. If a clinical validation ever changes the answer, it changes here.
INTENDED_USE = "research"

RESEARCH_USE_STATEMENT = (
    "FOR RESEARCH USE ONLY. Not for use in diagnostic or treatment procedures. "
    "This output was produced by software that has not been cleared or approved "
    "by the FDA or any other regulator, and has not been validated against "
    "patient outcomes."
)

# Said separately from the sentence above because it is a different claim, and
# the one a reader is most likely to assume the other way round.
NO_CLINICIAN_REVIEW_STATEMENT = (
    "No clinician has reviewed this output unless it is explicitly marked as "
    "reviewed."
)

# Where the limits are written out in full. Kept as a bare path rather than a
# URL because the document travels with the repository, not with a website.
REFERENCE_DOCUMENT = "docs/REGULATORY_FRAMEWORK.md"

# FHIR has no standard code for "produced by software that is not clinically
# validated". The nearest vocabularies all mean something else: HTEST is test
# data rather than real patient data, and the research purpose-of-use codes
# describe why data is being accessed, not how it was produced. So the marker
# is a tag under this project's own namespace, and the guarantee that a human
# sees it is the conclusion text, which is the field EMRs actually render.
FHIR_TAG_SYSTEM = "http://openoncology.org/fhir/CodeSystem/intended-use"
FHIR_EXTENSION_URL = "http://openoncology.org/fhir/StructureDefinition/intended-use"


def intended_use_payload(clinician_reviewed: bool = False) -> dict:
    """The block every API response carries, whatever else it does or does not
    manage to generate."""
    return {
        "intended_use": INTENDED_USE,
        "clinical_use_approved": False,
        "regulator_cleared": False,
        "clinician_reviewed": bool(clinician_reviewed),
        "statement": RESEARCH_USE_STATEMENT,
        "clinician_review_statement": NO_CLINICIAN_REVIEW_STATEMENT,
        "reference": REFERENCE_DOCUMENT,
    }


def fhir_meta(clinician_reviewed: bool = False) -> dict:
    """`meta.tag` entries marking a FHIR resource as research output."""
    tags = [
        {
            "system": FHIR_TAG_SYSTEM,
            "code": INTENDED_USE,
            "display": "Research use only. Not for diagnostic or treatment use.",
        }
    ]
    if not clinician_reviewed:
        tags.append(
            {
                "system": FHIR_TAG_SYSTEM,
                "code": "unreviewed",
                "display": "No clinician has reviewed this report.",
            }
        )
    return tags


def prefix_conclusion(conclusion: str, clinician_reviewed: bool = False) -> str:
    """
    Put the statement in front of the interpretation rather than after it.

    A trailing disclaimer is the one a truncating renderer drops, and EMR
    summary views truncate.
    """
    parts = [RESEARCH_USE_STATEMENT]
    if not clinician_reviewed:
        parts.append(NO_CLINICIAN_REVIEW_STATEMENT)
    parts.append((conclusion or "").strip())
    return "\n\n".join(p for p in parts if p)
