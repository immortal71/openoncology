"""AlphaFold Protein Structure Database client.

Public API (three functions):
  get_uniprot_sequence(gene_name)                        → str         (raises ValueError if not found)
  apply_mutation(sequence, hgvs)                         → str         (returns unchanged seq for unknown notation)
  fetch_reference_structure(uniprot_id, sid, gene)       → str | None  (MinIO key for .pdb)

Workflow inside the AI worker:
  1. _gene_to_uniprot("EGFR")                        → P00533
  2. fetch_reference_structure("P00533", sid, "EGFR") → MinIO path for .pdb
  3. Pass PDB MinIO path to DiffDock

THE STRUCTURES THIS RETURNS ARE WILD-TYPE, NOT MUTATION-SPECIFIC.

AlphaFold DB serves one pre-computed prediction per UniProt accession: the
canonical sequence, folded once, with no variant applied. Folding a mutated
sequence needs AlphaFold 3 inference, which this module does not do and this
repository has never done. Two routes exist and neither is wired here:

  - AlphaFold Server (alphafoldserver.com) has no public submission API, issues
    no API keys, and its output terms forbid use "in connection with any
    automated system that predicts the binding or interaction of the protein
    with ligands or peptides, including, but not limited to, Glide or AutoDock".
    Feeding its output to DiffDock is that prohibited use, so this module does
    not call it. An earlier version of this file POSTed to an invented
    /api/fold endpoint behind an ALPHAFOLD_API_KEY that could never be issued;
    it returned None on every call and DiffDock silently fell back to the EBI
    structure, which is what the pipeline has always actually scored against.

  - Self-hosted AlphaFold 3 (google-deepmind/alphafold3) carries no docking
    restriction but is non-commercial-only and needs approved weights plus GPU
    inference. That is the route to real mutant structures; see BACKLOG.md.

apply_mutation is kept because sequence-level mutant output is still used for
reporting, not because anything folds its result.

fetch_reference_structure returns None on any failure, so DiffDock falls back
to fetching the same EBI structure itself (ai/diffdock/prepare_inputs.py).
"""
from __future__ import annotations

import io
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BUCKET = "openoncology-vcf"
UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/search"
AFDB_PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"


def _get_s3_client():
    """Return a boto3 S3 client via the shared helper in api/services/storage.py."""
    _api_dir = Path(__file__).resolve().parents[2] / "api"
    if str(_api_dir) not in sys.path:
        sys.path.insert(0, str(_api_dir))
    from services.storage import _get_s3  # type: ignore
    return _get_s3()


# ── 1. UniProt sequence lookup ───────────────────────────────────────────────

async def get_uniprot_sequence(gene_name: str) -> str:
    """Fetch the canonical human protein sequence for *gene_name* from UniProt.

    Raises ValueError if no reviewed entry is found for the gene.
    """
    params = {
        "query": f"gene:{gene_name} AND organism_id:9606 AND reviewed:true",
        "fields": "sequence",
        "format": "json",
        "size": "1",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(UNIPROT_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        if not results:
            raise ValueError(f"No UniProt entry for gene {gene_name!r}")
        seq = results[0]["sequence"]["value"]
        logger.info("[alphafold] UniProt sequence for %s: %d aa", gene_name, len(seq))
        return seq


# ── 2. Mutation application ──────────────────────────────────────────────────

def apply_mutation(sequence: str, hgvs: str) -> str:
    """Apply an HGVS protein-level mutation to *sequence*.

    Supported notations (p. prefix is optional):
      Substitution:  p.V600E   or  p.Val600Glu
      Deletion:      p.E746_A750del

    Returns the mutated sequence on success, or the UNCHANGED sequence for
    unrecognised notations (never raises).
    """
    _AA3 = {
        "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
        "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
        "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
        "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
        "Ter": "*",
    }
    variant = re.sub(r"^[pP]\.", "", hgvs)

    def to1(aa: str) -> str:
        if len(aa) == 1:
            return aa.upper()
        return _AA3.get(aa[:1].upper() + aa[1:].lower(), aa[0].upper())

    # ── Substitution: V600E or Val600Glu ──────────────────────────────────
    m = re.match(r"^([A-Za-z]{1,3})(\d+)([A-Za-z]{1,3}|\*)$", variant)
    if m:
        pos = int(m.group(2))
        alt_aa = to1(m.group(3))
        idx = pos - 1
        if 0 <= idx < len(sequence):
            seq_list = list(sequence)
            seq_list[idx] = alt_aa
            return "".join(seq_list)
        logger.warning("[alphafold] Substitution pos %d out of range (len=%d)", pos, len(sequence))
        return sequence

    # ── Deletion range: E746_A750del ───────────────────────────────────────
    m = re.match(r"^[A-Za-z]{1,3}(\d+)_[A-Za-z]{1,3}(\d+)del$", variant)
    if m:
        start_idx = int(m.group(1)) - 1
        end_idx = int(m.group(2))
        if 0 <= start_idx and end_idx <= len(sequence):
            return sequence[:start_idx] + sequence[end_idx:]
        logger.warning("[alphafold] Deletion %d–%d out of range (len=%d)",
                       start_idx + 1, end_idx, len(sequence))
        return sequence

    logger.warning("[alphafold] Unrecognised mutation notation: %s — returning unchanged sequence", hgvs)
    return sequence


# ── 3. Reference structure from AlphaFold DB ─────────────────────────────────

async def fetch_reference_structure(
    uniprot_id: str, submission_id: str, gene: str
) -> Optional[str]:
    """Download the AlphaFold DB structure for *uniprot_id* and store it in MinIO.

    Queries the prediction API for the current pdbUrl rather than guessing a
    model version suffix, for the reason given in
    ai/diffdock/prepare_inputs.py: AlphaFold DB reprocesses entries under new
    versions and a hardcoded _v4 would silently 404 forever.

    The structure is wild-type. See the module docstring.

    Saves to structures/{submission_id}/{gene}.pdb in bucket BUCKET and returns
    the key, or None on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(AFDB_PREDICTION_URL.format(uniprot_id=uniprot_id))
            if resp.status_code in (400, 404):
                logger.info(
                    "[alphafold] No AlphaFold DB entry for %s (HTTP %d)",
                    uniprot_id,
                    resp.status_code,
                )
                return None
            resp.raise_for_status()
            entries = resp.json()
            if not entries:
                logger.info("[alphafold] No AlphaFold DB entry for %s", uniprot_id)
                return None

            pdb_url = entries[0]["pdbUrl"]
            logger.info("[alphafold] Fetching %s structure: %s", gene, pdb_url)
            pdb_resp = await client.get(pdb_url)
            pdb_resp.raise_for_status()
            pdb_bytes = pdb_resp.content
    except Exception as exc:
        logger.warning("[alphafold] AlphaFold DB fetch failed for %s: %s", uniprot_id, exc)
        return None

    try:
        minio_key = f"structures/{submission_id}/{gene}.pdb"
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=BUCKET,
            Key=minio_key,
            Body=io.BytesIO(pdb_bytes),
            ContentType="chemical/x-pdb",
            ServerSideEncryption="AES256",
        )
        logger.info("[alphafold] PDB saved to MinIO: %s", minio_key)
        return minio_key
    except Exception as exc:
        logger.warning("[alphafold] MinIO upload failed: %s", exc)
        return None
