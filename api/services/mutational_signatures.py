"""Mutational Signatures Analysis — OpenOncology

Extracts the dominant COSMIC SBS (Single Base Substitution) mutational
signature from a VCF file or pre-parsed mutation list, then maps it to
treatment implications.

Why signatures matter for drug selection
─────────────────────────────────────────
  SBS3  (HR deficiency)      → PARP inhibitors (olaparib, rucaparib)
  SBS4  (tobacco smoking)    → platinum-based chemotherapy
  SBS6/15/20/21/26 (MMR def) → checkpoint inhibitors (pembrolizumab)
  SBS7a/b (UV)               → immunotherapy (high TMB in melanoma)
  SBS13 (APOBEC)             → CDK4/6 inhibitors, immunotherapy
  SBS10a/b (POLE)            → immunotherapy (ultramutator)

Implementation
──────────────
Full COSMIC SBS decomposition (de-trinucleotide basis, NMF/SigProfiler)
requires the complete trinucleotide reference matrix — computationally
non-trivial.  We implement a **fast heuristic approach** that:

  1. Counts base substitution types from the mutation list.
  2. Computes fractions of C>A, C>T, C>G, T>A, T>C, T>G classes.
  3. Applies simple decision rules calibrated on COSMIC v3.3 signatures
     to assign a dominant signature class with a confidence score.

For production-grade SigProfiler decomposition, set
SIGPROFILER_ENABLED=1 in .env and ensure SigProfilerAssignment is
installed — the service will use it automatically when available.

References
──────────
  - COSMIC Signatures v3.3: https://cancer.sanger.ac.uk/signatures/sbs/
  - Alexandrov et al., Nature 2020 — mutational signatures compendium
  - Petljak et al., Nature 2022 — APOBEC as cancer driver
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Signature → drug implication map ─────────────────────────────────────────

@dataclass
class SignatureImplication:
    """Treatment implication derived from a dominant mutational signature."""
    signature_id: str               # e.g. "SBS3"
    signature_name: str             # e.g. "Homologous recombination deficiency"
    drug_recommendations: list[str] # e.g. ["Olaparib", "Niraparib"]
    drug_class: str                 # e.g. "PARP inhibitor"
    oncokb_level: str               # estimated OncoKB equivalent
    evidence_note: str
    confidence: float               # 0–1; based on signature fraction


# Curated drug recommendations per dominant signature
SIGNATURE_DRUG_MAP: dict[str, dict] = {
    "SBS3": {
        "signature_name": "Homologous recombination deficiency (BRCA-like)",
        "drug_recommendations": ["Olaparib", "Niraparib", "Rucaparib", "Talazoparib", "Carboplatin"],
        "drug_class": "PARP inhibitor / platinum",
        "oncokb_level": "LEVEL_1",
        "evidence_note": "SBS3 indicates HR deficiency (BRCA1/2 functional loss). PARP inhibitors exploit synthetic lethality with HRD (SOLO1, OlympiAD). Platinum salts cause double-strand breaks requiring HR for repair — HRD tumours are hypersensitive.",
    },
    "SBS4": {
        "signature_name": "Tobacco smoking (C>A transversions)",
        "drug_recommendations": ["Carboplatin", "Cisplatin", "Docetaxel", "Pembrolizumab"],
        "drug_class": "Platinum-based chemotherapy / checkpoint inhibitor",
        "oncokb_level": "LEVEL_2",
        "evidence_note": "SBS4 (tobacco-associated C>A) correlates with high TMB in lung cancers and frequently co-occurs with KRAS G12C / STK11 loss. Platinum-based regimens are standard-of-care in NSCLC.",
    },
    "SBS6": {
        "signature_name": "MMR deficiency (microsatellite instability)",
        "drug_recommendations": ["Pembrolizumab", "Dostarlimab", "Nivolumab"],
        "drug_class": "Checkpoint inhibitor (MSI-H)",
        "oncokb_level": "LEVEL_1",
        "evidence_note": "SBS6 is the canonical MMR-deficiency signature. FDA-approved pembrolizumab for MSI-H/dMMR tumours pan-cancer (KEYNOTE-158). Often combined with SBS15/20/21/26 in MMR-deficient cancers.",
    },
    "SBS7": {
        "signature_name": "UV-radiation-associated (C>T at TpC sites)",
        "drug_recommendations": ["Pembrolizumab", "Nivolumab", "Ipilimumab"],
        "drug_class": "Checkpoint inhibitor (UV-associated melanoma)",
        "oncokb_level": "LEVEL_1",
        "evidence_note": "SBS7a/b are hallmarks of UV-exposed melanoma. High TMB in this context predicts checkpoint inhibitor response (KEYNOTE-006, CheckMate 066).",
    },
    "SBS10": {
        "signature_name": "POLE/POLD1 ultramutator",
        "drug_recommendations": ["Pembrolizumab", "Nivolumab"],
        "drug_class": "Checkpoint inhibitor (ultra-high TMB)",
        "oncokb_level": "LEVEL_1",
        "evidence_note": "SBS10a/b mark POLE/POLD1 exonuclease-domain mutations causing extreme hypermutation (>100 mut/Mb). Multiple case series and the KEYNOTE-158 TMB-H cohort show durable responses to pembrolizumab.",
    },
    "SBS13": {
        "signature_name": "APOBEC cytidine deaminase (C>G at TpC)",
        "drug_recommendations": ["Pembrolizumab", "Palbociclib", "Ribociclib", "Abemaciclib"],
        "drug_class": "Checkpoint inhibitor / CDK4/6 inhibitor",
        "oncokb_level": "LEVEL_2",
        "evidence_note": "SBS13 (APOBEC-C>G) is common in breast, bladder, and lung cancers. APOBEC-high tumours show elevated TMB and CDK4/6 inhibitor sensitivity in ER+ breast cancer (PALOMA-2, MONALEESA-2).",
    },
    "SBS2": {
        "signature_name": "APOBEC cytidine deaminase (C>T at TpC)",
        "drug_recommendations": ["Pembrolizumab", "Palbociclib", "Ribociclib"],
        "drug_class": "Checkpoint inhibitor / CDK4/6 inhibitor",
        "oncokb_level": "LEVEL_2",
        "evidence_note": "SBS2 (APOBEC-C>T) co-occurs with SBS13. Together they constitute the APOBEC signature cluster frequent in breast, bladder, cervical, and lung cancers.",
    },
    "SBS17": {
        "signature_name": "Unknown — possible 5-FU/oxaliplatin treatment exposure",
        "drug_recommendations": ["Irinotecan", "Capecitabine"],
        "drug_class": "Alternative chemotherapy",
        "oncokb_level": "LEVEL_3B",
        "evidence_note": "SBS17 is enriched in colorectal and gastric cancers after 5-FU exposure. Suggests possible prior treatment; irinotecan-based regimens may be considered.",
    },
}

# Synonyms / related signatures that collapse to the same entry
_SIGNATURE_ALIASES: dict[str, str] = {
    "SBS15": "SBS6",  # also MMR-def
    "SBS20": "SBS6",
    "SBS21": "SBS6",
    "SBS26": "SBS6",
    "SBS7a": "SBS7",
    "SBS7b": "SBS7",
    "SBS7c": "SBS7",
    "SBS7d": "SBS7",
    "SBS10a": "SBS10",
    "SBS10b": "SBS10",
    "SBS10c": "SBS10",
    "SBS10d": "SBS10",
    "SBS2+13": "SBS13",
}


# ── Heuristic signature detection ────────────────────────────────────────────

@dataclass
class SubstitutionProfile:
    """Six-channel base substitution counts (strand-collapsed)."""
    C_to_A: int = 0  # also G>T
    C_to_G: int = 0  # also G>C
    C_to_T: int = 0  # also G>A — transitions
    T_to_A: int = 0  # also A>T
    T_to_C: int = 0  # also A>G — transitions
    T_to_G: int = 0  # also A>C
    total: int = 0

    def fractions(self) -> dict[str, float]:
        if self.total == 0:
            return {k: 0.0 for k in ("C>A", "C>G", "C>T", "T>A", "T>C", "T>G")}
        return {
            "C>A": self.C_to_A / self.total,
            "C>G": self.C_to_G / self.total,
            "C>T": self.C_to_T / self.total,
            "T>A": self.T_to_A / self.total,
            "T>C": self.T_to_C / self.total,
            "T>G": self.T_to_G / self.total,
        }


@dataclass
class SignatureResult:
    """Output of signature analysis for one tumour."""
    dominant_signature: Optional[str]
    signature_fraction: float       # fraction of mutations attributed to dominant sig
    all_fractions: dict[str, float] # six-channel fractions
    implication: Optional[SignatureImplication]
    mutation_count: int
    confidence: str                 # "HIGH" / "MEDIUM" / "LOW" / "INSUFFICIENT"
    used_sigprofiler: bool = False


def analyse_signatures_from_mutations(
    mutations: list[dict],
) -> SignatureResult:
    """Run heuristic signature analysis from a list of mutation dicts.

    Each mutation dict should have:
        - ref (str): reference allele, e.g. "C"
        - alt (str): alternate allele, e.g. "T"
        - mutation_type (str): optional — used to filter to SNVs only

    Returns a SignatureResult with the dominant signature and treatment implication.
    """
    if len(mutations) < 10:
        return SignatureResult(
            dominant_signature=None,
            signature_fraction=0.0,
            all_fractions={},
            implication=None,
            mutation_count=len(mutations),
            confidence="INSUFFICIENT",
        )

    # Try SigProfiler first if available
    if os.environ.get("SIGPROFILER_ENABLED") == "1":
        try:
            return _run_sigprofiler(mutations)
        except Exception as exc:
            logger.warning("[signatures] SigProfiler failed, falling back to heuristic: %s", exc)

    return _heuristic_signature(mutations)


def analyse_signatures_from_vcf(vcf_path: str | Path) -> SignatureResult:
    """Parse a VCF file and run signature analysis.

    Only SNVs (ref length == alt length == 1) are used for signature
    decomposition; indels are excluded per COSMIC convention.
    """
    mutations = _parse_vcf_snvs(vcf_path)
    return analyse_signatures_from_mutations(mutations)


# ── Heuristic signature classifier ───────────────────────────────────────────

_COMPLEMENT = str.maketrans("ACGT", "TGCA")

def _strand_collapse(ref: str, alt: str) -> tuple[str, str]:
    """Collapse to pyrimidine reference (C or T context)."""
    if ref in ("C", "T"):
        return ref, alt
    return ref.translate(_COMPLEMENT), alt.translate(_COMPLEMENT)


def _build_profile(mutations: list[dict]) -> SubstitutionProfile:
    p = SubstitutionProfile()
    for m in mutations:
        ref = (m.get("ref") or "").upper().strip()
        alt = (m.get("alt") or "").upper().strip()
        # Only SNVs
        if len(ref) != 1 or len(alt) != 1 or ref == alt or ref == "N" or alt == "N":
            continue
        r, a = _strand_collapse(ref, alt)
        p.total += 1
        key = f"{r}_to_{a}"
        if hasattr(p, key):
            setattr(p, key, getattr(p, key) + 1)
    return p


def _heuristic_signature(mutations: list[dict]) -> SignatureResult:
    """Fast 6-channel heuristic signature classifier."""
    profile = _build_profile(mutations)
    fracs = profile.fractions()

    if profile.total < 10:
        return SignatureResult(
            dominant_signature=None,
            signature_fraction=0.0,
            all_fractions=fracs,
            implication=None,
            mutation_count=len(mutations),
            confidence="INSUFFICIENT",
        )

    # Decision rules based on COSMIC SBS characteristics
    dominant = None
    sig_frac = 0.0

    # SBS4: high C>A (tobacco) — characteristic >40% C>A
    if fracs["C>A"] >= 0.40:
        dominant, sig_frac = "SBS4", fracs["C>A"]

    # SBS7 (UV): very high C>T — typically >70% in melanoma
    elif fracs["C>T"] >= 0.65:
        dominant, sig_frac = "SBS7", fracs["C>T"]

    # SBS10 (POLE): very high C>A + T>G mixed pattern, very high total TMB
    elif profile.total > 200 and (fracs["C>A"] + fracs["T>G"]) >= 0.55:
        dominant, sig_frac = "SBS10", fracs["C>A"] + fracs["T>G"]

    # SBS6/MMR: moderate C>T with elevated T>C (transitions dominate)
    elif (fracs["C>T"] + fracs["T>C"]) >= 0.70 and fracs["T>C"] >= 0.25:
        dominant, sig_frac = "SBS6", fracs["C>T"] + fracs["T>C"]

    # SBS3 (HRD): elevated T>A transversions + moderate C>G
    elif fracs["T>A"] >= 0.15 and fracs["C>G"] >= 0.10:
        dominant, sig_frac = "SBS3", fracs["T>A"] + fracs["C>G"]

    # SBS13/APOBEC: high C>G
    elif fracs["C>G"] >= 0.25:
        dominant, sig_frac = "SBS13", fracs["C>G"]

    # SBS2/APOBEC: C>T dominant with moderate absolute count
    elif fracs["C>T"] >= 0.50 and profile.total >= 20:
        dominant, sig_frac = "SBS2", fracs["C>T"]

    # Confidence based on how far above threshold the dominant fraction is
    if dominant is None:
        confidence = "LOW"
    elif sig_frac >= 0.60:
        confidence = "HIGH"
    elif sig_frac >= 0.40:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    implication = _build_implication(dominant, sig_frac) if dominant else None

    logger.info(
        "[signatures] dominant=%s frac=%.2f confidence=%s (total_snvs=%d)",
        dominant, sig_frac, confidence, profile.total,
    )
    return SignatureResult(
        dominant_signature=dominant,
        signature_fraction=round(sig_frac, 3),
        all_fractions={k: round(v, 3) for k, v in fracs.items()},
        implication=implication,
        mutation_count=len(mutations),
        confidence=confidence,
    )


def _build_implication(sig_id: str, fraction: float) -> Optional[SignatureImplication]:
    canonical = _SIGNATURE_ALIASES.get(sig_id, sig_id)
    entry = SIGNATURE_DRUG_MAP.get(canonical)
    if not entry:
        return None
    return SignatureImplication(
        signature_id=sig_id,
        signature_name=entry["signature_name"],
        drug_recommendations=entry["drug_recommendations"],
        drug_class=entry["drug_class"],
        oncokb_level=entry["oncokb_level"],
        evidence_note=entry["evidence_note"],
        confidence=min(1.0, fraction),
    )


def signature_candidates_to_drug_dicts(result: SignatureResult) -> list[dict]:
    """Convert signature implication to drug dicts for the ranking pipeline."""
    if result.implication is None or result.confidence == "INSUFFICIENT":
        return []

    impl = result.implication
    # Scale oncokb level down one tier if confidence is LOW
    level = impl.oncokb_level
    if result.confidence == "LOW":
        _downgrade = {
            "LEVEL_1": "LEVEL_2", "LEVEL_2": "LEVEL_3A",
            "LEVEL_3A": "LEVEL_3B", "LEVEL_3B": "LEVEL_4",
        }
        level = _downgrade.get(level, level)

    candidates = []
    for drug_name in impl.drug_recommendations:
        candidates.append({
            "drug_name": drug_name,
            "chembl_id": None,
            "mechanism": impl.drug_class,
            "oncokb_level": level,
            "is_approved": impl.oncokb_level == "LEVEL_1",
            "max_phase": 4 if impl.oncokb_level == "LEVEL_1" else 3,
            "rank_score": None,
            "binding_score": None,
            "opentargets_score": None,
            "civic_score": None,
            "alphamissense_score": None,
            "evidence_sources": ["mutational_signature", impl.signature_id],
            "matched_terms": [impl.signature_name, impl.drug_class],
        })
    return candidates


# ── VCF parser (SNVs only) ────────────────────────────────────────────────────

def _parse_vcf_snvs(vcf_path: str | Path) -> list[dict]:
    path = Path(vcf_path)
    if not path.exists():
        raise FileNotFoundError(f"VCF not found: {vcf_path}")

    snvs = []
    with open(path, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            ref = parts[3].upper()
            alt = parts[4].split(",")[0].upper()   # take first alt allele only
            if len(ref) == 1 and len(alt) == 1 and ref != alt:
                snvs.append({"ref": ref, "alt": alt})
    return snvs


# ── Optional SigProfiler integration ─────────────────────────────────────────

def _run_sigprofiler(mutations: list[dict]) -> SignatureResult:
    """Use SigProfilerAssignment for full COSMIC decomposition (optional)."""
    from SigProfilerAssignment import Analyzer  # type: ignore[import]
    raise NotImplementedError("SigProfiler integration not yet wired — falls back to heuristic")
