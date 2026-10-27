"""Fetch the MSK-CHORD cohort of patients who received a targeted therapy (OO-29).

Produces one JSON file per patient: cancer type, treatment events (with start
and stop days since diagnosis), somatic mutations with gene symbol and protein
change, discrete CNA calls for the actionable gene set, and the earliest
diagnosis day. The output is enough to score any mutation-based ranker against
the drugs the patient actually received.

Where the data comes from:
- The timeline tables (data_timeline_treatment.txt, data_timeline_diagnosis.txt)
  and the sample clinical table come from the public datahub release at
  https://media.githubusercontent.com/media/cBioPortal/datahub/master/public/msk_chord_2024/
- Mutations and discrete CNAs come from the cBioPortal API, because
  data_mutations.txt in the datahub release is a stub.

Why only the targeted-therapy subset:
- Dr. Warner's point on OO-28: a mutation ranker can only be measured against
  patients whose care was driven by their mutations. Chemotherapy-only
  patients are the wrong cohort for that question, even when their records
  are complete.

Why only a subset of genes for CNA:
- The CNA endpoint is per-gene, so pulling it unbounded is slow and most of
  the result would never affect ranking. The gene set here is the one with
  approved targeted-therapy indications. Edit ACTIONABLE_GENES to extend it.

Run time: about 15 minutes for the mutations fetch at the default batch size
of 500 samples; the CNA fetch adds another few minutes. The datahub text
files are small (treatment is 7MB, diagnosis 4MB) and arrive in seconds.

Network: needs reachable access to www.cbioportal.org and
media.githubusercontent.com. On a locked-down host, run the fetch on a
machine that can reach them and copy the resulting JSON over.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

CBIOPORTAL = "https://www.cbioportal.org/api"
DATAHUB = (
    "https://media.githubusercontent.com/media/cBioPortal/datahub/master/"
    "public/msk_chord_2024/"
)
STUDY = "msk_chord_2024"
MUT_PROFILE = f"{STUDY}_mutations"
CNA_PROFILE = f"{STUDY}_cna"

# Actionable genes: the ones with a well-defined targeted-therapy indication
# in FDA labels or OncoKB level 1-2. CNA is queried only for these.
ACTIONABLE_GENES = [
    "EGFR", "ALK", "ROS1", "ERBB2", "MET", "RET", "NTRK1", "NTRK2", "NTRK3",
    "KRAS", "BRAF", "PIK3CA", "FGFR1", "FGFR2", "FGFR3", "FGFR4", "IDH1",
    "IDH2", "SMO", "PTCH1", "VHL", "KIT", "PDGFRA", "MTOR", "TSC1", "TSC2",
    "BRCA1", "BRCA2", "PALB2", "ATM", "AR", "ESR1", "AKT1", "PTEN",
    "CDKN2A", "CDK4", "CDK6", "FLT3", "ABL1", "JAK2", "MPL", "DNMT3A",
    "TET2", "EZH2", "BTK", "PLCG2", "HRAS", "NRAS", "MAP2K1", "MAP2K2",
    "CHEK2", "RAD51C", "RAD51D", "BARD1", "BRIP1", "ARID1A", "SMARCB1",
]


def _http(url: str, body: dict | None = None, retries: int = 3) -> bytes:
    data = None if body is None else json.dumps(body).encode()
    headers = {"User-Agent": "openoncology-research"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt * 2)
    raise RuntimeError(f"unreachable: {url}")


def _fetch_text(name: str) -> str:
    return _http(DATAHUB + name).decode("utf-8", errors="replace")


def _parse_tsv(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.split("\n") if ln and not ln.startswith("#")]
    if not lines:
        return [], []
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:] if ln]
    return header, rows


def _gene_map(symbols: list[str]) -> dict[int, str]:
    """entrezGeneId -> HUGO symbol. One POST, covers everything we need."""
    data = _http(
        f"{CBIOPORTAL}/genes/fetch?geneIdType=HUGO_GENE_SYMBOL",
        body=list(dict.fromkeys(symbols)),
    )
    out = {}
    for g in json.loads(data):
        out[g["entrezGeneId"]] = g["hugoGeneSymbol"]
    return out


def _mutations_for(samples: list[str], entrez_to_symbol: dict[int, str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in range(0, len(samples), 500):
        chunk = samples[i : i + 500]
        data = _http(
            f"{CBIOPORTAL}/molecular-profiles/{MUT_PROFILE}/mutations/fetch?projection=SUMMARY",
            body={"sampleIds": chunk},
        )
        for m in json.loads(data):
            pid = m.get("patientId")
            if not pid:
                continue
            out.setdefault(pid, []).append({
                "gene": entrez_to_symbol.get(m.get("entrezGeneId")) or f"entrez:{m.get('entrezGeneId')}",
                "entrez_gene_id": m.get("entrezGeneId"),
                "protein_change": m.get("proteinChange") or "",
                "mutation_type": m.get("mutationType") or "",
                "sample_id": m.get("sampleId"),
            })
        print(f"  mutations: {min(i + 500, len(samples))}/{len(samples)}", file=sys.stderr)
        time.sleep(0.1)
    return out


def _cna_for(samples: list[str], entrez_ids: list[int], entrez_to_symbol: dict[int, str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in range(0, len(samples), 300):
        chunk = samples[i : i + 300]
        data = _http(
            f"{CBIOPORTAL}/molecular-profiles/{CNA_PROFILE}/discrete-copy-number/fetch"
            "?discreteCopyNumberEventType=HOMDEL_AND_AMP&projection=SUMMARY",
            body={"sampleIds": chunk, "entrezGeneIds": entrez_ids},
        )
        for c in json.loads(data):
            pid = c.get("patientId")
            if not pid:
                continue
            alt = c.get("alteration")
            kind = "Amplification" if alt == 2 else "Deep Deletion" if alt == -2 else f"alt{alt}"
            out.setdefault(pid, []).append({
                "gene": entrez_to_symbol.get(c.get("entrezGeneId")) or f"entrez:{c.get('entrezGeneId')}",
                "entrez_gene_id": c.get("entrezGeneId"),
                "alteration": kind,
                "sample_id": c.get("sampleId"),
            })
        print(f"  cnas: {min(i + 300, len(samples))}/{len(samples)}", file=sys.stderr)
        time.sleep(0.1)
    return out


def build(output_path: str) -> dict:
    print("Fetching treatment timeline (datahub)...", file=sys.stderr)
    header, rows = _parse_tsv(_fetch_text("data_timeline_treatment.txt"))
    col = {name: i for i, name in enumerate(header)}
    targeted_by_patient: dict[str, list[dict]] = {}
    for r in rows:
        if len(r) < len(header):
            continue
        if r[col["SUBTYPE"]] != "Targeted":
            continue
        try:
            start = int(r[col["START_DATE"]])
            stop = int(r[col["STOP_DATE"]]) if r[col["STOP_DATE"]] else start
        except ValueError:
            continue
        targeted_by_patient.setdefault(r[col["PATIENT_ID"]], []).append({
            "agent": r[col["AGENT"]],
            "start": start,
            "stop": stop,
        })
    print(f"  patients with targeted therapy: {len(targeted_by_patient)}", file=sys.stderr)

    print("Fetching clinical samples (datahub)...", file=sys.stderr)
    header, rows = _parse_tsv(_fetch_text("data_clinical_sample.txt"))
    col = {name: i for i, name in enumerate(header)}
    samples_by_patient: dict[str, list[str]] = {}
    cancer_by_patient: dict[str, str] = {}
    for r in rows:
        if len(r) < len(header):
            continue
        pid = r[col["PATIENT_ID"]]
        sid = r[col["SAMPLE_ID"]]
        samples_by_patient.setdefault(pid, []).append(sid)
        cancer_by_patient.setdefault(pid, r[col["CANCER_TYPE"]])

    print("Fetching diagnosis timeline (datahub)...", file=sys.stderr)
    header, rows = _parse_tsv(_fetch_text("data_timeline_diagnosis.txt"))
    col = {name: i for i, name in enumerate(header)}
    earliest_dx: dict[str, int] = {}
    for r in rows:
        if len(r) < len(header):
            continue
        pid = r[col["PATIENT_ID"]]
        try:
            d = int(r[col["START_DATE"]])
        except (ValueError, KeyError):
            continue
        if pid not in earliest_dx or d < earliest_dx[pid]:
            earliest_dx[pid] = d

    targeted_samples: list[str] = []
    for pid in targeted_by_patient:
        targeted_samples.extend(samples_by_patient.get(pid, []))
    print(f"Samples to pull alterations for: {len(targeted_samples)}", file=sys.stderr)

    print("Resolving gene symbols...", file=sys.stderr)
    entrez_to_symbol = _gene_map(ACTIONABLE_GENES)
    entrez_ids = sorted(entrez_to_symbol.keys())

    print("Fetching mutations...", file=sys.stderr)
    muts_by_patient = _mutations_for(targeted_samples, entrez_to_symbol)
    print("Fetching discrete CNAs for the actionable genes...", file=sys.stderr)
    cnas_by_patient = _cna_for(targeted_samples, entrez_ids, entrez_to_symbol)

    records = []
    for pid, events in targeted_by_patient.items():
        muts = muts_by_patient.get(pid, [])
        cnas = cnas_by_patient.get(pid, [])
        if not muts and not cnas:
            continue
        agents = sorted({e["agent"] for e in events})
        first = min(e["start"] for e in events)
        records.append({
            "cohort": "MSK-CHORD",
            "patient_id": pid,
            "cancer_type": cancer_by_patient.get(pid, ""),
            "first_diagnosis_day": earliest_dx.get(pid),
            "first_targeted_day": first,
            "targeted_drugs": agents,
            "targeted_events": events,
            "mutations": muts,
            "cnas": cnas,
        })

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, separators=(",", ":"))
    print(f"Wrote {len(records)} records to {output_path}", file=sys.stderr)
    return {"records": len(records), "patients_with_targeted": len(targeted_by_patient)}


def main() -> None:
    p = argparse.ArgumentParser()
    default = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "validation_results",
        "msk_chord_targeted_cohort.json",
    )
    p.add_argument("--out", default=default, help=f"Output JSON path (default: {default})")
    args = p.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
