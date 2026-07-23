"""
Standalone DiffDock re-scoring runner for the Vultr GPU box.

Reads diffdock_rescoring_inputs.json (produced by
prepare_diffdock_rescoring_inputs.py, run inside the api container),
and for each case:
  1. fetches the current AlphaFold structure via the prediction API
     (same live-metadata approach as ai/diffdock/prepare_inputs.py's fix —
     no hardcoded model version)
  2. converts the case's drug SMILES to a 3D SDF via RDKit
  3. runs DiffDock inference.py with samples_per_complex == batch_size
     (the fix for the uneven-final-batch crash found earlier)
  4. parses the top-ranked pose's confidence score from the output filename
  5. appends the result to an output JSON, checkpointed after every case
     so a ~14-hour run can be resumed if interrupted.

This script is intentionally plain synchronous Python — no async/FastAPI —
so it only needs what's already in the `diffdock` conda env on this box.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DIFFDOCK_DIR = Path("/root/diffdock_work/DiffDock")
INPUT_FILE = Path("/root/diffdock_work/diffdock_rescoring_inputs.json")
OUTPUT_FILE = Path("/root/diffdock_work/diffdock_rescore_results.json")
CROP_DECISIONS_FILE = Path("/root/diffdock_work/crop_decisions.json")
STRUCTURES_DIR = Path("/root/diffdock_work/structures_cache")
CROPPED_STRUCTURES_DIR = Path("/root/diffdock_work/structures_cache_cropped")
LIGANDS_DIR = Path("/root/diffdock_work/ligands_cache")
RUN_DIR = Path("/root/diffdock_work/rescore_runs")

_ALPHAFOLD_PREDICTION_API = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"

STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
CROPPED_STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
LIGANDS_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)

with open(CROP_DECISIONS_FILE) as _f:
    CROP_DECISIONS = json.load(_f)


def crop_pdb_to_region(pdb_path: Path, out_path: Path, start: int, end: int) -> Path:
    with open(pdb_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            if line.startswith(("ATOM", "HETATM")):
                try:
                    resnum = int(line[22:26])
                except ValueError:
                    continue
                if start <= resnum <= end:
                    fout.write(line)
            elif line.startswith(("HEADER", "TITLE", "COMPND")):
                fout.write(line)
    with open(out_path, "a") as fout:
        fout.write("END\n")
    return out_path


def get_dockable_structure(uniprot_id: str) -> tuple[Path | None, str | None]:
    """Returns (path_to_use_for_docking, skip_reason). Exactly one is None."""
    decision = CROP_DECISIONS.get(uniprot_id)
    if decision is None:
        return None, f"no crop decision recorded for {uniprot_id} (not in protein_domain_info.json sweep)"

    if decision["action"] == "skip":
        return None, decision["reason"]

    full_pdb = fetch_protein_pdb(uniprot_id)
    if full_pdb is None:
        return None, "AlphaFold structure fetch failed at run time (was available during the earlier sweep)"

    if decision["action"] == "use_full_length":
        return full_pdb, None

    # action == "crop"
    cropped_path = CROPPED_STRUCTURES_DIR / f"{uniprot_id}_{decision['crop_start']}-{decision['crop_end']}.pdb"
    if not cropped_path.exists():
        crop_pdb_to_region(full_pdb, cropped_path, decision["crop_start"], decision["crop_end"])
    return cropped_path, None


def fetch_protein_pdb(uniprot_id: str) -> Path | None:
    """Same logic as ai/diffdock/prepare_inputs.py's fixed fetch_protein_pdb,
    reimplemented standalone here since this box doesn't have the api/ai
    package installed — kept in sync deliberately, not copy-pasted blindly."""
    pdb_path = STRUCTURES_DIR / f"{uniprot_id}.pdb"
    if pdb_path.exists():
        return pdb_path

    api_url = _ALPHAFOLD_PREDICTION_API.format(uniprot_id=uniprot_id)
    try:
        with urllib.request.urlopen(api_url, timeout=15) as resp:
            entries = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return None
        raise RuntimeError(f"AlphaFold API returned HTTP {exc.code} for {uniprot_id}") from exc

    if not entries:
        return None

    pdb_url = entries[0]["pdbUrl"]
    urllib.request.urlretrieve(pdb_url, pdb_path)
    return pdb_path


def smiles_to_sdf(smiles: str, case_id: str) -> Path | None:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    sdf_path = LIGANDS_DIR / f"{case_id}.sdf"
    if sdf_path.exists():
        return sdf_path

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=42) != 0:
        return None
    AllChem.MMFFOptimizeMolecule(mol)

    writer = Chem.SDWriter(str(sdf_path))
    writer.write(mol)
    writer.close()
    return sdf_path


def parse_top_confidence(out_dir: Path) -> float | None:
    """DiffDock names output files rank1_confidence-X.XX.sdf; rank1.sdf has
    no confidence suffix when it's also the top-confidence pose."""
    for f in out_dir.glob("rank1_confidence*.sdf"):
        m = re.search(r"confidence(-?\d+\.\d+)", f.name)
        if m:
            return float(m.group(1))
    return None


def load_checkpoint() -> dict:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {"results": [], "errors": [], "skipped_by_design": []}


def save_checkpoint(state: dict):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    with open(INPUT_FILE) as f:
        input_data = json.load(f)

    cases = input_data["cases"]
    state = load_checkpoint()
    done_case_ids = (
        {r["case_id"] for r in state["results"]}
        | {e["case_id"] for e in state["errors"]}
        | {s["case_id"] for s in state["skipped_by_design"]}
    )

    remaining = [c for c in cases if c["case_id"] not in done_case_ids]
    print(f"{len(done_case_ids)}/{len(cases)} already done (resuming), {len(remaining)} remaining")

    for i, case in enumerate(remaining):
        case_id = case["case_id"]
        t0 = time.time()
        print(f"[{i+1}/{len(remaining)}] {case_id} ({case['gene']} / {case['drug_name']})")

        try:
            pdb_path, skip_reason = get_dockable_structure(case["uniprot_id"])
            if pdb_path is None:
                state["skipped_by_design"].append({
                    "case_id": case_id,
                    "gene": case["gene"],
                    "uniprot_id": case["uniprot_id"],
                    "reason": skip_reason,
                })
                save_checkpoint(state)
                print(f"  -> skipped: {skip_reason}")
                continue

            sdf_path = smiles_to_sdf(case["smiles"], case_id)
            if sdf_path is None:
                state["errors"].append({"case_id": case_id, "reason": "RDKit could not embed SMILES"})
                save_checkpoint(state)
                continue

            out_dir = RUN_DIR / case_id
            out_dir.mkdir(exist_ok=True)

            cmd = [
                sys.executable, str(DIFFDOCK_DIR / "inference.py"),
                "--protein_path", str(pdb_path),
                "--ligand", str(sdf_path),
                "--out_dir", str(out_dir),
                "--config", str(DIFFDOCK_DIR / "default_inference_args.yaml"),
                "--samples_per_complex", "10",
                "--batch_size", "10",
                "--no_final_step_noise",
            ]
            proc = subprocess.run(cmd, cwd=str(DIFFDOCK_DIR), capture_output=True, text=True, timeout=900)

            # inference.py writes outputs under out_dir/complex_0/
            complex_out = out_dir / "complex_0"
            confidence = parse_top_confidence(complex_out) if complex_out.exists() else None

            elapsed = time.time() - t0
            if confidence is None:
                state["errors"].append({
                    "case_id": case_id,
                    "reason": "DiffDock ran but produced no parseable confidence score",
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-2000:],
                    "elapsed_seconds": elapsed,
                })
            else:
                state["results"].append({
                    "case_id": case_id,
                    "gene": case["gene"],
                    "uniprot_id": case["uniprot_id"],
                    "drug_name": case["drug_name"],
                    "chembl_id": case["chembl_id"],
                    "diffdock_confidence": confidence,
                    "elapsed_seconds": elapsed,
                })
            save_checkpoint(state)
            print(f"  -> confidence={confidence}  ({elapsed:.0f}s)")

        except subprocess.TimeoutExpired:
            state["errors"].append({"case_id": case_id, "reason": "DiffDock timed out after 900s"})
            save_checkpoint(state)
        except Exception as exc:
            state["errors"].append({"case_id": case_id, "reason": f"{type(exc).__name__}: {exc}"})
            save_checkpoint(state)

    print(f"Done. {len(state['results'])} scored, {len(state['errors'])} errors, "
          f"{len(state['skipped_by_design'])} skipped by design (no principled binding domain), "
          f"out of {input_data['prepared']} prepared / {input_data['total_cases']} total cases.")


if __name__ == "__main__":
    main()
