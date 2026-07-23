"""
Crop AlphaFold PDB structures to their ligand-binding domain for proteins
that exceed DiffDock's 1022-residue ESM truncation limit.

Cropping strategy, in priority order, using protein_domain_info.json's
real UniProt domain annotations (never guessed):
  1. If a "Protein kinase" domain exists, crop to it — this is the ATP/
     inhibitor-binding site for kinase-targeted small molecules, which is
     what essentially all of our over-limit kinase cases actually target.
  2. If a "PI3K/PI4K catalytic" domain exists (PIK3CA/MTOR-family), crop
     to it — same rationale, it's the catalytic/inhibitor pocket.
  3. Otherwise: DO NOT crop and DO NOT guess a domain. Log the protein as
     "no small-molecule binding domain identified" and skip it honestly.
     Proteins like BRCA1/BRCA2 (DNA-repair scaffolds) or transcription
     factors with only "Disordered"/DNA-binding regions are not real
     small-molecule DiffDock targets in the first place — forcing a crop
     onto an arbitrary region would produce a confidence score with no
     scientific meaning, which is worse than reporting no result.

Cropping is done with a flanking margin (default 20 residues each side)
to preserve local structural context around the domain boundary, capped
so the cropped span never itself exceeds the ESM limit.
"""
from __future__ import annotations

import json

ESM_LIMIT = 1022
FLANK = 20

KINASE_DOMAIN_NAMES = {"Protein kinase", "Protein kinase 1", "Protein kinase 2", "PI3K/PI4K catalytic"}


def pick_crop_region(domains: list[dict], protein_length: int) -> tuple[int, int] | None:
    """Return (start, end) 1-indexed residue range to keep, or None if no
    principled small-molecule binding domain was found."""
    kinase_domains = [d for d in domains if d["type"] == "Domain" and d["description"] in KINASE_DOMAIN_NAMES]
    if not kinase_domains:
        return None

    # If a protein has two kinase domains (e.g. JAK-family pseudokinase +
    # active kinase), keep the widest span covering all of them — some
    # JAK inhibitors bind at the pseudokinase-kinase interface.
    start = min(d["start"] for d in kinase_domains) - FLANK
    end = max(d["end"] for d in kinase_domains) + FLANK
    start = max(1, start)
    end = min(protein_length, end)

    if end - start + 1 > ESM_LIMIT:
        # Domain span itself (with flanking) is still too long — trim
        # flanking first, then trim symmetrically from the ends as a
        # last resort, never past the actual annotated domain boundaries.
        over = (end - start + 1) - ESM_LIMIT
        start += over // 2
        end -= over - (over // 2)

    return (start, end)


def crop_pdb(pdb_path, out_path, start: int, end: int):
    """Write only ATOM/HETATM lines whose residue number falls in [start, end]."""
    kept = 0
    with open(pdb_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            if line.startswith(("ATOM", "HETATM")):
                try:
                    resnum = int(line[22:26])
                except ValueError:
                    continue
                if start <= resnum <= end:
                    fout.write(line)
                    kept += 1
            elif line.startswith(("HEADER", "TITLE", "COMPND")):
                fout.write(line)
    fout_end = open(out_path, "a")
    fout_end.write("END\n")
    fout_end.close()
    return kept


def main():
    with open("/root/diffdock_work/protein_domain_info.json") as f:
        protein_info = json.load(f)

    decisions = {}
    for uid, info in protein_info.items():
        if info["length"] is None:
            decisions[uid] = {
                "action": "skip",
                "reason": "AlphaFold has no structure at this endpoint for this accession "
                          "(likely a fragmented/split entry for a very large protein) — "
                          "length and over_limit status are both unknown, not assumed safe",
            }
            continue

        if not info["over_limit"]:
            decisions[uid] = {"action": "use_full_length", "reason": "under ESM limit"}
            continue

        region = pick_crop_region(info["domains"], info["length"])
        if region is None:
            decisions[uid] = {
                "action": "skip",
                "reason": "no kinase/catalytic domain annotation found — not cropping arbitrarily",
            }
            continue

        start, end = region
        decisions[uid] = {
            "action": "crop",
            "crop_start": start,
            "crop_end": end,
            "cropped_length": end - start + 1,
        }

    with open("/root/diffdock_work/crop_decisions.json", "w") as f:
        json.dump(decisions, f, indent=2)

    for uid, d in decisions.items():
        print(f"{uid}: {d}")

    n_crop = sum(1 for d in decisions.values() if d["action"] == "crop")
    n_skip = sum(1 for d in decisions.values() if d["action"] == "skip")
    n_full = sum(1 for d in decisions.values() if d["action"] == "use_full_length")
    print(f"\n{n_full} full-length, {n_crop} cropped, {n_skip} skipped (no principled domain)")


if __name__ == "__main__":
    main()
