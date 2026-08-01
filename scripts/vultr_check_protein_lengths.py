"""
One-time check: for each unique UniProt ID in the prepared case list,
fetch its sequence length (from AlphaFold's own prediction metadata,
which already includes sequenceEnd) and, for anything over the DiffDock
ESM truncation limit (1022 residues), fetch UniProt's domain annotations
so we know what to crop to.

Output: protein_domain_info.json — one entry per unique protein with
{uniprot_id, length, over_limit, domains: [{type, start, end}]}
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

ESM_LIMIT = 1022

with open("/root/diffdock_work/diffdock_rescoring_inputs.json") as f:
    data = json.load(f)

uniprots = sorted(set(c["uniprot_id"] for c in data["cases"]))
print(f"{len(uniprots)} unique proteins to check")

results = {}
for i, uid in enumerate(uniprots):
    try:
        with urllib.request.urlopen(
            f"https://alphafold.ebi.ac.uk/api/prediction/{uid}", timeout=15
        ) as resp:
            entries = json.loads(resp.read().decode("utf-8"))
        length = entries[0]["sequenceEnd"] if entries else None
    except Exception as exc:
        length = None
        print(f"  [{i+1}/{len(uniprots)}] {uid}: AlphaFold lookup failed: {exc}")

    entry = {"uniprot_id": uid, "length": length, "over_limit": bool(length and length > ESM_LIMIT), "domains": []}

    if entry["over_limit"]:
        try:
            with urllib.request.urlopen(
                f"https://rest.uniprot.org/uniprotkb/{uid}.json?fields=ft_domain,ft_region,ft_zn_fing",
                timeout=15,
            ) as resp:
                udata = json.loads(resp.read().decode("utf-8"))
            for feat in udata.get("features", []):
                loc = feat.get("location", {})
                start = loc.get("start", {}).get("value")
                end = loc.get("end", {}).get("value")
                if start and end:
                    entry["domains"].append({
                        "type": feat.get("type"),
                        "description": feat.get("description"),
                        "start": start,
                        "end": end,
                    })
        except Exception as exc:
            print(f"  [{i+1}/{len(uniprots)}] {uid}: UniProt domain lookup failed: {exc}")

    results[uid] = entry
    flag = "OVER LIMIT" if entry["over_limit"] else "ok"
    print(f"  [{i+1}/{len(uniprots)}] {uid}: length={length} ({flag}), {len(entry['domains'])} domain(s)")
    time.sleep(0.3)  # be polite to both APIs

over = [u for u, e in results.items() if e["over_limit"]]
print(f"\n{len(over)}/{len(uniprots)} proteins exceed the {ESM_LIMIT}-residue ESM limit:")
for u in over:
    print(f"  {u}: length={results[u]['length']}, domains={results[u]['domains']}")

with open("/root/diffdock_work/protein_domain_info.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nWritten to protein_domain_info.json")
