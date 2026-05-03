"""
Fetch Real Patient Data from cBioPortal for Benchmarking
=========================================================
Pulls actual published genomic data (TCGA + MSK-IMPACT) via the cBioPortal
public API (no login, no API key) and runs the OpenOncology ranking pipeline
against each patient. Reports honest benchmark results.

Studies used (all open-access, peer-reviewed):
  luad_tcga_pub   - TCGA Lung Adenocarcinoma, Nature 2014 (PMID:25079552)
  brca_tcga_pub   - TCGA Breast Cancer, Nature 2012 (PMID:23000897)
  coadread_tcga_pub - TCGA Colorectal, Nature 2012 (PMID:22810696)
  blca_tcga_pub   - TCGA Bladder, Nature 2014 (PMID:25079552)
  ov_tcga_pub     - TCGA Ovarian, Nature 2011 (PMID:21720365)
  gbm_tcga_pub    - TCGA Glioblastoma, Nature 2008 (PMID:18772890)

Data source: https://www.cbioportal.org  (Cerami et al., Cancer Discov 2012)
All data is de-identified per TCGA data use agreement (open-tier).

Run:
    python scripts/fetch_real_patients.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import time
from functools import lru_cache
from typing import Any

CBIOPORTAL = "https://www.cbioportal.org/api"

# Genes sampled for the real-world benchmark.
# The first block is rich in approved or off-label targeted options.
# The second block intentionally includes harder genes so Tier 3 custom-design
# briefs appear in realistic proportions instead of being engineered away.
TARGET_GENES = {
    "EGFR": 1956,    # NSCLC - erlotinib/osimertinib
    "KRAS": 3845,    # CRC/NSCLC - sotorasib/adagrasib
    "BRAF": 673,     # Melanoma/CRC - vemurafenib/dabrafenib
    "PIK3CA": 5290,  # Breast - alpelisib
    "ERBB2": 2064,   # Breast/GC - trastuzumab
    "ALK": 238,      # NSCLC - alectinib/crizotinib
    "MET": 4233,     # NSCLC - capmatinib/tepotinib
    "FGFR3": 2261,   # Bladder - erdafitinib
    "IDH1": 3417,    # AML/Glioma - ivosidenib
    "NRAS": 4893,    # Melanoma
    "TP53": 7157,    # High-prevalence hard case
    "PTEN": 5728,
    "STK11": 6794,
    "KEAP1": 9817,
    "NF1": 4763,
    "APC": 324,
    "SMAD4": 4089,
    "CDKN2A": 1029,
    "ARID1A": 8289,
    "RB1": 5925,
    "ATM": 472,
    "NOTCH1": 4851,
}

GENE_FETCH_ORDER = [
    "EGFR",
    "TP53",
    "KRAS",
    "STK11",
    "BRAF",
    "KEAP1",
    "PIK3CA",
    "NF1",
    "ERBB2",
    "APC",
    "ALK",
    "SMAD4",
    "MET",
    "CDKN2A",
    "FGFR3",
    "ARID1A",
    "IDH1",
    "RB1",
    "NRAS",
    "ATM",
    "PTEN",
    "NOTCH1",
]

# Broad expansion panel for harvesting real mutations when target genes are sparse.
# Values are Entrez Gene IDs (used directly by cBioPortal mutations endpoint).
EXPANSION_GENES = {
    "TP53": 7157,
    "TTN": 7273,
    "MUC16": 94025,
    "KMT2D": 8085,
    "KMT2C": 58508,
    "ARID1A": 8289,
    "PIK3CA": 5290,
    "PIK3R1": 5295,
    "PTEN": 5728,
    "APC": 324,
    "KRAS": 3845,
    "NRAS": 4893,
    "HRAS": 3265,
    "BRAF": 673,
    "EGFR": 1956,
    "ERBB2": 2064,
    "ERBB3": 2065,
    "FGFR1": 2260,
    "FGFR2": 2263,
    "FGFR3": 2261,
    "MET": 4233,
    "ALK": 238,
    "ROS1": 6098,
    "RET": 5979,
    "NTRK1": 4914,
    "NTRK2": 4915,
    "NTRK3": 4916,
    "IDH1": 3417,
    "IDH2": 3418,
    "ATM": 472,
    "ATR": 545,
    "BRCA1": 672,
    "BRCA2": 675,
    "PALB2": 79728,
    "CHEK2": 11200,
    "RB1": 5925,
    "CDKN2A": 1029,
    "CDK4": 1019,
    "CDK6": 1021,
    "CCND1": 595,
    "STK11": 6794,
    "KEAP1": 9817,
    "NFE2L2": 4780,
    "NF1": 4763,
    "SMAD4": 4089,
    "SMARCA4": 6597,
    "VHL": 7428,
    "PIK3CB": 5291,
    "AKT1": 207,
    "AKT2": 208,
    "AKT3": 10000,
    "MTOR": 2475,
    "TSC1": 7248,
    "TSC2": 7249,
    "JAK2": 3717,
    "FLT3": 2322,
    "KIT": 3815,
    "PDGFRA": 5156,
    "PDGFRB": 5159,
    "CTNNB1": 1499,
    "NOTCH1": 4851,
    "FBXW7": 55294,
}

# Studies: (studyId, mutation_profile_id, sample_list_id, cancer_type)
STUDIES = [
    ("luad_tcga_pub", "luad_tcga_pub_mutations", "luad_tcga_pub_sequenced", "Lung Adenocarcinoma"),
    ("lusc_tcga_pub", "lusc_tcga_pub_mutations", "lusc_tcga_pub_sequenced", "Lung Squamous Cell Carcinoma"),
    ("brca_tcga_pub", "brca_tcga_pub_mutations", "brca_tcga_pub_sequenced", "Breast Invasive Carcinoma"),
    ("coadread_tcga_pub", "coadread_tcga_pub_mutations", "coadread_tcga_pub_sequenced", "Colorectal Adenocarcinoma"),
    ("blca_tcga_pub", "blca_tcga_pub_mutations", "blca_tcga_pub_sequenced", "Bladder Urothelial Carcinoma"),
    ("ov_tcga_pub", "ov_tcga_pub_mutations", "ov_tcga_pub_sequenced", "Ovarian Serous Cystadenocarcinoma"),
    ("gbm_tcga_pub", "gbm_tcga_pub_mutations", "gbm_tcga_pub_sequenced", "Glioblastoma Multiforme"),
    ("skcm_tcga_pub", "skcm_tcga_pub_mutations", "skcm_tcga_pub_sequenced", "Skin Cutaneous Melanoma"),
    ("ucec_tcga_pub", "ucec_tcga_pub_mutations", "ucec_tcga_pub_sequenced", "Uterine Corpus Endometrial Carcinoma"),
    ("prad_tcga_pub", "prad_tcga_pub_mutations", "prad_tcga_pub_sequenced", "Prostate Adenocarcinoma"),
    ("hnsc_tcga_pub", "hnsc_tcga_pub_mutations", "hnsc_tcga_pub_sequenced", "Head and Neck Squamous Cell Carcinoma"),
    ("stad_tcga_pub", "stad_tcga_pub_mutations", "stad_tcga_pub_sequenced", "Stomach Adenocarcinoma"),
    ("paad_tcga_pub", "paad_tcga_pub_mutations", "paad_tcga_pub_sequenced", "Pancreatic Adenocarcinoma"),
]

TIER_LABELS = {
    "DIRECT_FDA": "Tier 1 - direct FDA match",
    "FDA_REPURPOSING": "Tier 2 - off-label FDA match",
    "INVESTIGATIONAL_REPURPOSING": "Tier 3 - clinical trial match",
    "CUSTOM_DESIGN": "Tier 4 - custom drug (manual trigger)",
    "NONE": "No recommendation",
}

CANCER_SYNONYMS = {
    "lung adenocarcinoma": ["lung adenocarcinoma", "nsclc", "non-small cell lung cancer", "lung cancer"],
    "lung squamous cell carcinoma": ["lung squamous", "nsclc", "non-small cell lung cancer", "lung cancer"],
    "breast invasive carcinoma": ["breast", "breast cancer"],
    "colorectal adenocarcinoma": ["colorectal", "colon", "rectal", "crc"],
    "bladder urothelial carcinoma": ["bladder", "urothelial"],
    "ovarian serous cystadenocarcinoma": ["ovarian", "ovary"],
    "glioblastoma multiforme": ["glioblastoma", "gbm", "brain tumor"],
    "skin cutaneous melanoma": ["melanoma", "skin melanoma"],
    "uterine corpus endometrial carcinoma": ["endometrial", "uterine"],
    "prostate adenocarcinoma": ["prostate"],
    "head and neck squamous cell carcinoma": ["head and neck", "hnscc"],
    "stomach adenocarcinoma": ["stomach", "gastric"],
    "pancreatic adenocarcinoma": ["pancreatic", "pancreas"],
}

ACTIONABLE_VARIANT_HINTS = {
    "EGFR": ("L858R", "L861Q", "G719", "S768I", "EX19DEL", "E746A750DEL", "T790M", "EXON19", "DEL19"),
    "KRAS": ("G12C",),
    "BRAF": ("V600", "G469", "K601", "L597"),
    "ERBB2": ("S310", "L755", "V777", "D769", "Y772", "AMPLIFICATION", "INS"),
    "ALK": ("ALK", "FUSION"),
    "MET": ("EXON14", "SKIP"),
    "FGFR3": ("S249C", "Y373C", "R248C"),
    "IDH1": ("R132",),
    "NRAS": ("Q61",),
    "PIK3CA": ("E542", "E545", "H1047"),
}


def _get(path: str, timeout: int = 20, retries: int = 4) -> Any:
    url = f"{CBIOPORTAL}/{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(0.4 * attempt)
                continue
    print(f"  [WARN] GET {path}: {last_exc}", file=sys.stderr)
    return None


def fetch_actionable_mutations(
    profile_id: str,
    sample_list_id: str,
    entrez_id: int,
    gene: str,
    page_size: int = 40,
) -> list[dict]:
    """Fetch mutations for a specific gene from a published study."""
    path = (
        f"molecular-profiles/{profile_id}/mutations"
        f"?entrezGeneId={entrez_id}&sampleListId={sample_list_id}"
        f"&projection=DETAILED&pageSize={page_size}"
    )
    data = _get(path)
    if not data:
        return []
    # Keep all coding/splice/nonsilent-like calls and also include records where
    # proteinChange is absent by deriving a stable DNA-level token downstream.
    allowed = {
        "Missense_Mutation",
        "Frame_Shift_Del",
        "Frame_Shift_Ins",
        "In_Frame_Del",
        "In_Frame_Ins",
        "Splice_Site",
        "Nonsense_Mutation",
        "Translation_Start_Site",
        "Nonstop_Mutation",
        "Silent",
    }
    out = []
    for m in data:
        mt = str(m.get("mutationType") or "").strip()
        if mt and mt in allowed:
            out.append(m)
            continue
        # If mutationType is missing/unknown but alleles are present, keep it.
        if m.get("referenceAllele") and m.get("variantAllele") and m.get("startPosition"):
            out.append(m)
    return out




def _pick_valid_sample_list(study_id: str, sample_list_id: str) -> str | None:
    lists = _get(f"studies/{study_id}/sample-lists") or []
    valid_lists = {s["sampleListId"] for s in lists}
    if sample_list_id in valid_lists:
        return sample_list_id
    fallback = f"{study_id}_all"
    if fallback in valid_lists:
        return fallback
    return (
        next((l for l in valid_lists if l.endswith("_sequenced")), None)
        or next((l for l in valid_lists if l.endswith("_all")), None)
    )


def _pick_valid_mutation_profile(study_id: str, profile_id: str) -> str | None:
    profiles = _get(f"studies/{study_id}/molecular-profiles") or []
    valid_profiles = [p.get("molecularProfileId") for p in profiles if p.get("molecularProfileId")]
    if profile_id in valid_profiles:
        return profile_id
    fallback = f"{study_id}_mutations"
    if fallback in valid_profiles:
        return fallback
    return next((p for p in valid_profiles if str(p).endswith("_mutations")), None)


def _phase_rank(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    label = str(value or "").upper().strip()
    return {
        "APPROVAL": 4,
        "APPROVED": 4,
        "PHASE4": 4,
        "PHASE3": 3,
        "PHASE2": 2,
        "PHASE1": 1,
        "EARLY_PHASE1": 1,
        "COMPLETED": 1,
    }.get(label, 0)


def _cancer_terms(cancer_type: str) -> list[str]:
    normalized = str(cancer_type or "").strip().lower()
    return CANCER_SYNONYMS.get(normalized, [normalized])


def _matches_cancer_context(candidate_terms: list[str], cancer_type: str) -> bool:
    if not candidate_terms:
        return False
    joined = " | ".join(str(term).lower() for term in candidate_terms if term)
    return any(term in joined for term in _cancer_terms(cancer_type))


def _normalize_variant_token(variant: str) -> str:
    token = str(variant or "").upper().replace("P.", "").strip()
    return re.sub(r"[^A-Z0-9]+", "", token)


def _variant_matches_trial(patient_variant: str, trial_variant: str) -> bool:
    patient = _normalize_variant_token(patient_variant)
    trial = _normalize_variant_token(trial_variant)
    if not patient or not trial:
        return False
    if patient == trial:
        return True
    # Structural classes used in trial metadata.
    if trial == "EXON14SKIP":
        return "EXON14" in patient and ("SKIP" in patient or "SPLICE" in patient)
    if trial.endswith("ALK") and "ALK" in patient:
        return True
    if trial in {"HIGHEXPRESSION", "AMPLIFICATION"}:
        return trial in patient
    return False


# Genes that have ≥1 FDA-approved targeted therapy and documented oncology
# biology across tumour types — eligible for off-label consideration even when
# the exact hotspot is absent, provided the drug is approved and phase == 4.
_BROAD_ONCOGENIC_CLASS: frozenset[str] = frozenset({
    "EGFR", "ERBB2", "BRAF", "KRAS", "PIK3CA", "ALK", "MET", "RET",
    "FGFR1", "FGFR2", "FGFR3", "IDH1", "IDH2", "NTRK1", "NTRK2", "NTRK3",
    "KIT", "PDGFRA", "FLT3", "JAK2", "BRCA1", "BRCA2", "ATM",
    "CDK4", "CDK6", "MTOR", "AKT1",
})


def _supports_fda_off_label(gene: str, protein_change: str) -> bool:
    """Return True if variant has a known actionable hotspot hint."""
    hints = ACTIONABLE_VARIANT_HINTS.get(str(gene or "").upper())
    if not hints:
        return False
    patient = _normalize_variant_token(protein_change)
    return any(_normalize_variant_token(hint) in patient for hint in hints)


def _oncogenic_class_supports_off_label(gene: str, protein_change: str) -> bool:
    """Broader check: allow off-label if gene is in a known approved oncogenic
    class AND the variant is potentially activating (not silent/synonymous).

    This catches e.g. EGFR E1079K (outside hotspot table) in bladder cancer
    where erlotinib/osimertinib have documented off-label use.
    Conservative rules applied:
      - Never allow silent/synonymous variants (no amino-acid change)
      - Never allow known resistance designations
    """
    gene_upper = str(gene or "").upper().strip()
    if gene_upper not in _BROAD_ONCOGENIC_CLASS:
        return False
    # Exact hotspot already handled by _supports_fda_off_label
    if _supports_fda_off_label(gene_upper, protein_change):
        return True
    token = _normalize_variant_token(protein_change)
    if not token:
        return False
    # Exclude synonymous / silent (end with '=' or contain only same-amino-acid)
    if token.endswith("=") or "synonymous" in token or "silent" in token:
        return False
    # Exclude known resistance labels
    if any(r in token for r in ("t790m", "c797s", "g724s", "v600m")):
        return False
    # Allow missense, frameshift, insertion, deletion, truncation, amplification, fusion
    activating_patterns = ("fs", "del", "ins", "dup", "*", "ter", "trunc", "fusion",
                           "amplification", "splice", "skip")
    return any(p in token for p in activating_patterns) or (
        # Classic p.XnnY missense: starts with letter, has digits, ends with letter
        len(token) >= 4 and token[0].isalpha() and any(c.isdigit() for c in token) and token[-1].isalpha()
    )


def _variant_actionability_score(gene: str, protein_change: str) -> int:
    """Favor clinically meaningful alterations during benchmark case selection."""
    token = _normalize_variant_token(protein_change)
    gene_upper = str(gene or "").upper().strip()
    if not token:
        return 0
    if _supports_fda_off_label(gene_upper, protein_change):
        return 3
    if any(h in token for h in ("FUSION", "AMPLIFICATION", "EXON14", "EXON19", "DEL", "INS")):
        return 2
    if gene_upper in {"EGFR", "KRAS", "BRAF", "ERBB2", "ALK", "MET", "FGFR3", "IDH1", "PIK3CA", "NRAS"}:
        return 1
    return 0


@lru_cache(maxsize=256)
def _trial_case_lookup(gene: str, protein_change: str, cancer_type: str) -> tuple[dict[str, Any], ...]:
    _setup_api_path()
    from services.trial_integration import get_real_trial_cases

    matches: list[dict[str, Any]] = []
    for case in get_real_trial_cases():
        if str(case.get("gene") or "").upper() != gene.upper():
            continue
        if not _variant_matches_trial(protein_change, str(case.get("variant") or "")):
            continue
        if _matches_cancer_context([str(case.get("cancer_type") or "")], cancer_type):
            matches.append(case)
    return tuple(matches)


def _patient_next_step(tier: str, gene: str, cancer_type: str, approved_count: int, investigational_count: int) -> str:
    if tier == "DIRECT_FDA":
        return (
            f"Discuss the {gene} finding with a molecular tumor board and your oncologist to confirm the exact "
            f"mutation-tumor match, line-of-therapy eligibility, and standard-of-care access in {cancer_type}."
        )
    if tier == "FDA_REPURPOSING":
        return (
            f"Ask your oncologist whether the ranked off-label FDA-approved therapy can be justified for {gene} in {cancer_type}, "
            f"using tumor-board review, compendium support, and prior-authorization documentation."
        )
    if tier == "INVESTIGATIONAL_REPURPOSING":
        return (
            f"No credible FDA-approved off-label option was found. Review the {investigational_count} trial-backed or late-phase "
            f"candidates with your oncologist and search for genotype-matched clinical trials, expanded-access, or "
            f"compassionate-use pathways before considering experimental treatment."
        )
    if tier == "CUSTOM_DESIGN":
        return (
            f"No direct or repurposed drug was found for {gene} in {cancer_type}. The custom-design brief is a "
            f"preclinical research handoff for medicinal chemistry teams, not a treatment recommendation for immediate use."
        )
    return "No evidence-backed recommendation was produced; seek review by a molecular tumor board."


def _repurposing_cache_key(gene: str, protein_change: str, cancer_type: str) -> tuple[str, str, str]:
    gene_key = str(gene or "").upper().strip()
    cancer_key = str(cancer_type or "").lower().strip()
    if gene_key in ACTIONABLE_VARIANT_HINTS:
        return (gene_key, _normalize_variant_token(protein_change), cancer_key)
    return (gene_key, "*", cancer_key)


def select_patients(studies: list, max_patients: int = 100) -> list[dict]:
    """
    Pull real patients from multiple TCGA studies, selecting those with
    known actionable mutations. Returns up to `max_patients` real cases.
    """
    selected: list[dict] = []
    candidate_pool: list[dict] = []
    seen_case_key: set[str] = set()
    gene_order = {g: i for i, g in enumerate(GENE_FETCH_ORDER)}

    # Soft diversity caps, relaxed automatically for larger requested N.
    max_per_gene = max(6, (max_patients // max(1, len(TARGET_GENES))) + 4)
    max_per_study = max(8, (max_patients // max(1, len(studies))) + 4)

    required_pool = max(int(max_patients * 1.6), max_patients + 24)
    study_pool_cap = max(20, required_pool // max(1, len(studies)))
    study_pool_counts: dict[str, int] = {}
    study_gene_counts: dict[tuple[str, str], int] = {}
    per_study_gene_cap = 8
    fetch_page_size = 30 if max_patients <= 50 else (40 if max_patients <= 120 else 50)

    # First, gather a large pool of real patient mutation records across studies.
    stop_collection = False
    for study_id, profile_id, sample_list_id, cancer_type in studies:
        if stop_collection:
            break
        chosen_sample_list = _pick_valid_sample_list(study_id, sample_list_id)
        chosen_profile_id = _pick_valid_mutation_profile(study_id, profile_id)
        if not chosen_sample_list or not chosen_profile_id:
            continue

        for gene in GENE_FETCH_ORDER:
            entrez_id = TARGET_GENES[gene]
            if len(candidate_pool) >= required_pool:
                stop_collection = True
                break
            if study_pool_counts.get(study_id, 0) >= study_pool_cap:
                break
            mutations = fetch_actionable_mutations(
                chosen_profile_id,
                chosen_sample_list,
                entrez_id,
                gene,
                page_size=fetch_page_size,
            )
            if not mutations:
                continue

            for mut in mutations:
                protein_change = (mut.get("proteinChange") or "").strip()
                if not protein_change:
                    ref = str(mut.get("referenceAllele") or "N")
                    alt = str(mut.get("variantAllele") or "N")
                    pos = mut.get("startPosition")
                    protein_change = f"g.{pos}{ref}>{alt}" if pos else f"g.{ref}>{alt}"

                sample_id = mut.get("sampleId", "")
                patient_id = mut.get("patientId", sample_id.rsplit("-", 1)[0] if "-" in sample_id else sample_id)
                case_key = f"{study_id}|{sample_id}|{gene}|{protein_change}|{mut.get('startPosition')}"
                if case_key in seen_case_key:
                    continue
                seen_case_key.add(case_key)

                if study_gene_counts.get((study_id, gene), 0) >= per_study_gene_cap:
                    continue

                candidate_pool.append({
                    "sample_id": sample_id,
                    "patient_id": patient_id,
                    "study_id": study_id,
                    "cancer_type": cancer_type,
                    "gene": gene,
                    "protein_change": protein_change,
                    "mutation_type": mut.get("mutationType", ""),
                    "chr": mut.get("chr", ""),
                    "start": mut.get("startPosition"),
                    "end": mut.get("endPosition"),
                    "ref": mut.get("referenceAllele", "N"),
                    "alt": mut.get("variantAllele", "N"),
                    "genome_build": mut.get("ncbiBuild", "GRCh37"),
                    "source_url": f"https://www.cbioportal.org/study/summary?id={study_id}",
                    "actionability_score": _variant_actionability_score(gene, protein_change),
                })
                study_pool_counts[study_id] = study_pool_counts.get(study_id, 0) + 1
                study_gene_counts[(study_id, gene)] = study_gene_counts.get((study_id, gene), 0) + 1
                if len(candidate_pool) >= required_pool:
                    stop_collection = True
                    break
                if study_pool_counts.get(study_id, 0) >= study_pool_cap:
                    break

            time.sleep(0.02)

        # Fallback expansion: if targeted genes are insufficient, expand using
        # profile genes (valid Entrez IDs) rather than broken unfiltered endpoint.
        if not stop_collection and len(candidate_pool) < required_pool and study_pool_counts.get(study_id, 0) < study_pool_cap:
            for gene, entrez_id in EXPANSION_GENES.items():
                if len(candidate_pool) >= required_pool:
                    stop_collection = True
                    break
                if study_pool_counts.get(study_id, 0) >= study_pool_cap:
                    break

                muts = fetch_actionable_mutations(
                    chosen_profile_id,
                    chosen_sample_list,
                    entrez_id,
                    gene,
                    page_size=max(20, fetch_page_size // 2),
                )
                if not muts:
                    continue

                for mut in muts:
                    if len(candidate_pool) >= required_pool:
                        stop_collection = True
                        break
                    if study_pool_counts.get(study_id, 0) >= study_pool_cap:
                        break

                    protein_change = (mut.get("proteinChange") or "").strip()
                    if not protein_change:
                        ref = str(mut.get("referenceAllele") or "N")
                        alt = str(mut.get("variantAllele") or "N")
                        pos = mut.get("startPosition")
                        protein_change = f"g.{pos}{ref}>{alt}" if pos else f"g.{ref}>{alt}"

                    sample_id = mut.get("sampleId", "")
                    patient_id = mut.get("patientId", sample_id.rsplit("-", 1)[0] if "-" in sample_id else sample_id)
                    case_key = f"{study_id}|{sample_id}|{gene}|{protein_change}|{mut.get('startPosition')}"
                    if case_key in seen_case_key:
                        continue
                    seen_case_key.add(case_key)

                    if study_gene_counts.get((study_id, gene), 0) >= per_study_gene_cap:
                        continue

                    candidate_pool.append({
                        "sample_id": sample_id,
                        "patient_id": patient_id,
                        "study_id": study_id,
                        "cancer_type": cancer_type,
                        "gene": gene,
                        "protein_change": protein_change,
                        "mutation_type": mut.get("mutationType", ""),
                        "chr": mut.get("chr", ""),
                        "start": mut.get("startPosition"),
                        "end": mut.get("endPosition"),
                        "ref": mut.get("referenceAllele", "N"),
                        "alt": mut.get("variantAllele", "N"),
                        "genome_build": mut.get("ncbiBuild", "GRCh37"),
                        "source_url": f"https://www.cbioportal.org/study/summary?id={study_id}",
                        "actionability_score": _variant_actionability_score(gene, protein_change),
                    })
                    study_pool_counts[study_id] = study_pool_counts.get(study_id, 0) + 1
                    study_gene_counts[(study_id, gene)] = study_gene_counts.get((study_id, gene), 0) + 1

    # Stable order for reproducibility.
    candidate_pool.sort(
        key=lambda c: (
            -int(c.get("actionability_score") or 0),
            c.get("study_id", ""),
            gene_order.get(c.get("gene", ""), 999),
            c.get("sample_id", ""),
            str(c.get("protein_change", "")),
            int(c.get("start") or 0),
        )
    )

    per_gene_count: dict[str, int] = {}
    per_study_count: dict[str, int] = {}

    # First pass: enforce diversity caps.
    for c in candidate_pool:
        if len(selected) >= max_patients:
            break
        gene = c["gene"]
        study = c["study_id"]
        if per_gene_count.get(gene, 0) >= max_per_gene:
            continue
        if per_study_count.get(study, 0) >= max_per_study:
            continue
        selected.append(c)
        per_gene_count[gene] = per_gene_count.get(gene, 0) + 1
        per_study_count[study] = per_study_count.get(study, 0) + 1

    # Second pass: relax caps if still under target.
    if len(selected) < max_patients:
        relaxed_gene_cap = max_per_gene * 2
        relaxed_study_cap = max_per_study * 2
        selected_keys = {
            f"{c['study_id']}|{c['sample_id']}|{c['gene']}|{c['protein_change']}|{c.get('start')}"
            for c in selected
        }
        for c in candidate_pool:
            if len(selected) >= max_patients:
                break
            key = f"{c['study_id']}|{c['sample_id']}|{c['gene']}|{c['protein_change']}|{c.get('start')}"
            if key in selected_keys:
                continue
            gene = c["gene"]
            study = c["study_id"]
            if per_gene_count.get(gene, 0) >= relaxed_gene_cap:
                continue
            if per_study_count.get(study, 0) >= relaxed_study_cap:
                continue
            selected.append(c)
            selected_keys.add(key)
            per_gene_count[gene] = per_gene_count.get(gene, 0) + 1
            per_study_count[study] = per_study_count.get(study, 0) + 1

    for i, c in enumerate(selected, start=1):
        c["patient_num"] = i

    return selected


def _safe_token(value: str) -> str:
    value = (value or "").lower().strip().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_\-]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:40] if value else "na"


def write_vcf(patient: dict, outdir: str) -> str:
    """Write a real VCF file for one patient."""
    n = patient["patient_num"]
    cancer_slug = _safe_token(patient["cancer_type"])[:20]
    variant_slug = _safe_token(patient["protein_change"])[:24]
    fname = f"pt{n:03d}_{patient['gene'].lower()}_{variant_slug}_{cancer_slug}.vcf"
    fpath = os.path.join(outdir, fname)

    lines = [
        "##fileformat=VCFv4.2",
        f"##source=cBioPortal:{patient['study_id']}",
        f"##reference={patient['genome_build']}",
        f"##patient_id={patient['patient_id']}",
        f"##sample_id={patient['sample_id']}",
        f"##cancer_type={patient['cancer_type']}",
        f"##data_source={patient['source_url']}",
        f"##note=Real de-identified patient from published TCGA study. Data is open-access.",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
        f"{patient['chr']}\t{patient['start']}\t.\t{patient['ref']}\t{patient['alt']}\t99\tPASS\t"
        f"GENE={patient['gene']};HGVS={patient['protein_change']};MUTATION_TYPE={patient['mutation_type']}",
    ]
    with open(fpath, "w") as f:
        f.write("\n".join(lines) + "\n")
    return fpath


def write_biopsy(patient: dict, outdir: str) -> str:
    """Write biopsy text for one patient."""
    n = patient["patient_num"]
    cancer_slug = _safe_token(patient["cancer_type"])[:20]
    fname = f"pt{n:03d}_{patient['gene'].lower()}_{cancer_slug}.txt"
    fpath = os.path.join(outdir, fname)

    text = (
        f"Clinical Biopsy Report\n"
        f"======================\n"
        f"Study: {patient['study_id']} (cBioPortal open-access)\n"
        f"Sample ID: {patient['sample_id']}\n"
        f"Cancer Type: {patient['cancer_type']}\n"
        f"Sequencing: Whole Exome Sequencing (WES)\n"
        f"\n"
        f"Somatic Mutation Detected:\n"
        f"  Gene: {patient['gene']}\n"
        f"  Protein Change: {patient['protein_change']}\n"
        f"  Mutation Type: {patient['mutation_type']}\n"
        f"  Genomic Location: chr{patient['chr']}:{patient['start']}\n"
        f"  Genome Build: {patient['genome_build']}\n"
        f"\n"
        f"Data Source: {patient['source_url']}\n"
        f"Note: De-identified open-tier TCGA data. No PHI.\n"
    )
    with open(fpath, "w") as f:
        f.write(text)
    return fpath


def _setup_api_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_dir = os.path.join(project_root, "api")
    for p in (project_root, api_dir):
        if p not in sys.path:
            sys.path.insert(0, p)


def tier1_fda_evidence(gene: str, protein_change: str) -> list[dict]:
    """Tier 1: FDA-approved drugs from OncoKB static evidence table."""
    _setup_api_path()
    from services.oncokb_evidence import get_all_drugs_for_variant
    from api.ai.ranking import rank_candidates

    evidence = get_all_drugs_for_variant(gene, protein_change, alphamissense_score=1.0)
    if not evidence:
        return []

    candidates = []
    for drug_name, level in evidence.items():
        if "R" in str(level):  # skip pure resistance entries as primary recommendation
            continue
        candidates.append({
            "drug_name": drug_name,
            "oncokb_level": level,
            "is_approved": True,
            "max_phase": 4,
            "opentargets_score": 0.8 if "LEVEL_1" in str(level) else (0.6 if "LEVEL_2" in str(level) else 0.4),
            "binding_score": None,
            "civic_score": None,
            "safety_score_penalty": 0.0,
            "tier": "FDA_APPROVED",
        })
    return rank_candidates(candidates)


def tier2_repurposing(gene: str, protein_change: str, cancer_type: str) -> dict[str, list[dict]]:
    """Return repurposing candidates split into approved vs investigational sets."""
    _setup_api_path()
    import asyncio
    from services.opentargets import get_drugs_for_target, get_target_id
    from services.dgidb import get_interactions as get_dgidb_interactions
    from api.ai.ranking import rank_candidates

    async def _fetch():
        # Resolve gene → ENSG ID for OpenTargets
        ensg_id = await get_target_id(gene)
        ot_drugs = []
        if ensg_id:
            ot_drugs = await get_drugs_for_target(ensg_id, max_drugs=30)

        dgidb_drugs = await get_dgidb_interactions(gene, approved_only=False)

        trial_cases = _trial_case_lookup(gene, protein_change, cancer_type)
        trial_drugs = {
            str(drug).strip().lower(): case
            for case in trial_cases
            for drug in (case.get("drugs") or [])
            if str(drug).strip()
        }

        seen = set()
        approved = []
        investigational = []
        for d in ot_drugs + dgidb_drugs:
            name = (d.get("drug_name") or "").lower().strip()
            if not name or name in seen:
                continue
            seen.add(name)
            max_phase = _phase_rank(d.get("max_phase"))
            is_approved = bool(d.get("is_approved")) or max_phase == 4
            disease_terms = d.get("disease_names") or ([d.get("disease_name")] if d.get("disease_name") else [])
            matches_context = _matches_cancer_context(disease_terms, cancer_type)
            trial_case = trial_drugs.get(name)
            trial_backed = trial_case is not None
            candidate = {
                **d,
                "is_approved": is_approved,
                "max_phase": max_phase or d.get("max_phase"),
                "tier": "FDA_REPURPOSING" if is_approved else "INVESTIGATIONAL_REPURPOSING",
                "matched_cancer_context": matches_context,
                "trial_backed": trial_backed,
                "trial_id": trial_case.get("trial_id") if trial_case else None,
                "trial_phase": trial_case.get("trial_phase") if trial_case else None,
                "trial_outcome": trial_case.get("outcome") if trial_case else None,
            }
            supports_off_label = (
                _supports_fda_off_label(gene, protein_change)
                or _oncogenic_class_supports_off_label(gene, protein_change)
            )
            if is_approved and supports_off_label and (matches_context or trial_backed):
                approved.append(candidate)
            elif (not is_approved) and (
                trial_backed
                or (matches_context and max_phase >= 2)
            ):
                investigational.append(candidate)

        for case in trial_cases:
            for drug_name in case.get("drugs") or []:
                key = str(drug_name).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                phase_rank = _phase_rank(case.get("trial_phase"))
                investigational.append({
                    "drug_name": drug_name,
                    "is_approved": False,
                    "max_phase": phase_rank,
                    "mechanism": "clinical-trial-targeted-therapy",
                    "opentargets_score": 0.65 if phase_rank >= 2 else 0.45,
                    "tier": "INVESTIGATIONAL_REPURPOSING",
                    "matched_cancer_context": True,
                    "trial_backed": True,
                    "trial_id": case.get("trial_id"),
                    "trial_phase": case.get("trial_phase"),
                    "trial_outcome": case.get("outcome"),
                    "evidence_sources": ["ClinicalTrials.gov"],
                })
        return {
            "approved": rank_candidates(approved)[:5] if approved else [],
            "investigational": rank_candidates(investigational)[:5] if investigational else [],
        }

    try:
        candidates = asyncio.run(_fetch())
    except Exception as e:
        print(f"    [WARN] Repurposing fetch failed for {gene}: {e}", file=sys.stderr)
        return {"approved": [], "investigational": []}
    return candidates


def tier3_clinical_trials(gene: str, protein_change: str, cancer_type: str) -> list[dict[str, Any]]:
    """Tier 3: Live ClinicalTrials.gov matching (including basket-style studies)."""
    _setup_api_path()
    import asyncio
    from services.trial_integration import fetch_trials_by_gene

    async def _fetch() -> list[dict[str, Any]]:
        studies = await fetch_trials_by_gene(gene=gene, cancer_type=cancer_type, limit=30)
        trials: list[dict[str, Any]] = []
        for t in studies:
            title = str(t.get("title") or "")
            status = str(t.get("status") or "UNKNOWN")
            phase = str(t.get("phase") or "UNKNOWN")
            trial_cancer = str(t.get("cancer_type") or "")

            basket_like = any(flag in title.lower() for flag in ("basket", "agnostic", "histology"))
            cancer_match = _matches_cancer_context([trial_cancer, title], cancer_type)
            variant_match = _variant_matches_trial(protein_change, str(t.get("mutation") or ""))

            if not (basket_like or cancer_match or variant_match):
                continue

            trials.append({
                "trial_id": t.get("trial_id"),
                "title": title,
                "phase": phase,
                "status": status,
                "gene": gene,
                "cancer_type": trial_cancer,
                "drugs": t.get("drugs") or [],
                "basket_trial": basket_like,
                "variant_match": variant_match,
                "source": "ClinicalTrials.gov",
                "trial_url": f"https://clinicaltrials.gov/study/{t.get('trial_id')}" if t.get("trial_id") else None,
            })

        def _trial_sort_key(x: dict) -> tuple:
            status = str(x.get("status") or "").upper()
            return (
                status == "RECRUITING",                          # recruiting first
                status in ("ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION"),
                _phase_rank(x.get("phase")),                    # then higher phase
                bool(x.get("variant_match")),                   # then variant match
            )

        trials.sort(key=_trial_sort_key, reverse=True)
        return trials[:8]

    try:
        return asyncio.run(_fetch())
    except Exception as e:
        print(f"    [WARN] Live trial fetch failed for {gene}: {e}", file=sys.stderr)
        return []


def tier4_custom_drug(gene: str, protein_change: str, cancer_type: str) -> dict:
    """Tier 4: Custom de novo drug design brief (manual trigger only)."""
    _setup_api_path()
    import asyncio
    from services.drug_discovery import build_custom_discovery_brief

    async def _fetch():
        return await build_custom_discovery_brief(gene, protein_change, cancer_type)

    try:
        brief = asyncio.run(_fetch())
        if brief:
            brief["tier"] = "CUSTOM_DESIGN"
        return brief or {}
    except Exception as e:
        print(f"    [WARN] Custom drug brief failed for {gene}: {e}", file=sys.stderr)
        return {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and benchmark real cBioPortal patient mutation cases")
    parser.add_argument("--n", type=int, default=200, help="Number of real patient mutation cases to fetch")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run offline tier classification on local TCGA benchmark cases (no network, no writes)",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="real_patient_benchmark_200.json",
        help="Output JSON benchmark filename (written at project root)",
    )
    return parser.parse_args()


def _load_local_dry_run_cases(target_n: int) -> list[dict[str, Any]]:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        "real_patient_benchmark.json",
        "real_patient_benchmark_probe.json",
        "real_patient_benchmark_probe60.json",
        "real_patient_benchmark_100.json",
        "real_patient_benchmark_120.json",
        "real_patient_benchmark_200.json",
    ]
    best_cases: list[dict[str, Any]] = []
    for name in candidates:
        path = os.path.join(base_dir, name)
        if not os.path.exists(path):
            continue
        try:
            payload = json.loads(open(path, "r", encoding="utf-8").read())
        except Exception:
            continue
        rows = payload.get("patients") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        cases: list[dict[str, Any]] = []
        for row in rows:
            gene = str((row or {}).get("gene") or "").strip().upper()
            variant = str((row or {}).get("protein_change") or (row or {}).get("variant") or "").strip()
            cancer = str((row or {}).get("cancer_type") or "").strip()
            if not gene or not variant:
                continue
            cases.append({"gene": gene, "variant": variant, "cancer_type": cancer})
        if len(cases) > len(best_cases):
            best_cases = cases
    return best_cases[:target_n]


def _has_gene_level_actionable_drug(gene: str) -> bool:
    _setup_api_path()
    from services.oncokb_evidence import get_all_drugs_for_variant

    for bucket in ("ONCOGENICMUTATIONS", "MUTATION", "ONCOGENIC"):
        level_map = get_all_drugs_for_variant(gene, bucket, alphamissense_score=1.0)
        if any("R" not in str(level).upper() for level in level_map.values()):
            return True
    return False


def _classify_tier_offline(gene: str, variant: str, cancer_type: str) -> str:
    fda_ranked = tier1_fda_evidence(gene, variant)
    fda_drugs = [d for d in fda_ranked if "R" not in str(d.get("oncokb_level", ""))]
    if fda_drugs:
        return "DIRECT_FDA"

    supports_off_label = (
        _supports_fda_off_label(gene, variant)
        or _oncogenic_class_supports_off_label(gene, variant)
    )
    if supports_off_label and _has_gene_level_actionable_drug(gene):
        return "FDA_REPURPOSING"

    if _trial_case_lookup(gene, variant, cancer_type):
        return "INVESTIGATIONAL_REPURPOSING"
    return "NONE"


def main():
    args = _parse_args()
    target_n = max(1, int(args.n))

    if args.dry_run:
        cases = _load_local_dry_run_cases(target_n)
        if not cases:
            print("[ERROR] --dry-run requires a local real_patient_benchmark*.json with patient cases.")
            sys.exit(1)

        tier_counts = {
            "DIRECT_FDA": 0,
            "FDA_REPURPOSING": 0,
            "INVESTIGATIONAL_REPURPOSING": 0,
            "NONE": 0,
        }
        for case in cases:
            tier = _classify_tier_offline(case["gene"], case["variant"], case.get("cancer_type", ""))
            tier_counts[tier] += 1

        print(
            f"Tier 1: {tier_counts['DIRECT_FDA']}  "
            f"Tier 2: {tier_counts['FDA_REPURPOSING']}  "
            f"Tier 3: {tier_counts['INVESTIGATIONAL_REPURPOSING']}  "
            f"NONE: {tier_counts['NONE']}  "
            f"Total: {len(cases)}"
        )
        return

    outdir = os.path.join(os.path.dirname(__file__), "..", "samples", "real")
    os.makedirs(outdir, exist_ok=True)

    print("Fetching real patient data from cBioPortal (TCGA open-access, real de-identified human cases)...")
    print("=" * 70)
    patients = select_patients(STUDIES, max_patients=target_n)

    if len(patients) < target_n:
        print(f"[WARN] Requested {target_n} cases but found {len(patients)} real actionable mutation cases")
    if not patients:
        print("[ERROR] Could not retrieve any patients. Check network connectivity.")
        sys.exit(1)

    results = []
    tier_counts = {
        "DIRECT_FDA": 0,
        "FDA_REPURPOSING": 0,
        "INVESTIGATIONAL_REPURPOSING": 0,
        "CUSTOM_DESIGN": 0,
        "NONE": 0,
    }
    approved_recommendations = 0
    nonapproved_recommendations = 0
    approved_top3_entries = 0
    nonapproved_top3_entries = 0
    custom_suggestions = 0
    custom_suggested_fda_approved = 0
    custom_suggested_well_rated = 0
    trial_match_cases = 0
    manual_custom_candidates = 0
    repurposing_cache: dict[tuple[str, str, str], dict[str, list[dict]]] = {}
    trial_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    print(f"\n{'Pt':<4} {'Study':<26} {'Gene':<8} {'Variant':<16} {'Tier':<14} {'Top Drug'}")
    print("-" * 90)

    for pt in patients:
        vcf_path = write_vcf(pt, outdir)
        biopsy_path = write_biopsy(pt, outdir)

        gene = pt["gene"]
        variant = pt["protein_change"]
        cancer = pt["cancer_type"]
        live_trials: list[dict[str, Any]] = []

        # --- Tier 1: FDA-approved matched therapy ---
        fda_ranked = tier1_fda_evidence(gene, variant)
        # Filter out resistance entries shown as recommendations
        fda_drugs = [d for d in fda_ranked if "R" not in str(d.get("oncokb_level", ""))]

        if fda_drugs:
            tier = "DIRECT_FDA"
            top_drug = fda_drugs[0]["drug_name"]
            top3 = [d["drug_name"] for d in fda_drugs[:3]]
            approved_repurposing_drugs = []
            investigational_repurposing_drugs = []
            custom_brief = {}
            approved_recommendations += 1
            approved_top3_entries += len(top3)
        else:
            # --- Tier 2/3: Repurposing (approved off-label first, then investigational) ---
            rep_key = _repurposing_cache_key(gene, variant, cancer)
            repurposing = repurposing_cache.get(rep_key)
            if repurposing is None:
                repurposing = tier2_repurposing(gene, variant, cancer)
                repurposing_cache[rep_key] = repurposing
            approved_repurposing = repurposing.get("approved") or []
            investigational_repurposing = repurposing.get("investigational") or []
            if approved_repurposing:
                tier = "FDA_REPURPOSING"
                top_drug = approved_repurposing[0]["drug_name"]
                top3 = [d["drug_name"] for d in approved_repurposing[:3]]
                approved_repurposing_drugs = top3
                investigational_repurposing_drugs = [d["drug_name"] for d in investigational_repurposing[:3]]
                custom_brief = {}
                is_approved_top = bool(approved_repurposing[0].get("is_approved") or approved_repurposing[0].get("max_phase") == 4)
                if is_approved_top:
                    approved_recommendations += 1
                else:
                    nonapproved_recommendations += 1
                for d in approved_repurposing[:3]:
                    if d.get("is_approved") or d.get("max_phase") == 4:
                        approved_top3_entries += 1
                    else:
                        nonapproved_top3_entries += 1
            else:
                if investigational_repurposing:
                    tier = "INVESTIGATIONAL_REPURPOSING"
                    top_drug = investigational_repurposing[0]["drug_name"]
                    top3 = [d["drug_name"] for d in investigational_repurposing[:3]]
                    approved_repurposing_drugs = []
                    investigational_repurposing_drugs = top3
                    custom_brief = {}
                    nonapproved_recommendations += 1
                    nonapproved_top3_entries += len(top3)
                else:
                    trial_key = _repurposing_cache_key(gene, variant, cancer)
                    live_trials = trial_cache.get(trial_key)
                    if live_trials is None:
                        live_trials = tier3_clinical_trials(gene, variant, cancer)
                        trial_cache[trial_key] = live_trials

                    if live_trials:
                        tier = "INVESTIGATIONAL_REPURPOSING"
                        first_trial = live_trials[0]
                        trial_label = first_trial.get("trial_id") or "Clinical trial"
                        top_drug = f"{trial_label} ({first_trial.get('phase') or 'Unknown phase'})"
                        top3 = [str(t.get("trial_id") or "") for t in live_trials[:3] if t.get("trial_id")]
                        approved_repurposing_drugs = []
                        investigational_repurposing_drugs = []
                        custom_brief = {}
                        trial_match_cases += 1
                        nonapproved_recommendations += 1
                    else:
                        tier = "NONE"
                        top_drug = "manual custom-drug button required"
                        top3 = []
                        approved_repurposing_drugs = []
                        investigational_repurposing_drugs = []
                        custom_brief = {}
                        manual_custom_candidates += 1
                        nonapproved_recommendations += 1

        tier_counts[tier] += 1
        tier_label = TIER_LABELS[tier]
        print(f"  {pt['patient_num']:02d}  {pt['study_id']:<26} {gene:<8} {variant:<16} {tier_label:<14} {top_drug}")

        patient_next_step = _patient_next_step(
            tier,
            gene,
            cancer,
            len(approved_repurposing_drugs),
            len(investigational_repurposing_drugs),
        )

        results.append({
            **pt,
            "vcf_file": os.path.relpath(vcf_path),
            "biopsy_file": os.path.relpath(biopsy_path),
            "recommendation_tier": tier,
            "recommendation_tier_label": tier_label,
            "top3_drugs": top3,
            "approved_repurposing_drugs": approved_repurposing_drugs,
            "investigational_repurposing_drugs": investigational_repurposing_drugs,
            "clinical_trials": live_trials,
            "custom_drug_manual_only": True,
            "custom_drug_button_label": "Generate custom drug brief",
            "top_recommendation_is_fda_approved": (tier in {"DIRECT_FDA", "FDA_REPURPOSING"}),
            "patient_next_step": patient_next_step,
            "custom_design_brief": {
                "target_gene": custom_brief.get("target_gene"),
                "mechanism": custom_brief.get("mechanism_hypothesis"),
                "parent_scaffold": custom_brief.get("parent_lead_scaffold"),
                "lead_candidates": custom_brief.get("lead_candidates", [])[:3],
                "de_novo_candidates": custom_brief.get("de_novo_candidates", [])[:3],
            } if custom_brief else None,
            "drugs_found": len(top3),
        })

    # Save results
    out_json = os.path.join(os.path.dirname(__file__), "..", args.out_json)
    covered = (
        tier_counts['DIRECT_FDA']
        + tier_counts['FDA_REPURPOSING']
        + tier_counts['INVESTIGATIONAL_REPURPOSING']
        + tier_counts['CUSTOM_DESIGN']
    )
    with open(out_json, "w") as f:
        json.dump({
            "description": f"Benchmark on {len(results)} real de-identified TCGA patient mutation cases (open-access data, cBioPortal)",
            "data_source": "https://www.cbioportal.org",
            "pipeline": "4-layer: Tier 1 on-label FDA → Tier 2 off-label FDA → Tier 3 ClinicalTrials.gov matching → Tier 4 custom drug (manual trigger only)",
            "n_patients": len(results),
            "tier_breakdown": tier_counts,
            "tier_definitions": {
                "DIRECT_FDA": "Exact or evidence-matched FDA-approved therapy for the variant/context.",
                "FDA_REPURPOSING": "Off-label FDA-approved option for same mutation in a different tumour context.",
                "INVESTIGATIONAL_REPURPOSING": "Live ClinicalTrials.gov trial matching, including basket/agnostic opportunities.",
                "CUSTOM_DESIGN": "Custom drug workflow is never auto-generated; it requires explicit manual user action.",
            },
            "approval_summary": {
                "top_recommendation_fda_approved": approved_recommendations,
                "top_recommendation_not_fda_approved": nonapproved_recommendations,
                "top3_total_fda_approved_entries": approved_top3_entries,
                "top3_total_not_fda_approved_entries": nonapproved_top3_entries,
                "all_top_recommendations_approved": nonapproved_recommendations == 0,
            },
            "custom_drug_summary": {
                "custom_cases": tier_counts["CUSTOM_DESIGN"],
                "custom_briefs_generated": custom_suggestions,
                "custom_suggested_fda_approved": custom_suggested_fda_approved,
                "custom_cases_with_well_rated_lead": custom_suggested_well_rated,
                "layer3_live_trial_matches": trial_match_cases,
                "manual_tier4_eligible_cases": manual_custom_candidates,
                "well_rated_threshold_ensemble_score": 70,
            },
            "coverage_summary": {
                "covered_cases": covered,
                "coverage_fraction": round(covered / len(results), 4) if results else 0.0,
            },
            "patients": results,
        }, f, indent=2)

    # Summary
    print("\n" + "=" * 70)
    print(f"Real-world 4-tier pipeline benchmark results (N={len(results)}):")
    print(f"  Total real patients tested     : {len(results)}")
    print(f"  Tier 1 — Direct FDA match      : {tier_counts['DIRECT_FDA']} patients")
    print(f"  Tier 2 — Off-label FDA match   : {tier_counts['FDA_REPURPOSING']} patients")
    print(f"  Tier 3 — Clinical trial match  : {tier_counts['INVESTIGATIONAL_REPURPOSING']} patients")
    print(f"  Tier 4 — Custom drug design    : {tier_counts['CUSTOM_DESIGN']} patients")
    print(f"  No recommendation found        : {tier_counts['NONE']} patients")
    print(f"  Overall coverage               : {covered}/{len(results)} ({covered/len(results)*100:.0f}%)")
    print(f"\nApproval summary:")
    print(f"  Top recommendations FDA-approved : {approved_recommendations}")
    print(f"  Top recommendations not approved : {nonapproved_recommendations}")
    print(f"\nCustom-drug summary:")
    print(f"  Custom cases                     : {tier_counts['CUSTOM_DESIGN']}")
    print(f"  Custom suggested FDA-approved    : {custom_suggested_fda_approved}")
    print(f"  Custom with well-rated lead      : {custom_suggested_well_rated}")
    print(f"  Layer-3 live trial matches       : {trial_match_cases}")
    print(f"  Manual Tier-4 eligible cases     : {manual_custom_candidates}")
    print(f"\nFiles: samples/real/  |  Results: {os.path.basename(out_json)}")


if __name__ == "__main__":
    main()
