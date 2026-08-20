"""A biomarker-to-drug answer key built from FDA labels, not from our evidence.

WHY THIS EXISTS
---------------
Every answer key this repository has used to judge drug ranking is contaminated
by the thing being judged.

  * build_concordance_labels.py derived the biomarker from the drug, so it could
    not fail. Retracted (risk_analysis.md F5).
  * The ranking gate's gold cases are OncoKB-derived, and
    validate_ranking_precision.py records that 94.5% of them have their expected
    drugs already inside the evidence table being scored.
  * NCI-MATCH is genuinely independent of our output, but only 15 of its 32
    scored arms fall outside the evidence table, and an A/B needs more than that.

That last point is what forced this. ab_candidate_pool.py tried to settle which
candidate pool production should use, and could not: 88.3% of the gold cases
leak in a direction that favours one of the two arms, and the clean subset was 8
cases. The comparison was not underpowered by accident, it was underpowered
because no uncontaminated case set existed.

WHERE THIS KEY COMES FROM
-------------------------
FDA drug labels, via openFDA, section INDICATIONS AND USAGE. A label states the
biomarker that selects patients for the drug, in the regulator's own words:

    TAGRISSO is a kinase inhibitor indicated for ... non-small cell lung cancer
    whose tumors have epidermal growth factor receptor (EGFR) exon 19 deletions
    or exon 21 L858R mutations, as detected by an FDA-approved test.

That is exactly the biomarker-drove-the-drug relationship the engine claims to
model, and openFDA is used nowhere in the recommendation path. The engine reads
OncoKB, OpenTargets, DGIdb and CIViC; it does not read drug labels. So a key
built here is independent of all four.

It is also the strongest form of the claim available. An FDA label is not a
database curator's opinion about actionability, it is the indication a regulator
approved.

HOW GENES ARE EXTRACTED, AND WHAT THAT COSTS
--------------------------------------------
Symbols are matched case-sensitively, on word boundaries, against an explicit
list held in this file rather than against the engine's gene vocabulary. Using
the engine's vocabulary would bias which genes are detectable toward the ones it
already knows, which is a smaller leak than the ones above but the same kind.

Case sensitivity does most of the work: label prose writes gene symbols in
capitals, so requiring uppercase separates the ALK gene from "alkaline" and the
KIT gene from ordinary usage. It is not perfect. MET and AR remain the risky
symbols and are handled by requiring an adjacent qualifier.

READ THIS BEFORE USING THE KEY
------------------------------
* A gene named in an indications section is not always the selecting biomarker.
  Labels also name genes in resistance statements and exclusions. Every pairing
  is emitted with the sentence it came from so a human can audit it, and the
  extraction is deliberately conservative rather than complete.
* Absence means the label did not name a gene this script recognises. It does
  not mean the drug has no biomarker.
* This measures agreement with an approved indication. It says nothing about
  patient outcome, which no benchmark here measures.

Usage:
    python scripts/build_fda_label_answer_key.py
    python scripts/build_fda_label_answer_key.py --limit 40 --out key.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_OUT = _REPO_ROOT / "validation_results" / "fda_label_answer_key.json"

# Oncology drugs to look up. Names only, and deliberately not sourced from the
# engine's candidate pool: a drug list drawn from what the engine can recommend
# would quietly restrict the key to drugs it already knows.
_DRUGS = """
osimertinib erlotinib gefitinib afatinib dacomitinib mobocertinib amivantamab
alectinib crizotinib brigatinib ceritinib lorlatinib entrectinib repotrectinib
dabrafenib vemurafenib encorafenib trametinib binimetinib cobimetinib selumetinib
trastuzumab pertuzumab lapatinib neratinib tucatinib
olaparib niraparib rucaparib talazoparib
palbociclib ribociclib abemaciclib
alpelisib capivasertib inavolisib everolimus temsirolimus
imatinib sunitinib regorafenib ripretinib avapritinib dasatinib nilotinib
erdafitinib pemigatinib infigratinib futibatinib
larotrectinib
sotorasib adagrasib
ivosidenib enasidenib olutasidenib
venetoclax ibrutinib acalabrutinib zanubrutinib
midostaurin gilteritinib quizartinib
vismodegib sonidegib glasdegib
pembrolizumab nivolumab atezolizumab durvalumab dostarlimab
selpercatinib pralsetinib capmatinib tepotinib
tazemetostat belzutifan mobocertinib tebentafusp
""".split()

# Gene symbols recognised in label text. Explicit rather than derived, so the
# key's vocabulary is auditable and does not track the engine's.
_GENES = [
    "EGFR", "ALK", "ROS1", "BRAF", "KRAS", "NRAS", "HRAS", "MEK", "ERBB2",
    "HER2", "PIK3CA", "AKT1", "PTEN", "MTOR", "TSC1", "TSC2", "BRCA1", "BRCA2",
    "PALB2", "ATM", "CHEK2", "CDK4", "CDK6", "CCND1", "FGFR1", "FGFR2", "FGFR3",
    "FGFR4", "NTRK1", "NTRK2", "NTRK3", "RET", "MET", "KIT", "PDGFRA", "PDGFRB",
    "FLT3", "IDH1", "IDH2", "BCL2", "BTK", "ABL1", "BCR", "JAK2", "SMO", "PTCH1",
    "VHL", "EZH2", "SMARCB1", "MSI", "TMB", "NF1", "NF2", "DDR2", "GNAQ", "GNA11",
    "ESR1", "AR", "MYC", "ERBB3", "ERBB4",
]

# Symbols that are also ordinary words or abbreviations. Only counted when the
# sentence also carries one of these qualifiers.
_AMBIGUOUS = {
    "MET": ("exon 14", "amplif", "MET-", "c-MET", "mesenchymal"),
    "AR": ("androgen receptor",),
    "MEK": ("MEK1", "MEK2", "MAP2K"),
    "BCR": ("BCR-ABL", "Philadelphia"),
    "MSI": ("microsatellite",),
    "TMB": ("tumor mutational burden", "tumour mutational burden"),
}

# Label prose uses the clinical name; the evidence table uses the HUGO symbol.
_ALIASES = {"HER2": "ERBB2", "MEK": "MAP2K1"}

# A gene can be named as the reason to give a drug or as the reason not to.
_NEGATION_BEFORE = re.compile(
    r"(?:non[-\s]?|without\s+|negative\s+for\s+|absence\s+of\s+|lack\s+of\s+)$",
    re.IGNORECASE,
)
_NEGATIVE_AFTER = re.compile(
    # A leading ")" matters: labels write "(HER2)-negative", so the symbol match
    # ends inside the parenthesis and the close paren sits before the hyphen.
    r"^\s*\)?\s*(?:\([^)]*\))?\s*[-‐-―]?\s*(?:negative|wild[-\s]?type"
    r"|non[-\s]?mutated|unmutated|not\s+(?:mutated|detected|amplified))",
    re.IGNORECASE,
)

_SENTENCE = re.compile(r"[^.;•]+[.;•]?")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.findall(text or "") if s.strip()]


def _is_negated(sentence: str, match: re.Match) -> bool:
    """True when the sentence names this gene as an exclusion, not a selector.

    "HER2-negative advanced breast cancer" selects patients who do NOT carry the
    marker. Recording that as a positive pairing penalises the engine for being
    right, and the first build of this key did exactly that: everolimus,
    palbociclib, ribociclib and talazoparib were all paired with ERBB2 purely on
    the strength of "HER2-negative".
    """
    before = sentence[max(0, match.start() - 24) : match.start()]
    after = sentence[match.end() : match.end() + 40]
    return bool(_NEGATION_BEFORE.search(before) or _NEGATIVE_AFTER.match(after))


def _genes_in(sentence: str) -> set[str]:
    """Genes this sentence names as a positive selection criterion."""
    found = set()
    for gene in _GENES:
        matches = list(re.finditer(rf"\b{re.escape(gene)}\b", sentence))
        if not matches:
            continue
        qualifiers = _AMBIGUOUS.get(gene)
        if qualifiers and not any(q.lower() in sentence.lower() for q in qualifiers):
            continue
        # Named only in negated form means it is an exclusion criterion.
        if all(_is_negated(sentence, m) for m in matches):
            continue
        found.add(_ALIASES.get(gene, gene))
    return found


async def _indications(drug: str) -> str:
    from services.openfda import get_drug_label_indications

    try:
        sections = await get_drug_label_indications(drug)
    except Exception as exc:
        print(f"    {drug}: {type(exc).__name__} {exc}", file=sys.stderr)
        return ""
    return " ".join(sections or [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    drugs = sorted(set(_DRUGS))
    if args.limit:
        drugs = drugs[: args.limit]
    print(f"  {len(drugs)} drugs, reading INDICATIONS AND USAGE from openFDA\n")

    by_gene: dict[str, set[str]] = {}
    evidence: list[dict] = []
    no_label, no_gene = [], []

    for i, drug in enumerate(drugs, 1):
        text = asyncio.run(_indications(drug))
        if not text:
            no_label.append(drug)
            continue
        hits: dict[str, str] = {}
        for sentence in _sentences(text):
            for gene in _genes_in(sentence):
                hits.setdefault(gene, sentence[:300])
        if not hits:
            no_gene.append(drug)
            continue
        for gene, sentence in hits.items():
            by_gene.setdefault(gene, set()).add(drug)
            evidence.append({"gene": gene, "drug": drug, "sentence": sentence})
        print(f"  [{i:>3}] {drug:<16} -> {', '.join(sorted(hits))}", flush=True)

    key = {g: sorted(d) for g, d in sorted(by_gene.items())}
    payload = {
        "answer_key": "fda_label_biomarker_to_drug",
        "source": "openFDA drug label, INDICATIONS AND USAGE",
        "independent_of": [
            "OncoKB (evidence table and live API)",
            "OpenTargets",
            "DGIdb",
            "CIViC",
        ],
        "why_independent": (
            "openFDA is not queried anywhere in the recommendation path. The "
            "engine reads OncoKB, OpenTargets, DGIdb and CIViC; it does not read "
            "drug labels."
        ),
        "drugs_queried": len(drugs),
        "drugs_with_no_label": sorted(no_label),
        "drugs_with_no_recognised_gene": sorted(no_gene),
        "genes": len(key),
        "pairs": sum(len(v) for v in key.values()),
        "key": key,
        "evidence": evidence,
        "caveats": [
            "A gene named in an indications section is not always the selecting "
            "biomarker; labels also name genes in resistance and exclusion "
            "statements. Every pairing carries its source sentence for audit.",
            "Absence means no recognised gene was named, not that the drug has "
            "no biomarker.",
            "Agreement with an approved indication says nothing about patient "
            "outcome.",
        ],
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"  genes: {payload['genes']}   gene-drug pairs: {payload['pairs']}")
    print(f"  no label: {len(no_label)}   label without a recognised gene: {len(no_gene)}")
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
