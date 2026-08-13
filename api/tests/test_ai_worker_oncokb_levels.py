"""OncoKB level handling in the AI worker.

Three defects lived here at once, and each one silently disabled a safety
behaviour rather than raising:

  1. `_query_oncokb` returned OncoKB's wire format ("LEVEL_1") straight into
     `Mutation.oncokb_level`, whose enum stores "1". The assignment is invalid
     and every downstream comparison against an enum member evaluated False.
  2. Because of that, the targetability check never fired, so no variant was
     ever marked targetable from the OncoKB path.
  3. The resistance check compared `.value` ("R1") against the string
     "LEVEL_R1", so `resistance_context` was unreachable and `rank_candidates`
     never learned that the top variant confers resistance.

None of these would surface in the default configuration, because
`_query_oncokb` returns None with no API token. They only bite once a
deployment wires up a real OncoKB token, which is exactly when the evidence
starts mattering.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from models.mutation import OncoKBLevel  # noqa: E402
from workers.ai_worker import _to_oncokb_level  # noqa: E402


class TestWireFormatMapping:
    @pytest.mark.parametrize(
        "wire, expected",
        [
            ("LEVEL_1", OncoKBLevel.level_1),
            ("LEVEL_2", OncoKBLevel.level_2),
            ("LEVEL_3A", OncoKBLevel.level_3a),
            ("LEVEL_3B", OncoKBLevel.level_3b),
            ("LEVEL_4", OncoKBLevel.level_4),
            ("LEVEL_R1", OncoKBLevel.r1),
            ("LEVEL_R2", OncoKBLevel.r2),
        ],
    )
    def test_oncokb_wire_levels_map_onto_the_enum(self, wire, expected):
        assert _to_oncokb_level(wire) is expected

    def test_bare_enum_values_also_map(self):
        assert _to_oncokb_level("1") is OncoKBLevel.level_1
        assert _to_oncokb_level("R1") is OncoKBLevel.r1

    def test_enum_passes_through(self):
        assert _to_oncokb_level(OncoKBLevel.r2) is OncoKBLevel.r2

    @pytest.mark.parametrize("raw", [None, "", "  ", "LEVEL_9", "garbage", 7])
    def test_unparseable_levels_become_unknown_not_actionable(self, raw):
        """An unreadable level must never be mistaken for an actionable one."""
        result = _to_oncokb_level(raw)
        assert result is OncoKBLevel.unknown
        assert result not in (OncoKBLevel.level_1, OncoKBLevel.level_2, OncoKBLevel.level_3a)


class TestTargetabilityGate:
    """The comparison the worker makes to decide `is_targetable`."""

    TARGETABLE = (OncoKBLevel.level_1, OncoKBLevel.level_2, OncoKBLevel.level_3a)

    def test_level_1_from_the_wire_is_targetable(self):
        # This is the regression: the raw string "LEVEL_1" is not in the tuple,
        # so before the fix a Level 1 variant was never marked targetable.
        assert "LEVEL_1" not in self.TARGETABLE
        assert _to_oncokb_level("LEVEL_1") in self.TARGETABLE

    @pytest.mark.parametrize("wire", ["LEVEL_R1", "LEVEL_R2", "LEVEL_4", "LEVEL_3B"])
    def test_non_actionable_levels_stay_out_of_the_targetable_set(self, wire):
        assert _to_oncokb_level(wire) not in self.TARGETABLE


class TestResistanceReachesTheRanker:
    def test_resistance_levels_compare_equal_as_enums(self):
        for wire in ("LEVEL_R1", "LEVEL_R2"):
            level = _to_oncokb_level(wire)
            assert level in (OncoKBLevel.r1, OncoKBLevel.r2)

    def test_the_old_string_comparison_could_never_match(self):
        """Documents the dead branch so it is not reintroduced."""
        assert OncoKBLevel.r1.value == "R1"
        assert OncoKBLevel.r1.value not in ("LEVEL_R1", "LEVEL_R2")

    def test_resistance_context_level_is_rebuilt_in_wire_form(self):
        """rank_candidates expects LEVEL_R1, so the enum is formatted back."""
        level = _to_oncokb_level("LEVEL_R1")
        assert f"LEVEL_{level.value}" == "LEVEL_R1"


class TestSensitiveAndResistanceAreBothRead:
    """`_query_oncokb` used to read only highestSensitiveLevel.

    api/services/oncokb.py already reads both fields; the worker's own inline
    client did not, so a pure-resistance annotation arrived as "unknown".
    """

    def test_resistance_only_annotation_is_not_lost(self):
        payload = {"highestSensitiveLevel": None, "highestResistanceLevel": "LEVEL_R1"}
        sensitive = payload.get("highestSensitiveLevel")
        resistance = payload.get("highestResistanceLevel")

        assert _to_oncokb_level(sensitive or resistance) is OncoKBLevel.r1
        assert _to_oncokb_level(resistance) is OncoKBLevel.r1

    def test_sensitive_wins_for_the_stored_level_but_resistance_is_kept(self):
        payload = {"highestSensitiveLevel": "LEVEL_1", "highestResistanceLevel": "LEVEL_R1"}
        sensitive = payload.get("highestSensitiveLevel")
        resistance = payload.get("highestResistanceLevel")

        # Stored level is the sensitive one, so the variant is still targetable,
        # while the resistance level survives separately for the ranker.
        assert _to_oncokb_level(sensitive or resistance) is OncoKBLevel.level_1
        assert _to_oncokb_level(resistance) is OncoKBLevel.r1
