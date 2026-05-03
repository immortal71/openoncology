"""
openFDA drug approvals API client.

Uses the publicly accessible openFDA REST API (no API key required for
low-volume requests; register at https://open.fda.gov/apis/authentication/
for higher rate limits).

API reference: https://open.fda.gov/apis/drug/drugsfda/
Endpoint:      https://api.fda.gov/drug/

Provides:
  - lookup_fda_approval(drug_name)  → confirm FDA approval + indication
  - get_oncology_approvals()        → NCI/oncology-indication approved drugs
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

from utils.http import fetch_with_retry

logger = logging.getLogger(__name__)

_BASE = "https://api.fda.gov/drug"
_TIMEOUT = 15

# Common oncology terms used to match FDA indication strings
_ONCOLOGY_TERMS = [
    "cancer", "tumor", "tumour", "carcinoma", "leukemia", "lymphoma",
    "melanoma", "sarcoma", "myeloma", "glioma", "glioblastoma", "neuroblastoma",
    "hepatocellular", "cholangiocarcinoma", "mesothelioma", "adenocarcinoma",
    "squamous", "neoplasm", "malignant", "oncology", "metastatic", "renal cell",
]


async def lookup_fda_approval(drug_name: str) -> Optional[dict]:
    """Look up FDA approval status for a drug by name.

    Queries the openFDA drug approvals dataset (drugsfda).  Returns a dict
    with approval details if found, or None if not found / not approved.

    Returns
    -------
    dict | None
        {
          "brand_name": str,
          "generic_name": str,
          "application_number": str,  # NDA/BLA number
          "sponsor": str,
          "approval_date": str,
          "is_approved": True,
          "indications": list[str],   # from drug label when available
          "oncology_indication": bool,
        }
    """
    # Search drugsfda for this drug name
    query = f'openfda.generic_name:"{drug_name}"'
    try:
        try:
            resp = await fetch_with_retry(
                f"{_BASE}/drugsfda.json",
                timeout=_TIMEOUT,
                params={"search": query, "limit": 5},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            # Try brand name search
            resp = await fetch_with_retry(
                f"{_BASE}/drugsfda.json",
                timeout=_TIMEOUT,
                params={
                    "search": f'openfda.brand_name:"{drug_name}"',
                    "limit": 5,
                },
            )
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None  # Not found — not approved
        logger.warning("[openfda] lookup failed for %s: %s", drug_name, exc)
        return None
    except Exception as exc:
        logger.warning("[openfda] lookup failed for %s: %s", drug_name, exc)
        return None

    results = data.get("results") or []
    if not results:
        return None

    # Pick the first approved result (NDA or BLA, not ANDA which is generic)
    for result in results:
        app_num = result.get("application_number", "")
        if not (app_num.startswith("NDA") or app_num.startswith("BLA")):
            continue

        submissions = result.get("submissions") or []
        approved_submissions = [
            s for s in submissions
            if str(s.get("submission_status", "")).upper() in ("AP", "TENTATIVELY APPROVED")
        ]
        if not approved_submissions and not submissions:
            continue

        openfda = result.get("openfda") or {}
        brand_names = openfda.get("brand_name") or []
        generic_names = openfda.get("generic_name") or []
        sponsor = result.get("sponsor_name") or ""
        # Approval date from most recent AP submission
        approval_date = ""
        for sub in sorted(submissions, key=lambda s: s.get("submission_status_date", ""), reverse=True):
            if str(sub.get("submission_status", "")).upper() == "AP":
                approval_date = sub.get("submission_status_date", "")
                break

        return {
            "brand_name": brand_names[0] if brand_names else drug_name,
            "generic_name": generic_names[0] if generic_names else drug_name,
            "application_number": app_num,
            "sponsor": sponsor,
            "approval_date": approval_date,
            "is_approved": True,
            "indications": [],      # populated by label lookup
            "oncology_indication": False,  # enriched below
        }

    return None


async def get_drug_label_indications(drug_name: str) -> list[str]:
    """Return indication strings from the FDA drug label for this drug.

    Uses the /drug/label endpoint which contains full label text including
    INDICATIONS AND USAGE sections.
    """
    try:
        resp = await fetch_with_retry(
            f"{_BASE}/label.json",
            timeout=_TIMEOUT,
            params={
                "search": f'openfda.generic_name:"{drug_name}"',
                "limit": 1,
            },
        )
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        logger.warning("[openfda] label lookup failed for %s: %s", drug_name, exc)
        return []
    except Exception as exc:
        logger.warning("[openfda] label lookup failed for %s: %s", drug_name, exc)
        return []

    results = data.get("results") or []
    if not results:
        return []

    label = results[0]
    indications = (
        label.get("indications_and_usage")
        or label.get("indications")
        or []
    )
    if isinstance(indications, list):
        return [str(i)[:400] for i in indications[:3]]
    if isinstance(indications, str):
        return [indications[:400]]
    return []


async def confirm_fda_approved(drug_name: str) -> bool:
    """Return True if this drug has FDA approval (NDA or BLA).

    This is a lightweight call used to filter repurposing candidates.
    Falls back to False on any API error to avoid including unapproved drugs.
    """
    try:
        result = await lookup_fda_approval(drug_name)
        return result is not None and result.get("is_approved", False)
    except Exception:
        return False


async def get_oncology_approved_drugs(limit: int = 100) -> list[dict]:
    """Return a list of FDA-approved oncology drugs from the drug label database.

    Searches for labels that mention oncology terms in their indications.
    Returns list of {drug_name, application_number, oncology_indication: True}.
    """
    query_term = " OR ".join(f'indications_and_usage:"{t}"' for t in _ONCOLOGY_TERMS[:6])
    try:
        resp = await fetch_with_retry(
            f"{_BASE}/label.json",
            timeout=_TIMEOUT,
            params={"search": query_term, "limit": limit},
        )
        data = resp.json()
    except Exception as exc:
        logger.warning("[openfda] oncology drug list failed: %s", exc)
        return []

    results = data.get("results") or []
    drugs = []
    for label in results:
        openfda = label.get("openfda") or {}
        generic_names = openfda.get("generic_name") or []
        brand_names = openfda.get("brand_name") or []
        app_nums = openfda.get("application_number") or []

        # Only NDA/BLA (approved new drug applications), skip ANDA (generics)
        nda_bla = [n for n in app_nums if n.startswith("NDA") or n.startswith("BLA")]
        if not nda_bla:
            continue

        name = generic_names[0] if generic_names else (brand_names[0] if brand_names else None)
        if not name:
            continue

        indications = label.get("indications_and_usage") or []
        if isinstance(indications, str):
            indications = [indications]

        indication_text = " ".join(str(i) for i in indications).lower()
        is_oncology = any(term in indication_text for term in _ONCOLOGY_TERMS)

        if is_oncology:
            drugs.append(
                {
                    "drug_name": name.lower(),
                    "brand_name": brand_names[0] if brand_names else None,
                    "application_number": nda_bla[0],
                    "is_approved": True,
                    "oncology_indication": True,
                }
            )

    return drugs
