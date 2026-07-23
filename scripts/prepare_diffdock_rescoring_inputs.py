"""
Prepare a flat {case_id, gene, uniprot_id, drug_name, smiles} list from
ADDITIONAL_VALIDATION_CASES for the one-DiffDock-call-per-case re-scoring run.

Intended to run inside the api container (has async chembl/uniprot lookups
and DB-free access to services.benchmark). Output is copied to the Vultr GPU
box, which only needs a plain synchronous DiffDock runner — no FastAPI/async
stack required there.

Cases with no known_drugs (expect_empty negative controls) are skipped —
there is nothing to dock. Only the first known drug per case is used, per
the "1 call per case" bounded-estimate scope agreed for this run.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from services.benchmark import ADDITIONAL_VALIDATION_CASES
from services.chembl import get_smiles_for_drug_name
from workers.ai_worker import _gene_to_uniprot


async def main():
    prepared = []
    skipped = []

    for case in ADDITIONAL_VALIDATION_CASES:
        case_id = case["case_id"]
        gene = case["gene"]
        known_drugs = case.get("known_drugs") or []

        if not known_drugs:
            skipped.append({"case_id": case_id, "reason": "no known_drugs (negative control)"})
            continue

        uniprot_id = _gene_to_uniprot(gene)
        if not uniprot_id:
            skipped.append({"case_id": case_id, "reason": f"no UniProt mapping for gene {gene}"})
            continue

        drug_name = known_drugs[0]
        mol = await get_smiles_for_drug_name(drug_name)
        if not mol or not mol.get("smiles"):
            skipped.append({
                "case_id": case_id,
                "reason": f"no SMILES for drug {drug_name!r} (biologic or unmatched)",
            })
            continue

        prepared.append({
            "case_id": case_id,
            "gene": gene,
            "uniprot_id": uniprot_id,
            "drug_name": drug_name,
            "chembl_id": mol.get("chembl_id"),
            "smiles": mol["smiles"],
        })

    out = {
        "total_cases": len(ADDITIONAL_VALIDATION_CASES),
        "prepared": len(prepared),
        "skipped": len(skipped),
        "skip_reasons": skipped,
        "cases": prepared,
    }

    with open("/app/diffdock_rescoring_inputs.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"Prepared {len(prepared)}/{len(ADDITIONAL_VALIDATION_CASES)} cases "
          f"({len(skipped)} skipped) -> /app/diffdock_rescoring_inputs.json")


if __name__ == "__main__":
    asyncio.run(main())
