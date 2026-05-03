#!/usr/bin/env python3
"""End-to-end demo pipeline — OpenOncology

Demonstrates a complete analysis run starting from a real VCF + biopsy text
file (sample3_dna.vcf + sample3_biopsy.txt) and producing:

  1. Sample QC report (FFPE detection, tumour purity, coverage summary)
  2. Variant annotation (gene, HGVS, AlphaMissense pathogenicity)
  3. Drug repurposing candidates with ranked scores + uncertainty intervals
  4. Toxicity / ADME / safety profile for top candidates
  5. Benchmark score against OncoKB gold standards
  6. LLM plain-language summary (template fallback when OPENAI_API_KEY absent)

This script requires no database, no MinIO, and no Celery — it runs entirely
in-process for demo and validation purposes.

Usage:
    python scripts/run_demo.py [--vcf PATH] [--biopsy PATH] [--cancer-type STR]

Outputs:
    - Console report (always)
    - demo_output.json (structured JSON in cwd)

Example:
    python scripts/run_demo.py \\
        --vcf sample3_dna.vcf \\
        --biopsy sample3_biopsy.txt \\
        --cancer-type "Non-Small Cell Lung Cancer"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import time as _time

# ── Setup paths ───────────────────────────────────────────────────────────────
# Allow imports from api/ and root ai/ when run from any working directory.
# NOTE: repo_root/ai/ and api/ai/ have the same package name; repo_root goes
# first so ai.alphamissense resolves to the root ai/ package.
# api/ai/ranking.py is loaded explicitly via importlib to avoid collision.
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "api"))
sys.path.insert(0, str(_repo_root))


def _import_rank_candidates():
    """Load rank_candidates from api/ai/ranking.py without namespace collision.

    Registers the module in sys.modules before exec so that @dataclass
    annotations resolve correctly (dataclasses.py uses sys.modules[cls.__module__]).
    """
    import importlib.util
    _MOD_NAME = "_api_ai_ranking"
    if _MOD_NAME in sys.modules:
        return sys.modules[_MOD_NAME].rank_candidates
    spec = importlib.util.spec_from_file_location(
        _MOD_NAME, _repo_root / "api" / "ai" / "ranking.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod           # register BEFORE exec — required for @dataclass
    spec.loader.exec_module(mod)           # type: ignore[union-attr]
    return mod.rank_candidates

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("demo")


# ── Step 1: Sample QC ─────────────────────────────────────────────────────────

def step_sample_qc(vcf_path: Path) -> dict:
    from services.sample_qc import run_sample_qc
    print(f"\n{'='*60}")
    print("STEP 1 — Sample QC")
    print(f"{'='*60}")
    report = run_sample_qc(vcf_path)

    print(f"  VCF:              {vcf_path.name}")
    print(f"  Total variants:   {report.total_variants}")
    print(f"  PASS variants:    {report.pass_variants}")
    print(f"  Verdict:          {report.verdict}")
    print(f"  FFPE score:       {report.ffpe.ffpe_score} ({report.ffpe.confidence})")
    print(f"  Tumour purity:    {report.tumour_purity.purity_pct}%  "
          f"({report.tumour_purity.confidence})")
    if report.tumour_purity.notes:
        print(f"  Purity note:      {report.tumour_purity.notes}")
    if report.verdict_reasons:
        for r in report.verdict_reasons:
            print(f"  ⚠ {r}")

    return {
        "verdict": report.verdict,
        "ffpe_score": report.ffpe.ffpe_score,
        "ffpe_flagged": report.ffpe.is_flagged,
        "tumour_purity_pct": report.tumour_purity.purity_pct,
        "total_variants": report.total_variants,
        "coverage_adequacy": report.coverage.coverage_adequacy,
        "recommendations": report.actionable_recommendations,
    }


# ── Step 2: Variant parsing & AlphaMissense ───────────────────────────────────

def step_variant_annotation(vcf_path: Path) -> list[dict]:
    from services.sample_qc import parse_vcf

    print(f"\n{'='*60}")
    print("STEP 2 — Variant Annotation")
    print(f"{'='*60}")

    records = parse_vcf(vcf_path)

    # Extract gene/HGVS from INFO field
    annotated: list[dict] = []
    for rec in records:
        info_map: dict[str, str] = {}
        for item in rec.raw_line.split("\t")[7].split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                info_map[k.strip()] = v.strip()

        gene = info_map.get("GENE", "UNKNOWN")
        hgvs_c = info_map.get("HGVS_C")
        hgvs_p = info_map.get("HGVS_P")
        so_term = info_map.get("SO", "unknown")

        # AlphaMissense lookup (requires scores.db)
        am_score: float | None = None
        am_label: str = "unavailable"
        try:
            from ai.alphamissense.classify import classifier
            # Map gene → UniProt inline
            from workers.ai_worker import _gene_to_uniprot, _hgvs_to_short
            uniprot = _gene_to_uniprot(gene)
            if uniprot and hgvs_p:
                short = _hgvs_to_short(hgvs_p)
                if short:
                    am_score = classifier.score(uniprot, short)
                    if am_score is not None:
                        am_label = classifier.classify(am_score) or "uncertain"
        except Exception as e:
            logger.debug("AlphaMissense unavailable: %s", e)

        var = {
            "gene": gene,
            "chrom": rec.chrom,
            "pos": rec.pos,
            "ref": rec.ref,
            "alt": rec.alt,
            "hgvs_c": hgvs_c,
            "hgvs_p": hgvs_p,
            "so_term": so_term,
            "qual": rec.qual,
            "filter": rec.filter_status,
            "vaf": rec.vaf,
            "depth": rec.depth,
            "alphamissense_score": am_score,
            "alphamissense_label": am_label,
        }
        annotated.append(var)

        am_display = f"{am_score:.3f} ({am_label})" if am_score is not None else am_label
        print(f"  {gene:10s}  {hgvs_c or '?':20s}  VAF={rec.vaf or '?'}  "
              f"AlphaMissense={am_display}")

    return annotated


# ── Step 3: Repurposing candidates ────────────────────────────────────────────

async def step_repurposing(variants: list[dict], cancer_type: str) -> list[dict]:
    print(f"\n{'='*60}")
    print("STEP 3 — Drug Repurposing + OncoKB Annotation")
    print(f"{'='*60}")

    # Select most clinically interesting mutation (EGFR > KRAS > TP53 > other)
    priority = {"EGFR": 1, "ALK": 1, "RET": 1, "BRAF": 2, "KRAS": 3, "TP53": 4}
    target_var = min(variants, key=lambda v: priority.get(v["gene"], 99))
    gene = target_var["gene"]
    # Prefer the protein change for OncoKB lookup
    hgvs_p = target_var.get("hgvs_p") or target_var.get("hgvs_c") or "Unknown"
    protein_change = hgvs_p.replace("p.", "") if hgvs_p.startswith("p.") else hgvs_p
    print(f"  Target gene:      {gene}")
    print(f"  Protein change:   {protein_change}")

    candidates: list[dict] = []
    try:
        from services.opentargets import get_target_id, get_drugs_for_target
        rank_candidates = _import_rank_candidates()

        ensg_id = await get_target_id(gene)
        print(f"  Ensembl ID:       {ensg_id or 'not found'}")

        if ensg_id:
            drugs = await get_drugs_for_target(ensg_id)
            print(f"  OpenTargets hits: {len(drugs)}")

            for drug in drugs[:20]:
                drug.setdefault("alphamissense_score", target_var.get("alphamissense_score"))
                drug.setdefault("oncokb_level", None)
                drug.setdefault("binding_score", None)

            # ── OncoKB evidence annotation (table + optional live API) ────────
            try:
                from services.oncokb_evidence import annotate_candidates_with_oncokb
                drugs = await annotate_candidates_with_oncokb(
                    drugs[:20], gene=gene,
                    protein_change=protein_change, cancer_type=cancer_type
                )
                n_annotated = sum(1 for d in drugs if d.get("oncokb_level"))
                print(f"  OncoKB annotated: {n_annotated}/{len(drugs)} drugs")
            except Exception as exc:
                logger.warning("OncoKB annotation failed: %s", exc)

            # Rank the full annotated list (may include injected OncoKB drugs)
            candidates = rank_candidates(drugs)
        else:
            print("  No OpenTargets data — demonstrating with stub candidates.")
            candidates = await _stub_candidates_async(gene, protein_change, cancer_type)

    except Exception as exc:
        logger.warning("OpenTargets query failed (%s) — using stub candidates.", exc)
        candidates = await _stub_candidates_async(gene, protein_change, cancer_type)

    print(f"\n  {'Rank':<5}{'Drug':<26}{'Score':<8}{'OncoKB':<10}{'CI':<22}{'Conf':<8}")
    print(f"  {'-'*4} {'-'*25} {'-'*7} {'-'*9} {'-'*21} {'-'*7}")
    for i, c in enumerate(candidates[:10], 1):
        ci = f"[{c.get('rank_score_ci_low', 0):.3f}–{c.get('rank_score_ci_high', 0):.3f}]"
        level = c.get("oncokb_level") or "—"
        # Flag resistance in display
        is_resistant = level and "R" in level
        flag = " [RESISTANT]" if is_resistant else ""
        print(f"  {i:<5}{c.get('drug_name', '?'):<26}"
              f"{c.get('rank_score', 0):<8.3f}"
              f"{level:<10}{ci:<22}{c.get('confidence_level', '?'):<8}{flag}")

    return candidates


async def _stub_candidates_async(
    gene: str, protein_change: str, cancer_type: str
) -> list[dict]:
    """Return stub candidates when live APIs are unavailable (demo mode)."""
    rank_candidates = _import_rank_candidates()
    stubs = {
        "EGFR": [
            {"drug_name": "Osimertinib",  "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.92, "oncokb_level": "LEVEL_1", "binding_score": 0.88},
            {"drug_name": "Erlotinib",    "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.85, "oncokb_level": "LEVEL_1", "binding_score": 0.80},
            {"drug_name": "Gefitinib",    "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.82, "oncokb_level": "LEVEL_1", "binding_score": 0.78},
            {"drug_name": "Afatinib",     "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.80, "oncokb_level": "LEVEL_2", "binding_score": 0.74},
        ],
        "KRAS": [
            {"drug_name": "Sotorasib",    "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.90, "oncokb_level": "LEVEL_1", "binding_score": 0.85},
            {"drug_name": "Adagrasib",    "is_approved": True,  "max_phase": 4,
             "opentargets_score": 0.88, "oncokb_level": "LEVEL_1", "binding_score": 0.82},
        ],
        "TP53": [
            {"drug_name": "APR-246",      "is_approved": False, "max_phase": 3,
             "opentargets_score": 0.55, "oncokb_level": "LEVEL_3A", "binding_score": 0.50},
        ],
    }
    raw = stubs.get(gene, [
        {"drug_name": "Placeholder", "is_approved": False, "max_phase": 1,
         "opentargets_score": 0.20, "oncokb_level": None, "binding_score": None},
    ])
    return rank_candidates(raw)


# ── Step 4: Toxicity / ADME for top candidates ────────────────────────────────

async def step_safety_profile(candidates: list[dict]) -> list[dict]:
    print(f"\n{'='*60}")
    print("STEP 4 — Safety & ADME Profile (Top 3 Candidates)")
    print(f"{'='*60}")

    enriched: list[dict] = []
    for cand in candidates[:3]:
        drug_name = cand.get("drug_name", "?")

        # ── 1. Fetch real SMILES + properties from ChEMBL ────────────────────
        mol_data: dict = {}
        try:
            from services.chembl import get_smiles_for_drug_name
            hit = await get_smiles_for_drug_name(drug_name)
            if hit:
                mol_data = hit
                if hit.get("is_biologic"):
                    print(f"\n  ── {drug_name} (biologic/mAb — structural SMILES N/A) ──")
                    enriched.append(cand)
                    continue
                if hit.get("smiles"):
                    print(f"\n  ── {drug_name} ──  [SMILES fetched, ChEMBL={hit.get('chembl_id', '?')}]")
                else:
                    print(f"\n  ── {drug_name} ──  [no SMILES, using physicochemical estimates]")
        except Exception as exc:
            logger.debug("ChEMBL SMILES fetch failed for %s: %s", drug_name, exc)

        # ── 2. Fall back to known physicochemical props if needed ─────────────
        if not mol_data.get("molecular_weight"):
            mol_data.setdefault("molecular_weight", cand.get("molecular_weight", 480.0))
            mol_data.setdefault("alogp", cand.get("alogp", 3.2))
            mol_data.setdefault("psa", cand.get("psa", 72.0))
            mol_data.setdefault("hba", cand.get("hba", 6))
            mol_data.setdefault("hbd", cand.get("hbd", 2))
            mol_data.setdefault("rtb", cand.get("rtb", 5))
            mol_data.setdefault("ro5_pass", True)

        try:
            from services.toxicity import assess_off_target_liability
            from services.adme import compute_adme_profile

            tox = assess_off_target_liability(mol_data)
            adme = compute_adme_profile(mol_data)

            if not mol_data.get("smiles"):
                print(f"\n  ── {drug_name} ──")
            print(f"    Off-target risk:   {tox.overall_risk_level} | Gate: {'PASS' if tox.safety_gate_pass else 'FAIL'}")
            print(f"    hERG flagged:      {tox.herg.flagged if tox.herg else 'N/A'}  "
                  f"({'HIGH' if tox.herg and tox.herg.confidence == 'HIGH' else 'ok'})")
            print(f"    Ames flagged:      {tox.ames.flagged if tox.ames else 'N/A'}")
            print(f"    CYP DDI risk:      {tox.cyp_inhibition.ddI_risk if tox.cyp_inhibition else 'N/A'}")
            if adme.synthetic_accessibility:
                print(f"    SA score:          {adme.synthetic_accessibility.sa_score:.1f} "
                      f"({adme.synthetic_accessibility.sa_class})")
            if adme.oral_bioavailability:
                print(f"    Oral F% (est):     {adme.oral_bioavailability.f_estimate_pct}% "
                      f"BCS class {adme.oral_bioavailability.bcs_class}")
            if adme.metabolic_stability:
                print(f"    t½ (est):          {adme.metabolic_stability.predicted_half_life_min} min "
                      f"({adme.metabolic_stability.clearance_class} clearance)")
            print(f"    Developability:    {adme.overall_developability}")

            enriched.append({
                **cand,
                "smiles": mol_data.get("smiles"),
                "chembl_id": mol_data.get("chembl_id"),
                "off_target_risk_level": tox.overall_risk_level,
                "safety_gate_pass": tox.safety_gate_pass,
                "safety_summary": tox.summary,
                "adme_developability": adme.overall_developability,
            })
        except ImportError as e:
            logger.warning("Toxicity/ADME services unavailable: %s", e)
            enriched.append(cand)

    return enriched


# ── Step 5: Benchmark ─────────────────────────────────────────────────────────

async def step_benchmark() -> dict:
    print(f"\n{'='*60}")
    print("STEP 5 — Benchmark vs. OncoKB Gold Standards")
    print(f"{'='*60}")
    try:
        from services.benchmark import run_benchmark_suite, GOLD_STANDARD_CASES
        # Run only the 3 NSCLC cases for speed in demo mode
        nsclc_cases = [c for c in GOLD_STANDARD_CASES if "Lung" in c["cancer_type"]]
        report = await run_benchmark_suite(nsclc_cases)
        print(f"  Cases evaluated:  {report.n_successful}/{report.n_cases}")
        print(f"  Precision@1:      {report.mean_precision_at_1:.3f}")
        print(f"  Precision@3:      {report.mean_precision_at_3:.3f}")
        print(f"  Hit@3:            {report.hit_rate_at_3:.1%}")
        print(f"  Mean MRR:         {report.mean_mrr:.3f}")
        print(f"  Quality gate:     {'PASS' if report.passes_quality_threshold() else 'NEEDS IMPROVEMENT'}")
        for cr in report.case_results:
            status = "✓" if cr.hit_at_3 else "✗"
            top_ranked = cr.ranked_drugs[0] if cr.ranked_drugs else "none"
            print(f"    {status} {cr.case_id}: top={top_ranked}, P@3={cr.precision_at_3:.2f}")

        return {
            "n_cases": report.n_successful,
            "precision_at_1": report.mean_precision_at_1,
            "precision_at_3": report.mean_precision_at_3,
            "hit_rate_at_3": report.hit_rate_at_3,
            "mrr": report.mean_mrr,
            "passes_quality_threshold": report.passes_quality_threshold(),
        }
    except Exception as exc:
        logger.warning("Benchmark skipped: %s", exc)
        print(f"  Benchmark skipped ({exc})")
        return {"error": str(exc)}


# ── Step 6: LLM summary ───────────────────────────────────────────────────────

async def step_llm_summary(
    variants: list[dict],
    candidates: list[dict],
    cancer_type: str,
) -> str:
    print(f"\n{'='*60}")
    print("STEP 6 — Plain-Language Summary")
    print(f"{'='*60}")
    try:
        from services.llm_explainer import generate_plain_language_summary
        gene = variants[0]["gene"] if variants else "UNKNOWN"
        top_drug = candidates[0].get("drug_name") if candidates else None
        summary = await generate_plain_language_summary(
            gene=gene,
            cancer_type=cancer_type,
            has_target=bool(candidates),
            mutations_summary=variants[:3],
            top_drug=top_drug,
            cosmic_count=0,
        )
        lines = summary.split("\n")[:6]  # show first 6 lines
        for line in lines:
            print(f"  {line}")
        return summary
    except Exception as exc:
        logger.warning("LLM summary failed: %s", exc)
        fallback = (
            f"Analysis identified {len(variants)} variant(s) in "
            f"{', '.join(set(v['gene'] for v in variants))}. "
            f"Top repurposing candidate: {candidates[0].get('drug_name') if candidates else 'none'}. "
            f"Cancer type: {cancer_type}."
        )
        print(f"  {fallback}")
        return fallback


# ── Main ──────────────────────────────────────────────────────────────────────

async def _main(vcf_path: Path, biopsy_path: Path, cancer_type: str) -> None:
    wall_start = _time.perf_counter()

    print("\n" + "=" * 60)
    print("  OpenOncology — End-to-End Demo Pipeline")
    print("=" * 60)
    print(f"  VCF:         {vcf_path}")
    print(f"  Biopsy:      {biopsy_path}")
    print(f"  Cancer type: {cancer_type}")

    # Read biopsy
    biopsy_text = biopsy_path.read_text(errors="replace") if biopsy_path.exists() else ""
    print(f"  Biopsy size: {len(biopsy_text)} chars")

    output: dict = {
        "vcf": str(vcf_path),
        "biopsy": str(biopsy_path),
        "cancer_type": cancer_type,
        "timings_sec": {},
    }

    # Run pipeline steps with per-step timing
    def _timed(label: str, fn, *a, **kw):
        t0 = _time.perf_counter()
        result = fn(*a, **kw)
        output["timings_sec"][label] = round(_time.perf_counter() - t0, 3)
        return result

    async def _timed_async(label: str, coro):
        t0 = _time.perf_counter()
        result = await coro
        output["timings_sec"][label] = round(_time.perf_counter() - t0, 3)
        return result

    output["sample_qc"] = _timed("sample_qc", step_sample_qc, vcf_path)
    output["variants"] = _timed("variant_annotation", step_variant_annotation, vcf_path)
    output["repurposing"] = await _timed_async(
        "repurposing", step_repurposing(output["variants"], cancer_type)
    )
    output["safety"] = await _timed_async("safety", step_safety_profile(output["repurposing"]))
    output["benchmark"] = await _timed_async("benchmark", step_benchmark())
    output["summary"] = await _timed_async(
        "llm_summary", step_llm_summary(output["variants"], output["repurposing"], cancer_type)
    )

    wall_elapsed = round(_time.perf_counter() - wall_start, 2)
    output["timings_sec"]["total_wall"] = wall_elapsed

    # Serialise to JSON
    out_path = Path("demo_output.json")
    with open(out_path, "w") as fh:
        json.dump(output, fh, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  Demo complete in {wall_elapsed}s (offline/stub mode)")
    step_times = ", ".join(f"{k}={v}s" for k, v in output["timings_sec"].items() if k != "total_wall")
    print(f"  Step times:    {step_times}")
    print(f"  Output:        {out_path.resolve()}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenOncology end-to-end demo")
    parser.add_argument(
        "--vcf",
        default=str(_repo_root / "sample3_dna.vcf"),
        help="Path to input VCF file",
    )
    parser.add_argument(
        "--biopsy",
        default=str(_repo_root / "sample3_biopsy.txt"),
        help="Path to biopsy text file",
    )
    parser.add_argument(
        "--cancer-type",
        default="Non-Small Cell Lung Cancer",
        help="Cancer type string for context",
    )
    args = parser.parse_args()

    vcf_path = Path(args.vcf)
    biopsy_path = Path(args.biopsy)

    if not vcf_path.exists():
        print(f"Error: VCF not found: {vcf_path}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_main(vcf_path, biopsy_path, args.cancer_type))


if __name__ == "__main__":
    main()
