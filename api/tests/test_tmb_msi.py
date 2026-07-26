"""Unit tests for TMB / MSI biomarker scoring (api/services/tmb_msi.py).

These functions take plain mutation dicts and return dataclasses — no network,
no DB, no async. Thresholds under test:
  - TMB-High : >= 10 mut/Mb (default exome 33 Mb -> needs >= 330 nonsynonymous)
  - MSI-H    : frameshift fraction >= 0.15 ; MSI-L 0.05-0.15 ; MSS < 0.05
"""

from api.services.tmb_msi import (
    calculate_tmb,
    calculate_msi,
    run_tmb_msi_analysis,
    tmb_msi_to_dict,
    EXOME_SIZE_MB,
    TMB_HIGH_THRESHOLD,
)


def _muts(classification: str, n: int) -> list[dict]:
    return [{"variant_classification": classification} for _ in range(n)]


# ── calculate_tmb ──────────────────────────────────────────────────────────────

class TestCalculateTmb:
    def test_empty_returns_tmb_low_with_zero(self):
        r = calculate_tmb([])
        assert r.classification == "TMB-Low"
        assert r.tmb_per_mb == 0.0
        assert r.nonsynonymous_count == 0
        assert r.confidence == "LOW"

    def test_high_burden_crosses_threshold(self):
        # 330 missense over 33 Mb -> exactly 10.0 mut/Mb -> TMB-High
        r = calculate_tmb(_muts("Missense_Mutation", 330))
        assert r.tmb_per_mb >= TMB_HIGH_THRESHOLD
        assert r.classification == "TMB-High"
        assert r.confidence == "HIGH"
        assert "pembrolizumab" in r.note.lower()

    def test_just_below_threshold_is_low(self):
        # 329 / 33 = 9.97 -> below 10 -> TMB-Low
        r = calculate_tmb(_muts("Missense_Mutation", 329))
        assert r.classification == "TMB-Low"

    def test_synonymous_variants_are_not_counted(self):
        r = calculate_tmb(_muts("Silent", 500))
        assert r.nonsynonymous_count == 0
        assert r.classification == "TMB-Low"

    def test_falls_back_to_mutation_type_key(self):
        muts = [{"mutation_type": "Nonsense_Mutation"} for _ in range(330)]
        r = calculate_tmb(muts)
        assert r.nonsynonymous_count == 330
        assert r.classification == "TMB-High"

    def test_confidence_tiers(self):
        assert calculate_tmb(_muts("Missense_Mutation", 5)).confidence == "LOW"
        assert calculate_tmb(_muts("Missense_Mutation", 15)).confidence == "MEDIUM"
        assert calculate_tmb(_muts("Missense_Mutation", 40)).confidence == "HIGH"

    def test_panel_size_raises_tmb_for_same_count(self):
        # A small targeted panel (2.5 Mb) inflates mut/Mb vs the full exome.
        muts = _muts("Missense_Mutation", 30)
        exome = calculate_tmb(muts, exome_size_mb=EXOME_SIZE_MB)
        panel = calculate_tmb(muts, exome_size_mb=2.5)
        assert panel.tmb_per_mb > exome.tmb_per_mb


# ── calculate_msi ──────────────────────────────────────────────────────────────

class TestCalculateMsi:
    def test_empty_is_mss(self):
        r = calculate_msi([])
        assert r.classification == "MSS"
        assert r.frameshift_fraction == 0.0

    def test_high_frameshift_fraction_is_msi_high(self):
        # 30 frameshift + 70 missense = 30% frameshift -> MSI-H
        muts = _muts("Frame_Shift_Del", 30) + _muts("Missense_Mutation", 70)
        r = calculate_msi(muts)
        assert r.classification == "MSI-H"
        assert r.frameshift_count == 30

    def test_indeterminate_fraction_is_msi_low(self):
        # 10 frameshift + 90 missense = 10% -> between 0.05 and 0.15 -> MSI-L
        muts = _muts("Frame_Shift_Ins", 10) + _muts("Missense_Mutation", 90)
        assert calculate_msi(muts).classification == "MSI-L"

    def test_low_fraction_is_mss(self):
        # 2 frameshift + 98 missense = 2% -> MSS
        muts = _muts("Frame_Shift_Del", 2) + _muts("Missense_Mutation", 98)
        assert calculate_msi(muts).classification == "MSS"

    def test_boundary_exactly_at_high_threshold(self):
        # 15 frameshift of 100 = 0.15 -> MSI-H (>= boundary)
        muts = _muts("Frame_Shift_Del", 15) + _muts("Missense_Mutation", 85)
        assert calculate_msi(muts).classification == "MSI-H"


# ── run_tmb_msi_analysis + serialisation ────────────────────────────────────────

class TestCombinedReport:
    def test_msi_high_alone_flags_immunotherapy(self):
        muts = _muts("Frame_Shift_Del", 30) + _muts("Missense_Mutation", 70)
        rep = run_tmb_msi_analysis(muts)
        assert rep.msi.classification == "MSI-H"
        assert rep.immunotherapy_relevant is True
        assert "MSI-High" in rep.immunotherapy_note or "MSI-H" in rep.immunotherapy_note

    def test_neither_biomarker_not_relevant(self):
        muts = _muts("Missense_Mutation", 50)  # low TMB, no frameshifts
        rep = run_tmb_msi_analysis(muts)
        assert rep.immunotherapy_relevant is False
        assert "Neither" in rep.immunotherapy_note

    def test_both_high_strong_signal(self):
        # 330 frameshifts: TMB-High AND 100% frameshift -> MSI-H
        rep = run_tmb_msi_analysis(_muts("Frame_Shift_Del", 330))
        assert rep.tmb.classification == "TMB-High"
        assert rep.msi.classification == "MSI-H"
        assert rep.immunotherapy_relevant is True
        assert "Both" in rep.immunotherapy_note

    def test_to_dict_is_json_safe_and_complete(self):
        rep = run_tmb_msi_analysis(_muts("Missense_Mutation", 10))
        d = tmb_msi_to_dict(rep)
        assert set(d.keys()) == {"tmb", "msi", "immunotherapy_relevant", "immunotherapy_note"}
        assert d["tmb"]["classification"] in {"TMB-High", "TMB-Low"}
        assert d["msi"]["classification"] in {"MSI-H", "MSI-L", "MSS"}
        assert isinstance(d["immunotherapy_relevant"], bool)
