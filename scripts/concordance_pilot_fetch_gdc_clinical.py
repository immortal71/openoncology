"""Fetch real GDC clinical/treatment data for additional TCGA cohorts.
Same source (api.gdc.cancer.gov) and same fields as the existing
scripts/clinical*.tsv files in the repo, just for cohorts not yet downloaded.
"""
import json
import urllib.parse
import urllib.request
import time

PROJECTS = ["TCGA-PAAD", "TCGA-PRAD", "TCGA-KIRC", "TCGA-THCA", "TCGA-STAD"]

FIELDS = [
    "submitter_id",
    "project.project_id",
    "diagnoses.treatments.therapeutic_agents",
    "diagnoses.treatments.treatment_type",
    "diagnoses.primary_diagnosis",
]


def gdc_fetch_all(project_id: str) -> list[dict]:
    all_hits = []
    frm = 0
    size = 500
    while True:
        params = {
            "filters": json.dumps({
                "op": "in",
                "content": {"field": "cases.project.project_id", "value": [project_id]},
            }),
            "fields": ",".join(FIELDS),
            "format": "JSON",
            "size": str(size),
            "from": str(frm),
        }
        url = "https://api.gdc.cancer.gov/cases?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "openoncology-research"})
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
        hits = payload["data"]["hits"]
        all_hits.extend(hits)
        total = payload["data"]["pagination"]["total"]
        frm += size
        if frm >= total:
            break
        time.sleep(0.3)
    return all_hits


def extract_patient_drugs(hits: list[dict]) -> dict[str, set[str]]:
    out = {}
    for h in hits:
        pid = h.get("submitter_id")
        if not pid:
            continue
        drugs = set()
        for dx in h.get("diagnoses") or []:
            for t in dx.get("treatments") or []:
                agent = t.get("therapeutic_agents")
                if agent and agent.strip() and agent.strip().lower() not in ("not reported", "unknown"):
                    drugs.add(agent.strip())
        if drugs:
            out[pid] = drugs
    return out


if __name__ == "__main__":
    all_patient_drugs = {}
    for proj in PROJECTS:
        print(f"Fetching {proj}...")
        hits = gdc_fetch_all(proj)
        patient_drugs = extract_patient_drugs(hits)
        print(f"  {len(hits)} cases, {len(patient_drugs)} with real recorded drugs")
        all_patient_drugs[proj] = {k: sorted(v) for k, v in patient_drugs.items()}

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gdc_extra_cohorts_drugs.json")
    with open(out_path, "w") as f:
        json.dump(all_patient_drugs, f, indent=2)
    print("saved to", out_path)
