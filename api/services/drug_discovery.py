"""Custom drug discovery brief generator.

Used when repurposing yields no strong candidate for a patient's mutation profile.
This service does NOT manufacture drugs; it prepares a structured discovery brief
for pharma teams with:
  - target context
  - lead molecules from OpenTargets/ChEMBL
  - scaffold and fragment component library
  - practical handoff notes for medicinal chemistry
"""

from __future__ import annotations

import re
from typing import Any

from .opentargets import get_target_id, get_drugs_for_target
from .chembl import get_molecule


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _phase_rank(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    label = str(value or "").upper()
    return {
        "APPROVAL": 4,
        "PHASE4": 4,
        "PHASE3": 3,
        "PHASE2": 2,
        "PHASE1": 1,
        "EARLY_PHASE1": 1,
        "COMPLETED": 1,
    }.get(label, 0)


def _score_oral_exposure(molecule: dict[str, Any]) -> float | None:
    mw = _to_float(molecule.get("molecular_weight"))
    alogp = _to_float(molecule.get("alogp"))
    psa = _to_float(molecule.get("psa"))
    hba = _to_float(molecule.get("hba"))
    hbd = _to_float(molecule.get("hbd"))
    ro5_pass = molecule.get("ro5_pass")

    if all(v is None for v in (mw, alogp, psa, hba, hbd, ro5_pass)):
        return None

    score = 1.0
    if mw is not None:
        if mw > 500:
            score -= 0.25
        elif mw < 180:
            score -= 0.08
    if alogp is not None and not 1 <= float(alogp) <= 4.5:
        score -= 0.15
    if psa is not None and float(psa) > 140:
        score -= 0.20
    if hba is not None and float(hba) > 10:
        score -= 0.12
    if hbd is not None and float(hbd) > 5:
        score -= 0.12
    if ro5_pass is False:
        score -= 0.15

    return round(_clamp(score) * 100, 1)


def _score_toxicity_risk(molecule: dict[str, Any]) -> float | None:
    mw = _to_float(molecule.get("molecular_weight"))
    alogp = _to_float(molecule.get("alogp"))
    psa = _to_float(molecule.get("psa"))
    rtb = _to_float(molecule.get("rtb"))
    ro5_pass = molecule.get("ro5_pass")

    if all(v is None for v in (mw, alogp, psa, rtb, ro5_pass)):
        return None

    risk = 0.20
    if mw is not None and float(mw) > 550:
        risk += 0.18
    if alogp is not None and float(alogp) > 4.5:
        risk += 0.22
    if psa is not None and float(psa) < 20:
        risk += 0.12
    if rtb is not None and float(rtb) > 10:
        risk += 0.12
    if ro5_pass is False:
        risk += 0.16

    return round(_clamp(risk) * 100, 1)


def _score_synthesis_feasibility(molecule: dict[str, Any]) -> float | None:
    mw = _to_float(molecule.get("molecular_weight"))
    rtb = _to_float(molecule.get("rtb"))
    hba = _to_float(molecule.get("hba"))
    hbd = _to_float(molecule.get("hbd"))

    if all(v is None for v in (mw, rtb, hba, hbd)):
        return None

    score = 0.85
    if mw is not None and float(mw) > 520:
        score -= 0.20
    if rtb is not None and float(rtb) > 9:
        score -= 0.18
    if hba is not None and float(hba) > 9:
        score -= 0.08
    if hbd is not None and float(hbd) > 4:
        score -= 0.06

    return round(_clamp(score) * 100, 1)


def _score_design_priority(lead: dict[str, Any]) -> float:
    source_scores = [
        float(lead.get("binding_score")) if lead.get("binding_score") is not None else None,
        float(lead.get("opentargets_score")) if lead.get("opentargets_score") is not None else None,
        (float(lead.get("oral_exposure_score")) / 100) if lead.get("oral_exposure_score") is not None else None,
        (1 - float(lead.get("toxicity_risk")) / 100) if lead.get("toxicity_risk") is not None else None,
        (float(lead.get("synthesis_feasibility_score")) / 100) if lead.get("synthesis_feasibility_score") is not None else None,
    ]
    available = [score for score in source_scores if score is not None]
    if not available:
        return 0.0
    return round(sum(available) / len(available) * 100, 1)


def _weighted_mean(components: list[tuple[float | None, float]]) -> float | None:
    usable = [(score, weight) for score, weight in components if score is not None]
    if not usable:
        return None
    weight_sum = sum(weight for _score, weight in usable)
    if weight_sum <= 0:
        return None
    value = sum(score * weight for score, weight in usable) / weight_sum
    return round(_clamp(value), 4)


def _attach_lead_ensemble_scores(leads: list[dict[str, Any]]) -> None:
    """Attach transparent multi-source consensus scores to lead candidates.

    Engines combined:
      - OpenTargets target evidence
      - Docking/repurposing signal (when available)
      - Oral exposure heuristic
      - Toxicity safety margin
      - Synthesis feasibility heuristic
    """
    for lead in leads:
        opentargets = float(lead.get("opentargets_score") or 0)
        docking = float(lead.get("binding_score")) if lead.get("binding_score") is not None else None
        oral = (float(lead.get("oral_exposure_score")) / 100) if lead.get("oral_exposure_score") is not None else None
        safety_margin = (1 - float(lead.get("toxicity_risk")) / 100) if lead.get("toxicity_risk") is not None else None
        synth = (float(lead.get("synthesis_feasibility_score")) / 100) if lead.get("synthesis_feasibility_score") is not None else None

        consensus = _weighted_mean(
            [
                (opentargets, 0.30),
                (docking, 0.30),
                (oral, 0.15),
                (safety_margin, 0.15),
                (synth, 0.10),
            ]
        )

        lead["ensemble_score"] = round((consensus or 0.0) * 100, 1)
        lead["ensemble_breakdown"] = {
            "opentargets": round(opentargets * 100, 1),
            "docking_or_binding": round(docking * 100, 1) if docking is not None else None,
            "oral_exposure": round(oral * 100, 1) if oral is not None else None,
            "toxicity_safety_margin": round(safety_margin * 100, 1) if safety_margin is not None else None,
            "synthesis_feasibility": round(synth * 100, 1) if synth is not None else None,
        }


def _attach_de_novo_ensemble_scores(
    de_novo_candidates: list[dict[str, Any]],
    leads: list[dict[str, Any]],
) -> None:
    """Attach ensemble consensus score using multiple engines/signals.

    Engines combined:
      - DiffDock confidence (if available)
      - Target-fit heuristic
      - Feasibility heuristic
      - Parent lead evidence score
      - Novelty heuristic
    """
    parent_lead_score: dict[str, float] = {
        str(lead.get("drug_name")): float(lead.get("ensemble_score") or 0) / 100
        for lead in leads
        if lead.get("drug_name")
    }

    for cand in de_novo_candidates:
        diffdock = float(cand.get("docking_binding_score")) if cand.get("docking_binding_score") is not None else None
        target_fit = float(cand.get("target_fit_score") or 0) / 100
        feasibility = float(cand.get("feasibility_score") or 0) / 100
        novelty = float(cand.get("novelty_score") or 0) / 100
        parent_signal = parent_lead_score.get(str(cand.get("parent_lead")))

        consensus = _weighted_mean(
            [
                (diffdock, 0.40),
                (target_fit, 0.25),
                (feasibility, 0.15),
                (parent_signal, 0.10),
                (novelty, 0.10),
            ]
        )

        cand["ensemble_score"] = round((consensus or 0.0) * 100, 1)
        cand["ensemble_breakdown"] = {
            "diffdock": round(diffdock * 100, 1) if diffdock is not None else None,
            "target_fit": round(target_fit * 100, 1),
            "feasibility": round(feasibility * 100, 1),
            "parent_lead_signal": round(parent_signal * 100, 1) if parent_signal is not None else None,
            "novelty": round(novelty * 100, 1),
        }


def _fallback_fragments(smiles: str) -> list[str]:
    """Lightweight SMILES token fallback when RDKit is unavailable."""
    tokens = [t for t in re.split(r"[.=()\[\]#-]", smiles) if t]
    uniq: list[str] = []
    for tok in tokens:
        if tok not in uniq:
            uniq.append(tok)
    return uniq[:24]


def _extract_components(smiles_list: list[str]) -> dict[str, list[str]]:
    """Extract scaffold and fragment components from candidate molecules."""
    scaffolds: set[str] = set()
    fragments: set[str] = set()

    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        from rdkit.Chem import BRICS

        for smiles in smiles_list:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue

            scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
            if scaffold:
                scaffolds.add(scaffold)

            for frag in BRICS.BRICSDecompose(mol):
                if frag:
                    fragments.add(frag)
    except Exception:
        for smiles in smiles_list:
            for frag in _fallback_fragments(smiles):
                fragments.add(frag)

    return {
        "scaffolds": sorted(scaffolds)[:30],
        "fragments": sorted(fragments)[:40],
    }


def _mutation_complexity_modifier(mutation_hgvs: list[str]) -> float:
    if not mutation_hgvs:
        return 0.0

    hotspot_tokens = ("G12", "L858", "V600", "T790", "R175", "Y220", "E545", "H1047")
    hotspot_hits = sum(1 for m in mutation_hgvs if any(tok in m for tok in hotspot_tokens))
    breadth_bonus = min(len(mutation_hgvs), 6) * 0.03
    hotspot_bonus = min(hotspot_hits, 4) * 0.05
    return _clamp(breadth_bonus + hotspot_bonus, 0.0, 0.25)


def _compose_de_novo_smiles(
    lead_smiles: str | None,
    scaffold: str | None,
    fragment: str | None,
) -> str | None:
    parts = [p for p in (lead_smiles, scaffold, fragment) if p]
    if not parts:
        return None
    # This is a heuristic assembly token for computational triage, not a synthesis-ready route.
    return ".".join(parts)


def _generate_de_novo_candidates(
    target_gene: str,
    mutation_hgvs: list[str],
    leads: list[dict[str, Any]],
    components: dict[str, list[str]],
    max_candidates: int = 8,
) -> list[dict[str, Any]]:
    if not leads:
        return []

    scaffolds = components.get("scaffolds") or []
    fragments = components.get("fragments") or []
    mutation_modifier = _mutation_complexity_modifier(mutation_hgvs)

    ranked_leads = sorted(
        leads,
        key=lambda lead: float(lead.get("design_priority_score") or 0),
        reverse=True,
    )

    de_novo: list[dict[str, Any]] = []
    for idx in range(max_candidates):
        lead = ranked_leads[idx % len(ranked_leads)]
        scaffold = scaffolds[idx % len(scaffolds)] if scaffolds else None
        fragment = fragments[(idx * 2) % len(fragments)] if fragments else None

        base_priority = float(lead.get("design_priority_score") or 0) / 100
        base_binding = float(lead.get("binding_score") or 0)
        oral = float(lead.get("oral_exposure_score") or 65) / 100
        tox = 1 - (float(lead.get("toxicity_risk") or 35) / 100)
        synth = float(lead.get("synthesis_feasibility_score") or 70) / 100

        target_fit_score = _clamp(base_priority * 0.55 + base_binding * 0.20 + mutation_modifier)
        novelty_score = _clamp(0.42 + (idx * 0.07) + (0.06 if fragment else 0.0))
        feasibility_score = _clamp(synth * 0.6 + oral * 0.25 + tox * 0.15)
        overall_score = _clamp(target_fit_score * 0.5 + novelty_score * 0.2 + feasibility_score * 0.3)

        de_novo.append(
            {
                "candidate_id": f"DNV-{target_gene}-{idx + 1:02d}",
                "parent_lead": lead.get("drug_name"),
                "design_strategy": "Scaffold hopping + fragment recombination",
                "proposed_smiles": _compose_de_novo_smiles(lead.get("smiles"), scaffold, fragment),
                "selected_scaffold": scaffold,
                "selected_fragment": fragment,
                "target_fit_score": round(target_fit_score * 100, 1),
                "novelty_score": round(novelty_score * 100, 1),
                "feasibility_score": round(feasibility_score * 100, 1),
                "overall_score": round(overall_score * 100, 1),
                "evidence_sources": sorted(set(lead.get("evidence_sources") or [])),
                "matched_terms": lead.get("matched_terms") or [],
                "disclaimer": (
                    "Computational design proposal for medicinal-chemistry triage only; "
                    "requires synthesis and wet-lab validation."
                ),
            }
        )

    return sorted(de_novo, key=lambda c: c["overall_score"], reverse=True)


def _estimate_precursor_count(smiles: str | None) -> int:
    if not smiles:
        return 0
    # Dot-separated fragments approximate independent precursor count.
    return max(1, len([p for p in smiles.split(".") if p]))


def _build_computational_synthesis_plan(
    target_gene: str,
    de_novo_candidates: list[dict[str, Any]],
    leads: list[dict[str, Any]],
) -> dict[str, Any]:
    top_candidates = de_novo_candidates[:3]
    if not top_candidates:
        return {
            "mode": "computational_only",
            "status": "insufficient_candidates",
            "summary": "No high-confidence de novo candidates are available for route planning.",
            "selected_candidates": [],
            "execution_stages": [],
            "constraints": [
                "No synthesis recommendation can be made without candidate molecules.",
            ],
            "disclaimer": (
                "This is an in-silico planning layer and does not represent physical synthesis. "
                "Wet-lab work and licensed chemistry review are required."
            ),
        }

    selected = []
    for cand in top_candidates:
        smiles = cand.get("proposed_smiles")
        feasibility = float(cand.get("feasibility_score") or 0)
        overall = float(cand.get("overall_score") or 0)
        precursor_count = _estimate_precursor_count(smiles)
        route_confidence = round(_clamp((feasibility / 100) * 0.7 + (overall / 100) * 0.3) * 100, 1)

        selected.append(
            {
                "candidate_id": cand.get("candidate_id"),
                "parent_lead": cand.get("parent_lead"),
                "proposed_smiles": smiles,
                "precursor_count_estimate": precursor_count,
                "route_confidence_score": route_confidence,
                "route_outline": [
                    "Retrosynthetic split around highest-complexity scaffold bonds.",
                    "Prioritize commercially available fragments/analogs for assembly.",
                    "Run protecting-group and regioselectivity checks in silico.",
                    "Generate 2-3 alternative routes and rank by step count + confidence.",
                ],
            }
        )

    avg_synth = round(
        sum(float(c.get("synthesis_feasibility_score") or 0) for c in leads[:5]) / max(1, len(leads[:5])),
        1,
    )

    return {
        "mode": "computational_synthesis_planning",
        "status": "ready_for_medicinal_chemistry_review",
        "summary": (
            f"Top {len(selected)} candidates for {target_gene} include route hypotheses and confidence scoring "
            "for medicinal-chemistry triage."
        ),
        "selected_candidates": selected,
        "execution_stages": [
            {
                "stage": "retrosynthesis_enumeration",
                "duration": "5-15 min",
                "deliverable": "Alternative route trees with precursor lists",
            },
            {
                "stage": "route_ranking",
                "duration": "2-5 min",
                "deliverable": "Ranked routes by confidence and synthetic complexity",
            },
            {
                "stage": "handoff_package",
                "duration": "<1 min",
                "deliverable": "Chemist-ready package with top candidate route notes",
            },
        ],
        "constraints": [
            "In-silico route confidence is heuristic and not a guaranteed laboratory outcome.",
            "Final route validation requires chemist review, reagent checks, and safety constraints.",
        ],
        "synthesis_readiness_score": avg_synth,
        "disclaimer": (
            "Computational synthesis planning only. No physical synthesis or clinical suitability is implied."
        ),
    }


def _derive_live_evidence_sources(
    drug: dict[str, Any],
    molecule: dict[str, Any],
    repurpose: dict[str, Any],
) -> list[str]:
    evidence_sources = list(repurpose.get("evidence_sources") or [])

    if drug.get("drug_name"):
        evidence_sources.append("OpenTargets clinical candidates")
    if drug.get("disease_names"):
        evidence_sources.append("OpenTargets disease associations")
    if drug.get("mechanism") or drug.get("action_type"):
        evidence_sources.append("OpenTargets mechanism of action")
    if molecule:
        evidence_sources.append("ChEMBL molecular properties")

    return sorted(dict.fromkeys(evidence_sources))


def _derive_live_matched_terms(
    drug: dict[str, Any],
    repurpose: dict[str, Any],
    cancer_terms: set[str],
) -> list[str]:
    matched_terms = list(repurpose.get("matched_terms") or [])

    for disease_name in drug.get("disease_names") or []:
        lowered = disease_name.lower()
        if any(term in lowered for term in cancer_terms):
            matched_terms.append(disease_name)

    mechanism = drug.get("mechanism")
    if mechanism:
        matched_terms.append(mechanism)

    action_type = drug.get("action_type")
    if action_type:
        matched_terms.append(action_type)

    return sorted(dict.fromkeys(term for term in matched_terms if term))


async def build_custom_discovery_brief(
    target_gene: str,
    cancer_type: str,
    mutation_hgvs: list[str],
    repurposing_candidates: list[dict[str, Any]] | None = None,
    pre_folded_structure_path: str | None = None,
    max_leads: int = 12,
) -> dict[str, Any]:
    """Build a pharma-ready custom discovery brief for a specific target.

    The brief is generated from public target/drug knowledge and enriched with
    molecular properties/components for medicinal chemistry teams.
    """
    if not target_gene:
        raise ValueError("target_gene is required to generate a discovery brief")

    integration_issues: list[str] = []
    ensg_id = await get_target_id(target_gene)
    raw_drugs = await get_drugs_for_target(ensg_id, max_drugs=40) if ensg_id else []
    repurposing_by_chembl = {
        candidate.get("chembl_id"): candidate
        for candidate in (repurposing_candidates or [])
        if candidate.get("chembl_id")
    }

    cancer_terms = {term.strip().lower() for term in re.split(r"[,/]|\bwith\b", cancer_type) if term.strip()}
    cancer_matched_drugs = [
        drug for drug in raw_drugs
        if any(
            any(term in disease_name.lower() for term in cancer_terms)
            for disease_name in (drug.get("disease_names") or [])
        )
    ]
    candidate_pool = cancer_matched_drugs or raw_drugs
    if raw_drugs and not cancer_matched_drugs:
        integration_issues.append(
            f"OpenTargets returned target drugs for {target_gene}, but none explicitly matched the cancer context '{cancer_type}'."
        )

    ranked = sorted(
        candidate_pool,
        key=lambda d: (float(d.get("opentargets_score") or 0), _phase_rank(d.get("max_phase"))),
        reverse=True,
    )

    if not ensg_id:
        integration_issues.append(f"OpenTargets target lookup returned no Ensembl ID for {target_gene}.")
    elif not raw_drugs:
        integration_issues.append(f"OpenTargets returned no clinical candidate drugs for {target_gene}.")

    leads: list[dict[str, Any]] = []
    smiles_bank: list[str] = []

    for d in ranked[:max_leads]:
        chembl_id = d.get("chembl_id")
        molecule = await get_molecule(chembl_id) if chembl_id else None
        repurpose = repurposing_by_chembl.get(chembl_id, {})
        smiles = molecule.get("smiles") if molecule else None
        if smiles:
            smiles_bank.append(smiles)

        oral_exposure_score = _score_oral_exposure(molecule or {})
        toxicity_risk = _score_toxicity_risk(molecule or {})
        synthesis_feasibility_score = _score_synthesis_feasibility(molecule or {})
        evidence_sources = _derive_live_evidence_sources(d, molecule or {}, repurpose)
        matched_terms = _derive_live_matched_terms(d, repurpose, cancer_terms)

        lead = {
            "drug_name": d.get("drug_name"),
            "chembl_id": chembl_id,
            "mechanism": d.get("mechanism"),
            "action_type": d.get("action_type"),
            "max_phase": (molecule or {}).get("max_phase", d.get("max_phase")),
            "is_approved": (molecule or {}).get("is_approved", d.get("is_approved", False)),
            "opentargets_score": float(d.get("opentargets_score") or 0),
            "binding_score": repurpose.get("binding_score"),
            "rank_score": repurpose.get("rank_score"),
            "smiles": smiles,
            "ro5_pass": (molecule or {}).get("ro5_pass"),
            "oral_exposure_score": oral_exposure_score,
            "toxicity_risk": toxicity_risk,
            "synthesis_feasibility_score": synthesis_feasibility_score,
            "molecular_weight": (molecule or {}).get("molecular_weight"),
            "alogp": (molecule or {}).get("alogp"),
            "psa": (molecule or {}).get("psa"),
            "evidence_sources": evidence_sources,
            "matched_terms": matched_terms,
        }
        lead["design_priority_score"] = _score_design_priority(lead)

        leads.append(lead)

    if raw_drugs and not leads:
        integration_issues.append(
            "ChEMBL property enrichment did not yield any molecule records for the OpenTargets clinical candidates."
        )

    components = _extract_components(smiles_bank)
    _attach_lead_ensemble_scores(leads)
    de_novo_candidates = _generate_de_novo_candidates(
        target_gene=target_gene,
        mutation_hgvs=mutation_hgvs,
        leads=leads,
        components=components,
    )

    docking_runs = 0
    uniprot_id = _gene_to_uniprot(target_gene)
    if uniprot_id and de_novo_candidates:
        try:
            from ai.diffdock.score import score_binding
        except ModuleNotFoundError:
            score_binding = None
            integration_issues.append("DiffDock module is not installed in this environment; docking scores are unavailable.")

        if score_binding is not None:
            for cand in de_novo_candidates[:6]:
                smiles = cand.get("proposed_smiles")
                if not smiles:
                    continue
                docking_runs += 1
                dock_score = score_binding(
                    uniprot_id=uniprot_id,
                    smiles=smiles,
                    chembl_id=cand.get("candidate_id") or f"DNV-{target_gene}",
                    pre_folded_structure=pre_folded_structure_path,
                )
                cand["docking_binding_score"] = dock_score
                if dock_score is not None:
                    # Re-weight overall using target fit + measured docking confidence.
                    fit = float(cand.get("target_fit_score") or 0) / 100
                    novelty = float(cand.get("novelty_score") or 0) / 100
                    feas = float(cand.get("feasibility_score") or 0) / 100
                    overall = _clamp(fit * 0.45 + float(dock_score) * 0.35 + novelty * 0.05 + feas * 0.15)
                    cand["overall_score"] = round(overall * 100, 1)

    _attach_de_novo_ensemble_scores(de_novo_candidates, leads)
    de_novo_candidates = sorted(
        de_novo_candidates,
        key=lambda c: (c.get("ensemble_score", 0), c.get("overall_score", 0)),
        reverse=True,
    )
    computational_synthesis_plan = _build_computational_synthesis_plan(
        target_gene=target_gene,
        de_novo_candidates=de_novo_candidates,
        leads=leads,
    )

    reason = "repurposing_insufficient"
    if repurposing_candidates:
        top_score = max((float(c.get("rank_score") or 0) for c in repurposing_candidates), default=0)
        if top_score < 0.5:
            reason = "repurposing_weak_rank_score"
        else:
            reason = "custom_optimization_requested"

    live_data_used = bool(leads)

    return {
        "mode": "custom_discovery",
        "reason": reason,
        "target_gene": target_gene,
        "cancer_type": cancer_type,
        "mutation_profile": mutation_hgvs[:12],
        "ensembl_target_id": ensg_id,
        "lead_candidates": leads,
        "de_novo_candidates": de_novo_candidates,
        "component_library": components,
        "design_mode": "hybrid_repurpose_plus_denovo",
        "live_data_used": live_data_used,
        "integration_issues": integration_issues,
        "scoring_engines_used": [
            "OpenTargets evidence",
            "ChEMBL molecular properties",
            "RDKit descriptor/scaffold extraction",
            "DiffDock docking (optional)",
            "OpenOncology ensemble consensus scorer",
        ],
        "docking_summary": {
            "runs_attempted": docking_runs,
            "used_mutation_specific_structure": bool(pre_folded_structure_path),
            "structure_path": pre_folded_structure_path,
        },
        "computational_synthesis_plan": computational_synthesis_plan,
        "design_rationale": (
            "Candidates are prioritized using public target evidence, available binding scores from the "
            "repurposing pipeline when present, molecule-level heuristics for oral exposure, toxicity risk, "
            "and synthesis feasibility, plus de novo scaffold/fragment recombination proposals. "
            "These are computational triage scores, not wet-lab measurements."
        ),
        "design_constraints": {
            "prioritize_target_selectivity": True,
            "prefer_oral_if_possible": True,
            "respect_lipinski_ro5": True,
        },
        "handoff_note": (
            "This brief proposes target-matched starting points and molecular components. "
            "Final synthesis feasibility, ADMET validation, and clinical decisions remain with licensed pharma teams."
        ),
    }


def _gene_to_uniprot(gene: str) -> str | None:
    mapping = {
        "TP53": "P04637", "KRAS": "P01116", "BRAF": "P15056",
        "EGFR": "P00533", "PIK3CA": "P42336", "PTEN": "P60484",
        "ERBB2": "P04626", "ALK": "Q9UM73", "RET": "P07949",
        "MET": "P08581", "NRAS": "P01111", "HRAS": "P01112",
    }
    return mapping.get(gene.upper())
