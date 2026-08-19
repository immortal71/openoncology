"""
NCI-MATCH concordance benchmark: does OpenOncology assign the same drug that
the NCI-MATCH molecular tumour board assigned for the same biomarker?

WHY THIS BENCHMARK EXISTS
-------------------------
The 2026-07-28 TCGA concordance pilot scored 15.1% exact Top-3
(docs/REAL_PATIENT_CONCORDANCE_PILOT_2026-07-28.md). That number is real, but
it is measured against an answer key where treatment was NOT chosen by the
patient's sequenced gene. In that dataset sunitinib was given to 20 TCGA-KIRC
patients spanning 16 different genes, and the top 5 drugs in TCGA-PRAD cover
10/10 patients. Those patients shared a diagnosis, not a gene. Scoring a
gene-to-drug engine against protocol care asks it to emit the same drug for 16
unrelated genes, which it can only do by ignoring the gene.

This benchmark uses an answer key where the biomarker provably DID drive the
drug: NCI-MATCH (EAY131, NCT02465060), the largest precision-oncology trial run
to date. Each subprotocol arm is an explicit, published, expert-committee
decision of the form "patients with biomarker X receive drug Y". That is the
same question OpenOncology answers, so it is a fair comparison.

NOT CIRCULAR
------------
The arm definitions are fetched live from ClinicalTrials.gov and parsed
mechanically. Nothing here is selected by checking what OpenOncology returns
first, and no variant is hand-picked for being one the evidence table is known
to handle. Contrast the old scripts/build_concordance_labels.py, whose
DRUG_BIOMARKER_MAP inferred each patient's gene FROM the drug they received --
which guaranteed a match and is why its 100% number was not usable as evidence.
That builder now joins sequencing and treatment records on patient id.

KNOWN LIMITATION -- READ BEFORE QUOTING THE NUMBER
--------------------------------------------------
NCI-MATCH arm assignments and this repo's OncoKB-derived evidence table are both
built from the same underlying body of published actionability literature. So
agreement is expected, and a high score here demonstrates that the evidence
table correctly ENCODES expert consensus actionability. It is not evidence of
independent discovery, and it is not a prospective outcome measure -- no patient
outcome is tested here, only drug-assignment agreement.

Usage:
    python scripts/benchmark_nci_match.py            # fetch + run
    python scripts/benchmark_nci_match.py --offline  # reuse cached arms
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from functools import lru_cache

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "api"))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "nci-match-benchmark-local-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

NCT_ID = "NCT02465060"
ARMS_CACHE = os.path.join(_REPO_ROOT, "validation_results", "nci_match_arms.json")
RESULTS_OUT = os.path.join(_REPO_ROOT, "validation_results", "nci_match_concordance.json")

# Drug-class equivalence. Same rationale and same groups as
# docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md: an arm assigning one drug in a
# class is clinically concordant with recommending another drug in that class
# for the same target. Reported SEPARATELY from exact match, never merged into it.
DRUG_CLASSES: dict[str, set[str]] = {
    "EGFR_TKI": {"afatinib", "erlotinib", "gefitinib", "osimertinib", "dacomitinib",
                 "amivantamab", "neratinib", "lapatinib"},
    "ALK_ROS1_MET_TKI": {"crizotinib", "alectinib", "brigatinib", "lorlatinib",
                         "ceritinib", "entrectinib", "capmatinib", "tepotinib"},
    "BRAF_INHIBITOR": {"dabrafenib", "vemurafenib", "encorafenib"},
    "MEK_INHIBITOR": {"trametinib", "binimetinib", "cobimetinib", "selumetinib"},
    "ERK_INHIBITOR": {"ulixertinib"},
    "PI3K_AKT_MTOR": {"taselisib", "copanlisib", "alpelisib", "inavolisib",
                      "capivasertib", "ipatasertib", "sapanisertib", "everolimus",
                      "temsirolimus", "gsk2636771"},
    "FGFR_INHIBITOR": {"erdafitinib", "azd4547", "pemigatinib", "infigratinib",
                       "futibatinib"},
    "HER2_DIRECTED": {"trastuzumab", "pertuzumab", "trastuzumab emtansine",
                      "ado-trastuzumab emtansine", "fam-trastuzumab deruxtecan",
                      "afatinib", "neratinib", "lapatinib", "tucatinib"},
    "KIT_PDGFRA_TKI": {"sunitinib", "imatinib", "regorafenib", "ripretinib",
                       "avapritinib", "dasatinib"},
    "HEDGEHOG": {"vismodegib", "sonidegib", "glasdegib"},
    "NTRK_INHIBITOR": {"larotrectinib", "entrectinib", "repotrectinib"},
    "CDK46_INHIBITOR": {"palbociclib", "ribociclib", "abemaciclib"},
    "CHECKPOINT": {"nivolumab", "pembrolizumab", "atezolizumab", "durvalumab",
                   "ipilimumab", "dostarlimab"},
    # PARP and WEE1 are NOT grouped together. Both act on the DNA-damage
    # response, but they are mechanistically distinct targets and a PARP
    # inhibitor is not a clinical substitute for a WEE1 inhibitor. They were
    # briefly grouped here, which silently converted the adavosertib arm (Z1I)
    # from a miss into a class hit once BRCA started resolving -- exactly the
    # "expand a class group to manufacture a hit" failure the doc warns about.
    "PARP_INHIBITOR": {"olaparib", "niraparib", "talazoparib", "rucaparib"},
    "WEE1_INHIBITOR": {"adavosertib"},
    "FAK_INHIBITOR": {"defactinib"},
}


def drug_class_of(drug: str) -> str | None:
    d = normalise_drug(drug)
    for cls, members in DRUG_CLASSES.items():
        if d in members:
            return cls
    return None


def normalise_drug(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(r"\(.*?\)", "", n)
    n = re.sub(
        r"\s+(mesylate|hydrochloride|dimaleate|maleate|acetate|tosylate|sodium"
        r"|disodium|malate|anhydrous|micronized|citrate|sulfate|phosphate|fumarate)\b",
        "", n)
    return re.sub(r"\s+", " ", n).strip()


# ---------------------------------------------------------------------------
# Arm fetching + mechanical parsing
# ---------------------------------------------------------------------------

def fetch_arms() -> list[dict]:
    import httpx
    r = httpx.get(f"https://clinicaltrials.gov/api/v2/studies/{NCT_ID}", timeout=60)
    r.raise_for_status()
    section = r.json()["protocolSection"]
    arms = section["armsInterventionsModule"]["armGroups"]
    os.makedirs(os.path.dirname(ARMS_CACHE), exist_ok=True)
    with open(ARMS_CACHE, "w", encoding="utf-8") as f:
        json.dump({"nct_id": NCT_ID, "arm_groups": arms}, f, indent=2)
    return arms


def load_arms(offline: bool) -> list[dict]:
    if offline and os.path.exists(ARMS_CACHE):
        with open(ARMS_CACHE, encoding="utf-8") as f:
            return json.load(f)["arm_groups"]
    return fetch_arms()


# Gene symbols appearing in NCI-MATCH arm labels, mapped to the symbol the
# evidence table uses. Purely a naming alignment -- no drug information here.
GENE_ALIASES = {"HER2": "ERBB2", "CKIT": "KIT", "AKT": "AKT1", "MTOR": "MTOR"}

# Some arms name a gene FAMILY rather than one gene ("FGFR amplification"
# covers FGFR1/2/3). "FGFR" is not itself a valid HUGO symbol, so querying it
# returns nothing and the arm scores as a false NO-PRED. Expand to the family
# members the arm actually refers to and take the first that resolves. This is
# faithful to the arm text, not a hand-picked substitution.
GENE_FAMILIES = {"FGFR": ["FGFR1", "FGFR2", "FGFR3"], "NTRK": ["NTRK1", "NTRK2", "NTRK3"]}


def parse_arm(arm: dict) -> dict | None:
    """Mechanically extract (arm_id, gene, alteration_text, drug) from one arm.

    Deliberately dumb: it reads the label and description as written. It does not
    consult the evidence table, and it does not choose 'a variant that works'.
    """
    label = (arm.get("label") or "").strip()
    desc = (arm.get("description") or "").strip()

    m_arm = re.match(r"Subprotocol\s+([A-Z0-9]+)\s*\((.+)\)\s*$", label)
    if not m_arm:
        return None
    arm_id, biomarker_text = m_arm.group(1), m_arm.group(2).strip()

    # Drug: text between "receive" and the route/schedule token. Allow a trailing
    # parenthetical compound code, e.g. "osimertinib (AZD9291) PO QD".
    m_drug = re.search(
        r"receive\s+(?:a\s+)?(.+?)\s*(?:\([A-Z0-9\-]+\)\s*)?"
        r"(?:PO\b|IV\b|orally|intravenously|by mouth|QD\b|BID\b|on days\b)",
        desc)
    drug = m_drug.group(1).strip() if m_drug else None
    if drug:
        drug = re.sub(r"\s*\(.*?\)\s*", " ", drug).strip()

    # Cross-check against the arm's declared Drug: interventions.
    declared = [x.split(":", 1)[1].strip()
                for x in (arm.get("interventionNames") or [])
                if x.lower().startswith("drug:")]
    if drug and declared:
        norm_declared = {normalise_drug(x) for x in declared}
        if normalise_drug(drug) not in norm_declared:
            for cand in declared:
                if normalise_drug(cand) in normalise_drug(desc):
                    drug = cand
                    break

    genes = re.findall(r"\b([A-Z][A-Z0-9]{1,7})\b", biomarker_text)
    stop = {"IHC", "LAG", "OR", "AND", "BY", "V600E", "V600", "R", "K", "D",
            "S768R", "I638F", "L239R", "T790M", "PO", "QD", "BID"}
    genes = [g for g in genes if g not in stop and not re.match(r"^[A-Z]\d", g)]
    gene = GENE_ALIASES.get(genes[0], genes[0]) if genes else None

    low = biomarker_text.lower()
    if "amplification" in low or "copy number" in low:
        alt_class = "amplification"
    elif "fusion" in low or "translocation" in low or "inversion" in low:
        alt_class = "fusion"
    elif "loss" in low and "ihc" in low:
        alt_class = "expression_ihc"
    elif "expression" in low:
        alt_class = "expression_ihc"
    elif "loss" in low or "deletion" in low or "inactivating" in low:
        alt_class = "loss"
    elif "mutation" in low:
        alt_class = "mutation"
    else:
        alt_class = "other"

    # Specific protein variant named in the label, if any (e.g. V600E, T790M).
    m_var = re.findall(r"\b([A-Z]\d{2,4}[A-Z*]?)\b", biomarker_text)
    specific = [v for v in m_var if not re.match(r"^[A-Z]\d{1,2}$", v)]

    return {
        "arm_id": arm_id,
        "label": label,
        "biomarker_text": biomarker_text,
        "gene": gene,
        "alteration_class": alt_class,
        "specific_variants": specific,
        "assigned_drug": drug,
        "declared_drugs": declared,
    }


# ---------------------------------------------------------------------------
# Running the real pipeline
# ---------------------------------------------------------------------------

HOTSPOT_CACHE = os.path.join(_REPO_ROOT, "validation_results", "hotspot_cache.json")
_hotspots: dict[str, list[str]] | None = None


def _load_hotspot_cache() -> dict[str, list[str]]:
    global _hotspots
    if _hotspots is None:
        if os.path.exists(HOTSPOT_CACHE):
            with open(HOTSPOT_CACHE, encoding="utf-8") as f:
                _hotspots = json.load(f)
        else:
            _hotspots = {}
    return _hotspots


def resolve_hotspots(gene: str, top_n: int = 3) -> list[str]:
    """Most PREVALENT real-world protein changes in `gene`, from MSK-IMPACT.

    Why this exists: an arm that reads "EGFR activating mutation" names no
    specific variant, but a real patient always submits one. Querying the
    literal string "MUTATION" makes the pipeline look worse than it is (it
    returns nothing), so the arm needs a representative variant.

    Choosing that variant by hand would be gaming -- it would be trivial to pick
    one already known to resolve. Instead it is chosen by PREVALENCE among real
    sequenced patients (cBioPortal / MSK-IMPACT, n~10k), which is entirely
    independent of any drug and of this repo's evidence table. Whatever variant
    is most common in real patients is what gets queried, whether or not the
    table happens to handle it.
    """
    cache = _load_hotspot_cache()
    if gene in cache:
        return cache[gene][:top_n]

    from collections import Counter
    import httpx
    base = "https://www.cbioportal.org/api"
    try:
        g = httpx.get(f"{base}/genes/{gene}", timeout=40)
        if g.status_code != 200:
            cache[gene] = []
        else:
            eid = g.json()["entrezGeneId"]
            r = httpx.post(
                f"{base}/molecular-profiles/msk_impact_2017_mutations/mutations/fetch",
                params={"projection": "DETAILED"},
                json={"entrezGeneIds": [eid], "sampleListId": "msk_impact_2017_all"},
                timeout=120)
            counts = Counter(
                m.get("proteinChange") for m in (r.json() if r.status_code == 200 else [])
                if m.get("proteinChange"))
            cache[gene] = [v for v, _ in counts.most_common(8)]
    except Exception:
        cache[gene] = []

    os.makedirs(os.path.dirname(HOTSPOT_CACHE), exist_ok=True)
    with open(HOTSPOT_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    return cache[gene][:top_n]


def variant_tokens(arm: dict) -> list[str]:
    """Query tokens to try for this arm, derived mechanically from the label.

    Ordering is fixed and identical for every arm. No arm gets a hand-tuned
    token, and no token was chosen by first checking what the table accepts.
    """
    if arm["specific_variants"]:
        return list(arm["specific_variants"])
    if arm["alteration_class"] in ("mutation", "other"):
        # Generic "<GENE> mutation" arm: use the gene's most prevalent
        # real-world variants (see resolve_hotspots) rather than the literal
        # string "MUTATION", which no real submission would ever contain.
        return resolve_hotspots(arm["gene"]) or ["MUTATION"]
    return {
        "amplification": ["AMPLIFICATION"],
        "fusion": ["FUSION"],
        "loss": ["DELETION", "LOSS"],
        "expression_ihc": [],
    }[arm["alteration_class"]]


def run_pipeline(gene: str, variant: str, mode: str = "tier2") -> list[str]:
    """Rank the engine's top three drugs for a gene and variant.

    Both tiers, because one tier is not the engine. This called only
    get_all_drugs_for_variant_live, the OncoKB live API plus the curated static
    table, and returned an empty list whenever that table had nothing. The
    repurposing path that exists precisely to answer the cases the table cannot
    was never invoked.

    That made the benchmark unable to measure generalisation in either
    direction. An audit split its arms on whether the assigned drug was already
    in the evidence table and found near-zero concordance on the ones that were
    not, which was read as the engine failing to generalise. The subset had been
    constructed to exclude everything the only tier being queried could answer.
    Six of those thirteen misses are drugs Tier 2 retrieves as approved.

    Tier 2 runs only when Tier 1 is empty, which is the convention the TCGA
    concordance pilot documented, and it asks the question that matters here:
    when the table holds nothing, can the engine still reach the right drug?

    Three candidate-pool models, because they do not agree and the difference
    is the point:

      tier1     the evidence table only. What this benchmark did until
                2026-08-19, and what produced its published figures.
      fallback  Tier 1, then Tier 2 only when Tier 1 is empty.
      union     both pools merged, Tier 1 levels annotated onto Tier 2 hits.
      tier2     Tier 2 pool only, annotated with Tier 1 levels. This is what
                production actually does, and it is the default here for that
                reason.

    Production is worth stating plainly, because the benchmark had it backwards.
    run_ai_analysis builds its entire candidate pool from
    _query_repurposing_candidates, which is Tier 2, and uses the evidence table
    to decide targetability and to stamp a level onto those candidates. The pool
    is Tier 2; the table annotates it. A Tier-1-only benchmark measures the
    annotation and calls it the engine.

    None of the three is exactly production, because production ranks against a
    specific mutation with structure scoring available. union is the closest
    without a submission to hang it on.
    """
    from services.oncokb_evidence import get_all_drugs_for_variant_live
    from ai.ranking import rank_candidates

    evidence = get_all_drugs_for_variant_live(
        gene, variant, cancer_type=None, alphamissense_score=1.0) or {}
    candidates = []
    for drug_name, level in evidence.items():
        if "R" in str(level):  # resistance markers are not recommendations
            continue
        lv = str(level)
        candidates.append({
            "drug_name": drug_name,
            "oncokb_level": level,
            "is_approved": True,
            "max_phase": 4,
            "opentargets_score": 0.8 if "LEVEL_1" in lv else (0.6 if "LEVEL_2" in lv else 0.4),
        })

    levels_by_drug = {normalise_drug(k): v for k, v in evidence.items()}

    if mode == "tier2":
        candidates = []
        for cand in (dict(c) for c in _tier2_candidates_cached(gene)):
            key = normalise_drug(cand.get("drug_name") or "")
            if key in levels_by_drug:
                cand = {**cand, "oncokb_level": levels_by_drug[key]}
            candidates.append(cand)
    elif mode == "fallback" and not candidates:
        candidates = [dict(c) for c in _tier2_candidates_cached(gene)]
    elif mode == "union":
        known = {normalise_drug(c["drug_name"]) for c in candidates}
        levels = {normalise_drug(k): v for k, v in evidence.items()}
        for cand in (dict(c) for c in _tier2_candidates_cached(gene)):
            key = normalise_drug(cand.get("drug_name") or "")
            if not key or key in known:
                continue
            # A Tier 2 candidate the table also knows keeps the table's level,
            # which is how production annotates its pool.
            if key in levels:
                cand = {**cand, "oncokb_level": levels[key]}
            candidates.append(cand)
            known.add(key)

    if not candidates:
        return []
    return [d["drug_name"] for d in rank_candidates(candidates)[:3]]


@lru_cache(maxsize=None)
def _tier2_candidates_cached(gene: str) -> tuple:
    """Tier 2 depends only on the gene, so one live call per gene per run.

    Without this an A/B over several hundred gold cases makes the same
    OpenTargets and DGIdb requests dozens of times.
    """
    return tuple(_tier2_candidates(gene))


def _tier2_candidates(gene: str) -> list[dict]:
    """The production repurposing path: OpenTargets, DGIdb, CIViC, OncoKB.

    Calls the same function the AI worker calls, rather than a reimplementation,
    so the benchmark cannot drift from what the app does. protein_variant is
    left None to skip structure folding, which is irrelevant to drug identity
    and would make the run hours long.
    """
    try:
        from workers.ai_worker import _query_repurposing_candidates
    except Exception as exc:  # pragma: no cover - import guard
        print(f"    [tier2] unavailable: {exc}", file=sys.stderr)
        return []
    try:
        drugs, _pdb, _excluded = _query_repurposing_candidates(
            gene,
            protein_variant=None,
            hgvs=None,
            cancer_type=None,
            submission_id="nci-match-benchmark",
        )
    except Exception as exc:
        print(f"    [tier2] failed for {gene}: {exc}", file=sys.stderr)
        return []
    return list(drugs or [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="reuse cached arms instead of refetching")
    ap.add_argument("--mode", choices=("tier1", "fallback", "union", "tier2"),
                    default="tier2",
                    help="candidate pool model. tier1 reproduces the figures "
                         "this benchmark reported before 2026-08-19; tier2 "
                         "mirrors what production does and is the default")
    args = ap.parse_args()

    raw_arms = load_arms(args.offline)
    arms = [a for a in (parse_arm(x) for x in raw_arms) if a]

    scored, out_of_scope, rows = [], [], []
    for arm in arms:
        if not arm["gene"] or not arm["assigned_drug"]:
            out_of_scope.append({**arm, "reason": "no gene or no drug in arm text"})
            continue
        if arm["alteration_class"] == "expression_ihc":
            out_of_scope.append({**arm, "reason": "protein-expression/IHC biomarker, not a DNA variant"})
            continue

        top3 = []
        used = None
        used_gene = None
        for gene in GENE_FAMILIES.get(arm["gene"], [arm["gene"]]):
            probe = {**arm, "gene": gene}
            for tok in variant_tokens(probe):
                top3 = run_pipeline(gene, tok, mode=args.mode)
                if top3:
                    used, used_gene = tok, gene
                    break
            if top3:
                break

        assigned = normalise_drug(arm["assigned_drug"])
        top3_norm = [normalise_drug(d) for d in top3]
        exact = assigned in top3_norm
        acls = drug_class_of(arm["assigned_drug"])
        klass = bool(acls) and any(drug_class_of(d) == acls for d in top3)

        row = {**arm, "variant_used": used, "gene_used": used_gene,
               "pipeline_top3": top3, "exact_hit": exact, "class_hit": klass}
        rows.append(row)
        scored.append(row)

    n = len(scored)
    exact_n = sum(1 for r in scored if r["exact_hit"])
    class_n = sum(1 for r in scored if r["class_hit"])
    nopred = sum(1 for r in scored if not r["pipeline_top3"])

    print("=" * 78)
    print("NCI-MATCH CONCORDANCE BENCHMARK  (EAY131 / %s)" % NCT_ID)
    print("Answer key: expert-committee biomarker->drug arm assignments")
    print("=" * 78)
    print()
    print("Arms parsed from trial record : %d" % len(arms))
    print("Scored (gene + drug + DNA alt) : %d" % n)
    print("Out of scope                   : %d" % len(out_of_scope))
    for o in out_of_scope:
        print("    %-6s %-46s %s" % (o["arm_id"], o["biomarker_text"][:46], o["reason"]))
    print()
    print("-" * 78)
    print("%-5s %-8s %-30s %-26s %s" % ("arm", "gene", "assigned drug", "our top-3", "result"))
    print("-" * 78)
    for r in rows:
        if r["exact_hit"]:
            verdict = "EXACT"
        elif r["class_hit"]:
            verdict = "CLASS"
        elif not r["pipeline_top3"]:
            verdict = "NO-PRED"
        else:
            verdict = "MISS"
        print("%-5s %-8s %-30s %-26s %s" % (
            r["arm_id"], r["gene"] or "-", (r["assigned_drug"] or "-")[:30],
            (", ".join(r["pipeline_top3"]) or "(none)")[:26], verdict))
    print()
    print("=" * 78)
    if n:
        print("Exact Top-3 concordance : %2d/%d = %.1f%%" % (exact_n, n, 100.0 * exact_n / n))
        print("Class Top-3 concordance : %2d/%d = %.1f%%" % (class_n, n, 100.0 * class_n / n))
        print("No recommendation       : %2d/%d = %.1f%%" % (nopred, n, 100.0 * nopred / n))
    print("=" * 78)

    payload = {
        "benchmark": "nci_match_arm_concordance",
        "source": f"ClinicalTrials.gov {NCT_ID} (NCI-MATCH / EAY131)",
        "n_arms_parsed": len(arms),
        "n_scored": n,
        "exact_top3": exact_n,
        "class_top3": class_n,
        "no_prediction": nopred,
        "exact_top3_pct": round(100.0 * exact_n / n, 1) if n else None,
        "class_top3_pct": round(100.0 * class_n / n, 1) if n else None,
        "results": rows,
        "out_of_scope": out_of_scope,
    }
    os.makedirs(os.path.dirname(RESULTS_OUT), exist_ok=True)
    with open(RESULTS_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Wrote %s" % RESULTS_OUT)


if __name__ == "__main__":
    main()
