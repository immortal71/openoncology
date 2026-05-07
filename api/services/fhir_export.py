"""FHIR R4 export — HL7 FHIR R4 DiagnosticReport and Observation resources.

Enables EMR integration (Epic, Cerner, OpenEMR) and is required for US clinical
use under the 21st Century Cures Act (ONC Final Rule, §170.315(g)(10)).

Resources generated:
  DiagnosticReport  — /api/fhir/DiagnosticReport/{submission_id}
  Observation       — /api/fhir/Observation/{mutation_id}

FHIR R4 spec: https://hl7.org/fhir/R4/

Coding systems used:
  - LOINC 55233-1 — Genetic analysis master panel
  - LOINC 48018-6 — Gene studied [ID]
  - LOINC 48004-6 — DNA change type
  - LOINC 53037-8 — Genetic disease sequence variation interpretation
  - SNOMED CT     — Cancer disorder codes
  - HGNC          — Human Gene Nomenclature Committee gene IDs
"""

from __future__ import annotations

from datetime import datetime, UTC


def build_diagnostic_report(
    submission: object,
    result: object,
    mutations: list[object],
    patient_id_fhir: str,
) -> dict:
    """Build a FHIR R4 DiagnosticReport resource for a genomic analysis submission.

    Args:
        submission:      SQLAlchemy Submission ORM instance.
        result:          SQLAlchemy Result ORM instance (may be None).
        mutations:       List of SQLAlchemy Mutation ORM instances.
        patient_id_fhir: FHIR Patient resource reference string.

    Returns:
        FHIR R4 DiagnosticReport resource as a Python dict (JSON-serialisable).
    """
    issued = (
        getattr(submission, "completed_at", None)
        or getattr(submission, "submitted_at", None)
        or datetime.now(UTC)
    )
    if hasattr(issued, "isoformat"):
        issued_str = issued.isoformat() + "Z"
    else:
        issued_str = str(issued)

    status = _map_status(getattr(submission, "status", "unknown"))

    observation_refs = [
        {"reference": f"Observation/mutation-{m.id}"}
        for m in mutations
    ]

    has_targetable = getattr(result, "has_targetable_mutation", False) if result else False
    interpretation_text = (
        getattr(result, "summary_text", None)
        or getattr(result, "plain_language_summary", None)
        or "Genomic analysis complete."
    ) if result else "Genomic analysis complete."

    report: dict = {
        "resourceType": "DiagnosticReport",
        "id": f"diagnostic-report-{getattr(submission, 'id', 'unknown')}",
        "meta": {
            "profile": ["http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomics-report"],
        },
        "status": status,
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "GE",
                        "display": "Genetics",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "55233-1",
                    "display": "Genetic analysis master panel",
                }
            ],
            "text": "Somatic Genomic Analysis",
        },
        "subject": {"reference": patient_id_fhir},
        "issued": issued_str,
        "result": observation_refs,
        "conclusion": interpretation_text,
        "conclusionCode": [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "LA6671-7" if has_targetable else "LA6675-8",
                        "display": "Pathogenic" if has_targetable else "Benign/Likely benign",
                    }
                ]
            }
        ],
        "extension": [
            {
                "url": "http://openoncology.org/fhir/StructureDefinition/cancer-type",
                "valueString": getattr(submission, "cancer_type", "Unknown"),
            },
            {
                "url": "http://openoncology.org/fhir/StructureDefinition/targetable-mutation",
                "valueBoolean": has_targetable,
            },
        ],
    }

    # Attach report PDF reference if available
    if result and getattr(result, "report_pdf_s3_key", None):
        report["presentedForm"] = [
            {
                "contentType": "application/pdf",
                "title": "Oncologist Report",
                "url": f"/api/results/{getattr(submission, 'id', '')}/oncologist-report.pdf",
            }
        ]

    return report


def build_observation(mutation: object) -> dict:
    """Build a FHIR R4 Observation resource for a single somatic mutation.

    Uses the HL7 Genomics Reporting IG (v2.0) Variant profile:
    https://hl7.org/fhir/uv/genomics-reporting/

    Args:
        mutation: SQLAlchemy Mutation ORM instance.

    Returns:
        FHIR R4 Observation resource as a Python dict.
    """
    gene = getattr(mutation, "gene", "UNKNOWN")
    hgvs = getattr(mutation, "hgvs_notation", None) or ""
    classification = str(getattr(mutation, "classification", "uncertain"))
    oncokb_level = str(getattr(mutation, "oncokb_level", "unknown"))
    alphamissense = getattr(mutation, "alphamissense_score", None)
    is_targetable = getattr(mutation, "is_targetable", False)
    chromosome = getattr(mutation, "chromosome", None)
    position = getattr(mutation, "position", None)
    ref_allele = getattr(mutation, "ref_allele", None)
    alt_allele = getattr(mutation, "alt_allele", None)
    mutation_id = getattr(mutation, "id", "unknown")
    submission_id = getattr(mutation, "submission_id", "unknown")

    interpretation_code, interpretation_display = _interpretation_coding(classification, oncokb_level)

    components = [
        {
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "48018-6", "display": "Gene studied [ID]"}],
            },
            "valueCodeableConcept": {
                "coding": [{"system": "https://www.genenames.org", "display": gene}],
                "text": gene,
            },
        },
    ]

    if hgvs:
        components.append({
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "81290-9", "display": "Genomic DNA change (gHGVS)"}],
            },
            "valueCodeableConcept": {"text": hgvs},
        })

    if chromosome and position:
        components.append({
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "81254-5", "display": "Variant exact start-end"}],
            },
            "valueRange": {
                "low": {"value": position, "system": "http://loinc.org"},
                "high": {"value": position, "system": "http://loinc.org"},
            },
            "extension": [
                {"url": "http://loinc.org/chromosome", "valueString": chromosome}
            ],
        })

    if ref_allele:
        components.append({
            "code": {"coding": [{"system": "http://loinc.org", "code": "69547-8", "display": "Ref nucleotide"}]},
            "valueString": ref_allele,
        })

    if alt_allele:
        components.append({
            "code": {"coding": [{"system": "http://loinc.org", "code": "69551-0", "display": "Alt allele"}]},
            "valueString": alt_allele,
        })

    if alphamissense is not None:
        components.append({
            "code": {
                "coding": [
                    {"system": "http://openoncology.org/fhir/CodeSystem/scores", "code": "alphamissense-score",
                     "display": "AlphaMissense pathogenicity score"}
                ],
            },
            "valueQuantity": {"value": round(alphamissense, 4), "unit": "score"},
        })

    components.append({
        "code": {
            "coding": [
                {"system": "http://openoncology.org/fhir/CodeSystem/oncokb", "code": "oncokb-level",
                 "display": "OncoKB Actionability Level"}
            ],
        },
        "valueString": oncokb_level,
    })

    if is_targetable:
        components.append({
            "code": {
                "coding": [
                    {"system": "http://openoncology.org/fhir/CodeSystem/targetability", "code": "targetable",
                     "display": "Therapeutically targetable"}
                ],
            },
            "valueBoolean": True,
        })

    created_at = getattr(mutation, "created_at", None)
    effective_dt = created_at.isoformat() + "Z" if created_at and hasattr(created_at, "isoformat") else None

    obs: dict = {
        "resourceType": "Observation",
        "id": f"mutation-{mutation_id}",
        "meta": {
            "profile": ["http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/variant"],
        },
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "69548-6",
                    "display": "Genetic variant assessment",
                }
            ],
            "text": f"{gene} variant",
        },
        "derivedFrom": [{"reference": f"DiagnosticReport/diagnostic-report-{submission_id}"}],
        "interpretation": [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": interpretation_code,
                        "display": interpretation_display,
                    }
                ],
                "text": interpretation_display,
            }
        ],
        "component": components,
    }

    if effective_dt:
        obs["effectiveDateTime"] = effective_dt

    return obs


# ── Helpers ────────────────────────────────────────────────────────────────────

def _map_status(submission_status: str) -> str:
    """Map OpenOncology submission status to FHIR DiagnosticReport.status."""
    mapping = {
        "queued": "registered",
        "processing": "partial",
        "awaiting_ai": "partial",
        "complete": "final",
        "failed": "cancelled",
    }
    return mapping.get(str(submission_status).lower(), "unknown")


def _interpretation_coding(classification: str, oncokb_level: str) -> tuple[str, str]:
    """Return (LOINC code, display) for clinical interpretation."""
    cl = classification.lower()
    if cl in ("pathogenic", "likely_pathogenic") or oncokb_level in ("1", "2", "3A"):
        return "LA6671-7", "Pathogenic"
    if cl == "likely_benign":
        return "LA6675-8", "Likely benign"
    if cl == "benign":
        return "LA6675-8", "Benign"
    return "LA6682-4", "Uncertain significance"
