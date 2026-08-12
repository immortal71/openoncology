"""Rebuild the WHO ATC drug-classification cache used by the Tier 2 oncology gate.

Writes validation_results/atc_cache.json as {normalised_drug_name: [atc_codes]}.
That file is committed so api/services/oncology_atc.py can classify drugs
offline, with no network call on the request path.

Why bulk rather than per-drug lookup: ChEMBL's /molecule/search endpoint is
unreliable under repeated queries. The same drug (digitoxin) resolved to
C01AA04 on one attempt and returned nothing on later attempts, including with
retries and backoff. Since the gate keeps unknown drugs, that flakiness would
silently make the filter inert. The /atc_class bulk endpoint is stable, so it
is paginated once here and the result committed.

Usage:
    python scripts/build_atc_cache.py
"""
from __future__ import annotations

import json
import os
import time

import httpx

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_OUT = os.path.join(_REPO_ROOT, "validation_results", "atc_cache.json")
_URL = "https://www.ebi.ac.uk/chembl/api/data/atc_class.json"
_PAGE = 1000


def _get(params: dict, tries: int = 5) -> dict | None:
    for attempt in range(tries):
        try:
            resp = httpx.get(_URL, params=params, timeout=120)
            if resp.status_code == 200:
                return resp.json()
        except Exception:  # noqa: BLE001 - retried below
            pass
        time.sleep(3 * (attempt + 1))
    return None


def main() -> None:
    rows: list[dict] = []
    offset = 0
    key: str | None = None

    while True:
        payload = _get({"limit": _PAGE, "offset": offset})
        if payload is None:
            raise SystemExit(f"ChEMBL unreachable at offset {offset}; cache not written")
        if key is None:
            key = next(k for k in payload if k != "page_meta")
        batch = payload.get(key) or []
        if not batch:
            break
        rows.extend(batch)
        offset += _PAGE
        print(f"fetched {len(rows)}")

    cache: dict[str, list[str]] = {}
    for row in rows:
        name = " ".join((row.get("who_name") or "").strip().lower().split())
        code = row.get("level5")
        if not name or not code:
            continue
        codes = cache.setdefault(name, [])
        if code not in codes:
            codes.append(code)

    os.makedirs(os.path.dirname(_OUT), exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=1, sort_keys=True)

    oncology = sum(
        1 for codes in cache.values()
        if any(c.startswith(("L01", "L02")) for c in codes)
    )
    print(f"wrote {_OUT}")
    print(f"  {len(cache)} drugs, {oncology} oncology (ATC L01/L02)")


if __name__ == "__main__":
    main()
