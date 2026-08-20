"""Failure modes of the generative patient-summary path.

risk_analysis.md section 3 listed the LLM summary as an unanalysed generative
component. Open action 7. Each class below is one failure mode, and each mode
has both a case that must be caught and a case that must NOT be, because a
guard that rejects everything is as useless as one that rejects nothing and
would silently disable the path it protects.

The last class is the one that matters most: rejected text must never reach a
caller, because a patient cannot un-read a sentence.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from services.llm_output_guard import validate_patient_summary  # noqa: E402

_CLEAN = (
    "Your tumour sample showed a change in the EGFR gene. Our system found "
    "that osimertinib is an existing medicine that targets this change. Your "
    "oncologist will decide whether it is right for you."
)


class TestCleanTextPasses:
    def test_ordinary_summary_is_accepted(self):
        v = validate_patient_summary(
            _CLEAN, allowed_drugs=["osimertinib"], allowed_genes=["EGFR"]
        )
        assert v.ok, v.violations

    def test_no_allowed_list_skips_the_drug_check(self):
        v = validate_patient_summary("A complete sentence about your results.")
        assert v.ok, v.violations

    def test_ordinary_medical_words_are_not_read_as_drugs(self):
        text = (
            "The laboratory reviewed your biopsy and the treatment options "
            "were discussed with the oncologist."
        )
        v = validate_patient_summary(text, allowed_drugs=[], allowed_genes=[])
        assert v.ok, v.violations


class TestFabricatedDrug:
    def test_invented_drug_name_is_caught(self):
        text = _CLEAN + " We also suggest pembrolizumab for this case."
        v = validate_patient_summary(
            text, allowed_drugs=["osimertinib"], allowed_genes=["EGFR"]
        )
        assert not v.ok
        assert any("not in candidate list" in x for x in v.violations)

    def test_the_actual_candidate_is_not_flagged(self):
        v = validate_patient_summary(
            _CLEAN, allowed_drugs=["osimertinib"], allowed_genes=["EGFR"]
        )
        assert not any("not in candidate list" in x for x in v.violations)

    def test_matching_ignores_case_and_punctuation(self):
        text = "Treatment with Osimertinib may be considered by your doctor."
        v = validate_patient_summary(text, allowed_drugs=["osimertinib"])
        assert v.ok, v.violations


class TestUnwarrantedCertainty:
    @pytest.mark.parametrize(
        "claim",
        [
            "This drug will cure your cancer.",
            "Treatment is guaranteed to work for you.",
            "This medicine is 100% effective.",
            "There is no risk with this treatment.",
        ],
    )
    def test_certainty_claims_are_caught(self, claim):
        v = validate_patient_summary(claim, allowed_drugs=[])
        assert not v.ok
        assert any("certainty" in x for x in v.violations)

    def test_hedged_language_is_allowed(self):
        text = "This medicine may help, and your oncologist will decide."
        v = validate_patient_summary(text, allowed_drugs=[])
        assert v.ok, v.violations


class TestPrognosis:
    @pytest.mark.parametrize(
        "claim",
        [
            "Your life expectancy is about two years.",
            "The survival rate for this is low.",
            "You have six months to live.",
            "Your prognosis is poor.",
        ],
    )
    def test_outcome_claims_are_caught(self, claim):
        v = validate_patient_summary(claim, allowed_drugs=[])
        assert not v.ok
        assert any("prognosis" in x for x in v.violations)

    def test_describing_the_finding_is_not_a_prognosis(self):
        text = "Your sample showed a change that some medicines can target."
        v = validate_patient_summary(text, allowed_drugs=[])
        assert v.ok, v.violations


class TestInstructionToAct:
    @pytest.mark.parametrize(
        "claim",
        [
            "You should start osimertinib right away.",
            "Stop taking your current medication.",
            "We recommend you stop chemotherapy.",
        ],
    )
    def test_treatment_instructions_are_caught(self, claim):
        v = validate_patient_summary(claim, allowed_drugs=["osimertinib"])
        assert not v.ok
        assert any("instruction" in x for x in v.violations)

    def test_deferring_to_the_oncologist_is_allowed(self):
        text = "Your oncologist will decide whether this medicine is right for you."
        v = validate_patient_summary(text, allowed_drugs=[])
        assert v.ok, v.violations


class TestTruncation:
    def test_text_ending_mid_sentence_is_caught(self):
        v = validate_patient_summary("Your results show that this drug is not")
        assert not v.ok
        assert any("truncated" in x for x in v.violations)

    def test_completed_sentence_passes(self):
        v = validate_patient_summary("Your results are ready.")
        assert v.ok, v.violations

    def test_empty_text_is_rejected(self):
        assert not validate_patient_summary("").ok
        assert not validate_patient_summary("   ").ok


class TestRejectedTextNeverReachesTheCaller:
    """The guard is only worth anything if a failing verdict changes the output."""

    def _run(self, generated, monkeypatch):
        import services.llm_explainer as le

        monkeypatch.setattr(
            "config.settings.openai_api_key", "test-key", raising=False
        )

        async def _fake(*a, **k):
            return generated

        monkeypatch.setattr(le, "_openai_summary", _fake)
        return asyncio.run(
            le.generate_plain_language_summary(
                gene="EGFR",
                has_target=True,
                cancer_type="Lung adenocarcinoma",
                mutations_summary=[{"gene": "EGFR"}],
                top_drug="osimertinib",
            )
        )

    def test_clean_generated_text_is_returned(self, monkeypatch):
        assert self._run(_CLEAN, monkeypatch) == _CLEAN

    def test_prognosis_claim_falls_back_to_template(self, monkeypatch):
        bad = "You have six months to live and this drug will cure you."
        out = self._run(bad, monkeypatch)
        assert out != bad
        assert "months to live" not in out

    def test_fabricated_drug_falls_back_to_template(self, monkeypatch):
        bad = _CLEAN + " Start pembrolizumab immediately."
        out = self._run(bad, monkeypatch)
        assert "pembrolizumab" not in out

    def test_truncated_text_falls_back_to_template(self, monkeypatch):
        out = self._run("Your results show that this drug is not", monkeypatch)
        assert out.rstrip().endswith((".", "!", "?"))
