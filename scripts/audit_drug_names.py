"""Audit: can evidence be reached when a drug is named the way it was
prescribed rather than by its INN?

Nothing mapped trade names, so lookup_oncokb_level("ERBB2", "Amplification",
"Herceptin") returned None while the same call with "trastuzumab" returned
LEVEL_1. A sweep of 20 common oncology trade names found all 20 unreachable.

This matters twice over. Clinical records and prescriptions carry trade names,
and so do TCGA's treatment fields, which is what the concordance benchmark
scores our recommendations against. An unmapped trade name there scores a miss
on a case we actually got right, so it understates accuracy rather than
overstating it.

Usage:
    python scripts/audit_drug_names.py
"""
import sys
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "audit-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services.oncokb_evidence import (  # noqa: E402
    _DRUG_BRAND_ALIASES,
    _known_table_drugs,
    _normalise_drug,
    lookup_oncokb_level,
)

# (trade name, INN, gene, alteration)
PROBES = [
    ("Herceptin", "trastuzumab", "ERBB2", "Amplification"),
    ("Enhertu", "trastuzumab deruxtecan", "ERBB2", "Amplification"),
    ("Tagrisso", "osimertinib", "EGFR", "T790M"),
    ("Iressa", "gefitinib", "EGFR", "L858R"),
    ("Tarceva", "erlotinib", "EGFR", "L858R"),
    ("Gleevec", "imatinib", "KIT", "EXON11MUT"),
    ("Glivec", "imatinib", "KIT", "EXON11MUT"),
    ("Zelboraf", "vemurafenib", "BRAF", "V600E"),
    ("Tafinlar", "dabrafenib", "BRAF", "V600E"),
    ("Mekinist", "trametinib", "BRAF", "V600E"),
    ("Xalkori", "crizotinib", "ALK", "EML4-ALK"),
    ("Alecensa", "alectinib", "ALK", "EML4-ALK"),
    ("Lumakras", "sotorasib", "KRAS", "G12C"),
    ("Lynparza", "olaparib", "BRCA1", "S1982fs"),
    ("Piqray", "alpelisib", "PIK3CA", "H1047R"),
    ("Sutent", "sunitinib", "KIT", "EXON11MUT"),
    ("Rybrevant", "amivantamab", "EGFR", "EXON20INS"),
    ("Tabrecta", "capmatinib", "MET", "EXON14SKIP"),
    ("Retevmo", "selpercatinib", "RET", "FUSION"),
    ("Vitrakvi", "larotrectinib", "NTRK1", "FUSION"),
]


def main() -> None:
    print("=" * 76)
    print("DRUG TRADE NAME REACHABILITY")
    print("=" * 76)
    print()

    unreachable, skipped = [], []
    for brand, inn, gene, alteration in PROBES:
        canonical = lookup_oncokb_level(gene, alteration, inn)
        if canonical is None:
            skipped.append((brand, inn))
            continue
        got = lookup_oncokb_level(gene, alteration, brand)
        ok = got == canonical
        if not ok:
            unreachable.append((brand, inn, canonical))
        print("  %s %-12s -> %-24s %-7s %-14s inn=%s brand=%s"
              % ("ok  " if ok else "MISS", brand, inn, gene, alteration,
                 canonical, got))

    print()
    print("unreachable: %d of %d comparable"
          % (len(unreachable), len(PROBES) - len(skipped)))
    for brand, inn, level in unreachable:
        print("   %-12s should resolve as %-22s (%s)" % (brand, inn, level))
    if skipped:
        print("skipped, the INN itself has no level for that alteration: %s"
              % ", ".join(b for b, _i in skipped))

    print()
    print("=" * 76)
    print("SAFETY")
    print("=" * 76)
    table_drugs = _known_table_drugs()
    shadowed = [k for k in _DRUG_BRAND_ALIASES if k in table_drugs]
    drifted = [d for d in table_drugs if _normalise_drug(d) != d]
    dangling = sorted({
        v for v in _DRUG_BRAND_ALIASES.values()
        if _normalise_drug(v) not in table_drugs
    })
    print("  trade names shadowing a real table drug : %s" % (shadowed or "none"))
    print("  table drugs not resolving to themselves : %s" % (drifted or "none"))
    print("  aliases whose INN the table lacks       : %d" % len(dangling))
    if dangling:
        print("    harmless, they resolve to a name with no evidence exactly as")
        print("    before, and are correct for when those drugs are curated:")
        print("    %s" % ", ".join(dangling))


if __name__ == "__main__":
    main()
