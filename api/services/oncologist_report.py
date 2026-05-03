"""Oncologist / Molecular Tumor Board Report Generator — OpenOncology

Generates a structured, professional-grade report for oncologists and
molecular tumor board review.  This is the technical companion to the
patient-facing ``patient_summary.py``.

Structure inspired by ESMO Precision Cancer Medicine and molecular tumor
board reporting guidelines (Stenzinger et al., Ann Oncol 2020; Li et al.,
J Clin Oncol 2017 — VICC/AMP/ASCO/CAP classification).

Sections
--------
1. Executive Summary (top 3 recommendations + overall conclusion)
2. Sample & Quality Metrics (QC, FFPE status, tumour purity)
3. Key Genomic Alterations (VAF, HGVS, AlphaMissense score)
4. Drug Recommendations — ranked table with evidence levels, rationale,
   ADME/toxicity notes
5. Custom / Experimental Drug Candidates (heavily caveated, separate section)
6. Evidence Audit Trail (full scoring breakdown per drug)
7. System Limitations & Mandatory Disclaimer

IMPORTANT
---------
This tool is experimental and NOT clinically validated or FDA-approved.
Every recommendation in this report REQUIRES review by a qualified oncologist
before any clinical decision is made.  This report is NOT a substitute for
certified molecular diagnostics (e.g., Foundation Medicine, Caris MolecularIQ,
FoundationOne CDx, or an accredited CAP/CLIA laboratory).
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Constants & disclaimer
# ---------------------------------------------------------------------------

ONCOLOGIST_DISCLAIMER = (
    "⚠  THIS IS NOT A VALIDATED CLINICAL DIAGNOSTIC TEST  ⚠\n"
    + "=" * 62 + "\n"
    "OpenOncology is an open-source RESEARCH prototype built outside any "
    "clinical quality management system. It has:\n\n"
    "  ✗  NOT undergone FDA 510(k), PMA, or CE-IVD marking.\n"
    "  ✗  NOT been validated in a CAP/CLIA-certified laboratory.\n"
    "  ✗  NOT been prospectively validated against patient outcomes.\n"
    "  ✗  NOT been reviewed by a notified body or regulatory authority.\n\n"
    "BENCHMARK PERFORMANCE (offline, OncoKB L1/L2 cases only):\n"
    "  • Precision@3 ≈ 0.49–0.61  (correct drug in top-3, ~60% of the time)\n"
    "  • Hit@3 ≈ 0.65–0.92        (at least one correct drug in top-3)\n"
    "  • MRR ≈ 0.58–0.86          (mean reciprocal rank)\n"
    "  • False positive rate on VUS / no-target cases: NOT MEASURED\n"
    "  • Rare cancers, pediatric oncology, complex co-mutations: "
    "UNDERREPRESENTED\n\n"
    "All drug recommendations are computational hypotheses derived from "
    "public databases (OncoKB, CIViC, OpenTargets, ChEMBL). They reflect "
    "the literature at the time of analysis and may be incomplete or "
    "incorrect for a given patient's specific molecular context.\n\n"
    "MANDATORY ACTIONS before clinical use:\n"
    "  1. Independently verify all evidence citations in primary literature.\n"
    "  2. Confirm findings with a CAP/CLIA-certified molecular pathology lab.\n"
    "  3. Consider co-mutations, tumour heterogeneity, performance status,\n"
    "     organ function, and patient preferences before prescribing.\n"
    "  4. Submit complex cases to a multidisciplinary molecular tumour board.\n"
    "  5. Do NOT use the experimental compound section to guide treatment\n"
    "     without prior in-vitro validation, synthesis, and regulatory review.\n\n"
    "Version: OpenOncology v0.1 (research prototype — NOT a medical device). "
    "Evidence freeze date: varies by upstream database."
)

_ONCOKB_TIER_LABELS = {
    "LEVEL_1":  "Level 1 — FDA-approved for this variant/tumour type",
    "LEVEL_2":  "Level 2 — Standard-of-care (NCCN / ESMO guideline)",
    "LEVEL_3A": "Level 3A — Compelling clinical evidence (phase II/III trial)",
    "LEVEL_3B": "Level 3B — Pre-clinical or early clinical evidence",
    "LEVEL_4":  "Level 4 — Biological rationale only; no clinical data",
    "LEVEL_R1": "Level R1 — FDA-recognised RESISTANCE (do NOT use)",
    "LEVEL_R2": "Level R2 — Emergent RESISTANCE evidence",
}

_CONFIDENCE_DESCRIPTIONS = {
    "HIGH":   "High confidence (score ≥ 0.80). Multiple concordant evidence sources.",
    "MEDIUM": "Medium confidence (score 0.50–0.79). Partial evidence available.",
    "LOW":    "Low confidence (score < 0.50). Limited or conflicting evidence.",
}

_REFRACTORY_COMBINATION_REGIMENS: dict[str, list[str]] = {
    "EGFR": [
        "osimertinib (preferred for T790M)",
        "amivantamab + lazertinib",
    ],
    "BRAF": [
        "dabrafenib + trametinib",
        "encorafenib + binimetinib",
    ],
    "ERBB2": [
        "trastuzumab + pertuzumab",
        "trastuzumab deruxtecan",
        "tucatinib + trastuzumab",
    ],
    "ALK": [
        "lorlatinib (preferred after second-generation ALK TKI resistance)",
    ],
    "ROS1": [
        "repotrectinib",
        "lorlatinib",
    ],
    "RET": [
        "selpercatinib",
        "pralsetinib",
    ],
    "MET": [
        "tepotinib",
        "capmatinib",
    ],
    "KRAS": [
        "adagrasib + cetuximab",
        "sotorasib",
    ],
    "FLT3": [
        "gilteritinib",
        "quizartinib",
    ],
    "ABL1": [
        "ponatinib",
        "asciminib",
    ],
    "KIT": [
        "avapritinib",
        "ripretinib",
    ],
    "PDGFRA": [
        "avapritinib",
    ],
    "BTK": [
        "pirtobrutinib",
        "venetoclax-based regimens",
    ],
    "PIK3CA": [
        "alpelisib + endocrine therapy",
        "capivasertib + endocrine therapy",
    ],
    "ESR1": [
        "elacestrant",
        "elacestrant + CDK4/6 inhibitor (trial context)",
    ],
    "IDH1": [
        "ivosidenib",
        "olutasidenib",
    ],
    "IDH2": [
        "enasidenib",
    ],
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class OncologistReport:
    """Structured oncologist/tumor-board report."""

    # Metadata
    patient_id: Optional[str]
    report_date: str
    cancer_type: str

    # Sections
    executive_summary: dict          # {conclusion, top_3, overall_confidence}
    sample_quality: Optional[dict]   # QC metrics if provided
    genomic_alterations: list[dict]  # per-mutation detail
    drug_recommendations: list[dict] # ranked, annotated
    experimental_candidates: list[dict]  # de-novo section
    audit_trail: dict                # scoring breakdown + interpretation guide
    withdrawn_warnings: list[dict]
    system_limitations: list[str]
    tier_gap_explanation: list[str]  # why no Tier 1/2 found (empty when Tier 1/2 present)

    # Rendered outputs
    plain_text: str = field(default="", init=False)
    sections: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.plain_text = _render_plain_text(self)
        self.sections = _render_sections(self)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_oncologist_report(
    ranked_candidates: list[dict],
    mutation_summary: list[dict],
    cancer_type: str,
    qc_report: Optional[dict] = None,
    discovery_brief: Optional[dict] = None,
    withdrawn_warnings: Optional[list[dict]] = None,
    patient_id: Optional[str] = None,
    report_date: Optional[str] = None,
) -> OncologistReport:
    """Generate a structured oncologist/tumor-board report.

    Parameters
    ----------
    ranked_candidates:
        Output of ``rank_candidates()`` — list of dicts, highest score first.
    mutation_summary:
        List of mutation dicts from the analysis pipeline.
    cancer_type:
        Human-readable cancer type string (e.g. ``"Non-small cell lung cancer"``).
    qc_report:
        Optional output of ``sample_qc.run_qc_pipeline()``; used for the
        Sample & Quality section.
    discovery_brief:
        Optional output of ``drug_discovery.generate_discovery_brief()``; used
        for the experimental candidates section.
    withdrawn_warnings:
        Output of ``check_withdrawn_status()``.
    patient_id:
        Anonymised patient/submission ID (shown in header only).
    report_date:
        ISO date string; defaults to today.
    """
    from api.ai.ranking import get_system_limitations, detect_no_strong_candidate

    report_date = report_date or date.today().isoformat()
    withdrawn_set: set[str] = set()
    if withdrawn_warnings:
        for w in withdrawn_warnings:
            name = w.get("drug_name") or w.get("name") or ""
            if name:
                withdrawn_set.add(name.lower())

    has_tier1_or_2 = any(
        str(c.get("oncokb_level") or "").upper() in {"LEVEL_1", "LEVEL_2"}
        for c in ranked_candidates
    )

    # ── 1. Drug recommendations ────────────────────────────────────────────
    drug_recs = []
    for i, c in enumerate(ranked_candidates[:10]):
        oncokb = c.get("oncokb_level") or ""
        drug_name = c.get("drug_name") or c.get("name") or "Unknown"

        is_resistance = oncokb in ("LEVEL_R1", "LEVEL_R2")
        is_withdrawn = drug_name.lower() in withdrawn_set
        is_denovo = _is_denovo(c)

        if is_denovo:
            continue  # de-novo go into experimental_candidates

        rec = {
            "rank": i + 1,
            "drug_name": drug_name,
            "chembl_id": c.get("chembl_id"),
            "drug_class": c.get("drug_class") or c.get("mechanism_of_action") or "",
            "target": c.get("target") or c.get("target_gene") or "",
            "approval_status": _approval_status_label(c),
            "oncokb_level": oncokb,
            "oncokb_label": _ONCOKB_TIER_LABELS.get(oncokb, "No OncoKB annotation"),
            "rank_score": c.get("rank_score"),
            "rank_score_ci_low": c.get("rank_score_ci_low"),
            "rank_score_ci_high": c.get("rank_score_ci_high"),
            "confidence_level": c.get("confidence_level", "LOW"),
            "evidence_completeness": c.get("evidence_completeness"),
            "missing_sources": c.get("missing_sources", []),
            "evidence_audit_trail": c.get("evidence_audit_trail", []),
            "immunotherapy_context": c.get("immunotherapy_context"),
            "is_resistance": is_resistance,
            "is_withdrawn": is_withdrawn,
            "rationale_bullets": _build_rationale_bullets(c),
            "adme_notes": _build_adme_notes(c),
            "resistance_notes": _build_resistance_notes(c, oncokb),
            "clinical_action": _build_clinical_action(c, oncokb, is_resistance, is_withdrawn),
            "evidence_note_short": _build_evidence_note_short(c, oncokb),
            "key_safety_note": _build_key_safety_note(c, is_resistance, is_withdrawn),
            "next_step_for_oncologist": _build_next_step_for_oncologist(c, oncokb, is_resistance),
            "combination_suggestions": (
                _get_refractory_combinations(c, mutation_summary)
                if is_resistance and not has_tier1_or_2
                else []
            ),
            "_injected": (
                c.get("_injected_from_oncokb_table")
                or c.get("_injected_from_oncokb_api")
                or c.get("_injected_from_ici_context")
            ),
        }
        drug_recs.append(rec)

    # ── 2. Experimental / de-novo candidates ──────────────────────────────
    exp_candidates = []
    denovo_source = []

    # From ranked_candidates
    for c in ranked_candidates:
        if _is_denovo(c):
            denovo_source.append(c)

    # From discovery_brief — only include candidates that passed the strict gate
    if discovery_brief:
        for c in discovery_brief.get("de_novo_candidates", []):
            c["_from_discovery_brief"] = True
            # Only include if it passed the strict experimental gate (or gate wasn't run)
            if c.get("show_in_clinical_report", True):
                denovo_source.append(c)

    for c in denovo_source[:3]:   # hard cap: max 3 experimental candidates
        exp_candidates.append(_format_experimental_candidate(c))

    # ── 3. Genomic alterations ─────────────────────────────────────────────
    genomic_alts = []
    for m in mutation_summary:
        genomic_alts.append({
            "gene": m.get("gene") or m.get("Gene"),
            "hgvs_notation": m.get("hgvs_notation") or m.get("hgvs"),
            "mutation_type": m.get("mutation_type"),
            "vaf": m.get("vaf"),
            "classification": m.get("classification"),
            "oncokb_level": m.get("oncokb_level"),
            "alphamissense_score": m.get("alphamissense_score"),
            "alphamissense_class": m.get("alphamissense_class"),
            "cosmic_id": m.get("cosmic_id"),
            "clinvar_id": m.get("clinvar_id"),
            "is_targetable": m.get("is_targetable", False),
        })

    # ── 4. Sample quality ──────────────────────────────────────────────────
    sample_quality = _format_qc(qc_report) if qc_report else None

    # ── 5. Executive summary ───────────────────────────────────────────────
    top_3 = [
        r for r in drug_recs[:3] if not r["is_resistance"] and not r["is_withdrawn"]
    ]
    resistance_flags = [r for r in drug_recs if r["is_resistance"]]
    overall_conf = _overall_confidence(drug_recs)
    conclusion = _build_executive_conclusion(
        top_3=top_3,
        cancer_type=cancer_type,
        n_mutations=len(mutation_summary),
        has_experimental=bool(exp_candidates),
        qc_verdict=qc_report.get("qc_verdict") if qc_report else None,
        resistance_flags=resistance_flags,
    )
    tumor_board_questions = _build_tumor_board_questions(
        top_3=top_3,
        genomic_alts=genomic_alts,
        has_experimental=bool(exp_candidates),
        cancer_type=cancer_type,
    )

    # ── No-strong-candidate detection ─────────────────────────────────────
    from api.ai.ranking import DEFAULT_CONFIG as _ranking_cfg
    no_drug_verdict = detect_no_strong_candidate(ranked_candidates, _ranking_cfg)

    # ── Benchmark transparency block ───────────────────────────────────────
    benchmark_transparency = _build_benchmark_transparency()

    executive_summary = {
        "conclusion": conclusion,
        "recommended_actions_line": _build_recommended_actions_line(top_3),
        "top_3_recommendations": top_3,
        "resistance_flagged_drugs": [r["drug_name"] for r in resistance_flags],
        "overall_confidence": overall_conf,
        "overall_confidence_label": _CONFIDENCE_DESCRIPTIONS.get(overall_conf, overall_conf),
        "no_drug_verdict": no_drug_verdict,
        "total_mutations_analysed": len(mutation_summary),
        "total_candidates_evaluated": len(ranked_candidates),
        "has_experimental_candidates": bool(exp_candidates),
        "tumor_board_discussion_questions": tumor_board_questions,
        "benchmark_transparency": benchmark_transparency,
        "how_to_use_this_report": _build_how_to_use_this_report(),
    }

    # ── 6. Audit trail ─────────────────────────────────────────────────────
    audit_trail = {
        "interpretation_guide": _interpretation_guide(),
        "all_candidates": [
            {
                "rank": i + 1,
                "drug_name": c.get("drug_name"),
                "rank_score": c.get("rank_score"),
                "evidence_audit_trail": c.get("evidence_audit_trail", []),
                "evidence_completeness": c.get("evidence_completeness"),
                "missing_sources": c.get("missing_sources", []),
            }
            for i, c in enumerate(ranked_candidates[:10])
        ],
    }

    system_lims = get_system_limitations()

    # ── 7. Why no Tier 1 / Tier 2 ─────────────────────────────────────────
    tier_gap = _build_tier_gap_explanation(ranked_candidates, genomic_alts, cancer_type)

    return OncologistReport(
        patient_id=patient_id,
        report_date=report_date,
        cancer_type=cancer_type,
        executive_summary=executive_summary,
        sample_quality=sample_quality,
        genomic_alterations=genomic_alts,
        drug_recommendations=drug_recs,
        experimental_candidates=exp_candidates,
        audit_trail=audit_trail,
        withdrawn_warnings=withdrawn_warnings or [],
        system_limitations=system_lims if isinstance(system_lims, list) else [str(system_lims)],
        tier_gap_explanation=tier_gap,
    )


# ---------------------------------------------------------------------------
# Private helpers — drug recommendations
# ---------------------------------------------------------------------------

def _is_denovo(candidate: dict) -> bool:
    """Return True if this candidate is a novel/de-novo molecule."""
    if candidate.get("is_denovo") or candidate.get("_from_discovery_brief"):
        return True
    if not candidate.get("chembl_id") and not candidate.get("pubchem_cid"):
        phase = candidate.get("max_phase", -1)
        if phase is None or (isinstance(phase, (int, float)) and phase < 1):
            return True
    return False


def _approval_status_label(c: dict) -> str:
    phase = c.get("max_phase")
    oncokb = c.get("oncokb_level", "")
    if c.get("approved") or oncokb in ("LEVEL_1", "LEVEL_2") or (phase and phase >= 4):
        return "Approved"
    if phase and phase >= 3:
        return "Phase III trial"
    if phase and phase >= 2:
        return "Phase II trial"
    if phase and phase >= 1:
        return "Phase I trial"
    return "Pre-clinical / investigational"


def _get_refractory_combinations(candidate: dict, mutation_summary: list[dict]) -> list[str]:
    genes: set[str] = set()

    direct_gene = candidate.get("target") or candidate.get("target_gene") or candidate.get("gene")
    if direct_gene:
        genes.add(str(direct_gene).upper())

    for m in mutation_summary:
        m_level = str(m.get("oncokb_level") or "").upper()
        if m_level in {"LEVEL_R1", "LEVEL_R2"}:
            m_gene = str(m.get("gene") or "").upper()
            if m_gene:
                genes.add(m_gene)

    out: list[str] = []
    for gene in genes:
        for regimen in _REFRACTORY_COMBINATION_REGIMENS.get(gene, []):
            if regimen not in out:
                out.append(regimen)
    return out[:5]


def _build_rationale_bullets(c: dict) -> list[str]:
    """Build evidence-level rationale bullets for a drug recommendation."""
    bullets: list[str] = []
    oncokb = c.get("oncokb_level") or ""

    if oncokb.startswith("LEVEL_R"):
        bullets.append(
            f"RESISTANCE FLAG — OncoKB {oncokb}: this agent should NOT be used "
            "for this variant. Score is hard-capped per system policy."
        )
        return bullets

    if oncokb:
        label = _ONCOKB_TIER_LABELS.get(oncokb, oncokb)
        bullets.append(f"OncoKB: {label}.")

    civic = c.get("civic_evidence_level")
    if civic:
        tier_map = {"A": "validated association", "B": "clinical trial evidence",
                    "C": "case report / cohort", "D": "pre-clinical", "E": "indirect / inferential"}
        bullets.append(
            f"CIViC: Level {civic} — {tier_map.get(str(civic).upper(), 'evidence reported')}."
        )

    binding = c.get("binding_score")
    if binding is not None:
        quality = "strong" if binding >= 0.7 else ("moderate" if binding >= 0.4 else "low")
        bullets.append(
            f"Predicted binding affinity: {quality} (DiffDock score = {binding:.3f}; "
            "range 0–1). Note: requires experimental validation."
        )
    else:
        bullets.append(
            "Binding affinity: not computed (DiffDock requires GPU pipeline). "
            "Score weighted as absent; other sources compensate."
        )

    ot = c.get("opentargets_score")
    if ot is not None:
        strength = "strong" if ot >= 0.5 else ("moderate" if ot >= 0.2 else "weak")
        bullets.append(
            f"OpenTargets gene-disease association: {ot:.3f} / 1.00 ({strength}). "
            "Combines genetic, somatic, expression, and literature evidence."
        )

    am = c.get("alphamissense_score")
    am_cls = c.get("alphamissense_class") or ""
    if am is not None:
        bullets.append(
            f"AlphaMissense pathogenicity: {am:.3f} ({am_cls}). "
            "Score > 0.75 = likely pathogenic per DeepMind calibration."
        )

    ec = c.get("evidence_completeness")
    if ec is not None and ec < 1.0:
        missing = c.get("missing_sources", [])
        bullets.append(
            f"Evidence completeness: {ec:.0%} ({len(missing)} source(s) absent: "
            f"{', '.join(missing) if missing else 'none listed'}). "
            "95% CI is wider when sources are missing — treat rank score as indicative only."
        )
    elif ec == 1.0:
        bullets.append("Evidence completeness: 100% — all 6 evidence sources contributed.")

    return bullets


def _build_clinical_action(c: dict, oncokb: str, is_resistance: bool, is_withdrawn: bool) -> dict:
    """Return a structured clinical action summary for this drug.

    This is the 'what should the oncologist actually do' box — the most
    actionable part of each drug entry.
    """
    drug_name = c.get("drug_name") or "this agent"

    if is_resistance:
        return {
            "recommendation": "DO NOT USE",
            "action": f"Avoid {drug_name} for this variant. FDA/OncoKB recognises "
                       f"this as a resistance mechanism. If the patient is currently "
                       f"on {drug_name}, discuss switching to an alternative agent.",
            "priority": "CRITICAL",
        }

    if is_withdrawn:
        return {
            "recommendation": "AVOID — WITHDRAWN",
            "action": f"{drug_name} has been withdrawn from the market in some "
                       f"countries due to safety concerns. Do not prescribe without "
                       f"independent safety review.",
            "priority": "HIGH",
        }

    oncokb_lvl = oncokb or ""
    phase = c.get("max_phase") or 0
    approved = c.get("approved") or phase >= 4 or oncokb_lvl in ("LEVEL_1", "LEVEL_2")

    if oncokb_lvl == "LEVEL_1":
        return {
            "recommendation": "CONSIDER — FDA-APPROVED FOR THIS VARIANT",
            "action": (
                f"Review {drug_name} as first-line or combination option. "
                f"Confirm tumour type and co-mutation profile match labelled indication. "
                f"Check for contraindications (organ function, performance status, "
                f"drug interactions) before prescribing."
            ),
            "priority": "HIGH",
        }
    elif oncokb_lvl == "LEVEL_2":
        return {
            "recommendation": "CONSIDER — STANDARD-OF-CARE EVIDENCE",
            "action": (
                f"{drug_name} has guideline support (NCCN/ESMO) for this alteration. "
                f"Review current guidelines for your tumour type. "
                f"May qualify for on-label use or compassionate access in some jurisdictions."
            ),
            "priority": "HIGH",
        }
    elif oncokb_lvl in ("LEVEL_3A", "LEVEL_3B"):
        return {
            "recommendation": "EXPLORE — CLINICAL TRIAL OR OFF-LABEL",
            "action": (
                f"Search ClinicalTrials.gov for open trials matching {drug_name} "
                f"and this alteration. Consider off-label expanded access if no trial "
                f"is available and evidence is compelling. Discuss risk/benefit at "
                f"molecular tumour board."
            ),
            "priority": "MEDIUM",
        }
    elif approved:
        return {
            "recommendation": "CONSIDER OFF-LABEL",
            "action": (
                f"{drug_name} is approved for a different indication but may have "
                f"relevance to this alteration. Review institutional policy for "
                f"off-label prescribing. ClinicalTrials.gov search recommended."
            ),
            "priority": "MEDIUM",
        }
    else:
        return {
            "recommendation": "INVESTIGATIONAL — LOW PRIORITY",
            "action": (
                f"{drug_name} has limited clinical evidence for this alteration. "
                f"Flag for future monitoring if no other option is available. "
                f"Consider molecular tumour board discussion only."
            ),
            "priority": "LOW",
        }


def _build_adme_notes(c: dict) -> list[str]:
    """Summarise ADME/toxicity data available for a candidate."""
    notes: list[str] = []
    oral = c.get("oral_exposure_score")
    tox = c.get("toxicity_risk")
    sa = c.get("synthesis_feasibility_score")
    adme_flags = c.get("adme_flags") or []
    tox_flags = c.get("toxicity_flags") or []

    if oral is not None:
        notes.append(f"Oral exposure score: {oral:.0f}/100 (heuristic ADME estimate).")
    if tox is not None:
        notes.append(f"Toxicity risk score: {tox:.0f}/100 (lower = safer; heuristic estimate).")
    if sa is not None:
        notes.append(f"Synthetic accessibility: {sa:.0f}/100 (for approved drugs: informational only).")
    for flag in adme_flags[:3]:
        notes.append(f"ADME flag: {flag}.")
    for flag in tox_flags[:3]:
        notes.append(f"Toxicity flag: {flag}.")

    if not notes:
        notes.append("No ADME/toxicity data available for this candidate.")
    return notes


def _build_resistance_notes(c: dict, oncokb: str) -> list[str]:
    notes: list[str] = []
    if oncokb == "LEVEL_R1":
        notes.append(
            "FDA-recognised primary resistance. This drug should NOT be recommended "
            "for patients with this variant."
        )
    elif oncokb == "LEVEL_R2":
        notes.append(
            "Emergent resistance evidence. Clinical relevance is context-dependent; "
            "discuss with a molecular tumour board."
        )
    resistance_mechanisms = c.get("resistance_mechanisms") or []
    for mech in resistance_mechanisms[:2]:
        notes.append(f"Known resistance mechanism: {mech}.")
    return notes


def _build_evidence_note_short(c: dict, oncokb: str) -> str:
    level_label = _ONCOKB_TIER_LABELS.get(oncokb, "No OncoKB annotation")
    civic = c.get("civic_score")
    civic_label = f"; CIViC {civic}" if civic else ""
    return f"{level_label}{civic_label}."


def _build_key_safety_note(c: dict, is_resistance: bool, is_withdrawn: bool) -> str:
    if is_resistance:
        return "OncoKB resistance flag present: avoid this therapy for the current variant context."
    if is_withdrawn:
        return "Safety/withdrawal concern reported in some jurisdictions; do not prescribe without independent review."
    tox = c.get("toxicity_risk")
    if tox is not None:
        if float(tox) >= 60:
            return "High predicted toxicity risk; verify risk-benefit before any consideration."
        if float(tox) >= 40:
            return "Moderate predicted toxicity risk; confirm with standard safety checks."
    return "No major safety alert in available computational annotations; clinical contraindications still apply."


def _build_next_step_for_oncologist(c: dict, oncokb: str, is_resistance: bool) -> str:
    gene = str(c.get("target_gene") or c.get("gene") or "").upper()
    if is_resistance:
        return "Check prior exposure and switch to an alternative mechanism if patient is on this agent."
    if gene == "EGFR":
        return "Check prior TKI exposure and resistance mechanism (e.g., T790M/C797S) before selection."
    if gene == "MET":
        return "Assess MET amplification/overexpression and consider EGFR+MET strategy when appropriate."
    if gene == "ERBB2":
        return "Confirm HER2 status (IHC/FISH/NGS context) and prior anti-HER2 treatment history."
    if oncokb in ("LEVEL_1", "LEVEL_2"):
        return "Confirm line-of-therapy fit, prior exposure, and organ-function contraindications."
    return "Review trial eligibility and discuss at molecular tumour board before off-label use."


def _build_recommended_actions_line(top_3: list[dict]) -> str:
    if not top_3:
        return "No strong actionable drug identified; prioritise tumour board review and clinical-trial pathways."
    snippets: list[str] = []
    for rec in top_3[:2]:
        action = rec.get("next_step_for_oncologist") or rec.get("clinical_action", {}).get("recommendation", "Review")
        snippets.append(f"{rec['drug_name']} - {action}")
    return " | ".join(snippets)


def _build_how_to_use_this_report() -> list[str]:
    return [
        "Use Section 1 first: confirm whether strong actionable options exist before reading lower-ranked entries.",
        "For each suggested drug, verify tumour context, prior treatment exposure, and contraindications in local guidelines.",
        "Treat all scores as triage signals only; independently validate citations and molecular findings.",
        "Discuss uncertain or conflicting cases in a multidisciplinary molecular tumour board.",
        "Experimental candidates are computational hypotheses only and require independent docking plus wet-lab validation.",
    ]


# ---------------------------------------------------------------------------
# Private helpers — experimental candidates
# ---------------------------------------------------------------------------

def _format_experimental_candidate(c: dict) -> dict:
    """Format a de-novo/experimental candidate with full transparency data."""
    name = c.get("drug_name") or c.get("name") or "Unnamed experimental compound"
    smiles = c.get("smiles") or c.get("canonical_smiles")
    target_gene = c.get("target_gene") or c.get("target") or ""

    binding = c.get("binding_score")
    ensemble = c.get("ensemble_score")
    oral = c.get("oral_exposure_score")
    tox = c.get("toxicity_risk")
    synth = c.get("synthesis_feasibility_score")

    # Confidence tier: conservative rules with clear explanation
    scores = [s for s in [binding, (ensemble or 0) / 100 if ensemble else None] if s is not None]
    avg = sum(scores) / len(scores) if scores else 0.0
    if avg >= 0.7:
        conf_tier = "Moderate"
        conf_explanation = (
            f"Binding/ensemble scores average {avg:.2f} — above the 0.70 threshold for "
            "Moderate confidence. This means the molecule shows computational promise "
            "but has NOT been experimentally confirmed. Moderate confidence here means "
            "'worth prioritising for wet-lab testing', NOT 'likely to work clinically'."
        )
    elif avg >= 0.4:
        conf_tier = "Low-Moderate"
        conf_explanation = (
            f"Binding/ensemble scores average {avg:.2f} — in the 0.40–0.70 range. "
            "This is a weak computational signal. Consider only if no stronger "
            "repurposing candidate exists and the target biology is compelling."
        )
    else:
        conf_tier = "Low"
        conf_explanation = (
            f"Binding/ensemble scores average {avg:.2f} — below 0.40. "
            "Very weak signal. This compound should only be considered for "
            "exploratory in-silico analysis, not synthesis."
        )

    # Target rationale: why was this molecule designed/selected?
    target_rationale = _build_target_rationale(c, target_gene)

    # Risk profile narrative
    risk_profile = _build_risk_profile(c, tox, oral, synth)

    toxicity_flags = c.get("toxicity_flags") or []
    adme_flags = c.get("adme_flags") or []
    tox_summary = c.get("toxicity_summary") or {}
    blocked = c.get("safety_gate_blocked", False)

    # Prioritised, concrete next steps (not a generic list)
    next_steps = _build_experimental_next_steps(blocked, conf_tier, binding, tox, synth)

    return {
        "name": name,
        "smiles": smiles,
        "target_gene": target_gene,
        "target_rationale": target_rationale,
        "binding_score": binding,
        "ensemble_score": ensemble,
        "oral_exposure_score": oral,
        "toxicity_risk": tox,
        "synthesis_feasibility_score": synth,
        "adme_flags": adme_flags,
        "toxicity_flags": toxicity_flags,
        "toxicity_summary": tox_summary,
        "safety_gate_blocked": blocked,
        "confidence_tier": conf_tier,
        "confidence_explanation": conf_explanation,
        "risk_profile": risk_profile,
        "ensemble_breakdown": c.get("ensemble_breakdown", {}),
        "suggested_next_steps": next_steps,
        "mandatory_caveats": [
            "HIGHLY EXPERIMENTAL — Computational hypothesis only. Not a drug.",
            "Has NOT been tested in humans, animals, or any in-vitro system.",
            "QSAR/heuristic scores: AUC ~0.71–0.79 on published benchmarks — "
            "comparable to early-stage in-silico filters, not validated QSAR models.",
            "Wet-lab confirmation is MANDATORY before any synthesis or in-vivo experiment.",
            "Not approved by the FDA, EMA, or any regulatory authority.",
            "Do NOT use to guide patient treatment decisions.",
            "Oncologists should treat this section as a research direction pointer, "
            "not a clinical recommendation.",
        ],
        "_from_discovery_brief": c.get("_from_discovery_brief", False),
    }


def _build_target_rationale(c: dict, target_gene: str) -> str:
    """Explain WHY this molecule was selected/designed — the target biology."""
    gene = (target_gene or "").upper()

    # Gene-specific mechanistic rationale
    _GENE_BIOLOGY: dict[str, str] = {
        "EGFR": (
            "EGFR (Epidermal Growth Factor Receptor) is an RTK whose kinase domain "
            "mutations (exon 19 del, L858R) constitutively activate downstream RAS/MAPK "
            "and PI3K/AKT. First/second-generation TKIs (erlotinib, gefitinib, afatinib) "
            "compete at the ATP-binding pocket. The T790M gatekeeper substitution sterically "
            "blocks them; osimertinib overcomes this via covalent Cys797 adduct. If C797S is "
            "also present, ALL covalent strategies fail — allosteric (type III) inhibitors "
            "targeting the αC-helix-out state remain the only viable option. "
            "Priority assays: Ba/F3 cellular IC50, selectivity panel (ERBB2/4), "
            "crystallography with compound + mutant protein."
        ),
        "KRAS": (
            "KRAS is a small GTPase locked in an active GTP-bound state by oncogenic mutations "
            "(G12C, G12D, G12V). G12C creates a novel covalent handle — sotorasib/adagrasib "
            "form an irreversible bond with the mutant cysteine in the switch-II pocket (S-IIP). "
            "Non-G12C mutations lack this handle; allosteric KRAS(OFF)-state binders or SOS1 "
            "inhibitors are the current investigational route. Acquired resistance commonly "
            "involves Y96D (disrupts S-IIP) or secondary KRAS amplification. "
            "Priority assays: covalent labelling confirmation (LC-MS), ERK phosphorylation "
            "suppression, NCI-H23 (G12C) and combinability with MEK inhibition."
        ),
        "BRAF": (
            "BRAF V600E encodes a constitutively active kinase that bypasses RAS-dependent "
            "dimerisation. Class I inhibitors (vemurafenib, dabrafenib) selectively bind the "
            "inactive ('DFG-out') V600E monomer; paradoxical activation occurs in RAS-mutant "
            "cells via enhanced BRAF dimer formation. Combination with MEK inhibitors "
            "(trametinib, cobimetinib, binimetinib) suppresses this rebound. "
            "Non-V600 class II/III mutations require pan-RAF or MEK-directed strategies. "
            "Priority assays: BRAF V600E selectivity vs. WT, ERK/pERK suppression in A375."
        ),
        "ALK": (
            "ALK fusions (EML4-ALK, KIF5B-ALK) produce constitutive dimerisation and kinase "
            "activation. Three generations of TKIs exist: 1G (crizotinib), 2G (alectinib, "
            "brigatinib, ceritinib), 3G (lorlatinib). Resistance to 2G TKIs is dominated by "
            "ALK G1202R solvent-front mutation; lorlatinib retains activity but risks compound "
            "mutations (L1196M+G1202R). "
            "Priority assays: ALK fusion Ba/F3 IC50 panel against ALK WT + G1202R + L1196M."
        ),
        "MET": (
            "MET exon 14 skipping mutations remove the juxtamembrane region that mediates "
            "CBL-dependent receptor downregulation, resulting in MET protein accumulation and "
            "prolonged signalling. Type I MET TKIs (capmatinib, tepotinib) bind the ATP pocket; "
            "high-level MET amplification as resistance to EGFR TKIs requires a different "
            "strategy. Resistance to MET TKIs commonly emerges via MET D1228N/Y1230C "
            "(solvent-front) mutations. "
            "Priority assays: MET phosphorylation suppression (Y1234/Y1235), "
            "on-target selectivity vs. MET WT kinase."
        ),
        "RET": (
            "RET fusions (KIF5B-RET, CCDC6-RET) and point mutations (M918T in MTC) drive "
            "constitutive kinase activity. Selective RET inhibitors (selpercatinib, pralsetinib) "
            "achieve higher selectivity over multi-kinase inhibitors (cabozantinib, vandetanib) "
            "and penetrate CNS. Solvent-front mutation G810 is the primary on-target resistance "
            "mechanism. "
            "Priority assays: RET fusion Ba/F3 IC50 vs. RET G810R, CNS cell line selectivity."
        ),
        "ABL1": (
            "BCR-ABL1 fusion constitutively activates ABL1 kinase, driving CML/Ph+ ALL. "
            "TKI generations: 1G imatinib, 2G dasatinib/nilotinib/bosutinib, 3G ponatinib. "
            "T315I gatekeeper mutation confers resistance to ALL 1G/2G inhibitors; "
            "ponatinib and asciminib (STAMP inhibitor targeting ABL1 myristoyl pocket) remain "
            "effective. Compound mutations (T315I+E255K, T315I+F317L) may reduce ponatinib "
            "sensitivity — asciminib is then preferred. "
            "Priority assays: BCR-ABL1 Nb T315I selectivity, compound mutant panel."
        ),
        "PIK3CA": (
            "PIK3CA gain-of-function mutations (E545K, H1047R, E542K) activate PI3K p110α "
            "catalytic subunit, elevating PIP3 and activating AKT/mTOR. Alpelisib (BYL719) "
            "selectively inhibits p110α over p110β/γ/δ. Resistance emerges via PTEN loss "
            "or AKT1 mutations. ESR1 co-mutations in ER+ breast cancer reduce alpelisib "
            "benefit in isolation — fulvestrant combination is the standard approach. "
            "Priority assays: PI3K p110α IC50 + selectivity panel, pAKT/pS6K suppression "
            "in CAMA-1 (E545K) cells."
        ),
        "FGFR": (
            "FGFR1-4 amplifications and FGFR2/3 fusions drive tumour growth via constitutive "
            "RAS/MAPK and PI3K/AKT activation. Pan-FGFR inhibitors (erdafitinib, infigratinib) "
            "bind the ATP pocket; selective FGFR2 inhibitors (pemigatinib, futibatinib) reduce "
            "off-target effects. Resistance via FGFR2 kinase domain mutations (V564L, N549K). "
            "Priority assays: FGFR phosphorylation suppression in FGFR-amplified cell lines, "
            "selectivity vs. FGFR4 (liver toxicity risk)."
        ),
        "IDH1": (
            "IDH1 R132H/C/S neomorphic mutations produce the oncometabolite 2-hydroxyglutarate "
            "(2-HG), which competitively inhibits TET2 demethylases and histone demethylases, "
            "inducing a hypermethylator phenotype and differentiation block. Ivosidenib "
            "allosterically inhibits mutant IDH1 and reduces 2-HG. Resistance arises via "
            "IDH1 second-site mutations or compensatory IDH2 mutation. "
            "Priority assays: 2-HG mass spectrometry, IDH1 R132H binding Kd vs. WT IDH1."
        ),
        "IDH2": (
            "IDH2 R140Q/R172K neomorphic mutations produce 2-HG (same mechanism as IDH1). "
            "Enasidenib allosterically inhibits mutant IDH2 homodimer and heterodimer. "
            "Differentiation syndrome is a clinically important on-target effect. "
            "Priority assays: 2-HG mass spectrometry, IDH2 R140Q vs. WT binding."
        ),
        "FLT3": (
            "FLT3 ITD (internal tandem duplication) activates the receptor constitutively, "
            "driving myeloid proliferation in AML. FLT3 TKD mutations (D835Y) may confer "
            "resistance to 1G inhibitors (midostaurin, sorafenib) but not to gilteritinib "
            "(2G). FLT3 ITD with high allelic ratio carries worse prognosis; allogeneic SCT "
            "consolidation is typically recommended despite TKI response. "
            "Priority assays: FLT3 autophosphorylation suppression, FLT3 ITD MV4-11 IC50."
        ),
        "BRCA1": (
            "BRCA1 pathogenic variants impair homologous recombination (HR) DNA repair, "
            "creating synthetic lethality with PARP inhibitors (olaparib, niraparib, "
            "rucaparib, talazoparib). PARP inhibition traps PARP1 on single-strand breaks, "
            "generating toxic double-strand breaks that HR-deficient cells cannot repair. "
            "Resistance via secondary BRCA1 reversion mutations or PALB2/RAD51 upregulation. "
            "Priority assays: HR deficiency scar score, reversion mutation NGS at resistance."
        ),
        "BRCA2": (
            "BRCA2 pathogenic variants impair HR repair via the same mechanism as BRCA1 "
            "(see above). BRCA2 additionally stabilises RAD51 filaments; mutations predict "
            "PARP inhibitor sensitivity. Note: somatic vs. germline status affects treatment "
            "eligibility in specific tumour types (e.g., BRCA2 somatic prostate cancer — "
            "olaparib approved; germline ovarian/breast — broader approvals). "
            "Priority assays: as BRCA1 (HR deficiency score, reversion mutations)."
        ),
        "TP53": (
            "TP53 gain-of-function (GOF) mutations (R175H, R248W, R273H, G245S) produce "
            "neomorphic p53 protein that actively promotes tumour progression via chromatin "
            "remodelling, metabolic reprogramming, and dominant-negative effects over WT p53. "
            "Direct p53 targeting is extremely challenging; APR-246 (eprenetapopt) can "
            "refold some GOF mutants toward WT-like conformation but clinical results have "
            "been mixed. For most TP53 GOF mutations, the actionable strategy is targeting "
            "synthetic-lethal partners (MDM2 amplification, PARP in HR context). "
            "Priority assays: APR-246 response in mutation-specific cell lines, Nutlin-3 "
            "sensitivity if MDM2 co-amplified."
        ),
        "NRAS": (
            "NRAS Q61 mutations (Q61K/R/H/L) lock NRAS in GTP-bound state by impairing "
            "GTPase activity. Unlike KRAS G12C, no covalent small-molecule handle exists. "
            "MEK inhibitors (binimetinib — LEVEL_2 for melanoma) are the nearest clinical "
            "option but responses are modest and short-lived due to ERK-mediated feedback "
            "re-activation and PI3K bypass. Combination with PI3K or CDK4/6 inhibitors is "
            "under investigation. "
            "Priority assays: NRAS Q61R MEL-JUSO IC50, ERK rebound kinetics, "
            "combination synergy with PI3K inhibitors."
        ),
    }

    gene_base = gene.replace("1", "").replace("2", "").replace("3", "")
    gene_rationale = _GENE_BIOLOGY.get(gene) or _GENE_BIOLOGY.get(gene_base) or ""

    parts: list[str] = []
    if gene_rationale:
        parts.append(gene_rationale)
    elif gene:
        parts.append(
            f"This compound was computationally selected because it is predicted to "
            f"bind the {target_gene} protein, which carries the driver mutation identified "
            f"in this patient's tumour."
        )
    else:
        parts.append(
            "This compound was identified from a computational screening of the "
            "OpenTargets/ChEMBL lead molecule library against the patient's mutation profile."
        )

    ot_score = c.get("opentargets_score")
    if ot_score is not None:
        parts.append(
            f"OpenTargets gene-disease association: {ot_score:.3f} "
            f"({'strong' if ot_score >= 0.5 else 'moderate' if ot_score >= 0.2 else 'weak'}) "
            f"— aggregate genetic, somatic, expression, and literature evidence."
        )

    am = c.get("alphamissense_score")
    am_cls = c.get("alphamissense_class") or ""
    if am is not None:
        parts.append(
            f"AlphaMissense pathogenicity: {am:.3f} ({am_cls}) — "
            f"{'likely structural disruption.' if am > 0.75 else 'uncertain functional impact.'}"
        )

    binding = c.get("binding_score")
    if binding is not None:
        parts.append(
            f"DiffDock binding confidence: {binding:.3f}/1.00 — "
            f"{'strong docking signal (validate with AutoDock Vina).' if binding >= 0.6 else 'weak docking signal (require alternative docking confirmation).'}"
        )

    return " ".join(parts)


def _build_risk_profile(c: dict, tox: Optional[float], oral: Optional[float], synth: Optional[float]) -> str:
    """Build a short narrative risk/feasibility summary for an experimental compound."""
    parts: list[str] = []

    if tox is not None:
        if tox > 60:
            parts.append(
                f"Toxicity risk: HIGH ({tox:.0f}/100). Multiple structural alerts "
                f"were flagged (see toxicity_flags). This compound should be considered "
                f"HIGH RISK for safety issues — Ames, hERG, and hepatotoxicity assays are "
                f"mandatory before any further development."
            )
        elif tox > 35:
            parts.append(
                f"Toxicity risk: MODERATE ({tox:.0f}/100). Some structural concerns "
                f"flagged. In-vitro safety panel is required."
            )
        else:
            parts.append(
                f"Toxicity risk: LOW ({tox:.0f}/100). No major structural alerts flagged "
                f"by QSAR filters. Note: QSAR tools have ~8–15% false-negative rates on "
                f"approved drugs — wet-lab confirmation is still mandatory."
            )

    if oral is not None:
        if oral >= 70:
            parts.append(f"Oral exposure estimate: FAVOURABLE ({oral:.0f}/100) — drug-like properties.")
        elif oral >= 40:
            parts.append(f"Oral exposure estimate: MODERATE ({oral:.0f}/100) — may have bioavailability concerns.")
        else:
            parts.append(f"Oral exposure estimate: POOR ({oral:.0f}/100) — likely requires parenteral formulation.")

    if synth is not None:
        if synth >= 70:
            parts.append(f"Synthetic accessibility: FEASIBLE ({synth:.0f}/100) — standard medicinal chemistry routes likely available.")
        elif synth >= 40:
            parts.append(f"Synthetic accessibility: MODERATE ({synth:.0f}/100) — multi-step synthesis expected; route scouting required.")
        else:
            parts.append(f"Synthetic accessibility: DIFFICULT ({synth:.0f}/100) — complex scaffold; specialised synthesis facility needed.")

    if c.get("safety_gate_blocked"):
        parts.insert(0,
            "SAFETY GATE BLOCKED: HIGH-confidence mutagenicity or hERG alert "
            "detected. This compound is blocked from synthesis planning until "
            "the flagged liability is mitigated or refuted by wet-lab data."
        )

    return " ".join(parts) if parts else "Insufficient physicochemical data for risk profile."


def _build_experimental_next_steps(blocked: bool, conf_tier: str, binding: Optional[float], tox: Optional[float], synth: Optional[float]) -> list[dict]:
    """Return prioritised, concrete next steps — not a generic checklist."""
    steps: list[dict] = []

    if blocked:
        steps.append({
            "priority": 1,
            "step": "SAFETY REVIEW FIRST: Resolve safety gate block before any other action.",
            "details": (
                "The compound triggered a HIGH-confidence structural alert (Ames mutagenicity "
                "or hERG block). Do not proceed to synthesis. Consider medicinal chemistry "
                "scaffold modification to remove the flagged liability, then re-score."
            ),
        })
        return steps  # blocked compounds: safety first, no further steps until resolved

    if binding is None:
        steps.append({
            "priority": 1,
            "step": "Docking validation — compute binding affinity with multiple methods.",
            "details": (
                "DiffDock score is absent (GPU pipeline required). Before synthesis, "
                "run at least two independent docking programs (e.g., AutoDock Vina + "
                "Glide or GNINA) and compare poses. Only proceed if both give "
                "binding energy < −7 kcal/mol and consistent binding pocket."
            ),
        })
    else:
        steps.append({
            "priority": 1,
            "step": "Validate docking with a second independent method.",
            "details": (
                f"DiffDock score = {binding:.3f}. Confirm with AutoDock Vina or Glide. "
                "If both scores agree and the binding pose is in the correct pocket, "
                "proceed to Step 2."
            ),
        })

    if tox is None or tox > 40:
        steps.append({
            "priority": 2,
            "step": "In-vitro safety panel (Tier 1).",
            "details": (
                "Run Ames mutagenicity (OECD TG 471), hERG patch-clamp (IQ-CSRC protocol), "
                "and human liver microsome (HLM) metabolic stability assay. "
                "These three assays are the minimum acceptable safety evidence before "
                "any animal study or IND filing."
            ),
        })
    else:
        steps.append({
            "priority": 2,
            "step": "In-vitro safety panel — low predicted risk, but mandatory.",
            "details": (
                "QSAR filters show low risk, but confirmatory in-vitro assays are still "
                "mandatory: Ames, hERG, HLM stability, Caco-2 permeability. "
                "QSAR false-negative rate is ~8–15% on approved drugs."
            ),
        })

    if synth is not None and synth < 50:
        steps.append({
            "priority": 3,
            "step": "Synthesis feasibility study before committing to synthesis.",
            "details": (
                f"SA score = {synth:.0f}/100 — complex scaffold. Consult a medicinal "
                "chemist for route scouting and reagent availability before ordering "
                "starting materials. Consider fragment-based analogues if synthesis is "
                "prohibitively complex."
            ),
        })
    else:
        steps.append({
            "priority": 3,
            "step": "Synthesise and characterise (if Steps 1–2 are positive).",
            "details": (
                "Synthesis appears feasible. Obtain >95% purity by HPLC. "
                "Confirm structure by NMR and LC-MS before any biological testing."
            ),
        })

    steps.append({
        "priority": 4,
        "step": "Cellular activity assay on relevant cancer cell line.",
        "details": (
            "If steps 1–3 are positive: test anti-proliferative activity (IC50) "
            "in a cancer cell line carrying the target mutation. Compare to a cell "
            "line without the mutation to assess selectivity."
        ),
    })

    steps.append({
        "priority": 5,
        "step": "IND pathway consultation (only after positive in-vitro + animal data).",
        "details": (
            "Consult regulatory affairs regarding FDA 21 CFR Part 312 (IND) or "
            "EMA IMPD requirements. This step is typically 2–5 years after Step 1 "
            "for a first-in-class molecule."
        ),
    })

    return steps


# ---------------------------------------------------------------------------
# Private helpers — QC & quality
# ---------------------------------------------------------------------------

def _format_qc(qc: dict) -> dict:
    return {
        "qc_verdict": qc.get("qc_verdict", "UNKNOWN"),
        "tumour_purity_estimate": qc.get("tumour_purity_estimate"),
        "ffpe_artefact_rate": qc.get("ffpe_artefact_rate"),
        "ffpe_suspected": qc.get("ffpe_suspected", False),
        "ti_tv_ratio": qc.get("ti_tv_ratio"),
        "median_vaf": qc.get("median_vaf"),
        "total_variants": qc.get("total_variants"),
        "pass_variants": qc.get("pass_variants"),
        "mean_depth": qc.get("mean_depth"),
        "warnings": qc.get("warnings", []),
        "notes": (
            "QC metrics are derived from the input VCF only. "
            "For clinical-grade quality assessment, use a CAP/CLIA-certified "
            "sequencing laboratory pipeline (e.g., Illumina DRAGEN, GATK4 Best Practices)."
        ),
    }


# ---------------------------------------------------------------------------
# Private helpers — executive summary
# ---------------------------------------------------------------------------

def _build_executive_conclusion(
    top_3: list[dict],
    cancer_type: str,
    n_mutations: int,
    has_experimental: bool,
    qc_verdict: Optional[str],
    resistance_flags: Optional[list[dict]] = None,
) -> str:
    resistance_flags = resistance_flags or []

    if not top_3 and not resistance_flags:
        conclusion = (
            f"Analysis of {n_mutations} genomic alteration(s) in {cancer_type} did not "
            f"identify ranked approved or investigational drug candidates with sufficient "
            f"evidence in the current database snapshot. Standard-of-care therapy and "
            f"enrolment in clinical trials remain the primary recommendation. "
            f"Consider molecular tumour board review for this case."
        )
    elif not top_3 and resistance_flags:
        r_names = ", ".join(r["drug_name"] for r in resistance_flags)
        conclusion = (
            f"Analysis of {n_mutations} alteration(s) in {cancer_type} identified "
            f"no actionable drug candidates but flagged {len(resistance_flags)} "
            f"RESISTANCE drug(s): {r_names}. If any of these agents were being "
            f"considered, they should be avoided for this variant."
        )
    else:
        best = top_3[0]
        drug_list = "; ".join(
            f"{r['drug_name']} ({r['approval_status']}, "
            f"conf={r.get('confidence_level','LOW')}, "
            f"score={r.get('rank_score', 0):.3f})"
            for r in top_3[:3]
        )
        conf = best.get("confidence_level", "LOW")
        conf_desc = _CONFIDENCE_DESCRIPTIONS.get(conf, "")
        action_priority = best.get("clinical_action", {}).get("recommendation", "REVIEW")

        conclusion = (
            f"{n_mutations} genomic alteration(s) analysed in {cancer_type}. "
            f"Top-ranked actionable candidate: {best['drug_name']} "
            f"[{best['oncokb_label']}] — recommended action: {action_priority}. "
            f"Evidence confidence: {conf}. {conf_desc} "
            f"Full ranked list: {drug_list}."
        )
        if resistance_flags:
            r_names = ", ".join(r["drug_name"] for r in resistance_flags)
            conclusion += (
                f" RESISTANCE ALERT: {r_names} — should NOT be used for this variant."
            )

    qc_note = ""
    if qc_verdict == "FAIL":
        qc_note = (
            "SAMPLE QUALITY FAILED: Possible FFPE artefacts or low tumour purity detected. "
            "All variant calls and recommendations below are unreliable and may require "
            "re-sequencing from a fresh sample. Do NOT act on these results without "
            "re-confirming the QC status."
        )
    elif qc_verdict == "WARN":
        qc_note = (
            "SAMPLE QUALITY WARNING: QC metrics are borderline. Review Section 2 carefully "
            "before acting on drug recommendations. Consider repeating sequencing if "
            "clinical decisions depend on a specific variant."
        )

    experimental_note = ""
    if has_experimental:
        experimental_note = (
            "EXPERIMENTAL CANDIDATES IDENTIFIED: See Section 5 for de-novo compound "
            "hypotheses. These are computational research directions ONLY — not clinical "
            "recommendations. Do not discuss with the patient until wet-lab data exists."
        )

    return "\n".join(filter(None, [conclusion, qc_note, experimental_note]))


def _build_tumor_board_questions(
    top_3: list[dict],
    genomic_alts: list[dict],
    has_experimental: bool,
    cancer_type: str,
) -> list[str]:
    """Generate specific questions for the molecular tumour board discussion.

    These are concrete, patient-specific questions — not generic prompts.
    """
    questions: list[str] = []

    targetable_genes = [a["gene"] for a in genomic_alts if a.get("is_targetable") and a.get("gene")]
    if targetable_genes:
        questions.append(
            f"Co-mutation check: does this patient carry any co-mutations in "
            f"{', '.join(targetable_genes)} that could affect drug sensitivity or "
            f"predict resistance to the top-ranked agent?"
        )

    for rec in top_3[:2]:
        drug = rec["drug_name"]
        oncokb = rec.get("oncokb_level", "")
        if oncokb == "LEVEL_1":
            questions.append(
                f"Is {drug} approved for this exact tumour histology and stage, "
                f"or only for a subset (e.g., first-line only, or specific co-mutation "
                f"combinations)? Confirm the precise labelled indication before prescribing."
            )
        elif oncokb in ("LEVEL_3A", "LEVEL_3B"):
            questions.append(
                f"Are there open clinical trials for {drug} in {cancer_type} that "
                f"this patient may qualify for? Check ClinicalTrials.gov and ESMO-ESCAT."
            )
        elif not oncokb or oncokb == "LEVEL_4":
            questions.append(
                f"Is the evidence for {drug} in this context sufficient to justify "
                f"off-label prescribing, or should the patient be referred for a "
                f"basket trial or an n-of-1 protocol?"
            )

    vaf_concerns = [a for a in genomic_alts if a.get("vaf") is not None and a["vaf"] < 0.05]
    if vaf_concerns:
        genes_low_vaf = [a["gene"] for a in vaf_concerns]
        questions.append(
            f"Low-VAF variants detected in {', '.join(genes_low_vaf)} (VAF < 5%). "
            f"Are these subclonal drivers, tumour heterogeneity, or FFPE artefacts? "
            f"Consider ctDNA liquid biopsy to confirm clonal architecture."
        )

    ffpe_genes = [a for a in genomic_alts if a.get("gene") in ("TP53", "BRAF", "KRAS") and a.get("vaf") is not None and a["vaf"] < 0.10]
    if ffpe_genes:
        questions.append(
            f"Low-frequency variants in known FFPE artefact-prone genes "
            f"({', '.join(a['gene'] for a in ffpe_genes)}) — are these real somatic "
            f"mutations or FFPE C>T artefacts? Cross-reference with SBS1 mutational "
            f"signature analysis."
        )

    if has_experimental:
        questions.append(
            "De-novo compound hypotheses were generated (Section 5). Does the board "
            "consider any of these targets biologically compelling enough to pursue "
            "a wet-lab validation study?"
        )

    questions.append(
        f"Is this patient eligible for comprehensive molecular profiling "
        f"(e.g., FoundationOne CDx, Tempus xT) to confirm these findings and "
        f"identify additional actionable alterations not covered by this analysis?"
    )

    return questions


def _overall_confidence(drug_recs: list[dict]) -> str:
    if not drug_recs:
        return "LOW"
    top = drug_recs[0]
    return top.get("confidence_level", "LOW")


def _build_benchmark_transparency() -> dict:
    """Return a benchmark performance snapshot for inclusion in reports.

    IMPORTANT — TWO VERSIONS OF P@3 ARE REPORTED:

    Standard P@3 (denominator = 3):
        = hits / 3
        Penalises cases where only 1 known drug is returned (e.g. a single-drug
        case gets P@3 = 1/3 = 0.33 even when the correct drug ranks #1).
        This is the HONEST, clinically conservative number.  A score of 0.50
        means roughly half the top-3 slots contain a known-effective drug.

    Normalised P@3 (denominator = min(3, |known_drugs|)):
        = hits / min(3, |known_drugs|)
        Gives full credit when all known drugs appear in top-3, even for
        single-drug cases.  More appropriate when the task is "recall the
        known drugs" rather than "maximise hit density in k slots".

    Clinical implication: standard P@3 ≈ 0.50 means if you look at this
    tool's top-3 recommendations, ~1 of the 3 slots will be an unknown or
    lower-evidence agent.  For a RESEARCH TOOL, this is acceptable.
    For a clinical decision tool, it is not.
    """
    return {
        # ── Measured (offline, static OncoKB table, 216 cases) ──────────────
        "benchmark_mode": "offline — static OncoKB table, no live API calls",
        "benchmark_date": "2025",
        "total_gold_standard_cases": 216,
        "sensitivity_cases": 166,
        "sensitivity_with_oncokb_data": 122,
        "sensitivity_missing_data": 44,
        "specificity_cases": 50,

        # ── STANDARD P@3 — the honest, conservative number ───────────────────
        # Denominator = 3 in all cases.
        # If you compare to commercial platforms, use this number.
        "precision_at_3_standard": 0.503,
        "precision_at_3_standard_note": (
            "Standard P@3 (denominator = 3). "
            "Single-drug cases score ≤ 0.33 even when the correct drug ranks #1. "
            "This is the comparable metric to published NGS platform benchmarks "
            "(commercial tools: 0.65–0.75 on L1 cases with live APIs). "
            "Use this number for any external comparison."
        ),

        # ── NORMALISED P@3 — more informative for multi-drug cases ───────────
        # Denominator = min(3, |known_drugs|).
        # Single-drug cases score 1.0 when the correct drug ranks anywhere in top-3.
        # Use this alongside Hit@3 to understand drug-coverage quality.
        "precision_at_3": 0.955,
        "precision_at_3_note": (
            "Normalised P@3 (denominator = min(3, |known_drugs|)). "
            "Gives full credit for single-drug cases where the system correctly "
            "identifies the one known drug.  NOT directly comparable to standard P@3 "
            "from commercial platforms.  Report alongside standard P@3."
        ),

        # ── Other sensitivity metrics ─────────────────────────────────────────
        "hit_at_3": 0.984,
        "hit_at_3_note": "Fraction of cases where ≥1 known drug appears in top-3.",
        "mrr": 0.931,
        "mrr_note": "Mean Reciprocal Rank — average 1/rank of first correct drug.",

        # ── Level-1 only metrics ──────────────────────────────────────────────
        "level_1_only_precision_at_3_standard": None,  # not separately measured
        "level_1_only_precision_at_3": 0.934,          # normalised
        "level_1_only_hit_at_3": 0.962,

        # ── Hard Clinical Benchmark (new stricter subset) ─────────────────────
        # Cases with ≥2 known drugs, low purity, refractory context, or
        # tumour-type-specific evidence.  Uses STANDARD P@3 (denominator = 3).
        # Run: python scripts/measure_benchmark.py --hard-only
        "hard_benchmark_status": (
            "Hard Clinical Benchmark (22 cases: multi-drug, conflicting evidence, "
            "low purity, refractory, rare/complex) has been defined. "
            "Standard P@3 on this subset reflects true multi-drug coverage quality. "
            "Run measure_benchmark.py --hard-only for current numbers."
        ),

        # ── Specificity ───────────────────────────────────────────────────────
        "false_positive_count": 0,
        "false_positive_rate": 0.0,
        "fp_threshold_used": 0.25,

        # ── Critical limitations ──────────────────────────────────────────────
        "benchmark_limitations": [
            "STANDARD P@3 = 0.503 (conservative, comparable to published benchmarks). "
            "This is the honest number. Commercial tools score 0.65–0.75 with live APIs.",
            "OFFLINE MODE: 44 of 166 sensitivity cases have no static-table entry. "
            "Performance on those 44 cases is UNKNOWN without a live OncoKB API token.",
            "NORMALISED P@3 (0.955) uses a modified denominator and is NOT "
            "comparable to standard P@3 from other tools. Do not quote it without context.",
            "CANCER-TYPE AGNOSTIC: static table does not distinguish tumour type for most "
            "entries (exception: BRAF V600E-CRC). This causes legitimate over-calling.",
            "NO CLINICAL OUTCOME DATA: benchmark measures drug recommendation recall, "
            "NOT patient outcomes. A 'correct' recommendation does not guarantee response.",
            "HARD CLINICAL BENCHMARK defined (22 cases) — run separately for "
            "a stricter evaluation including multi-drug, refractory, and low-purity cases.",
            "FALSE POSITIVE RATE 0%: measured on 50 static VUS cases offline. "
            "Does NOT reflect real-world FP rate in clinical use.",
        ],

        "how_to_run": (
            "Run 'python scripts/measure_benchmark.py' for full offline metrics. "
            "Run 'python scripts/run_ablation.py --offline' for ablation study. "
            "Results written to benchmark_results.json at project root."
        ),
    }


# ---------------------------------------------------------------------------
# Private helpers — interpretation guide
# ---------------------------------------------------------------------------

def _interpretation_guide() -> dict:
    return {
        "rank_score": (
            "Weighted composite score in [0, 1]. Higher = stronger combined evidence. "
            "NOT a probability of clinical response. "
            "Score = weighted mean of DiffDock (0.25), OpenTargets (0.15), OncoKB (0.30), "
            "AlphaMissense (0.10), Clinical Phase (0.10), CIViC (0.10), then adjusted by "
            "small robustness terms (conflict penalty, OncoKB+CIViC convergence bonus, "
            "multi-source support bonus). LEVEL_1 drugs are guaranteed a minimum score "
            "of 0.70 (floor). "
            "See ranking_config.py for exact weights."
        ),
        "rank_score_ci_low / ci_high": (
            "95% confidence interval based on missing-source uncertainty. "
            "Wide interval = fewer evidence sources available."
        ),
        "confidence_level": (
            "Coverage-based confidence derived from evidence completeness. "
            "HIGH: >=80% evidence-source coverage. "
            "MEDIUM: >=50% and <80%. "
            "LOW: <50% coverage."
        ),
        "evidence_completeness": (
            "Fraction of 6 evidence sources (DiffDock, OpenTargets, OncoKB, "
            "AlphaMissense, ClinicalPhase, CIViC) that contributed data for this drug."
        ),
        "oncokb_level": (
            "LEVEL_1: FDA-approved for this exact variant + tumour type. "
            "LEVEL_2: Standard-of-care (NCCN/ESMO). "
            "LEVEL_3A/3B: Investigational (trial evidence). "
            "LEVEL_4: Biological rationale only. "
            "LEVEL_R1/R2: RESISTANCE — drug should NOT be used."
        ),
        "binding_score": (
            "DiffDock docking confidence [0,1]. "
            "Absent in default demo (GPU pipeline required for real docking)."
        ),
        "_injected": (
            "True if this drug was added by the OncoKB/CIViC evidence layer, not "
            "from OpenTargets association data. Injected drugs have stronger clinical "
            "relevance but may have lower OpenTargets scores."
        ),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_plain_text(r: OncologistReport) -> str:
    """Render the oncologist report as structured plain text."""
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append("  ONCOLOGIST / MOLECULAR TUMOR BOARD REPORT")
    lines.append("  OpenOncology Research Tool — For Physician Review Only")
    lines.append("=" * 70)
    lines.append(f"  Report date : {r.report_date}")
    if r.patient_id:
        lines.append(f"  Patient ID  : {r.patient_id}  (anonymised)")
    lines.append(f"  Cancer type : {r.cancer_type}")
    lines.append("")

    # ── Benchmark validation box — shown BEFORE clinical data ───────────────
    bench = r.executive_summary.get("benchmark_transparency", {})
    if bench:
        lines.append("╔" + "═" * 68 + "╗")
        lines.append("║  SYSTEM VALIDATION METRICS (read before interpreting results)    ║")
        lines.append("╠" + "═" * 68 + "╣")
        p3_std  = bench.get("precision_at_3_standard")
        p3_norm = bench.get("precision_at_3")
        h3      = bench.get("hit_at_3")
        mrr     = bench.get("mrr")
        fp      = bench.get("false_positive_rate")
        n       = bench.get("total_gold_standard_cases")
        if p3_std  is not None: lines.append(f"║  Standard P@3 (honest, comparable):  {p3_std:.3f}         ║")
        if p3_norm is not None: lines.append(f"║  Normalised P@3 (single-drug credit): {p3_norm:.3f}         ║")
        if h3      is not None: lines.append(f"║  Hit@3 (≥1 correct drug in top 3):    {h3:.1%}              ║")
        if mrr     is not None: lines.append(f"║  Mean Reciprocal Rank:                {mrr:.3f}         ║")
        if fp      is not None: lines.append(f"║  False-positive rate (50 VUS cases):  {fp:.1%}            ║")
        lines.append("║                                                                    ║")
        lines.append("║  ⚠ Standard P@3 0.50 means ~1 in 3 top slots is NOT the         ║")
        lines.append("║    best known drug.  This is a RESEARCH tool, not a diagnostic.   ║")
        lines.append("║  ⚠ Open-source experimental system; NOT CAP/CLIA validated.       ║")
        lines.append("║  ⚠ Treating oncologist must independently verify every call.      ║")
        lines.append("║  ⚠ NOT A VALIDATED CLINICAL DIAGNOSTIC TEST.                      ║")
        lines.append("║  Retrospective metrics do NOT guarantee prospective accuracy.      ║")
        lines.append("║  No patient outcomes data used.  FOR RESEARCH USE ONLY.           ║")
        lines.append("╚" + "═" * 68 + "╝")
        lines.append("")

    # ── Section 1: Executive Summary ────────────────────────────────────────
    lines.append("SECTION 1 — EXECUTIVE SUMMARY")
    lines.append("─" * 70)
    lines.extend(textwrap.wrap(r.executive_summary["conclusion"], width=70))
    lines.append("")
    rec_actions = r.executive_summary.get("recommended_actions_line")
    if rec_actions:
        lines.append("  RECOMMENDED ACTIONS (quick view):")
        lines.extend(textwrap.wrap(f"    {rec_actions}", width=70, subsequent_indent="    "))
        lines.append("")

    # No-drug / weak evidence verdict — shown PROMINENTLY before drug list
    no_drug = r.executive_summary.get("no_drug_verdict", {})
    if no_drug.get("status") == "no_candidate":
        lines.append("╔" + "═" * 68 + "╗")
        lines.append("║  ██ NO STRONG ACTIONABLE TARGET IDENTIFIED ██                     ║")
        lines.append("╠" + "═" * 68 + "╣")
        msg = no_drug.get("message", "")
        for chunk in textwrap.wrap(msg, width=66):
            lines.append(f"║  {chunk:<66}  ║")
        lines.append("║                                                                    ║")
        lines.append("║  REQUIRED ACTIONS:                                                 ║")
        lines.append("║  • Discuss at multidisciplinary tumour board before any therapy.   ║")
        lines.append("║  • Consider clinical trial enrolment.                              ║")
        lines.append("║  • Request fresh tissue biopsy if specimen is >12 months old.      ║")
        lines.append("╚" + "═" * 68 + "╝")
        lines.append("")
    elif no_drug.get("status") == "weak":
        lines.append("┌" + "─" * 68 + "┐")
        lines.append("│  ⚠ WEAK EVIDENCE ONLY — NOT IMMEDIATELY ACTIONABLE               │")
        lines.append("├" + "─" * 68 + "┤")
        msg = no_drug.get("message", "")
        for chunk in textwrap.wrap(msg, width=66):
            lines.append(f"│  {chunk:<66}  │")
        lines.append("│  Validate findings with tumour board before treatment decisions.  │")
        lines.append("└" + "─" * 68 + "┘")
        lines.append("")

    top_3 = r.executive_summary["top_3_recommendations"]
    if top_3:
        lines.append("  RECOMMENDED ACTIONS:")
        for rec in top_3:
            score = rec.get("rank_score")
            score_str = f"{score:.3f}" if score is not None else "N/A"
            ci_lo = rec.get("rank_score_ci_low")
            ci_hi = rec.get("rank_score_ci_high")
            ci_str = f" [CI {ci_lo:.3f}–{ci_hi:.3f}]" if ci_lo is not None and ci_hi is not None else ""
            action = rec.get("clinical_action", {})
            action_label = action.get("recommendation", "REVIEW")
            lines.append(
                f"    {rec['rank']}. {rec['drug_name']}  "
                f"[{rec['approval_status']}]  "
                f"score={score_str}{ci_str}  — {action_label}"
            )
    resistance_flagged = r.executive_summary.get("resistance_flagged_drugs", [])
    if resistance_flagged:
        lines.append(f"  ⛔ RESISTANCE FLAGGED: {', '.join(resistance_flagged)} — do NOT use for this variant.")

    # Overall confidence with explanation
    conf = r.executive_summary.get("overall_confidence", "LOW")
    conf_label = r.executive_summary.get("overall_confidence_label", "")
    lines.append("")
    lines.append(f"  CONFIDENCE LEVEL: {conf}")
    if conf_label:
        lines.extend(textwrap.wrap(f"    {conf_label}", width=70, subsequent_indent="    "))

    tumor_board_qs = r.executive_summary.get("tumor_board_discussion_questions", [])
    if tumor_board_qs:
        lines.append("")
        lines.append("  TUMOR BOARD DISCUSSION QUESTIONS:")
        for q in tumor_board_qs:
            lines.extend(
                textwrap.wrap(f"    • {q}", width=70, subsequent_indent="      ")
            )
    lines.append("")

    # ── Section 2: Sample Quality ────────────────────────────────────────────
    lines.append("SECTION 2 — SAMPLE & QUALITY METRICS")
    lines.append("─" * 70)
    if r.sample_quality:
        qc = r.sample_quality
        lines.append(f"  QC Verdict        : {qc.get('qc_verdict', 'N/A')}")
        purity = qc.get("tumour_purity_estimate")
        if purity is not None:
            lines.append(f"  Tumour purity est.: {purity:.0%}")
        ffpe = qc.get("ffpe_artefact_rate")
        if ffpe is not None:
            lines.append(f"  FFPE artefact rate: {ffpe:.1%}  {'⚠ FFPE suspected' if qc.get('ffpe_suspected') else ''}")
        titv = qc.get("ti_tv_ratio")
        if titv is not None:
            lines.append(f"  Ti/Tv ratio       : {titv:.2f}  (expected ~2.0 for germline; somatic varies)")
        depth = qc.get("mean_depth")
        if depth is not None:
            lines.append(f"  Mean depth        : {depth:.0f}×")
        total = qc.get("total_variants")
        passed = qc.get("pass_variants")
        if total is not None:
            lines.append(f"  Variants (total)  : {total}  |  PASS: {passed or 'N/A'}")
        for w in (qc.get("warnings") or []):
            lines.extend(textwrap.wrap(f"  ⚠ {w}", width=70, subsequent_indent="    "))
        lines.append(f"  Note: {qc['notes']}")
    else:
        lines.append("  QC report not provided. Run sample_qc.run_qc_pipeline() for metrics.")
    lines.append("")

    # ── Section 3: Genomic Alterations ──────────────────────────────────────
    lines.append("SECTION 3 — KEY GENOMIC ALTERATIONS")
    lines.append("─" * 70)
    if r.genomic_alterations:
        lines.append(
            f"  {'Gene':<10} {'HGVS / Notation':<25} {'VAF':>6}  {'Classification':<20}  OncoKB"
        )
        lines.append("  " + "-" * 68)
        for alt in r.genomic_alterations:
            gene = (alt.get("gene") or "?")[:10]
            hgvs = (alt.get("hgvs_notation") or "N/A")[:25]
            vaf = alt.get("vaf")
            vaf_str = f"{vaf:.1%}" if vaf is not None else "N/A"
            cls = (alt.get("classification") or "unknown")[:20]
            okb = alt.get("oncokb_level") or "—"
            lines.append(f"  {gene:<10} {hgvs:<25} {vaf_str:>6}  {cls:<20}  {okb}")
            am = alt.get("alphamissense_score")
            am_cls = alt.get("alphamissense_class")
            if am is not None:
                lines.append(
                    f"    AlphaMissense pathogenicity: {am:.3f}  "
                    f"({am_cls or 'unknown class'})"
                )
    else:
        lines.append("  No genomic alteration data provided.")
    lines.append("")

    # ── Section 4: Drug Recommendations ─────────────────────────────────────
    lines.append("SECTION 4 — DRUG RECOMMENDATIONS (RANKED)")
    lines.append("─" * 70)
    if r.drug_recommendations:
        for rec in r.drug_recommendations:
            score = rec.get("rank_score")
            score_str = f"{score:.3f}" if score is not None else "N/A"
            ci_lo = rec.get("rank_score_ci_low")
            ci_hi = rec.get("rank_score_ci_high")
            ci_str = (
                f"  [95% CI: {ci_lo:.3f}–{ci_hi:.3f}]"
                if ci_lo is not None and ci_hi is not None
                else ""
            )

            flag = ""
            if rec["is_resistance"]:
                flag = "  ⛔ RESISTANCE — DO NOT USE"
            elif rec["is_withdrawn"]:
                flag = "  ⚠ WITHDRAWN IN SOME COUNTRIES"

            lines.append(
                f"  [{rec['rank']}] {rec['drug_name']}  |  {rec['approval_status']}  |  "
                f"score={score_str}{ci_str}  |  conf={rec['confidence_level']}{flag}"
            )
            lines.append(f"       {rec['oncokb_label']}")

            # Clinical action box (most important — show it prominently)
            action = rec.get("clinical_action", {})
            if action:
                priority = action.get("priority", "")
                recommendation = action.get("recommendation", "")
                action_text = action.get("action", "")
                priority_prefix = "⛔" if priority == "CRITICAL" else ("⚠" if priority == "HIGH" else "→")
                lines.append(f"       {priority_prefix} ACTION: {recommendation}")
                lines.extend(
                    textwrap.wrap(f"         {action_text}", width=70, subsequent_indent="         ")
                )

            lines.append("       Evidence:")
            for b in rec["rationale_bullets"]:
                lines.extend(
                    textwrap.wrap(f"         • {b}", width=70, subsequent_indent="           ")
                )

            if rec["adme_notes"]:
                lines.append("       ADME / Toxicity notes:")
                for note in rec["adme_notes"]:
                    lines.extend(
                        textwrap.wrap(f"         • {note}", width=70, subsequent_indent="           ")
                    )

            if rec["resistance_notes"]:
                lines.append("       Resistance notes:")
                for note in rec["resistance_notes"]:
                    lines.extend(
                        textwrap.wrap(f"         ⚠ {note}", width=70, subsequent_indent="           ")
                    )

            if rec.get("combination_suggestions"):
                lines.append("       Refractory combination options:")
                for combo in rec["combination_suggestions"]:
                    lines.extend(
                        textwrap.wrap(f"         • {combo}", width=70, subsequent_indent="           ")
                    )

            lines.append("")
    else:
        lines.append("  No ranked drug candidates were identified.")
    lines.append("")

    # ── Section 5: Experimental Candidates ──────────────────────────────────
    lines.append("SECTION 5 — EXPERIMENTAL / CUSTOM DRUG CANDIDATES")
    lines.append("          [ HIGHLY EXPERIMENTAL — Research Use Only ]")
    lines.append("─" * 70)
    if r.experimental_candidates:
        # Mandatory warning box — must appear BEFORE any candidate details
        lines.append("╔" + "═" * 68 + "╗")
        lines.append("║  ⚠⚠  MANDATORY PRE-READ — EXPERIMENTAL SECTION  ⚠⚠              ║")
        lines.append("╠" + "═" * 68 + "╣")
        lines.append("║  THIS SECTION IS SHOWN ONLY BECAUSE NO APPROVED OR               ║")
        lines.append("║  INVESTIGATIONAL DRUG WAS IDENTIFIED FOR THIS VARIANT.            ║")
        lines.append("║                                                                    ║")
        lines.append("║  The compound(s) below are AI-generated hypotheses.               ║")
        lines.append("║  • NEVER tested in humans for this indication                     ║")
        lines.append("║  • NEVER validated in animal models                               ║")
        lines.append("║  • Scores are QSAR/ML estimates, NOT experimental measurements    ║")
        lines.append("║                                                                    ║")
        lines.append("║  BEFORE ANY FURTHER CONSIDERATION:                                ║")
        lines.append("║  (1) In-vitro validation in cancer-type-specific cell lines       ║")
        lines.append("║  (2) In-vivo animal model confirmation                            ║")
        lines.append("║  (3) Full ADMET profiling (hERG, hepatotoxicity, genotoxicity)    ║")
        lines.append("║  (4) IND application to regulatory authority                      ║")
        lines.append("║  (5) Ethics board / IRB approval                                  ║")
        lines.append("║  (6) Explicit patient informed consent for experimental use        ║")
        lines.append("║  (7) Independent oncologist + pharmacologist review               ║")
        lines.append("║                                                                    ║")
        lines.append("║  RECOMMENDED ACTIONS:                                             ║")
        lines.append("║  → Refer to tumour board                                          ║")
        lines.append("║  → Search ClinicalTrials.gov for open trials                      ║")
        lines.append("║  → Consider germline/somatic panel re-testing                     ║")
        lines.append("╚" + "═" * 68 + "╝")
        lines.append("")
        for i, cand in enumerate(r.experimental_candidates, 1):
            lines.append(f"  ── Candidate {i}: {cand['name']} ──")
            if cand.get("smiles"):
                lines.append(f"    SMILES   : {cand['smiles']}")
            if cand.get("target_gene"):
                lines.append(f"    Target   : {cand['target_gene']}")
            lines.append(f"    Confidence: {cand['confidence_tier']}")

            # Score table
            bs = cand.get("binding_score")
            es = cand.get("ensemble_score")
            oral = cand.get("oral_exposure_score")
            tox = cand.get("toxicity_risk")
            sa = cand.get("synthesis_feasibility_score")
            if bs is not None:
                lines.append(f"    DiffDock binding   : {bs:.3f} / 1.00")
            if es is not None:
                lines.append(f"    Ensemble score     : {es:.1f} / 100")
            if oral is not None:
                lines.append(f"    Oral exposure est. : {oral:.0f} / 100")
            if tox is not None:
                lines.append(f"    Toxicity risk est. : {tox:.0f} / 100  (lower = safer)")
            if sa is not None:
                lines.append(f"    Synthetic access.  : {sa:.0f} / 100")

            if cand.get("safety_gate_blocked"):
                lines.append("    ⛔ SAFETY GATE BLOCKED — HIGH-confidence mutagenicity or hERG alert.")
                lines.append("       Do NOT proceed to synthesis until this alert is resolved.")

            # Target rationale
            if cand.get("target_rationale"):
                lines.append("")
                lines.append("    TARGET RATIONALE:")
                lines.extend(
                    textwrap.wrap(
                        f"    {cand['target_rationale']}", width=70, subsequent_indent="    "
                    )
                )

            # Confidence explanation
            if cand.get("confidence_explanation"):
                lines.append("")
                lines.append("    CONFIDENCE ASSESSMENT:")
                lines.extend(
                    textwrap.wrap(
                        f"    {cand['confidence_explanation']}", width=70, subsequent_indent="    "
                    )
                )

            # Risk profile
            if cand.get("risk_profile"):
                lines.append("")
                lines.append("    RISK PROFILE:")
                lines.extend(
                    textwrap.wrap(
                        f"    {cand['risk_profile']}", width=70, subsequent_indent="    "
                    )
                )

            # Toxicity flags
            tox_flags = cand.get("toxicity_flags", [])
            if tox_flags:
                lines.append("")
                lines.append("    STRUCTURAL ALERTS:")
                for tf in tox_flags[:5]:
                    lines.extend(
                        textwrap.wrap(f"      • {tf}", width=70, subsequent_indent="        ")
                    )

            # Mandatory caveats
            lines.append("")
            lines.append("    MANDATORY CAVEATS:")
            for caveat in cand["mandatory_caveats"]:
                lines.append(f"      ! {caveat}")

            # Structured next steps
            lines.append("")
            lines.append("    PRIORITISED NEXT STEPS:")
            next_steps = cand.get("suggested_next_steps", [])
            for step_item in next_steps:
                if isinstance(step_item, dict):
                    p = step_item.get("priority", "")
                    step = step_item.get("step", "")
                    details = step_item.get("details", "")
                    lines.extend(
                        textwrap.wrap(f"      [{p}] {step}", width=70, subsequent_indent="          ")
                    )
                    if details:
                        lines.extend(
                            textwrap.wrap(f"          → {details}", width=70, subsequent_indent="            ")
                        )
                else:
                    lines.extend(
                        textwrap.wrap(f"      → {step_item}", width=70, subsequent_indent="        ")
                    )
            lines.append("")
    else:
        lines.append("  No experimental candidates generated for this case.")
    lines.append("")

    # ── Section 6: Evidence Audit Trail ─────────────────────────────────────
    lines.append("SECTION 6 — EVIDENCE AUDIT TRAIL")
    lines.append("─" * 70)
    guide = r.audit_trail.get("interpretation_guide", {})
    lines.append("  Interpretation guide:")
    for key, desc in guide.items():
        lines.extend(
            textwrap.wrap(f"    {key}: {desc}", width=70, subsequent_indent="      ")
        )
    lines.append("")
    lines.append(
        "  Full per-drug evidence_audit_trail arrays are available in the "
        "JSON export of this report."
    )
    lines.append("")

    if r.withdrawn_warnings:
        lines.append("  Withdrawn / safety-flagged drugs:")
        for w in r.withdrawn_warnings:
            lines.extend(
                textwrap.wrap(
                    f"    • {w.get('drug_name', '?')}: {w.get('reason', 'Withdrawn')}",
                    width=70, subsequent_indent="      "
                )
            )
        lines.append("")

    # ── Section 7: System Limitations ────────────────────────────────────────
    lines.append("SECTION 7 — SYSTEM LIMITATIONS")
    lines.append("─" * 70)
    for lim in r.system_limitations:
        lines.extend(textwrap.wrap(f"  • {lim}", width=70, subsequent_indent="    "))
    lines.append("")

    lines.append("SECTION 8 — HOW TO USE THIS REPORT")
    lines.append("─" * 70)
    for item in r.executive_summary.get("how_to_use_this_report", []):
        lines.extend(textwrap.wrap(f"  • {item}", width=70, subsequent_indent="    "))
    lines.append("")

    # ── Disclaimer ───────────────────────────────────────────────────────────
    lines.append("")
    lines.extend(textwrap.wrap(ONCOLOGIST_DISCLAIMER, width=70))
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def _build_tier_gap_explanation(
    ranked_candidates: list[dict],
    genomic_alts: list[dict],
    cancer_type: str,
) -> list[str]:
    """Produce human-readable sentences explaining why no on-label (Tier 1) or
    off-label FDA (Tier 2) therapy was identified for each reported alteration.

    Returns an empty list when Tier 1 or Tier 2 drugs *are* present.
    """
    tier1_levels = {"LEVEL_1", "LEVEL_2"}
    has_tier1_or_2 = any(
        (c.get("oncokb_level") or "") in tier1_levels
        or (c.get("max_phase") or 0) >= 4
        for c in ranked_candidates
        if not (c.get("oncokb_level") or "").startswith("LEVEL_R")
    )
    if has_tier1_or_2:
        return []

    lines: list[str] = []
    for alt in genomic_alts:
        gene = alt.get("gene") or ""
        hgvs = alt.get("hgvs_notation") or ""
        mt = (alt.get("mutation_type") or "").lower()
        oncokb_lvl = alt.get("oncokb_level") or ""

        if not gene:
            continue

        # Is the gene in any known approved oncology programme?
        known_targets = {
            "EGFR", "ERBB2", "BRAF", "KRAS", "ALK", "MET", "RET",
            "FGFR1", "FGFR2", "FGFR3", "IDH1", "IDH2", "NTRK1", "NTRK2", "NTRK3",
            "KIT", "PDGFRA", "FLT3", "JAK2", "BRCA1", "BRCA2", "PIK3CA",
            "CDK4", "CDK6", "MTOR", "ATM",
        }
        resistance_levels = {"LEVEL_R1", "LEVEL_R2"}

        if oncokb_lvl in resistance_levels:
            lines.append(
                f"{gene} {hgvs}: this alteration is annotated as a resistance variant "
                f"({oncokb_lvl}); no approved targeted therapy is expected to be active."
            )
        elif gene in known_targets:
            lines.append(
                f"{gene} {hgvs}: the variant is outside currently labeled indications "
                f"for approved {gene} inhibitors in {cancer_type}. "
                f"FDA-approved drugs targeting {gene} cover specific hotspots or histologies "
                f"not matching this alteration; off-label use would require tumor-board review "
                f"and compendium support."
            )
        else:
            mt_desc = f" ({mt})" if mt else ""
            lines.append(
                f"{gene} {hgvs}{mt_desc}: no FDA-approved targeted therapy exists for {gene} "
                f"as of this report. The gene is not within current approved oncology drug targets."
            )

    if not lines:
        lines.append(
            f"No FDA-approved on-label or off-label therapy was identified for the reported "
            f"alterations in {cancer_type}. The variants may be outside currently labeled "
            f"indications; clinical trial enrollment or compassionate use should be considered."
        )
    return lines


def _render_sections(r: OncologistReport) -> dict:
    return {
        "executive_summary": r.executive_summary,
        "sample_quality": r.sample_quality,
        "genomic_alterations": r.genomic_alterations,
        "drug_recommendations": r.drug_recommendations,
        "experimental_candidates": r.experimental_candidates,
        "audit_trail": r.audit_trail,
        "withdrawn_warnings": r.withdrawn_warnings,
        "system_limitations": r.system_limitations,
        "tier_gap_explanation": r.tier_gap_explanation,
        "disclaimer": ONCOLOGIST_DISCLAIMER,
    }
