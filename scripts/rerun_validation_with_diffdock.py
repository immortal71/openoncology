"""
Re-run industry_grade_validation.py's evaluation with real DiffDock
binding_score values substituted in, for the subset of (case, drug)
pairs where a real GPU-backed docking result exists.

Does NOT modify or overwrite industry_grade_validation.py or its output
file (industry_validation_report.json). Reuses its real
run_industry_grade_validation() function unmodified — only the
candidate-building step (_build_candidates) is monkeypatched to fill in
binding_score where a real result is available, leaving it None
(unchanged, real weight-renormalization) everywhere else.

Matching key: (gene, drug_name normalised via the script's own _norm_drug).
Not case_id, because a single case can produce multiple ranked drug
candidates (via get_all_drugs_for_variant_live) — DiffDock was only run
for each case's single known/top drug (the agreed 1-call-per-case scope),
so only that one candidate per case gets a real score; every other
candidate for that same case is left as None, exactly like any other
missing evidence source.
"""
import json
import math
import sys

sys.path.insert(0, "/tmp/repo_root")

import scripts.industry_grade_validation as ivg  # noqa: E402


def sigmoid_normalise(raw_confidence: float) -> float:
    """Identical to ai/diffdock/score.py's parse_confidence: sigmoid(x/2)."""
    return round(1.0 / (1.0 + math.exp(-raw_confidence / 2.0)), 4)


def main():
    with open("/tmp/repo_root/real_patient_benchmark_375_diffdock_gpu_2026-07-22_COMPLETED.json") as f:
        diffdock_report = json.load(f)

    # Build lookup: (gene, normalised_drug_name) -> normalised [0,1] binding_score
    score_lookup = {}
    for r in diffdock_report["results"]:
        key = (r["gene"], ivg._norm_drug(r["drug_name"]))
        score_lookup[key] = sigmoid_normalise(r["diffdock_confidence"])

    print(f"Loaded {len(score_lookup)} real DiffDock scores for substitution")

    substituted_count = {"n": 0}
    original_build_candidates = ivg._build_candidates

    def patched_build_candidates(case):
        gene = case["gene"]
        # Reproduce the original function's candidate list, then patch
        # binding_score in place before ranking — this requires inlining
        # rather than post-hoc patching the return value, since
        # _build_candidates already calls rank_candidates() internally.
        # We replicate its pre-ranking steps here instead of touching its
        # source, to keep this script's diff isolated to this file only.
        from api.services.oncokb_evidence import get_all_drugs_for_variant_live
        from api.ai.ranking import rank_candidates

        variant = case["variant"]
        cancer_type = case.get("cancer_type")
        level_map = get_all_drugs_for_variant_live(gene, variant, cancer_type)
        civic_levels = ivg._fetch_civic_levels_sync(gene, variant) if ivg.USE_CIVIC else {}
        vaf = case.get("vaf")
        co_mutated_genes = ivg._co_mutated_genes(case)

        candidates = []
        for drug_name, level in level_map.items():
            level_upper = str(level).upper().strip()
            if not level_upper:
                continue

            key = (gene, ivg._norm_drug(drug_name))
            real_score = score_lookup.get(key)
            if real_score is not None:
                substituted_count["n"] += 1

            candidates.append({
                "drug_name": str(drug_name).title(),
                "oncokb_level": level_upper,
                "opentargets_score": None,
                "is_approved": level_upper == "LEVEL_1",
                "max_phase": 4 if level_upper == "LEVEL_1" else (3 if level_upper == "LEVEL_2" else 2),
                "binding_score": real_score,  # None if no real result — same as baseline
                "alphamissense_score": None,
                "civic_score": civic_levels.get(ivg._norm_drug(drug_name)),
                "vaf": vaf,
                "target_gene": gene,
                "co_mutated_genes": co_mutated_genes,
            })
        return rank_candidates(candidates)

    ivg._build_candidates = patched_build_candidates
    try:
        report = ivg.run_industry_grade_validation(max_cases=None)
    finally:
        ivg._build_candidates = original_build_candidates

    print(f"binding_score substituted on {substituted_count['n']} candidate(s) across all cases")

    report["_diffdock_substitution_info"] = {
        "real_scores_available": len(score_lookup),
        "candidates_with_substituted_binding_score": substituted_count["n"],
        "matching_key": "(gene, normalised_drug_name) — NOT case_id, since one case can yield multiple ranked drug candidates",
        "unmatched_candidates_binding_score_handling": (
            "Left as None, unchanged from baseline. Verified directly in api/ai/ranking.py "
            "compute_rank_score(): sources with score is None are excluded from the `raw` list "
            "entirely (line ~279), and the weighted mean is computed only over available sources "
            "with weights renormalised to sum to the original total (not a default numeric value "
            "such as 0 or 0.5 substituted in). This is the exact same mechanism used for any other "
            "missing signal (e.g. missing OpenTargets or CIViC score) — DiffDock absence is handled "
            "identically, not as a special case."
        ),
    }

    with open("/tmp/repo_root/validation_report_with_real_diffdock_2026-07-22.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\nBASELINE (pre-existing industry_validation_report.json, DiffDock always None):")
    print("  cannot print here — not loaded by this script; compare files directly")
    print("\nNEW (with real DiffDock substituted where available):")
    m = report["metrics"]
    print(f"  Hit@3:               {m['hit_at_3']:.4f}")
    print(f"  Standard P@3:        {m['standard_precision_at_3']:.4f}")
    print(f"  Ceiling-norm P@3:    {m['ceiling_normalised_p3']:.4f}")
    print(f"  MRR:                 {m['mrr']:.4f}")
    print(f"  NDCG@3:              {m['ndcg_at_3']:.4f}")
    print(f"  FP rate:             {m['false_positive_rate']:.4f}")


if __name__ == "__main__":
    main()
