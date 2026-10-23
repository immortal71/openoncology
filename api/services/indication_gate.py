"""Indication gate: is this drug indicated for this alteration, in this cancer?

WHY THIS EXISTS
---------------
Rescoring the 69-patient concordance pilot against HemOncKB (OO-25) found that
39 of the 53 picks were wrong for the patient's cancer and setting even today,
not merely early. They share causes recorded in OO-26:

    gene to drug across cancer types   avapritinib for KIT in kidney cancer,
                                       sonidegib for PTCH1/SMO in kidney cancer,
                                       afatinib for EGFR in glioblastoma
    alteration type ignored            alectinib for an ALK point mutation,
                                       adagrasib for KRAS G12V,
                                       cetuximab for KRAS-mutant colorectal
    line of therapy ignored            belzutifan first line for VHL-mutant RCC

Both tiers produce these. Tier 1's gene-level fallback hands out a gene's drug
list whatever the cancer, and Tier 2 returns every approved drug that touches
the gene. Neither asks what the drug is actually indicated for.

HOW IT DECIDES
--------------
`_RULES` maps (gene, drug) to where that drug has an FDA indication driven by
that gene: the cancer contexts, the alteration type it needs (a fusion, G12C,
MET exon 14 skipping), and for belzutifan in RCC the line of therapy. Each rule
cites the label it encodes.

A DRUG IS DROPPED ONLY ON POSITIVE EVIDENCE OF A MISMATCH
---------------------------------------------------------
Same direction as services/oncology_atc.py:

    (gene, drug) has no rule                  -> KEEP  (unknown is not evidence)
    rule, cancer context unknown              -> KEEP, unless the alteration
                                                 itself disqualifies the drug
    rule, context known and not indicated     -> DROP
    rule, alteration type does not qualify    -> DROP  (context-independent)
    RAS mutation and an anti-EGFR antibody    -> DROP  (labels require RAS
                                                 wild type)
    line of therapy known and too early       -> DROP
    line of therapy unknown                   -> KEEP, with indication_note

Dropped candidates are returned, not discarded, with `indication_exclusion`
saying why, so the report can show what was withheld.

WHAT IT DOES NOT COVER
----------------------
BRAF V600 (dabrafenib with trametinib is tumour-agnostic), ERBB2 (amplification
versus mutation versus IHC), and MTOR/TSC1/TSC2 (everolimus and temsirolimus
are approved in RCC on histology, not on the mutation) carry no rules yet.
Those are human decisions in OO-26, not omissions to fill by guessing.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

FUSION = "FUSION"
FUSION_OR_KINASE_DOMAIN = "FUSION_OR_KINASE_DOMAIN"
KRAS_G12C = "G12C"
MET_EXON14_OR_AMP = "MET_EXON14_OR_AMP"

# Kinase-domain point mutations in ALK and ROS1 arise as resistance in tumours
# that are already fusion-positive (ALK G1202R, ROS1 G2032R), so in NSCLC they
# stand in for the fusion. A point mutation outside the domain does not.
_KINASE_DOMAIN = {"ALK": (1116, 1399), "ROS1": (1945, 2222)}


@dataclass(frozen=True)
class IndicationRule:
    drugs: frozenset[str]
    contexts: Optional[frozenset[str]]
    requires: Optional[str] = None
    any_alteration_contexts: frozenset[str] = frozenset()
    min_line_by_context: tuple[tuple[str, int], ...] = ()
    adjuvant_contexts: frozenset[str] = frozenset()
    basis: str = ""


def _r(drugs, contexts, **kw) -> IndicationRule:
    return IndicationRule(
        drugs=frozenset(drugs),
        contexts=None if contexts is None else frozenset(contexts),
        **kw,
    )


_PARP = ("olaparib", "niraparib", "rucaparib", "talazoparib")
_KIT_PDGFRA_TKIS = ("avapritinib", "ripretinib", "imatinib", "sunitinib", "regorafenib")

_RULES: dict[str, tuple[IndicationRule, ...]] = {
    "ALK": (
        _r(("alectinib", "brigatinib", "ceritinib", "lorlatinib"), {"NSCLC", "ALCL"},
           requires=FUSION_OR_KINASE_DOMAIN, any_alteration_contexts=frozenset({"NEUROBLASTOMA"}),
           basis="FDA labels: ALK-positive (rearranged) NSCLC; ALCL per the project benchmark"),
        _r(("crizotinib",), {"NSCLC", "ALCL", "IMT"},
           requires=FUSION_OR_KINASE_DOMAIN, any_alteration_contexts=frozenset({"NEUROBLASTOMA"}),
           basis="FDA label: ALK-positive NSCLC, ALCL and IMT"),
    ),
    "ROS1": (
        _r(("crizotinib", "entrectinib", "repotrectinib", "lorlatinib"), {"NSCLC"},
           requires=FUSION_OR_KINASE_DOMAIN, basis="FDA labels: ROS1-positive NSCLC"),
    ),
    "NTRK1": (_r(("larotrectinib", "entrectinib", "repotrectinib"), None,
                 requires=FUSION, basis="FDA labels: NTRK gene fusion, any solid tumour"),),
    "NTRK2": (_r(("larotrectinib", "entrectinib", "repotrectinib"), None,
                 requires=FUSION, basis="FDA labels: NTRK gene fusion, any solid tumour"),),
    "NTRK3": (_r(("larotrectinib", "entrectinib", "repotrectinib"), None,
                 requires=FUSION, basis="FDA labels: NTRK gene fusion, any solid tumour"),),
    "RET": (
        _r(("selpercatinib", "pralsetinib"), None, requires=FUSION,
           any_alteration_contexts=frozenset({"MTC", "THYROID"}),
           basis="FDA labels: RET fusion-positive tumours; RET-mutant MTC"),
    ),
    "MET": (
        _r(("capmatinib", "tepotinib"), {"NSCLC", "GASTRIC"}, requires=MET_EXON14_OR_AMP,
           basis="FDA labels: NSCLC with MET exon 14 skipping; amplification is off-label"),
    ),
    "KRAS": (
        _r(("sotorasib", "adagrasib"), {"NSCLC", "COLORECTAL", "PANCREATIC"}, requires=KRAS_G12C,
           basis="FDA labels: KRAS G12C-mutated NSCLC and colorectal cancer; pancreatic per NCCN"),
        _r(("cetuximab", "panitumumab"), {"COLORECTAL"}, requires=KRAS_G12C,
           basis=("FDA labels: RAS wild-type colorectal cancer, or KRAS G12C colorectal "
                  "cancer in combination with a G12C inhibitor")),
    ),
    "NRAS": (
        _r(("cetuximab", "panitumumab"), frozenset(),
           basis="FDA labels: colorectal use limited to RAS wild-type tumours"),
    ),
    "EGFR": (
        _r(("erlotinib", "gefitinib"), {"NSCLC", "GLIOMA"},
           basis="FDA labels: EGFR-mutated NSCLC; glioma per the project benchmark"),
        _r(("afatinib",), {"NSCLC", "HNSCC"},
           basis="FDA label: EGFR-mutated NSCLC; HNSCC per the project benchmark"),
        _r(("dacomitinib", "osimertinib", "amivantamab", "lazertinib", "sunvozertinib"), {"NSCLC"},
           basis="FDA labels: EGFR-mutated NSCLC"),
    ),
    "SMO": (_r(("vismodegib", "sonidegib"), {"BCC"},
               basis="FDA labels: basal cell carcinoma"),),
    "PTCH1": (_r(("vismodegib", "sonidegib"), {"BCC"},
                 basis="FDA labels: basal cell carcinoma"),),
    "PIK3CA": (
        _r(("alpelisib",), {"BREAST", "CERVICAL", "ENDOMETRIAL", "COLORECTAL"},
           basis="FDA label: PIK3CA-mutated HR+/HER2- breast cancer; others per the project benchmark"),
        _r(("capivasertib", "inavolisib"), {"BREAST"},
           basis="FDA labels: PIK3CA-mutated HR+/HER2- breast cancer"),
    ),
    "AKT1": (_r(("capivasertib",), {"BREAST", "NSCLC"},
                basis="FDA label: AKT1/PIK3CA/PTEN-altered breast cancer; NSCLC per the project benchmark"),),
    "PTEN": (_r(("capivasertib",), {"BREAST", "ENDOMETRIAL"},
                basis="FDA label: AKT1/PIK3CA/PTEN-altered breast cancer; endometrial per the project benchmark"),),
    "ESR1": (_r(("elacestrant",), {"BREAST"},
                basis="FDA label: ESR1-mutated breast cancer"),),
    "KIT": (
        _r(("imatinib",), {"GIST", "MELANOMA", "MASTOCYTOSIS"},
           basis="FDA label: KIT-positive GIST and systemic mastocytosis; melanoma per OncoKB"),
        _r(("avapritinib",), {"GIST", "MASTOCYTOSIS"},
           basis="FDA label: GIST and systemic mastocytosis"),
        _r(("ripretinib", "sunitinib", "regorafenib"), {"GIST"},
           basis="FDA labels: KIT-driven GIST"),
        _r(("dasatinib", "nilotinib"), {"MELANOMA"},
           basis="No FDA indication driven by KIT; melanoma per NCCN"),
    ),
    "PDGFRA": (
        _r(_KIT_PDGFRA_TKIS, {"GIST"},
           basis="FDA labels: PDGFRA-mutated GIST"),
    ),
    "VHL": (
        _r(("belzutifan",), {"RCC", "VHL_DISEASE"},
           min_line_by_context=(("RCC", 2),),
           adjuvant_contexts=frozenset({"RCC"}),
           basis=("FDA label: advanced RCC after a PD-1/PD-L1 inhibitor and a "
                  "VEGF-TKI; germline von Hippel-Lindau disease")),
    ),
    "IDH1": (
        _r(("ivosidenib",), {"AML", "MDS", "CHOLANGIO", "GLIOMA", "LOW_GRADE_GLIOMA"},
           basis="FDA label: IDH1-mutated AML, MDS and cholangiocarcinoma; glioma per NCCN"),
        _r(("olutasidenib",), {"AML", "MDS"}, basis="FDA label: IDH1-mutated AML"),
        _r(("vorasidenib",), {"GLIOMA", "LOW_GRADE_GLIOMA", "AML"},
           basis="FDA label: IDH-mutant grade 2 glioma; AML per the project benchmark"),
    ),
    "IDH2": (
        _r(("enasidenib",), {"AML", "MDS", "GLIOMA", "LOW_GRADE_GLIOMA", "CHOLANGIO"},
           basis="FDA label: IDH2-mutated AML; others per the project benchmark"),
        _r(("vorasidenib",), {"GLIOMA", "LOW_GRADE_GLIOMA"},
           basis="FDA label: IDH-mutant grade 2 glioma"),
    ),
    "FGFR2": (
        _r(("pemigatinib", "futibatinib"), {"CHOLANGIO", "GASTRIC"},
           basis="FDA labels: FGFR2 fusion-positive cholangiocarcinoma; amplification per the project benchmark"),
        _r(("erdafitinib",), {"BLADDER", "CHOLANGIO"},
           basis="FDA label: FGFR-altered urothelial cancer; cholangiocarcinoma per the project benchmark"),
    ),
    "FGFR3": (
        _r(("erdafitinib",), {"BLADDER"}, basis="FDA label: FGFR3-altered urothelial cancer"),
    ),
    "BRCA1": (_r(_PARP, {"BREAST", "OVARIAN", "PROSTATE", "PANCREATIC"},
                 basis="FDA labels: BRCA-mutated breast, ovarian, prostate, pancreatic"),),
    "BRCA2": (_r(_PARP, {"BREAST", "OVARIAN", "PROSTATE", "PANCREATIC"},
                 basis="FDA labels: BRCA-mutated breast, ovarian, prostate, pancreatic"),),
}

_EXTRA_CONTEXTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gastrointestinal stromal|\bgist\b"), "GIST"),
    (re.compile(r"mastocytosis"), "MASTOCYTOSIS"),
    (re.compile(r"inflammatory myofibroblastic|\bimt\b"), "IMT"),
    (re.compile(r"von hippel|\bvhl disease\b"), "VHL_DISEASE"),
    (re.compile(r"myelodysplastic|\bmds\b"), "MDS"),
)

_SALT_WORDS = frozenset({
    "hydrochloride", "dihydrochloride", "mesylate", "maleate", "dimaleate",
    "tosylate", "malate", "s-malate", "citrate", "sulfate", "phosphate",
    "sodium", "potassium", "anhydrous", "hydrate", "monohydrate",
})


def _drug_key(name: str) -> str:
    words = re.sub(r"[^a-z0-9\- ]", " ", (name or "").lower()).split()
    while len(words) > 1 and words[-1] in _SALT_WORDS:
        words.pop()
    return " ".join(words)


def indication_context(cancer_type: Optional[str]) -> Optional[str]:
    """Cancer context for indication matching.

    Extends services.oncokb_evidence._normalise_cancer_context with contexts
    that function does not name (GIST, mastocytosis, IMT, VHL disease, MDS),
    checked first so a GIST of the stomach is not read as gastric cancer.
    """
    if not cancer_type:
        return None
    s = str(cancer_type).strip().lower()
    for pattern, context in _EXTRA_CONTEXTS:
        if pattern.search(s):
            return context
    from services.oncokb_evidence import _normalise_cancer_context

    return _normalise_cancer_context(cancer_type)


def _is_fusion(alt: str) -> bool:
    if any(t in alt for t in ("FUSION", "REARRANGEMENT", "TRANSLOCATION", "::")):
        return True
    parts = alt.split("-")
    return len(parts) == 2 and all(re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", p) for p in parts)


def _alteration_qualifies(requires: Optional[str], alteration: str, gene: str) -> bool:
    if requires is None:
        return True
    alt = re.sub(r"^P\.", "", (alteration or "").strip().upper())
    if requires == FUSION:
        return _is_fusion(alt)
    if requires == FUSION_OR_KINASE_DOMAIN:
        if _is_fusion(alt):
            return True
        m = re.fullmatch(r"[A-Z](\d+)[A-Z]", alt)
        span = _KINASE_DOMAIN.get(gene)
        return bool(m and span and span[0] <= int(m.group(1)) <= span[1])
    if requires == KRAS_G12C:
        return alt.startswith("G12C") or alt == "GLY12CYS"
    if requires == MET_EXON14_OR_AMP:
        compact = alt.replace(" ", "").replace("_", "")
        if any(t in compact for t in ("EXON14", "EX14", "AMPLIFICATION", "AMP")):
            return True
        from services.oncokb_evidence import _is_met_exon14_splice, _normalise_alteration

        return _is_met_exon14_splice(_normalise_alteration(alteration).upper())
    return True


def evaluate(
    drug_name: str,
    gene: str,
    alteration: str,
    cancer_type: Optional[str],
    *,
    line_of_therapy: Optional[int] = None,
    intent: Optional[str] = None,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Return (keep, exclusion_reason, note) for one drug.

    exclusion_reason is set only when keep is False. note is set when the drug
    is kept but its indication depends on something the caller did not supply.
    """
    rules = _RULES.get((gene or "").strip().upper())
    if not rules:
        return True, None, None
    key = _drug_key(drug_name)
    rule = next((r for r in rules if key in r.drugs), None)
    if rule is None:
        return True, None, None

    context = indication_context(cancer_type)

    if rule.contexts is not None and not rule.contexts:
        return False, f"{rule.basis}; not indicated for a {gene.upper()} alteration", None

    if context is not None and context in rule.any_alteration_contexts:
        return True, None, None

    if not _alteration_qualifies(rule.requires, alteration, (gene or "").strip().upper()):
        return False, f"{rule.basis}; {alteration} does not meet the {rule.requires} requirement", None

    if rule.contexts is not None:
        if context is None:
            return True, None, f"Indicated only in: {', '.join(sorted(rule.contexts))}; cancer type not recognised"
        if context not in rule.contexts:
            return False, f"{rule.basis}; not indicated in {context}", None

    min_line = dict(rule.min_line_by_context).get(context or "")
    if min_line is not None:
        adjuvant = (intent or "").strip().lower() in {"adjuvant", "curative"}
        if adjuvant and context in rule.adjuvant_contexts:
            return True, None, "Adjuvant use is approved only in combination; check the label"
        if line_of_therapy is None:
            return True, None, f"In {context}, indicated from line {min_line}; line of therapy not supplied"
        if line_of_therapy < min_line:
            return False, f"{rule.basis}; line {line_of_therapy} is before line {min_line}", None

    return True, None, None


def partition_candidates(
    candidates: Iterable[dict[str, Any]],
    gene: str,
    alteration: str,
    cancer_type: Optional[str],
    *,
    line_of_therapy: Optional[int] = None,
    intent: Optional[str] = None,
    name_key: str = "drug_name",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split candidates into (indicated_or_unknown, excluded)."""
    keep: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for candidate in candidates:
        ok, reason, note = evaluate(
            candidate.get(name_key) or "",
            gene,
            alteration,
            cancer_type,
            line_of_therapy=line_of_therapy,
            intent=intent,
        )
        if ok:
            keep.append({**candidate, "indication_note": note} if note else candidate)
        else:
            dropped.append({**candidate, "indication_exclusion": reason})
    if dropped:
        logger.info(
            "[indication] withheld %d candidate(s) for %s %s in %s: %s",
            len(dropped), gene, alteration, cancer_type,
            ", ".join(d.get(name_key, "?") for d in dropped[:5]),
        )
    return keep, dropped
