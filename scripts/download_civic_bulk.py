#!/usr/bin/env python3
"""Download CIViC bulk evidence data and extract drug-variant associations.

Downloads the nightly ClinicalEvidenceSummaries TSV from CIViC (civicdb.org).
CIViC is a community-curated, CC BY-SA 4.0 licensed resource.

Outputs:
    data/civic_evidence.tsv         — raw downloaded TSV
    data/civic_new_entries.py       — Python snippet with new _LEVEL_TABLE entries
    data/civic_summary.json         — summary of what's new vs existing

Usage:
    python scripts/download_civic_bulk.py
    python scripts/download_civic_bulk.py --no-download   # use cached TSV
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx required: pip install httpx")

# ── CIViC bulk download URL (nightly, free, no auth) ─────────────────────────
CIVIC_URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"

# ── Output paths ──────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
TSV_PATH = DATA_DIR / "civic_evidence.tsv"
NEW_ENTRIES_PATH = DATA_DIR / "civic_new_entries.py"
SUMMARY_PATH = DATA_DIR / "civic_summary.json"

# ── CIViC level → OncoKB level mapping ───────────────────────────────────────
# CIViC evidence tiers (for PREDICTIVE evidence):
#   A  — Validated association (strong clinical evidence, usually FDA-level)
#   B  — Clinical evidence (multiple small studies or single strong RCT)
#   C  — Case report / individual study
#   D  — Preclinical evidence only
#   E  — Inferential/theoretical
CIVIC_TO_ONCOKB: dict[str, str] = {
    "A": "LEVEL_1",
    "B": "LEVEL_2",
    "C": "LEVEL_3A",
    "D": "LEVEL_3B",
    "E": "LEVEL_4",
}

# Resistance direction mapping
RESISTANCE_CIVIC_TO_ONCOKB: dict[str, str] = {
    "A": "LEVEL_R1",
    "B": "LEVEL_R1",
    "C": "LEVEL_R2",
    "D": "LEVEL_R2",
}

# Clinical significance values we want (sensitivity/response only unless resistance)
SENSITIVITY_TERMS = {"SENSITIVITYRESPONSE", "SENSITIVITY", "RESPONSE", "POSITIVE"}
RESISTANCE_TERMS = {"RESISTANCE", "REDUCED SENSITIVITY"}

# ── Already-covered genes (rough filter — we expand this in the output) ────────
KNOWN_GENES = {
    "EGFR", "ALK", "ROS1", "KRAS", "BRAF", "NRAS", "RET", "MET", "ERBB2",
    "PIK3CA", "BRCA1", "BRCA2", "IDH1", "IDH2", "FLT3", "KIT", "PDGFRA",
    "ABL1", "JAK2", "MPL", "CALR", "TP53", "APC", "VHL", "PTEN",
    "FGFR1", "FGFR2", "FGFR3", "NTRK1", "NTRK2", "NTRK3", "NF1",
    "CDKN2A", "CDK4", "CDK6", "CCND1", "ESR1", "AR", "PALB2",
    "RAD51", "ATM", "CDK12", "ARID1A", "SMARCA4",
    "TSC1", "TSC2", "MTOR", "STK11", "MAP2K1", "MAP2K2",
    "EZH2", "DNMT3A", "TET2", "ASXL1", "NPM1", "RUNX1",
    "NOTCH1", "NOTCH2", "NOTCH3", "MLH1", "MSH2", "MSH6", "PMS2",
    "HRAS", "NF2", "SMO", "PTCH1", "RB1", "AKT1", "AKT2",
}


def download_civic_tsv() -> None:
    """Download the CIViC nightly evidence TSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading CIViC evidence from:\n  {CIVIC_URL}")
    headers = {"User-Agent": "OpenOncology-Research/1.0 (educational; contact=research@openoncology.local)"}
    try:
        with httpx.stream("GET", CIVIC_URL, headers=headers, timeout=120, follow_redirects=True) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with TSV_PATH.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {downloaded:,} / {total:,} bytes ({pct:.1f}%)", end="", flush=True)
        print(f"\n  Saved to {TSV_PATH}")
    except httpx.HTTPStatusError as e:
        sys.exit(f"HTTP error: {e}")
    except httpx.RequestError as e:
        sys.exit(f"Network error: {e}")


def _normalize_variant(variant_name: str) -> str:
    """Normalize CIViC variant name to our format."""
    v = variant_name.strip().upper()
    # Common normalizations
    v = v.replace(" ", "").replace("–", "-").replace("—", "-")
    # Fusion normalization: "EML4-ALK FUSION" → "EML4-ALK"
    if v.endswith("FUSION"):
        v = v[:-6].rstrip("-").strip()
        if not v:
            v = "FUSION"
        elif not v.endswith("-FUSION"):
            v = v + "" if "-" in v else v  # keep as-is for fusions
    return v


def _normalize_drug(drug_name: str) -> str:
    """Normalize CIViC drug name to our lowercase convention."""
    return drug_name.strip().lower().replace(" ", "_").replace("-", "_")


def _cancer_type_to_context(disease: str) -> str | None:
    """Map CIViC disease name to our cancer context strings."""
    d = disease.upper()
    mappings = {
        "LUNG": "NSCLC",
        "NON-SMALL CELL": "NSCLC",
        "NSCLC": "NSCLC",
        "COLORECTAL": "COLORECTAL",
        "COLON": "COLORECTAL",
        "RECTAL": "COLORECTAL",
        "BREAST": "BREAST",
        "OVARIAN": "OVARIAN",
        "PROSTATE": "PROSTATE",
        "MELANOMA": "MELANOMA",
        "LEUKEMIA": "AML",
        "AML": "AML",
        "CML": "CML",
        "LYMPHOMA": "LYMPHOMA",
        "GLIOMA": "GLIOMA",
        "GLIOBLASTOMA": "GLIOBLASTOMA",
        "BLADDER": "BLADDER",
        "THYROID": "THYROID",
        "GASTRIC": "GASTRIC",
        "STOMACH": "GASTRIC",
        "HEPATOCELLULAR": "HCC",
        "CHOLANGIOCARCINOMA": "CHOLANGIOCARCINOMA",
        "PANCREATIC": "PANCREATIC",
        "RENAL": "RCC",
        "KIDNEY": "RCC",
    }
    for key, val in mappings.items():
        if key in d:
            return val
    return None


def parse_civic_tsv(path: Path) -> list[dict]:
    """Parse CIViC evidence TSV and return processed rows."""
    rows = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rows.append(dict(row))
    return rows


def build_evidence_map(rows: list[dict]) -> dict:
    """Build a map of (gene, variant) → {drug → level} from CIViC rows.
    
    Returns:
        {
            (gene, variant): {drug: oncokb_level},
            ...
        }
    Also returns context-specific overrides:
        {
            (gene, variant, cancer_type): {drug: oncokb_level}
        }
    """
    sensitivity: dict[tuple, dict[str, str]] = defaultdict(dict)
    context_specific: dict[tuple, dict[str, str]] = defaultdict(dict)
    
    for row in rows:
        # Filter: only human, only accepted evidence, only predictive type
        if row.get("evidence_type", "").upper() != "PREDICTIVE":
            continue
        if row.get("evidence_status", "").upper() not in ("ACCEPTED",):
            continue
        
        gene = row.get("gene", "").strip().upper()
        if not gene:
            continue

        variant = row.get("variant", "").strip()
        drugs_raw = row.get("drugs", "").strip()
        level = row.get("evidence_level", "").strip().upper()
        clinical_sig = row.get("clinical_significance", "").strip().upper()
        disease = row.get("disease", "").strip()

        if not drugs_raw or not level or not variant:
            continue

        # Handle multiple drugs (comma-separated in CIViC)
        drugs = [d.strip() for d in drugs_raw.split(",") if d.strip()]
        
        is_resistance = clinical_sig in RESISTANCE_TERMS
        is_sensitivity = clinical_sig in SENSITIVITY_TERMS

        if not is_resistance and not is_sensitivity:
            continue

        # Map level
        if is_resistance:
            oncokb_level = RESISTANCE_CIVIC_TO_ONCOKB.get(level)
        else:
            oncokb_level = CIVIC_TO_ONCOKB.get(level)
        
        if not oncokb_level:
            continue

        norm_variant = _normalize_variant(variant)
        cancer_context = _cancer_type_to_context(disease)

        for drug_raw in drugs:
            drug = _normalize_drug(drug_raw)
            if not drug:
                continue

            key = (gene, norm_variant)
            # Keep the best (highest) level for each drug
            existing = sensitivity[key].get(drug)
            if existing is None or _level_rank(oncokb_level) > _level_rank(existing):
                sensitivity[key][drug] = oncokb_level

            # Also track cancer-context-specific data
            if cancer_context:
                ctx_key = (gene, norm_variant, cancer_context)
                ctx_existing = context_specific[ctx_key].get(drug)
                if ctx_existing is None or _level_rank(oncokb_level) > _level_rank(ctx_existing):
                    context_specific[ctx_key][drug] = oncokb_level

    return dict(sensitivity), dict(context_specific)


def _level_rank(level: str) -> int:
    """Higher rank = more specific/higher evidence level."""
    ranks = {
        "LEVEL_1": 7, "LEVEL_2": 6, "LEVEL_3A": 5, "LEVEL_3B": 4,
        "LEVEL_4": 3, "LEVEL_R1": 2, "LEVEL_R2": 1,
    }
    return ranks.get(level, 0)


def load_existing_table_keys() -> set[tuple]:
    """Load existing (gene, variant) keys from oncokb_evidence.py."""
    evidence_path = Path(__file__).parent.parent / "api" / "services" / "oncokb_evidence.py"
    keys = set()
    with evidence_path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith('("') and '"):' in stripped:
                # Extract tuple key
                import re
                m = re.match(r'\("([^"]+)",\s*"([^"]+)"\)', stripped)
                if m:
                    keys.add((m.group(1).upper(), m.group(2).upper()))
    return keys


def generate_new_entries(
    civic_map: dict,
    existing_keys: set[tuple],
    min_level: str = "LEVEL_3A",
) -> list[tuple]:
    """Find entries in CIViC not already in our table.
    
    Returns list of (gene, variant, drug_dict) for new entries.
    """
    min_rank = _level_rank(min_level)
    new_entries = []

    for (gene, variant), drugs in sorted(civic_map.items()):
        # Normalize key for comparison
        key = (gene, variant.upper())
        
        # Skip if already fully covered
        if key in existing_keys:
            continue

        # Filter to only high-confidence entries
        good_drugs = {
            drug: level for drug, level in drugs.items()
            if _level_rank(level) >= min_rank
        }
        if not good_drugs:
            continue

        # Skip variants with too-generic names
        skip_patterns = {"MUTATION", "EXPRESSION", "UNDEREXPRESSION", "OVEREXPRESSION",
                         "WILDTYPE", "WILD TYPE", "COPY NUMBER VARIATION"}
        if variant.upper() in skip_patterns:
            continue

        new_entries.append((gene, variant, good_drugs))

    return new_entries


def write_new_entries_file(new_entries: list[tuple], path: Path) -> None:
    """Write Python snippet that can be appended to oncokb_evidence.py."""
    lines = [
        "# ── AUTO-GENERATED from CIViC nightly bulk download ─────────────────────────",
        "# Run scripts/download_civic_bulk.py to regenerate.",
        "# Review before merging — some entries may need manual curation.",
        "# Only ACCEPTED PREDICTIVE evidence, Level A-C mapped to LEVEL_1-3A.",
        "",
        "# Add these to _LEVEL_TABLE in api/services/oncokb_evidence.py:",
        "_CIVIC_NEW_ENTRIES = {",
    ]
    for gene, variant, drugs in new_entries:
        drug_str = ", ".join(
            f'"{drug}": "{level}"'
            for drug, level in sorted(drugs.items(), key=lambda x: -_level_rank(x[1]))
        )
        lines.append(f'    ("{gene}", "{variant}"): {{{drug_str}}},')
    lines.append("}")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(new_entries)} new entries to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and process CIViC bulk evidence data")
    parser.add_argument("--no-download", action="store_true", help="Use existing TSV, skip download")
    parser.add_argument("--min-level", default="LEVEL_3A", help="Minimum evidence level to include (default: LEVEL_3A)")
    args = parser.parse_args()

    if not args.no_download:
        if TSV_PATH.exists():
            age_hours = (time.time() - TSV_PATH.stat().st_mtime) / 3600
            if age_hours < 24:
                print(f"Using cached TSV ({age_hours:.1f}h old). Use --no-download to force reuse, or delete data/civic_evidence.tsv to re-download.")
            else:
                download_civic_tsv()
        else:
            download_civic_tsv()
    else:
        if not TSV_PATH.exists():
            sys.exit(f"No cached TSV found at {TSV_PATH}. Remove --no-download to download it.")
        print(f"Using existing TSV: {TSV_PATH}")

    print("\nParsing CIViC evidence data...")
    rows = parse_civic_tsv(TSV_PATH)
    print(f"  {len(rows):,} total rows")

    # Filter stats
    predictive = sum(1 for r in rows if r.get("evidence_type", "").upper() == "PREDICTIVE")
    accepted = sum(1 for r in rows if r.get("evidence_type", "").upper() == "PREDICTIVE"
                   and r.get("evidence_status", "").upper() == "ACCEPTED")
    print(f"  {predictive:,} predictive evidence items")
    print(f"  {accepted:,} accepted predictive items")

    print("\nBuilding evidence map...")
    civic_map, context_map = build_evidence_map(rows)
    print(f"  {len(civic_map):,} unique (gene, variant) pairs with drug data")
    print(f"  {len(context_map):,} context-specific (gene, variant, cancer_type) entries")

    print("\nLoading existing table keys...")
    existing_keys = load_existing_table_keys()
    print(f"  {len(existing_keys):,} existing (gene, variant) keys")

    print(f"\nIdentifying new entries (min level: {args.min_level})...")
    new_entries = generate_new_entries(civic_map, existing_keys, min_level=args.min_level)
    print(f"  {len(new_entries):,} new (gene, variant) pairs to add")

    # Write outputs
    write_new_entries_file(new_entries, NEW_ENTRIES_PATH)

    # Summary JSON
    summary = {
        "total_civic_rows": len(rows),
        "predictive_accepted": accepted,
        "civic_unique_pairs": len(civic_map),
        "existing_table_keys": len(existing_keys),
        "new_entries_count": len(new_entries),
        "top_new_genes": {},
        "top_new_drugs": {},
    }
    
    # Count by gene
    gene_counts: dict[str, int] = defaultdict(int)
    drug_counts: dict[str, int] = defaultdict(int)
    for gene, variant, drugs in new_entries:
        gene_counts[gene] += 1
        for drug in drugs:
            drug_counts[drug] += 1
    
    summary["top_new_genes"] = dict(sorted(gene_counts.items(), key=lambda x: -x[1])[:20])
    summary["top_new_drugs"] = dict(sorted(drug_counts.items(), key=lambda x: -x[1])[:20])

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary written to {SUMMARY_PATH}")
    print("\nTop new genes with missing entries:")
    for gene, count in list(summary["top_new_genes"].items())[:15]:
        print(f"  {gene}: {count} new variants")
    print("\nTop new drugs mentioned in new entries:")
    for drug, count in list(summary["top_new_drugs"].items())[:15]:
        print(f"  {drug}: {count} new variant associations")
    print(f"\nDone. Review {NEW_ENTRIES_PATH} before integrating into oncokb_evidence.py")


if __name__ == "__main__":
    main()
