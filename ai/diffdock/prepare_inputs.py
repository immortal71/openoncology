"""
Input preparation for DiffDock:
  1. Fetch AlphaFold PDB for a given UniProt ID.
  2. Convert a SMILES string to SDF via RDKit.

Both outputs are written to a temp directory so DiffDock can read them.
"""

from __future__ import annotations

import logging
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ALPHAFOLD_URL = "https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb"


def fetch_protein_pdb(uniprot_id: str, dest_dir: Path) -> Optional[Path]:
    """Download the AlphaFold predicted structure for a UniProt accession.

    Returns the path to the saved .pdb file, or None on failure.
    """
    url = _ALPHAFOLD_URL.format(uniprot_id=uniprot_id)
    pdb_path = dest_dir / f"{uniprot_id}.pdb"

    if pdb_path.exists():
        return pdb_path

    try:
        logger.info("Fetching AlphaFold PDB for %s", uniprot_id)
        urllib.request.urlretrieve(url, pdb_path)
        return pdb_path
    except Exception as exc:
        logger.warning("Could not fetch PDB for %s: %s", uniprot_id, exc)
        return None


def smiles_to_sdf(smiles: str, chembl_id: str, dest_dir: Path) -> Optional[Path]:
    """Convert a SMILES string to a 3D SDF file using RDKit.

    Returns the path to the SDF file, or None if RDKit is not installed
    or 3D embedding fails.
    """
    sdf_path = dest_dir / f"{chembl_id}.sdf"
    if sdf_path.exists():
        return sdf_path

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            logger.warning("RDKit could not parse SMILES for %s", chembl_id)
            return None

        mol = Chem.AddHs(mol)
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        if result != 0:
            logger.warning("3D embedding failed for %s", chembl_id)
            return None

        AllChem.MMFFOptimizeMolecule(mol)
        writer = Chem.SDWriter(str(sdf_path))
        writer.write(mol)
        writer.close()
        return sdf_path

    except ImportError:
        logger.warning("RDKit not installed — cannot convert SMILES to SDF for %s", chembl_id)
        return None
    except Exception as exc:
        logger.warning("SMILES→SDF conversion failed for %s: %s", chembl_id, exc)
        return None


def cif_to_pdb(cif_path: Path, dest_dir: Path) -> Optional[Path]:
    """Convert an mmCIF structure file to PDB format for DiffDock.

    Requires BioPython (pip install biopython). Falls back gracefully
    when BioPython is not installed.

    Returns path to the .pdb file, or None on failure.
    """
    pdb_path = dest_dir / cif_path.with_suffix(".pdb").name
    if pdb_path.exists():
        return pdb_path
    try:
        from Bio.PDB import MMCIFParser, PDBIO

        parser = MMCIFParser(QUIET=True)
        structure = parser.get_structure("protein", str(cif_path))
        io = PDBIO()
        io.set_structure(structure)
        io.save(str(pdb_path))
        logger.info("Converted %s → %s", cif_path.name, pdb_path.name)
        return pdb_path
    except ImportError:
        logger.warning("BioPython not installed — cannot convert .cif to .pdb")
        return None
    except Exception as exc:
        logger.warning("CIF→PDB conversion failed: %s", exc)
        return None
