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
