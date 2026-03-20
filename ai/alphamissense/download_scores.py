"""
Download and import the AlphaMissense pre-computed scores into a SQLite DB.

Source: https://zenodo.org/records/8208688
File:   AlphaMissense_hg38.tsv.gz (~3.6 GB download, ~8 GB uncompressed)

Usage:
    python ai/alphamissense/download_scores.py [--tsv /path/to/existing.tsv.gz]

After running, scores.db (~2–3 GB) is created next to this script.
The SQLite DB uses an indexed table for fast (< 1 ms) lookups.
"""

from __future__ import annotations

import argparse
import gzip
import logging
import sqlite3
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ZENODO_URL = (
    "https://zenodo.org/records/8208688/files/AlphaMissense_hg38.tsv.gz?download=1"
)
HERE = Path(__file__).parent
TSV_GZ = HERE / "alphamissense_hg38.tsv.gz"
DB = HERE / "scores.db"
BATCH_SIZE = 50_000


def download(url: str, dest: Path) -> None:
    logger.info("Downloading %s → %s", url, dest)
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        while chunk := resp.read(1 << 20):  # 1 MB chunks
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r  {pct:.1f}% ({downloaded // 1_048_576} MB)", end="", flush=True)
    print()


def import_tsv(tsv_gz: Path, db: Path) -> None:
    logger.info("Importing %s → %s", tsv_gz, db)

    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            uniprot_id      TEXT NOT NULL,
            protein_variant TEXT NOT NULL,
            am_pathogenicity REAL NOT NULL,
            am_class        TEXT NOT NULL,
            PRIMARY KEY (uniprot_id, protein_variant)
        )
        """
    )
    con.execute("DELETE FROM scores")  # idempotent re-import

    batch: list[tuple] = []
    total = 0

    with gzip.open(tsv_gz, "rt", encoding="utf-8") as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                continue
            if header is None:
                header = line.split("\t")
                # Expected: uniprot_id, transcript_id, protein_variant,
                #           am_pathogenicity, am_class
                continue

            cols = line.split("\t")
            if len(cols) < 5:
                continue

            uniprot_id = cols[0]
            protein_variant = cols[2]
            am_pathogenicity = float(cols[3])
            am_class = cols[4]

            batch.append((uniprot_id, protein_variant, am_pathogenicity, am_class))

            if len(batch) >= BATCH_SIZE:
                con.executemany(
                    "INSERT OR REPLACE INTO scores VALUES (?,?,?,?)", batch
                )
                con.commit()
                total += len(batch)
                batch.clear()
                print(f"\r  {total:,} rows imported", end="", flush=True)

    if batch:
        con.executemany("INSERT OR REPLACE INTO scores VALUES (?,?,?,?)", batch)
        con.commit()
        total += len(batch)

    print(f"\n  Total: {total:,} rows")

    logger.info("Creating index…")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_scores_uniprot ON scores (uniprot_id)"
    )
    con.commit()
    con.close()
    logger.info("Done. DB size: %.1f GB", db.stat().st_size / 1_073_741_824)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and import AlphaMissense scores")
    parser.add_argument(
        "--tsv",
        type=Path,
        default=None,
        help="Path to existing AlphaMissense_hg38.tsv.gz (skip download)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB,
        help=f"Output SQLite database path (default: {DB})",
    )
    args = parser.parse_args()

    tsv = args.tsv or TSV_GZ
    if not tsv.exists():
        download(ZENODO_URL, tsv)

    if not tsv.exists():
        logger.error("TSV file not found: %s", tsv)
        sys.exit(1)

    import_tsv(tsv, args.db)


if __name__ == "__main__":
    main()
