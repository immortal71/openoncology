"""A/B the candidate-pool models on the gold cases, with a paired test.

THE QUESTION
------------
docs/BENCHMARK_NCI_MATCH.md found that production ranks a Tier 2 pool annotated
with evidence-table levels (`tier2`), and that a model preferring the evidence
table and falling back to Tier 2 (`fallback`) scored better on exact match: 15
arms against 12. That is a three-arm difference over 32 arms, which is enough to
justify testing the change and nowhere near enough to justify making it.

This runs the same comparison over the ranking gate's gold cases, which number
in the hundreds rather than the dozens, and applies a paired statistical test
instead of comparing two percentages by eye.

WHY A PAIRED TEST
-----------------
Both models see the same cases, so the outcomes are paired and the cases that
both get right or both get wrong carry no information about which is better.
Only the discordant pairs do: cases A gets right and B does not, and the
reverse. That is McNemar's test, and its exact binomial form is used here
because the discordant counts are small enough that the chi-square
approximation is not safe.

The bootstrap interval alongside it is over the paired difference, resampling
cases rather than outcomes, so it answers "how much would this difference move
if we had drawn a different set of gold cases".

THE LEAKAGE IS NOT NEUTRAL BETWEEN THESE TWO ARMS
-------------------------------------------------
This script was written believing the opposite, and the first full run
disproved it. The reasoning is left here because the mistake is instructive.

scripts/validate_ranking_precision.py records that 94.5% of gold cases have
their expected drugs already inside the evidence table. The assumption was that
such a bias inflates both arms equally, so a paired difference survives it even
though the absolute rate does not.

It does not, because the two arms are not symmetric with respect to the thing
that leaks. `fallback` preferentially reads the evidence table. The "contained"
subset is *defined* as the cases whose gold answer is in the evidence table. So
scoring `fallback` on contained cases asks whether a model that reads the table
does well on cases selected for the table containing the answer. It wins by 20
points, and that number means almost nothing.

A leakage bias is only neutral in a paired comparison when neither arm is
correlated with the leak. Here one arm is defined by it.

The subset that can actually answer the question is `independent`, and on this
gold set that subset is 8 cases out of 470. That is why the independent block
below is the one to read, and why the overall figure is reported but should not
be quoted.

READ THIS BEFORE ACTING ON THE RESULT
-------------------------------------
* A win here is a win on drug identity within the top three. It is not evidence
  that either model produces better treatment decisions, which no benchmark in
  this repository measures.
* Tier 2 calls OpenTargets and DGIdb live, so the result moves as those services
  do. Results are cached per gene within a run, not across runs.
* hit@3 is the primary outcome: does any expected drug appear in the top three.
  Precision@3 is reported too, but hit@3 is the paired binary outcome the test
  needs.

Usage:
    python scripts/ab_candidate_pool.py
    python scripts/ab_candidate_pool.py --a tier2 --b fallback --limit 120
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api"), str(_REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_GOLD = _REPO_ROOT / "validation_results" / "ranking_precision.json"
_OUT = _REPO_ROOT / "validation_results" / "ab_candidate_pool.json"


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _binom_two_sided(b: int, c: int) -> float:
    """Exact McNemar: two-sided binomial test on the discordant pairs.

    Under the null that neither model is better, each discordant case is a fair
    coin. Returns 1.0 when there are no discordant pairs, which is the correct
    answer to "is there evidence of a difference" when nothing disagreed.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _bootstrap_ci(
    pairs: list[tuple[int, int]], iterations: int = 5000, seed: int = 11
) -> tuple[float, float]:
    """Percentile CI on (rate_b - rate_a), resampling cases with replacement."""
    if not pairs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(pairs)
    diffs = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        a = sum(p[0] for p in sample) / n
        b = sum(p[1] for p in sample) / n
        diffs.append(b - a)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs)) - 1]
    return (round(lo * 100, 2), round(hi * 100, 2))


def _bootstrap_ci_continuous(
    pairs: list[tuple[float, float]], iterations: int = 5000, seed: int = 11
) -> tuple[float, float]:
    """Percentile CI on the mean paired difference for a continuous outcome.

    hit@3 saturates on a broad answer key: if a gene's gold set holds five
    approved drugs, almost any sane ranker puts one of them in the top three, so
    both arms score near 100% and the binary test has nothing to separate. On
    the FDA key that is exactly what happened, 95.24% against 100% with a single
    discordant pair.

    Precision@3 does not saturate, because it asks how many of the three slots
    were right rather than whether any of them was. It is the outcome with power
    on a key like this one.
    """
    if not pairs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(pairs)
    diffs = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        diffs.append(sum(b - a for a, b in sample) / n)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs)) - 1]
    return (round(lo * 100, 2), round(hi * 100, 2))


def _sign_test(pairs: list[tuple[float, float]]) -> tuple[int, int, float]:
    """Two-sided sign test over cases where the two arms differ."""
    b_wins = sum(1 for a, b in pairs if b > a)
    a_wins = sum(1 for a, b in pairs if a > b)
    return b_wins, a_wins, _binom_two_sided(b_wins, a_wins)


def _load_cases(path: Path, limit: int | None) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for case in payload.get("cases") or []:
        gene = case.get("gene")
        variant = case.get("variant")
        gold = {_norm(d) for d in (case.get("known_drugs") or []) if d}
        if not gene or not gold:
            continue
        cases.append(
            {
                "case_id": case.get("case_id"),
                "gene": gene,
                "variant": variant or "",
                "gold": gold,
                "containment": case.get("containment"),
            }
        )
    if limit:
        cases = cases[:limit]
    return cases


def _filter_independent(cases: list[dict]) -> list[dict]:
    return [c for c in cases if c.get("containment") == "independent"]


def _load_fda_cases(path: Path) -> list[dict]:
    """Cases from the FDA-label answer key.

    One case per gene, gold set being every drug whose approved indication names
    that gene as a positive selection criterion. Built by
    scripts/build_fda_label_answer_key.py from openFDA, which no part of the
    recommendation path reads, so nothing here leaks from the evidence table
    being scored. Every case is therefore "independent" by construction, which
    is the whole reason this source exists.

    No variant is supplied. A label names the gene and often a specific
    alteration, but the pairing under test is gene to drug, and passing an empty
    variant is the honest expression of that.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for gene, drugs in (payload.get("key") or {}).items():
        gold = {_norm(d) for d in drugs if d}
        if not gold:
            continue
        cases.append(
            {
                "case_id": f"FDA_{gene}",
                "gene": gene,
                "variant": "",
                "gold": gold,
                "containment": "independent",
            }
        )
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gold", default=str(_GOLD))
    ap.add_argument(
        "--fda-key",
        nargs="?",
        const=str(_REPO_ROOT / "validation_results" / "fda_label_answer_key.json"),
        help="use the FDA-label answer key instead of the OncoKB-derived gold "
        "cases. Independent of every source the engine reads, and the only "
        "answer key here that is.",
    )
    ap.add_argument("--a", default="tier2", help="baseline model (production)")
    ap.add_argument("--b", default="fallback", help="challenger model")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--independent-only",
        action="store_true",
        help="score only cases whose gold drugs are NOT already in the evidence "
        "table. The only subset where the two pool models can be compared "
        "fairly, and on the current gold set it is very small.",
    )
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    from benchmark_nci_match import run_pipeline

    if args.fda_key:
        cases = _load_fda_cases(Path(args.fda_key))
        if args.limit:
            cases = cases[: args.limit]
    else:
        cases = _load_cases(Path(args.gold), args.limit)
    if args.independent_only:
        cases = _filter_independent(cases)
    if not cases:
        print("no usable gold cases", file=sys.stderr)
        return 1
    print(f"  {len(cases)} gold cases, comparing {args.a} (A) vs {args.b} (B)\n")

    rows = []
    for i, case in enumerate(cases, 1):
        outcome = {}
        for label, mode in (("a", args.a), ("b", args.b)):
            try:
                top3 = run_pipeline(case["gene"], case["variant"], mode=mode)
            except Exception as exc:
                print(f"    {case['case_id']} {mode}: {exc}", file=sys.stderr)
                top3 = []
            hit = int(any(_norm(d) in case["gold"] for d in top3))
            prec = (
                sum(1 for d in top3[:3] if _norm(d) in case["gold"]) / len(top3[:3])
                if top3
                else 0.0
            )
            outcome[label] = {"top3": top3, "hit": hit, "precision": prec}
        rows.append({**case, "gold": sorted(case["gold"]), **outcome})
        if i % 25 == 0:
            print(f"    {i}/{len(cases)} cases", flush=True)

    def summarise(subset: list[dict]) -> dict:
        n = len(subset)
        if not n:
            return {"n": 0}
        a_hits = sum(r["a"]["hit"] for r in subset)
        b_hits = sum(r["b"]["hit"] for r in subset)
        # discordant pairs
        b_only = sum(1 for r in subset if r["b"]["hit"] and not r["a"]["hit"])
        a_only = sum(1 for r in subset if r["a"]["hit"] and not r["b"]["hit"])
        pairs = [(r["a"]["hit"], r["b"]["hit"]) for r in subset]
        lo, hi = _bootstrap_ci(pairs)
        prec_pairs = [(r["a"]["precision"], r["b"]["precision"]) for r in subset]
        p_lo, p_hi = _bootstrap_ci_continuous(prec_pairs)
        p_b, p_a, p_sign = _sign_test(prec_pairs)
        return {
            "n": n,
            "a_hit_at_3": round(100 * a_hits / n, 2),
            "b_hit_at_3": round(100 * b_hits / n, 2),
            "a_precision_at_3": round(
                100 * sum(r["a"]["precision"] for r in subset) / n, 2
            ),
            "b_precision_at_3": round(
                100 * sum(r["b"]["precision"] for r in subset) / n, 2
            ),
            "b_only_wins": b_only,
            "a_only_wins": a_only,
            "difference_pct_points": round(100 * (b_hits - a_hits) / n, 2),
            "bootstrap_95ci_pct_points": [lo, hi],
            "mcnemar_exact_p": round(_binom_two_sided(b_only, a_only), 5),
            "precision_difference_pct_points": round(
                100
                * sum(b - a for a, b in prec_pairs)
                / n,
                2,
            ),
            "precision_bootstrap_95ci_pct_points": [p_lo, p_hi],
            "precision_b_wins": p_b,
            "precision_a_wins": p_a,
            "precision_sign_test_p": round(p_sign, 5),
        }

    overall = summarise(rows)
    independent = summarise([r for r in rows if r.get("containment") == "independent"])
    contained = summarise([r for r in rows if r.get("containment") == "contained"])

    payload = {
        "audit": "ab_candidate_pool",
        "question": (
            f"Does the {args.b} candidate pool beat the {args.a} pool that "
            "production uses, on drug identity within the top three?"
        ),
        "model_a": args.a,
        "model_b": args.b,
    "primary_outcome": (
            "hit@3 where it discriminates; Precision@3 where hit@3 saturates. "
            "On a broad answer key a gene with several approved drugs makes "
            "hit@3 near-certain for any sane ranker, so the binary test loses "
            "its power and P@3 is the outcome to read."
        ),
        "test": "McNemar exact (two-sided binomial on discordant pairs)",
        "overall": overall,
        "independent_subset": independent,
        "contained_subset": contained,
        "caveats": [
            "The leakage is NOT neutral between these arms. `fallback` reads the "
            "evidence table by design, and the contained subset is defined as "
            "cases whose answer is in that table, so its win there is close to "
            "circular. Read the independent subset, and note how small it is.",
            "A win is a win on drug identity in the top three, not evidence of "
            "better treatment decisions, which nothing here measures.",
            "Tier 2 is a live service; results move as it does.",
        ],
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for name, block in (
        ("overall", overall),
        ("independent", independent),
        ("contained", contained),
    ):
        if not block.get("n"):
            continue
        print()
        print(f"  {name}  (n={block['n']})")
        print(f"    A {args.a:<9} hit@3 {block['a_hit_at_3']:>6}%   P@3 {block['a_precision_at_3']:>6}%")
        print(f"    B {args.b:<9} hit@3 {block['b_hit_at_3']:>6}%   P@3 {block['b_precision_at_3']:>6}%")
        print(
            f"    difference {block['difference_pct_points']:+.2f} pts   "
            f"95% CI [{block['bootstrap_95ci_pct_points'][0]}, "
            f"{block['bootstrap_95ci_pct_points'][1]}]"
        )
        print(
            f"    hit@3 discordant: B only {block['b_only_wins']}, A only "
            f"{block['a_only_wins']}   McNemar p={block['mcnemar_exact_p']}"
        )
        print(
            f"    P@3 difference {block['precision_difference_pct_points']:+.2f} pts   "
            f"95% CI [{block['precision_bootstrap_95ci_pct_points'][0]}, "
            f"{block['precision_bootstrap_95ci_pct_points'][1]}]   "
            f"B wins {block['precision_b_wins']}, A wins {block['precision_a_wins']}, "
            f"sign p={block['precision_sign_test_p']}"
        )
    print()
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
