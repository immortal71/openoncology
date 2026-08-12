"""Audit: can real-world copy-number notation reach the curated CNV evidence?

Same question the LOF audit asked, pointed at the other half of the table.
The BRCA1/2 defect was that ("BRCA2","TRUNCATING") held LEVEL_1 evidence only
an exact literal key could reach, so real HGVS frameshift notation returned
nothing. Amplification and deletion buckets are stored the same way, as literal
keys like ("ERBB2","AMPLIFICATION"), which makes them candidates for the same
failure.

Copy-number calls arrive in more spellings than point mutations do, because
there is no equivalent of HGVS that everyone follows. cBioPortal says
"Amplification", GISTIC output gets rendered as "amp", pathology reports say
"HER2 amplified" or "copy number gain", ISCN says "amp(17)(q12)". Any of those
that fails to resolve is a silently dropped patient: an unrecognised
amplification looks exactly like a gene with no amplification evidence.

This asserts nothing about what the evidence ought to be. It only checks
whether what is already curated can be retrieved.

Usage:
    python scripts/audit_cnv_reachability.py
"""
import sys
import os
from collections import defaultdict

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "audit-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services.oncokb_evidence import _LEVEL_TABLE, get_all_drugs_for_variant  # noqa: E402

# Canonical bucket names as stored in the table.
AMP_KEYS = {"AMPLIFICATION", "AMPLIFIED", "AMP", "GAIN", "COPYNUMBERGAIN"}
DEL_KEYS = {"DELETION", "DELETED", "HOMDEL", "HOMOZYGOUSDELETION",
            "COPYNUMBERLOSS", "LOSS"}

# How the same call actually turns up in submitted data.
AMP_PROBES = [
    "Amplification",           # cBioPortal / OncoKB canonical
    "AMPLIFICATION",
    "amplification",
    "amplified",               # pathology report phrasing
    "Amplified",
    "amp",                     # GISTIC / CNV caller shorthand
    "AMP",
    "gain",                    # copy-number caller
    "copy number gain",
    "copy_number_gain",
    "high level amplification",
]
DEL_PROBES = [
    "Deletion",
    "DELETION",
    "deletion",
    "deleted",
    "del",
    "homozygous deletion",
    "homdel",
    "HOMDEL",
    "deep deletion",
    "copy number loss",
    "copy_number_loss",
    "loss",
]


def _probe(gene: str, alteration: str) -> int:
    try:
        return len(get_all_drugs_for_variant(gene, alteration) or {})
    except Exception:
        return 0


def audit(label: str, bucket_keys: set[str], probes: list[str]) -> None:
    genes: defaultdict[str, set] = defaultdict(set)
    for (gene, alt) in _LEVEL_TABLE:
        normalised = str(alt).upper().replace("_", "").replace("-", "").replace(" ", "")
        if normalised in bucket_keys:
            genes[gene].add(str(alt))

    print("=" * 78)
    print(label)
    print("=" * 78)
    print()

    if not genes:
        print("  no genes carry this bucket\n")
        return

    # Which spellings work, aggregated across every gene that has the bucket.
    per_probe: dict[str, int] = {p: 0 for p in probes}
    unreachable: list[tuple[str, list[str], list[str]]] = []
    partial: list[tuple[str, list[str]]] = []

    for gene in sorted(genes):
        direct: dict = {}
        for key in sorted(genes[gene]):
            direct = get_all_drugs_for_variant(gene, key) or {}
            if direct:
                break
        if not direct:
            continue  # bucket exists but is empty; nothing to reach

        working = []
        for probe in probes:
            if _probe(gene, probe) > 0:
                per_probe[probe] += 1
                working.append(probe)

        if not working:
            unreachable.append((gene, sorted(genes[gene]), list(direct)[:4]))
        elif len(working) < len(probes):
            partial.append((gene, [p for p in probes if p not in working]))

    total = len([g for g in genes if get_all_drugs_for_variant(g, sorted(genes[g])[0])])

    print("SPELLING COVERAGE (genes resolved out of %d with curated evidence)" % total)
    print("-" * 78)
    for probe in probes:
        count = per_probe[probe]
        bar = "OK " if count == total else ("MISS" if count == 0 else "PART")
        print("  %-4s %-28s %d/%d" % (bar, repr(probe), count, total))
    print()

    print("UNREACHABLE by every spelling tried")
    print("-" * 78)
    if unreachable:
        for gene, keys, drugs in unreachable:
            print("  %-9s keys=%-24s evidence: %s"
                  % (gene, ",".join(keys)[:24], ", ".join(drugs)))
    else:
        print("  none")
    print()

    if partial:
        print("PARTIAL (resolves for some spellings, not others): %d genes" % len(partial))
        missing_counts: defaultdict[str, int] = defaultdict(int)
        for _gene, missing in partial:
            for m in missing:
                missing_counts[m] += 1
        for probe, count in sorted(missing_counts.items(), key=lambda kv: -kv[1]):
            print("    %-28s fails for %d gene(s)" % (repr(probe), count))
        print()


if __name__ == "__main__":
    audit("AMPLIFICATION REACHABILITY", AMP_KEYS, AMP_PROBES)
    audit("DELETION REACHABILITY", DEL_KEYS, DEL_PROBES)
