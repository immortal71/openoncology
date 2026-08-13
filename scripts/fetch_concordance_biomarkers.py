"""Fetch the per-patient biomarker side of the oncologist-concordance answer key.

WHY THIS EXISTS
---------------
scripts/build_concordance_labels.py used to derive each patient's biomarker from
the drug they were given (DRUG_BIOMARKER_MAP). That made concordance a tautology:
every trastuzumab patient was labelled "ERBB2 Amplified" whether or not anyone
had ever sequenced them, so the benchmark could not return anything but a high
number. scripts/detect_label_circularity.py measures that defect directly.

The fix is to take the biomarker from the patient's own sequencing record. This
script fetches that record. It knows nothing about treatment: no drug name
appears anywhere in this file, and nothing here is filtered by what the
OpenOncology evidence table happens to be able to answer.

WHAT IT FETCHES
---------------
For each TCGA cohort backing the concordance labels, from cBioPortal:
  - somatic mutations (MUTATION_EXTENDED profile), keyed by patient
  - discrete copy-number calls (GISTIC profile), amplifications and deep
    deletions only

GENE UNIVERSE
-------------
Restricted to the MSK-IMPACT 468-gene panel, read live from cBioPortal's
gene-panel endpoint (panel id IMPACT468; Cheng et al., J Mol Diagn 2015;17:251,
doi:10.1016/j.jmoldx.2014.12.006).

That panel is used because it is the gene set a real sequenced patient's report
would actually contain, it is published and fixed, and it was defined with no
reference to this repository. Two alternatives were rejected: taking every gene
in the exome buries the record in passengers, and selecting genes from this
repo's own evidence table would silently restrict the answer key to questions
the pipeline is already known to answer, which inflates concordance the same way
DRUG_BIOMARKER_MAP did.

Usage:
    python scripts/fetch_concordance_biomarkers.py
    python scripts/fetch_concordance_biomarkers.py --out scripts/concordance_biomarkers.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_OUT = os.path.join(_REPO_ROOT, "scripts", "concordance_biomarkers.json")

BASE = "https://www.cbioportal.org/api"

# Cohort key -> cBioPortal study id. The cohort keys match COHORT_BY_FILE in
# scripts/build_concordance_labels.py so the two sides join cleanly.
#
# TCGA-COAD maps to coadread_tcga because cBioPortal publishes colon and rectal
# adenocarcinoma as one study. The join is on patient id, so the extra READ
# patients simply never match a COAD clinical row and drop out.
STUDIES: dict[str, str] = {
    "TCGA-SKCM": "skcm_tcga",
    "TCGA-LUAD": "luad_tcga",
    "TCGA-BRCA": "brca_tcga",
    "TCGA-COAD": "coadread_tcga",
    "TCGA-GBM": "gbm_tcga",
}

GENE_PANEL_ID = "IMPACT468"

# GISTIC discrete calls. Only the unambiguous ends are kept; shallow single-copy
# gain and loss are too common and too noisy to read as a biomarker. The second
# element is the token the evidence lookup is queried with, matching the
# convention scripts/benchmark_nci_match.py already uses for non-point alterations.
CNA_EVENTS = {
    "AMP": ("Amplification", "AMPLIFICATION"),
    "HOMDEL": ("Deep Deletion", "DELETION"),
}

# Defensive: the TCGA MAFs served by these profiles are already coding-only, but
# do not let a silent call through if a profile ever changes.
NON_CODING_MUTATION_TYPES = {"silent", "synonymous_variant", "3'utr", "5'utr", "intron", "igr", "rna"}

_HEADERS = {"User-Agent": "openoncology-research", "Accept": "application/json"}


def _get(url: str, timeout: int = 120):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _post(url: str, body: dict, timeout: int = 300):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={**_HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def fetch_panel_genes() -> list[int]:
    panel = _get(f"{BASE}/gene-panels/{GENE_PANEL_ID}")
    return sorted({g["entrezGeneId"] for g in panel["genes"]})


def pick_profiles(study_id: str) -> tuple[str | None, str | None]:
    profiles = _get(f"{BASE}/studies/{study_id}/molecular-profiles")
    mutation = next(
        (p["molecularProfileId"] for p in profiles if p["molecularAlterationType"] == "MUTATION_EXTENDED"),
        None,
    )
    cna = next(
        (
            p["molecularProfileId"]
            for p in profiles
            if p["molecularAlterationType"] == "COPY_NUMBER_ALTERATION" and p.get("datatype") == "DISCRETE"
        ),
        None,
    )
    return mutation, cna


def sequenced_patient_ids(study_id: str) -> list[str]:
    """Every patient in the study, whether or not they carry a panel alteration.

    Needed so the label builder can report attrition honestly: a patient who was
    sequenced and had nothing on the panel is a different case from a patient who
    was never sequenced at all.
    """
    return sorted({p["patientId"] for p in _get(f"{BASE}/studies/{study_id}/patients")})


def fetch_mutations(profile_id: str, sample_list_id: str, entrez_ids: list[int]) -> list[dict]:
    records = _post(
        f"{BASE}/molecular-profiles/{profile_id}/mutations/fetch?projection=DETAILED",
        {"sampleListId": sample_list_id, "entrezGeneIds": entrez_ids},
    )
    out = []
    for record in records:
        protein_change = (record.get("proteinChange") or "").strip()
        mutation_type = (record.get("mutationType") or "").strip()
        if not protein_change:
            continue
        if mutation_type.lower() in NON_CODING_MUTATION_TYPES:
            continue
        gene = (record.get("gene") or {}).get("hugoGeneSymbol")
        if not gene:
            continue
        out.append(
            {
                "patient_id": record["patientId"],
                "gene": gene,
                "protein_change": protein_change,
                "alteration_type": "Mutation",
                "mutation_type": mutation_type,
            }
        )
    return out


def fetch_cna(profile_id: str, sample_list_id: str, entrez_ids: list[int]) -> list[dict]:
    out = []
    for event_type, (label, query_token) in CNA_EVENTS.items():
        records = _post(
            f"{BASE}/molecular-profiles/{profile_id}/discrete-copy-number/fetch"
            f"?discreteCopyNumberEventType={event_type}&projection=DETAILED",
            {"sampleListId": sample_list_id, "entrezGeneIds": entrez_ids},
        )
        for record in records:
            gene = (record.get("gene") or {}).get("hugoGeneSymbol")
            if not gene:
                continue
            out.append(
                {
                    "patient_id": record["patientId"],
                    "gene": gene,
                    "protein_change": query_token,
                    "alteration_type": label,
                    "mutation_type": None,
                }
            )
        time.sleep(0.3)
    return out


def _dedupe(alterations: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for alteration in sorted(
        alterations, key=lambda a: (a["gene"], a["alteration_type"], a["protein_change"])
    ):
        key = (alteration["gene"], alteration["alteration_type"], alteration["protein_change"])
        if key in seen:
            continue
        seen.add(key)
        out.append(alteration)
    return out


def build_payload() -> dict:
    entrez_ids = fetch_panel_genes()
    print(f"Gene panel {GENE_PANEL_ID}: {len(entrez_ids)} genes")

    studies_meta: dict[str, dict] = {}
    patients: dict[str, dict[str, list[dict]]] = {}

    for cohort, study_id in STUDIES.items():
        print(f"Fetching {cohort} ({study_id})...")
        mutation_profile, cna_profile = pick_profiles(study_id)
        sample_list = f"{study_id}_all"

        alterations: list[dict] = []
        if mutation_profile:
            muts = fetch_mutations(mutation_profile, sample_list, entrez_ids)
            print(f"  {len(muts)} panel mutations")
            alterations.extend(muts)
        if cna_profile:
            cnas = fetch_cna(cna_profile, sample_list, entrez_ids)
            print(f"  {len(cnas)} panel amplification/deep-deletion calls")
            alterations.extend(cnas)

        by_patient: dict[str, list[dict]] = {}
        for alteration in alterations:
            by_patient.setdefault(alteration.pop("patient_id"), []).append(alteration)
        by_patient = {pid: _dedupe(rows) for pid, rows in sorted(by_patient.items())}

        all_patients = sequenced_patient_ids(study_id)
        print(f"  {len(all_patients)} patients in study, {len(by_patient)} with a panel alteration")

        studies_meta[cohort] = {
            "study_id": study_id,
            "mutation_profile": mutation_profile,
            "cna_profile": cna_profile,
            "n_patients_in_study": len(all_patients),
            "n_patients_with_panel_alteration": len(by_patient),
            "patient_ids_in_study": all_patients,
        }
        patients[cohort] = by_patient
        time.sleep(0.5)

    return {
        "description": (
            "Per-patient sequenced biomarkers for the oncologist-concordance answer key. "
            "Contains no treatment information by construction."
        ),
        "source": "cBioPortal public API (https://www.cbioportal.org/api)",
        "gene_panel": {
            "panel_id": GENE_PANEL_ID,
            "n_genes": len(entrez_ids),
            "citation": "Cheng DT et al. J Mol Diagn 2015;17:251. doi:10.1016/j.jmoldx.2014.12.006",
        },
        "cna_calls_kept": sorted(label for label, _token in CNA_EVENTS.values()),
        "studies": studies_meta,
        "patients": patients,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=_DEFAULT_OUT, help="Output JSON path.")
    args = parser.parse_args()

    payload = build_payload()
    out_path = os.path.abspath(args.out)
    # Written compactly: this is a fetched cache of roughly 46k alteration rows,
    # and pretty-printing it triples the size for no reader benefit.
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)

    total = sum(len(rows) for rows in payload["patients"].values())
    print()
    print(f"Patients with at least one panel alteration: {total}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
