"""DGIdb GraphQL API client.

DGIdb migrated away from the legacy REST v2 API. This module uses:
POST https://dgidb.org/api/graphql

Public async entry points:
  - get_interactions(gene, approved_only=True)
  - get_categories(gene)
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from api.utils.http import fetch_with_retry
except ModuleNotFoundError:
    from utils.http import fetch_with_retry

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://dgidb.org/api/graphql"
_TIMEOUT = 20

_TRUSTED_SOURCES = {
    "CIViC",
    "CGI",
    "CancerCommons",
    "ChemblInteractions",
    "ClinicalTrials",
    "DoCM",
    "FDA",
    "Guida2018",
    "JAX-CKB",
    "MyCancerGenome",
    "MyCancerGenomeClinicalTrial",
    "OncoKB",
    "PharmGKB",
    "TEND",
    "TdgClinicalTrial",
}

_THERAPEUTIC_TYPES = {
    "inhibitor",
    "antagonist",
    "blocker",
    "modulator",
    "activator",
    "agonist",
    "antibody",
    "allosteric modulator",
    "negative modulator",
    "partial agonist",
    "positive modulator",
    "suppressor",
}


async def _graphql(query: str) -> dict:
    resp = await fetch_with_retry(
        _GRAPHQL_URL,
        method="POST",
        timeout=_TIMEOUT,
        json={"query": query},
    )
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


async def get_interactions(gene: str, approved_only: bool = True) -> list[dict]:
    """Return DGIdb drug-gene interactions for a gene symbol.

    Output format is kept compatible with current ranking/worker code.
    """
    query = f"""
    {{
      genes(names: [\"{gene}\"]) {{
        nodes {{
          name
          interactions {{
            drug {{ name approved antiNeoplastic conceptId }}
            interactionScore
            evidenceScore
            sources {{ sourceDbName }}
            interactionTypes {{ type directionality }}
          }}
        }}
      }}
    }}
    """

    try:
        data = await _graphql(query)
    except Exception as exc:
        logger.warning("[dgidb] interactions query failed for %s: %s", gene, exc)
        return []

    nodes = (data.get("data") or {}).get("genes", {}).get("nodes") or []
    if not nodes:
        return []

    interactions: list[dict] = []
    for interaction in nodes[0].get("interactions") or []:
        drug = interaction.get("drug") or {}
        drug_name = (drug.get("name") or "").strip()
        if not drug_name:
            continue

        is_approved = bool(drug.get("approved"))
        if approved_only and not is_approved:
            continue

        concept_id = drug.get("conceptId") or ""
        chembl_id: Optional[str] = None
        if "chembl:" in concept_id.lower():
            chembl_id = concept_id.split(":")[-1].upper()

        interaction_types = [
            item.get("type", "").lower()
            for item in (interaction.get("interactionTypes") or [])
            if item.get("type")
        ]
        sources = [
            item.get("sourceDbName", "")
            for item in (interaction.get("sources") or [])
            if item.get("sourceDbName")
        ]

        interaction_score = interaction.get("interactionScore")
        evidence_score = int(interaction.get("evidenceScore") or 0)
        trusted_source_count = evidence_score
        has_therapeutic_type = any(t in _THERAPEUTIC_TYPES for t in interaction_types)

        interactions.append(
            {
                "drug_name": drug_name,
                "chembl_id": chembl_id,
                "is_approved": is_approved,
                "max_phase": 4 if is_approved else None,
                "dgidb_score": float(interaction_score) if interaction_score is not None else None,
                "trusted_source_count": trusted_source_count,
                "interaction_types": interaction_types,
                "mechanism": interaction_types[0] if interaction_types else "inhibitor",
                "sources": sources,
                "evidence_sources": sorted(
                    {"DGIdb"} | {src for src in sources if src in _TRUSTED_SOURCES}
                ),
                "has_therapeutic_interaction": has_therapeutic_type,
                "matched_terms": interaction_types[:3],
                "opentargets_score": min(0.9, 0.5 + (evidence_score * 0.008)),
                "dgidb_drug_id": concept_id,
            }
        )

    seen: dict[str, dict] = {}
    for item in interactions:
        key = item["drug_name"].upper()
        existing = seen.get(key)
        if existing is None or item["trusted_source_count"] > existing["trusted_source_count"]:
            seen[key] = item

    result = sorted(seen.values(), key=lambda x: x["trusted_source_count"], reverse=True)
    logger.info("[dgidb] %d interactions for %s", len(result), gene)
    return result


async def get_categories(gene: str) -> list[str]:
    """Return DGIdb druggability category labels for a gene."""
    query = f"""
    {{
      genes(names: [\"{gene}\"]) {{
        nodes {{
          geneCategories {{ name }}
        }}
      }}
    }}
    """

    try:
        data = await _graphql(query)
    except Exception as exc:
        logger.warning("[dgidb] categories query failed for %s: %s", gene, exc)
        return []

    nodes = (data.get("data") or {}).get("genes", {}).get("nodes") or []
    if not nodes:
        return []
    return [cat.get("name", "") for cat in (nodes[0].get("geneCategories") or [])]
