"""Kaplan-Meier survival analysis service — Phase 3 visualisations.

Computes Kaplan-Meier survival curves for a cohort stratified by gene
alteration status (mutated vs wildtype).  Used by the study explorer and
gene detail pages to show survival data comparable to cBioPortal's
survival plots.

Survival analysis steps:
  1. Fetch OS/DFS data from cohort_samples for the requested study
  2. Split into two groups: samples with the alteration vs without
  3. Compute Kaplan-Meier survival function for each group
  4. Compute log-rank test p-value
  5. Return curve data points for frontend rendering

The KM computation is done with a pure-Python implementation that avoids
the lifelines dependency (which is large) while being accurate for standard
clinical oncology use cases.

For production use with large cohorts, consider replacing _km_curve() with
the lifelines KaplanMeierFitter for better confidence interval handling.

References:
  - Kaplan & Meier, JASA 1958
  - Mantel, Cancer Chemotherapy Reports 1966 (log-rank test)
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


# ── KM computation ─────────────────────────────────────────────────────────────

def _km_curve(times: list[float], events: list[int]) -> list[dict]:
    """Compute Kaplan-Meier survival function.

    Args:
        times:  List of survival times (months).
        events: List of event indicators (1=deceased/progressed, 0=censored).

    Returns:
        List of {time, survival, n_at_risk, n_events, n_censored} dicts,
        sorted by time ascending.  Suitable for step-function rendering.
    """
    if not times:
        return []

    n = len(times)
    # Sort by time
    data = sorted(zip(times, events), key=lambda x: x[0])

    survival = 1.0
    n_at_risk = n
    curve: list[dict] = [{"time": 0.0, "survival": 1.0, "n_at_risk": n, "n_events": 0, "n_censored": 0}]

    i = 0
    while i < len(data):
        t = data[i][0]
        # Collect all records at this time point
        n_events = 0
        n_censored = 0
        j = i
        while j < len(data) and data[j][0] == t:
            if data[j][1] == 1:
                n_events += 1
            else:
                n_censored += 1
            j += 1

        if n_events > 0:
            survival *= (n_at_risk - n_events) / n_at_risk

        curve.append({
            "time": float(t),
            "survival": round(survival, 6),
            "n_at_risk": n_at_risk,
            "n_events": n_events,
            "n_censored": n_censored,
        })

        n_at_risk -= (n_events + n_censored)
        i = j

    return curve


def _log_rank_test(
    times_a: list[float], events_a: list[int],
    times_b: list[float], events_b: list[int],
) -> float:
    """Compute log-rank test p-value between two survival groups.

    Returns p-value (float, 0–1).  Returns 1.0 if insufficient data.
    """
    if len(times_a) < 3 or len(times_b) < 3:
        return 1.0

    # Combine all unique event times
    all_times = sorted(set(
        t for t, e in zip(times_a + times_b, events_a + events_b) if e == 1
    ))

    if not all_times:
        return 1.0

    O_a_total = 0.0
    E_a_total = 0.0
    V_total = 0.0

    for t in all_times:
        # n at risk in each group at time t
        n_a = sum(1 for ti in times_a if ti >= t)
        n_b = sum(1 for ti in times_b if ti >= t)
        n_total = n_a + n_b

        if n_total == 0:
            continue

        # observed events at time t
        o_a = sum(1 for ti, ei in zip(times_a, events_a) if ti == t and ei == 1)
        o_b = sum(1 for ti, ei in zip(times_b, events_b) if ti == t and ei == 1)
        o_total = o_a + o_b

        if o_total == 0:
            continue

        e_a = o_total * n_a / n_total
        E_a_total += e_a
        O_a_total += o_a

        if n_total > 1:
            v = (o_total * n_a * n_b * (n_total - o_total)) / (n_total ** 2 * (n_total - 1))
            V_total += v

    if V_total <= 0:
        return 1.0

    chi2 = (O_a_total - E_a_total) ** 2 / V_total
    # Chi-squared CDF approximation (1 degree of freedom)
    p_value = _chi2_sf(chi2, df=1)
    return round(p_value, 6)


def _chi2_sf(x: float, df: int = 1) -> float:
    """Survival function (1 - CDF) for chi-squared distribution with df degrees of freedom.
    Uses regularised incomplete gamma function approximation for df=1.
    """
    if x <= 0:
        return 1.0
    # For df=1: chi2_sf(x) = erfc(sqrt(x/2))
    return math.erfc(math.sqrt(x / 2))


def _median_survival(curve: list[dict]) -> Optional[float]:
    """Return median survival time (time when survival ≤ 0.5)."""
    for point in curve:
        if point["survival"] <= 0.5:
            return point["time"]
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def compute_survival_curves(
    study_id_internal: str,
    gene: str,
    protein_change: Optional[str],
    db,
    survival_type: str = "OS",
) -> dict:
    """Compute Kaplan-Meier curves for mutated vs wildtype groups in a study.

    Args:
        study_id_internal: Internal DB Study.id (UUID).
        gene:              Hugo gene symbol.
        protein_change:    Optional specific alteration (e.g. "L858R").
                           If None, all mutations in the gene are used.
        db:                AsyncSession.
        survival_type:     "OS" (overall survival) or "DFS" (disease-free survival).

    Returns:
        Dict with mutant_curve, wildtype_curve, log_rank_p, median_mutant,
        median_wildtype, n_mutant, n_wildtype keys.
    """
    from sqlalchemy import select
    from models.cohort import Sample, CohortMutation

    # Fetch all samples with survival data
    if survival_type == "DFS":
        samples_stmt = select(Sample).where(
            Sample.study_id == study_id_internal,
            Sample.dfs_months.isnot(None),
            Sample.dfs_status.isnot(None),
        )
    else:
        samples_stmt = select(Sample).where(
            Sample.study_id == study_id_internal,
            Sample.os_months.isnot(None),
            Sample.os_status.isnot(None),
        )

    samples = (await db.execute(samples_stmt)).scalars().all()
    if not samples:
        return _empty_survival_response(gene, protein_change, survival_type)

    # Find samples with the alteration
    mut_stmt = select(CohortMutation.sample_id).where(
        CohortMutation.study_id == study_id_internal,
        CohortMutation.gene == gene.upper(),
    )
    if protein_change:
        mut_stmt = mut_stmt.where(CohortMutation.protein_change == protein_change)
    mutant_sample_ids = {
        row[0] for row in (await db.execute(mut_stmt)).all()
    }

    # Split samples into mutant and wildtype groups
    mutant_times, mutant_events = [], []
    wildtype_times, wildtype_events = [], []

    for s in samples:
        if survival_type == "DFS":
            t = s.dfs_months
            e = s.dfs_status
        else:
            t = s.os_months
            e = s.os_status

        if t is None or e is None:
            continue

        if s.id in mutant_sample_ids:
            mutant_times.append(float(t))
            mutant_events.append(int(e))
        else:
            wildtype_times.append(float(t))
            wildtype_events.append(int(e))

    if not mutant_times and not wildtype_times:
        return _empty_survival_response(gene, protein_change, survival_type)

    mutant_curve = _km_curve(mutant_times, mutant_events)
    wildtype_curve = _km_curve(wildtype_times, wildtype_events)
    p_value = _log_rank_test(mutant_times, mutant_events, wildtype_times, wildtype_events)

    return {
        "gene": gene.upper(),
        "protein_change": protein_change,
        "survival_type": survival_type,
        "n_mutant": len(mutant_times),
        "n_wildtype": len(wildtype_times),
        "log_rank_p": p_value,
        "median_mutant_months": _median_survival(mutant_curve),
        "median_wildtype_months": _median_survival(wildtype_curve),
        "mutant_curve": mutant_curve,
        "wildtype_curve": wildtype_curve,
    }


def _empty_survival_response(gene: str, protein_change: Optional[str], survival_type: str) -> dict:
    return {
        "gene": gene.upper(),
        "protein_change": protein_change,
        "survival_type": survival_type,
        "n_mutant": 0,
        "n_wildtype": 0,
        "log_rank_p": None,
        "median_mutant_months": None,
        "median_wildtype_months": None,
        "mutant_curve": [],
        "wildtype_curve": [],
        "message": "Insufficient survival data for this gene/alteration in the selected study.",
    }
