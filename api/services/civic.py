"""CIViC GraphQL API client.

Docs: https://docs.civicdb.org/en/latest/api/graphql.html
Public API — no auth required.
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_GRAPHQL = "https://civicdb.org/api/graphql"


_VARIANT_QUERY = """
query VariantEvidence($gene: String!, $variant: String!) {
  variants(geneSymbol: $gene, name: $variant, first: 1) {
    nodes {
      name
      variantAliases
      evidenceItems(first: 5) {
        nodes {
          evidenceLevel
          evidenceType
          clinicalSignificance
          description
          disease { name }
          drugs { name }
        }
      }
    }
  }
}
"""


async def get_civic_evidence(gene: str, variant: str) -> Optional[list[dict]]:
    """Return a list of CIViC evidence items for a gene/variant pair.

    Each item contains: evidenceLevel, evidenceType, clinicalSignificance,
    description, disease, drugs.
    Returns None on error or if no variant found.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _GRAPHQL,
                json={"query": _VARIANT_QUERY, "variables": {"gene": gene, "variant": variant}},
            )
            resp.raise_for_status()
            data = resp.json()
            nodes = data.get("data", {}).get("variants", {}).get("nodes", [])
            if not nodes:
                return None
            evidence = nodes[0].get("evidenceItems", {}).get("nodes", [])
            return evidence if evidence else None
    except Exception as exc:
        logger.warning("CIViC lookup failed for %s %s: %s", gene, variant, exc)
        return None
