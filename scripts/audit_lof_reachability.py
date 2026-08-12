"""Audit: which genes carry loss-of-function evidence that real-world
truncating variant notation cannot actually reach?

The BRCA1/2 bug was not a one-off. ("BRCA2","TRUNCATING") held LEVEL_1 PARP
evidence that only an exact literal key could reach, so real HGVS frameshift
and nonsense variants returned nothing. Tumour suppressors are inactivated
precisely by that class of variant, so any gene with a TRUNCATING / LOSS /
LOSSOFFUNCTION / PATHOGENIC bucket is a candidate for the same defect.

For each such gene this probes a representative frameshift and nonsense variant
and reports whether the curated evidence is reachable. It asserts nothing about
what the evidence should be -- it only checks whether what is already curated
can be retrieved.
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

LOF_KEYS = {"TRUNCATING", "LOSS", "LOSSOFFUNCTION", "DELETION", "PATHOGENIC",
            "INACTIVATING", "LOF"}

genes = defaultdict(set)
for (gene, alt) in _LEVEL_TABLE:
    a = str(alt).upper().replace("_", "").replace("-", "")
    if a in LOF_KEYS:
        genes[gene].add(str(alt))

print("=" * 76)
print("LOSS-OF-FUNCTION REACHABILITY AUDIT")
print("Genes whose curated LOF evidence real-world notation may not reach")
print("=" * 76)
print()

broken, ok = [], []
for gene in sorted(genes):
    # Representative real-world truncating variants. Position is arbitrary and
    # deliberately not tuned per gene.
    probes = ["Q500*", "R500fs", "W500X", "Q500fs*12"]
    hits = {}
    for p in probes:
        try:
            r = get_all_drugs_for_variant(gene, p) or {}
        except Exception:
            r = {}
        hits[p] = len(r)
    reachable = any(v > 0 for v in hits.values())
    # What the curated bucket itself returns when addressed directly.
    direct = {}
    for key in genes[gene]:
        try:
            direct = get_all_drugs_for_variant(gene, key) or {}
        except Exception:
            direct = {}
        if direct:
            break
    if direct and not reachable:
        broken.append((gene, sorted(genes[gene]), list(direct)[:4]))
    elif direct and reachable:
        ok.append(gene)

print("UNREACHABLE -- curated LOF evidence exists but truncating notation fails")
print("-" * 76)
for gene, keys, drugs in broken:
    print("  %-9s keys=%-28s evidence: %s" % (gene, ",".join(keys)[:28], ", ".join(drugs)))
print()
print("  total unreachable: %d genes" % len(broken))
print()
print("REACHABLE (already working): %d genes -- %s" % (len(ok), ", ".join(ok)))
