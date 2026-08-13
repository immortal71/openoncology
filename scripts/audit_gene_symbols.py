"""Audit: can evidence be reached when a report names a gene the way
clinicians name it rather than the way HGNC does?

The evidence table keys on HGNC-approved symbols. Nothing normalised the
incoming symbol, so "HER2 Amplification" returned nothing while "ERBB2
Amplification" returned 8 drugs including trastuzumab. HER2 is how HER2 status
is written in essentially every breast and gastric pathology report, so this
was not an edge case.

Same failure mode as the LOF, fusion and copy-number audits: the evidence is
curated and correct, the notation reaching it is not, and an unrecognised
symbol is indistinguishable from a gene with no evidence.

Usage:
    python scripts/audit_gene_symbols.py
"""
import sys
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "audit-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services.oncokb_evidence import (  # noqa: E402
    _GENE_ALIASES,
    _LEVEL_TABLE,
    _normalise_gene,
    get_all_drugs_for_variant,
)

# (symbol as written in reports, HGNC symbol, representative alteration)
PROBES = [
    ("HER2", "ERBB2", "Amplification"),
    ("HER-2", "ERBB2", "Amplification"),
    ("HER2/neu", "ERBB2", "Amplification"),
    ("NEU", "ERBB2", "Amplification"),
    ("HER1", "EGFR", "L858R"),
    ("ERBB1", "EGFR", "L858R"),
    ("HER3", "ERBB3", "Amplification"),
    ("c-KIT", "KIT", "V559D"),
    ("CKIT", "KIT", "V559D"),
    ("CD117", "KIT", "V559D"),
    ("MLL", "KMT2A", "KMT2A-MLLT3"),
    ("PD-L1", "CD274", "Amplification"),
    ("PDL1", "CD274", "Amplification"),
    ("B7-H1", "CD274", "Amplification"),
    ("c-MET", "MET", "exon 14 skipping"),
    ("HGFR", "MET", "exon 14 skipping"),
    ("BRG1", "SMARCA4", "Q729fs"),
    ("BAF250A", "ARID1A", "Q1334*"),
    ("TRKA", "NTRK1", "TPM3-NTRK1"),
    ("K-RAS", "KRAS", "G12C"),
    ("B-RAF", "BRAF", "V600E"),
    ("ABL", "ABL1", "T315I"),
    ("FLT-3", "FLT3", "ITD"),
    ("p16", "CDKN2A", "homozygous deletion"),
    ("INK4A", "CDKN2A", "homozygous deletion"),
    ("MMAC1", "PTEN", "R130Q"),
]


def main() -> None:
    print("=" * 76)
    print("GENE SYMBOL REACHABILITY")
    print("=" * 76)
    print()

    unreachable, skipped = [], []
    for legacy, hgnc, alteration in PROBES:
        canonical = get_all_drugs_for_variant(hgnc, alteration) or {}
        if not canonical:
            skipped.append((legacy, hgnc, alteration))
            continue
        got = get_all_drugs_for_variant(legacy, alteration) or {}
        ok = got == canonical
        if not ok:
            unreachable.append((legacy, hgnc, len(canonical)))
        print("  %s %-10s -> %-8s %-22s canonical=%d got=%d"
              % ("ok  " if ok else "MISS", legacy, hgnc, alteration,
                 len(canonical), len(got)))

    print()
    print("unreachable: %d of %d probed" % (len(unreachable), len(PROBES)))
    for legacy, hgnc, n in unreachable:
        print("   %-10s should resolve as %-8s (%d drugs lost)" % (legacy, hgnc, n))

    if skipped:
        print()
        print("skipped, the HGNC gene itself has no evidence to compare against:")
        for legacy, hgnc, alteration in skipped:
            print("   %-10s (%s %s)" % (legacy, hgnc, alteration))

    # Regression guards. An alias that shadows a real symbol silently redirects
    # every lookup for it, which is how H3-3A broke: stripping punctuation
    # turned the approved symbol into H33A. Some HGNC symbols do contain a
    # hyphen, the histone genes having been renamed in 2021.
    print()
    print("=" * 76)
    print("SAFETY")
    print("=" * 76)
    table_genes = {g for (g, _a) in _LEVEL_TABLE}
    shadowed = [k for k in _GENE_ALIASES if k in table_genes and _GENE_ALIASES[k] != k]
    drifted = [g for g in table_genes if _normalise_gene(g) != g]
    print("  alias keys shadowing a real table gene : %s" % (shadowed or "none"))
    print("  table genes not resolving to themselves: %s" % (drifted or "none"))


if __name__ == "__main__":
    main()
