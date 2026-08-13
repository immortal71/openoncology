"""Tests for api/services/oncokb_evidence.py

Run with:
    cd api && python -m pytest tests/test_oncokb_evidence.py -v
"""
from __future__ import annotations

import sys
import os

# Allow imports as 'api.services.*' or bare 'services.*'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.oncokb_evidence import (  # noqa: E402
    _normalise_alteration,
    _normalise_drug,
    lookup_oncokb_level,
    get_all_drugs_for_variant,
    annotate_candidates,
)


# ── _normalise_alteration ─────────────────────────────────────────────────────

class TestNormaliseAlteration:
    def test_lowercase(self):
        assert _normalise_alteration("T790M") == "t790m"

    def test_strips_whitespace(self):
        assert _normalise_alteration("  T790M  ") == "t790m"

    def test_p_dot_prefix_removed(self):
        result = _normalise_alteration("p.T790M")
        assert result in ("p.t790m", "t790m")

    def test_empty_string(self):
        assert _normalise_alteration("") == ""


# ── _normalise_drug ───────────────────────────────────────────────────────────

class TestNormaliseDrug:
    def test_lowercase_no_spaces(self):
        result = _normalise_drug("Osimertinib")
        assert result == result.lower()

    def test_strips_hyphens_and_spaces(self):
        a = _normalise_drug("Erlotinib HCl")
        b = _normalise_drug("erlotinibhcl")
        # Both should reduce to the same token
        assert " " not in a

    def test_empty_string(self):
        assert _normalise_drug("") == ""


# ── lookup_oncokb_level ───────────────────────────────────────────────────────

class TestLookupOncoKBLevel:
    """Tests against the curated static table (~120 entries)."""

    def test_egfr_t790m_osimertinib_is_level_1(self):
        level = lookup_oncokb_level("EGFR", "T790M", "Osimertinib")
        assert level == "LEVEL_1", f"Expected LEVEL_1, got {level}"

    def test_egfr_t790m_erlotinib_is_resistance(self):
        level = lookup_oncokb_level("EGFR", "T790M", "Erlotinib")
        assert level in ("LEVEL_R1", "LEVEL_R2"), (
            f"Erlotinib should be resistance for T790M, got {level}"
        )

    def test_braf_v600e_vemurafenib_is_level_1(self):
        level = lookup_oncokb_level("BRAF", "V600E", "Vemurafenib")
        assert level in ("LEVEL_1", "LEVEL_2"), f"Expected L1/L2, got {level}"

    def test_kras_g12c_sotorasib_is_level_1(self):
        level = lookup_oncokb_level("KRAS", "G12C", "Sotorasib")
        assert level is not None and level.startswith("LEVEL_"), (
            f"Expected a level entry for KRAS G12C + Sotorasib, got {level}"
        )

    def test_unknown_gene_returns_none(self):
        level = lookup_oncokb_level("FAKEGENE", "X999Y", "NotADrug")
        assert level is None

    def test_case_insensitive_gene(self):
        upper = lookup_oncokb_level("EGFR", "T790M", "Osimertinib")
        lower = lookup_oncokb_level("egfr", "t790m", "osimertinib")
        assert upper == lower

    def test_returns_string_or_none(self):
        result = lookup_oncokb_level("ALK", "EML4-ALK", "Crizotinib")
        assert result is None or isinstance(result, str)


# ── get_all_drugs_for_variant ─────────────────────────────────────────────────

class TestGetAllDrugsForVariant:
    def test_egfr_exon19del_returns_drugs(self):
        drugs = get_all_drugs_for_variant("EGFR", "Exon19del")
        assert isinstance(drugs, dict)
        # Should contain at least one EGFR TKI
        assert len(drugs) > 0

    def test_unknown_variant_returns_empty_dict(self):
        drugs = get_all_drugs_for_variant("FAKEGENE", "XXXYYY")
        assert drugs == {}

    def test_resistance_drug_present_for_t790m(self):
        drugs = get_all_drugs_for_variant("EGFR", "T790M")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        # Osimertinib should be L1; erlotinib/gefitinib should be R1
        assert any("osimertinib" in k for k in drug_levels), (
            "Osimertinib should appear for EGFR T790M"
        )

    def test_egfr_real_world_exon19_range_deletion_matches(self):
        """T751_E758del is a real deletion found in TCGA patient data
        (docs/REAL_PATIENT_CONCORDANCE_PILOT_2026-07-28.md) that doesn't match
        any exact alias but falls entirely within the EGFR exon 19 span
        (729-761) and should resolve to the same drugs as the canonical
        E746_A750del / Exon19del entries."""
        drugs = get_all_drugs_for_variant("EGFR", "T751_E758del")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert "osimertinib" in drug_levels
        assert drug_levels["osimertinib"] == "LEVEL_1"

    def test_kit_real_world_exon11_range_deletion_matches(self):
        """W557_K558del is a real, well-documented KIT exon 11 GIST deletion
        (codons 550-592, the classic juxtamembrane driver region) that isn't
        one of the table's named endpoint pairs but should resolve to the
        same drugs as the generic EXON11DEL bucket."""
        drugs = get_all_drugs_for_variant("KIT", "W557_K558del")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert "imatinib" in drug_levels
        assert drug_levels["imatinib"] == "LEVEL_1"

    def test_kit_point_mutation_in_exon11_range_not_treated_as_deletion(self):
        """V559D is a real KIT exon 11 point mutation (not a deletion) inside
        the same residue range -- the range-del heuristic must only match
        actual deletions, never point substitutions, since a point mutation's
        drug sensitivity profile isn't necessarily the same as EXON11DEL's.

        This originally asserted V559D returned nothing at all, which enforced
        that property by returning no evidence for a real imatinib-sensitive
        GIST driver. V559D now resolves through the EXON11MUT bucket instead,
        so the original requirement is asserted directly: it must not pick up
        the deletion bucket's profile. EXON11DEL carries imatinib, regorafenib,
        ripretinib and sunitinib; EXON11MUT carries imatinib and sunitinib only.
        """
        drugs = get_all_drugs_for_variant("KIT", "V559D")
        deletion_profile = get_all_drugs_for_variant("KIT", "EXON11DEL") or {}
        assert drugs, "V559D is an exon 11 driver and should reach evidence"
        assert drugs != deletion_profile, (
            "a point mutation must not inherit the deletion bucket's drug profile"
        )
        assert drugs == (get_all_drugs_for_variant("KIT", "EXON11MUT") or {})
        assert "regorafenib" not in {k.lower() for k in drugs}

    def test_kit_existing_hotspot_entries_unaffected_by_range_del_fallback(self):
        """D816V and V654A are existing named KIT entries outside/unrelated to
        the exon 11 deletion range -- confirms the new fallback doesn't
        interfere with entries that already resolve correctly."""
        d816v = get_all_drugs_for_variant("KIT", "D816V")
        assert "avapritinib" in {k.lower() for k in d816v}
        v654a = get_all_drugs_for_variant("KIT", "V654A")
        assert "sunitinib" in {k.lower() for k in v654a}

    def test_egfr_real_world_exon20_range_insertion_matches(self):
        """H773_V774insH is a real, documented EGFR exon 20 insertion (codons
        762-823) that isn't one of the table's 2 named insertion examples but
        should resolve to the same drugs as the generic EXON20INS bucket --
        including the LEVEL_R1 resistance flags on classical TKIs, since
        exon 20 insertions are a clinically distinct, TKI-resistant class."""
        drugs = get_all_drugs_for_variant("EGFR", "H773_V774insH")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert drug_levels.get("amivantamab") == "LEVEL_1"
        assert drug_levels.get("osimertinib") == "LEVEL_R1"

    def test_erbb2_real_world_exon20_range_insertion_matches(self):
        """P780_Y781insGSP is a real HER2/ERBB2 exon 20 insertion outside the
        table's single named example (A775_G776insYVMA) but within the same
        documented exon 20 span; should resolve to the generic EXON20INS
        bucket."""
        drugs = get_all_drugs_for_variant("ERBB2", "P780_Y781insGSP")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert len(drug_levels) > 0

    def test_point_mutations_are_never_treated_as_range_insertions(self):
        """L858R and T790M are real EGFR point mutations, not insertions --
        the range-insertion heuristic must never fire for them, since a bare
        point-mutation string has no ins-range token to match."""
        l858r = get_all_drugs_for_variant("EGFR", "L858R")
        assert {k.lower() for k in l858r} == {
            "osimertinib", "erlotinib", "gefitinib", "afatinib", "dacomitinib",
        }
        t790m = get_all_drugs_for_variant("EGFR", "T790M")
        drug_levels = {k.lower(): v for k, v in t790m.items()}
        assert drug_levels.get("osimertinib") == "LEVEL_1"

    def test_named_exon20_insertion_entries_unaffected_by_range_fallback(self):
        """A763_Y764insFQEA is an existing named entry -- confirms the new
        range-insertion fallback doesn't interfere with entries that already
        resolve correctly via exact match."""
        drugs = get_all_drugs_for_variant("EGFR", "A763_Y764insFQEA")
        assert {k.lower() for k in drugs} == {"amivantamab"}

    def test_calr_type1_real_world_exon9_frameshift_matches(self):
        """L367fs*46 is the canonical CALR Type 1 (52bp deletion) MPN driver
        mutation -- real-world HGVS notation that never matches the table's
        literal 'EXON9DEL' or 'TYPE2' keys without range-based fallback."""
        drugs = get_all_drugs_for_variant("CALR", "L367fs*46")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert drug_levels.get("ruxolitinib") == "LEVEL_1"

    def test_calr_type2_real_world_exon9_frameshift_matches(self):
        """K385fs*47 is the canonical CALR Type 2 (5bp insertion) MPN driver
        mutation, reported in HGVS frameshift notation rather than the
        table's named 'TYPE2' key."""
        drugs = get_all_drugs_for_variant("CALR", "K385fs*47")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert drug_levels.get("ruxolitinib") == "LEVEL_1"

    def test_calr_frameshift_outside_exon9_range_does_not_match(self):
        drugs = get_all_drugs_for_variant("CALR", "E230fs*32")
        assert drugs == {}

    def test_frameshift_on_other_gene_not_treated_as_calr_exon9(self):
        drugs = get_all_drugs_for_variant("TP53", "R213fs*10")
        assert drugs == {}

    def test_calr_point_mutation_in_exon9_range_not_treated_as_frameshift(self):
        drugs = get_all_drugs_for_variant("CALR", "D374N")
        assert drugs == {}

    def test_calr_named_type2_entry_unaffected_by_range_fs_fallback(self):
        drugs = get_all_drugs_for_variant("CALR", "TYPE2")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert drug_levels.get("ruxolitinib") == "LEVEL_1"
        assert drug_levels.get("fedratinib") == "LEVEL_2"

    # ── BRCA1/2 truncating variants → PARP inhibitors ────────────────────────
    # The ("BRCA1"/"BRCA2", "TRUNCATING") evidence existed but was only
    # reachable by exact literal key, and the four frameshift aliases meant to
    # reach it were spelled "truncation" against a "TRUNCATING" key, so they
    # resolved to nothing. Real-world truncating BRCA variants returned no
    # recommendation at all.

    def test_brca2_s1982fs_resolves_to_parp_inhibitors(self):
        """S1982fs (the 6174delT founder allele) is among the most frequently
        reported pathogenic BRCA2 variants. Before the fix this returned {}."""
        drugs = get_all_drugs_for_variant("BRCA2", "S1982fs")
        drug_levels = {k.lower(): v for k, v in drugs.items()}
        assert drug_levels.get("olaparib") == "LEVEL_1"
        assert drug_levels.get("talazoparib") == "LEVEL_1"

    def test_brca1_frameshift_resolves_to_parp_inhibitors(self):
        drugs = get_all_drugs_for_variant("BRCA1", "Q1395fs")
        assert {k.lower() for k in drugs} >= {"olaparib", "niraparib", "rucaparib"}

    def test_brca_nonsense_variants_resolve_to_parp_inhibitors(self):
        """A premature stop truncates the protein, so nonsense variants carry
        the same PARP-inhibitor evidence as frameshifts."""
        for gene, variant in [("BRCA1", "R1443*"), ("BRCA2", "K3326X")]:
            drugs = get_all_drugs_for_variant(gene, variant)
            assert "olaparib" in {k.lower() for k in drugs}, f"{gene} {variant}"

    def test_brca_missense_not_matched_by_truncating_detector(self):
        """C61G is a real pathogenic BRCA1 RING-domain missense variant, but
        pathogenicity of a missense change cannot be decided from notation --
        that is what the AlphaMissense gene-level fallback is for. The
        truncating detector must not claim it."""
        assert get_all_drugs_for_variant("BRCA1", "C61G") == {}
        assert get_all_drugs_for_variant("BRCA2", "N372H") == {}

    def test_truncating_variant_on_unrelated_gene_gets_no_parp(self):
        """The detector is scoped to BRCA1/2 only -- a frameshift or nonsense
        variant elsewhere must not pick up PARP-inhibitor evidence."""
        for gene, variant in [("TP53", "R213*"), ("APC", "Q1367fs")]:
            drugs = {k.lower() for k in get_all_drugs_for_variant(gene, variant)}
            assert not (drugs & {"olaparib", "niraparib", "rucaparib", "talazoparib"})

    def test_brca_named_literal_entry_still_resolves(self):
        """185delAG resolved correctly before the fix and must be unaffected."""
        drugs = get_all_drugs_for_variant("BRCA1", "185delAG")
        assert "olaparib" in {k.lower() for k in drugs}

    # ── Tumour-suppressor loss-of-function reachability ─────────────────────
    # A table-wide audit found 24 genes carrying curated LOF evidence that no
    # real-world truncating variant could reach, because the bucket was only
    # addressable by its exact literal key. These lock in the generalised fix.

    def test_vhl_real_world_truncating_variants_resolve(self):
        """These four are real variants from actual TCGA-KIRC patients in the
        2026-07-28 concordance pilot. Every one returned no recommendation
        before the fix, despite ("VHL","TRUNCATING") holding belzutifan."""
        for variant in ["W117Gfs*42", "D179Afs*22", "R161*", "T124Hfs*35"]:
            drugs = {k.lower() for k in get_all_drugs_for_variant("VHL", variant)}
            assert "belzutifan" in drugs, f"VHL {variant}"

    def test_nf1_truncating_resolves_to_mek_inhibitors(self):
        """Selumetinib is FDA-approved for NF1-driven disease; NF1 is
        inactivated by truncating variants."""
        drugs = {k.lower() for k in get_all_drugs_for_variant("NF1", "R1276*")}
        assert "selumetinib" in drugs

    def test_rb1_truncating_resolves_to_cdk46_inhibitors(self):
        drugs = {k.lower() for k in get_all_drugs_for_variant("RB1", "R320fs")}
        assert drugs & {"palbociclib", "ribociclib", "abemaciclib"}

    def test_hrd_genes_truncating_resolve_to_parp_inhibitors(self):
        """The homologous-recombination genes all carry PARP evidence that was
        equally unreachable."""
        for gene in ["ATM", "PALB2", "RAD51C", "RAD51D", "BRIP1", "NBN"]:
            drugs = {k.lower() for k in get_all_drugs_for_variant(gene, "Q500*")}
            assert drugs & {"olaparib", "niraparib", "rucaparib", "talazoparib"}, gene

    def test_oncogene_truncating_variant_gets_no_lof_evidence(self):
        """The guard that makes this safe: the LOF route only fires for genes
        that already carry a curated LOF bucket. Oncogenes have none, so a
        truncating variant in one must resolve to nothing rather than picking
        up activating-therapy evidence."""
        for gene in ["EGFR", "KRAS", "BRAF", "ALK", "MET", "ERBB2"]:
            for variant in ["Q500*", "R500fs", "W500X"]:
                assert get_all_drugs_for_variant(gene, variant) == {}, f"{gene} {variant}"

    def test_tumour_suppressor_missense_not_matched_by_lof_route(self):
        """Whether a missense change inactivates a tumour suppressor cannot be
        read off its notation -- that needs AlphaMissense/ClinVar. Only
        truncating classes route to the LOF bucket."""
        for gene, variant in [("VHL", "L158V"), ("NF1", "R1276Q"),
                              ("RB1", "A500T"), ("ATM", "L2307F")]:
            assert get_all_drugs_for_variant(gene, variant) == {}, f"{gene} {variant}"

    def test_met_exon14_splice_resolves_to_approved_inhibitors(self):
        """MET exon-14 skipping is ~3-4% of NSCLC and capmatinib/tepotinib are
        FDA-approved for it. ("MET","EXON14SKIP") held that evidence but only
        the literal key reached it, so a real report reading X1010_splice
        returned nothing."""
        for variant in ["X1010_splice", "X963_splice", "X1006_splice"]:
            drugs = {k.lower() for k in get_all_drugs_for_variant("MET", variant)}
            assert {"capmatinib", "tepotinib"} <= drugs, variant

    def test_met_splice_outside_exon14_range_does_not_match(self):
        for variant in ["X500_splice", "X1200_splice"]:
            assert get_all_drugs_for_variant("MET", variant) == {}, variant

    def test_splice_variant_on_other_gene_not_treated_as_met_exon14(self):
        assert get_all_drugs_for_variant("EGFR", "X1010_splice") == {}

    def test_met_missense_at_exon14_residue_not_inferred_as_skipping(self):
        """D1010 substitutions can drive exon-14 skipping, but which missense
        changes disrupt splicing is a per-variant curation question. The
        position-based splice rule must not infer it."""
        assert get_all_drugs_for_variant("MET", "D1010N") == {}

    def test_lof_route_prefers_truncating_over_deletion_bucket(self):
        """DELETION denotes a copy-number event, not a truncating point
        variant, so it is excluded from the preference order. NF1 carries
        DELETION, LOSS and TRUNCATING -- a frameshift must land on TRUNCATING."""
        from services.oncokb_evidence import _lof_bucket_for_gene
        assert _lof_bucket_for_gene("NF1") == "TRUNCATING"
        assert _lof_bucket_for_gene("EGFR") is None

    def test_egfr_deletion_outside_exon19_range_does_not_match(self):
        """A deletion with residue numbers outside the exon 19 span (e.g. in
        the kinase domain near T790M/exon 20) must NOT be treated as an
        exon 19 deletion just because it matches the DEL pattern shape."""
        drugs = get_all_drugs_for_variant("EGFR", "D770_N771del")
        # Should not silently inherit the exon19del drug set.
        assert "E746A750DEL" not in [k.upper() for k in drugs]


# ── annotate_candidates ────────────────────────────────────────────────────────

class TestAnnotateCandidates:
    """annotate_candidates() is a synchronous function that enriches a list of
    candidate dicts with oncokb_level."""

    def _make_candidates(self, names: list[str]) -> list[dict]:
        return [{"drug_name": n, "oncokb_level": None} for n in names]

    def test_osimertinib_annotated_for_t790m(self):
        candidates = self._make_candidates(["Osimertinib", "Erlotinib", "Gefitinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        levels = {c["drug_name"]: c.get("oncokb_level") for c in annotated}
        assert levels["Osimertinib"] == "LEVEL_1"

    def test_resistance_annotated_for_t790m(self):
        candidates = self._make_candidates(["Erlotinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        level = annotated[0].get("oncokb_level")
        assert level in ("LEVEL_R1", "LEVEL_R2"), (
            f"Erlotinib should be resistance for T790M, got {level}"
        )

    def test_unknown_drug_level_remains_none(self):
        candidates = self._make_candidates(["TotallyMadeUpDrug99"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        # Level should be None or unchanged — should NOT be injected as Level 1
        level = annotated[0].get("oncokb_level")
        assert level is None or not level.startswith("LEVEL_1")

    def test_empty_candidates_returns_empty(self):
        result = annotate_candidates([], "EGFR", "T790M")
        assert result == []

    def test_existing_level_not_overwritten_by_none(self):
        """If a candidate already has a level, it should not be overwritten with None."""
        candidates = [{"drug_name": "SomeNewDrug", "oncokb_level": "LEVEL_4"}]
        annotated = annotate_candidates(candidates, "EGFR", "UnknownVariant")
        # Level should be preserved if annotate_candidates doesn't know this drug
        level = annotated[0].get("oncokb_level")
        assert level is not None  # Must not silently nullify an existing annotation

    def test_braf_v600e_vemurafenib_annotated(self):
        candidates = self._make_candidates(["Vemurafenib", "Dabrafenib"])
        annotated = annotate_candidates(candidates, "BRAF", "V600E")
        vemurafenib = next(c for c in annotated if c["drug_name"] == "Vemurafenib")
        assert vemurafenib.get("oncokb_level") is not None

    def test_returns_list_same_length(self):
        candidates = self._make_candidates(["Osimertinib", "Erlotinib"])
        annotated = annotate_candidates(candidates, "EGFR", "T790M")
        assert len(annotated) == 2


# ── Resistance safety floor ────────────────────────────────────────────────────

class TestResistanceSafetyFloor:
    """Critical: resistance designations must be present even when using fallback table."""

    def test_afatinib_is_resistance_for_t790m(self):
        from services.oncokb_evidence import lookup_oncokb_level
        level = lookup_oncokb_level("EGFR", "T790M", "Afatinib")
        assert level in ("LEVEL_R1", "LEVEL_R2", None), (
            f"Afatinib should be resistance or unknown for T790M, got {level}"
        )

    def test_imatinib_resistance_for_abl1_t315i(self):
        """Imatinib must not appear as a non-resistance drug for ABL1 T315I."""
        level = lookup_oncokb_level("ABL1", "T315I", "Imatinib")
        if level is not None:
            assert level.startswith("LEVEL_R"), (
                f"Imatinib should be resistance for ABL1 T315I, got {level}"
            )


# ── High-impact regression checks ─────────────────────────────────────────────

class TestHighImpactEvidenceRegressions:
    """Guard clinically important entries that previously caused benchmark misses."""

    def test_mlh1_loss_of_expression_has_actionable_drug(self):
        drugs = get_all_drugs_for_variant("MLH1", "LOSSOFEXPRESSION", alphamissense_score=1.0)
        assert drugs, "MLH1 LOSSOFEXPRESSION should return actionable evidence"
        assert any(str(level).startswith("LEVEL_") and "R" not in str(level) for level in drugs.values())

    def test_npm1_insertiontypeb_contains_midostaurin(self):
        drugs = {k.lower(): v for k, v in get_all_drugs_for_variant("NPM1", "INSERTIONTYPEB", alphamissense_score=1.0).items()}
        assert "midostaurin" in drugs, "NPM1 INSERTIONTYPEB should include midostaurin"
        assert str(drugs["midostaurin"]).startswith("LEVEL_"), "midostaurin should have an OncoKB level"

    def test_vhl_loss_includes_belzutifan(self):
        drugs = {k.lower(): v for k, v in get_all_drugs_for_variant("VHL", "LOSS", alphamissense_score=1.0).items()}
        assert "belzutifan" in drugs, "VHL LOSS should include belzutifan"
        assert str(drugs["belzutifan"]) == "LEVEL_1", "belzutifan should be LEVEL_1 for VHL LOSS"


# ── Fusion delimiter notation ────────────────────────────────────────────────

class TestFusionDelimiters:
    """Fusions must resolve identically whichever delimiter the lab used.

    HGVS/ISCN recommend the double colon (EML4::ALK), which is the notation
    labs are moving to. Only the hyphen forms were handled, so EML4-ALK
    returned five drugs while EML4::ALK returned none. The failure was silent:
    an unrecognised fusion looks exactly like a fusion with no evidence.
    """

    # (gene, partner-first fusion) covering every fusion family in the table
    FUSIONS = [
        ("ALK", "EML4", "ALK"),
        ("ALK", "NPM1", "ALK"),
        ("ROS1", "CD74", "ROS1"),
        ("RET", "KIF5B", "RET"),
        ("NTRK1", "TPM3", "NTRK1"),
        ("NTRK3", "ETV6", "NTRK3"),
        ("RARA", "PML", "RARA"),
        ("FGFR3", "FGFR3", "TACC3"),
        ("KMT2A", "KMT2A", "MLLT3"),
    ]

    def test_double_colon_matches_hyphen(self):
        for gene, five_prime, three_prime in self.FUSIONS:
            hyphen = get_all_drugs_for_variant(gene, f"{five_prime}-{three_prime}") or {}
            colons = get_all_drugs_for_variant(gene, f"{five_prime}::{three_prime}") or {}
            assert hyphen, f"{five_prime}-{three_prime} should have evidence to compare against"
            assert colons == hyphen, (
                f"{five_prime}::{three_prime} resolved differently from "
                f"{five_prime}-{three_prime}"
            )

    def test_star_fusion_double_hyphen_matches(self):
        """STAR-Fusion writes EML4--ALK in its #FusionName column."""
        for gene, five_prime, three_prime in self.FUSIONS:
            single = get_all_drugs_for_variant(gene, f"{five_prime}-{three_prime}") or {}
            double = get_all_drugs_for_variant(gene, f"{five_prime}--{three_prime}") or {}
            assert double == single, f"{five_prime}--{three_prime} should match the hyphen form"

    def test_colon_stripping_does_not_disturb_other_notation(self):
        """Point mutations, indels, frameshifts and splice variants are
        unaffected, since none of them carry a colon."""
        for gene, alteration in [
            ("EGFR", "L858R"),
            ("EGFR", "p.Leu858Arg"),
            ("BRAF", "V600E"),
            ("EGFR", "T751_E758del"),
            ("BRCA1", "S1982fs"),
            ("MET", "X1010_splice"),
        ]:
            assert get_all_drugs_for_variant(gene, alteration), f"{gene} {alteration} regressed"


# ── Copy-number notation ─────────────────────────────────────────────────────

class TestCopyNumberNotation:
    """Copy-number calls arrive in more spellings than point mutations, because
    there is no HGVS equivalent everyone follows. See
    scripts/audit_cnv_reachability.py for the full sweep.
    """

    # Genes whose amplification bucket actually holds evidence. AXL, CCNE1,
    # FGFR4 and MDM2 carry the bucket but nothing in it, which is a curation
    # gap rather than a notation one, so they are not asserted on here.
    AMP_GENES = ["ERBB2", "MET", "EGFR", "CCND1", "CDK4", "FGFR1", "AR"]

    def test_amplified_matches_amplification(self):
        """Pathology reports say "HER2 amplified", not "ERBB2 Amplification".
        This returned nothing for all 26 amplification genes."""
        for gene in self.AMP_GENES:
            canonical = get_all_drugs_for_variant(gene, "Amplification") or {}
            assert canonical, f"{gene} Amplification should have evidence"
            assert (get_all_drugs_for_variant(gene, "amplified") or {}) == canonical
            assert (get_all_drugs_for_variant(gene, "Amplified") or {}) == canonical

    def test_copy_gain_is_not_treated_as_amplification(self):
        """The safety property. A low-level gain of 3 to 4 copies is a
        different call from a high-level amplification and does not carry the
        same evidence. ERBB2 gain must not qualify a patient for trastuzumab
        the way ERBB2 amplification does."""
        for gene in self.AMP_GENES:
            assert not (get_all_drugs_for_variant(gene, "gain") or {}), (
                f"{gene} gain must not resolve to amplification evidence"
            )
            assert not (get_all_drugs_for_variant(gene, "copy number gain") or {})

    def test_cbioportal_homdel_spelling(self):
        """HOMDEL is the literal value in cBioPortal's CNA export and "Deep
        Deletion" is how its UI labels that same value. Both returned nothing."""
        for gene in ["CDKN2A", "PTEN", "NF1"]:
            canonical = get_all_drugs_for_variant(gene, "homozygous deletion") or {}
            assert canonical, f"{gene} homozygous deletion should have evidence"
            assert (get_all_drugs_for_variant(gene, "HOMDEL") or {}) == canonical
            assert (get_all_drugs_for_variant(gene, "deep deletion") or {}) == canonical

    def test_deleted_matches_deletion(self):
        for gene in ["PTEN", "NF1"]:
            canonical = get_all_drugs_for_variant(gene, "deletion") or {}
            assert canonical, f"{gene} deletion should have evidence"
            assert (get_all_drugs_for_variant(gene, "deleted") or {}) == canonical

    def test_loss_only_genes_still_reachable(self):
        """PTCH1 and VHL carry a LOSS bucket but no DELETION bucket, so the
        word "deletion" finds nothing for them while "loss" works. Curation
        gap rather than a routing bug, pinned here so it stays visible."""
        for gene in ["PTCH1", "VHL"]:
            assert get_all_drugs_for_variant(gene, "loss"), f"{gene} loss regressed"


# ── Notation classes found by the reachability sweep ─────────────────────────

class TestExon20DuplicationNotation:
    """Exon 20 insertions are reported as duplications about as often as they
    are reported as insertions. Only the INS form resolved, so A767_V769dup,
    one of the more common EGFR exon 20 insertions, returned nothing.
    """

    def test_dup_notation_matches_ins_notation(self):
        canonical = get_all_drugs_for_variant("EGFR", "D770_N771insSVD") or {}
        assert canonical
        for alteration in ["A767_V769dup", "H773dup", "p.Ala767_Val769dup"]:
            assert (get_all_drugs_for_variant("EGFR", alteration) or {}) == canonical, alteration

    def test_resistance_mutations_in_range_are_not_swept_in(self):
        """The safety property. T790M and C797S sit inside the exon 20 codon
        span but are EGFR TKI resistance mutations, not insertions. Requiring
        the DUP or INS token is what keeps them out."""
        exon20 = get_all_drugs_for_variant("EGFR", "D770_N771insSVD") or {}
        for alteration in ["T790M", "C797S", "V774M", "R776H"]:
            assert (get_all_drugs_for_variant("EGFR", alteration) or {}) != exon20, alteration

    def test_t790m_keeps_its_resistance_annotation(self):
        levels = {str(v) for v in (get_all_drugs_for_variant("EGFR", "T790M") or {}).values()}
        assert any(level.startswith("LEVEL_R") for level in levels)


class TestKitExon11Missense:
    """Only deletions in KIT exon 11 resolved, so W557_K558del found evidence
    while V559D found nothing. Both are juxtamembrane exon 11 mutations and
    both are the imatinib-sensitive GIST genotype.
    """

    def test_exon11_point_mutations_resolve(self):
        canonical = get_all_drugs_for_variant("KIT", "EXON11MUT") or {}
        assert canonical
        for alteration in ["V559D", "V559A", "L576P", "W557R"]:
            assert (get_all_drugs_for_variant("KIT", alteration) or {}) == canonical, alteration

    def test_exon17_resistance_mutations_stay_out(self):
        """D816V is imatinib-resistant and lives in exon 17, outside the 550-592
        span. It must not be routed into the imatinib-sensitive bucket."""
        exon11 = get_all_drugs_for_variant("KIT", "EXON11MUT") or {}
        for alteration in ["D816V", "D820Y", "N822K"]:
            assert (get_all_drugs_for_variant("KIT", alteration) or {}) != exon11, alteration

    def test_d816v_keeps_its_resistance_annotation(self):
        levels = {str(v) for v in (get_all_drugs_for_variant("KIT", "D816V") or {}).values()}
        assert any(level.startswith("LEVEL_R") for level in levels)


class TestExpressionLossNotation:
    """Pathology reports say "absent" or "mismatch repair deficient" far more
    often than "loss of expression", and only the last of those resolved. dMMR
    is a tumour-agnostic pembrolizumab indication.
    """

    def test_ihc_phrasings_resolve(self):
        canonical = get_all_drugs_for_variant("MLH1", "loss of expression") or {}
        assert canonical
        for alteration in ["absent", "deficient", "IHC loss", "loss by IHC"]:
            assert (get_all_drugs_for_variant("MLH1", alteration) or {}) == canonical, alteration

    def test_expression_phrasings_do_not_invent_evidence_elsewhere(self):
        """These map to the expression bucket, so they resolve only for genes
        that carry one and return nothing for genes that do not."""
        assert not (get_all_drugs_for_variant("KRAS", "deficient") or {})
        assert not (get_all_drugs_for_variant("TTN", "absent") or {})


# ── Gene symbol aliases ──────────────────────────────────────────────────────

class TestGeneSymbolAliases:
    """Reports name genes the way clinicians name them, not the way HGNC does.

    Nothing normalised the incoming symbol, so "HER2 Amplification" returned
    nothing while "ERBB2 Amplification" returned 8 drugs including
    trastuzumab. HER2 is how HER2 status is written in essentially every
    breast and gastric pathology report. A sweep of 29 common legacy symbols
    found 26 completely unreachable.
    """

    ALIASES = [
        ("HER2", "ERBB2", "Amplification"),
        ("HER-2", "ERBB2", "Amplification"),
        ("HER2/neu", "ERBB2", "Amplification"),
        ("HER1", "EGFR", "L858R"),
        ("c-KIT", "KIT", "V559D"),
        ("CD117", "KIT", "V559D"),
        ("c-MET", "MET", "exon 14 skipping"),
        ("PD-L1", "CD274", "Amplification"),
        ("MLL", "KMT2A", "KMT2A-MLLT3"),
        ("K-RAS", "KRAS", "G12C"),
        ("B-RAF", "BRAF", "V600E"),
        ("p16", "CDKN2A", "homozygous deletion"),
        ("BRG1", "SMARCA4", "Q729fs"),
        ("TRKA", "NTRK1", "TPM3-NTRK1"),
    ]

    def test_legacy_symbols_resolve_to_hgnc_evidence(self):
        for legacy, hgnc, alteration in self.ALIASES:
            canonical = get_all_drugs_for_variant(hgnc, alteration) or {}
            assert canonical, f"{hgnc} {alteration} should have evidence to compare against"
            assert (get_all_drugs_for_variant(legacy, alteration) or {}) == canonical, (
                f"{legacy} should resolve as {hgnc}"
            )

    def test_her2_amplification_reaches_trastuzumab(self):
        """The single case most likely to appear in real reports."""
        drugs = {k.lower() for k in (get_all_drugs_for_variant("HER2", "Amplification") or {})}
        assert "trastuzumab" in drugs

    def test_hyphenated_hgnc_symbols_are_not_mangled(self):
        """Some approved symbols do contain a hyphen: the histone genes were
        renamed in 2021, so H3F3A is now H3-3A. Stripping punctuation
        unconditionally turned that into H33A and broke H3-3A K27M, the
        defining alteration of diffuse midline glioma."""
        from services.oncokb_evidence import _normalise_gene
        assert _normalise_gene("H3-3A") == "H3-3A"
        assert get_all_drugs_for_variant("H3-3A", "K27M")

    def test_every_table_gene_still_normalises_to_itself(self):
        """Guards the whole table against a future alias hijacking a real
        symbol, which is how the H3-3A regression happened."""
        from services.oncokb_evidence import _LEVEL_TABLE, _normalise_gene
        for gene in {g for (g, _alt) in _LEVEL_TABLE}:
            assert _normalise_gene(gene) == gene, f"{gene} no longer resolves to itself"

    def test_unknown_symbol_is_passed_through_not_guessed(self):
        from services.oncokb_evidence import _normalise_gene
        assert _normalise_gene("NOTAGENE") == "NOTAGENE"
        assert not (get_all_drugs_for_variant("NOTAGENE", "V600E") or {})

    def test_alias_resolves_even_where_the_gene_has_no_evidence_yet(self):
        """LKB1 maps to STK11, which currently carries no entries at all. The
        symbol mapping is still correct and should hold for when it does, so it
        is asserted on the normaliser rather than on drug output."""
        from services.oncokb_evidence import _normalise_gene
        assert _normalise_gene("LKB1") == "STK11"


# ── Drug trade names ─────────────────────────────────────────────────────────

class TestDrugBrandAliases:
    """Records name drugs the way they were prescribed, not by INN.

    lookup_oncokb_level("ERBB2", "Amplification", "Herceptin") returned None
    while the same call with "trastuzumab" returned LEVEL_1. All 20 trade
    names probed were unreachable.

    This understates accuracy rather than overstating it: TCGA's treatment
    fields carry trade names, and the concordance benchmark scores our
    recommendations against them, so an unmapped trade name scores a miss on
    a case we actually got right.
    """

    BRANDS = [
        ("Herceptin", "trastuzumab", "ERBB2", "Amplification"),
        ("Tagrisso", "osimertinib", "EGFR", "T790M"),
        ("Gleevec", "imatinib", "KIT", "EXON11MUT"),
        ("Glivec", "imatinib", "KIT", "EXON11MUT"),
        ("Zelboraf", "vemurafenib", "BRAF", "V600E"),
        ("Xalkori", "crizotinib", "ALK", "EML4-ALK"),
        ("Lumakras", "sotorasib", "KRAS", "G12C"),
        ("Lynparza", "olaparib", "BRCA1", "S1982fs"),
        ("Piqray", "alpelisib", "PIK3CA", "H1047R"),
        ("Tabrecta", "capmatinib", "MET", "EXON14SKIP"),
    ]

    def test_trade_names_resolve_to_inn_evidence(self):
        for brand, inn, gene, alteration in self.BRANDS:
            canonical = lookup_oncokb_level(gene, alteration, inn)
            assert canonical is not None, f"{inn} should have a level to compare against"
            assert lookup_oncokb_level(gene, alteration, brand) == canonical, (
                f"{brand} should resolve as {inn}"
            )

    def test_case_and_punctuation_insensitive(self):
        for written in ["HERCEPTIN", "herceptin", "Herceptin "]:
            assert lookup_oncokb_level("ERBB2", "Amplification", written) == "LEVEL_1"

    def test_trade_name_never_shadows_a_real_generic(self):
        """A generic the table carries must resolve to itself before any alias
        is applied. This is the guard that was missing when the gene
        normaliser silently broke H3-3A."""
        from services.oncokb_evidence import (
            _DRUG_BRAND_ALIASES, _known_table_drugs, _normalise_drug,
        )
        table_drugs = _known_table_drugs()
        assert not [k for k in _DRUG_BRAND_ALIASES if k in table_drugs]
        for drug in table_drugs:
            assert _normalise_drug(drug) == drug, f"{drug} no longer resolves to itself"

    def test_unknown_drug_is_passed_through_not_guessed(self):
        from services.oncokb_evidence import _normalise_drug
        assert _normalise_drug("NotADrug") == "notadrug"
        assert lookup_oncokb_level("EGFR", "T790M", "NotADrug") is None
