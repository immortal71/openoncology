"""CIViC may fill gaps in the actionability table. It may not outrank OncoKB.

OncoKB's public dumps need a token this deployment may not have, and without one
the table is the undated built-in set of ~335 entries. That mattered less when
the ranker scored a broad repurposing pool. It matters more now that
`candidate_pool_policy` defaults to `evidence_first`, because the table decides
what is recommended wherever it has an answer.

`data/civic_evidence.tsv` is a CIViC bulk export already in this repository,
used only for live per-variant lookups and never loaded into the table. Loading
its level A/B predictive evidence adds 298 gene-alteration keys across 149
genes, an expansion of roughly 89%.

Three properties make that safe rather than reckless, and each is pinned here:

  1. OncoKB always wins. CIViC is merged as the base layer, so it can only fill
     keys nothing else answers.
  2. Everything CIViC contributes is capped at LEVEL_3B, whatever CIViC's own
     rating. A CIViC A is not an FDA approval, and the OncoKB level carries the
     single largest weight in the ranker, so an entry claiming LEVEL_1 would
     outrank genuine standard-of-care evidence.
  3. Only Predictive evidence with a Supports direction at level A or B is
     admitted. Loading C, D or E as actionable would inflate what the system
     claims relative to what it knows.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _API_DIR.parent
for _p in (str(_API_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import services.oncokb_evidence as ev  # noqa: E402

_HEADER = (
    "molecular_profile\tevidence_type\tevidence_direction\tevidence_level\t"
    "therapies\n"
)


def _tsv(tmp_path: Path, rows: list[str], name: str = "civic.tsv") -> Path:
    path = tmp_path / name
    path.write_text(_HEADER + "".join(rows), encoding="utf-8")
    return path


def _row(profile, etype="Predictive", direction="Supports", level="A", therapies="drugx"):
    return f"{profile}\t{etype}\t{direction}\t{level}\t{therapies}\n"


class TestOnlyAdmissibleEvidenceIsLoaded:
    def test_level_a_and_b_are_admitted(self, tmp_path):
        path = _tsv(tmp_path, [_row("EGFR L858R", level="A"), _row("BRAF V600E", level="B")])
        table = ev._load_civic_supplement(path)
        assert len(table) == 2

    @pytest.mark.parametrize("level", ["C", "D", "E"])
    def test_weaker_evidence_is_refused(self, tmp_path, level):
        path = _tsv(tmp_path, [_row("EGFR L858R", level=level)])
        assert ev._load_civic_supplement(path) == {}

    def test_non_predictive_evidence_is_refused(self, tmp_path):
        path = _tsv(tmp_path, [_row("EGFR L858R", etype="Prognostic")])
        assert ev._load_civic_supplement(path) == {}

    def test_evidence_that_does_not_support_is_refused(self, tmp_path):
        path = _tsv(tmp_path, [_row("EGFR L858R", direction="Does Not Support")])
        assert ev._load_civic_supplement(path) == {}

    def test_multiple_therapies_split(self, tmp_path):
        path = _tsv(tmp_path, [_row("EGFR L858R", therapies="drugx, drugy; drugz")])
        table = ev._load_civic_supplement(path)
        assert len(next(iter(table.values()))) == 3

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert ev._load_civic_supplement(tmp_path / "absent.tsv") == {}


class TestEverythingIsCapped:
    def test_level_a_is_capped_at_3b(self, tmp_path):
        path = _tsv(tmp_path, [_row("EGFR L858R", level="A")])
        table = ev._load_civic_supplement(path)
        assert set(next(iter(table.values())).values()) == {"LEVEL_3B"}

    def test_no_civic_entry_can_claim_level_1(self, tmp_path):
        path = _tsv(
            tmp_path,
            [_row("EGFR L858R", level="A"), _row("BRAF V600E", level="B")],
        )
        table = ev._load_civic_supplement(path)
        levels = {lvl for drugs in table.values() for lvl in drugs.values()}
        assert "LEVEL_1" not in levels
        assert "LEVEL_2" not in levels


class TestOncoKBWins:
    """The merge order is the whole safety argument."""

    def test_existing_entries_are_not_overridden(self):
        base = {("EGFR", "L858R"): {"osimertinib": "LEVEL_1"}}
        supplement = {("EGFR", "L858R"): {"osimertinib": "LEVEL_3B"}}
        merged = ev._merge_level_tables(supplement, base)
        assert merged[("EGFR", "L858R")]["osimertinib"] == "LEVEL_1"

    def test_supplement_fills_keys_nothing_else_answers(self):
        base = {("EGFR", "L858R"): {"osimertinib": "LEVEL_1"}}
        supplement = {("RARE1", "V1M"): {"drugx": "LEVEL_3B"}}
        merged = ev._merge_level_tables(supplement, base)
        assert merged[("RARE1", "V1M")]["drugx"] == "LEVEL_3B"
        assert merged[("EGFR", "L858R")]["osimertinib"] == "LEVEL_1"

    def test_a_new_drug_on_an_existing_key_is_added_not_promoted(self):
        base = {("EGFR", "L858R"): {"osimertinib": "LEVEL_1"}}
        supplement = {("EGFR", "L858R"): {"someother": "LEVEL_3B"}}
        merged = ev._merge_level_tables(supplement, base)
        assert merged[("EGFR", "L858R")] == {
            "osimertinib": "LEVEL_1",
            "someother": "LEVEL_3B",
        }


class TestDisabledByDefault:
    def test_setting_defaults_to_off(self):
        from config import Settings

        assert Settings().civic_supplement_enabled is False

    def test_apply_is_a_no_op_when_disabled(self, monkeypatch):
        monkeypatch.setattr(
            "config.settings.civic_supplement_enabled", False, raising=False
        )
        before = dict(ev._LEVEL_TABLE)
        ev._apply_civic_supplement()
        assert len(ev._LEVEL_TABLE) == len(before)
