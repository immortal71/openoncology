"""COSMIC (Catalogue Of Somatic Mutations In Cancer) REST v3.1 client.

COSMIC is the world's most comprehensive catalogue of somatic mutations in human cancer.
Free academic access is available at https://cancer.sanger.ac.uk/cosmic.

Authentication: Base64-encoded "email:password" via COSMIC REST v3.1
API docs: https://cancer.sanger.ac.uk/cosmic/download/cosmic/v99/restapi

Set COSMIC_EMAIL + COSMIC_PASSWORD in .env to enable.  Falls back gracefully to
returning None when credentials are absent, so the pipeline always finishes.
"""
import base64
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://cancer.sanger.ac.uk/cosmic/v3.1"
_TIMEOUT = 20.0


def _auth_header() -> dict[str, str]:
    """Build a Basic-auth header using COSMIC email+password credentials."""
    email = getattr(settings, "cosmic_email", "")
    password = getattr(settings, "cosmic_password", "")
    if not email or not password:
        return {}
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def get_cosmic_mutations(gene: str, cancer_type: Optional[str] = None) -> list[dict]:
    """Return COSMIC somatic mutation records for *gene*.

    Each record contains:
      - mutation_id    : COSM ID
      - mutation_aa    : protein change (e.g. p.Glu746_Ala750del)
      - mutation_cds   : CDS notation
      - primary_site   : tissue of origin
      - histology      : tumour histology
      - sample_count   : number of COSMIC tumour samples carrying this mutation

    Returns an empty list when credentials are absent or the API is unavailable.
    """
    headers = _auth_header()
    if not headers:
        logger.debug("[cosmic] No credentials configured — skipping COSMIC lookup for %s", gene)
        return []

    params: dict = {"gene_name": gene, "output_format": "json"}
    if cancer_type:
        params["primary_site"] = cancer_type

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE_URL}/mutations/gene",
                headers=headers,
                params=params,
            )
            if resp.status_code == 401:
                logger.warning("[cosmic] Authentication failed — check COSMIC_EMAIL / COSMIC_PASSWORD")
                return []
            resp.raise_for_status()
            data = resp.json()
            mutations = data if isinstance(data, list) else data.get("mutations", [])
            return [
                {
                    "mutation_id": m.get("mutation_id"),
                    "mutation_aa": m.get("mutation_aa"),
                    "mutation_cds": m.get("mutation_cds"),
                    "primary_site": m.get("primary_site"),
                    "histology": m.get("histology"),
                    "sample_count": m.get("sample_count", 0),
                }
                for m in mutations[:50]  # cap at 50 to limit payload size
            ]
    except Exception as exc:
        logger.warning("[cosmic] Lookup failed for gene %s: %s", gene, exc)
        return []


async def get_cosmic_variant(cosmic_id: str) -> Optional[dict]:
    """Fetch detailed information for a single COSM mutation by its numeric ID.

    Returns a dict with clinical and frequency data, or None on error.
    """
    headers = _auth_header()
    if not headers:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE_URL}/mutations/{cosmic_id}",
                headers=headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("[cosmic] Variant fetch failed for %s: %s", cosmic_id, exc)
        return None
