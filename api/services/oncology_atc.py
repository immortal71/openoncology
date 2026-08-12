"""Oncology-relevance gate for Tier 2 repurposing candidates.

WHY THIS EXISTS
---------------
Tier 2 repurposing pulled any FDA-approved drug with a recorded gene
interaction from DGIdb/OpenTargets. The only filter was "is this approved for
anything?", with no check that the drug is an oncology therapy at all. Real
output from the 2026-07-28 concordance pilot:

    ATP1A2 mutation -> acetyldigitoxin, deslanoside, digitoxin  (cardiac glycosides)
    DPYS   mutation -> atenolol, dexrazoxane                    (beta blocker)
    ARG1   mutation -> glycerol phenylbutyrate, sildenafil
    ARSB   mutation -> ascorbic acid, galsulfase                (vitamin C)
    ADRA1A mutation -> alfuzosin, doxazosin                     (BPH drugs)

Those were presented to cancer patients as ranked drug candidates. Digitoxin
in particular is a narrow-therapeutic-index cardiac glycoside. Showing it as a
treatment option is worse than returning nothing.

This matters at scale: the 200-patient TCGA benchmark reports 7.5% Tier 1 and
92.5% escalation, so Tier 2 is the path most patients actually land on.

HOW IT DECIDES
--------------
WHO ATC classification, sourced from ChEMBL, never hand-written here:

    L01 = antineoplastic agents
    L02 = endocrine therapy

A drug is oncology-relevant if any of its ATC codes starts with L01 or L02.
Verified to separate the real cases above: imatinib L01EA01 and tamoxifen
L02BA01 pass; atenolol C07AB03, digitoxin C01AA04 and ascorbic acid G01AD03
do not.

A DRUG IS DROPPED ONLY ON POSITIVE EVIDENCE THAT IT IS NOT ONCOLOGY
-------------------------------------------------------------------
The rule is deliberately NOT "keep only what we can prove is oncology". That
version was written first and rejected: it dropped tamoxifen, sunitinib,
bevacizumab, trastuzumab and everolimus, because ChEMBL's search endpoint
answers inconsistently under repeated queries and many biologics carry no ATC
there at all. A filter that removes trastuzumab from a patient's options is far
worse than the noise it was built to remove.

So the decision is inverted:

    has an ATC starting L01/L02   -> KEEP  (oncology therapy)
    has ATC codes, none L01/L02   -> DROP  (positively classified as something
                                            else: digitoxin C01AA04, atenolol
                                            C07AB03, ascorbic acid G01AD03)
    no ATC codes / lookup failed  -> KEEP  (unknown is not evidence)

Every absurd case from the pilot carries a known non-oncology ATC, so all of
them are still removed, while a failed lookup or an unclassified biologic
degrades to today's behaviour instead of deleting a real therapy. For a filter
standing between a patient and their treatment options, that is the correct
direction to fail.

This will still REDUCE reported coverage, and that is the point. The previous
"100% coverage, zero empty outputs" figure was partly an artifact of never
filtering: the system could always find some approved drug with a gene
interaction, so it never had to report that it found nothing.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

_CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_ONCOLOGY_ATC_PREFIXES = ("L01", "L02")

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "validation_results", "atc_cache.json",
)

_lock = threading.Lock()
_cache: Optional[dict[str, list[str]]] = None


def _load_cache() -> dict[str, list[str]]:
    global _cache
    if _cache is None:
        try:
            with open(os.path.abspath(_CACHE_PATH), encoding="utf-8") as fh:
                _cache = json.load(fh)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save_cache() -> None:
    try:
        path = os.path.abspath(_CACHE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_cache or {}, fh, indent=2, sort_keys=True)
    except OSError as exc:  # cache is an optimisation; never fail the request
        logger.warning("[atc] could not write cache: %s", exc)


def normalise(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def atc_codes(drug_name: str, *, allow_network: bool = True) -> list[str]:
    """ATC codes for a drug. Empty list means unknown, not 'no codes exist'."""
    key = normalise(drug_name)
    if not key:
        return []

    cache = _load_cache()
    if key in cache:
        return cache[key]
    if not allow_network:
        return []

    codes: list[str] = []
    try:
        import httpx

        # Take several hits, not one. ChEMBL's first search result is often a
        # null record or a salt form carrying no ATC, with the real molecule
        # ranked second or third -- querying SUNITINIB returns (None, []) first
        # and ('SUNITINIB', ['L01EX01']) second. Reading only hit[0] silently
        # dropped genuine cancer drugs, which is the dangerous direction for a
        # filter that excludes unknowns.
        resp = httpx.get(
            f"{_CHEMBL_BASE}/molecule/search.json",
            params={"q": drug_name, "limit": 10},
            timeout=30,
        )
        if resp.status_code == 200:
            molecules = resp.json().get("molecules") or []
            seen: set[str] = set()
            for molecule in molecules:
                for code in molecule.get("atc_classifications") or []:
                    if code and str(code) not in seen:
                        seen.add(str(code))
                        codes.append(str(code))
        else:
            logger.warning("[atc] ChEMBL returned %s for %r", resp.status_code, drug_name)
            return []  # transient failure: do not poison the cache
    except Exception as exc:  # noqa: BLE001 - network/parse issues are non-fatal
        logger.warning("[atc] lookup failed for %r: %s", drug_name, exc)
        return []

    with _lock:
        cache[key] = codes
        _save_cache()
    return codes


def is_oncology_drug(drug_name: str, *, allow_network: bool = True) -> bool:
    """True if the drug carries an ATC L01/L02 (antineoplastic/endocrine) code.

    Note this is a positive test only. Do not use it directly to filter -- an
    unknown drug answers False here but must NOT be dropped. Use
    `should_exclude` or `partition_candidates` for filtering decisions.
    """
    return any(
        code.upper().startswith(_ONCOLOGY_ATC_PREFIXES)
        for code in atc_codes(drug_name, allow_network=allow_network)
    )


def should_exclude(drug_name: str, *, allow_network: bool = True) -> bool:
    """True only when the drug is positively classified as non-oncology.

    Unknown drugs (no ATC on record, or a failed lookup) return False and are
    therefore kept. See the module docstring for why this direction matters.
    """
    codes = atc_codes(drug_name, allow_network=allow_network)
    if not codes:
        return False  # unknown is not evidence of anything
    return not any(c.upper().startswith(_ONCOLOGY_ATC_PREFIXES) for c in codes)


def partition_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    name_key: str = "drug_name",
    allow_network: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split candidates into (oncology_relevant, excluded).

    Excluded candidates are returned rather than discarded so a caller can show
    them under a separate, clearly-labelled heading instead of silently
    dropping evidence. They must not be mixed into the ranked recommendations.
    """
    keep: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for candidate in candidates:
        name = candidate.get(name_key) or ""
        codes = atc_codes(name, allow_network=allow_network)
        oncology = any(c.upper().startswith(_ONCOLOGY_ATC_PREFIXES) for c in codes)
        # Drop only on positive evidence of a non-oncology class. No codes means
        # unknown, and unknown is kept.
        exclude = bool(codes) and not oncology
        annotated = {
            **candidate,
            "atc_codes": codes,
            "oncology_relevant": oncology,
            "atc_classified": bool(codes),
        }
        (dropped if exclude else keep).append(annotated)
    if dropped:
        logger.info(
            "[atc] filtered %d non-oncology candidate(s): %s",
            len(dropped), ", ".join(d.get(name_key, "?") for d in dropped[:5]),
        )
    return keep, dropped


# ── STATUS: WIRED IN ─────────────────────────────────────────────────────────
# Called from api/workers/ai_worker.py::_query_repurposing_candidates with
# allow_network=False, so it reads only the committed offline cache
# (validation_results/atc_cache.json -- 4,841 drugs from ChEMBL's bulk
# atc_class endpoint, 374 of them L01/L02). No live lookup on the request path,
# and the gate is wrapped so it can never fail a case.
#
# The cache is committed rather than fetched at runtime because ChEMBL's
# per-drug /molecule/search endpoint is unreliable: digitoxin resolved to
# C01AA04 on one attempt and returned nothing on later ones. The bulk
# atc_class endpoint is stable, so it is fetched once and stored.
#
# Rebuild with: python scripts/build_atc_cache.py
