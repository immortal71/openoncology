"""Map a targeted-therapy drug name to the alterations it is approved for.

This is the ground truth for the MSK-CHORD benchmark (OO-29). A patient
belongs in the gold-standard subset when their record pairs a drug they
received with an alteration whose FDA label names it. The scorer uses this
map to find those pairs; the ranker itself uses OncoKB and CIViC, which this
file deliberately does not substitute.

Each entry is (drug, {gene -> alteration-matcher}). An alteration-matcher is:
  "any_mutation"           any somatic mutation of this gene qualifies.
  "amplification"           discrete CNA = Amplification.
  "deep_deletion"           discrete CNA = Deep Deletion.
  "fusion"                  a structural variant / fusion. MSK-CHORD's
                            structural-variant endpoint is not exposed, so
                            the benchmark marks fusion-only drugs
                            UNEVALUABLE rather than counting them as misses.
  A callable (protein_change, mutation_type) -> bool, for drugs with a
  specific-residue indication, e.g. KRAS G12C.

Cancer context is intentionally not encoded here, because the fetched records
already carry the cancer type and the pipeline enforces the context through
services.indication_gate. Scoring reports gene-level matches and keeps
context separate.
"""
from __future__ import annotations

from collections.abc import Callable

Matcher = str | Callable[[str, str], bool]


def _is_g12c(aa: str, _mt: str) -> bool:
    return aa.upper().replace("P.", "").startswith("G12C")


def _is_exon14_skip(aa: str, mt: str) -> bool:
    s = (aa or "").upper()
    return "EXON14" in s or "EX14" in s or "SKIP" in s or "SPLICE" in (mt or "").upper()


def _is_vhl_mutation(aa: str, _mt: str) -> bool:
    return bool(aa)


def _d816v_or_similar(aa: str, _mt: str) -> bool:
    return "D816" in (aa or "").upper()


# Drug -> {gene: matcher}. All drug names are lowercase; the agent column in
# MSK-CHORD is upper-case so the scorer lower-cases both sides.
TARGETS: dict[str, dict[str, Matcher]] = {
    # EGFR TKIs
    "erlotinib": {"EGFR": "any_mutation"},
    "gefitinib": {"EGFR": "any_mutation"},
    "afatinib": {"EGFR": "any_mutation"},
    "dacomitinib": {"EGFR": "any_mutation"},
    "osimertinib": {"EGFR": "any_mutation"},
    "rociletinib": {"EGFR": "any_mutation"},
    "mobocertinib": {"EGFR": "any_mutation"},
    # ALK/ROS1 fusion drugs; MSK-CHORD lacks the SV endpoint here, so these
    # are UNEVALUABLE when the gene's only alteration would be a fusion.
    "crizotinib": {"ALK": "fusion", "ROS1": "fusion", "MET": _is_exon14_skip},
    "alectinib": {"ALK": "fusion"},
    "brigatinib": {"ALK": "fusion"},
    "ceritinib": {"ALK": "fusion"},
    "lorlatinib": {"ALK": "fusion", "ROS1": "fusion"},
    "entrectinib": {"ROS1": "fusion", "NTRK1": "fusion", "NTRK2": "fusion", "NTRK3": "fusion"},
    "larotrectinib": {"NTRK1": "fusion", "NTRK2": "fusion", "NTRK3": "fusion"},
    # KRAS G12C
    "sotorasib": {"KRAS": _is_g12c},
    "adagrasib": {"KRAS": _is_g12c},
    # BRAF V600 (combination targets BRAF)
    "dabrafenib": {"BRAF": "any_mutation"},
    "trametinib": {"BRAF": "any_mutation"},
    "vemurafenib": {"BRAF": "any_mutation"},
    "encorafenib": {"BRAF": "any_mutation"},
    "binimetinib": {"BRAF": "any_mutation"},
    "cobimetinib": {"BRAF": "any_mutation"},
    "selumetinib": {"NF1": "any_mutation"},
    # HER2 / ERBB2
    "trastuzumab": {"ERBB2": "amplification"},
    "pertuzumab": {"ERBB2": "amplification"},
    "ado-trastuzumab emtansine": {"ERBB2": "amplification"},
    "fam-trastuzumab deruxtecan": {"ERBB2": "amplification"},
    "lapatinib": {"ERBB2": "amplification"},
    "tucatinib": {"ERBB2": "amplification"},
    "neratinib": {"ERBB2": "amplification"},
    # MET
    "capmatinib": {"MET": _is_exon14_skip},
    "tepotinib": {"MET": _is_exon14_skip},
    # RET
    "selpercatinib": {"RET": "fusion"},
    "pralsetinib": {"RET": "fusion"},
    # CDK4/6
    "palbociclib": {"CDK4": "any_mutation", "CDK6": "any_mutation", "CDKN2A": "deep_deletion"},
    "ribociclib": {"CDK4": "any_mutation", "CDK6": "any_mutation", "CDKN2A": "deep_deletion"},
    "abemaciclib": {"CDK4": "any_mutation", "CDK6": "any_mutation", "CDKN2A": "deep_deletion"},
    # PIK3CA / mTOR / AKT1
    "alpelisib": {"PIK3CA": "any_mutation"},
    "capivasertib": {"AKT1": "any_mutation", "PIK3CA": "any_mutation", "PTEN": "any_mutation"},
    "everolimus": {"MTOR": "any_mutation", "TSC1": "any_mutation", "TSC2": "any_mutation"},
    "temsirolimus": {"MTOR": "any_mutation", "TSC1": "any_mutation", "TSC2": "any_mutation"},
    # PARP (BRCA1/2 and HRR)
    "olaparib": {"BRCA1": "any_mutation", "BRCA2": "any_mutation", "ATM": "any_mutation",
                 "PALB2": "any_mutation", "CHEK2": "any_mutation"},
    "rucaparib": {"BRCA1": "any_mutation", "BRCA2": "any_mutation", "ATM": "any_mutation",
                  "PALB2": "any_mutation"},
    "niraparib": {"BRCA1": "any_mutation", "BRCA2": "any_mutation", "PALB2": "any_mutation"},
    "talazoparib": {"BRCA1": "any_mutation", "BRCA2": "any_mutation", "PALB2": "any_mutation"},
    # IDH1/2
    "ivosidenib": {"IDH1": "any_mutation"},
    "enasidenib": {"IDH2": "any_mutation"},
    # FGFR
    "erdafitinib": {"FGFR1": "any_mutation", "FGFR2": "any_mutation", "FGFR3": "any_mutation"},
    "pemigatinib": {"FGFR2": "fusion"},
    # KIT / PDGFRA (mastocytosis / GIST)
    "imatinib": {"KIT": "any_mutation", "PDGFRA": "any_mutation", "ABL1": "any_mutation"},
    "sunitinib": {"KIT": "any_mutation", "PDGFRA": "any_mutation", "VHL": _is_vhl_mutation},
    "regorafenib": {"KIT": "any_mutation", "PDGFRA": "any_mutation"},
    "ripretinib": {"KIT": "any_mutation", "PDGFRA": "any_mutation"},
    "avapritinib": {"KIT": _d816v_or_similar, "PDGFRA": "any_mutation"},
    # VHL / HIF2a
    "belzutifan": {"VHL": _is_vhl_mutation},
    # Hedgehog
    "vismodegib": {"PTCH1": "any_mutation", "SMO": "any_mutation"},
    "sonidegib": {"PTCH1": "any_mutation", "SMO": "any_mutation"},
    # BCR-ABL and related
    "dasatinib": {"ABL1": "any_mutation", "BCR": "fusion"},
    "nilotinib": {"ABL1": "any_mutation", "BCR": "fusion"},
    "ponatinib": {"ABL1": "any_mutation", "BCR": "fusion"},
    "bosutinib": {"ABL1": "any_mutation", "BCR": "fusion"},
    "asciminib": {"ABL1": "any_mutation", "BCR": "fusion"},
    # BTK
    "ibrutinib": {"BTK": "any_mutation", "MYD88": "any_mutation"},
    "acalabrutinib": {"BTK": "any_mutation"},
    "zanubrutinib": {"BTK": "any_mutation"},
    # FLT3
    "midostaurin": {"FLT3": "any_mutation", "KIT": _d816v_or_similar},
    "gilteritinib": {"FLT3": "any_mutation"},
    "quizartinib": {"FLT3": "any_mutation"},
    # JAK / Myeloproliferative
    "ruxolitinib": {"JAK2": "any_mutation", "MPL": "any_mutation"},
    "pacritinib": {"JAK2": "any_mutation"},
    # Others with a defined genetic indication
    "venetoclax": {"BCL2": "any_mutation"},
    "tazemetostat": {"EZH2": "any_mutation", "SMARCB1": "deep_deletion"},
    "selinexor": {},  # molecular target not required by label; score as context-only
    "duvelisib": {"PIK3CD": "any_mutation"},
    "idelalisib": {"PIK3CD": "any_mutation"},
    "umbralisib": {"PIK3CD": "any_mutation"},
    "carfilzomib": {},
    "ixazomib": {},
    "vorinostat": {},
    "cedazuridine-decitabine": {},
    "isotretinoin": {},
    "cabozantinib": {"VHL": _is_vhl_mutation, "MET": _is_exon14_skip, "RET": "fusion"},
    "pazopanib": {"VHL": _is_vhl_mutation},
    "sorafenib": {},
    "axitinib": {"VHL": _is_vhl_mutation},
    "lenvatinib": {},
}


FUSION_ONLY_MATCHER = "fusion"


def targeted_match(drug: str, mutations: list[dict], cnas: list[dict]) -> tuple[str, list[str]]:
    """Return ("hit"|"miss"|"unevaluable"|"unknown_drug", reasons).

    Fusion-only expectations are UNEVALUABLE here because MSK-CHORD's SV
    endpoint is not exposed; the benchmark records them so the user can
    revisit when a fusion feed is added.
    """
    rules = TARGETS.get(drug.lower())
    if rules is None:
        return "unknown_drug", [f"no target rule for drug: {drug}"]
    if not rules:
        return "unevaluable", [f"drug {drug} not selected by a tumour alteration under its label"]

    needs_fusion = any(m == FUSION_ONLY_MATCHER for m in rules.values())
    reasons: list[str] = []
    for gene, matcher in rules.items():
        if matcher == "any_mutation":
            hits = [m for m in mutations if (m.get("gene") or "").upper() == gene]
            if hits:
                reasons.append(f"{gene} mutation ({hits[0].get('protein_change') or hits[0].get('mutation_type')})")
                return "hit", reasons
        elif matcher == "amplification":
            hits = [c for c in cnas if (c.get("gene") or "").upper() == gene
                    and c.get("alteration") == "Amplification"]
            if hits:
                reasons.append(f"{gene} amplification")
                return "hit", reasons
        elif matcher == "deep_deletion":
            hits = [c for c in cnas if (c.get("gene") or "").upper() == gene
                    and c.get("alteration") == "Deep Deletion"]
            if hits:
                reasons.append(f"{gene} deep deletion")
                return "hit", reasons
        elif matcher == FUSION_ONLY_MATCHER:
            continue  # evaluated below
        elif callable(matcher):
            for m in mutations:
                if (m.get("gene") or "").upper() != gene:
                    continue
                if matcher(m.get("protein_change") or "", m.get("mutation_type") or ""):
                    reasons.append(f"{gene} {m.get('protein_change') or m.get('mutation_type')}")
                    return "hit", reasons

    if needs_fusion:
        return "unevaluable", [f"{drug} needs a fusion in {', '.join(g for g,m in rules.items() if m==FUSION_ONLY_MATCHER)}; MSK-CHORD SV endpoint not exposed"]
    return "miss", [f"no qualifying alteration for {drug}"]
