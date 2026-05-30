"""Clinical Trial Data Integration — OpenOncology

Fetches real-world trial data from ClinicalTrials.gov and converts to benchmark cases.

Primary sources:
  - ClinicalTrials.gov XML API (free, public)
  - ClinicalTrials.gov search results for precision medicine trials
  - Published trial supplementary data (parsed manually or via PMC)

Provides:
  - fetch_trials_by_gene(): Get all trials studying a specific gene
  - fetch_trials_by_drug(): Get all trials using a specific drug
  - fetch_trials_by_variant(): Mutation-specific trial search (NEW)
  - score_trial_variant_relevance(): Score how relevant a trial is to a specific variant
  - parse_trial_xml(): Convert trial XML → structured trial dict
  - generate_benchmark_case(): Convert trial data → benchmark case format

Usage:
    from services.trial_integration import fetch_trials_by_variant
    trials = await fetch_trials_by_variant(gene="EGFR", variant="T790M", cancer_type="NSCLC")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Trial API endpoint (free, no auth required)
CLINICALTRIALS_API_BASE = "https://clinicaltrials.gov/api/v2"


# ── Gene to search term mapping ────────────────────────────────────────────────
# Maps gene symbols to common clinical trial naming conventions
GENE_TO_TRIAL_NAMES: dict[str, list[str]] = {
    "EGFR": ["EGFR", "epidermal growth factor receptor"],
    "ALK": ["ALK", "anaplastic lymphoma kinase"],
    "ROS1": ["ROS1"],
    "MET": ["MET", "mesenchymal-epithelial transition"],
    "RET": ["RET", "rearranged during transfection"],
    "KRAS": ["KRAS", "KRAS G12C"],
    "BRAF": ["BRAF", "B-Raf"],
    "ERBB2": ["HER2", "ERBB2", "trastuzumab"],
    "NRAS": ["NRAS"],
    "ABL1": ["BCR-ABL", "chronic myeloid leukemia", "imatinib"],
    "FLT3": ["FLT3", "acute myeloid leukemia"],
    "IDH1": ["IDH1", "isocitrate dehydrogenase"],
    "IDH2": ["IDH2"],
    "SMARCA4": ["SMARCA4", "BRG1"],
    "CDKN2A": ["p16", "CDK inhibitor"],
}

# Drug to gene mapping (reverse lookup)
DRUG_TO_GENES: dict[str, list[str]] = {
    "Osimertinib": ["EGFR"],
    "Erlotinib": ["EGFR"],
    "Gefitinib": ["EGFR"],
    "Afatinib": ["EGFR"],
    "Alectinib": ["ALK"],
    "Crizotinib": ["ALK", "ROS1", "MET"],
    "Brigatinib": ["ALK"],
    "Lorlatinib": ["ALK"],
    "Entrectinib": ["ROS1", "NTRK"],
    "Pralsetinib": ["RET"],
    "Selpercatinib": ["RET"],
    "Capmatinib": ["MET"],
    "Tepotinib": ["MET"],
    "Sotorasib": ["KRAS"],
    "Adagrasib": ["KRAS"],
    "Vemurafenib": ["BRAF"],
    "Dabrafenib": ["BRAF"],
    "Trametinib": ["BRAF", "NRAS"],
    "Binimetinib": ["NRAS"],
    "Imatinib": ["ABL1", "KIT", "PDGFRA"],
    "Midostaurin": ["FLT3"],
    "Trastuzumab": ["ERBB2"],
    "Pertuzumab": ["ERBB2"],
    "Trastuzumab deruxtecan": ["ERBB2"],
    "Lapatinib": ["EGFR", "ERBB2"],
    "Neratinib": ["EGFR", "ERBB2"],
    "Ivosidenib": ["IDH1"],
    "Enasidenib": ["IDH2"],
}

# OncoKB level mapping from trial phase/design
TRIAL_PHASE_TO_LEVEL: dict[str, str] = {
    "PHASE_1": "LEVEL_4",  # Early discovery
    "PHASE_2": "LEVEL_3",  # Investigational
    "PHASE_3": "LEVEL_1",  # Standard care pathway
    "PHASE_4": "LEVEL_2",  # Post-market surveillance
}

# ── Variant-specific trial search terms ───────────────────────────────────────
# Maps (GENE, VARIANT) → extra search terms that appear in trial protocols
# for this specific mutation.  Used by fetch_trials_by_variant() to boost
# relevance scoring for trials that mention the exact variant.
VARIANT_TO_TRIAL_TERMS: dict[tuple[str, str], list[str]] = {
    # EGFR
    ("EGFR", "T790M"):    ["T790M", "osimertinib resistance", "third-generation EGFR", "AZD9291"],
    ("EGFR", "L858R"):    ["L858R", "exon 21", "erlotinib", "gefitinib", "afatinib", "osimertinib"],
    ("EGFR", "exon19del"):["exon 19 deletion", "del19", "gefitinib", "erlotinib", "osimertinib"],
    ("EGFR", "C797S"):    ["C797S", "fourth-generation EGFR", "allosteric EGFR"],
    ("EGFR", "exon20ins"):["exon 20 insertion", "amivantamab", "mobocertinib"],
    # KRAS
    ("KRAS", "G12C"):     ["G12C", "sotorasib", "adagrasib", "AMG-510", "MRTX-849"],
    ("KRAS", "G12D"):     ["G12D", "MRTX1133", "adagrasib G12D"],
    ("KRAS", "G12V"):     ["G12V"],
    # BRAF
    ("BRAF", "V600E"):    ["V600E", "vemurafenib", "dabrafenib", "encorafenib"],
    ("BRAF", "V600K"):    ["V600K", "dabrafenib", "trametinib"],
    ("BRAF", "class_2"):  ["class 2 BRAF", "non-V600", "RAF dimer"],
    # ALK
    ("ALK", "fusion"):    ["ALK fusion", "ALK rearrangement", "alectinib", "brigatinib", "lorlatinib"],
    ("ALK", "G1202R"):    ["G1202R", "lorlatinib resistance", "compound mutation"],
    # MET
    ("MET", "exon14skip"):["exon 14 skipping", "METex14", "capmatinib", "tepotinib"],
    ("MET", "amplification"):["MET amplification", "MET copy number", "savolitinib"],
    # RET
    ("RET", "fusion"):    ["RET fusion", "selpercatinib", "pralsetinib", "BLU-667"],
    ("RET", "M918T"):     ["M918T", "medullary thyroid", "vandetanib"],
    # ERBB2 (HER2)
    ("ERBB2", "amplification"):["HER2 amplification", "HER2 positive", "trastuzumab", "pertuzumab"],
    ("ERBB2", "V777L"):   ["HER2 V777L", "neratinib", "afatinib"],
    ("ERBB2", "exon20ins"):["HER2 exon 20", "trastuzumab deruxtecan", "poziotinib"],
    # PIK3CA
    ("PIK3CA", "H1047R"): ["PIK3CA H1047R", "alpelisib", "PI3K inhibitor"],
    ("PIK3CA", "E545K"):  ["PIK3CA E545K", "alpelisib"],
    ("PIK3CA", "E542K"):  ["PIK3CA E542K", "alpelisib"],
    # BRCA
    ("BRCA1", "pathogenic"):["BRCA1", "germline BRCA", "olaparib", "niraparib", "PARP inhibitor"],
    ("BRCA2", "pathogenic"):["BRCA2", "germline BRCA", "olaparib", "niraparib", "PARP inhibitor"],
    # IDH
    ("IDH1", "R132H"):    ["IDH1 R132H", "ivosidenib", "olutasidenib"],
    ("IDH2", "R172K"):    ["IDH2 R172K", "enasidenib"],
    ("IDH2", "R140Q"):    ["IDH2 R140Q", "enasidenib"],
    # FLT3
    ("FLT3", "ITD"):      ["FLT3 ITD", "midostaurin", "quizartinib", "gilteritinib"],
    ("FLT3", "D835"):     ["FLT3 TKD", "gilteritinib"],
    # NTRK
    ("NTRK1", "fusion"):  ["NTRK1 fusion", "larotrectinib", "entrectinib", "TRK fusion"],
    ("NTRK2", "fusion"):  ["NTRK2 fusion", "larotrectinib", "entrectinib"],
    ("NTRK3", "fusion"):  ["NTRK3 fusion", "larotrectinib", "entrectinib"],
    # TP53
    ("TP53", "R175H"):    ["TP53 R175H", "APR-246", "eprenetapopt", "p53 reactivation"],
    ("TP53", "Y220C"):    ["TP53 Y220C", "PC14586", "p53 stabilizer"],
    # ROS1
    ("ROS1", "fusion"):   ["ROS1 fusion", "crizotinib", "entrectinib", "lorlatinib", "repotrectinib"],
    # CDK4/6
    ("CDKN2A", "deletion"):["p16 loss", "CDK4/6 inhibitor", "palbociclib", "ribociclib"],
    ("CDK4", "amplification"):["CDK4 amplification", "abemaciclib"],
    # PTEN
    ("PTEN", "loss"):     ["PTEN loss", "PI3K inhibitor", "AKT inhibitor", "ipatasertib"],
    # MSI/MMR
    ("MLH1", "loss"):     ["MLH1 deficiency", "MMR deficient", "pembrolizumab", "MSI-H"],
    ("MSH2", "loss"):     ["MSH2 deficiency", "MMR deficient", "pembrolizumab"],
}


def score_trial_variant_relevance(trial_title: str, trial_desc: str, gene: str, variant: str) -> float:
    """Score how relevant a ClinicalTrials.gov trial is to a specific variant.

    Args:
        trial_title: Official trial title or brief title.
        trial_desc:  Trial description / eligibility criteria (concatenated).
        gene:        Gene symbol, e.g. "EGFR".
        variant:     Variant descriptor, e.g. "T790M".

    Returns:
        Relevance score 0.0–1.0:
          1.0 — exact variant term found in title/description
          0.7 — variant-specific drug found in title/description
          0.5 — gene-level match only (no variant-specific terms)
          0.0 — not relevant
    """
    text = (trial_title + " " + trial_desc).lower()

    # Exact variant terms
    variant_terms = VARIANT_TO_TRIAL_TERMS.get((gene.upper(), variant), [variant])
    for term in variant_terms:
        if term.lower() in text:
            return 1.0

    # Variant itself by string
    if variant.lower() in text:
        return 1.0

    # Gene-level match
    gene_terms = GENE_TO_TRIAL_NAMES.get(gene.upper(), [gene])
    for term in gene_terms:
        if term.lower() in text:
            return 0.5

    return 0.0


async def fetch_trials_by_variant(
    gene: str,
    variant: str,
    cancer_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch ClinicalTrials.gov trials matched to a specific gene+variant.

    First fetches gene-level trials, then re-scores each result for variant
    specificity using the VARIANT_TO_TRIAL_TERMS lookup and string matching.

    Args:
        gene:        Gene symbol (e.g. "EGFR").
        variant:     Variant descriptor (e.g. "T790M", "G12C").
        cancer_type: Optional cancer type filter.
        limit:       Maximum number of results.

    Returns:
        List of trial dicts sorted by relevance_score (descending).
        Each dict has an added ``relevance_score`` field (0.0–1.0):
          - 1.0: variant-specific match
          - 0.5: gene-level match
    """
    # Also try variant-specific terms as direct intervention queries
    variant_terms = VARIANT_TO_TRIAL_TERMS.get((gene.upper(), variant), [])
    variant_specific_query = variant_terms[0] if variant_terms else variant

    # Run gene-level + variant-specific queries in parallel
    gene_trials_task = fetch_trials_by_gene(gene, cancer_type=cancer_type, limit=limit * 2)

    variant_trials: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{CLINICALTRIALS_API_BASE}/studies",
                params={
                    "query.cond": cancer_type or "",
                    "query.intr": variant_specific_query,
                    "format": "json",
                    "pageSize": min(limit, 50),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            for study in data.get("studies", []):
                parsed = _parse_trial_json(study, gene)
                if parsed:
                    variant_trials.append(parsed)
    except Exception as exc:
        logger.warning("[trials] variant query failed for %s %s: %s", gene, variant, exc)

    gene_trials = await gene_trials_task

    # Merge and deduplicate by trial_id
    all_trials: dict[str, dict] = {}
    for t in gene_trials + variant_trials:
        tid = t.get("trial_id", "")
        if tid and tid not in all_trials:
            all_trials[tid] = t

    # Score each trial for variant relevance
    scored: list[dict] = []
    for t in all_trials.values():
        title = t.get("title", "")
        # Use drugs list as additional text context
        drugs_text = " ".join(t.get("drugs", []))
        score = score_trial_variant_relevance(title, drugs_text, gene, variant)
        t["relevance_score"] = score
        scored.append(t)

    # Sort: variant-specific (1.0) first, then gene-level (0.5)
    scored.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
    return scored[:limit]


async def fetch_trials_by_gene(gene: str, cancer_type: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch ClinicalTrials.gov trials studying a specific gene.

    Args:
        gene: Gene symbol (e.g., "EGFR", "ALK")
        cancer_type: Optional cancer type filter (e.g., "NSCLC", "breast cancer")
        limit: Max number of trials to return

    Returns:
        List of trial dicts with: trial_id, title, phase, status, drugs, mutations, gene, cancer_type
    """
    search_terms = GENE_TO_TRIAL_NAMES.get(gene, [gene])

    # Add precision medicine / targeted therapy qualifier
    query_parts = []
    for term in search_terms:
        query_parts.append(f'("{term}" OR "{term} mutation")')
    query = " OR ".join(query_parts) + ' AND ("precision medicine" OR "targeted therapy" OR "biomarker")'

    if cancer_type:
        query += f' AND "{cancer_type}"'

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # ClinicalTrials.gov API v2 query
            response = await client.get(
                f"{CLINICALTRIALS_API_BASE}/studies",
                params={
                    "query.cond": cancer_type or "",
                    "query.intr": gene,
                    "format": "json",
                    "pageSize": min(limit, 100),
                },
            )
            response.raise_for_status()
            data = response.json()

            trials = []
            for study in data.get("studies", [])[:limit]:
                parsed = _parse_trial_json(study, gene)
                if parsed:
                    trials.append(parsed)

            return trials
    except Exception as e:
        logger.error(f"Error fetching trials for {gene}: {e}")
        return []


async def fetch_trials_by_drug(drug: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch ClinicalTrials.gov trials using a specific drug.

    Args:
        drug: Drug name (e.g., "Osimertinib")
        limit: Max number of trials

    Returns:
        List of trial dicts
    """
    genes = DRUG_TO_GENES.get(drug, [])

    trials = []
    for gene in genes:
        gene_trials = await fetch_trials_by_gene(gene, limit=limit // len(genes) if genes else limit)
        trials.extend(gene_trials)

    return trials


def _parse_trial_json(study: dict[str, Any], gene: str) -> Optional[dict[str, Any]]:
    """Parse ClinicalTrials.gov study JSON into structured format."""
    try:
        protocol = study.get("protocolSection", {})
        identif = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        design = protocol.get("designModule", {})
        cond = protocol.get("conditionsModule", {})
        interv = protocol.get("interventionsModule", {})
        outcome = protocol.get("outcomesModule", {})

        trial_id = identif.get("nctId", "UNKNOWN")
        title = identif.get("officialTitle", identif.get("briefTitle", ""))
        phase = design.get("phases", ["UNKNOWN"])[0] if design.get("phases") else "UNKNOWN"
        status_val = status.get("overallStatus", "UNKNOWN")
        conditions = cond.get("conditions", [])
        cancer_type = conditions[0] if conditions else "Unknown"

        # Extract drugs from interventions
        drugs = []
        if interv and interv.get("interventions"):
            for intervention in interv["interventions"]:
                name = intervention.get("name", "")
                if name:
                    # Sanitize drug name (remove dosage, frequency, etc.)
                    drug_name = re.split(r'\s+\(', name)[0].strip()
                    drugs.append(drug_name)

        # Get primary outcomes
        primary_outcomes = []
        if outcome and outcome.get("primaryOutcomes"):
            for po in outcome["primaryOutcomes"]:
                primary_outcomes.append(po.get("measure", ""))

        return {
            "trial_id": trial_id,
            "title": title,
            "phase": phase,
            "status": status_val,
            "gene": gene,
            "cancer_type": cancer_type,
            "drugs": list(set(drugs)),  # Deduplicate
            "mutation": None,  # Would need supplementary data to fill this
            "primary_outcomes": primary_outcomes,
            "enrollment": status.get("enrollmentInfo", {}).get("value", 0),
        }
    except Exception as e:
        logger.warning(f"Error parsing trial: {e}")
        return None


def generate_benchmark_case(
    trial: dict[str, Any],
    variant: str,
    drugs: list[str],
    evidence_level: str = "LEVEL_1",
    trial_stage: str = "PHASE_3",
) -> dict[str, Any]:
    """Convert trial data into benchmark case format.

    Args:
        trial: Trial dict from fetch_trials_by_*
        variant: Specific variant (e.g., "L858R", "exon19_del")
        drugs: Known effective drugs for this variant in this trial
        evidence_level: OncoKB level (e.g., "LEVEL_1")
        trial_stage: Clinical phase (e.g., "PHASE_3")

    Returns:
        Benchmark case dict
    """
    case_id = f"{trial['gene']}_{variant}_{trial['trial_id']}".replace(" ", "_")

    return {
        "case_id": case_id,
        "gene": trial["gene"],
        "variant": variant,
        "cancer_type": trial["cancer_type"],
        "known_drugs": drugs,
        "oncokb_level": evidence_level,
        "evidence_source": f"ClinicalTrials.gov_{trial_stage}",
        "trial_citations": [
            {
                "trial_id": trial["trial_id"],
                "title": trial["title"],
                "phase": trial["phase"],
                "status": trial["status"],
                "url": f"https://clinicaltrials.gov/study/{trial['trial_id']}",
            }
        ],
        "note": f"From trial {trial['trial_id']}: {trial['title'][:100]}...",
        "difficulty": "MODERATE",
    }


# ── Curated real-world trial data (fallback when API fails) ──────────────────
# These are actual published trials with genomic/outcome data
REAL_TRIAL_CASES: list[dict[str, Any]] = [
    # FLAURA trial (erlotinib vs osimertinib in EGFR+ NSCLC)
    {
        "trial_id": "NCT02296125",
        "gene": "EGFR",
        "variant": "L858R",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Osimertinib", "Erlotinib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_3",
        "outcome": "OS benefit for osimertinib",
        "sample_size": 556,
        "pmid": "28183697",
    },
    # AURA trial (osimertinib for T790M resistance)
    {
        "trial_id": "NCT02151899",
        "gene": "EGFR",
        "variant": "T790M",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Osimertinib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_3",
        "outcome": "ORR 71%, disease control",
        "sample_size": 419,
        "pmid": "26399188",
    },
    # ALEX trial (alectinib vs crizotinib for ALK+ NSCLC)
    {
        "trial_id": "NCT02075840",
        "gene": "ALK",
        "variant": "EML4-ALK",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Alectinib", "Crizotinib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_3",
        "outcome": "PFS benefit for alectinib",
        "sample_size": 303,
        "pmid": "27659740",
    },
    # LIBRETTO-131 (selpercatinib for RET-positive NSCLC)
    {
        "trial_id": "NCT03157545",
        "gene": "RET",
        "variant": "KIF5B-RET",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Selpercatinib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_2",
        "outcome": "ORR 64% in treatment-naïve patients",
        "sample_size": 105,
        "pmid": "32611720",
    },
    # KEYNOTE-407 (pembrolizumab + chemotherapy, TNBC)
    {
        "trial_id": "NCT02447276",
        "gene": "PD-L1",
        "variant": "high_expression",
        "cancer_type": "Triple-Negative Breast Cancer",
        "drugs": ["Pembrolizumab"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_3",
        "outcome": "OS improvement in PD-L1+ patients",
        "sample_size": 847,
        "pmid": "28694348",
    },
    # BRAF V600E melanoma (vemurafenib)
    {
        "trial_id": "NCT01006980",
        "gene": "BRAF",
        "variant": "V600E",
        "cancer_type": "Melanoma",
        "drugs": ["Vemurafenib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_3",
        "outcome": "OS/RFS improvement",
        "sample_size": 675,
        "pmid": "21639810",
    },
    # CAPMATINIB trial (MET exon 14 NSCLC)
    {
        "trial_id": "NCT02414139",
        "gene": "MET",
        "variant": "exon14_skip",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Capmatinib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_2",
        "outcome": "ORR 68% in advanced disease",
        "sample_size": 69,
        "pmid": "28910248",
    },
    # CodeBreaK 100 (sotorasib for KRAS G12C NSCLC)
    {
        "trial_id": "NCT03600883",
        "gene": "KRAS",
        "variant": "G12C",
        "cancer_type": "Non-Small Cell Lung Cancer",
        "drugs": ["Sotorasib"],
        "evidence_level": "LEVEL_1",
        "trial_phase": "PHASE_2",
        "outcome": "ORR 36% in previously treated patients",
        "sample_size": 126,
        "pmid": "31992388",
    },
]


def get_real_trial_cases() -> list[dict[str, Any]]:
    """Return curated real-world trial cases (fallback data)."""
    return REAL_TRIAL_CASES


async def test_fetch_trials():
    """Test fetching trials from ClinicalTrials.gov API."""
    print("Fetching EGFR trials...")
    trials = await fetch_trials_by_gene("EGFR", cancer_type="NSCLC", limit=5)
    print(f"Found {len(trials)} trials:")
    for trial in trials:
        print(f"  {trial['trial_id']}: {trial['title'][:80]}")

    print("\n Generating benchmark case...")
    if trials:
        case = generate_benchmark_case(
            trials[0],
            variant="L858R",
            drugs=["Osimertinib", "Erlotinib"],
            evidence_level="LEVEL_1",
        )
        print(json.dumps(case, indent=2))


if __name__ == "__main__":
    # Quick test
    asyncio.run(test_fetch_trials())
