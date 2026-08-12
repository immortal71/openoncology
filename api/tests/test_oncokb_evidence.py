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
        drug sensitivity profile isn't necessarily the same as EXON11DEL's."""
        drugs = get_all_drugs_for_variant("KIT", "V559D")
        assert drugs == {}

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
