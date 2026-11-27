"""
The FHIR export codes variant interpretations with LOINC answers. Each code
must be the LOINC answer whose own display matches the display we send, from
LL4034-6, the answer list for "Genetic variation clinical significance".
"""
from __future__ import annotations

import pytest

from services.fhir_export import build_diagnostic_report, build_observation

# LL4034-6 answers, as listed at https://loinc.org/LL4034-6
LL4034_6 = {
    "LA6668-3": "Pathogenic",
    "LA26332-9": "Likely pathogenic",
    "LA26333-7": "Uncertain significance",
    "LA26334-5": "Likely benign",
    "LA6675-8": "Benign",
}


class _Mutation:
    id = "mut-1"
    submission_id = "sub-1"
    gene = "EGFR"
    hgvs_notation = "p.L858R"
    classification = "pathogenic"
    oncokb_level = "unknown"
    is_targetable = False
    alphamissense_score = None
    chromosome = "7"
    position = 55191822
    ref_allele = "T"
    alt_allele = "G"
    created_at = None


class _Submission:
    id = "sub-1"
    cancer_type = "Lung adenocarcinoma"
    status = "complete"


class _Result:
    has_targetable_mutation = True
    summary_text = "EGFR L858R detected."
    oncologist_reviewed = False


@pytest.mark.parametrize(
    "classification,display",
    [
        ("pathogenic", "Pathogenic"),
        ("likely_benign", "Likely benign"),
        ("benign", "Benign"),
        ("uncertain", "Uncertain significance"),
    ],
)
def test_interpretation_code_matches_its_display(classification, display):
    mutation = _Mutation()
    mutation.classification = classification
    coding = build_observation(mutation)["interpretation"][0]["coding"][0]
    assert coding["display"] == display
    assert LL4034_6.get(coding["code"]) == display, coding


def test_targetable_report_conclusion_is_coded_pathogenic():
    report = build_diagnostic_report(
        submission=_Submission(),
        result=_Result(),
        mutations=[_Mutation()],
        patient_id_fhir="Patient/p-1",
    )
    coding = report["conclusionCode"][0]["coding"][0]
    assert coding["display"] == "Pathogenic"
    assert LL4034_6.get(coding["code"]) == "Pathogenic", coding
