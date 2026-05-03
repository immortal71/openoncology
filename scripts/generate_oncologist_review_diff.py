"""Generate before/after oncologist review packet diff for blind holdout runs.

Compares baseline artifacts (saved under artifacts/validation_baseline/) with the
latest blind review outputs in project root, and writes:

  - artifacts/validation_diff/oncologist_review_packet_diff.json
  - artifacts/validation_diff/oncologist_review_packet_diff.md

Focus is on difficult cases (non-L1/L2 by default), with top-3 ordering changes,
rank score deltas, confidence/evidence shifts, and aggregate metric deltas.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "artifacts" / "validation_baseline"
OUT_DIR = ROOT / "artifacts" / "validation_diff"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _index_by_case_code(rows: list[dict]) -> dict[str, dict]:
    return {r.get("case_code", ""): r for r in rows if r.get("case_code")}


def _summarize_key_delta(before_key_case: dict, after_key_case: dict) -> dict:
    return {
        "case_code": after_key_case.get("case_code") or before_key_case.get("case_code"),
        "case_id": after_key_case.get("case_id") or before_key_case.get("case_id"),
        "before_auto_pass": bool(before_key_case.get("auto_pass", False)),
        "after_auto_pass": bool(after_key_case.get("auto_pass", False)),
        "before_standard_precision_at_3": before_key_case.get("standard_precision_at_3"),
        "after_standard_precision_at_3": after_key_case.get("standard_precision_at_3"),
        "before_hit_at_3": before_key_case.get("hit_at_3"),
        "after_hit_at_3": after_key_case.get("hit_at_3"),
    }


def _top3_names(case_row: dict) -> list[str]:
    return [c.get("drug_name") for c in (case_row.get("top3_candidates") or []) if c.get("drug_name")]


def _summarize_case_delta(before_case: dict, after_case: dict) -> dict:
    before_top3 = before_case.get("top3_candidates") or []
    after_top3 = after_case.get("top3_candidates") or []

    before_names = [c.get("drug_name") for c in before_top3 if c.get("drug_name")]
    after_names = [c.get("drug_name") for c in after_top3 if c.get("drug_name")]

    changed = before_names != after_names
    all_names = sorted(set(before_names) | set(after_names))

    per_drug_delta = []
    for name in all_names:
        b = next((c for c in before_top3 if c.get("drug_name") == name), None)
        a = next((c for c in after_top3 if c.get("drug_name") == name), None)
        per_drug_delta.append(
            {
                "drug_name": name,
                "before_rank": before_names.index(name) + 1 if name in before_names else None,
                "after_rank": after_names.index(name) + 1 if name in after_names else None,
                "before_score": b.get("rank_score") if b else None,
                "after_score": a.get("rank_score") if a else None,
                "before_confidence": b.get("confidence_level") if b else None,
                "after_confidence": a.get("confidence_level") if a else None,
                "before_evidence_completeness": b.get("evidence_completeness") if b else None,
                "after_evidence_completeness": a.get("evidence_completeness") if a else None,
                "before_oncokb_level": b.get("oncokb_level") if b else None,
                "after_oncokb_level": a.get("oncokb_level") if a else None,
            }
        )

    return {
        "case_code": after_case.get("case_code") or before_case.get("case_code"),
        "gene": after_case.get("gene") or before_case.get("gene"),
        "variant": after_case.get("variant") or before_case.get("variant"),
        "cancer_type": after_case.get("cancer_type") or before_case.get("cancer_type"),
        "difficulty": after_case.get("difficulty") or before_case.get("difficulty"),
        "top3_changed": changed,
        "before_top3": before_names,
        "after_top3": after_names,
        "per_drug_delta": per_drug_delta,
    }


def main() -> int:
    before_packet_path = BASE_DIR / "blind_review_packet_before.json"
    before_key_path = BASE_DIR / "blind_review_key_scoring_before.json"
    after_packet_path = ROOT / "blind_review_packet.json"
    after_key_path = ROOT / "blind_review_key_scoring.json"

    if not before_packet_path.exists() or not before_key_path.exists():
        raise FileNotFoundError("Baseline artifacts not found in artifacts/validation_baseline/")
    if not after_packet_path.exists() or not after_key_path.exists():
        raise FileNotFoundError("Current artifacts not found in project root")

    before_packet = _load_json(before_packet_path)
    before_key = _load_json(before_key_path)
    after_packet = _load_json(after_packet_path)
    after_key = _load_json(after_key_path)

    before_cases = _index_by_case_code(before_packet.get("cases", []))
    after_cases = _index_by_case_code(after_packet.get("cases", []))
    before_key_cases = _index_by_case_code(before_key.get("cases", []))
    after_key_cases = _index_by_case_code(after_key.get("cases", []))

    difficult_levels = {"L3_L4", "VUS_NEG", "UNKNOWN"}
    case_diffs = []
    changed_count = 0
    key_flips: list[dict] = []

    for case_code, after_case in sorted(after_cases.items()):
        before_case = before_cases.get(case_code)
        if not before_case:
            continue
        delta = _summarize_case_delta(before_case, after_case)
        if delta["difficulty"] in difficult_levels:
            case_diffs.append(delta)
            if delta["top3_changed"]:
                changed_count += 1

        before_key_case = before_key_cases.get(case_code)
        after_key_case = after_key_cases.get(case_code)
        if before_key_case and after_key_case:
            kd = _summarize_key_delta(before_key_case, after_key_case)
            if kd["before_auto_pass"] != kd["after_auto_pass"]:
                key_flips.append(kd)

    metrics_before = before_key.get("metrics", {})
    metrics_after = after_key.get("metrics", {})

    summary = {
        "before_run_at": before_packet.get("run_at"),
        "after_run_at": after_packet.get("run_at"),
        "n_cases_total": len(after_cases),
        "n_difficult_cases_in_diff": len(case_diffs),
        "n_difficult_top3_changed": changed_count,
        "n_auto_pass_flips": len(key_flips),
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "delta": {
            "standard_precision_at_3": round(
                float(metrics_after.get("standard_precision_at_3", 0.0))
                - float(metrics_before.get("standard_precision_at_3", 0.0)),
                4,
            ),
            "normalized_precision_at_3": round(
                float(metrics_after.get("normalized_precision_at_3", 0.0))
                - float(metrics_before.get("normalized_precision_at_3", 0.0)),
                4,
            ),
            "hit_at_3": round(
                float(metrics_after.get("hit_at_3", 0.0))
                - float(metrics_before.get("hit_at_3", 0.0)),
                4,
            ),
            "mrr": round(
                float(metrics_after.get("mrr", 0.0))
                - float(metrics_before.get("mrr", 0.0)),
                4,
            ),
            "ndcg_at_3": round(
                float(metrics_after.get("ndcg_at_3", 0.0))
                - float(metrics_before.get("ndcg_at_3", 0.0)),
                4,
            ),
            "false_positives": int(metrics_after.get("false_positives", 0))
            - int(metrics_before.get("false_positives", 0)),
        },
    }

    result = {
        "summary": summary,
        "difficult_case_diffs": case_diffs,
        "auto_pass_flips": key_flips,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "oncologist_review_packet_diff.json"
    out_md = OUT_DIR / "oncologist_review_packet_diff.md"

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    md_lines = [
        "# Oncologist Review Packet Diff (Before vs After)",
        "",
        f"- Before run: {summary['before_run_at']}",
        f"- After run: {summary['after_run_at']}",
        f"- Cases total: {summary['n_cases_total']}",
        f"- Difficult cases reviewed: {summary['n_difficult_cases_in_diff']}",
        f"- Difficult cases with top-3 changes: {summary['n_difficult_top3_changed']}",
        f"- Auto-pass flips: {summary['n_auto_pass_flips']}",
        "",
        "## Metrics Delta",
        "",
        f"- Standard P@3: {metrics_before.get('standard_precision_at_3')} -> {metrics_after.get('standard_precision_at_3')} (delta {summary['delta']['standard_precision_at_3']:+.4f})",
        f"- Normalized P@3: {metrics_before.get('normalized_precision_at_3')} -> {metrics_after.get('normalized_precision_at_3')} (delta {summary['delta']['normalized_precision_at_3']:+.4f})",
        f"- Hit@3: {metrics_before.get('hit_at_3')} -> {metrics_after.get('hit_at_3')} (delta {summary['delta']['hit_at_3']:+.4f})",
        f"- MRR: {metrics_before.get('mrr')} -> {metrics_after.get('mrr')} (delta {summary['delta']['mrr']:+.4f})",
        f"- NDCG@3: {metrics_before.get('ndcg_at_3')} -> {metrics_after.get('ndcg_at_3')} (delta {summary['delta']['ndcg_at_3']:+.4f})",
        f"- False positives: {metrics_before.get('false_positives')} -> {metrics_after.get('false_positives')} (delta {summary['delta']['false_positives']:+d})",
        "",
        "## Difficult Case Top-3 Changes",
        "",
    ]

    for d in case_diffs:
        if not d["top3_changed"]:
            continue
        md_lines.append(
            f"- {d['case_code']} | {d['gene']} {d['variant']} | {d['cancer_type']} | {d['difficulty']}"
        )
        md_lines.append(f"  - Before: {', '.join(d['before_top3']) if d['before_top3'] else '(none)'}")
        md_lines.append(f"  - After: {', '.join(d['after_top3']) if d['after_top3'] else '(none)'}")

    if changed_count == 0:
        md_lines.append("- No difficult-case top-3 ordering changes detected between runs.")

    md_lines.extend([
        "",
        "## Auto-Pass Outcome Flips",
        "",
    ])
    if key_flips:
        for kf in key_flips:
            md_lines.append(
                f"- {kf['case_code']} | {kf['case_id']} | auto_pass {kf['before_auto_pass']} -> {kf['after_auto_pass']}"
            )
    else:
        md_lines.append("- No auto-pass outcome flips.")

    with out_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print("=" * 72)
    print("ONCOLOGIST REVIEW PACKET DIFF")
    print("=" * 72)
    print(f"Difficult cases reviewed: {summary['n_difficult_cases_in_diff']}")
    print(f"Difficult top-3 changed:  {summary['n_difficult_top3_changed']}")
    print(
        "Standard P@3 delta:      "
        f"{summary['delta']['standard_precision_at_3']:+.4f}"
    )
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
