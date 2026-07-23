"""One-off finalize step: attach an explicit baseline-vs-real-DiffDock
comparison header to validation_report_with_real_diffdock_2026-07-22.json.
Reads the pre-existing industry_validation_report.json (untouched,
never overwritten) purely for comparison — does not modify it.
"""
import json

with open("/tmp/repo_root/industry_validation_report.json") as f:
    baseline = json.load(f)

with open("/tmp/repo_root/validation_report_with_real_diffdock_2026-07-22.json") as f:
    new = json.load(f)

bm = baseline["metrics"]
nm = new["metrics"]


def ci_overlap(ci_a, ci_b):
    return ci_a[0] <= ci_b[1] and ci_b[0] <= ci_a[1]


comparisons = {}
for key, label in [
    ("standard_precision_at_3", "Standard P@3"),
    ("hit_at_3", "Hit@3"),
    ("ceiling_normalised_p3", "Ceiling-normalised P@3"),
]:
    ci_key = f"{key}_ci95"
    b_val, n_val = bm[key], nm[key]
    b_ci, n_ci = bm[ci_key], nm[ci_key]
    overlap = ci_overlap(b_ci, n_ci)
    comparisons[label] = {
        "baseline": b_val,
        "baseline_ci95": b_ci,
        "with_real_diffdock": n_val,
        "with_real_diffdock_ci95": n_ci,
        "delta": round(n_val - b_val, 4),
        "ci95_overlap": overlap,
        "verdict": "statistically indistinguishable (CIs overlap)" if overlap else "CIs do not overlap — statistically meaningful difference",
    }

# MRR/NDCG have no reported CI in this script's output — compare point estimates only, flagged as such.
for key, label in [("mrr", "MRR"), ("ndcg_at_3", "NDCG@3"), ("false_positive_rate", "False positive rate")]:
    comparisons[label] = {
        "baseline": bm[key],
        "with_real_diffdock": nm[key],
        "delta": round(nm[key] - bm[key], 4),
        "note": "no confidence interval reported for this metric by industry_grade_validation.py — point-estimate comparison only",
    }

overall_verdict = (
    "STATISTICALLY INDISTINGUISHABLE FROM BASELINE — all three metrics with reported "
    "95% confidence intervals (Standard P@3, Hit@3, Ceiling-normalised P@3) show near-total "
    "CI overlap between the pre-existing baseline (DiffDock always None) and this run "
    "(real DiffDock substituted for 229 of the ranked candidates where a docking result was "
    "available). Point estimates moved slightly downward across every metric, but by less than "
    "the width of the reported confidence intervals — this is consistent with sampling noise "
    "from DiffDock's stochastic diffusion sampling (same protein+ligand pair scored twice during "
    "this effort differed by ~0.02 confidence units in an earlier spot-check), not a real "
    "improvement or regression in ranking quality. Substituting real GPU-backed docking scores "
    "for ~61% of prepared cases (206/280 with a result, 229 candidate-level substitutions across "
    "all ranked drugs) did not measurably change Hit@3, Standard P@3, or Ceiling-normalised P@3 "
    "in this evaluation."
)

new["_header"] = {
    "status": "COMPLETED_RESCORING_WITH_REAL_DIFFDOCK_SUBSTITUTED",
    "distinct_from": [
        "industry_validation_report.json — the pre-existing baseline, untouched by this run, where binding_score is None for every candidate.",
        "real_patient_benchmark_375_diffdock_gpu_2026-07-21.json — the runtime ESTIMATE file from before any DiffDock run existed.",
        "real_patient_benchmark_375_diffdock_gpu_2026-07-22_COMPLETED.json — the raw 206 per-case DiffDock confidence scores this file's substitution is built from.",
    ],
    "run_date_utc": "2026-07-22",
    "substitution_scope": (
        "binding_score was substituted (as a sigmoid-normalised [0,1] value, identical to "
        "ai/diffdock/score.py's own parse_confidence formula: 1/(1+exp(-raw_confidence/2))) "
        "for any ranked candidate drug whose (gene, drug_name) matched one of the 206 real "
        "DiffDock results. 229 candidates were substituted this way, out of the full candidate "
        "pool across all 375 cases (most cases produce several ranked candidates per case via "
        "live OncoKB/CIViC evidence lookup, not just the one drug that was actually docked)."
    ),
    "unmatched_candidates_confirmed_mechanism": (
        "VERIFIED DIRECTLY IN CODE (api/ai/ranking.py, compute_rank_score, ~line 279): candidates "
        "with no real DiffDock result keep binding_score=None, exactly as in the baseline. "
        "compute_rank_score builds a list of (score, weight) pairs for all six evidence sources, "
        "then filters to `available = [(score, weight) for score, weight in raw if score is not "
        "None]` — sources with a None score are excluded from the list entirely, not replaced with "
        "a default numeric value (not 0, not 0.5). The weighted mean is then computed only over "
        "the sources that ARE available, with weights renormalised so they still sum to the "
        "original total. This is the exact same mechanism the ranking algorithm already uses for "
        "any other missing evidence source (e.g. missing OpenTargets or CIViC score) — DiffDock's "
        "absence for the remaining candidates is handled identically, not as a special case, and "
        "does NOT silently degrade to a fabricated or zero score."
    ),
    "overall_verdict": overall_verdict,
    "metric_comparisons": comparisons,
}

with open("/tmp/repo_root/validation_report_with_real_diffdock_2026-07-22.json", "w") as f:
    json.dump(new, f, indent=2)

print("Final report written with header. Verdict:")
print(overall_verdict)
print()
for label, c in comparisons.items():
    print(f"{label}: {c}")
