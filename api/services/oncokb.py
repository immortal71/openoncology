"""OncoKB REST API client.

Docs: https://api.oncokb.org/api/v1/
Uses the Bearer token from settings.ONCOKB_API_TOKEN.
"""
import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_BASE = "https://www.oncokb.org/api/v1"


class OncoKBClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def annotate_mutation(
        self,
        gene: str,
        protein_change: str,
        tumor_type: Optional[str] = None,
    ) -> dict:
        """Return OncoKB annotation for a single protein change.

        Returns a dict with keys: oncogenic, mutationEffect, highestSensitiveLevel,
        highestResistanceLevel, treatments, etc.
        """
        params: dict = {
            "hugoSymbol": gene,
            "alteration": protein_change,
            "referenceGenome": "GRCh38",
        }
        if tumor_type:
            params["tumorType"] = tumor_type

        url = f"{_BASE}/annotate/mutations/byProteinChange"
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def oncokb_level(self, annotation: dict) -> Optional[str]:
        """Extract the highest sensitivity level string, e.g. 'LEVEL_1'."""
        return annotation.get("highestSensitiveLevel") or annotation.get("highestResistanceLevel")

    def is_oncogenic(self, annotation: dict) -> bool:
        return annotation.get("oncogenic", "") in ("Oncogenic", "Likely Oncogenic")
