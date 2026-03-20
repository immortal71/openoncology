"""
ChEMBL REST API client.

Docs:     https://www.ebi.ac.uk/chembl/api/data/docs
Base URL: https://www.ebi.ac.uk/chembl/api/data/

Provides:
  - get_molecule(chembl_id)           → SMILES, drug properties, approval status
  - get_mechanisms_for_target(target) → MOA rows for a ChEMBL target ID
  - search_molecule_by_name(name)     → fuzzy name search → ChEMBL IDs
  - get_activities_for_target(target) → bioactivity measurements (IC50, Ki, etc.)
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_TIMEOUT = 15
_FMT = {"format": "json"}


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE}{path}", params={**_FMT, **(params or {})})
        resp.raise_for_status()
        return resp.json()


# ── Single molecule lookup ────────────────────────────────────────────────────

async def get_molecule(chembl_id: str) -> Optional[dict]:
    """Return molecule properties for a ChEMBL compound ID.

    Returns dict with:
      chembl_id, preferred_name, smiles, molecular_formula, molecular_weight,
      max_phase, is_approved, first_approval_year, alogp, hba, hbd, psa, rtb
    Or None if not found.
    """
    try:
        data = await _get(f"/molecule/{chembl_id}")
        props = data.get("molecule_properties") or {}
        struct = data.get("molecule_structures") or {}
        return {
            "chembl_id": data.get("molecule_chembl_id"),
            "preferred_name": data.get("pref_name"),
            "smiles": struct.get("canonical_smiles"),
            "molecular_formula": struct.get("standard_inchi_key"),
            "molecular_weight": props.get("full_mwt"),
            "max_phase": data.get("max_phase", 0),
            "is_approved": data.get("max_phase") == 4,
            "first_approval_year": data.get("first_approval"),
            "alogp": props.get("alogp"),
            "hba": props.get("hba"),
            "hbd": props.get("hbd"),
            "psa": props.get("psa"),
            "rtb": props.get("rtb"),
            # Lipinski rule-of-5 flag
            "ro5_pass": props.get("num_ro5_violations", 1) == 0,
        }
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        logger.warning("ChEMBL molecule lookup failed for %s: %s", chembl_id, exc)
        return None
    except Exception as exc:
        logger.warning("ChEMBL molecule lookup failed for %s: %s", chembl_id, exc)
        return None


# ── Molecule name search ──────────────────────────────────────────────────────

async def search_molecule_by_name(name: str, limit: int = 5) -> list[dict]:
    """Fuzzy search ChEMBL molecules by preferred name.

    Returns a list of (chembl_id, preferred_name, max_phase) dicts.
    """
    try:
        data = await _get("/molecule/search", {"q": name, "limit": limit})
        molecules = data.get("molecules", [])
        return [
            {
                "chembl_id": m.get("molecule_chembl_id"),
                "preferred_name": m.get("pref_name"),
                "max_phase": m.get("max_phase", 0),
            }
            for m in molecules
        ]
    except Exception as exc:
        logger.warning("ChEMBL name search failed for '%s': %s", name, exc)
        return []


# ── Target mechanisms ──────────────────────────────────────────────────────────

async def get_mechanisms_for_target(chembl_target_id: str) -> list[dict]:
    """Return drug mechanisms of action for a ChEMBL target.

    Returns list of dicts: chembl_id, mechanism_of_action, action_type, direct_interaction
    """
    try:
        data = await _get("/mechanism", {"target_chembl_id": chembl_target_id, "limit": 50})
        return [
            {
                "chembl_id": m.get("molecule_chembl_id"),
                "mechanism_of_action": m.get("mechanism_of_action"),
                "action_type": m.get("action_type"),
                "direct_interaction": m.get("direct_interaction", False),
            }
            for m in data.get("mechanisms", [])
        ]
    except Exception as exc:
        logger.warning("ChEMBL mechanism lookup failed for %s: %s", chembl_target_id, exc)
        return []


# ── Bioactivity data ───────────────────────────────────────────────────────────

async def get_activities_for_target(
    chembl_target_id: str,
    standard_type: str = "IC50",
    limit: int = 50,
) -> list[dict]:
    """Return bioactivity measurements (IC50, Ki, Kd, etc.) for a target.

    Returns list of dicts: chembl_id, standard_type, standard_value,
    standard_units, assay_type, pchembl_value
    """
    try:
        data = await _get(
            "/activity",
            {
                "target_chembl_id": chembl_target_id,
                "standard_type": standard_type,
                "limit": limit,
            },
        )
        return [
            {
                "chembl_id": a.get("molecule_chembl_id"),
                "standard_type": a.get("standard_type"),
                "standard_value": a.get("standard_value"),
                "standard_units": a.get("standard_units"),
                "assay_type": a.get("assay_type"),
                "pchembl_value": a.get("pchembl_value"),
            }
            for a in data.get("activities", [])
            if a.get("standard_value") is not None
        ]
    except Exception as exc:
        logger.warning("ChEMBL activities lookup failed for %s: %s", chembl_target_id, exc)
        return []
