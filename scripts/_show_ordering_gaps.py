import json

with open("hard_benchmark_results.json") as f:
    data = json.load(f)

print("=== Ordering gaps ===")
for c in data.get("cases", []):
    if c.get("root_cause") in ("ordering_gap_within_top3", "ranking_miss_top3"):
        print(f"  {c.get('case_id')}  root_cause={c.get('root_cause')}")
        print(f"    known: {c.get('known_drugs')}")
        print(f"    top3:  {c.get('top3_drugs') or c.get('top3')}")
        print(f"    p3:    {c.get('precision_at_3')}")

print("\n=== All non-passing cases ===")
for c in data.get("cases", []):
    rc = c.get("root_cause", "")
    if rc not in ("full_top3_coverage", "negative_control_pass", "single_drug_denominator_penalty"):
        print(f"  {c.get('case_id')}  root_cause={rc}")
        print(f"    known: {c.get('known_drugs')}")
        print(f"    top3:  {c.get('top3_drugs') or c.get('top3')}")
