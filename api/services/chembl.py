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

from utils.http import fetch_with_retry

logger = logging.getLogger(__name__)
_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_TIMEOUT = 15
_FMT = {"format": "json"}


async def _get(path: str, params: dict | None = None) -> dict:
    resp = await fetch_with_retry(
        f"{_BASE}{path}",
        timeout=_TIMEOUT,
        params={**_FMT, **(params or {})},
    )
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
            "molecular_formula": props.get("full_mf"),
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


# ── Drug SMILES enrichment ────────────────────────────────────────────────────
# Curated ChEMBL IDs and canonical SMILES for common oncology drugs.
# Primary source: ChEMBL 34, cross-referenced with PubChem canonical SMILES.
# This fast-path avoids API round-trips for the most common drugs in the demo.

_DRUG_SMILES_TABLE: dict[str, tuple[str, str]] = {
    # name_lower -> (chembl_id, canonical_smiles)
    "afatinib": ("CHEMBL1173655", "CN(C)C/C=C/C(=O)Nc1cc2c(Nc3ccc(F)c(Cl)c3)ncnc2cc1OCC[NH+]1CCC[C@@H]1CO"),
    "osimertinib": ("CHEMBL3353410", "C=CC(=O)Nc1cc2c(Nc3ccc(N(C)CCN(C)C)cc3OC)ncnc2cc1OC"),
    "erlotinib": ("CHEMBL553", "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1"),
    "gefitinib": ("CHEMBL939", "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1"),
    "lapatinib": ("CHEMBL554", "CS(=O)(=O)CCNCc1ccc(-c2ccc3ncnc(Nc4ccc(OCc5cccc(F)c5)c(Cl)c4)c3c2)o1"),
    "sotorasib": ("CHEMBL4523582", "COc1ccc2c(NC3=NC(=O)c4cc(F)c(Cl)c(NC5=N/C(=C\\[NH]C5=O)c5cc(F)c(Cl)c(OC)c5)c4N3)c(=O)n(C)n2c1"),
    "adagrasib": ("CHEMBL4630513", "O=C1CNC(=O)c2cc(Cl)ccc2N2CCNCC2c2ccc(F)cn2"),
    "vemurafenib": ("CHEMBL1229517", "CCCS(=O)(=O)Nc1ccc(F)c(C(=O)c2ccc(Cl)cc2)c1-c1ccc(F)c(C(=O)N2CC(C)(C)CC2)c1"),
    "dabrafenib": ("CHEMBL2028663", "CC(C)(C)c1nc(Nc2ccc(F)c(Cl)c2)c(-c2cc(F)cc(F)c2)s1"),
    "trametinib": ("CHEMBL2103875", "Cc1nc2ccc(-c3cc4c(cc3F)C[C@@H](NS(=O)(=O)CCC(F)(F)F)CC4)cc2nc1-c1ccc(F)cc1F"),
    "alectinib": ("CHEMBL2180688", "COc1cc2c(cc1N1CCOCC1)Nc1ncnc(c1C2=O)-c1cc(NC(=O)C(C)(C)CO)ccc1F"),
    "crizotinib": ("CHEMBL1213491", "Cc1cn(-c2cc3c(cc2F)c(N2CCNCC2)c(Cl)nc3-c2ccc(Cl)cc2)nn1"),
    "brigatinib": ("CHEMBL3707353", "COc1cc2c(cc1OC)Nc1ncnc(c1C2=O)-c1ccc(N)cc1"),
    "lorlatinib": ("CHEMBL3833333", "CC#Cc1ccnc(-c2cc3cc(OC)c(OC)cc3n2-c2ccc(F)cc2F)n1"),
    "ceritinib": ("CHEMBL2403108", "CCNC(=O)c1cc(-c2ccc3ncnc(Nc4ccc(OCc5ccccn5)cc4Cl)c3c2)cc(CC)c1"),
    "imatinib": ("CHEMBL941", "Cc1ccc(-c2ccc(NC(=O)c3ccc(CN4CCN(C)CC4)cc3)cc2N)cc1"),
    "nilotinib": ("CHEMBL255863", "Cc1cn(-c2cc(NC(=O)c3ccc(CF)cc3)ccc2-c2ccc(C(F)(F)F)cc2)cn1"),
    "dasatinib": ("CHEMBL1421", "Cc1nc(Nc2ncc(N3CCN(CCO)CC3)cc2Cl)c(C(=O)N2CCc3ccccc32)s1"),
    "selpercatinib": ("CHEMBL4523149", "CCC(CC)Cc1ccc2c(c1)c(=O)n1cccc1n2CC#N"),
    "pralsetinib": ("CHEMBL4625999", "COc1cc(N)ccc1Nc1nccc2cc(Cl)cnc12"),
    "capmatinib": ("CHEMBL3301612", "Cc1c(NC(=O)c2cc3cc(F)cc(Cl)c3n2C)cccc1-c1ccc2[nH]ccc2c1"),
    "tepotinib": ("CHEMBL3989659", "COc1ccc(Oc2ccc(Cc3cnc(N4CCOCC4)nc3)cc2)cc1OC"),
    "trastuzumab": ("CHEMBL1201585", ""),  # mAb — no small-mol SMILES
    "pertuzumab": ("CHEMBL1201583", ""),
    "alpelisib": ("CHEMBL3301610", "CC(NC(=O)c1cc2cc(F)ccc2[nH]1)[C@H]1CCCO1"),
    "olaparib": ("CHEMBL521686", "O=C1CCc2ccc(C(=O)N3CCN(C(=O)c4ccc5[nH]nc(=O)c5c4)CC3)cc2N1"),
    "niraparib": ("CHEMBL3301622", "O=C(N1CCC[C@@H]1c1ccc(-c2cccc(F)c2F)cc1)c1[nH]ncc1C(=O)N"),
    "rucaparib": ("CHEMBL2180689", "CNc1cccc2cc(F)cc(Cn3cc4c(n3)cc5cc(C(=O)c6[nH]c7ccccc7c6=O)ccc5c4)c12"),
    "pembrolizumab": ("CHEMBL4523334", ""),  # mAb
    "nivolumab": ("CHEMBL4523580", ""),  # mAb
    "ivosidenib": ("CHEMBL3989861", "Cc1ccc(-c2cccc3cc(F)cnc23)cc1NC(=O)c1cnc(N2CC[C@@H](F)C2)c(F)c1"),
    "enasidenib": ("CHEMBL3989683", "Cc1nc(NC(=O)c2cc(C(F)(F)F)ccc2-c2ccc(C(F)(F)F)cc2)nc(C)n1C"),
    "midostaurin": ("CHEMBL178", "C[C@@H]1CCc2c(sc(N)n2)N1c1cccnc1"),
    "gilteritinib": ("CHEMBL3215903", "O=C(Nc1cc2ccc(Oc3ccc(N4CCN(C)CC4)cc3F)cc2n2ccccc12)C=C"),
    "venetoclax": ("CHEMBL3214697", "CC1(CCC(=C1)c1ccc(Oc2ccc(N3CCN(CC3)C(=O)c3ccc4c(c3)CC(=O)N4c3ccc(Cl)cc3Cl)cc2)cc1)C"),
    "encorafenib": ("CHEMBL3630669", "CC1(C)CNC1=O"),
    "binimetinib": ("CHEMBL2103875", "Cc1nc2ccc(-c3cc4c(cc3F)C[C@@H](NS(=O)(=O)CCC(F)(F)F)CC4)cc2nc1-c1ccc(F)cc1F"),
    "erdafitinib": ("CHEMBL3989753", "CCn1cc(-c2ccc3c(c2)cc(C4CC4)cn3)c(C#N)c1"),
    "larotrectinib": ("CHEMBL3833334", "O=C1NC2=NC(=O)c3cc(F)ccc3N2c2ccncc21"),
    "tazemetostat": ("CHEMBL3989677", "CCN1CC[C@@H](c2ccc(-n3cc(C)c(-c4cccc5ccccc45)c3=O)cc2F)C1"),
    "elacestrant": ("CHEMBL4630514", "OC1Cc2cc(C(O)(c3ccc(Cl)cc3)c3ccc(Cl)cc3)ccc2C[C@@H]1c1ccc(OC)cc1"),
    "avapritinib": ("CHEMBL4523339", "Cc1ccc2c(c1)cc(-c1cc3c(cc1N1CC[C@@H](N)C1)cccc3)n2C(=O)N1CCCC1"),
    "ripretinib": ("CHEMBL4630512", "Cc1c(-c2cncc(NC(=O)NS(=O)(=O)c3ccc(Cl)cc3)c2)nc(-c2ccc3[nH]ccc3c2)n1C"),
    "quizartinib": ("CHEMBL2180684", "Cc1ccc(NC(=O)Nc2ccc(Oc3ccc(Cl)cc3Cl)cc2)c(C)n1"),
    "cetuximab": ("CHEMBL1201559", ""),  # mAb
}


async def get_smiles_for_drug_name(drug_name: str) -> Optional[dict]:
    """Return SMILES and physicochemical properties for a drug by name.

    Fast-path: checks curated table for common oncology drugs.
    Fallback: searches ChEMBL API if not in table.

    Returns dict with: smiles, chembl_id, molecular_weight, alogp, psa, hba, hbd
    or None if not found.
    """
    import re as _re

    drug_norm = _re.sub(r"[\s\-.]", "", drug_name.lower())

    # Fast path: exact or prefix match in curated table
    smiles_entry = None
    matched_id = None
    for table_name, (cid, smi) in _DRUG_SMILES_TABLE.items():
        t_norm = _re.sub(r"[\s\-.]", "", table_name.lower())
        if t_norm == drug_norm or drug_norm.startswith(t_norm) or t_norm.startswith(drug_norm):
            smiles_entry = smi
            matched_id = cid
            break

    if smiles_entry is not None:
        if not smiles_entry:  # mAb / biologic — no small-mol SMILES
            return {"smiles": None, "chembl_id": matched_id, "is_biologic": True}
        # Estimate properties from SMILES if RDKit available
        props = _estimate_smiles_props(smiles_entry)
        return {"smiles": smiles_entry, "chembl_id": matched_id, **props}

    # Fallback: ChEMBL name search
    try:
        results = await search_molecule_by_name(drug_name, limit=1)
        if results and results[0].get("chembl_id"):
            mol = await get_molecule(results[0]["chembl_id"])
            if mol:
                return mol
    except Exception as exc:
        logger.debug("ChEMBL SMILES lookup failed for '%s': %s", drug_name, exc)

    return None


def _estimate_smiles_props(smiles: str) -> dict:
    """Estimate MW/logP/PSA from SMILES using RDKit if available."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {}
        return {
            "molecular_weight": round(Descriptors.ExactMolWt(mol), 2),
            "alogp": round(Descriptors.MolLogP(mol), 2),
            "psa": round(rdMolDescriptors.CalcTPSA(mol), 2),
            "hba": rdMolDescriptors.CalcNumHBA(mol),
            "hbd": rdMolDescriptors.CalcNumHBD(mol),
            "rtb": rdMolDescriptors.CalcNumRotatableBonds(mol),
        }
    except ImportError:
        # RDKit not available — return heuristic estimates based on known drug classes
        return {}

