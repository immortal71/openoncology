"""cBioPortal public REST API client.

cBioPortal for Cancer Genomics (cbioportal.org) aggregates large-scale cancer
genomic datasets including TCGA, ICGC, and institutional studies.  It exposes a
fully public REST API — no authentication required.

Docs: https://www.cbioportal.org/api/swagger-ui/index.html#/

This service enriches a patient mutation with population-level data:
  - How frequently this gene/mutation appears across cBioPortal study cohorts
  - Which cancer types most commonly carry muttions in this gene
  - Survival statistics from matched cohorts (where available)
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_API = "https://www.cbioportal.org/api"
_TIMEOUT = 20.0


async def get_gene_panel_data(gene: str) -> list[dict]:
    """Return a summary of mutation frequency for *gene* across all cBioPortal studies.

    Returns a list of dicts, each representing one cancer study where the gene
    was profiled, containing:
      - study_id      : cBioPortal study identifier
      - cancer_type   : human-readable cancer type
      - mutation_freq : fraction of profiled samples that carry any mutation in gene
      - sample_count  : number of samples in study
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # Resolve Hugo gene symbol to Entrez ID
            gene_resp = await client.get(
                f"{_API}/genes/{gene.upper()}",
                headers={"Accept": "application/json"},
            )
            if gene_resp.status_code == 404:
                logger.debug("[cbioportal] Gene %s not found", gene)
                return []
            gene_resp.raise_for_status()
            entrez_id = gene_resp.json().get("entrezGeneId")
            if not entrez_id:
                return []

            # Fetch mutation counts across studies
            # We query the molecular profiles endpoint for mutation data
            # and use the gene-panel-data endpoint
            profiles_resp = await client.post(
                f"{_API}/molecular-profiles/fetch",
                json={"molecularAlterationType": "MUTATION_EXTENDED"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            profiles_resp.raise_for_status()
            profiles = profiles_resp.json()[:30]  # cap at 30 studies for speed

            results = []
            for profile in profiles:
                study_id = profile.get("studyId")
                profile_id = profile.get("molecularProfileId")
                cancer_type = profile.get("study", {}).get("cancerTypeId", study_id)
                if not profile_id:
                    continue
                try:
                    counts_resp = await client.post(
                        f"{_API}/molecular-profiles/{profile_id}/mutation-counts-by-gene/fetch",
                        json={"entrezGeneIds": [entrez_id]},
                        headers={"Accept": "application/json", "Content-Type": "application/json"},
                        timeout=8,
                    )
                    counts_resp.raise_for_status()
                    counts = counts_resp.json()
                    if counts:
                        c = counts[0]
                        results.append({
                            "study_id": study_id,
                            "cancer_type": cancer_type,
                            "mutation_count": c.get("mutationCount", 0),
                            "profile_id": profile_id,
                        })
                except Exception:
                    continue  # skip individual study errors

            return results
    except Exception as exc:
        logger.warning("[cbioportal] Gene panel data failed for %s: %s", gene, exc)
        return []


async def get_mutations_in_gene(gene: str, study_id: str = "tcga_pan_can_atlas_2018") -> list[dict]:
    """Fetch individual mutation records for *gene* in a cBioPortal study.

    Default study is the TCGA PanCancer Atlas 2018 (pan-cancer, ~10k samples).
    Returns up to 100 mutation records with:
      - sample_id, protein_change, mutation_type, chromosome, start_position
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # Resolve gene
            gene_resp = await client.get(
                f"{_API}/genes/{gene.upper()}",
                headers={"Accept": "application/json"},
            )
            if gene_resp.status_code == 404:
                return []
            gene_resp.raise_for_status()
            entrez_id = gene_resp.json().get("entrezGeneId")
            if not entrez_id:
                return []

            profile_id = f"{study_id}_mutations"
            mutations_resp = await client.post(
                f"{_API}/molecular-profiles/{profile_id}/mutations/fetch",
                json={"entrezGeneIds": [entrez_id]},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                params={"pageSize": 100, "pageNumber": 0},
            )
            if mutations_resp.status_code == 404:
                return []
            mutations_resp.raise_for_status()
            raw = mutations_resp.json()
            return [
                {
                    "sample_id": m.get("sampleId"),
                    "protein_change": m.get("proteinChange"),
                    "mutation_type": m.get("mutationType"),
                    "chromosome": m.get("chr"),
                    "start_position": m.get("startPosition"),
                }
                for m in raw
            ]
    except Exception as exc:
        logger.warning("[cbioportal] Mutations fetch failed for %s/%s: %s", gene, study_id, exc)
        return []


async def get_cancer_studies() -> list[dict]:
    """Return the list of all publicly available cBioPortal cancer studies."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_API}/studies",
                params={"projection": "SUMMARY", "pageSize": 500},
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return [
                {
                    "study_id": s.get("studyId"),
                    "name": s.get("name"),
                    "cancer_type": s.get("cancerTypeId"),
                    "sample_count": s.get("allSampleCount", 0),
                }
                for s in resp.json()
            ]
    except Exception as exc:
        logger.warning("[cbioportal] Studies list failed: %s", exc)
        return []
