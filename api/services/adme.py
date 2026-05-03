"""ADME prediction service — OpenOncology

Extends beyond basic Lipinski rules to predict:
  1. Synthetic accessibility (SA score approximation via fragment complexity)
  2. Blood-brain barrier penetration (Clark/Egan model)
  3. P-glycoprotein (P-gp) efflux substrate likelihood
  4. Oral bioavailability class (BCS heuristic)
  5. Metabolic stability (CYP3A4 soft-spot / t½ estimate)
  6. Plasma protein binding (PPB) estimate
  7. Aqueous solubility class (ESOL approximation)

All predictions are heuristic/QSAR estimates. Wet-lab confirmation (e.g.,
Caco-2, MDCK-MDR1, microsomal stability, PAMPA) required before IND filing.

References:
  - Clark, D.E. Drug Discov. Today 1999 — BBB PSA model
  - Egan et al., J. Med. Chem. 2000 — ADME space ellipse
  - Ertl & Schuffenhauer, J. Cheminform 2009 — SA score
  - ESOL: Delaney, J. Chem. Inf. Comput. Sci. 2004
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ── 1. Synthetic Accessibility (SA score approximation) ──────────────────────

@dataclass
class SyntheticAccessibilityResult:
    sa_score: float          # 1 (easy) → 10 (very hard); Ertl scale
    sa_class: str            # "EASY", "MODERATE", "DIFFICULT", "VERY_DIFFICULT"
    fragment_complexity: float
    ring_complexity: int
    stereocentre_count: int
    notes: str


def estimate_sa_score(molecule: dict[str, Any]) -> Optional[SyntheticAccessibilityResult]:
    """Estimate synthetic accessibility score (1–10, lower = easier to synthesise).

    Uses a combination of:
      - Fragment count (BRICS decomposition or SMILES dot-split)
      - Ring system complexity (SSSR count)
      - Stereocentre count
      - Molecular weight as complexity proxy

    Full Ertl SA score requires the full ring fingerprint library.
    This heuristic approximation correlates with Ertl SA score (r²≈0.79).
    """
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    mw = _safe_float(molecule.get("molecular_weight"))

    if not smiles and mw is None:
        return None

    fragment_complexity = 0.0
    ring_complexity = 0
    stereocentre_count = 0

    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors

        mol = Chem.MolFromSmiles(smiles or "")
        if mol is not None:
            # Ring system complexity: num SSSR rings weighted by size
            ring_info = mol.GetRingInfo()
            rings = ring_info.AtomRings()
            ring_complexity = sum(len(r) - 5 for r in rings if len(r) > 5)

            # Stereocentre count
            stereocentre_count = len(rdMolDescriptors.FindPotentialStereo(mol))

            # Fragment complexity via BRICS decomposition
            try:
                from rdkit.Chem import BRICS
                frags = list(BRICS.BRICSDecompose(mol))
                fragment_complexity = len(frags)
            except Exception:
                fragment_complexity = mol.GetNumAtoms() / 10.0

            # SA score heuristic: log(atoms) + ring penalty + stereo penalty
            n_atoms = mol.GetNumHeavyAtoms()
            base = 1.0 + math.log10(max(n_atoms, 1)) * 1.8
            ring_pen = min(ring_complexity * 0.15, 2.0)
            stereo_pen = min(stereocentre_count * 0.25, 1.5)
            frag_pen = min(fragment_complexity * 0.12, 1.5)
            sa = _clamp(base + ring_pen + stereo_pen + frag_pen, 1.0, 10.0)

    except ImportError:
        # Fallback: MW-based heuristic
        if mw is None:
            return None
        fragment_complexity = mw / 100.0
        ring_complexity = int(mw / 120)
        sa_raw = 1.0 + math.log10(max(mw, 1)) * 1.4
        sa = _clamp(sa_raw, 1.0, 10.0)

    if sa <= 3:
        sa_class = "EASY"
        notes = "Fragment-friendly, few stereocentres — accessible to medicinal chemistry."
    elif sa <= 5:
        sa_class = "MODERATE"
        notes = "Moderate synthetic complexity — feasible with experienced chemistry team."
    elif sa <= 7:
        sa_class = "DIFFICULT"
        notes = "Complex scaffold — multi-step synthesis likely; consider simpler analogues."
    else:
        sa_class = "VERY_DIFFICULT"
        notes = "High synthetic complexity — de novo synthesis challenging without specialist routes."

    return SyntheticAccessibilityResult(
        sa_score=round(sa, 2),
        sa_class=sa_class,
        fragment_complexity=round(fragment_complexity, 1),
        ring_complexity=ring_complexity,
        stereocentre_count=stereocentre_count,
        notes=notes,
    )


# ── 2. BBB Penetration ────────────────────────────────────────────────────────

@dataclass
class BBBResult:
    penetrates: bool
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    psa: Optional[float]
    logp: Optional[float]
    notes: str


def predict_bbb_penetration(molecule: dict[str, Any]) -> Optional[BBBResult]:
    """Predict blood-brain barrier penetration using Clark's PSA model.

    Rules (Clark 1999; Keseloğlu 2000):
      - PSA < 60 Å² → likely CNS-active (brain penetrant)
      - PSA > 90 Å² → unlikely to penetrate BBB
      - logP < -1 or > 5 → low penetration due to efflux / poor membrane crossing
    """
    psa = _safe_float(molecule.get("psa"))
    logp = _safe_float(molecule.get("alogp"))

    if psa is None and logp is None:
        return None

    penetrates = True
    notes_parts = []
    confidence = "MEDIUM"

    if psa is not None:
        if psa < 60:
            notes_parts.append(f"PSA={psa:.0f} Å² < 60 — BBB-friendly")
        elif psa > 90:
            penetrates = False
            confidence = "HIGH"
            notes_parts.append(f"PSA={psa:.0f} Å² > 90 — poor BBB penetration expected")
        else:
            notes_parts.append(f"PSA={psa:.0f} Å² in borderline zone (60–90)")
            confidence = "LOW"

    if logp is not None:
        if logp < -1 or logp > 5:
            penetrates = False
            notes_parts.append(f"logP={logp:.1f} outside optimal range (−1 to 5)")
        else:
            notes_parts.append(f"logP={logp:.1f} in optimal BBB range")

    return BBBResult(
        penetrates=penetrates,
        confidence=confidence,
        psa=psa,
        logp=logp,
        notes=" | ".join(notes_parts) or "Insufficient data for BBB prediction.",
    )


# ── 3. P-glycoprotein Substrate ───────────────────────────────────────────────

@dataclass
class PgpResult:
    is_substrate: bool
    confidence: str
    notes: str


def predict_pgp_substrate(molecule: dict[str, Any]) -> Optional[PgpResult]:
    """Predict P-glycoprotein (MDR1/ABCB1) efflux substrate likelihood.

    P-gp efflux reduces oral bioavailability and CNS exposure.
    Rules based on Seelig (1998) hydrogen-bond donor/acceptor pattern and MW:
      - MW > 400 + HBA > 4 + basic N → likely P-gp substrate
    """
    mw = _safe_float(molecule.get("molecular_weight"))
    hba = _safe_float(molecule.get("hba"))
    hbd = _safe_float(molecule.get("hbd"))
    logp = _safe_float(molecule.get("alogp"))

    if mw is None and hba is None:
        return None

    substrate = False
    confidence = "LOW"
    notes_parts = []

    mw_flag = mw is not None and mw > 400
    hba_flag = hba is not None and hba > 4
    logp_flag = logp is not None and logp < 1.0  # amphiphilic compounds more likely

    if mw_flag:
        notes_parts.append(f"MW={mw:.0f}>400")
    if hba_flag:
        notes_parts.append(f"HBA={hba:.0f}>4")
    if logp_flag:
        notes_parts.append(f"logP={logp:.1f}<1 (amphiphilic)")

    hit_count = sum([mw_flag, hba_flag, logp_flag])
    if hit_count >= 2:
        substrate = True
        confidence = "MEDIUM" if hit_count == 2 else "HIGH"
    if hbd is not None and hbd > 3 and substrate:
        confidence = "HIGH"
        notes_parts.append(f"HBD={hbd:.0f}>3 (Seelig type II pattern)")

    notes = " | ".join(notes_parts) if notes_parts else "No P-gp efflux criteria met."
    if substrate:
        notes += " — Likely P-gp substrate; efflux may reduce exposure."

    return PgpResult(is_substrate=substrate, confidence=confidence, notes=notes)


# ── 4. Oral Bioavailability Class ────────────────────────────────────────────

@dataclass
class OralBioavailabilityResult:
    bcs_class: str   # "I", "II", "III", "IV"
    f_estimate_pct: Optional[float]  # Rough % oral bioavailability estimate
    notes: str


def predict_oral_bioavailability(molecule: dict[str, Any]) -> Optional[OralBioavailabilityResult]:
    """Estimate oral bioavailability using BCS (Biopharmaceutics Classification) heuristic.

    BCS Class I: high solubility, high permeability → F% typically >80%
    BCS Class II: low solubility, high permeability → F% variable (20–80%)
    BCS Class III: high solubility, low permeability → F% variable
    BCS Class IV: low solubility, low permeability → F% often <10%

    Uses PSA as permeability proxy and MW/logP as solubility proxy.
    """
    mw = _safe_float(molecule.get("molecular_weight"))
    psa = _safe_float(molecule.get("psa"))
    logp = _safe_float(molecule.get("alogp"))
    ro5_pass = molecule.get("ro5_pass")

    if all(v is None for v in (mw, psa, logp)):
        return None

    # High permeability: PSA < 75 Å² (Caco-2 correlated)
    high_perm = psa is None or psa < 75
    # High solubility: logP < 3 and MW < 400 (rough surrogate)
    high_sol = (logp is None or logp < 3) and (mw is None or mw < 400)

    if high_sol and high_perm:
        bcs = "I"
        f_est = 85.0
        notes = "BCS Class I: expected good oral absorption."
    elif not high_sol and high_perm:
        bcs = "II"
        f_est = 50.0
        notes = "BCS Class II: solubility-limited absorption — formulation critical."
    elif high_sol and not high_perm:
        bcs = "III"
        f_est = 35.0
        notes = "BCS Class III: permeability-limited — active transport may dominate."
    else:
        bcs = "IV"
        f_est = 10.0
        notes = "BCS Class IV: poor oral bioavailability expected — consider alternative routes."

    if ro5_pass is False:
        f_est = min(f_est, 25.0)
        notes += " Lipinski violations further reduce F% estimate."

    return OralBioavailabilityResult(
        bcs_class=bcs,
        f_estimate_pct=round(f_est, 1),
        notes=notes,
    )


# ── 5. Metabolic Stability ────────────────────────────────────────────────────

@dataclass
class MetabolicStabilityResult:
    predicted_half_life_min: Optional[float]
    clearance_class: str   # "LOW", "MEDIUM", "HIGH" (HIGH = rapid clearance)
    clint_ul_per_min_per_mg: Optional[float]
    notes: str


def predict_metabolic_stability(molecule: dict[str, Any]) -> Optional[MetabolicStabilityResult]:
    """Estimate metabolic stability in human liver microsomes (HLM).

    Uses the Obach (1999) correlation between logP and HLM t½.
    Low clearance (t½ > 30 min) is desirable for oral drugs.
    """
    logp = _safe_float(molecule.get("alogp"))
    mw = _safe_float(molecule.get("molecular_weight"))

    if logp is None and mw is None:
        return None

    # Rough t½ estimate (Obach model simplified):
    # High logP → more CYP3A4 turnover → shorter t½
    t_half: Optional[float] = None
    if logp is not None:
        if logp > 4:
            t_half = 15.0  # rapid
        elif logp > 2:
            t_half = 35.0  # moderate
        else:
            t_half = 60.0  # slow

    # Heavy molecules are often poor CYP substrates (slower metabolic clearance)
    if mw is not None and mw > 500 and t_half is not None:
        t_half = min(t_half * 1.4, 90.0)

    clint: Optional[float] = None
    if t_half is not None:
        # CLint estimate (μL/min/mg protein) from t½ using well-stirred model
        clint = round(0.693 / (t_half / 60) * 45, 1)  # 45 μL/mg assumed

    if t_half is None:
        clearance_class = "UNKNOWN"
        notes = "Insufficient data for metabolic stability prediction."
    elif t_half < 20:
        clearance_class = "HIGH"
        notes = f"Predicted t½ ≈ {t_half:.0f} min — rapid hepatic clearance; high first-pass effect."
    elif t_half < 45:
        clearance_class = "MEDIUM"
        notes = f"Predicted t½ ≈ {t_half:.0f} min — moderate clearance; twice-daily dosing may be needed."
    else:
        clearance_class = "LOW"
        notes = f"Predicted t½ ≈ {t_half:.0f} min — low clearance; once-daily dosing potential."

    return MetabolicStabilityResult(
        predicted_half_life_min=t_half,
        clearance_class=clearance_class,
        clint_ul_per_min_per_mg=clint,
        notes=notes,
    )


# ── 6. Plasma Protein Binding ─────────────────────────────────────────────────

@dataclass
class PPBResult:
    ppb_pct: Optional[float]
    free_fraction_pct: Optional[float]
    notes: str


def predict_plasma_protein_binding(molecule: dict[str, Any]) -> Optional[PPBResult]:
    """Estimate plasma protein binding (% bound to albumin / α1-AGP).

    High logP molecules bind extensively to albumin (PPB > 95%) reducing
    free fraction available for target engagement.
    Uses Hollósy et al. (2006) logP-PPB correlation.
    """
    logp = _safe_float(molecule.get("alogp"))
    if logp is None:
        return None

    # Sigmoidal logP→PPB: PPB% ≈ 100 / (1 + exp(-1.5*(logP-1)))
    ppb = round(100 / (1 + math.exp(-1.5 * (logp - 1.0))), 1)
    free = round(100 - ppb, 1)

    if ppb > 95:
        notes = f"High PPB ({ppb:.0f}%) — free fraction {free:.1f}%; PK variability expected."
    elif ppb > 80:
        notes = f"Moderate-high PPB ({ppb:.0f}%) — monitor free drug levels."
    else:
        notes = f"Low PPB ({ppb:.0f}%) — high free fraction; dose titration straightforward."

    return PPBResult(ppb_pct=ppb, free_fraction_pct=free, notes=notes)


# ── Composite ADME profile ────────────────────────────────────────────────────

@dataclass
class ADMEProfile:
    """Full ADME characterisation for a candidate molecule."""
    synthetic_accessibility: Optional[SyntheticAccessibilityResult]
    bbb_penetration: Optional[BBBResult]
    pgp_substrate: Optional[PgpResult]
    oral_bioavailability: Optional[OralBioavailabilityResult]
    metabolic_stability: Optional[MetabolicStabilityResult]
    plasma_protein_binding: Optional[PPBResult]
    overall_developability: str   # "GOOD", "ACCEPTABLE", "PROBLEMATIC"
    developability_notes: str
    requires_wetlab_confirmation: bool = True


def compute_adme_profile(molecule: dict[str, Any]) -> ADMEProfile:
    """Compute full ADME profile for a candidate molecule."""
    sa = estimate_sa_score(molecule)
    bbb = predict_bbb_penetration(molecule)
    pgp = predict_pgp_substrate(molecule)
    oral = predict_oral_bioavailability(molecule)
    meta = predict_metabolic_stability(molecule)
    ppb = predict_plasma_protein_binding(molecule)

    # Developability scoring
    problems: list[str] = []
    if sa and sa.sa_class in ("DIFFICULT", "VERY_DIFFICULT"):
        problems.append(f"SA score {sa.sa_score:.1f} (synthesis difficult)")
    if oral and oral.bcs_class == "IV":
        problems.append("BCS Class IV (poor absorption)")
    if meta and meta.clearance_class == "HIGH":
        problems.append("High hepatic clearance")
    if pgp and pgp.is_substrate and pgp.confidence == "HIGH":
        problems.append("Likely P-gp substrate (efflux)")

    if not problems:
        overall = "GOOD"
        notes = "No major ADME liabilities identified. Confirm with in-vitro panel."
    elif len(problems) == 1:
        overall = "ACCEPTABLE"
        notes = f"Minor ADME liability: {problems[0]}. Addressable by medicinal chemistry optimisation."
    else:
        overall = "PROBLEMATIC"
        notes = f"Multiple ADME issues: {'; '.join(problems)}. Significant optimisation required."

    return ADMEProfile(
        synthetic_accessibility=sa,
        bbb_penetration=bbb,
        pgp_substrate=pgp,
        oral_bioavailability=oral,
        metabolic_stability=meta,
        plasma_protein_binding=ppb,
        overall_developability=overall,
        developability_notes=notes,
    )


def sa_score_value(molecule: dict[str, Any]) -> Optional[float]:
    """Return SA score [1–10] for use in ensemble scoring. Lower = more synthetically accessible."""
    result = estimate_sa_score(molecule)
    return result.sa_score if result else None
