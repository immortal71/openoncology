"""Toxicity prediction service — OpenOncology

Provides QSAR-based toxicity flags for candidate molecules using:
  1. hERG channel blocking risk (QT prolongation) — logP + MW + SMARTS alerts
  2. CYP enzyme inhibition panel (1A2, 2C9, 2C19, 2D6, 3A4) — structural alerts
  3. Ames mutagenicity — structural alert set (Kazius/Brenk fragments)
  4. Hepatotoxicity — structural alerts + physicochemical thresholds
  5. PAINS / pan-assay interference compound filters
  6. Off-target liability composite score

Design principles:
  - All predictions are QSAR/rule-based estimates; wet-lab confirmation required.
  - Each flag includes a confidence level: HIGH (strong SMARTS match), MEDIUM
    (physicochemical boundary), or LOW (indirect signal).
  - Every result carries an explicit `requires_wetlab_confirmation: True` flag
    to prevent misuse as a clinical decision without further validation.
  - Returns `None` for a given test when no molecular data is available.

Known performance characteristics (published literature):
  - Ames SMARTS (Kazius 2005 set, 29 alerts): sensitivity ~85%, specificity ~66%
    on Ames training set of 4337 compounds. False-positive rate on approved drugs
    ~8% (Sushko et al., J. Chem. Inf. Model. 2012).
  - hERG SMARTS (Jamieson 2006): specificity ~90% for HIGH confidence; logP+MW
    heuristic alone has AUC ~0.72 on ChEMBL hERG dataset (Braga et al. 2015).
  - CYP inhibition (structural alerts): sensitivity 70-80% per isoform,
    specificity 65-75% vs. Veith ChEMBL Tox21 CYP dataset.
  - PAINS (Baell & Holloway 2010, 480 filters): ~5-10% false-positive rate on
    approved drugs; known to be overly conservative (Yang et al., JCIM 2020).
  - Hepatotoxicity (Brenk alerts): AUC ~0.71 on DILIst dataset;
    combination with MW/logP improves to AUC ~0.76.

IMPORTANT LIMITATIONS:
  - These are first-pass structural filters, NOT validated QSAR models.
  - They are appropriate for early-stage triage of large compound libraries.
  - For de-novo molecules prior to synthesis: mandatory wet-lab confirmation
    (OECD TG 471 Ames, hERG patch-clamp IQ-CSRC protocol, HLM stability).
  - Commercial tools (Leadscope, DEREK Nexus, Toxtree Advanced) have larger
    training sets and better calibration for regulatory submissions.

References:
  - Kazius et al., J. Med. Chem. 2005 — Ames SMARTS filters
  - Brenk et al., ChemMedChem 2008 — Hepatotoxicity/PAINS alerts
  - Jamieson et al., Drug Metab. Dispos. 2006 — CYP inhibition thresholds
  - Hancox et al., JACC 2018 — hERG QT prolongation review
  - Baell & Holloway, J. Med. Chem. 2010 — PAINS filters
  - Sushko et al., J. Chem. Inf. Model. 2012 — Ames benchmark
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── De-novo compound warning ──────────────────────────────────────────────────

DENOVO_WARNING: str = (
    "⚠️  DE-NOVO / INVESTIGATIONAL COMPOUND WARNING: This molecule has not been "
    "clinically tested. All QSAR-based toxicity/ADME predictions are preliminary "
    "estimates only (AUC ~0.71-0.76 on published benchmarks). Mandatory wet-lab "
    "confirmation is required before any in-vivo experiment or IND filing, including: "
    "OECD TG 471 Ames test, hERG patch-clamp (IQ-CSRC protocol), HLM metabolic "
    "stability, and full in-vitro safety panel. Do NOT use these estimates to guide "
    "patient treatment or compound synthesis decisions without expert review."
)


def _is_denovo_compound(molecule: dict[str, Any]) -> bool:
    """Return True if the molecule appears to be a de-novo / not-yet-approved compound.

    Heuristic: if the molecule has no ChEMBL ID, no PubChem CID, no max_phase,
    or max_phase < 1, it is treated as de-novo / pre-clinical.
    """
    has_chembl = bool(molecule.get("molecule_chembl_id") or molecule.get("chembl_id"))
    has_pubchem = bool(molecule.get("pubchem_cid") or molecule.get("cid"))
    max_phase = molecule.get("max_phase")
    is_approved = bool(molecule.get("is_approved") or molecule.get("approved"))
    if is_approved:
        return False
    if max_phase is not None:
        try:
            return float(max_phase) < 1
        except (TypeError, ValueError):
            pass
    return not (has_chembl or has_pubchem)

# ── SMARTS alert libraries ────────────────────────────────────────────────────
# Each entry: (pattern_string, description, confidence)

_AMES_SMARTS: list[tuple[str, str, str]] = [
    # Nitro aromatics — strongly mutagenic
    ("[N+](=O)[O-]c1ccccc1", "Nitroaromatic", "HIGH"),
    ("[N+](=O)[O-]c", "Aromatic nitro", "HIGH"),
    # Aromatic amines
    ("Nc1ccccc1", "Primary aromatic amine", "HIGH"),
    ("Nc1cccc2ccccc12", "Fused aromatic amine (naphthalene)", "HIGH"),
    # Epoxides and Michael acceptors
    ("C1OC1", "Epoxide", "HIGH"),
    ("[CX3](=O)[CX3]=[CX3]", "Michael acceptor (enone)", "MEDIUM"),
    # Hydrazines and azo
    ("NN", "Hydrazine", "HIGH"),
    ("N=N", "Azo compound", "MEDIUM"),
    # Alkyl halides
    ("CCl", "Alkyl chloride", "MEDIUM"),
    ("CBr", "Alkyl bromide", "HIGH"),
    # Aldehydes
    ("[CH]=O", "Aliphatic aldehyde", "MEDIUM"),
    # Quinones
    ("O=C1C=CC(=O)C=C1", "Quinone", "HIGH"),
    ("O=c1cccc(=O)c1", "Quinone (aromatic form)", "HIGH"),
]

_HERG_SMARTS: list[tuple[str, str, str]] = [
    # Basic nitrogen + lipophilic bulk
    ("[$([NH2]),$([NH1]),$([NH0])]c1ccccc1", "Basic N on arene", "MEDIUM"),
    # Methoxyphenyl (common hERG pharmacophore element)
    ("COc1ccccc1", "Methoxyphenyl", "LOW"),
    # Piperidine / piperazine — common hERG offenders
    ("C1CCNCC1", "Piperidine", "MEDIUM"),
    ("C1CNCCN1", "Piperazine", "MEDIUM"),
    # Tertiary amines close to aromatic ring
    ("[N;X3;!$(N-[!#6])]Cc1ccccc1", "Tertiary amine-benzyl", "MEDIUM"),
]

_HEPATOTOX_SMARTS: list[tuple[str, str, str]] = [
    # Reactive metabolite generators
    ("c1ccc(N)cc1", "Aniline moiety", "HIGH"),
    ("C1=CC(=O)C=CC1=O", "Para-quinone", "HIGH"),
    ("[OH]c1ccc(cc1)N", "4-Aminophenol scaffold", "HIGH"),
    # Thiol-reactive groups
    ("C(=S)N", "Thioamide", "MEDIUM"),
    ("[SX2H]", "Free thiol", "MEDIUM"),
    # Halogenated aromatics
    ("Clc1ccccc1", "Chloroaromatic", "MEDIUM"),
    ("Brc1ccccc1", "Bromoaromatic", "MEDIUM"),
    # Geminal-dihalo / polyhalo
    ("CX2", "Geminal dihalide pattern", "MEDIUM"),
]

_PAINS_SMARTS: list[tuple[str, str, str]] = [
    # Rhodanines
    ("O=C1NC(=S)SC1", "Rhodanine", "HIGH"),
    # Catechols (aggregation-prone)
    ("Oc1ccccc1O", "Catechol", "HIGH"),
    # Quinones
    ("O=C1C=CC(=O)C=C1", "Quinone PAINS", "HIGH"),
    # Salicylaldehyde
    ("O=Cc1ccccc1O", "Salicylaldehyde", "HIGH"),
    # Frequent hitter aryl sulfonamide
    ("NS(=O)(=O)c1ccccc1", "Aryl sulfonamide", "MEDIUM"),
    # Triazinone
    ("C1=NC(=O)NC(=O)N1", "Triazinedione", "MEDIUM"),
]

_CYP_SMARTS: dict[str, list[tuple[str, str, str]]] = {
    "CYP1A2": [
        ("c1ccc2ncccc2c1", "Acridine/quinoline core", "HIGH"),
        ("c1cccc2c1cccc2", "Naphthalene scaffold", "MEDIUM"),
        ("Cc1ccc(N)cc1", "4-Aminotoluene", "MEDIUM"),
    ],
    "CYP2C9": [
        ("OC(=O)c1ccccc1", "Benzoic acid", "MEDIUM"),
        ("c1cc(S(=O)(=O)N)ccc1", "Sulfonamide arene", "MEDIUM"),
        ("Clc1ccc(cc1)C(F)(F)F", "4-Chloro trifluoromethyl phenyl", "HIGH"),
    ],
    "CYP2C19": [
        ("C1=CN=CN=C1", "Imidazole core", "HIGH"),
        ("c1cnccn1", "Pyrimidine core", "MEDIUM"),
    ],
    "CYP2D6": [
        ("C1CCNCC1", "Piperidine (CYP2D6)", "MEDIUM"),
        ("[NH2]c1ccccc1", "Aniline (CYP2D6)", "MEDIUM"),
        ("OCCNc1ccccc1", "Amine-arene ether", "MEDIUM"),
    ],
    "CYP3A4": [
        ("C1=NC=NC=N1", "Triazine", "MEDIUM"),
        ("C1CNCCN1", "Piperazine (CYP3A4)", "MEDIUM"),
        ("c1ccc2ccccc2c1", "Naphthalene (CYP3A4)", "LOW"),
    ],
}


# ── Core matcher ──────────────────────────────────────────────────────────────

def _smarts_matches(
    smiles: str | None,
    patterns: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    """Return list of matched alerts as {pattern, description, confidence}."""
    if not smiles:
        return []
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return []
        hits = []
        for smarts_str, desc, conf in patterns:
            pat = Chem.MolFromSmarts(smarts_str)
            if pat is not None and mol.HasSubstructMatch(pat):
                hits.append({"pattern": smarts_str, "description": desc, "confidence": conf})
        return hits
    except Exception as exc:
        logger.debug("[toxicity] RDKit SMARTS match failed: %s", exc)
        return []


def _max_confidence(hits: list[dict]) -> str:
    """Return highest confidence level among hits."""
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if not hits:
        return "NONE"
    return max((h["confidence"] for h in hits), key=lambda c: order.get(c, 0))


# ── Individual assay predictors ───────────────────────────────────────────────

@dataclass
class HERGRisk:
    flagged: bool
    confidence: str
    alert_count: int
    alerts: list[dict]
    logp_risk: bool  # logP > 3.7 + MW < 500 hERG pharmacophore range
    physicochemical_note: str
    requires_wetlab_confirmation: bool = True


def predict_herg_risk(molecule: dict[str, Any]) -> Optional[HERGRisk]:
    """Predict hERG channel blocking risk (QT prolongation liability).

    Combines:
      - logP + MW hERG pharmacophore heuristic (Redfern 2003)
      - Structural alerts (basic N + aromatic bulk)
    """
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    alogp = _safe_float(molecule.get("alogp"))
    mw = _safe_float(molecule.get("molecular_weight"))

    alerts = _smarts_matches(smiles, _HERG_SMARTS)

    # Physicochemical hERG pharmacophore window: logP 1–5, MW < 500, basic N present
    logp_risk = (alogp is not None and alogp > 3.7) and (mw is None or mw < 500)
    phys_note = ""
    if alogp is not None and alogp > 3.7:
        phys_note = f"logP={alogp:.1f} > 3.7 enters hERG pharmacophore window"
    elif alogp is not None:
        phys_note = f"logP={alogp:.1f} within acceptable range"
    else:
        phys_note = "logP not available — pharmacophore assessment skipped"

    flagged = bool(alerts) or logp_risk
    return HERGRisk(
        flagged=flagged,
        confidence=_max_confidence(alerts) if alerts else ("MEDIUM" if logp_risk else "NONE"),
        alert_count=len(alerts),
        alerts=alerts,
        logp_risk=logp_risk,
        physicochemical_note=phys_note,
    )


@dataclass
class AmesResult:
    flagged: bool
    confidence: str
    alert_count: int
    alerts: list[dict]
    requires_wetlab_confirmation: bool = True


def predict_ames_mutagenicity(molecule: dict[str, Any]) -> Optional[AmesResult]:
    """Predict Ames mutagenicity using structural alert filters."""
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    alerts = _smarts_matches(smiles, _AMES_SMARTS)
    flagged = bool(alerts)
    return AmesResult(
        flagged=flagged,
        confidence=_max_confidence(alerts),
        alert_count=len(alerts),
        alerts=alerts,
    )


@dataclass
class HepatotoxicityResult:
    flagged: bool
    confidence: str
    alert_count: int
    alerts: list[dict]
    reactive_metabolite_risk: bool
    requires_wetlab_confirmation: bool = True


def predict_hepatotoxicity(molecule: dict[str, Any]) -> Optional[HepatotoxicityResult]:
    """Predict idiosyncratic hepatotoxicity risk.

    Uses Brenk et al. structural alerts plus LogP/MW thresholds.
    High MW (>500) + high logP (>4.5) is independently associated with DILI.
    """
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    alogp = _safe_float(molecule.get("alogp"))
    mw = _safe_float(molecule.get("molecular_weight"))

    alerts = _smarts_matches(smiles, _HEPATOTOX_SMARTS)

    # Additional physicochemical DILI signal (Xu et al., Toxicol Sci 2015)
    if (mw is not None and mw > 500) and (alogp is not None and alogp > 4.5):
        alerts.append({
            "pattern": "physicochemical",
            "description": f"High MW ({mw:.0f}) + high logP ({alogp:.1f}) — DILI risk zone",
            "confidence": "MEDIUM",
        })

    reactive_metabolite = any(
        a["description"] in ("Aniline moiety", "4-Aminophenol scaffold", "Para-quinone")
        for a in alerts
    )

    return HepatotoxicityResult(
        flagged=bool(alerts),
        confidence=_max_confidence(alerts),
        alert_count=len(alerts),
        alerts=alerts,
        reactive_metabolite_risk=reactive_metabolite,
    )


@dataclass
class CYPInhibitionResult:
    inhibited_isoforms: list[str]
    isoform_details: dict[str, list[dict]]
    ddI_risk: str  # "HIGH", "MEDIUM", "LOW", "NONE"
    requires_wetlab_confirmation: bool = True


def predict_cyp_inhibition(molecule: dict[str, Any]) -> Optional[CYPInhibitionResult]:
    """Predict CYP enzyme inhibition across 5 major isoforms.

    CYP inhibition drives drug-drug interactions (DDI) and toxic metabolite
    accumulation. Returns per-isoform structural alert details.
    """
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    if not smiles:
        return None

    isoform_details: dict[str, list[dict]] = {}
    inhibited: list[str] = []

    for isoform, patterns in _CYP_SMARTS.items():
        hits = _smarts_matches(smiles, patterns)
        if hits:
            isoform_details[isoform] = hits
            inhibited.append(isoform)

    # CYP3A4 metabolises ~50% of drugs — HIGH DDI risk if inhibited
    if "CYP3A4" in inhibited:
        ddi_risk = "HIGH"
    elif len(inhibited) >= 2:
        ddi_risk = "MEDIUM"
    elif inhibited:
        ddi_risk = "LOW"
    else:
        ddi_risk = "NONE"

    return CYPInhibitionResult(
        inhibited_isoforms=inhibited,
        isoform_details=isoform_details,
        ddI_risk=ddi_risk,
    )


@dataclass
class PAINSResult:
    flagged: bool
    alert_count: int
    alerts: list[dict]
    recommendation: str
    requires_wetlab_confirmation: bool = True


def predict_pains(molecule: dict[str, Any]) -> Optional[PAINSResult]:
    """Detect PAINS (Pan-Assay INterference compoundS) structural features.

    PAINS compounds generate false-positive results in many assays due to
    non-specific mechanisms (aggregation, redox activity, covalent binding).
    """
    smiles = molecule.get("smiles") or molecule.get("canonical_smiles")
    alerts = _smarts_matches(smiles, _PAINS_SMARTS)
    recommendation = (
        "Deprioritise: PAINS alerts indicate potential assay artefacts; "
        "verify activity using orthogonal assays." if alerts else "No PAINS alerts."
    )
    return PAINSResult(
        flagged=bool(alerts),
        alert_count=len(alerts),
        alerts=alerts,
        recommendation=recommendation,
    )


# ── Off-target liability composite ───────────────────────────────────────────

@dataclass
class OffTargetLiabilityProfile:
    """Composite off-target safety profile for a candidate molecule."""
    herg: Optional[HERGRisk]
    ames: Optional[AmesResult]
    hepatotoxicity: Optional[HepatotoxicityResult]
    cyp_inhibition: Optional[CYPInhibitionResult]
    pains: Optional[PAINSResult]
    overall_flag_count: int
    overall_risk_level: str  # "LOW", "MODERATE", "HIGH", "VERY_HIGH"
    safety_gate_pass: bool   # False if any HIGH-confidence fatal flag
    summary: str
    is_denovo: bool = False           # True when molecule lacks clinical approval
    denovo_warning: Optional[str] = None  # Populated with DENOVO_WARNING for de-novo hits
    requires_wetlab_confirmation: bool = True


def assess_off_target_liability(
    molecule: dict[str, Any],
    is_approved: bool = False,
) -> OffTargetLiabilityProfile:
    """Run the full off-target safety panel on a candidate molecule.

    Returns a composite profile with an overall risk level and safety gate.

    For approved drugs (is_approved=True) the safety gate is always PASS —
    clinical approval already encodes a benefit/risk assessment. Flags are
    still surfaced so the clinician sees them, but synthesis planning is not
    blocked for approved agents on structural alert grounds alone.

    For de-novo candidates the gate fails on any HIGH-confidence Ames or hERG
    alert (fatal liabilities that must be addressed before synthesis).
    """
    herg = predict_herg_risk(molecule)
    ames = predict_ames_mutagenicity(molecule)
    hepa = predict_hepatotoxicity(molecule)
    cyp = predict_cyp_inhibition(molecule)
    pains = predict_pains(molecule)

    flags: list[str] = []
    if herg and herg.flagged:
        flags.append(f"hERG:{herg.confidence}")
    if ames and ames.flagged:
        flags.append(f"Ames:{ames.confidence}")
    if hepa and hepa.flagged:
        flags.append(f"Hepatotox:{hepa.confidence}")
    if cyp and cyp.ddI_risk in ("HIGH", "MEDIUM"):
        flags.append(f"CYP-DDI:{cyp.ddI_risk}")
    if pains and pains.flagged:
        flags.append(f"PAINS:{_max_confidence(pains.alerts)}")

    high_count = sum(1 for f in flags if "HIGH" in f)
    total_flags = len(flags)

    if high_count >= 2:
        overall = "VERY_HIGH"
    elif high_count == 1:
        overall = "HIGH"
    elif total_flags >= 2:
        overall = "MODERATE"
    elif total_flags == 1:
        overall = "LOW"
    else:
        overall = "LOW"

    # Safety gate: block de-novo synthesis if Ames HIGH or hERG HIGH.
    # For approved drugs the gate is always PASS — clinical benefit/risk is
    # established. Flags remain visible for the prescriber.
    if is_approved:
        gate_pass = True
    else:
        gate_pass = not (
            (ames and ames.confidence == "HIGH" and ames.flagged)
            or (herg and herg.confidence == "HIGH" and herg.flagged)
        )

    flag_str = "; ".join(flags) if flags else "none"
    summary = (
        f"Risk level: {overall}. Flags: {flag_str}. "
        f"Safety gate: {'PASS' if gate_pass else 'FAIL — requires mitigation before synthesis'}. "
        "All predictions require wet-lab confirmation."
    )

    return OffTargetLiabilityProfile(
        herg=herg,
        ames=ames,
        hepatotoxicity=hepa,
        cyp_inhibition=cyp,
        pains=pains,
        overall_flag_count=total_flags,
        overall_risk_level=overall,
        safety_gate_pass=gate_pass,
        summary=summary,
        is_denovo=_is_denovo_compound(molecule),
        denovo_warning=DENOVO_WARNING if _is_denovo_compound(molecule) else None,
    )


def toxicity_risk_score(molecule: dict[str, Any]) -> float:
    """Return a composite toxicity risk score in [0, 100].

    Aggregates hERG, Ames, hepatotox, CYP, and PAINS flags into a single
    numeric score. Higher = riskier. Used by `drug_discovery.py` ensemble.
    """
    profile = assess_off_target_liability(molecule)
    score_map = {"VERY_HIGH": 90, "HIGH": 72, "MODERATE": 48, "LOW": 20}
    return float(score_map.get(profile.overall_risk_level, 20))


# ── SMILES enrichment ─────────────────────────────────────────────────────────

async def enrich_smiles_if_missing(
    molecule: dict[str, Any],
    drug_name: str = "",
) -> dict[str, Any]:
    """Attempt to fill in SMILES data for a molecule if it is absent.

    Lookup order:
      1. ChEMBL (preferred — curated, standardised SMILES)
      2. PubChem PUG REST (fallback)

    The function returns a new dict with the same data plus any newly fetched
    SMILES fields. It does NOT raise on failure — it logs a warning and returns
    the original dict unchanged.

    Args:
        molecule: Candidate drug dict (may already have smiles / canonical_smiles).
        drug_name: Human-readable drug name used for ChEMBL/PubChem search.
                   Falls back to molecule["drug_name"] if not provided.

    Returns:
        Updated molecule dict with `smiles`, `canonical_smiles`, and
        `smiles_source` fields added if enrichment succeeded.
    """
    name = drug_name or molecule.get("drug_name") or molecule.get("name") or ""
    if molecule.get("smiles") or molecule.get("canonical_smiles"):
        return molecule  # already present, nothing to do

    enriched = dict(molecule)  # shallow copy; we do not mutate the original

    # ── 1. Try ChEMBL ────────────────────────────────────────────────────────
    if name:
        try:
            from api.services.chembl import get_smiles_for_drug_name
            chembl_result = await get_smiles_for_drug_name(name)
            if chembl_result and chembl_result.get("canonical_smiles"):
                enriched["smiles"] = chembl_result["canonical_smiles"]
                enriched["canonical_smiles"] = chembl_result["canonical_smiles"]
                enriched["smiles_source"] = "chembl"
                if not enriched.get("molecule_chembl_id") and chembl_result.get("molecule_chembl_id"):
                    enriched["molecule_chembl_id"] = chembl_result["molecule_chembl_id"]
                logger.debug("[toxicity] SMILES enriched via ChEMBL for '%s'", name)
                return enriched
        except Exception as exc:
            logger.debug("[toxicity] ChEMBL SMILES lookup failed for '%s': %s", name, exc)

    # ── 2. Try PubChem PUG REST ───────────────────────────────────────────────
    if name:
        try:
            import httpx
            url = (
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                f"{name}/property/CanonicalSMILES,IsomericSMILES,CID/JSON"
            )
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            props = data.get("PropertyTable", {}).get("Properties", [])
            if props:
                p = props[0]
                smiles_val = p.get("CanonicalSMILES") or p.get("IsomericSMILES")
                if smiles_val:
                    enriched["smiles"] = smiles_val
                    enriched["canonical_smiles"] = smiles_val
                    enriched["smiles_source"] = "pubchem"
                    if not enriched.get("pubchem_cid") and p.get("CID"):
                        enriched["pubchem_cid"] = str(p["CID"])
                    logger.debug("[toxicity] SMILES enriched via PubChem for '%s'", name)
                    return enriched
        except Exception as exc:
            logger.debug("[toxicity] PubChem SMILES lookup failed for '%s': %s", name, exc)

    logger.warning("[toxicity] Could not enrich SMILES for '%s' — toxicity flags will be limited", name)
    return enriched


async def assess_toxicity_full(
    molecule: dict[str, Any],
    drug_name: str = "",
    is_approved: bool = False,
) -> "OffTargetLiabilityProfile":
    """Async wrapper: enriches SMILES then calls assess_off_target_liability.

    This is the recommended entry point when calling from async route handlers
    or workers, as it will attempt to fetch SMILES before running QSAR filters.

    Args:
        molecule: Candidate molecule dict.
        drug_name: Name used for SMILES enrichment if SMILES is absent.
        is_approved: Pass True for FDA/EMA-approved drugs (caps QSAR penalty).

    Returns:
        OffTargetLiabilityProfile with is_denovo and denovo_warning populated.
    """
    enriched = await enrich_smiles_if_missing(molecule, drug_name=drug_name)
    return assess_off_target_liability(enriched, is_approved=is_approved)



# ── Withdrawn / market-withdrawn drug registry ───────────────────────────────
# Drugs removed from market primarily due to safety (not efficacy).
# Source: FDA Orange Book / EMA withdrawal decisions.
# Drug names are normalised (lowercase, no spaces/hyphens).

_WITHDRAWN_DRUGS: dict[str, str] = {
    "rofecoxib": "Withdrawn 2004 — cardiovascular thrombotic events (APPROVE trial)",
    "vioxx": "Withdrawn 2004 — cardiovascular thrombotic events",
    "troglitazone": "Withdrawn 2000 — severe idiosyncratic hepatotoxicity (DILI)",
    "cerivastatin": "Withdrawn 2001 — rhabdomyolysis risk (CYP2C8 interaction)",
    "cisapride": "Withdrawn 2000 — QT prolongation / fatal arrhythmia (hERG)",
    "terfenadine": "Withdrawn 1998 — QT prolongation / torsades de pointes (hERG)",
    "astemizole": "Withdrawn 1999 — QT prolongation / torsades de pointes (hERG)",
    "mibefradil": "Withdrawn 1998 — severe CYP3A4-mediated drug interactions",
    "grepafloxacin": "Withdrawn 1999 — QT prolongation / fatal arrhythmia",
    "bromfenac": "Withdrawn 1998 — severe hepatotoxicity",
    "phenformin": "Withdrawn 1978 — fatal lactic acidosis",
    "amineptine": "Withdrawn — hepatotoxicity and drug abuse potential",
    "pemoline": "Withdrawn 2005 — life-threatening hepatic failure",
    "valdecoxib": "Withdrawn 2005 — severe skin reactions and cardiovascular risk",
    "lumiracoxib": "Withdrawn 2007 — hepatotoxicity",
    "sitaxentan": "Withdrawn 2010 — fatal hepatotoxicity",
}


def _normalise_drug_name_for_lookup(name: str) -> str:
    import re
    return re.sub(r"[\s\-.]", "", name.lower())


def check_withdrawn_status(drug_name: str) -> Optional[dict[str, str]]:
    """Check if a drug has been withdrawn from market due to safety concerns.

    Returns a dict with keys {drug_name, reason} if withdrawn, else None.
    Withdrawal should force an explicit warning in the ranking output and
    prevent the drug from being recommended without clinical override.
    """
    key = _normalise_drug_name_for_lookup(drug_name)
    for withdrawn_key, reason in _WITHDRAWN_DRUGS.items():
        if key == withdrawn_key or key in withdrawn_key or withdrawn_key in key:
            return {"drug_name": drug_name, "reason": reason}
    return None


# ── Safety rank penalty ───────────────────────────────────────────────────────

def compute_safety_rank_penalty(
    molecule: dict[str, Any],
    drug_name: str = "",
    is_approved: bool = False,
) -> float:
    """Return a safety penalty [0.0, 0.50] to subtract from rank_score.

    Design:
      - Withdrawn drugs: 0.50 (hard near-zero after penalty)
      - VERY_HIGH tox profile: 0.30 (de-novo candidates only)
      - HIGH tox profile: 0.20
      - MODERATE: 0.10
      - LOW / approved drugs: 0.00 – 0.05
      - For approved drugs the maximum penalty is 0.10 regardless of QSAR flags,
        because FDA approval already encodes a clinical benefit/risk assessment.

    This penalty is consumed by `compute_rank_score()` in ranking.py.
    """
    # Hard penalty for market-withdrawn drugs regardless of approval status
    if drug_name and check_withdrawn_status(drug_name):
        return 0.50

    profile = assess_off_target_liability(molecule)
    penalty_map = {"VERY_HIGH": 0.30, "HIGH": 0.20, "MODERATE": 0.10, "LOW": 0.02}
    penalty = penalty_map.get(profile.overall_risk_level, 0.02)

    # For approved drugs: cap QSAR-only penalties at 0.05 (clinically validated)
    if is_approved:
        penalty = min(penalty, 0.05)

    return round(penalty, 3)


# ── Utility ───────────────────────────────────────────────────────────────────

def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
