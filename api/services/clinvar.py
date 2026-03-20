"""ClinVar E-utilities client.

Uses NCBI E-utilities (esearch + efetch) to look up variant clinical significance.
No API key required but a contact email is sent per NCBI guidelines.
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_EMAIL = "admin@openoncology.org"


async def get_clinvar_significance(gene: str, hgvs_c: str) -> Optional[str]:
    """Return the ClinVar clinical significance string for a variant.

    Searches by HGVS notation, fetches the first result's clinical significance.
    Returns None if nothing found or on network error.
    """
    query = f"{gene}[gene] {hgvs_c}[variant name]"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: search
            search_resp = await client.get(
                _ESEARCH,
                params={
                    "db": "clinvar",
                    "term": query,
                    "retmode": "json",
                    "retmax": "1",
                    "email": _EMAIL,
                },
            )
            search_resp.raise_for_status()
            ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None

            # Step 2: fetch summary
            fetch_resp = await client.get(
                _EFETCH,
                params={
                    "db": "clinvar",
                    "id": ids[0],
                    "retmode": "json",
                    "rettype": "vcv",
                    "email": _EMAIL,
                },
            )
            fetch_resp.raise_for_status()
            data = fetch_resp.json()

            # Navigate the JSON to extract clinical significance
            records = (
                data.get("ClinVarResult-Set", {})
                .get("VariationArchive", {})
            )
            if isinstance(records, list):
                records = records[0]
            interp = (
                records.get("InterpretedRecord", {})
                .get("Interpretations", {})
                .get("Interpretation", {})
            )
            if isinstance(interp, list):
                interp = interp[0]
            return interp.get("Description")
    except Exception as exc:
        logger.warning("ClinVar lookup failed for %s %s: %s", gene, hgvs_c, exc)
        return None
