"""A dump that exists and parses to nothing must not look like no dump at all.

`api/static/oncokb_actionable_variants_cache.txt` held 253 rows of real OncoKB
data and parsed to zero entries for as long as it has been in the repository.
`csv.DictReader(..., delimiter="\\t")` was reading the whole header as one
column, because the file has no tab characters: its columns are aligned with
runs of eight spaces, which is what a hand download from the dataAccess page
produces. That route is the documented workaround for the 401 the public dump
returns without a token, so the format the workaround produces is the one the
parser could not read.

Nothing reported it. An unparseable cache and an absent cache both returned an
empty table, and the service logged only that the dump was unreachable, which
was true and beside the point.

Two behaviours are pinned here.

  1. Both layouts parse, tabs and whitespace alignment, and a byte-order mark
     does not corrupt the first column.
  2. A stale cache beats the built-in table. A cache past its freshness window
     is still a dated OncoKB dump; the built-in table has no date at all.
     Preferring the undated one was the wrong way round. The provenance says
     `stale_cache` and `is_current` stays False, because being dated is not the
     same as being current.
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

TAB = chr(9)
NL = chr(10)

_COLS = ["Gene", "Alteration", "Cancer Type", "Level", "Drug(s)", "Drug Abstracts"]
_ROWS = [
    ["ABL1", "BCR-ABL1 Fusion", "Chronic Myelogenous Leukemia", "LEVEL_1", "Imatinib", ""],
    ["EGFR", "L858R", "Non-Small Cell Lung Cancer", "LEVEL_1", "Osimertinib", ""],
]


def _tabbed() -> str:
    return "\n".join("\t".join(r) for r in [_COLS] + _ROWS) + "\n"


def _spaced(width: int = 8) -> str:
    sep = " " * width
    return "\n".join(sep.join(r).rstrip() for r in [_COLS] + _ROWS) + "\n"


class TestBothLayoutsParse:
    def test_tab_separated(self):
        table = ev._parse_oncokb_public_dump_tsv(_tabbed())
        assert ("EGFR", "L858R") in table

    def test_whitespace_aligned(self):
        """The layout a hand download actually produces."""
        table = ev._parse_oncokb_public_dump_tsv(_spaced())
        assert ("EGFR", "L858R") in table
        assert table[("EGFR", "L858R")] == {"osimertinib": "LEVEL_1"}

    def test_both_layouts_agree(self):
        assert ev._parse_oncokb_public_dump_tsv(_tabbed()) == (
            ev._parse_oncokb_public_dump_tsv(_spaced())
        )

    def test_single_spaces_inside_a_field_survive(self):
        """Splitting on one space would break 'BCR-ABL1 Fusion'."""
        table = ev._parse_oncokb_public_dump_tsv(_spaced())
        assert ("ABL1", "BCRABL1FUSION") in table

    def test_byte_order_mark_does_not_corrupt_the_first_column(self):
        assert ("EGFR", "L858R") in ev._parse_oncokb_public_dump_tsv("﻿" + _spaced())

    def test_empty_input_is_not_an_error(self):
        assert ev._parse_oncokb_public_dump_tsv("") == {}
        assert ev._parse_oncokb_public_dump_tsv("   \n\n") == {}

    def test_a_header_with_one_column_yields_nothing(self):
        assert ev._parse_oncokb_public_dump_tsv("JustOneColumn\nvalue\n") == {}


class TestTheRealCacheFileParses:
    """The regression that started this: the shipped cache read as empty."""

    def test_shipped_cache_yields_entries(self):
        path = ev.get_oncokb_cache_path()
        if not path.exists():
            pytest.skip("no cache file in this checkout")
        table = ev._load_public_table_from_cache(path)
        assert table, "the committed OncoKB cache must not parse to zero entries"

    def test_shipped_cache_covers_many_genes(self):
        """A cache worth preferring has to carry real breadth.

        This cannot compare against `_LEVEL_TABLE`: the module merges the cache
        into it at import, so by the time a test runs every cache key is
        trivially present. Asserting breadth directly is what is left, and it
        is what matters, since a cache with a handful of rows would not be
        worth preferring over the built-in table.
        """
        path = ev.get_oncokb_cache_path()
        if not path.exists():
            pytest.skip("no cache file in this checkout")
        table = ev._load_public_table_from_cache(path)
        assert len(table) >= 50, f"only {len(table)} entries parsed"
        assert len({gene for gene, _alt in table}) >= 25


class TestCrossCancerConflicts:
    """The dump is per cancer type; this table is not. Not all splits are equal.

    Two rows for the same gene, alteration and drug can mean opposite things or
    merely differ in strength, and treating those the same is wrong in both
    directions. Dropping every disagreement discards real actionability;
    resolving every disagreement can turn a sensitising drug into a resistance
    marker. Of the ten conflicts in the shipped dump, two are contradictions
    and eight are strength differences.
    """

    def test_sensitising_against_resistant_is_unresolvable(self):
        """BRAF V600E vemurafenib: LEVEL_1 in melanoma, LEVEL_R1 in colorectal."""
        assert ev._reconcile_cross_cancer_levels("LEVEL_1", "LEVEL_R1") is None
        assert ev._reconcile_cross_cancer_levels("LEVEL_R1", "LEVEL_1") is None

    def test_two_sensitising_levels_keep_the_weaker(self):
        """Both say the drug works. The weaker claim is the safe one to keep."""
        assert ev._reconcile_cross_cancer_levels("LEVEL_1", "LEVEL_2") == "LEVEL_2"
        assert ev._reconcile_cross_cancer_levels("LEVEL_2", "LEVEL_1") == "LEVEL_2"
        assert ev._reconcile_cross_cancer_levels("LEVEL_1", "LEVEL_3B") == "LEVEL_3B"

    def test_two_resistance_levels_keep_the_stronger_warning(self):
        assert ev._reconcile_cross_cancer_levels("LEVEL_R1", "LEVEL_R2") == "LEVEL_R1"
        assert ev._reconcile_cross_cancer_levels("LEVEL_R2", "LEVEL_R1") == "LEVEL_R1"

    def test_unparseable_levels_are_refused(self):
        assert ev._reconcile_cross_cancer_levels("LEVEL_1", "nonsense") is None

    @staticmethod
    def _dump(*rows: tuple[str, str, str, str, str]) -> str:
        header = ("Gene", "Alteration", "Cancer Type", "Level", "Drug(s)")
        lines = [TAB.join(header)] + [TAB.join(r) for r in rows]
        return NL.join(lines) + NL

    def test_a_contradiction_drops_the_drug_from_the_dump_table(self):
        text = self._dump(
            ("BRAF", "V600E", "Melanoma", "LEVEL_1", "Vemurafenib"),
            ("BRAF", "V600E", "Colorectal Cancer", "LEVEL_R1", "Vemurafenib"),
        )
        table = ev._parse_oncokb_public_dump_tsv(text)
        assert "vemurafenib" not in table.get(("BRAF", "V600E"), {})

    def test_a_strength_split_keeps_the_weaker_level(self):
        text = self._dump(
            ("ERBB2", "Amplification", "Breast Cancer", "LEVEL_1", "Trastuzumab"),
            ("ERBB2", "Amplification", "Gastric Cancer", "LEVEL_2", "Trastuzumab"),
        )
        table = ev._parse_oncokb_public_dump_tsv(text)
        assert table[("ERBB2", "AMPLIFICATION")]["trastuzumab"] == "LEVEL_2"

    def test_a_key_left_empty_by_conflicts_is_removed(self):
        text = self._dump(
            ("BRAF", "V600E", "Melanoma", "LEVEL_1", "Vemurafenib"),
            ("BRAF", "V600E", "Colorectal Cancer", "LEVEL_R1", "Vemurafenib"),
        )
        assert ("BRAF", "V600E") not in ev._parse_oncokb_public_dump_tsv(text)


class TestInvestigationalTiersAreNotAdmitted:
    """The dump may supply approved evidence and resistance, nothing else.

    The clinical gate caught this one. TP53 R248W is a negative control with no
    approved therapy, and the shipped dump carries

        TP53  R248W  Any Solid Tumor  LEVEL_3A  APR-246

    which is factually correct: OncoKB does list APR-246 there. But LEVEL_3A is
    compelling evidence for an agent that is not approved, and an actionability
    table presents it with the same weight as standard of care, so a
    discontinued investigational drug reached a patient's top three as a
    high-confidence recommendation.

    Investigational options belong to the repurposing tier, which carries phase
    and approval status alongside them. This costs three drug pairs out of 218.

    Resistance is admitted on purpose: it is a safety floor, never a
    recommendation (risk_analysis.md F1).
    """

    @staticmethod
    def _dump(*rows):
        header = ("Gene", "Alteration", "Cancer Type", "Level", "Drug(s)")
        return NL.join([TAB.join(header)] + [TAB.join(r) for r in rows]) + NL

    def test_level_3a_is_refused(self):
        text = self._dump(
            ("TP53", "R248W", "Any Solid Tumor", "LEVEL_3A", "APR-246")
        )
        assert ev._parse_oncokb_public_dump_tsv(text) == {}

    @pytest.mark.parametrize("level", ["LEVEL_3A", "LEVEL_3B", "LEVEL_4"])
    def test_every_investigational_tier_is_refused(self, level):
        text = self._dump(("GENEX", "V1M", "Any Solid Tumor", level, "drugx"))
        assert ev._parse_oncokb_public_dump_tsv(text) == {}

    @pytest.mark.parametrize("level", ["LEVEL_1", "LEVEL_2"])
    def test_approved_tiers_are_admitted(self, level):
        text = self._dump(("EGFR", "L858R", "NSCLC", level, "Osimertinib"))
        assert ev._parse_oncokb_public_dump_tsv(text)[("EGFR", "L858R")] == {
            "osimertinib": level
        }

    @pytest.mark.parametrize("level", ["LEVEL_R1", "LEVEL_R2"])
    def test_resistance_is_admitted_as_a_safety_floor(self, level):
        text = self._dump(("EGFR", "T790M", "NSCLC", level, "Gefitinib"))
        assert ev._parse_oncokb_public_dump_tsv(text)[("EGFR", "T790M")] == {
            "gefitinib": level
        }

    def test_the_shipped_dump_yields_no_investigational_levels(self):
        path = ev.get_oncokb_cache_path()
        if not path.exists():
            pytest.skip("no cache file in this checkout")
        table = ev._load_public_table_from_cache(path)
        levels = {lv for drugs in table.values() for lv in drugs.values()}
        assert not (levels - ev._DUMP_ADMISSIBLE_LEVELS), (
            f"inadmissible levels reached the table: "
            f"{sorted(levels - ev._DUMP_ADMISSIBLE_LEVELS)}"
        )

    def test_tp53_r248w_has_no_table_answer(self):
        """The exact negative control the gate scores."""
        assert ev.lookup_oncokb_level("TP53", "R248W", "APR-246") is None


class TestCuratedEvidenceWins:
    """A cancer-blind dump must not overwrite a cancer-aware curated entry.

    The curated table resolves cancer context through
    _apply_cancer_context_override. This projection of the dump has no cancer
    dimension at all, so merging it on top would let a LEVEL_2 drawn from some
    other cancer replace a curated LEVEL_1. The dump fills gaps; it does not
    overrule.
    """

    def test_curated_level_survives_the_merge(self):
        assert ev.lookup_oncokb_level("ERBB2", "Amplification", "trastuzumab") == "LEVEL_1"

    def test_a_contradicted_drug_still_answers_from_the_curated_table(self):
        assert ev.lookup_oncokb_level("BRAF", "V600E", "vemurafenib") == "LEVEL_1"

    def test_merge_order_puts_the_dump_underneath(self):
        curated = {("EGFR", "L858R"): {"osimertinib": "LEVEL_1"}}
        dump = {("EGFR", "L858R"): {"osimertinib": "LEVEL_2"},
                ("RARE", "V1M"): {"drugx": "LEVEL_3B"}}
        merged = ev._merge_level_tables(dump, curated)
        assert merged[("EGFR", "L858R")]["osimertinib"] == "LEVEL_1"
        assert merged[("RARE", "V1M")]["drugx"] == "LEVEL_3B"


class TestPrecedenceIsUniformAcrossPaths:
    """Cache age must not decide which evidence wins.

    Briefly it did: a stale cache merged underneath the curated table while a
    fresh one merged on top, so the same dump produced different
    recommendations depending on the age of a file. Currency and cancer context
    are different properties and only the second is at stake in the merge, so
    every path now merges the dump underneath.

    These read the source rather than running the loaders, because reaching the
    fresh_cache and download branches needs a reachable dump and an OncoKB
    token, and neither is available here. Checking the call shape is what is
    possible; leaving the branches unpinned is not.
    """

    @staticmethod
    def _source() -> str:
        return (_API_DIR / "services" / "oncokb_evidence.py").read_text(
            encoding="utf-8"
        )

    def test_no_path_merges_the_dump_on_top(self):
        src = self._source()
        assert "_merge_level_tables(_LEVEL_TABLE, " not in src, (
            "a dump merged on top of the curated table can overwrite a "
            "cancer-aware level with a cancer-blind one"
        )

    def test_every_merge_puts_the_curated_table_second(self):
        import re

        calls = re.findall(r"_merge_level_tables\(([^,]+), ([^)]+)\)", self._source())
        calls = [c for c in calls if "base" not in c[0]]
        assert calls, "no merge calls found; this test is not looking at anything"
        for first, second in calls:
            assert second.strip() == "_LEVEL_TABLE", (
                f"_merge_level_tables({first}, {second}) puts the curated table "
                "first, so the dump would overrule it"
            )


class TestStaleBeatsUndated:
    def test_stale_cache_is_a_known_provenance_path(self):
        assert ev.PROVENANCE_STALE_CACHE == "stale_cache"

    def test_stale_cache_is_not_reported_as_current(self):
        """Dated is not the same as current, and over-claiming is the hazard."""
        assert ev.PROVENANCE_STALE_CACHE not in ev._CURRENT_EVIDENCE_PATHS

    def test_stale_cache_carries_a_caveat(self):
        assert ev._PROVENANCE_CAVEATS.get(ev.PROVENANCE_STALE_CACHE)

    def test_unknown_paths_still_default_to_not_current(self):
        """Whitelist, not blacklist: a new path must not be assumed current."""
        ev._record_evidence_provenance("some_future_path")
        assert ev.get_evidence_provenance()["is_current"] is False

    def test_stale_cache_records_the_snapshot_date(self):
        path = ev.get_oncokb_cache_path()
        if not path.exists():
            pytest.skip("no cache file in this checkout")
        ev._record_evidence_provenance(ev.PROVENANCE_STALE_CACHE, path)
        provenance = ev.get_evidence_provenance()
        assert provenance["path"] == "stale_cache"
        assert provenance["is_current"] is False
        assert provenance["snapshot_date"], "a dated source must report its date"
        assert provenance["age_days"] is not None


class TestABrokenCacheIsAnnounced:
    def test_unparseable_cache_logs_a_warning(self, tmp_path, caplog):
        """Zero entries from a non-empty file is a defect, not an absence."""
        broken = tmp_path / "cache.txt"
        broken.write_text("this file is not a dump at all\n", encoding="utf-8")
        with caplog.at_level("WARNING"):
            assert ev._load_public_table_from_cache(broken) == {}
        assert any("ZERO entries" in r.message for r in caplog.records)

    def test_a_missing_cache_does_not_warn(self, tmp_path, caplog):
        with caplog.at_level("WARNING"):
            assert ev._load_public_table_from_cache(tmp_path / "absent.txt") == {}
        assert not [r for r in caplog.records if "ZERO entries" in r.message]
