"""
DiffDock binding affinity scorer.

DiffDock (Corso et al., ICLR 2023) is a diffusion-based molecular docking model
that predicts protein-ligand binding poses and confidence scores.

GitHub: https://github.com/gcorso/DiffDock

Integration strategy:
  1. Accept a UniProt accession (protein) + SMILES string (ligand).
  2. Prepare inputs: fetch AlphaFold PDB + convert SMILES → SDF.
  3. Run DiffDock as a subprocess (must be installed separately).
  4. Parse the output confidence score from DiffDock's results CSV.
  5. Return a normalised score in [0, 1] (1 = high binding confidence).

Prerequisites (not installed by default — install per DiffDock README):
  - DiffDock cloned to DIFFDOCK_DIR (default: ai/diffdock/DiffDock/)
  - Its Python environment activated, or diffdock_python pointing to it
  - RDKit for SMILES → SDF conversion

If DiffDock is not available, returns None gracefully so the rest of the
pipeline continues with OpenTargets scores only.
"""

from __future__ import annotations

import csv
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ai.diffdock.prepare_inputs import fetch_protein_pdb, smiles_to_sdf

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DIFFDOCK_DIR = Path(os.environ.get("DIFFDOCK_DIR", _REPO_ROOT / "ai" / "diffdock" / "DiffDock"))
DIFFDOCK_PYTHON = Path(os.environ.get("DIFFDOCK_PYTHON", "python"))  # override for venv


def score_binding(
    uniprot_id: str,
    smiles: str,
    chembl_id: str,
    samples: int = 10,
    pre_folded_cif: Optional[Path] = None,
) -> Optional[float]:
    """Run DiffDock and return a normalised binding confidence in [0, 1].

    Args:
        uniprot_id: UniProt accession for the target protein.
        smiles: SMILES string of the ligand molecule.
        chembl_id: ChEMBL ID used for naming temp files.
        samples: Number of DiffDock sampling poses (higher = more accurate, slower).
        pre_folded_cif: Optional .cif file from AlphaFold Server for the *mutated*
                        protein.  When provided, this structure is used instead of
                        the generic EBI pre-computed PDB — giving mutation-specific
                        binding scores.

    Returns:
        Normalised confidence score (0–1), or None if DiffDock unavailable.
    """
    if not DIFFDOCK_DIR.exists():
        logger.warning(
            "DiffDock not found at %s. Set DIFFDOCK_DIR env var or clone repo. "
            "Binding scores will be unavailable.",
            DIFFDOCK_DIR,
        )
        return None

    with tempfile.TemporaryDirectory(prefix="diffdock_") as tmpdir:
        tmp = Path(tmpdir)

        # Prepare inputs — prefer mutated structure from AlphaFold Server
        if pre_folded_cif is not None and pre_folded_cif.exists():
            from ai.diffdock.prepare_inputs import cif_to_pdb
            pdb_path = cif_to_pdb(pre_folded_cif, tmp)
            if pdb_path is None:
                logger.warning("CIF→PDB failed, falling back to EBI structure for %s", uniprot_id)
                pdb_path = fetch_protein_pdb(uniprot_id, tmp)
        else:
            pdb_path = fetch_protein_pdb(uniprot_id, tmp)

        sdf_path = smiles_to_sdf(smiles, chembl_id, tmp)

        if pdb_path is None or sdf_path is None:
            logger.warning("Could not prepare inputs for DiffDock (%s / %s)", uniprot_id, chembl_id)
            return None

        out_dir = tmp / "output"
        out_dir.mkdir()

        cmd = [
            str(DIFFDOCK_PYTHON),
            str(DIFFDOCK_DIR / "inference.py"),
            "--protein_path", str(pdb_path),
            "--ligand", str(sdf_path),
            "--out_dir", str(out_dir),
            "--samples_per_complex", str(samples),
            "--batch_size", "6",
            "--no_final_step_noise",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout per complex
                cwd=str(DIFFDOCK_DIR),
            )
        except subprocess.TimeoutExpired:
            logger.warning("DiffDock timed out for %s / %s", uniprot_id, chembl_id)
            return None
        except Exception as exc:
            logger.warning("DiffDock subprocess error: %s", exc)
            return None

        if result.returncode != 0:
            logger.warning("DiffDock failed (rc=%d): %s", result.returncode, result.stderr[:500])
            return None

        return _parse_confidence(out_dir)


def _parse_confidence(out_dir: Path) -> Optional[float]:
    """Parse the best confidence score from DiffDock output directory.

    DiffDock names output files like:
      rank1_confidence-1.234.sdf
      rank2_confidence-0.876.sdf

    The confidence score is the value after "confidence".
    We take the rank-1 (best pose) confidence and normalise it to [0, 1]
    using a sigmoid with centre 0 and scale 2.
    """
    import math

    best_conf: Optional[float] = None

    for sdf_file in out_dir.rglob("rank1_confidence*.sdf"):
        # Extract float from filename e.g. "rank1_confidence-1.23.sdf" → -1.23
        stem = sdf_file.stem  # "rank1_confidence-1.23"
        try:
            conf_str = stem.split("confidence")[1]
            conf = float(conf_str)
            best_conf = conf
            break
        except (IndexError, ValueError):
            continue

    if best_conf is None:
        logger.warning("Could not parse DiffDock confidence from %s", out_dir)
        return None

    # Normalise: sigmoid(x/2) maps [-3..3] → [0.18..0.82], centred at 0.5
    normalised = 1.0 / (1.0 + math.exp(-best_conf / 2.0))
    return round(normalised, 4)
