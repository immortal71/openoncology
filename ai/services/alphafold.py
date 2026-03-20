"""AlphaFold Server API client.

Public API (four functions):
  get_uniprot_sequence(gene_name)               → str           (raises ValueError if not found)
  apply_mutation(sequence, hgvs)                → str           (returns unchanged seq for unknown notation)
  fold_sequence(sequence, submission_id, gene)  → str | None    (MinIO key for .cif)
  cif_to_pdb(cif_bytes, submission_id, gene)    → str | None    (MinIO key for .pdb)

Workflow inside the AI worker:
  1. get_uniprot_sequence("EGFR")              → canonical protein sequence
  2. apply_mutation(seq, "p.L858R")            → mutated sequence
  3. fold_sequence(mutated_seq, sid, gene)     → MinIO path for .cif
  4. s3.get_object(Bucket=..., Key=cif_path)["Body"].read()  → raw .cif bytes
  5. cif_to_pdb(cif_bytes, sid, gene)          → MinIO path for .pdb
  6. Pass PDB MinIO path to DiffDock

fold_sequence and cif_to_pdb return None on any failure so DiffDock
can fall back to the EBI pre-computed wild-type structure.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BUCKET = "openoncology-vcf"
UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/search"
ALPHAFOLD_URL = "https://alphafoldserver.com/api"
_POLL_INTERVAL = 30   # seconds between polls
_MAX_POLLS = 60       # 30 min maximum


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


# ── 3. Fold sequence via AlphaFold Server ────────────────────────────────────

async def fold_sequence(sequence: str, submission_id: str, gene: str) -> Optional[str]:
    """Submit *sequence* to AlphaFold Server, poll until done, save .cif to MinIO.

    POST https://alphafoldserver.com/api/fold
    Body: {"sequences": [{"proteinChain": {"sequence": ..., "count": 1}}]}

    Polls GET /api/fold/{job_id} every 30 s.  When status is "done" reads
    data["cifContent"] (base64-encoded or raw CIF text) and stores it at:
      structures/{submission_id}/{gene}.cif  in bucket BUCKET.

    Returns the MinIO key on success, or None on any failure.
    """
    payload = {
        "name": f"{gene}_{submission_id}"[:50],
        "modelSeeds": [],
        "sequences": [
            {"proteinChain": {"sequence": sequence, "count": 1}}
        ],
    }

    # ── Submit job ────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ALPHAFOLD_URL}/fold",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code in (401, 403):
                logger.warning("[alphafold] Server requires auth — skipping AlphaFold")
                return None
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("jobId") or data.get("id")
            if not job_id:
                logger.warning("[alphafold] No job ID in response: %s", data)
                return None
            logger.info("[alphafold] Job submitted: %s", job_id)
    except Exception as exc:
        logger.warning("[alphafold] Submission failed: %s", exc)
        return None

    # ── Poll until done ───────────────────────────────────────────────────
    cif_content: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for _ in range(_MAX_POLLS):
                await asyncio.sleep(_POLL_INTERVAL)
                try:
                    resp = await client.get(f"{ALPHAFOLD_URL}/fold/{job_id}")
                    resp.raise_for_status()
                    data = resp.json()
                    status = (data.get("status") or "").lower()
                    logger.debug("[alphafold] Job %s status: %s", job_id, status)
                    if status in ("done", "complete", "completed"):
                        cif_content = data.get("cifContent")
                        break
                    if status in ("error", "failed", "cancelled"):
                        logger.warning("[alphafold] Job %s ended with status: %s", job_id, status)
                        return None
                except Exception as poll_exc:
                    logger.warning("[alphafold] Poll error for %s: %s", job_id, poll_exc)
            else:
                logger.warning("[alphafold] Job %s timed out after %d polls", job_id, _MAX_POLLS)
                return None
    except Exception as exc:
        logger.warning("[alphafold] Polling loop failed: %s", exc)
        return None

    if not cif_content:
        logger.warning("[alphafold] No cifContent in response for job %s", job_id)
        return None

    # ── Upload CIF to MinIO ───────────────────────────────────────────────
    try:
        try:
            cif_bytes = base64.b64decode(cif_content)
        except Exception:
            cif_bytes = cif_content.encode("utf-8")
        minio_key = f"structures/{submission_id}/{gene}.cif"
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=BUCKET,
            Key=minio_key,
            Body=io.BytesIO(cif_bytes),
            ContentType="chemical/x-cif",
            ServerSideEncryption="AES256",
        )
        logger.info("[alphafold] CIF saved to MinIO: %s", minio_key)
        return minio_key
    except Exception as exc:
        logger.warning("[alphafold] MinIO upload failed: %s", exc)
        return None


# ── 4. CIF → PDB conversion ──────────────────────────────────────────────────

def cif_to_pdb(cif_bytes: bytes, submission_id: str, gene: str) -> Optional[str]:
    """Convert raw *cif_bytes* to PDB format via BioPython and upload to MinIO.

    Uploads to structures/{submission_id}/{gene}.pdb in bucket BUCKET.
    Returns the MinIO key on success, or None on any failure.
    """
    try:
        from Bio.PDB import MMCIFParser, PDBIO
    except ImportError:
        logger.warning("[alphafold] biopython not installed — cannot convert CIF to PDB")
        return None

    pdb_key = f"structures/{submission_id}/{gene}.pdb"
    with tempfile.TemporaryDirectory(prefix="alphafold_") as tmpdir:
        cif_local = Path(tmpdir) / f"{gene}.cif"
        pdb_local = Path(tmpdir) / f"{gene}.pdb"

        cif_local.write_bytes(cif_bytes)
        try:
            parser = MMCIFParser(QUIET=True)
            structure = parser.get_structure("protein", str(cif_local))
            io_writer = PDBIO()
            io_writer.set_structure(structure)
            io_writer.save(str(pdb_local))
        except Exception as exc:
            logger.warning("[alphafold] CIF→PDB conversion failed: %s", exc)
            return None

        try:
            pdb_data = pdb_local.read_bytes()
            s3 = _get_s3_client()
            s3.put_object(
                Bucket=BUCKET,
                Key=pdb_key,
                Body=io.BytesIO(pdb_data),
                ContentType="chemical/x-pdb",
                ServerSideEncryption="AES256",
            )
            logger.info("[alphafold] PDB saved to MinIO: %s", pdb_key)
            return pdb_key
        except Exception as exc:
            logger.warning("[alphafold] PDB upload failed: %s", exc)
            return None
