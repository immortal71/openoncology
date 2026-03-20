"""
OpenTargets Platform GraphQL API client — full integration.

Docs: https://platform-docs.opentargets.org/api-overview
Endpoint: https://api.platform.opentargets.org/api/v4/graphql

Provides:
  - get_drugs_for_target(ensg_id)     → drugs with clinical phase, MOA, indication
  - get_target_id(gene_symbol)        → Ensembl gene ID for a HGNC symbol
  - get_disease_associations(ensg_id) → disease association scores
  - get_evidence_for_target(ensg_id)  → evidence chain scores (genetic, somatic, drugs, lit.)
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_GQL = "https://api.platform.opentargets.org/api/v4/graphql"
_TIMEOUT = 20


async def _gql(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_GQL, json={"query": query, "variables": variables})
        resp.raise_for_status()
        return resp.json().get("data", {})


# ── Gene symbol → Ensembl ID ──────────────────────────────────────────────────

_SEARCH_QUERY = """
query TargetSearch($q: String!) {
  search(queryString: $q, entityNames: ["target"], page: {size: 1, index: 0}) {
    hits {
      id
      object {
        ... on Target {
          id
          approvedSymbol
          approvedName
        }
      }
    }
  }
}
"""


async def get_target_id(gene_symbol: str) -> Optional[str]:
    """Return the Ensembl gene ID (ENSG…) for a HGNC gene symbol."""
    try:
        data = await _gql(_SEARCH_QUERY, {"q": gene_symbol})
        hits = data.get("search", {}).get("hits", [])
        if not hits:
            return None
        return hits[0].get("id")
    except Exception as exc:
        logger.warning("OpenTargets search failed for %s: %s", gene_symbol, exc)
        return None


# ── Drugs for target ──────────────────────────────────────────────────────────

_DRUGS_QUERY = """
query DrugsForTarget($ensgId: String!, $size: Int!) {
  target(ensemblId: $ensgId) {
    id
    approvedSymbol
    knownDrugs(size: $size) {
      count
      rows {
        drug {
          id
          name
          isApproved
          maximumClinicalTrialPhase
          description
          mechanismsOfAction {
            rows {
              mechanismOfAction
              actionType
            }
          }
        }
        approvedIndications
        phase
        status
        disease {
          id
          name
        }
        datasourceScore
      }
    }
  }
}
"""


async def get_drugs_for_target(ensg_id: str, max_drugs: int = 20) -> list[dict]:
    """Return drugs associated with a target gene.

    Each item contains:
      chembl_id, drug_name, is_approved, max_phase, mechanism,
      action_type, indication, phase, status, disease_name, opentargets_score
    """
    try:
        data = await _gql(_DRUGS_QUERY, {"ensgId": ensg_id, "size": max_drugs})
        target = data.get("target")
        if not target:
            return []

        rows = target.get("knownDrugs", {}).get("rows", [])
        result = []
        for row in rows:
            drug = row.get("drug", {})
            moa_rows = drug.get("mechanismsOfAction", {}).get("rows", [])
            mechanism = moa_rows[0].get("mechanismOfAction") if moa_rows else None
            action_type = moa_rows[0].get("actionType") if moa_rows else None
            disease = row.get("disease") or {}

            result.append(
                {
                    "chembl_id": drug.get("id"),
                    "drug_name": drug.get("name"),
                    "is_approved": drug.get("isApproved", False),
                    "max_phase": drug.get("maximumClinicalTrialPhase", 0),
                    "description": drug.get("description"),
                    "mechanism": mechanism,
                    "action_type": action_type,
                    "approved_indications": row.get("approvedIndications") or [],
                    "phase": row.get("phase", 0),
                    "status": row.get("status"),
                    "disease_name": disease.get("name"),
                    "opentargets_score": float(row.get("datasourceScore") or 0),
                }
            )
        return result
    except Exception as exc:
        logger.warning("OpenTargets drugs query failed for %s: %s", ensg_id, exc)
        return []


# ── Evidence chain scores ─────────────────────────────────────────────────────

_EVIDENCE_QUERY = """
query EvidenceScores($ensgId: String!) {
  target(ensemblId: $ensgId) {
    associatedDiseases(page: {size: 5, index: 0}) {
      rows {
        disease { id name }
        score
        datatypeScores {
          componentId
          score
        }
      }
    }
  }
}
"""


async def get_evidence_scores(ensg_id: str) -> list[dict]:
    """Return top associated diseases with evidence scores broken down by datatype."""
    try:
        data = await _gql(_EVIDENCE_QUERY, {"ensgId": ensg_id})
        rows = (
            data.get("target", {})
            .get("associatedDiseases", {})
            .get("rows", [])
        )
        return [
            {
                "disease_id": r["disease"]["id"],
                "disease_name": r["disease"]["name"],
                "overall_score": r["score"],
                "datatype_scores": {
                    d["componentId"]: d["score"]
                    for d in r.get("datatypeScores", [])
                },
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("OpenTargets evidence query failed for %s: %s", ensg_id, exc)
        return []
