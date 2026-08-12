"""Fetch real per-patient mutation data from cBioPortal (POST-based bulk
mutation fetch, correct per the actual API spec) for the additional TCGA
cohorts pulled from GDC."""
import json
import urllib.request
import time

BASE = "https://www.cbioportal.org/api"
STUDIES = {
    "TCGA-PAAD": "paad_tcga",
    "TCGA-PRAD": "prad_tcga_pub",
    "TCGA-KIRC": "kirc_tcga_pub",
    "TCGA-THCA": "thca_tcga_pub",
    "TCGA-STAD": "stad_tcga_pub",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "openoncology-research", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _post(url, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": "openoncology-research", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pick_profile_and_samplelist(study_id):
    profiles = _get(f"{BASE}/studies/{study_id}/molecular-profiles")
    mut_profile = next((p["molecularProfileId"] for p in profiles if p["molecularAlterationType"] == "MUTATION_EXTENDED"), None)
    sample_lists = _get(f"{BASE}/studies/{study_id}/sample-lists")
    ids = {s["sampleListId"] for s in sample_lists}
    all_id = f"{study_id}_all" if f"{study_id}_all" in ids else next(iter(ids), None)
    return mut_profile, all_id


if __name__ == "__main__":
    all_mutations = {}
    for tcga_proj, study_id in STUDIES.items():
        print(f"Fetching mutations for {study_id} ({tcga_proj})...")
        try:
            mut_profile, sample_list = pick_profile_and_samplelist(study_id)
            print(f"  profile={mut_profile} sample_list={sample_list}")
            muts = _post(
                f"{BASE}/molecular-profiles/{mut_profile}/mutations/fetch?projection=DETAILED",
                {"sampleListId": sample_list},
            )
            print(f"  {len(muts)} mutation records")
            # Keep only fields we need to save space
            slim = [
                {
                    "patientId": m["patientId"],
                    "gene": m.get("gene", {}).get("hugoGeneSymbol"),
                    "proteinChange": m.get("proteinChange"),
                    "mutationType": m.get("mutationType"),
                    "chr": m.get("chr"),
                    "startPosition": m.get("startPosition"),
                    "referenceAllele": m.get("referenceAllele"),
                    "variantAllele": m.get("variantAllele"),
                }
                for m in muts
            ]
            all_mutations[tcga_proj] = slim
        except Exception as e:
            print(f"  FAILED: {e}")
            all_mutations[tcga_proj] = []
        time.sleep(0.5)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cbioportal_extra_mutations.json")
    with open(out_path, "w") as f:
        json.dump(all_mutations, f)
    print("saved to", out_path)
