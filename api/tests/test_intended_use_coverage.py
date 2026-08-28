"""
Every output path has to say what this system is.

`docs/REGULATORY_FRAMEWORK.md` section 3 lists the clinical validation gates and
none is met, so nothing here has been shown fit to inform a treatment decision.
That was written down in the documentation and enforced almost nowhere.

Two gaps these tests close.

The results payload carried no statement of its own. The only disclaimer in it
was nested inside `patient_summary`, which is built inside a `try` and set to
None when generation fails. That failure path exists, is logged, and reports
itself in `generation_errors`, and after it the response still returns
`summary`, `plain_language_summary`, `has_targetable_mutation`, `target_gene`
and per-mutation OncoKB levels. A disclaimer that disappears exactly when
generation goes wrong is not a control.

The FHIR export carried nothing at all, and it is the path that matters most,
because it exists to be ingested by an EMR where a DiagnosticReport looks like
one a validated laboratory produced. It also reported `status: final`, which in
FHIR R4 means complete and verified. The only thing verified was that the
pipeline finished.
"""
from __future__ import annotations

import pytest

from services.fhir_export import build_diagnostic_report, build_observation, _map_status
from services.intended_use import (
    INTENDED_USE,
    RESEARCH_USE_STATEMENT,
    intended_use_payload,
)


class _Submission:
    id = "sub-1"
    cancer_type = "Lung adenocarcinoma"
    status = "complete"
    completed_at = None
    submitted_at = None
    sample_qc = None


class _Result:
    has_targetable_mutation = True
    target_gene = "EGFR"
    summary_text = "EGFR L858R detected."
    plain_language_summary = "A change was found in the EGFR gene."
    report_pdf_s3_key = None
    oncologist_reviewed = False
    ranked_candidates = []
    evidence_provenance = None
    algorithm_version = "v1"
    oncologist_notes = None
    cbioportal_data = None
    cosmic_sample_count = None


class _Mutation:
    id = "mut-1"
    submission_id = "sub-1"
    gene = "EGFR"
    hgvs_notation = "p.L858R"
    mutation_type = "missense"
    classification = "pathogenic"
    oncokb_level = "1"
    is_targetable = True
    alphamissense_score = 0.9
    chromosome = "7"
    position = 55191822
    ref_allele = "T"
    alt_allele = "G"
    created_at = None
    allele_fraction = None


def _report(reviewed: bool = False) -> dict:
    result = _Result()
    result.oncologist_reviewed = reviewed
    return build_diagnostic_report(
        submission=_Submission(),
        result=result,
        mutations=[_Mutation()],
        patient_id_fhir="Patient/p-1",
    )


# ── The statement itself ─────────────────────────────────────────────────────

def test_intended_use_is_research_and_says_so():
    payload = intended_use_payload()
    assert payload["intended_use"] == "research"
    assert payload["clinical_use_approved"] is False
    assert payload["regulator_cleared"] is False
    assert "RESEARCH USE ONLY" in payload["statement"]


def test_review_flag_is_reported_and_defaults_to_unreviewed():
    assert intended_use_payload()["clinician_reviewed"] is False
    assert intended_use_payload(clinician_reviewed=True)["clinician_reviewed"] is True


# ── FHIR DiagnosticReport ────────────────────────────────────────────────────

def test_diagnostic_report_is_tagged_as_research_output():
    tags = _report()["meta"]["tag"]
    assert any(t["code"] == INTENDED_USE for t in tags)


def test_diagnostic_report_conclusion_leads_with_the_statement():
    """
    Leading rather than trailing: EMR summary views truncate, and a trailing
    disclaimer is the part that gets cut.
    """
    conclusion = _report()["conclusion"]
    assert conclusion.startswith(RESEARCH_USE_STATEMENT)
    assert "EGFR L858R detected." in conclusion


def test_diagnostic_report_carries_the_intended_use_extension():
    urls = [e["url"] for e in _report()["extension"]]
    assert "http://openoncology.org/fhir/StructureDefinition/intended-use" in urls


def test_unreviewed_report_is_preliminary_not_final():
    """
    FHIR R4 `final` means complete and verified. Nothing verified this. A
    completed pipeline run is not a clinician's sign-off, and status is the one
    field an ingesting system cannot ignore.
    """
    assert _report(reviewed=False)["status"] == "preliminary"


def test_reviewed_report_becomes_final():
    assert _report(reviewed=True)["status"] == "final"


def test_unreviewed_report_is_tagged_unreviewed():
    codes = [t["code"] for t in _report(reviewed=False)["meta"]["tag"]]
    assert "unreviewed" in codes
    assert "unreviewed" not in [t["code"] for t in _report(reviewed=True)["meta"]["tag"]]


@pytest.mark.parametrize(
    "submission_status,expected",
    [
        ("queued", "registered"),
        ("processing", "partial"),
        ("awaiting_ai", "partial"),
        ("failed", "cancelled"),
        ("nonsense", "unknown"),
    ],
)
def test_other_statuses_are_unchanged(submission_status, expected):
    """Only the completed case was over-claiming; the rest keep their mapping."""
    assert _map_status(submission_status) == expected
    assert _map_status(submission_status, True) == expected


# ── FHIR Observation ─────────────────────────────────────────────────────────

def test_observation_carries_the_marker_on_its_own():
    """
    Observations are individually addressable at /api/fhir/Observation/{id} and
    leave the bundle alone, so inheriting the report's tag is not enough.
    """
    obs = build_observation(_Mutation())
    assert any(t["code"] == INTENDED_USE for t in obs["meta"]["tag"])


def test_unreviewed_observation_is_preliminary():
    assert build_observation(_Mutation())["status"] == "preliminary"
    assert build_observation(_Mutation(), clinician_reviewed=True)["status"] == "final"


# ── The results API ──────────────────────────────────────────────────────────

async def test_results_response_carries_intended_use(client, seeded_submission):
    """
    The payload states it unconditionally, at the top level, rather than
    nesting it in a section that is allowed to fail.
    """
    resp = await client.get(f"/api/results/{seeded_submission.id}")
    assert resp.status_code == 200

    body = resp.json()
    assert body["intended_use"]["intended_use"] == "research"
    assert body["intended_use"]["clinical_use_approved"] is False
    assert "RESEARCH USE ONLY" in body["intended_use"]["statement"]


async def test_intended_use_survives_a_failed_patient_summary(
    client, seeded_submission, monkeypatch
):
    """
    The case the old placement could not handle. When the section carrying the
    disclaimer fails to generate, the response still returns drug and
    actionability content, so the statement has to outlive it.
    """
    def _boom(*_args, **_kwargs):
        raise RuntimeError("patient summary generation failed")

    monkeypatch.setattr("services.patient_summary.generate_patient_summary", _boom)

    resp = await client.get(f"/api/results/{seeded_submission.id}")
    assert resp.status_code == 200

    body = resp.json()
    assert body["patient_summary"] is None
    assert "patient_summary" in body["generation_errors"]
    assert body["intended_use"]["intended_use"] == "research"
    assert "RESEARCH USE ONLY" in body["intended_use"]["statement"]
