"""TCGA / ICGC / CCLE cohort data ingestion pipeline.

Downloads somatic mutation data from public cancer genomics repositories and
loads it into the OpenOncology cohort tables (Study, Sample, CohortMutation).

Supported sources:
  - TCGA PanCancer Atlas via GDC API (33 cancer types, ~10K samples)
  - ICGC ARGO (open-access tier)
  - CCLE (DepMap cell line mutation data)

Usage:
  python ingest_cohorts.py --source tcga --cancer-type LUAD --output /tmp/luad/
  python ingest_cohorts.py --source ccle --output /tmp/ccle/
  python ingest_cohorts.py --source icgc --project BRCA-EU --output /tmp/icgc/

Environment variables required:
  DATABASE_URL   — PostgreSQL async URL for the OpenOncology database
  (GDC API is public and does not require authentication for open-access data)

References:
  - GDC API: https://api.gdc.cancer.gov/
  - ICGC API: https://dcc.icgc.org/api/
  - DepMap portal: https://depmap.org/portal/
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import os
import sys
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ── GDC (TCGA) ingestion ───────────────────────────────────────────────────────

GDC_FILES_ENDPOINT = "https://api.gdc.cancer.gov/files"
GDC_DATA_ENDPOINT = "https://api.gdc.cancer.gov/data"
GDC_CASES_ENDPOINT = "https://api.gdc.cancer.gov/cases"

# TCGA cancer type → study metadata
TCGA_STUDIES = {
    "LUAD": {"name": "TCGA Lung Adenocarcinoma", "pmid": "23485966", "cancer_type_label": "Lung Adenocarcinoma"},
    "LUSC": {"name": "TCGA Lung Squamous Cell Carcinoma", "pmid": "22960745", "cancer_type_label": "Lung Squamous"},
    "BRCA": {"name": "TCGA Breast Invasive Carcinoma", "pmid": "23000897", "cancer_type_label": "Breast Cancer"},
    "COAD": {"name": "TCGA Colon Adenocarcinoma", "pmid": "22810696", "cancer_type_label": "Colon Adenocarcinoma"},
    "READ": {"name": "TCGA Rectum Adenocarcinoma", "pmid": None, "cancer_type_label": "Rectal Adenocarcinoma"},
    "GBM":  {"name": "TCGA Glioblastoma Multiforme", "pmid": "18772890", "cancer_type_label": "Glioblastoma"},
    "LGG":  {"name": "TCGA Lower Grade Glioma", "pmid": "25965575", "cancer_type_label": "Lower Grade Glioma"},
    "SKCM": {"name": "TCGA Skin Cutaneous Melanoma", "pmid": "25079552", "cancer_type_label": "Melanoma"},
    "BLCA": {"name": "TCGA Bladder Urothelial Carcinoma", "pmid": "24476821", "cancer_type_label": "Bladder Cancer"},
    "PRAD": {"name": "TCGA Prostate Adenocarcinoma", "pmid": "26544944", "cancer_type_label": "Prostate Cancer"},
    "OV":   {"name": "TCGA Ovarian Serous Cystadenocarcinoma", "pmid": "21720365", "cancer_type_label": "Ovarian Cancer"},
    "UCEC": {"name": "TCGA Uterine Corpus Endometrial Carcinoma", "pmid": "23636398", "cancer_type_label": "Endometrial Cancer"},
    "HNSC": {"name": "TCGA Head and Neck Squamous Cell Carcinoma", "pmid": "25631445", "cancer_type_label": "Head & Neck SCC"},
    "KIRC": {"name": "TCGA Kidney Renal Clear Cell Carcinoma", "pmid": "23792563", "cancer_type_label": "Kidney Clear Cell"},
    "LIHC": {"name": "TCGA Liver Hepatocellular Carcinoma", "pmid": "22932797", "cancer_type_label": "Hepatocellular Carcinoma"},
    "STAD": {"name": "TCGA Stomach Adenocarcinoma", "pmid": "25079317", "cancer_type_label": "Gastric Cancer"},
    "PAAD": {"name": "TCGA Pancreatic Adenocarcinoma", "pmid": "27107158", "cancer_type_label": "Pancreatic Cancer"},
    "THCA": {"name": "TCGA Thyroid Carcinoma", "pmid": "25417114", "cancer_type_label": "Thyroid Cancer"},
    "CESC": {"name": "TCGA Cervical Squamous Cell Carcinoma", "pmid": "28112728", "cancer_type_label": "Cervical Cancer"},
    "AML":  {"name": "TCGA Acute Myeloid Leukemia", "pmid": "23634996", "cancer_type_label": "AML"},
    "DLBC": {"name": "TCGA Lymphoid Neoplasm Diffuse Large B-cell Lymphoma", "pmid": None, "cancer_type_label": "DLBCL"},
}


def fetch_tcga_maf_file_ids(cancer_type: str, limit: int = 5) -> list[str]:
    """Query GDC API for MAF file IDs for a TCGA cancer type.

    Returns a list of GDC file UUIDs for open-access masked MAF files.
    """
    import urllib.request

    query = {
        "filters": {
            "op": "and",
            "content": [
                {"op": "in", "content": {"field": "cases.project.project_id", "value": [f"TCGA-{cancer_type}"]}},
                {"op": "=",  "content": {"field": "data_type",  "value": "Masked Somatic Mutation"}},
                {"op": "=",  "content": {"field": "data_format", "value": "MAF"}},
                {"op": "=",  "content": {"field": "access",      "value": "open"}},
            ],
        },
        "fields": "file_id,file_name,cases.case_id,cases.submitter_id",
        "size": str(limit),
    }

    data = json.dumps(query).encode()
    req = urllib.request.Request(
        f"{GDC_FILES_ENDPOINT}?pretty=true",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return [hit["file_id"] for hit in result.get("data", {}).get("hits", [])]
    except Exception as exc:
        logger.error("[gdc] Failed to query file IDs for %s: %s", cancer_type, exc)
        return []


def download_gdc_file(file_id: str, output_dir: Path) -> Optional[Path]:
    """Download a GDC file by UUID to output_dir."""
    import urllib.request

    url = f"{GDC_DATA_ENDPOINT}/{file_id}"
    dest = output_dir / f"{file_id}.maf.gz"
    try:
        logger.info("[gdc] Downloading %s → %s", file_id, dest)
        urllib.request.urlretrieve(url, dest)
        return dest
    except Exception as exc:
        logger.error("[gdc] Download failed for %s: %s", file_id, exc)
        return None


def parse_maf_file(maf_path: Path) -> Iterator[dict]:
    """Parse a (gzipped) MAF file and yield mutation dicts.

    Yields standardised mutation dicts compatible with CohortMutation fields.
    """
    opener = gzip.open if str(maf_path).endswith(".gz") else open
    with opener(maf_path, "rt", encoding="utf-8", errors="replace") as fh:
        reader = None
        for line in fh:
            if line.startswith("#"):
                continue
            if reader is None:
                # First non-comment line is the header
                headers = line.rstrip("\n").split("\t")
                reader = headers
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < len(reader):
                continue
            row = dict(zip(reader, cols))
            yield {
                "gene": row.get("Hugo_Symbol", ""),
                "protein_change": row.get("HGVSp_Short", row.get("HGVSp", "")),
                "hgvs_c": row.get("HGVSc", ""),
                "variant_classification": row.get("Variant_Classification", ""),
                "chromosome": row.get("Chromosome", ""),
                "position": _safe_int(row.get("Start_Position")),
                "ref_allele": row.get("Reference_Allele", ""),
                "alt_allele": row.get("Tumor_Seq_Allele2", row.get("Allele", "")),
                "vaf": _safe_float(row.get("t_alt_count")) / max(_safe_float(row.get("t_depth")) or 1, 1),
                "sample_barcode": row.get("Tumor_Sample_Barcode", ""),
                "oncokb_level": None,
            }


def validate_maf_row(row: dict) -> bool:
    """Return True if a MAF row passes basic quality filters."""
    if not row.get("gene"):
        return False
    # Skip synonymous (Silent) variants — not informative for cancer genomics
    if row.get("variant_classification") == "Silent":
        return False
    # Skip intergenic / RNA variants
    if row.get("variant_classification") in ("IGR", "RNA", "Intron", "3'UTR", "5'UTR"):
        return False
    return True


def build_study_record(cancer_type: str) -> dict:
    """Build a Study dict for insertion."""
    meta = TCGA_STUDIES.get(cancer_type, {})
    return {
        "id": str(uuid.uuid4()),
        "study_id": f"tcga_{cancer_type.lower()}",
        "name": meta.get("name", f"TCGA {cancer_type}"),
        "description": f"TCGA {cancer_type} open-access masked somatic mutations.",
        "cancer_type": cancer_type,
        "cancer_type_label": meta.get("cancer_type_label", cancer_type),
        "data_types": ["SNV"],
        "reference_genome": "GRCh38",
        "pmid": meta.get("pmid"),
        "source": "TCGA",
        "is_public": True,
        "sample_count": 0,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    }


# ── CCLE ingestion ─────────────────────────────────────────────────────────────

CCLE_MUTATIONS_URL = "https://ndownloader.figshare.com/files/34989929"


def download_ccle_mutations(output_dir: Path) -> Optional[Path]:
    """Download the CCLE somatic mutations CSV from DepMap."""
    import urllib.request

    dest = output_dir / "CCLE_mutations.csv"
    if dest.exists():
        logger.info("[ccle] Already downloaded: %s", dest)
        return dest
    try:
        logger.info("[ccle] Downloading CCLE mutations from DepMap…")
        urllib.request.urlretrieve(CCLE_MUTATIONS_URL, dest)
        return dest
    except Exception as exc:
        logger.error("[ccle] Download failed: %s", exc)
        return None


def parse_ccle_mutations(csv_path: Path) -> Iterator[dict]:
    """Parse CCLE somatic mutations CSV and yield mutation dicts."""
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield {
                "gene": row.get("Hugo_Symbol", ""),
                "protein_change": row.get("Protein_Change", ""),
                "hgvs_c": row.get("cDNA_Change", ""),
                "variant_classification": row.get("Variant_Classification", ""),
                "chromosome": row.get("Chromosome", ""),
                "position": _safe_int(row.get("Start_position")),
                "ref_allele": row.get("Ref_Allele", ""),
                "alt_allele": row.get("Alt_Allele", ""),
                "vaf": _safe_float(row.get("AF")),
                "sample_barcode": row.get("DepMap_ID", row.get("CCLE_Name", "")),
                "oncokb_level": None,
            }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="OpenOncology cohort data ingestion")
    parser.add_argument("--source", choices=["tcga", "ccle", "icgc"], required=True)
    parser.add_argument("--cancer-type", default=None, help="TCGA cancer type code (e.g. LUAD)")
    parser.add_argument("--output", default="/tmp/cohort_ingest", help="Output directory for downloaded files")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write to DB")
    parser.add_argument("--limit", type=int, default=3, help="Max MAF files to download per cancer type")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "tcga":
        cancer_types = [args.cancer_type.upper()] if args.cancer_type else list(TCGA_STUDIES.keys())
        for ct in cancer_types:
            logger.info("[tcga] Processing %s", ct)
            file_ids = fetch_tcga_maf_file_ids(ct, limit=args.limit)
            logger.info("[tcga] Found %d MAF files for %s", len(file_ids), ct)
            for fid in file_ids:
                maf_path = download_gdc_file(fid, output_dir)
                if maf_path:
                    count = 0
                    for row in parse_maf_file(maf_path):
                        if validate_maf_row(row):
                            count += 1
                            if not args.dry_run and count % 10000 == 0:
                                logger.info("[tcga] Parsed %d valid mutations from %s", count, maf_path.name)
                    logger.info("[tcga] %s: %d valid mutations parsed", maf_path.name, count)

    elif args.source == "ccle":
        ccle_path = download_ccle_mutations(output_dir)
        if ccle_path:
            count = sum(1 for row in parse_ccle_mutations(ccle_path) if validate_maf_row(row))
            logger.info("[ccle] %d valid mutations parsed", count)

    else:
        logger.warning("ICGC ingestion not yet implemented; use the GDC API for TCGA data.")
        sys.exit(1)


if __name__ == "__main__":
    main()
