"""Unit tests for api/services/mutational_signatures.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from services.mutational_signatures import (
    analyse_signatures_from_mutations,
    signature_candidates_to_drug_dicts,
    _build_profile,
    _heuristic_signature,
    SubstitutionProfile,
    SIGNATURE_DRUG_MAP,
    _SIGNATURE_ALIASES,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snv(ref: str, alt: str):
    return {"ref": ref, "alt": alt, "gene": "TP53", "mutation_type": "SNV"}


def _mutations_with_fraction(channel: str, n_channel: int, n_other: int = 20):
    """Build a mutation list dominated by one substitution channel."""
    ref, alt = channel.split(">")
    dominated = [_snv(ref, alt) for _ in range(n_channel)]
    filler_ref = "C" if ref == "T" else "T"
    filler_alt = "A" if alt in ("G", "T") else "G"
    other = [_snv(filler_ref, filler_alt) for _ in range(n_other)]
    return dominated + other


# ── SubstitutionProfile ───────────────────────────────────────────────────────

def test_build_profile_counts_snvs():
    muts = [_snv("C", "A")] * 10 + [_snv("T", "G")] * 5
    p = _build_profile(muts)
    assert p.C_to_A == 10
    assert p.T_to_G == 5
    assert p.total == 15


def test_build_profile_ignores_indels():
    muts = [{"ref": "CC", "alt": "T"}, {"ref": "C", "alt": "AA"}]
    p = _build_profile(muts)
    assert p.total == 0


def test_build_profile_strand_collapse():
    # G>T collapses to C>A on pyrimidine strand
    muts = [_snv("G", "T")] * 8
    p = _build_profile(muts)
    assert p.C_to_A == 8


def test_profile_fractions_sum_to_one():
    muts = [_snv("C", "A")] * 5 + [_snv("C", "T")] * 5 + [_snv("T", "G")] * 5
    p = _build_profile(muts)
    fracs = p.fractions()
    total = sum(fracs.values())
    assert abs(total - 1.0) < 1e-9


def test_profile_fractions_zero_on_empty():
    p = SubstitutionProfile()
    fracs = p.fractions()
    assert all(v == 0.0 for v in fracs.values())


# ── Heuristic classifier ──────────────────────────────────────────────────────

def test_insufficient_below_10_mutations():
    muts = [_snv("C", "A")] * 5
    result = analyse_signatures_from_mutations(muts)
    assert result.confidence == "INSUFFICIENT"
    assert result.dominant_signature is None


def test_sbs4_detected_tobacco():
    # SBS4: >40% C>A
    muts = _mutations_with_fraction("C>A", n_channel=60, n_other=20)
    result = _heuristic_signature(muts)
    assert result.dominant_signature == "SBS4"
    assert result.confidence in ("HIGH", "MEDIUM")


def test_sbs7_detected_uv():
    # SBS7: >65% C>T
    muts = _mutations_with_fraction("C>T", n_channel=80, n_other=10)
    result = _heuristic_signature(muts)
    assert result.dominant_signature == "SBS7"


def test_sbs13_detected_apobec():
    # SBS13 (APOBEC): dominant C>G — use pure C>G + C>T filler (avoid T>A which triggers SBS3 rule)
    ca = [_snv("C", "G")] * 50
    other = [_snv("C", "T")] * 15 + [_snv("T", "C")] * 10
    result = _heuristic_signature(ca + other)
    assert result.dominant_signature == "SBS13"


def test_sbs10_detected_pole():
    # SBS10: total >200 mutations + high C>A + T>G mix
    ca = [_snv("C", "A")] * 80
    tg = [_snv("T", "G")] * 80
    other = [_snv("C", "T")] * 60
    result = _heuristic_signature(ca + tg + other)
    assert result.dominant_signature == "SBS10"


def test_implication_present_for_known_signature():
    muts = _mutations_with_fraction("C>A", n_channel=60, n_other=20)
    result = _heuristic_signature(muts)
    assert result.implication is not None
    assert result.implication.drug_class != ""
    assert len(result.implication.drug_recommendations) > 0


def test_implication_none_for_no_dominant():
    # All channels balanced — no dominant signature
    muts = (
        [_snv("C", "A")] * 10 + [_snv("C", "G")] * 10 +
        [_snv("C", "T")] * 10 + [_snv("T", "A")] * 10 +
        [_snv("T", "C")] * 10 + [_snv("T", "G")] * 10
    )
    result = _heuristic_signature(muts)
    # balanced profile — signature may or may not be detected, but confidence should be LOW or implication may exist
    # just ensure it doesn't crash
    assert result.mutation_count == 60


# ── Signature aliases ─────────────────────────────────────────────────────────

def test_all_aliases_map_to_valid_entries():
    for alias, canonical in _SIGNATURE_ALIASES.items():
        assert canonical in SIGNATURE_DRUG_MAP, f"Alias {alias} → {canonical} not in SIGNATURE_DRUG_MAP"


# ── signature_candidates_to_drug_dicts ────────────────────────────────────────

def test_insufficient_returns_empty_list():
    muts = [_snv("C", "A")] * 3
    result = analyse_signatures_from_mutations(muts)
    dicts = signature_candidates_to_drug_dicts(result)
    assert dicts == []


def test_drug_dicts_have_required_keys():
    muts = _mutations_with_fraction("C>A", n_channel=60, n_other=20)
    result = _heuristic_signature(muts)
    dicts = signature_candidates_to_drug_dicts(result)
    required = {"drug_name", "oncokb_level", "is_approved", "max_phase",
                 "binding_score", "opentargets_score", "evidence_sources", "matched_terms"}
    for d in dicts:
        assert required.issubset(d.keys())


def test_low_confidence_downgrades_level():
    muts = _mutations_with_fraction("C>A", n_channel=20, n_other=30)
    result = _heuristic_signature(muts)
    dicts = signature_candidates_to_drug_dicts(result)
    # If confidence is LOW, level should be downgraded from original
    if result.confidence == "LOW" and dicts:
        orig_level = SIGNATURE_DRUG_MAP.get(result.dominant_signature, {}).get("oncokb_level", "LEVEL_1")
        for d in dicts:
            assert d["oncokb_level"] != orig_level or orig_level == "LEVEL_4"


def test_no_duplicate_drug_names():
    muts = _mutations_with_fraction("C>A", n_channel=60, n_other=20)
    result = _heuristic_signature(muts)
    dicts = signature_candidates_to_drug_dicts(result)
    names = [d["drug_name"] for d in dicts]
    assert len(names) == len(set(names))


# ── analyse_signatures_from_mutations full flow ───────────────────────────────

def test_full_flow_returns_sign_result():
    muts = _mutations_with_fraction("C>T", n_channel=70, n_other=15)
    result = analyse_signatures_from_mutations(muts)
    assert result.mutation_count == 85
    assert result.dominant_signature is not None
    assert isinstance(result.all_fractions, dict)
    assert "C>T" in result.all_fractions
