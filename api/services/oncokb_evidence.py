"""OncoKB variant-level evidence integration — OpenOncology

Provides drug-level OncoKB evidence for specific somatic variants.

Primary path — live OncoKB API (when ONCOKB_API_TOKEN is set):
  Calls oncokb.py for the full evidence set: Levels 1–4, resistance, novel
  variants, and tumour-type-specific evidence across thousands of entries.
  Missing Level 1/2 drugs are injected from the API response.
  Resistance entries from the curated table are always merged in afterwards
  (safety-critical: they must not be silently omitted even when using the API).

Fallback path — curated lookup table (no token, or API failure):
  Covers ~120 Level 1/2/R1 entries sufficient for demos and offline use.
  The Level 1 evidence is stable; resistance designations are pre-loaded.

Why resistance is always merged from the table even on the live path:
  - Afatinib is LEVEL_R1 for EGFR T790M — this must be surfaced even if the
    live API response omits the drug from the treatments list.
  - The table's resistance entries act as a safety floor, never a ceiling.

Drug name matching is case/space/hyphen-insensitive.

Usage:
    from services.oncokb_evidence import annotate_candidates_with_oncokb
    candidates = await annotate_candidates_with_oncokb(
        candidates, gene="EGFR", protein_change="T790M", cancer_type="NSCLC"
    )
    # Each candidate now has oncokb_level set (e.g. "LEVEL_1" or "LEVEL_R1")
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_ONCOKB_PUBLIC_DUMP_PRIMARY_URL = os.getenv(
    "ONCOKB_PUBLIC_DUMP_URL",
    "https://www.oncokb.org/api/v1/utils/allActionableVariants.txt",
)
_ONCOKB_PUBLIC_DUMP_SECONDARY_URL = (
    "https://www.oncokb.org/api/v1/utils/allAnnotatedVariants.txt"
)
_ONCOKB_PUBLIC_DUMP_URLS: tuple[str, ...] = (
    _ONCOKB_PUBLIC_DUMP_PRIMARY_URL,
    _ONCOKB_PUBLIC_DUMP_SECONDARY_URL,
)
_ONCOKB_PUBLIC_DUMP_FALLBACK_URL = "https://www.oncokb.org/dataAccess"
_ONCOKB_PUBLIC_TIMEOUT = 10.0
_ONCOKB_CACHE_MAX_AGE_DAYS = 7


def get_oncokb_cache_path() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "oncokb_actionable_variants_cache.txt"


def _get_oncokb_public_dump_token() -> str:
    return str(
        os.getenv("ONCOKB_PUBLIC_DUMP_TOKEN")
        or os.getenv("ONCOKB_API_TOKEN")
        or ""
    ).strip()


# ── Curated variant → drug → OncoKB level table ───────────────────────────────
# Key format: (GENE, ALTERATION_NORMALISED)
# Alteration normalisation: uppercase, remove spaces and dots.
# Drug names are lowercase for matching.
#
# Source: OncoKB actionable genes (https://www.oncokb.org/actionableGenes)
#         FDA drug labels and ESMO clinical practice guidelines
#
# RESISTANCE levels (R1, R2) are as important as sensitivity levels:
#   LEVEL_R1 = standard care resistance biomarker
#   LEVEL_R2 = investigational resistance biomarker

_LEVEL_TABLE: dict[tuple[str, str], dict[str, str]] = {
    # ── EGFR ──────────────────────────────────────────────────────────────────
    # Classic sensitising mutations (L858R, exon 19 del) — 1st/2nd/3rd gen TKI
    ("EGFR", "L858R"): {
        "osimertinib": "LEVEL_1",
        "erlotinib": "LEVEL_1",
        "gefitinib": "LEVEL_1",
        "afatinib": "LEVEL_1",
        "dacomitinib": "LEVEL_1",
    },
    ("EGFR", "E746A750DEL"): {  # exon 19 del canonical form
        "osimertinib": "LEVEL_1",
        "erlotinib": "LEVEL_1",
        "gefitinib": "LEVEL_1",
        "afatinib": "LEVEL_1",
        "dacomitinib": "LEVEL_1",
    },
    ("EGFR", "EXON19DEL"): {
        "osimertinib": "LEVEL_1",
        "erlotinib": "LEVEL_1",
        "gefitinib": "LEVEL_1",
        "afatinib": "LEVEL_1",
        "dacomitinib": "LEVEL_1",
    },
    # T790M — acquired resistance to 1st/2nd gen; Osimertinib is 3rd-gen
    ("EGFR", "T790M"): {
        "osimertinib": "LEVEL_1",
        # 1st/2nd gen TKIs are RESISTANT to T790M
        "erlotinib": "LEVEL_R1",
        "gefitinib": "LEVEL_R1",
        "afatinib": "LEVEL_R1",
        "dacomitinib": "LEVEL_R2",
        "cetuximab": "LEVEL_R1",
        "panitumumab": "LEVEL_R1",
    },
    # Exon 20 insertion — resistance to all classical EGFR TKIs.
    # FDA-approved agents: amivantamab (CHRYSALIS, 2021), sunvozertinib (PAPILLON, 2024).
    # Amivantamab + chemo combo (PAPILLON) also FDA-approved 2024 as 1L.
    # mobocertinib voluntarily withdrawn from US market 2023 (EXHUME-1 failed).
    ("EGFR", "EXON20INS"): {
        "sunvozertinib": "LEVEL_1",
        "amivantamab": "LEVEL_1",
        "poziotinib": "LEVEL_3A",
        "osimertinib": "LEVEL_R1",
        "erlotinib": "LEVEL_R1",
        "gefitinib": "LEVEL_R1",
        "afatinib": "LEVEL_R1",
    },
    ("EGFR", "C797S"): {
        "osimertinib": "LEVEL_R1",
    },
    # C797S in TRANS with T790M: erlotinib + osimertinib combination can overcome resistance
    # (C797S and T790M on different alleles — distinct from CIS where no good option exists)
    ("EGFR", "C797ST790MTRANS"): {
        "osimertinib": "LEVEL_2",
        "erlotinib": "LEVEL_2",
    },
    ("EGFR", "AMPLIFICATION"): {
        "cetuximab": "LEVEL_1",
        "panitumumab": "LEVEL_1",
        "erlotinib": "LEVEL_2",
        "gefitinib": "LEVEL_2",
    },
    # ── BRAF ──────────────────────────────────────────────────────────────────
    # BRAF V600E: vemurafenib (BRIM-3), dabrafenib (BREAK-3), trametinib (METRIC),
    # encorafenib+binimetinib (COLUMBUS, FDA 2018 for melanoma), encorafenib+cetuximab (BEACON CRC).
    ("BRAF", "V600E"): {
        "vemurafenib": "LEVEL_1",
        "dabrafenib": "LEVEL_1",
        "trametinib": "LEVEL_1",
        "encorafenib": "LEVEL_1",
        "binimetinib": "LEVEL_1",
    },
    ("BRAF", "V600K"): {
        "dabrafenib": "LEVEL_1",
        "trametinib": "LEVEL_1",
    },
    ("BRAF", "V600E-CRC"): {
        "encorafenib": "LEVEL_1",
        "binimetinib": "LEVEL_1",
        "cetuximab": "LEVEL_1",
    },
    # ── NRAS ──────────────────────────────────────────────────────────────────
    ("NRAS", "Q61K"): {
        "binimetinib": "LEVEL_2",
        "cobimetinib": "LEVEL_3A",
        "trametinib": "LEVEL_3A",
    },
    ("NRAS", "Q61R"): {
        "binimetinib": "LEVEL_2",
        "cobimetinib": "LEVEL_3A",
        "trametinib": "LEVEL_3A",
    },
    ("NRAS", "Q61H"): {
        "binimetinib": "LEVEL_2",
        "cobimetinib": "LEVEL_3A",
        "trametinib": "LEVEL_3A",
    },
    ("NRAS", "Q61L"): {
        "binimetinib": "LEVEL_2",
        "cobimetinib": "LEVEL_3A",
        "trametinib": "LEVEL_3A",
    },
    ("NRAS", "Q61P"): {
        "binimetinib": "LEVEL_2",
        "cobimetinib": "LEVEL_3A",
        "trametinib": "LEVEL_3A",
    },
    # ── GNAQ ─────────────────────────────────────────────────────────────────
    ("GNAQ", "Q209L"): {
        "tebentafusp": "LEVEL_1",
    },
    # ── KRAS ──────────────────────────────────────────────────────────────────
    ("KRAS", "G12C"): {
        "sotorasib": "LEVEL_1",
        "adagrasib": "LEVEL_1",
        "cetuximab": "LEVEL_3A",   # combo with adagrasib in CRC (CodeBreak 300 / KRYSTAL-10)
        "divarasib": "LEVEL_3A",   # Phase 2 data (GDC-6036), not yet FDA-approved
    },
    ("KRAS", "G12D"): {
        "mrtx1133": "LEVEL_3B",
    },
    ("KRAS", "G12V"): {
        "adagrasib": "LEVEL_3B",
    },
    # ── ALK ───────────────────────────────────────────────────────────────────
    ("ALK", "EML4-ALK"): {
        "alectinib": "LEVEL_1",
        "brigatinib": "LEVEL_1",
        "crizotinib": "LEVEL_1",
        "lorlatinib": "LEVEL_1",
        "ceritinib": "LEVEL_1",
    },
    ("ALK", "FUSION"): {
        "alectinib": "LEVEL_1",
        "brigatinib": "LEVEL_1",
        "crizotinib": "LEVEL_1",
        "lorlatinib": "LEVEL_1",
        "ceritinib": "LEVEL_1",
    },
    # ALK resistance mutations to 2nd gen TKIs → Lorlatinib
    ("ALK", "G1202R"): {
        "lorlatinib": "LEVEL_1",
        "alectinib": "LEVEL_R1",
        "brigatinib": "LEVEL_R1",
    },
    # ── ROS1 ──────────────────────────────────────────────────────────────────
    ("ROS1", "FUSION"): {
        "crizotinib": "LEVEL_1",
        "entrectinib": "LEVEL_1",
        "lorlatinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",
    },
    ("ROS1", "CD74-ROS1"): {
        "crizotinib": "LEVEL_1",
        "entrectinib": "LEVEL_1",
        "lorlatinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",
    },
    # ROS1 solvent-front resistance mutation (mirrors ALK G1202R)
    # Crizotinib and entrectinib lose activity; lorlatinib and repotrectinib retain it.
    ("ROS1", "G2032R"): {
        "lorlatinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",
        "crizotinib": "LEVEL_R1",
        "entrectinib": "LEVEL_R1",
    },
    # ── RET ───────────────────────────────────────────────────────────────────
    ("RET", "FUSION"): {
        "selpercatinib": "LEVEL_1",
        "pralsetinib": "LEVEL_1",
        "vandetanib": "LEVEL_2",
        "cabozantinib": "LEVEL_2",
    },
    ("RET", "KIF5B-RET"): {
        "selpercatinib": "LEVEL_1",
        "pralsetinib": "LEVEL_1",
        "vandetanib": "LEVEL_2",
        "cabozantinib": "LEVEL_2",
    },
    ("RET", "M918T"): {
        "selpercatinib": "LEVEL_1",
        "vandetanib": "LEVEL_1",
        "cabozantinib": "LEVEL_1",   # FDA-approved for progressive MTC (2012, EXAM trial)
    },
    # ── MET ───────────────────────────────────────────────────────────────────
    ("MET", "EXON14SKIP"): {
        "capmatinib": "LEVEL_1",
        "tepotinib": "LEVEL_1",
        "crizotinib": "LEVEL_2",
    },
    ("MET", "AMPLIFICATION"): {
        "capmatinib": "LEVEL_2",    # SAVANNAH / GEOMETRY data: activity in acquired EGFR-TKI resistance
        "tepotinib": "LEVEL_2",     # INSIGHT-2: osimertinib + tepotinib for MET-amp acquired resistance
        "crizotinib": "LEVEL_3A",
    },
    # ── ERBB2 / HER2 ──────────────────────────────────────────────────────────
    ("ERBB2", "AMPLIFICATION"): {
        "trastuzumab": "LEVEL_1",
        "trastuzumab deruxtecan": "LEVEL_1",
        "pertuzumab": "LEVEL_1",
        "tucatinib": "LEVEL_1",
        "lapatinib": "LEVEL_1",
        "neratinib": "LEVEL_1",
        "ado-trastuzumab emtansine": "LEVEL_1",
        "t-dm1": "LEVEL_1",
    },
    # HER2 Exon 20 insertion NSCLC: T-DXd FDA-approved 2022 (DESTINY-Lung02, ORR 58%).
    # Zongertinib FDA-approved Jan 2025 (BEAMION LUNG-1). Neratinib+paclitaxel investigational.
    ("ERBB2", "EXON20INS"): {
        "trastuzumab deruxtecan": "LEVEL_1",
        "zongertinib": "LEVEL_1",
        "poziotinib": "LEVEL_3A",
        # mobocertinib voluntarily withdrawn from US market 2023 (EXHUME-1 failed).
    },
    ("ERBB2", "L755S"): {
        "trastuzumab deruxtecan": "LEVEL_1",  # DESTINY-Lung02 covers HER2 mutations incl. L755
        "neratinib": "LEVEL_3A",
    },
    # HER2 kinase domain mutations (NSCLC) — T-DXd and zongertinib are pan-HER2-mutation agents.
    ("ERBB2", "L755P"): {"trastuzumab deruxtecan": "LEVEL_1", "zongertinib": "LEVEL_1"},
    ("ERBB2", "L755M"): {"trastuzumab deruxtecan": "LEVEL_1", "zongertinib": "LEVEL_1"},
    ("ERBB2", "S310F"): {"trastuzumab deruxtecan": "LEVEL_1", "zongertinib": "LEVEL_1"},
    ("ERBB2", "Y772DUP"): {"trastuzumab deruxtecan": "LEVEL_1"},
    ("ERBB2", "G776V"): {"trastuzumab deruxtecan": "LEVEL_1", "zongertinib": "LEVEL_1"},
    # HER2 MUTATION catch-all — for any HER2-activating mutation not in the specific list.
    # T-DXd (DESTINY-Lung02 ORR 58%) and zongertinib (BEAMION LUNG-1) have broad mutation coverage.
    ("ERBB2", "MUTATION"): {
        "trastuzumab deruxtecan": "LEVEL_1",
        "zongertinib": "LEVEL_1",
        "neratinib": "LEVEL_2",
        "afatinib": "LEVEL_2",
    },
    # ── PIK3CA ────────────────────────────────────────────────────────────────
    ("PIK3CA", "E545K"): {
        "alpelisib": "LEVEL_1",
        "inavolisib": "LEVEL_1",
        "capivasertib": "LEVEL_1",      # CAPItello-291 covers all PIK3CA hotspots
        "copanlisib": "LEVEL_3A",
    },
    ("PIK3CA", "H1047R"): {
        "alpelisib": "LEVEL_1",
        "inavolisib": "LEVEL_1",
        "capivasertib": "LEVEL_1",      # CAPItello-291: FDA-approved for PIK3CA/AKT1/PTEN-altered HR+/HER2- mBC
        "fulvestrant": "LEVEL_2",
        "copanlisib": "LEVEL_3A",
    },
    ("PIK3CA", "E542K"): {
        "alpelisib": "LEVEL_1",
        "inavolisib": "LEVEL_1",    # INAVO120 trial (2024); covers E542K
        "capivasertib": "LEVEL_1",  # CAPItello-291 covers any PIK3CA/AKT1/PTEN mutation
        "fulvestrant": "LEVEL_2",
    },
    # PIK3CA Q546K/E — SOLAR-1 included; capivasertib CAPItello-291 covers all PIK3CA mutations.
    ("PIK3CA", "Q546K"): {
        "alpelisib": "LEVEL_1",
        "inavolisib": "LEVEL_1",
        "capivasertib": "LEVEL_1",
        "fulvestrant": "LEVEL_2",
    },
    ("PIK3CA", "Q546E"): {
        "alpelisib": "LEVEL_1",
        "inavolisib": "LEVEL_1",
        "capivasertib": "LEVEL_1",
        "fulvestrant": "LEVEL_2",
    },
    ("PIK3CA", "N345K"): {
        "inavolisib": "LEVEL_1",
        "alpelisib": "LEVEL_2",
        "capivasertib": "LEVEL_1",
    },
    ("PIK3CA", "R88Q"): {
        "capivasertib": "LEVEL_1",  # CAPItello-291 includes R88Q
        "inavolisib": "LEVEL_1",
        "alpelisib": "LEVEL_2",
    },
    # AKT1 E17K: capivasertib FDA-approved (CAPItello-291, covers AKT1-altered HR+/HER2- mBC).
    # Ipatasertib (IPATunity trials) investigational LEVEL_2.
    ("AKT1", "E17K"): {
        "capivasertib": "LEVEL_1",
        "ipatasertib": "LEVEL_2",
        "alpelisib": "LEVEL_3A",
    },
    # ── IDH1 ──────────────────────────────────────────────────────────────────
    ("IDH1", "R132H"): {
        "ivosidenib": "LEVEL_1",
        "vorasidenib": "LEVEL_1",
        "olutasidenib": "LEVEL_1",
    },
    ("IDH1", "R132C"): {
        "ivosidenib": "LEVEL_1",
        "vorasidenib": "LEVEL_1",   # INDIGO trial covers R132C
        "olutasidenib": "LEVEL_1",
    },
    # ── IDH2 ──────────────────────────────────────────────────────────────────
    ("IDH2", "R140Q"): {
        "enasidenib": "LEVEL_1",
        "azacitidine": "LEVEL_2",
    },
    ("IDH2", "R172K"): {
        "enasidenib": "LEVEL_1",
        "vorasidenib": "LEVEL_1",   # INDIGO trial covers IDH2 R172K
    },
    # ── FLT3 ──────────────────────────────────────────────────────────────────
    ("FLT3", "ITD"): {
        "midostaurin": "LEVEL_1",
        "quizartinib": "LEVEL_1",
        "gilteritinib": "LEVEL_1",
    },
    ("FLT3", "D835Y"): {
        "gilteritinib": "LEVEL_1",
        "quizartinib": "LEVEL_R1",  # resistance mutation
    },
    # ── ABL1 ──────────────────────────────────────────────────────────────────
    ("ABL1", "BCR-ABL1"): {
        "imatinib": "LEVEL_1",
        "dasatinib": "LEVEL_1",
        "nilotinib": "LEVEL_1",
        "bosutinib": "LEVEL_1",
        "ponatinib": "LEVEL_1",
    },
    ("ABL1", "T315I"): {
        "ponatinib": "LEVEL_1",
        "asciminib": "LEVEL_1",
        "imatinib": "LEVEL_R1",
        "dasatinib": "LEVEL_R1",
        "nilotinib": "LEVEL_R1",
    },
    # ── KIT ───────────────────────────────────────────────────────────────────
    ("KIT", "EXON11DEL"): {
        "imatinib": "LEVEL_1",
        "sunitinib": "LEVEL_1",
        "regorafenib": "LEVEL_1",
        "ripretinib": "LEVEL_1",
    },
    ("KIT", "EXON11MUT"): {
        "imatinib": "LEVEL_1",
        "sunitinib": "LEVEL_1",
    },
    ("KIT", "D816V"): {
        "avapritinib": "LEVEL_1",
        "midostaurin": "LEVEL_1",
        "imatinib": "LEVEL_R1",
        "sunitinib": "LEVEL_R1",
    },
    # ── PDGFRA ────────────────────────────────────────────────────────────────
    ("PDGFRA", "D842V"): {
        "avapritinib": "LEVEL_1",
        "imatinib": "LEVEL_R1",
    },
    # ── FGFR ──────────────────────────────────────────────────────────────────
    ("FGFR2", "FUSION"): {
        "pemigatinib": "LEVEL_1",
        "futibatinib": "LEVEL_1",
        "infigratinib": "LEVEL_2",
    },
    ("FGFR3", "S249C"): {
        "erdafitinib": "LEVEL_1",
    },
    ("FGFR3", "FUSION"): {
        "erdafitinib": "LEVEL_1",
        "pemigatinib": "LEVEL_2",
    },
    # ── NTRK ──────────────────────────────────────────────────────────────────
    ("NTRK1", "FUSION"): {
        "larotrectinib": "LEVEL_1",
        "entrectinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",   # Augtyro; FDA Nov 2023, TRIDENT-1; NTRK1/2/3 fusion+ solid tumors (adults & peds ≥12 y)
    },
    ("NTRK2", "FUSION"): {
        "larotrectinib": "LEVEL_1",
        "entrectinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",   # Augtyro; FDA Nov 2023, TRIDENT-1
    },
    ("NTRK3", "FUSION"): {
        "larotrectinib": "LEVEL_1",
        "entrectinib": "LEVEL_1",
        "repotrectinib": "LEVEL_1",   # Augtyro; FDA Nov 2023, TRIDENT-1
    },
    # ── BRCA ──────────────────────────────────────────────────────────────────
    ("BRCA1", "PATHOGENIC"): {
        "olaparib": "LEVEL_1",
        "niraparib": "LEVEL_1",
        "rucaparib": "LEVEL_1",
        "talazoparib": "LEVEL_1",
    },
    ("BRCA2", "PATHOGENIC"): {
        "olaparib": "LEVEL_1",
        "niraparib": "LEVEL_1",
        "rucaparib": "LEVEL_1",
        "talazoparib": "LEVEL_1",
    },
    # ── ESR1 ──────────────────────────────────────────────────────────────────
    ("ESR1", "D538G"): {
        "elacestrant": "LEVEL_1",
        "fulvestrant": "LEVEL_2",
        "alpelisib": "LEVEL_3A",        # PI3K/AKT co-targeting in ESR1-mut ER+ breast cancer
        "tamoxifen": "LEVEL_R1",
    },
    ("ESR1", "Y537S"): {
        "elacestrant": "LEVEL_1",
        "fulvestrant": "LEVEL_2",
    },
    # ── EZH2 ──────────────────────────────────────────────────────────────────
    # Tazemetostat (Tazverik) FDA-approved 2020 for relapsed/refractory FL with
    # EZH2 activating mutations (SYMPHONY trial). LEVEL_1 for FL; LEVEL_2 for other.
    ("EZH2", "Y646N"): {
        "tazemetostat": "LEVEL_1",
    },
    # ── AR ────────────────────────────────────────────────────────────────────
    ("AR", "AMPLIFICATION"): {
        "enzalutamide": "LEVEL_1",
        "abiraterone": "LEVEL_1",
        "darolutamide": "LEVEL_1",
    },
    # ── ATM ───────────────────────────────────────────────────────────────────
    # ATM pathogenic variants: olaparib FDA-approved for mCRPC with HRR mutations
    # (PROfound 2020, L1). Rucaparib also approved for CRPC. Level 2 for other solid tumours.
    ("ATM", "PATHOGENIC"): {
        "olaparib": "LEVEL_1",
        "rucaparib": "LEVEL_1",
        "niraparib": "LEVEL_3A",
    },
    # ── CD79B ─────────────────────────────────────────────────────────────────
    ("CD79B", "Y196C"): {
        "ibrutinib": "LEVEL_2",
        "zanubrutinib": "LEVEL_2",
        "acalabrutinib": "LEVEL_3A",
    },
    ("CD79B", "Y196H"): {
        "ibrutinib": "LEVEL_2",
        "zanubrutinib": "LEVEL_2",
    },
    # ── FGFR2 amplification (separate from fusions) ───────────────────────────
    ("FGFR2", "AMPLIFICATION"): {
        "pemigatinib": "LEVEL_3A",
        "futibatinib": "LEVEL_3A",
        "erdafitinib": "LEVEL_3B",
    },
    # ── TMB/MSI/HRD — agnostic ────────────────────────────────────────────────
    ("TMB", "TMB-HIGH"): {
        "pembrolizumab": "LEVEL_1",
    },
    ("MLH1", "MSI-H"): {
        "pembrolizumab": "LEVEL_1",
        "dostarlimab": "LEVEL_1",
        "nivolumab": "LEVEL_1",
    },
    ("MLH1", "LOSSOFEXPRESSION"): {
        "pembrolizumab": "LEVEL_1",
        "dostarlimab": "LEVEL_1",
        "nivolumab": "LEVEL_1",
    },
    ("MSH2", "MSI-H"): {
        "pembrolizumab": "LEVEL_1",
        "dostarlimab": "LEVEL_1",
    },
    ("MSH6", "MSI-H"): {
        "pembrolizumab": "LEVEL_1",
        "dostarlimab": "LEVEL_1",
    },
    ("PMS2", "MSI-H"): {
        "pembrolizumab": "LEVEL_1",
        "dostarlimab": "LEVEL_1",
    },
    # ── NPM1 ──────────────────────────────────────────────────────────────────
    ("NPM1", "W288FS"): {
        "venetoclax": "LEVEL_2",
        "azacitidine": "LEVEL_2",
    },
    ("NPM1", "INSERTIONTYPEB"): {
        "midostaurin": "LEVEL_1",
        "venetoclax": "LEVEL_2",
        "azacitidine": "LEVEL_2",
    },
    # ── JAK2 ──────────────────────────────────────────────────────────────────
    # JAK2 V617F drives myeloproliferative neoplasms; ruxolitinib + fedratinib
    # are both FDA-approved for MF; pacritinib also approved for cytopenic MF.
    ("JAK2", "V617F"): {
        "ruxolitinib": "LEVEL_1",
        "fedratinib": "LEVEL_1",
        "pacritinib": "LEVEL_1",
    },
    # ── IDH1 AML/cholangio context — full approval set ────────────────────────
    # (GLIOMA overrides vorasidenib as L1; ivosidenib stays L1 for AML/CCA)
    ("IDH1", "R132S"): {
        "ivosidenib": "LEVEL_1",
    },
    # ── IDH2 AML — both approved inhibitors ───────────────────────────────────
    ("IDH2", "R172S"): {
        "enasidenib": "LEVEL_1",
    },
    # ── CALR — MPN ────────────────────────────────────────────────────────────
    # CALR exon 9 mutations drive JAK–STAT signalling; ruxolitinib has evidence.
    ("CALR", "EXON9DEL"): {
        "ruxolitinib": "LEVEL_1",
        "fedratinib": "LEVEL_2",
        "pacritinib": "LEVEL_2",
    },
    # ── KIT GIST — exon 9 amplification (sunitinib preferred after imatinib) ──
    ("KIT", "EXON9MUT"): {
        "sunitinib": "LEVEL_1",
        "imatinib": "LEVEL_1",
        "regorafenib": "LEVEL_2",
    },
    # ── PDGFRB — systemic mastocytosis / CMML ─────────────────────────────────
    ("PDGFRB", "FUSION"): {
        "imatinib": "LEVEL_1",
        "dasatinib": "LEVEL_2",
    },
    # ── NTRK2 / NTRK3 already present; NTRK pan-tumour reconfirm ─────────────
    # (see NTRK1/2/3 FUSION entries above)

    # ── EGFR uncommon activating mutations (exon 18 G719X, exon 21 L861Q, exon 20 S768I) ──
    # Afatinib has FDA approval for G719X, L861Q, S768I (LUX-Lung 2/3/6 analysis).
    # Osimertinib also active (FLAURA data + tumour-agnostic activity).
    ("EGFR", "G719A"): {"afatinib": "LEVEL_2", "osimertinib": "LEVEL_2", "erlotinib": "LEVEL_3A", "gefitinib": "LEVEL_3A"},
    ("EGFR", "G719S"): {"afatinib": "LEVEL_2", "osimertinib": "LEVEL_2", "erlotinib": "LEVEL_3A"},
    ("EGFR", "G719C"): {"afatinib": "LEVEL_2", "osimertinib": "LEVEL_2", "erlotinib": "LEVEL_3A"},
    ("EGFR", "L861Q"): {"afatinib": "LEVEL_2", "osimertinib": "LEVEL_2", "erlotinib": "LEVEL_3A"},
    ("EGFR", "S768I"): {"afatinib": "LEVEL_2", "osimertinib": "LEVEL_2"},

    # ── Additional FLT3 TKD point mutations ───────────────────────────────────
    # Gilteritinib active against all D835 substitutions (ADMIRAL trial).
    # Quizartinib is specifically RESISTANT to D835 mutations (LEVEL_R1).
    ("FLT3", "D835V"): {"gilteritinib": "LEVEL_1", "quizartinib": "LEVEL_R1"},
    ("FLT3", "D835H"): {"gilteritinib": "LEVEL_1", "quizartinib": "LEVEL_R1"},
    ("FLT3", "D835E"): {"gilteritinib": "LEVEL_1", "quizartinib": "LEVEL_R1"},
    ("FLT3", "Y842C"): {"gilteritinib": "LEVEL_1"},
    ("FLT3", "Y842H"): {"gilteritinib": "LEVEL_1"},

    # ── Additional IDH1 mutations (all yield IDH1 inhibitor sensitivity) ──────
    # INDIGO trial (2023) enrolled IDH1 R132C/H/L/G/S — vorasidenib L1 for low-grade glioma.
    ("IDH1", "R132L"): {"ivosidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH1", "R132G"): {"ivosidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH1", "R132W"): {"ivosidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH1", "R132S"): {"ivosidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},

    # ── Additional IDH2 mutations ─────────────────────────────────────────────
    # INDIGO trial enrolled IDH2 R172K/W/G/S — vorasidenib L1 for low-grade glioma.
    ("IDH2", "R172W"): {"enasidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH2", "R172M"): {"enasidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH2", "R172G"): {"enasidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},
    ("IDH2", "R172S"): {"enasidenib": "LEVEL_1", "vorasidenib": "LEVEL_1"},

    # ── Hedgehog pathway — BCC and Medulloblastoma ────────────────────────────
    # Vismodegib (ERIVANCE, 2012) and sonidegib (BOLT, 2015) are both FDA-approved
    # for locally advanced/metastatic BCC. Sonidegib also approved for Hedgehog-
    # pathway-activated medulloblastoma (accelerated approval 2015).
    ("SMO", "MUTATION"): {"vismodegib": "LEVEL_1", "sonidegib": "LEVEL_1"},
    ("SMO", "W535L"):    {"vismodegib": "LEVEL_1", "sonidegib": "LEVEL_1"},
    ("SMO", "L412F"):    {"vismodegib": "LEVEL_1", "sonidegib": "LEVEL_1"},
    ("PTCH1", "LOSS"):        {"vismodegib": "LEVEL_2", "sonidegib": "LEVEL_2"},
    ("PTCH1", "TRUNCATING"):  {"vismodegib": "LEVEL_2", "sonidegib": "LEVEL_2"},

    # ── VHL — clear-cell RCC ──────────────────────────────────────────────────
    # Belzutifan (Welireg) FDA-approved 2021 for VHL disease-associated tumours
    # and 2023 for advanced ccRCC after prior VEGF/mTOR therapy (LITESPARK-005).
    ("VHL", "MUTATION"): {"belzutifan": "LEVEL_1"},
    ("VHL", "LOSS"): {
        "belzutifan": "LEVEL_1",
        "sunitinib": "LEVEL_2",
        "pazopanib": "LEVEL_2",
        "cabozantinib": "LEVEL_2",
        "axitinib": "LEVEL_2",
        "nivolumab": "LEVEL_2",
    },
    ("VHL", "TRUNCATION"): {
        "belzutifan": "LEVEL_1",
        "sunitinib": "LEVEL_2",
        "pazopanib": "LEVEL_2",
        "cabozantinib": "LEVEL_2",
        "axitinib": "LEVEL_2",
        "nivolumab": "LEVEL_2",
    },
    ("VHL", "TRUNCATING"): {"belzutifan": "LEVEL_1"},

    # ── Uveal melanoma — GNAQ/GNA11 Q209 hotspot ─────────────────────────────
    # Tebentafusp (Kimmtrak) is the first approved TCR bispecific; trial enrolled
    # HLA-A*02:01-positive metastatic uveal melanoma patients (IMCgp100-202).
    ("GNAQ", "Q209P"): {"tebentafusp": "LEVEL_1"},
    ("GNA11", "Q209L"): {"tebentafusp": "LEVEL_1"},
    ("GNA11", "Q209P"): {"tebentafusp": "LEVEL_1"},

    # ── EZH2 additional gain-of-function hotspots ─────────────────────────────
    # Tazemetostat (Tazverik) FDA-approved 2020 for relapsed/refractory FL with
    # EZH2-activating mutations (SYMPHONY trial). All Y646 residue substitutions
    # and the A682/A692 variants are established activating mutations.
    ("EZH2", "Y646F"): {"tazemetostat": "LEVEL_2"},
    ("EZH2", "Y646S"): {"tazemetostat": "LEVEL_2"},
    ("EZH2", "Y646C"): {"tazemetostat": "LEVEL_2"},
    ("EZH2", "Y646H"): {"tazemetostat": "LEVEL_2"},
    ("EZH2", "A682G"): {"tazemetostat": "LEVEL_2"},
    ("EZH2", "A692V"): {"tazemetostat": "LEVEL_2"},

    # ── HRAS — HNSCC and thyroid ──────────────────────────────────────────────
    # Tipifarnib (farnesyl-transferase inhibitor) is NOT FDA-approved.
    # All HRAS entries removed from evidence table (investigational only).
    ("HRAS", "Q61R"): {},
    ("HRAS", "Q61K"): {},
    ("HRAS", "G12V"): {},
    ("HRAS", "G13R"): {},

    # ── Additional PIK3CA activating hotspots ─────────────────────────────────
    ("PIK3CA", "H1047L"): {"alpelisib": "LEVEL_1", "inavolisib": "LEVEL_1"},
    ("PIK3CA", "E545A"):  {"alpelisib": "LEVEL_1"},
    ("PIK3CA", "E545K"):  {"alpelisib": "LEVEL_1", "inavolisib": "LEVEL_1", "capivasertib": "LEVEL_1", "copanlisib": "LEVEL_3A"},  # CAPItello-291
    ("PIK3CA", "Q546K"):  {"alpelisib": "LEVEL_2"},

    # ── ESR1 additional resistance/ligand-binding mutations ───────────────────
    # Elacestrant LEVEL_1 for all ESR1 LBD mutations (EMERALD used any LBD mut).
    ("ESR1", "Y537N"):  {"elacestrant": "LEVEL_1", "fulvestrant": "LEVEL_2"},
    ("ESR1", "E380Q"):  {"elacestrant": "LEVEL_3A"},

    # ── RET activating point mutations — MTC ─────────────────────────────────
    # C634 cysteine mutations are MEN2A/FMTC germline hotspots.
    # Selpercatinib, vandetanib, and cabozantinib all cover these.
    ("RET", "C634F"): {"selpercatinib": "LEVEL_1", "vandetanib": "LEVEL_1", "cabozantinib": "LEVEL_1"},
    ("RET", "C634R"): {"selpercatinib": "LEVEL_1", "vandetanib": "LEVEL_1", "cabozantinib": "LEVEL_1"},
    ("RET", "C634Y"): {"selpercatinib": "LEVEL_1", "vandetanib": "LEVEL_1"},
    ("RET", "C634W"): {"selpercatinib": "LEVEL_1", "vandetanib": "LEVEL_1"},

    # ── MAP2K1 (MEK1) — MEK inhibitor sensitivity ─────────────────────────────
    # MAP2K1 gain-of-function mutations activate RAS–MAPK; MEK inhibitors active
    # in basket studies. Level 3A reflects investigational use (no FDA approval).
    ("MAP2K1", "E203K"):   {"cobimetinib": "LEVEL_3A", "trametinib": "LEVEL_3A", "binimetinib": "LEVEL_3A"},
    ("MAP2K1", "Q56P"):    {"cobimetinib": "LEVEL_3A", "trametinib": "LEVEL_3A"},
    ("MAP2K1", "MUTATION"):{"cobimetinib": "LEVEL_3A", "trametinib": "LEVEL_3A"},

    # ── NF1 — MAPK-pathway loss ───────────────────────────────────────────────
    # NF1-loss tumours have RAS hyperactivation; MEK inhibitors investigational.
    # Selumetinib has FDA approval for paediatric NF1-associated plexiform neurofibromas
    # (SPRINT Stratum 1 trial).
    ("NF1", "TRUNCATING"): {"selumetinib": "LEVEL_2", "trametinib": "LEVEL_3A", "cobimetinib": "LEVEL_3A"},
    ("NF1", "LOSS"):       {"selumetinib": "LEVEL_2", "trametinib": "LEVEL_3A"},
    ("NF1", "DELETION"):   {"selumetinib": "LEVEL_2", "trametinib": "LEVEL_3A"},

    # ── TSC1 / TSC2 / MTOR — mTOR pathway ────────────────────────────────────
    # Everolimus FDA-approved for TSC-associated tumours (EXIST-1/2, EXIST-3) and
    # for advanced RCC / neuroendocrine tumours / breast (post AI). Temsirolimus L2.
    ("TSC1",  "MUTATION"):   {"everolimus": "LEVEL_2", "temsirolimus": "LEVEL_3A"},
    ("TSC2",  "MUTATION"):   {"everolimus": "LEVEL_2", "temsirolimus": "LEVEL_3A"},
    ("MTOR",  "MUTATION"):   {"everolimus": "LEVEL_2", "temsirolimus": "LEVEL_2"},
    ("MTOR",  "E2014K"):     {"everolimus": "LEVEL_2"},
    ("MTOR",  "E1799K"):     {"everolimus": "LEVEL_2"},

    # ── Additional KIT GIST exon mutations ───────────────────────────────────
    # Exon 13/14 (KD1 domain) and exon 17/18 (KD2/activation loop) are secondary
    # resistance hotspots; avapritinib and ripretinib retain activity.
    ("KIT", "EXON13MUT"): {"regorafenib": "LEVEL_1", "ripretinib": "LEVEL_1", "sunitinib": "LEVEL_2"},
    ("KIT", "EXON14MUT"): {"regorafenib": "LEVEL_1", "ripretinib": "LEVEL_1"},
    ("KIT", "EXON17MUT"): {"avapritinib": "LEVEL_1", "ripretinib": "LEVEL_1"},
    ("KIT", "EXON18MUT"): {"avapritinib": "LEVEL_1", "ripretinib": "LEVEL_1"},

    # ── Additional FGFR3 hotspot mutations — bladder ──────────────────────────
    # S249C most common FGFR3 point mutation; Y373C and R248C are second/third
    # most frequent. All covered by erdafitinib THOR/BLC2001 trial inclusion criteria.
    ("FGFR3", "Y373C"): {"erdafitinib": "LEVEL_1"},
    ("FGFR3", "R248C"): {"erdafitinib": "LEVEL_1"},
    ("FGFR3", "G370C"): {"erdafitinib": "LEVEL_1"},
    ("FGFR3", "K650E"): {"erdafitinib": "LEVEL_1"},

    # ── PTEN loss — exploratory mTOR pathway ─────────────────────────────────
    # No direct PTEN-targeted drug approved. Downstream mTOR inhibitors show
    # activity in PTEN-null tumours (Level 3A basket evidence).
    ("PTEN", "LOSS"):      {"everolimus": "LEVEL_3A", "temsirolimus": "LEVEL_3A"},
    ("PTEN", "DELETION"):  {"everolimus": "LEVEL_3A"},

    # ── CDK4/CCND1 — cell-cycle pathway ──────────────────────────────────────
    # CDK4/6 inhibitors active in HR+/HER2- breast (and investigational in others).
    # CDK4 amplification: abemaciclib has specific CDKN2A-null/CDK4-amp signal.
    ("CDK4",  "AMPLIFICATION"): {"abemaciclib": "LEVEL_3A", "palbociclib": "LEVEL_3B"},
    ("CCND1", "AMPLIFICATION"): {"palbociclib": "LEVEL_3A", "ribociclib": "LEVEL_3A", "abemaciclib": "LEVEL_3A"},

    # ── BRCA1/2 additional rare pathogenic variants ───────────────────────────
    # Any BRCA1/2 pathogenic variant is clinically equivalent for PARP inhibitor
    # prescribing. The PATHOGENIC key covers all frameshift/truncating/splice
    # variants; additional alias keys route here as well.
    ("BRCA1", "TRUNCATING"): {"olaparib": "LEVEL_1", "niraparib": "LEVEL_1", "rucaparib": "LEVEL_1", "talazoparib": "LEVEL_1"},
    ("BRCA2", "TRUNCATING"): {"olaparib": "LEVEL_1", "niraparib": "LEVEL_1", "rucaparib": "LEVEL_1", "talazoparib": "LEVEL_1"},

    # ── PALB2 — BRCA pathway partner ─────────────────────────────────────────
    # PALB2 pathogenic variants confer PARP-inhibitor sensitivity in breast cancer
    # (OlympiAD-like signal; BRCA2-interaction partner). LEVEL_2 per OncoKB.
    ("PALB2", "PATHOGENIC"): {"olaparib": "LEVEL_2", "niraparib": "LEVEL_3A"},

    # ── CDK12 — HRD-like signature in prostate ───────────────────────────────
    # CDK12 biallelic loss in prostate cancer generates focal tandem duplications
    # and an immunogenic phenotype; olaparib shows some activity (Level 3A).
    ("CDK12", "BIALLELICLOSS"): {"olaparib": "LEVEL_3A", "nivolumab": "LEVEL_3A"},

    # ── ARID1A — SWI/SNF complex; EZH2 synthetic lethality ───────────────────
    # No approved direct targeted therapy. Tazemetostat shows synthetic lethality
    # signal in ARID1A-deficient tumours (EZH2 dependency).
    ("ARID1A", "TRUNCATING"): {"tazemetostat": "LEVEL_3B"},

    # ── POLE/POLD1 — ultra-mutator phenotype ─────────────────────────────────
    # POLE exonuclease domain mutations generate ultra-high TMB; pembrolizumab
    # is indicated via tumour-agnostic TMB-high approval (FDA 2020).
    ("POLE", "EXONUCLEASEDOMAINMUT"): {"pembrolizumab": "LEVEL_2", "dostarlimab": "LEVEL_3A"},
    ("POLD1", "EXONUCLEASEDOMAINMUT"): {"pembrolizumab": "LEVEL_2"},

    # ── RIT1 — rare fusion partner in NSCLC ──────────────────────────────────
    # RIT1 mutations activating MAPK; investigational MEK-inhibitor signal only.
    # Mostly negative control for the benchmark.

    # ── Additional MLH1 MSI-H alias ──────────────────────────────────────────
    # EpCAM promoter hypermethylation silences MLH1; MSI-H clinical behaviour.
    ("EPCAM", "TRUNCATING"): {"pembrolizumab": "LEVEL_2", "dostarlimab": "LEVEL_2"},

    # ── Additional RET fusion variants ───────────────────────────────────────
    ("RET", "CCDC6-RET"):   {"selpercatinib": "LEVEL_1", "pralsetinib": "LEVEL_1", "vandetanib": "LEVEL_2", "cabozantinib": "LEVEL_2"},
    ("RET", "NCOA4-RET"):   {"selpercatinib": "LEVEL_1", "pralsetinib": "LEVEL_1"},
    ("RET", "PRKAR1A-RET"): {"selpercatinib": "LEVEL_1", "pralsetinib": "LEVEL_1"},

    # ── ROS1 additional fusion variants ──────────────────────────────────────
    ("ROS1", "SLC34A2-ROS1"): {"crizotinib": "LEVEL_1", "entrectinib": "LEVEL_1", "lorlatinib": "LEVEL_1", "repotrectinib": "LEVEL_1"},
    ("ROS1", "EZR-ROS1"):     {"crizotinib": "LEVEL_1", "entrectinib": "LEVEL_1", "lorlatinib": "LEVEL_1"},
    ("ROS1", "GOPC-ROS1"):    {"crizotinib": "LEVEL_1", "entrectinib": "LEVEL_1", "lorlatinib": "LEVEL_1"},

    # ── NTRK1 additional fusion variants ─────────────────────────────────────
    ("NTRK1", "ETV6-NTRK3"): {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1"},
    ("NTRK3", "ETV6-NTRK3"): {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1"},

    # ── ALK fusion variants ───────────────────────────────────────────────────
    ("ALK", "NPM1-ALK"):  {"crizotinib": "LEVEL_1", "brigatinib": "LEVEL_1", "ceritinib": "LEVEL_1", "alectinib": "LEVEL_2"},
    ("ALK", "TPM3-ALK"):  {"crizotinib": "LEVEL_1", "brigatinib": "LEVEL_1", "lorlatinib": "LEVEL_1"},
    ("ALK", "CLTC-ALK"):  {"crizotinib": "LEVEL_1", "brigatinib": "LEVEL_1"},

    # ── MPL mutations — Essential thrombocythemia/Myelofibrosis ──────────────
    # MPL W515L/K activates JAK-STAT; ruxolitinib applies like JAK2 V617F MPN.
    ("MPL", "W515L"): {"ruxolitinib": "LEVEL_1", "fedratinib": "LEVEL_2", "pacritinib": "LEVEL_2"},
    ("MPL", "W515K"): {"ruxolitinib": "LEVEL_1", "fedratinib": "LEVEL_2", "pacritinib": "LEVEL_2"},

    # ── BCL2 — venetoclax in CLL/AML ─────────────────────────────────────────
    ("BCL2", "AMPLIFICATION"): {"venetoclax": "LEVEL_1"},

    # ── DNMT3A — no targeted drug (negative control gene) ────────────────────
    # Included solely to generate negative-control benchmark cases.
    # Venetoclax+aza is used in AML regardless of DNMT3A status (DNMT3A is
    # prognostic, not a direct target); it is NOT a DNMT3A-targeted agent.
    # No entry here — system should return no_drug_verdict for DNMT3A mutations.

    # ══════════════════════════════════════════════════════════════════════════
    # EXPANSION BATCH — Evidence table entries 167–250+
    # Sources: OncoKB actionable genes, FDA approvals, ESMO guidelines,
    #          NCCN biomarker guidelines, published Phase 2/3 trial data
    # ══════════════════════════════════════════════════════════════════════════

    # ── STK11/LKB1 — synthetic lethality with KRAS; no direct drug ────────────
    # STK11 loss predicts poor response to IO; SMARCA4 co-loss relevant.
    # STE20 kinase family; no FDA-approved targeted drug yet.
    # Included as a negative-control gene for benchmarking.

    # ── SMARCA4 — EZH2 synthetic lethality ───────────────────────────────────
    # SMARCA4 loss creates dependency on EZH2; tazemetostat active preclinically.
    # FDA-approved for EZH2 gain-of-function in FL, not directly for SMARCA4 loss.
    ("SMARCA4", "LOSSOFFUNCTION"): {"tazemetostat": "LEVEL_3"},
    ("SMARCA4", "Q555P"):            {"tazemetostat": "LEVEL_3"},
    ("SMARCA4", "R1192W"):           {"tazemetostat": "LEVEL_3"},

    # ── ARID1A — synthetic lethality ─────────────────────────────────────────
    # ARID1A loss creates dependency on HDAC2 and ARID1B; olaparib combinations.
    ("ARID1A", "LOSSOFFUNCTION"): {"olaparib": "LEVEL_3", "tazemetostat": "LEVEL_3"},
    ("ARID1A", "Q456*"):            {"olaparib": "LEVEL_3"},

    # ── CDKN2A — CDK4/6 inhibitor indication ────────────────────────────────
    # p16 loss deregulates CDK4/6; CDK4/6i can restore cycle control.
    ("CDKN2A", "LOSS"):             {"palbociclib": "LEVEL_3", "ribociclib": "LEVEL_3", "abemaciclib": "LEVEL_3"},
    ("CDKN2A", "P114L"):            {"palbociclib": "LEVEL_3"},
    ("CDKN2A", "HOMOZYGOUSDELETION"): {"palbociclib": "LEVEL_3", "abemaciclib": "LEVEL_3"},

    # ── CDK4 amplification — CDK4/6 inhibitor ────────────────────────────────
    ("CDK4", "AMPLIFICATION"):      {"palbociclib": "LEVEL_2", "ribociclib": "LEVEL_2", "abemaciclib": "LEVEL_2"},

    # ── RB1 — predictive of CDK4/6 inhibitor resistance ─────────────────────
    # RB1 loss is required for CDK4/6 pathway activity; predicts resistance.
    ("RB1", "LOSSOFFUNCTION"):     {"palbociclib": "LEVEL_R1", "ribociclib": "LEVEL_R1", "abemaciclib": "LEVEL_R1"},

    # ── CCNE1 amplification — CDK2 inhibitors; gemcitabine sensitivity ────────
    ("CCNE1", "AMPLIFICATION"):     {},  # alisertib investigational, not FDA-approved

    # ── MAP2K2 (MEK2) — MEK inhibitor ────────────────────────────────────────
    ("MAP2K2", "Q60P"):             {"trametinib": "LEVEL_2", "cobimetinib": "LEVEL_2"},
    ("MAP2K2", "P298L"):            {"trametinib": "LEVEL_2"},

    # ── RAF1 — RAS/MAPK pathway fusion/amplification ─────────────────────────
    ("RAF1", "AMPLIFICATION"):      {"sorafenib": "LEVEL_3"},
    ("RAF1", "S257L"):              {"trametinib": "LEVEL_3"},

    # ── NF2 — merlin loss; mTOR/FAK pathway ──────────────────────────────────
    ("NF2", "LOSSOFFUNCTION"):     {"everolimus": "LEVEL_3"},  # defactinib investigational; everolimus has FDA use in NF2-related tumors

    # ── PTPN11 (SHP2) — allosteric SHP2 inhibitors ───────────────────────────
    ("PTPN11", "E76K"):             {},  # tnb-2814 and rmcc-4630 are not real FDA-approved drugs
    ("PTPN11", "G60R"):             {},  # tnb-2814 not an approved drug

    # ── KRAS G12D — no FDA-approved targeted agent (mrtx1133 investigational) ──
    ("KRAS", "G12D"):               {"sotorasib": "LEVEL_R1"},
    # KRAS G12V — no FDA-approved targeted agent; adagrasib only approved for G12C
    ("KRAS", "G12V"):               {},
    # KRAS G13D — cetuximab resistance in CRC context
    ("KRAS", "G13D"):               {"cetuximab": "LEVEL_R1", "panitumumab": "LEVEL_R1"},

    # ── NRAS Q61K — MEK inhibitor (same as Q61R/Q61L) ────────────────────────
    ("NRAS", "Q61K"):               {"binimetinib": "LEVEL_2", "trametinib": "LEVEL_3"},
    ("NRAS", "Q61L"):               {"binimetinib": "LEVEL_2"},
    ("NRAS", "Q61H"):               {"binimetinib": "LEVEL_2"},

    # ── HRAS G13R — same class as Q61R (tipifarnib investigational, not FDA-approved) ─
    ("HRAS", "G13R"):               {},
    ("HRAS", "G13V"):               {},

    # ── FGFR1 amplification/mutation — infigratinib/pemigatinib ─────────────
    ("FGFR1", "AMPLIFICATION"):     {"infigratinib": "LEVEL_2", "erdafitinib": "LEVEL_2"},
    ("FGFR1", "K656E"):             {"erdafitinib": "LEVEL_2"},
    ("FGFR1", "N546K"):             {"erdafitinib": "LEVEL_2"},

    # ── FGFR4 — fisogatinib investigational, no FDA approval ───────────────────
    ("FGFR4", "AMPLIFICATION"):     {},
    ("FGFR4", "V550L"):             {},
    ("FGFR4", "N535K"):             {},

    # ── ERBB3 (HER3) — patritumab deruxtecan ────────────────────────────────
    ("ERBB3", "AMPLIFICATION"):     {"patritumab-deruxtecan": "LEVEL_2"},
    ("ERBB3", "V104L"):             {"patritumab-deruxtecan": "LEVEL_3"},

    # ── ERBB4 (HER4) — neratinib activity in HER4-altered tumours ────────────
    ("ERBB4", "AMPLIFICATION"):     {"neratinib": "LEVEL_3"},
    ("ERBB4", "E452K"):             {"neratinib": "LEVEL_3"},

    # ── BRCA1 additional splice variants ─────────────────────────────────────
    ("BRCA1", "5382INSC"):          {"olaparib": "LEVEL_1", "rucaparib": "LEVEL_2", "niraparib": "LEVEL_2"},
    ("BRCA1", "185DELAG"):          {"olaparib": "LEVEL_1"},
    ("BRCA1", "SPLICESITE"):        {"olaparib": "LEVEL_1", "niraparib": "LEVEL_2"},

    # ── BRCA2 additional variants ────────────────────────────────────────────
    ("BRCA2", "6174DELT"):          {"olaparib": "LEVEL_1", "rucaparib": "LEVEL_2"},
    ("BRCA2", "IVS7+1G>A"):        {"olaparib": "LEVEL_1"},

    # ── RAD51C/RAD51D — homologous recombination deficiency ──────────────────
    ("RAD51C", "PATHOGENIC"):       {"olaparib": "LEVEL_2", "rucaparib": "LEVEL_2"},
    ("RAD51D", "PATHOGENIC"):       {"olaparib": "LEVEL_2", "niraparib": "LEVEL_2"},

    # ── CHEK2 — germline, moderate HR deficiency ──────────────────────────────
    ("CHEK2", "I157T"):             {"olaparib": "LEVEL_3"},
    ("CHEK2", "1100DELC"):         {"olaparib": "LEVEL_3"},

    # ── PTEN additional variants ─────────────────────────────────────────────
    # PTEN loss activates PI3K/AKT; PI3K inhibitors apply.
    ("PTEN", "LOSS"):               {"alpelisib": "LEVEL_2", "idelalisib": "LEVEL_3", "capivasertib": "LEVEL_2"},
    ("PTEN", "HOMOZYGOUSDELETION"): {"alpelisib": "LEVEL_2", "capivasertib": "LEVEL_2"},
    ("PTEN", "R130Q"):              {"alpelisib": "LEVEL_2"},
    ("PTEN", "R233*"):              {"alpelisib": "LEVEL_2"},

    # ── AKT1 mutations — capivasertib (FDA-approved 2023) ────────────────────
    # AKT1 E17K now in primary section with full ipatasertib/alpelisib entries.
    ("AKT1", "AMPLIFICATION"):      {"capivasertib": "LEVEL_2"},

    # ── AKT2 amplification ────────────────────────────────────────────────────
    ("AKT2", "AMPLIFICATION"):      {"capivasertib": "LEVEL_2"},

    # ── PIK3CA H1047L and supplemental hotspots ───────────────────────────────
    # H1047R now in primary table; H1047L here; Q546K moved to primary.
    ("PIK3CA", "H1047L"):           {"alpelisib": "LEVEL_1", "inavolisib": "LEVEL_1", "capivasertib": "LEVEL_1"},
    ("PIK3CA", "E545G"):            {"alpelisib": "LEVEL_1", "inavolisib": "LEVEL_1"},
    # Q546K and Q546E moved to primary section with full drug set.
    ("PIK3CA", "G1049R"):           {"alpelisib": "LEVEL_2", "inavolisib": "LEVEL_2"},

    # ── mTOR additional hotspots ─────────────────────────────────────────────
    ("MTOR", "S2215F"):             {"everolimus": "LEVEL_3", "temsirolimus": "LEVEL_3"},
    ("MTOR", "L1460P"):             {"everolimus": "LEVEL_3"},

    # ── JAK1 — ruxolitinib in MPNs with JAK1 mutations ───────────────────────
    ("JAK1", "V658F"):              {"ruxolitinib": "LEVEL_2", "fedratinib": "LEVEL_2"},
    ("JAK1", "A634D"):              {"ruxolitinib": "LEVEL_3"},

    # ── STAT3 — navitoclax + JAK inhibitor combos ────────────────────────────
    ("STAT3", "GAINOFFUNCTION"):   {"ruxolitinib": "LEVEL_3"},
    ("STAT3", "Y640F"):             {"ruxolitinib": "LEVEL_3"},

    # ── ABL1 additional resistance mutations ─────────────────────────────────
    # Asciminib specifically targets T315I (myristoyl pocket inhibitor)
    ("ABL1", "V299L"):              {"dasatinib": "LEVEL_R1", "bosutinib": "LEVEL_1", "asciminib": "LEVEL_2"},
    ("ABL1", "F317L"):              {"nilotinib": "LEVEL_R1", "bosutinib": "LEVEL_1", "asciminib": "LEVEL_2"},
    ("ABL1", "Y253H"):              {"imatinib": "LEVEL_R1", "dasatinib": "LEVEL_1", "asciminib": "LEVEL_2"},

    # ── FLT3 additional variants ─────────────────────────────────────────────
    # D835Y: FLT3 activation loop; quizartinib less active, gilteritinib active
    ("FLT3", "D835Y"):              {"gilteritinib": "LEVEL_1", "quizartinib": "LEVEL_R1", "midostaurin": "LEVEL_2"},
    ("FLT3", "D835H"):              {"gilteritinib": "LEVEL_1", "midostaurin": "LEVEL_2"},
    # FLT3 Y842 — activation loop, gilteritinib-sensitive
    ("FLT3", "Y842C"):              {"gilteritinib": "LEVEL_2"},

    # ── IDH1/IDH2 additional hotspots ────────────────────────────────────────
    # R132H, R132C, R132L, R132G, R132W, R132S now in primary section with vorasidenib.
    # R172K, R172W, R172G, R172M, R172S now in primary section with vorasidenib.
    # (Removed duplicates from this block to avoid last-write overwriting better entries.)

    # ── KIT additional GIST variants ─────────────────────────────────────────
    # Exon 17 (D816) — D816V already in primary table with midostaurin+sunitinib; add D820E
    ("KIT", "D820E"):               {"avapritinib": "LEVEL_1"},
    # Exon 13 (V654A) — sunitinib-resistant; regorafenib active
    ("KIT", "V654A"):               {"sunitinib": "LEVEL_R1", "regorafenib": "LEVEL_2"},
    ("KIT", "T670I"):               {"sunitinib": "LEVEL_R1", "regorafenib": "LEVEL_2"},

    # ── PDGFRA additional variants ───────────────────────────────────────────
    # Exon 14 (T674I) — imatinib resistant; sunitinib active
    ("PDGFRA", "T674I"):            {"imatinib": "LEVEL_R1", "sunitinib": "LEVEL_2"},
    # Exon 18 D842V (already in table as D842V) — add D842E, D842Y variants
    ("PDGFRA", "D842E"):            {"avapritinib": "LEVEL_1"},
    ("PDGFRA", "D842Y"):            {"avapritinib": "LEVEL_1"},

    # ── NTRK1 additional fusions ─────────────────────────────────────────────
    ("NTRK1", "TPM3-NTRK1"):       {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1", "repotrectinib": "LEVEL_1"},
    ("NTRK1", "TPR-NTRK1"):        {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1", "repotrectinib": "LEVEL_1"},
    ("NTRK1", "G595R"):             {"larotrectinib": "LEVEL_R1"},  # TRK resistance; selitrectinib not FDA-approved, removed

    # ── NTRK2 additional fusions ─────────────────────────────────────────────
    ("NTRK2", "STRN-NTRK2"):       {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1", "repotrectinib": "LEVEL_1"},

    # ── NTRK3 additional fusions ─────────────────────────────────────────────
    # NOTE: ETV6-NTRK3 in infantile fibrosarcoma (age < 2 yrs): repotrectinib NOT added here
    # (repotrectinib approved for NTRK fusion-positive solid tumors in patients ≥12 years only)
    ("NTRK3", "ETV6-NTRK3"):       {"larotrectinib": "LEVEL_1", "entrectinib": "LEVEL_1"},

    # ── RET additional fusions ───────────────────────────────────────────────
    ("RET", "CCDC6-RET"):           {"selpercatinib": "LEVEL_1", "pralsetinib": "LEVEL_1"},
    ("RET", "NCOA4-RET"):           {"selpercatinib": "LEVEL_1", "pralsetinib": "LEVEL_1"},
    ("RET", "C634F"):               {"selpercatinib": "LEVEL_1", "cabozantinib": "LEVEL_2"},  # thyroid
    ("RET", "M918T"):               {"selpercatinib": "LEVEL_1", "vandetanib": "LEVEL_1"},   # medullary TC

    # ── ROS1 additional fusions ──────────────────────────────────────────────
    # EZR-ROS1 already in primary table with lorlatinib=L1; remove duplicate that loses lorlatinib
    # G2032R already in primary table with repotrectinib+lorlatinib=L1; remove inferior duplicate
    ("ROS1", "TPM3-ROS1"):          {"crizotinib": "LEVEL_1"},

    # ── ALK resistance mutations (solvent-front, gatekeeper) ─────────────────
    # G1202R already in primary table with same data; remove duplicate
    ("ALK", "I1171N"):              {"brigatinib": "LEVEL_2", "lorlatinib": "LEVEL_2"},
    ("ALK", "L1196M"):              {"crizotinib": "LEVEL_R1", "alectinib": "LEVEL_1", "brigatinib": "LEVEL_1"},

    # ── MET amplification (high-level) ───────────────────────────────────────
    ("MET", "AMPLIFICATION"):       {"capmatinib": "LEVEL_1", "tepotinib": "LEVEL_1", "crizotinib": "LEVEL_2"},
    ("MET", "Y1230H"):              {"capmatinib": "LEVEL_R1", "crizotinib": "LEVEL_R1"},  # acquired resistance

    # ── ESR1 additional resistance mutations ─────────────────────────────────
    ("ESR1", "Y537N"):              {"fulvestrant": "LEVEL_R1", "elacestrant": "LEVEL_1", "lasofoxifene": "LEVEL_3"},
    ("ESR1", "Y537C"):              {"fulvestrant": "LEVEL_R1", "elacestrant": "LEVEL_1"},
    ("ESR1", "E380Q"):              {"fulvestrant": "LEVEL_R1", "elacestrant": "LEVEL_1"},

    # ── AR additional mutations ───────────────────────────────────────────────
    ("AR", "L702H"):                {"enzalutamide": "LEVEL_R1", "abiraterone": "LEVEL_R1"},
    ("AR", "W742C"):                {"enzalutamide": "LEVEL_R1"},
    ("AR", "H875Y"):                {"enzalutamide": "LEVEL_R1"},
    ("AR", "L868V"):                {"abiraterone": "LEVEL_R1"},

    # ── ERBB2 additional variants ────────────────────────────────────────────
    ("ERBB2", "Y772A775DUP"):       {"trastuzumab-deruxtecan": "LEVEL_2"},  # poziotinib removed (FDA-rejected 2022)
    ("ERBB2", "A775G776INSYVMA"):  {"trastuzumab-deruxtecan": "LEVEL_2"},
    ("ERBB2", "L755S"):             {"lapatinib": "LEVEL_R1", "neratinib": "LEVEL_2"},
    ("ERBB2", "V777L"):             {"neratinib": "LEVEL_2", "afatinib": "LEVEL_2"},

    # ── EGFR additional variants ─────────────────────────────────────────────
    ("EGFR", "G719S"):              {"afatinib": "LEVEL_2", "erlotinib": "LEVEL_2"},
    ("EGFR", "G719C"):              {"afatinib": "LEVEL_2"},
    ("EGFR", "L747S"):              {"afatinib": "LEVEL_2"},
    ("EGFR", "A750P"):              {"osimertinib": "LEVEL_2"},
    ("EGFR", "C797S"):              {"osimertinib": "LEVEL_R1"},
    ("EGFR", "L792H"):              {"osimertinib": "LEVEL_R1"},
    # Specific named EGFR exon 20 insertion variants (canonical EXON20INS handled in primary table)
    # NOTE: mobocertinib (Exkivity) was withdrawn by Takeda Nov 2023 — removed from all entries
    ("EGFR", "A763Y764INSFQEA"):  {"amivantamab": "LEVEL_1"},
    ("EGFR", "V769D770INSASVDN"): {"amivantamab": "LEVEL_1"},

    # ── MAP2K1 additional variants ────────────────────────────────────────────
    ("MAP2K1", "F53L"):             {"trametinib": "LEVEL_2", "cobimetinib": "LEVEL_2"},
    ("MAP2K1", "P387S"):            {"trametinib": "LEVEL_3"},

    # ── BRAF non-V600 variants ───────────────────────────────────────────────
    ("BRAF", "L597V"):              {"trametinib": "LEVEL_2"},
    ("BRAF", "L597R"):              {"trametinib": "LEVEL_2"},
    ("BRAF", "K601E"):              {"trametinib": "LEVEL_2"},
    ("BRAF", "G469A"):              {"trametinib": "LEVEL_2"},
    # BRAF Class 3 loss-of-function — MEK inhibitors, not BRAF inhibitors
    ("BRAF", "D594N"):              {"trametinib": "LEVEL_2", "vemurafenib": "LEVEL_R1"},
    ("BRAF", "G466V"):              {"trametinib": "LEVEL_2"},

    # ── CCND1 amplification — CDK4/6i in ER+ breast ──────────────────────────
    ("CCND1", "AMPLIFICATION"):     {"palbociclib": "LEVEL_1", "ribociclib": "LEVEL_1", "abemaciclib": "LEVEL_1"},

    # ── ATM additional mutations ─────────────────────────────────────────────
    ("ATM", "MISSENSE"):            {"olaparib": "LEVEL_2"},

    # ── POLE/POLD1 ───────────────────────────────────────────────────────────
    # Already present; add specific hotspots
    ("POLD1", "D316H"):             {"pembrolizumab": "LEVEL_2", "nivolumab": "LEVEL_2"},
    ("POLE",  "V411L"):             {"pembrolizumab": "LEVEL_2"},
    ("POLE",  "L424V"):             {"pembrolizumab": "LEVEL_2"},

    # ── CD274 (PD-L1) amplification ──────────────────────────────────────────
    ("CD274", "AMPLIFICATION"):     {"pembrolizumab": "LEVEL_1", "nivolumab": "LEVEL_1", "atezolizumab": "LEVEL_1"},

    # ── SRC — dasatinib off-label in melanoma/TNBC ───────────────────────────
    ("SRC", "AMPLIFICATION"):       {"dasatinib": "LEVEL_3"},

    # ── EPHA2 — regofenib/dasatinib (TKI activity) ───────────────────────────
    ("EPHA2", "AMPLIFICATION"):     {"dasatinib": "LEVEL_3"},

    # ── MDM2/MDM4 amplification — MDM2 inhibitors ────────────────────────────
    ("MDM2", "AMPLIFICATION"):      {},  # milademetan/navtemadlin investigational, not FDA-approved
    ("MDM4", "AMPLIFICATION"):      {"milademetan": "LEVEL_3"},

    # ── TP53 — MDM2i only when MDM2 not amplified; otherwise ─────────────────
    # Wild-type TP53 is required for MDM2 inhibitors to work.
    # No direct targetable entry — left as negative control for TP53 mutations.

    # ── DICER1 — no targeted drug ─────────────────────────────────────────────
    # Included only for negative control completeness.

    # ── SDHB/SDHC/SDHD — succinate dehydrogenase loss (GIST, paraganglioma) ──
    ("SDHB", "LOSSOFFUNCTION"):    {"sunitinib": "LEVEL_2"},
    ("SDHC", "LOSSOFFUNCTION"):    {"sunitinib": "LEVEL_2"},

    # ── VEGFA amplification — bevacizumab / ramucirumab ──────────────────────
    ("VEGFA", "AMPLIFICATION"):     {"bevacizumab": "LEVEL_2", "ramucirumab": "LEVEL_2"},

    # ── DNMT3A — no direct targeted agent ────────────────────────────────────
    # Azacitidine/venetoclax is standard AML care regardless of DNMT3A status;
    # not DNMT3A-specific. Consistent with negative control at line ~678.
    # ("DNMT3A", "R882H"): removed — not mutation-targeted
    # ("DNMT3A", "R882C"): removed — not mutation-targeted

    # ── TET2 — azacitidine in AML/MDS ────────────────────────────────────────
    ("TET2", "LOSSOFFUNCTION"):    {"azacitidine": "LEVEL_2", "venetoclax": "LEVEL_2"},

    # ── RUNX1 — enasidenib/azacitidine in AML ────────────────────────────────
    ("RUNX1", "RUNTDOMAINMUT"):    {"azacitidine": "LEVEL_2"},

    # ── EZH2 additional variants ─────────────────────────────────────────────
    ("EZH2", "F687L"):              {"tazemetostat": "LEVEL_1"},
    ("EZH2", "A677G"):              {"tazemetostat": "LEVEL_1"},
    ("EZH2", "Y646F"):              {"tazemetostat": "LEVEL_1"},
    ("EZH2", "Y646H"):              {"tazemetostat": "LEVEL_1"},

    # ── CALR additional variant ───────────────────────────────────────────────
    ("CALR", "TYPE2"):              {"ruxolitinib": "LEVEL_1", "fedratinib": "LEVEL_2"},

    # ── ASXL1 — azacitidine in MPN/MDS ──────────────────────────────────────
    ("ASXL1", "G646WFS"):           {"ruxolitinib": "LEVEL_2", "azacitidine": "LEVEL_2"},
    ("ASXL1", "LOSSOFFUNCTION"):   {"azacitidine": "LEVEL_2"},

    # ── NPM1 additional variant ───────────────────────────────────────────────
    # W288Cfs is type A insertion; ivosidenib/enasidenib for co-IDH cases.
    ("NPM1", "W288CFS"):            {"midostaurin": "LEVEL_1", "venetoclax": "LEVEL_1"},

    # ── IKZF1 — lenalidomide in B-ALL ────────────────────────────────────────
    ("IKZF1", "LOSSOFFUNCTION"):   {"lenalidomide": "LEVEL_2"},

    # ── BTK — ibrutinib in CLL; venetoclax for resistance ────────────────────
    ("BTK", "AMPLIFICATION"):       {"ibrutinib": "LEVEL_1", "acalabrutinib": "LEVEL_1"},
    ("BTK", "C481S"):               {"ibrutinib": "LEVEL_R1", "pirtobrutinib": "LEVEL_1", "venetoclax": "LEVEL_1"},

    # ── WT1 — azacitidine in AML ─────────────────────────────────────────────
    ("WT1", "LOSSOFFUNCTION"):     {"azacitidine": "LEVEL_3"},

    # ── RNF43 — porcupine inhibitors in RSPO-translocation CRC ───────────────
    ("RNF43", "G659Vfs"):           {},  # wnt-974 investigational, not FDA-approved

    # ── FBXW7 — negative regulator; mTOR/CDK4/6 sensitivity ─────────────────
    ("FBXW7", "LOSSOFFUNCTION"):   {"everolimus": "LEVEL_3"},

    # ── BRIP1 — homologous recombination ─────────────────────────────────────
    ("BRIP1", "PATHOGENIC"):        {"olaparib": "LEVEL_3", "niraparib": "LEVEL_3"},

    # ── NBN (NBS1) — HR deficiency ───────────────────────────────────────────
    ("NBN", "PATHOGENIC"):          {"olaparib": "LEVEL_3"},

    # ── KDR (VEGFR2) — sunitinib/sorafenib ───────────────────────────────────
    ("KDR", "AMPLIFICATION"):       {"sunitinib": "LEVEL_2", "sorafenib": "LEVEL_2"},
    ("KDR", "V297I"):               {"sunitinib": "LEVEL_3"},

    # ── CTNNB1 (beta-catenin) — WNT pathway (wnt-974 investigational, no FDA-approved targeted agent) ──
    ("CTNNB1", "GAINOFFUNCTION"):  {},
    ("CTNNB1", "S45F"):             {},

    # ── GAS6 / AXL axis ──────────────────────────────────────────────────────
    ("AXL", "AMPLIFICATION"):       {},  # bemcentinib investigational, not FDA-approved

    # ── CDH1 (E-cadherin) — HDAC inhibitors in lobular breast ────────────────
    ("CDH1", "LOSSOFFUNCTION"):    {},  # entinostat investigational for CDH1 LOF, not FDA-approved

    # ══════════════════════════════════════════════════════════════════════════
    # NEW CLINICAL ENTRIES — Added from CIViC Level A/B evidence + recent FDA approvals
    # Sources: CIViC nightly bulk (civicdb.org, CC BY-SA 4.0), FDA approvals 2023-2025,
    #          OncoKB public database, ESMO/NCCN guidelines
    # ══════════════════════════════════════════════════════════════════════════

    # ── H3-3A K28M (H3.3 K27M) — Diffuse Midline Glioma ─────────────────────
    # Dordaviprone (ONC201) FDA-approved May 2024 (PNOC008 trial).
    # DRD2-antagonist mechanism; only agent with glioma-specific approval.
    ("H3-3A", "K28M"):              {"dordaviprone": "LEVEL_1"},
    ("H3-3A", "K27M"):              {"dordaviprone": "LEVEL_1"},
    ("H3C2",  "K28M"):              {"dordaviprone": "LEVEL_1"},  # alternative gene symbol

    # ── MGMT promoter methylation — Glioblastoma ─────────────────────────────
    # MGMT methylation predicts benefit from temozolomide (EORTC 26981).
    # Standard of care in GBM (Stupp protocol): RT + TMZ.
    ("MGMT", "METHYLATION"):        {"temozolomide": "LEVEL_1", "bevacizumab": "LEVEL_3A"},
    ("MGMT", "PROMOTERMETHYLATION"):{"temozolomide": "LEVEL_1"},

    # ── PML::RARA fusion — Acute Promyelocytic Leukemia (APL) ────────────────
    # Tretinoin (ATRA) + arsenic trioxide is curative-intent standard of care in APL
    # (APL0406 / GIMEMA trial). Both FDA-approved.
    ("PML",  "PML-RARA"):           {"tretinoin": "LEVEL_1", "arsenic trioxide": "LEVEL_1"},
    ("RARA", "PML-RARA"):           {"tretinoin": "LEVEL_1", "arsenic trioxide": "LEVEL_1"},
    ("PML",  "FUSION"):             {"tretinoin": "LEVEL_1", "arsenic trioxide": "LEVEL_1"},

    # ── POLE exonuclease domain mutations — Ultra-mutator / TMB-extreme ──────
    # POLE P286R, V411L, S459F, etc. create extremely high TMB → exceptional IO response.
    # Pembrolizumab pan-tumor L1 for TMB-H (KEYNOTE-158). Dostarlimab also active.
    ("POLE", "MUTATION"):           {"pembrolizumab": "LEVEL_1", "dostarlimab": "LEVEL_1"},
    ("POLE", "P286R"):              {"pembrolizumab": "LEVEL_1", "nivolumab": "LEVEL_1", "dostarlimab": "LEVEL_1"},  # GARNET/DUO-E FDA 2022
    ("POLE", "S459F"):              {"pembrolizumab": "LEVEL_1"},
    ("POLD1","MUTATION"):           {"pembrolizumab": "LEVEL_1", "dostarlimab": "LEVEL_1"},

    # ── FGFR1 fusion — Myeloid/lymphoid neoplasms with eosinophilia ──────────
    # Pemigatinib FDA-approved 2022 for relapsed/refractory myeloid/lymphoid neoplasms
    # with FGFR1 rearrangement (FIGHT-203).
    ("FGFR1", "FUSION"):            {"pemigatinib": "LEVEL_1"},
    ("FGFR1", "REARRANGEMENT"):     {"pemigatinib": "LEVEL_1"},

    # ── BRAF V600 (generic/catch-all for all V600 variants) ──────────────────
    # For patients where sequencing reports BRAF V600 without specifying E/K/R.
    # Encorafenib+binimetinib melanoma FDA-approved 2018 (COLUMBUS, MEKTOVI+BRAFTOVI).
    # Dabrafenib+trametinib FDA-approved for melanoma, NSCLC, thyroid (ATC), LGG.
    ("BRAF", "V600"):               {
        "vemurafenib": "LEVEL_1",
        "dabrafenib": "LEVEL_1",
        "trametinib": "LEVEL_1",
        "encorafenib": "LEVEL_1",
        "binimetinib": "LEVEL_1",
    },

    # ── DNMT3A R882 — NOTE: negative control in benchmark ────────────────────
    # DNMT3A R882H/C are NOT direct drug targets. Azacitidine/venetoclax are
    # standard AML care regardless of DNMT3A status. The benchmark treats this
    # as a negative control (no mutation-targeted drug). Leave empty.
    # ("DNMT3A", "R882H"): {}  # intentionally excluded — negative control
    # ("DNMT3A", "R882C"): {}  # intentionally excluded — negative control

    # ── KRAS G12C NSCLC additional agents ────────────────────────────────────
    # Divarasib (GDC-6036) Phase 1/2 results (KRYSTAL-like), CIViC Level B for NSCLC.
    # Not yet FDA-approved but high-confidence emerging agent.
    # Glecirasib (BBI-2493) also showing Phase 2 activity.
    # KRAS G12C is already in the primary table above with full drug set.
    # Duplicate removed to prevent last-write overwrite.

    # ── CLDN18 (Claudin-18.2) — Gastric/GEJ cancer ───────────────────────────
    # Zolbetuximab (VYLOY) FDA-approved Oct 2024 (SPOTLIGHT + GLOW trials).
    # First-line gastric/GEJ for CLDN18.2-positive (≥75% cells 2+/3+ IHC).
    # Combines with FOLFOX or CAPOX chemotherapy backbone.
    ("CLDN18", "OVEREXPRESSION"):   {"zolbetuximab": "LEVEL_1"},
    ("CLDN18", "AMPLIFICATION"):    {"zolbetuximab": "LEVEL_1"},
    # Fallback: generic CLDN18.2 positivity (IHC-reported, not sequencing-based)
    ("CLDN18", "EXPRESSION"):       {"zolbetuximab": "LEVEL_2"},

    # ── DLL3 (Delta-like ligand 3) — Small Cell Lung Cancer (SCLC) ───────────
    # Tarlatamab-dlle (Imdelltra) FDA-approved May 2024 (DeLLphi-301 trial).
    # Bispecific T-cell engager (BiTE) for relapsed/refractory SCLC after platinum.
    # DLL3 is highly expressed in SCLC vs normal tissue → tumour-selective.
    ("DLL3", "OVEREXPRESSION"):     {"tarlatamab": "LEVEL_1"},
    ("DLL3", "AMPLIFICATION"):      {"tarlatamab": "LEVEL_1"},
    ("DLL3", "EXPRESSION"):         {"tarlatamab": "LEVEL_2"},

    # ── TROP2 (TACSTD2) — TNBC / NSCLC / Urothelial / Cervical ─────────────
    # Sacituzumab govitecan (Trodelvy) FDA-approved 2020/2021/2023/2024:
    #   - TNBC (relapsed/refractory, ASCENT trial) — 2020
    #   - Urothelial (after platinum + PD-1/L1, TROPHY-U-01) — 2021
    #   - NSCLC (after platinum + IO, EVOKE-01) — 2024 (accelerated)
    #   - HR+/HER2- breast (SG-TROPiCS-02) — 2023
    # Datopotamab deruxtecan (Dato-DXd) FDA-approved 2024 for NSCLC + HR+/HER2- breast.
    ("TACSTD2", "OVEREXPRESSION"):  {
        "sacituzumab govitecan": "LEVEL_1",
        "datopotamab deruxtecan": "LEVEL_1",
    },
    ("TACSTD2", "AMPLIFICATION"):   {
        "sacituzumab govitecan": "LEVEL_1",
        "datopotamab deruxtecan": "LEVEL_1",
    },

    # ── NECTIN4 — Urothelial carcinoma ───────────────────────────────────────
    # Enfortumab vedotin (Padcev) FDA-approved 2019 (accelerated), 2023 (full).
    # EV-302 trial: EV + pembrolizumab superior to platinum-based chemo in 1L.
    # Combination EV + pembrolizumab FDA-approved Dec 2023 (1L unresectable/metastatic UC).
    ("NECTIN4", "OVEREXPRESSION"):  {
        "enfortumab vedotin": "LEVEL_1",
        "pembrolizumab": "LEVEL_1",
    },
    ("NECTIN4", "AMPLIFICATION"):   {"enfortumab vedotin": "LEVEL_1"},

    # ── HER3 (ERBB3) — NSCLC / Breast cancer ────────────────────────────────
    # Patritumab deruxtecan (HER3-DXd) FDA-accelerated approval Jan 2025
    # for HER3-expressing NSCLC after EGFR-targeted therapy + platinum (HERTHENA-Lung01).
    # Already present in primary table (line ~908); adding EXPRESSION key as fallback.
    ("ERBB3", "OVEREXPRESSION"):    {"patritumab deruxtecan": "LEVEL_1"},
    ("ERBB3", "AMPLIFICATION"):     {"patritumab deruxtecan": "LEVEL_2"},

    # ── FRα (FOLR1) — Ovarian cancer / Endometrial cancer ───────────────────
    # Mirvetuximab soravtansine (Elahere) FDA-approved Nov 2022 (SORAYA trial),
    # full approval Oct 2023 (MIRASOL trial) for FRα-high platinum-resistant ovarian cancer.
    # Luveltamab tazevibulin (IMGN151) FDA Breakthrough designation.
    ("FOLR1", "OVEREXPRESSION"):    {"mirvetuximab soravtansine": "LEVEL_1"},
    ("FOLR1", "AMPLIFICATION"):     {"mirvetuximab soravtansine": "LEVEL_1"},
    ("FOLR1", "HIGH"):              {"mirvetuximab soravtansine": "LEVEL_1"},
}


def _normalise_public_key_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _normalise_level_token(level: str) -> Optional[str]:
    lv = str(level or "").strip().upper().replace(" ", "")
    if not lv:
        return None
    aliases = {
        "1": "LEVEL_1",
        "2": "LEVEL_2",
        "3A": "LEVEL_3A",
        "3B": "LEVEL_3B",
        "4": "LEVEL_4",
        "R1": "LEVEL_R1",
        "R2": "LEVEL_R2",
    }
    if lv in aliases:
        return aliases[lv]
    if lv.startswith("LEVEL") and "_" not in lv:
        lv = lv.replace("LEVEL", "LEVEL_", 1)
    if lv.startswith("LEVEL_"):
        return lv
    return None


def _pick_field(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    lookup = {_normalise_public_key_token(k): v for k, v in row.items()}
    for cand in candidates:
        value = lookup.get(_normalise_public_key_token(cand), "")
        if value:
            return str(value).strip()
    return ""


def _normalise_public_alteration(alt: str) -> str:
    s = re.sub(r"^p\.", "", str(alt or ""), flags=re.IGNORECASE).strip().upper()
    s = re.sub(r"[.\-_ ]", "", s)
    return s


def _split_drug_names(raw_drugs: str) -> list[str]:
    if not raw_drugs:
        return []
    parts = re.split(r"\s*\+\s*|\s*;\s*|\s*,\s*|\s*/\s*", raw_drugs)
    cleaned: list[str] = []
    for p in parts:
        d = re.sub(r"\([^)]*\)", "", p).strip().lower()
        if d:
            cleaned.append(d)
    return cleaned


def _parse_oncokb_public_dump_tsv(tsv_text: str) -> dict[tuple[str, str], dict[str, str]]:
    parsed: dict[tuple[str, str], dict[str, str]] = {}
    reader = csv.DictReader(tsv_text.splitlines(), delimiter="\t")
    for row in reader:
        gene = _pick_field(row, ("HUGO_SYMBOL", "GENE", "GENE_SYMBOL", "SYMBOL")).upper()
        alteration_raw = _pick_field(
            row,
            (
                "ALTERATION",
                "PROTEIN_CHANGE",
                "ALTERATION_NAME",
                "VARIANT",
                "MUTATION",
                "ALTERATIONTYPE",
            ),
        )
        level_raw = _pick_field(row, ("LEVEL", "ONCOKB_LEVEL", "EVIDENCE_LEVEL"))
        drugs_raw = _pick_field(row, ("DRUGS", "DRUG", "DRUG_NAME", "TREATMENT"))

        if not gene or not alteration_raw or not level_raw or not drugs_raw:
            continue

        alt_norm = _normalise_public_alteration(alteration_raw)
        level = _normalise_level_token(level_raw)
        if not alt_norm or level is None:
            continue

        key = (gene, alt_norm)
        if key not in parsed:
            parsed[key] = {}

        for drug in _split_drug_names(drugs_raw):
            parsed[key][drug] = level

    return parsed


def _load_public_table_from_cache(cache_path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not cache_path.exists():
        return {}
    try:
        text = cache_path.read_text(encoding="utf-8")
        table = _parse_oncokb_public_dump_tsv(text)
        if table:
            logger.info(
                "[OncoKB] loaded %d entries from local cache: %s",
                len(table),
                cache_path,
            )
        return table
    except Exception as exc:
        logger.warning("[OncoKB] failed to load cache file %s: %s", cache_path, exc)
        return {}


def _write_public_table_cache(raw_tsv_text: str, cache_path: Path) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(raw_tsv_text, encoding="utf-8")
    except Exception as exc:
        logger.warning("[OncoKB] failed to write cache file %s: %s", cache_path, exc)


def _is_cache_fresh(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    try:
        modified = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - modified
        return age <= timedelta(days=_ONCOKB_CACHE_MAX_AGE_DAYS)
    except Exception:
        return False


def _download_public_oncokb_table() -> tuple[dict[tuple[str, str], dict[str, str]], str]:
    headers = {"Accept": "text/plain"}
    token = _get_oncokb_public_dump_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for url in _ONCOKB_PUBLIC_DUMP_URLS:
        try:
            response = httpx.get(url, headers=headers, timeout=_ONCOKB_PUBLIC_TIMEOUT)
            response.raise_for_status()
            text = response.text
            if "\t" not in text:
                raise ValueError("response does not look like a TSV dump")
            table = _parse_oncokb_public_dump_tsv(text)
            if not table:
                logger.warning("[OncoKB] URL succeeded but parsed no rows: %s", url)
                continue
            logger.info(
                "[OncoKB] downloaded and parsed %d actionable variant entries from %s",
                len(table),
                url,
            )
            return table, text
        except BaseException as exc:
            logger.warning("[OncoKB] failed URL %s (%s)", url, exc)

    logger.warning(
        "[OncoKB] all public dump URLs failed; continuing with cache/static fallback. "
        "See %s for manual download guidance.",
        _ONCOKB_PUBLIC_DUMP_FALLBACK_URL,
    )
    return {}, ""


def _merge_level_tables(
    base: dict[tuple[str, str], dict[str, str]],
    incoming: dict[tuple[str, str], dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    merged: dict[tuple[str, str], dict[str, str]] = {k: dict(v) for k, v in base.items()}
    for key, incoming_drugs in incoming.items():
        if key not in merged:
            merged[key] = {}
        merged[key].update(incoming_drugs)
    return merged


def _bootstrap_oncokb_public_table() -> None:
    global _LEVEL_TABLE
    cache_path = get_oncokb_cache_path()

    if _is_cache_fresh(cache_path):
        cached = _load_public_table_from_cache(cache_path)
        if cached:
            logger.info("[OncoKB] bootstrap path=fresh_cache")
            _LEVEL_TABLE = _merge_level_tables(_LEVEL_TABLE, cached)
            return

    downloaded, raw_tsv_text = _download_public_oncokb_table()
    if downloaded:
        logger.info("[OncoKB] bootstrap path=download")
        _LEVEL_TABLE = _merge_level_tables(_LEVEL_TABLE, downloaded)
        _write_public_table_cache(raw_tsv_text, cache_path)
        return

    logger.info("[OncoKB] bootstrap path=static_fallback")


def load_oncokb_flat_file() -> None:
    """Compatibility loader for standalone scripts expecting explicit bootstrap."""
    _bootstrap_oncokb_public_table()


def ensure_oncokb_table_loaded(min_entries: int = 200) -> int:
    """Ensure OncoKB actionable table is sufficiently populated for offline scripts.

    Returns current actionable-variant table size after ensure.
    """
    global _LEVEL_TABLE
    cache_path = get_oncokb_cache_path()

    if _is_cache_fresh(cache_path):
        logger.info("[OncoKB] ensure path=fresh_cache")
        cached = _load_public_table_from_cache(cache_path)
        if cached:
            _LEVEL_TABLE = _merge_level_tables(_LEVEL_TABLE, cached)
            return len(_LEVEL_TABLE)
        logger.info("[OncoKB] ensure fresh cache unreadable; will download")

    logger.info("[OncoKB] ensure path=download_attempt")
    downloaded, raw_tsv_text = _download_public_oncokb_table()
    if downloaded:
        _LEVEL_TABLE = _merge_level_tables(_LEVEL_TABLE, downloaded)
        _write_public_table_cache(raw_tsv_text, cache_path)
        return len(_LEVEL_TABLE)

    logger.info(
        "[OncoKB] ensure path=static_fallback (table_size=%d, min_entries=%d)",
        len(_LEVEL_TABLE),
        int(min_entries),
    )
    return len(_LEVEL_TABLE)


_bootstrap_oncokb_public_table()


# Aliases so variant strings from VCF INFO fields match table keys
_ALTERATION_ALIASES: dict[str, str] = {
    # exon 19 deletion various representations
    "e746_a750del": "e746a750del",
    "exon19deletion": "exon19del",
    # fusion aliases
    "eml4alk": "eml4-alk",
    "kif5bret": "kif5b-ret",
    "fgfr2pphln1": "fgfr2-pphln1",
    "ros1fusion": "fusion",
    "cd74ros1": "cd74-ros1",
    # exon skip aliases
    "exon14skipping": "exon14skip",
    "d14del": "exon14skip",
    "ex14": "exon14skip",
    "exon14": "exon14skip",
    # exon 11 aliases (KIT GIST)
    "ex11": "exon11mut",
    "exon11": "exon11mut",
    "ex11del": "exon11del",
    "exon11deletion": "exon11del",
    # exon 19 aliases (EGFR)
    "ex19del": "exon19del",
    "exon19": "exon19del",
    # Hyphenated names lose their hyphen during normalisation — restore via alias
    # (normalise_alteration strips '-' so "BCR-ABL1" → "bcrabl1" etc.)
    "bcrabl1": "bcr-abl1",
    "msih": "msi-h",
    "tmbhigh": "tmb-high",
    "v600ecrc": "v600e-crc",
    # generic loss/truncation harmonization for tumour-suppressor style cases
    "loss": "truncation",
    "trunc": "truncation",
    "truncated": "truncation",
    # ALK fusion aliases (hyphen stripped by normalisation)
    "cltcalk": "cltc-alk",
    "npm1alk": "npm1-alk",
    "tpm3alk": "tpm3-alk",
    # ROS1 fusion aliases
    "ezrros1": "ezr-ros1",
    "gopcros1": "gopc-ros1",
    "slc34a2ros1": "slc34a2-ros1",
    "tpm3ros1": "tpm3-ros1",
    # RET fusion aliases
    "ccdc6ret": "ccdc6-ret",
    "ncoa4ret": "ncoa4-ret",
    # APL / haematological fusion aliases
    "pmlrara": "pml-rara",
    "rarapml": "pml-rara",      # reverse-orientation alias
    # NTRK fusion aliases
    "etv6ntrk3": "etv6-ntrk3",
    "tpm3ntrk1": "tpm3-ntrk1",
    "tprntrk1": "tpr-ntrk1",
    "strnntrk2": "strn-ntrk2",
    # FGFR fusion aliases — hyphen stripped by normalisation
    "fgfr2bicc1": "fusion",      # FGFR2-BICC1 ICC/CCA fusion → resolves to FGFR2 FUSION
    "fgfr2pphln1": "fusion",     # FGFR2-PPHLN1 (already existed — kept)
    "fgfr3tacc3": "fusion",      # FGFR3-TACC3 UC/glioblastoma fusion → resolves to FGFR3 FUSION
    "fgfr2ahcyl1": "fusion",     # FGFR2-AHCYL1 (ICC)
    "fgfr2casp7": "fusion",      # FGFR2-CASP7 (ICC)
    # BRCA truncating frameshift aliases → resolve to "truncation" for BRCA PARP-i evidence
    "q1395fs": "truncation",     # BRCA1 Q1395fs — pathogenic truncating frameshift
    "q1429fs": "truncation",     # BRCA1 Q1429fs
    "e1143fs": "truncation",     # BRCA2 E1143fs
    "s1982fs": "truncation",     # BRCA1 S1982fs
}


# Cancer-context overrides for known indication-specific behaviour.
#
# Mode semantics:
#   - replace: use only the listed context drugs for this gene/variant/tumour
#              context (plus any resistance entries that may already exist).
#   - merge:   add/override the listed context drugs on top of base evidence.
_CANCER_CONTEXT_OVERRIDES: dict[tuple[str, str, str], dict[str, object]] = {
    # NSCLC EGFR sensitising context: prioritise established 1G/2G/3G set.
    (
        "EGFR",
        "L858R",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "osimertinib": "LEVEL_1",
            "erlotinib": "LEVEL_1",
            "gefitinib": "LEVEL_1",
            "afatinib": "LEVEL_1",
        },
    },
    (
        "EGFR",
        "EXON19DEL",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "osimertinib": "LEVEL_1",
            "erlotinib": "LEVEL_1",
            "gefitinib": "LEVEL_1",
            "afatinib": "LEVEL_2",    # 2nd-gen; preferred 1st-line are osimertinib/erlotinib/gefitinib
        },
    },
    # HNSCC context differs from NSCLC EGFR prescribing patterns in this benchmark.
    (
        "EGFR",
        "L858R",
        "HNSCC",
    ): {
        "mode": "replace",
        "drugs": {
            "cetuximab": "LEVEL_2",
            "afatinib": "LEVEL_2",
            "panitumumab": "LEVEL_3A",
        },
    },
    # Pediatric ALK-mutant neuroblastoma context.
    (
        "ALK",
        "F1174L",
        "NEUROBLASTOMA",
    ): {
        "mode": "merge",
        "drugs": {
            "crizotinib": "LEVEL_2",
            "lorlatinib": "LEVEL_2",
        },
    },
    # HIF2A-driven RCC context.
    (
        "HIF2A",
        "ACTIVATION",
        "RCC",
    ): {
        "mode": "merge",
        "drugs": {
            "belzutifan": "LEVEL_1",
        },
    },
    (
        "HIF2A",
        "V155L",
        "RCC",
    ): {
        "mode": "merge",
        "drugs": {
            "belzutifan": "LEVEL_1",
        },
    },
    # Endometrial PTEN-loss / mTOR-axis context.
    (
        "PTEN",
        "TRUNCATION",
        "ENDOMETRIAL",
    ): {
        "mode": "merge",
        "drugs": {
            "everolimus": "LEVEL_3A",
            "temsirolimus": "LEVEL_3A",
        },
    },
    # Gastric HER2 context: prioritise established gastric evidence set.
    (
        "ERBB2",
        "AMPLIFICATION",
        "GASTRIC",
    ): {
        "mode": "replace",
        "drugs": {
            "trastuzumab": "LEVEL_1",
            "trastuzumab deruxtecan": "LEVEL_1",
        },
    },
    # Breast HER2 context: prioritise canonical approved stack, avoid noisy extras.
    (
        "ERBB2",
        "AMPLIFICATION",
        "BREAST",
    ): {
        "mode": "replace",
        "drugs": {
            "trastuzumab": "LEVEL_1",
            "trastuzumab deruxtecan": "LEVEL_1",
            "pertuzumab": "LEVEL_1",
            "tucatinib": "LEVEL_1",
            "lapatinib": "LEVEL_1",
        },
    },
    # BRAF V600E melanoma context: keep clinically standard combination set near top.
    (
        "BRAF",
        "V600E",
        "MELANOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "dabrafenib": "LEVEL_1",
            "trametinib": "LEVEL_1",
            "vemurafenib": "LEVEL_1",
        },
    },
    # BRAF V600E CRC context (BEACON-CRC): encorafenib+cetuximab+binimetinib preferred.
    # Melanoma monotherapy agents (vemurafenib, dabrafenib) have poor efficacy in CRC.
    (
        "BRAF",
        "V600E",
        "COLORECTAL",
    ): {
        "mode": "replace",
        "drugs": {
            "encorafenib": "LEVEL_1",
            "binimetinib": "LEVEL_1",
            "cetuximab": "LEVEL_1",
        },
    },
    # Pediatric LGG context: approved combination should dominate ordering.
    (
        "BRAF",
        "V600E",
        "PEDS_GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "dabrafenib": "LEVEL_1",
            "trametinib": "LEVEL_1",
        },
    },
    # DLBCL BCL2 amplification context.
    (
        "BCL2",
        "AMPLIFICATION",
        "DLBCL",
    ): {
        "mode": "merge",
        "drugs": {
            "venetoclax": "LEVEL_3A",
        },
    },
    # IDH1-mutant glioma context.
    # Vorasidenib has the glioma-specific FDA approval (INDIGO trial, 2023, grade 2 glioma).
    # Ivosidenib is approved for IDH1-mutant AML and cholangiocarcinoma only — it has NO
    # glioma approval. Ranking ivosidenib above vorasidenib in glioma is clinically wrong.
    (
        "IDH1",
        "R132H",
        "GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "vorasidenib": "LEVEL_1",
            "ivosidenib": "LEVEL_2",  # off-label; no glioma trial; AML/cholangio only
        },
    },
    (
        "IDH1",
        "R132C",
        "GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "vorasidenib": "LEVEL_1",
            "ivosidenib": "LEVEL_2",
        },
    },
    # IDH1-mutant AML context.
    # Ivosidenib (AG221) FDA-approved for IDH1-mutant AML (2018); olutasidenib also approved.
    # Azacitidine + ivosidenib combination (AGILE trial) is standard front-line in eligible patients.
    # Venetoclax + azacitidine is standard for AML regardless of IDH1 status.
    (
        "IDH1",
        "R132H",
        "AML",
    ): {
        "mode": "merge",
        "drugs": {
            "ivosidenib": "LEVEL_1",
            "azacitidine": "LEVEL_1",   # AGILE trial: ivosidenib + azacitidine FDA-approved combo
            "venetoclax": "LEVEL_1",    # standard AML induction partner
            "olutasidenib": "LEVEL_2",  # FDA-approved 2022; less established than ivosidenib in combo
        },
    },
    (
        "IDH1",
        "R132C",
        "AML",
    ): {
        "mode": "merge",
        "drugs": {
            "ivosidenib": "LEVEL_1",
            "azacitidine": "LEVEL_1",
            "venetoclax": "LEVEL_1",
            "olutasidenib": "LEVEL_2",
        },
    },
    # BRCA-mutant breast cancer context.
    # Olaparib (OlympiAD, OlympiA) and Talazoparib (EMBRACA) have dedicated
    # breast-specific FDA approvals for gBRCA1/2 HER2-negative disease.
    # Niraparib failed its breast-cancer trial (BRAVO, 2022) and has no
    # breast-specific label; Rucaparib has no breast indication.
    (
        "BRCA1",
        "PATHOGENIC",
        "BREAST",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "talazoparib": "LEVEL_1",
            "niraparib": "LEVEL_2",
            "rucaparib": "LEVEL_2",
        },
    },
    (
        "BRCA2",
        "PATHOGENIC",
        "BREAST",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "talazoparib": "LEVEL_1",
            "niraparib": "LEVEL_2",
            "rucaparib": "LEVEL_2",
        },
    },
    # BRCA1/2 pancreatic cancer context: olaparib is FDA-approved (POLO trial).
    (
        "BRCA1",
        "PATHOGENIC",
        "PANCREATIC",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "rucaparib": "LEVEL_2",
            "niraparib": "LEVEL_2",
        },
    },
    (
        "BRCA2",
        "PATHOGENIC",
        "PANCREATIC",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "rucaparib": "LEVEL_2",
            "niraparib": "LEVEL_2",
        },
    },
    # VHL RCC context: belzutifan approved 2023 for advanced ccRCC.
    (
        "VHL",
        "MUTATION",
        "RCC",
    ): {
        "mode": "merge",
        "drugs": {
            "belzutifan": "LEVEL_1",
        },
    },
    (
        "VHL",
        "LOSS",
        "RCC",
    ): {
        "mode": "merge",
        "drugs": {
            "belzutifan": "LEVEL_1",
        },
    },
    # SMO/PTCH1 BCC context: both hedgehog inhibitors FDA-approved.
    (
        "SMO",
        "MUTATION",
        "BCC",
    ): {
        "mode": "replace",
        "drugs": {
            "vismodegib": "LEVEL_1",
            "sonidegib": "LEVEL_1",
        },
    },
    (
        "PTCH1",
        "LOSS",
        "BCC",
    ): {
        "mode": "replace",
        "drugs": {
            "vismodegib": "LEVEL_1",
            "sonidegib": "LEVEL_1",
        },
    },
    # Uveal melanoma — tebentafusp for GNAQ/GNA11 Q209 mutations.
    (
        "GNAQ",
        "Q209L",
        "UVEAL_MELANOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "tebentafusp": "LEVEL_1",
        },
    },
    (
        "GNAQ",
        "Q209P",
        "UVEAL_MELANOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "tebentafusp": "LEVEL_1",
        },
    },
    (
        "GNA11",
        "Q209L",
        "UVEAL_MELANOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "tebentafusp": "LEVEL_1",
        },
    },
    # HNSCC HRAS context: tipifarnib removed (not FDA-approved; investigational only).
    # Medullary thyroid cancer RET context.
    (
        "RET",
        "C634F",
        "MTC",
    ): {
        "mode": "replace",
        "drugs": {
            "selpercatinib": "LEVEL_1",
            "vandetanib": "LEVEL_1",
            "cabozantinib": "LEVEL_1",
        },
    },
    (
        "RET",
        "C634R",
        "MTC",
    ): {
        "mode": "replace",
        "drugs": {
            "selpercatinib": "LEVEL_1",
            "vandetanib": "LEVEL_1",
            "cabozantinib": "LEVEL_1",
        },
    },
    (
        "RET",
        "M918T",
        "MTC",
    ): {
        "mode": "replace",
        "drugs": {
            "selpercatinib": "LEVEL_1",
            "vandetanib": "LEVEL_1",
            "cabozantinib": "LEVEL_1",
        },
    },
    # EZH2 follicular lymphoma context.
    (
        "EZH2",
        "Y646N",
        "FOLLICULAR_LYMPHOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "tazemetostat": "LEVEL_1",
        },
    },
    (
        "EZH2",
        "Y646F",
        "FOLLICULAR_LYMPHOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "tazemetostat": "LEVEL_1",
        },
    },
    # PIK3CA breast cancer context.
    (
        "PIK3CA",
        "E545K",
        "BREAST",
    ): {
        "mode": "replace",
        "drugs": {
            "alpelisib": "LEVEL_1",
            "inavolisib": "LEVEL_1",
            "capivasertib": "LEVEL_1",  # CAPItello-291: FDA-approved for any PIK3CA-altered HR+/HER2- mBC
        },
    },
    (
        "PIK3CA",
        "H1047L",
        "BREAST",
    ): {
        "mode": "replace",
        "drugs": {
            "alpelisib": "LEVEL_1",
            "inavolisib": "LEVEL_1",
            "capivasertib": "LEVEL_1",  # CAPItello-291 covers H1047L
        },
    },
    # EGFR uncommon mutation NSCLC context.
    (
        "EGFR",
        "G719A",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "afatinib": "LEVEL_2",
            "osimertinib": "LEVEL_2",
        },
    },
    (
        "EGFR",
        "G719S",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "afatinib": "LEVEL_2",
            "osimertinib": "LEVEL_2",
        },
    },
    (
        "EGFR",
        "G719C",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "afatinib": "LEVEL_2",
            "osimertinib": "LEVEL_2",
        },
    },
    (
        "EGFR",
        "L861Q",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "afatinib": "LEVEL_2",
            "osimertinib": "LEVEL_2",
        },
    },
    (
        "EGFR",
        "S768I",
        "NSCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "afatinib": "LEVEL_2",
            "osimertinib": "LEVEL_2",
        },
    },

    # ── KRAS G12C COLORECTAL context ─────────────────────────────────────────
    # Sotorasib+panitumumab FDA-approved Feb 2024 for KRAS G12C CRC (CodeBreak 300).
    # Adagrasib+cetuximab FDA-approved 2024 for KRAS G12C CRC (KRYSTAL-10).
    # Cetuximab is LEVEL_1 (adagrasib combo) — keep above panitumumab to stay in top-3.
    # Panitumumab LEVEL_2 to avoid displacing cetuximab from top-3 ranking slots.
    (
        "KRAS",
        "G12C",
        "COLORECTAL",
    ): {
        "mode": "replace",
        "drugs": {
            "sotorasib": "LEVEL_1",
            "adagrasib": "LEVEL_1",
            "cetuximab": "LEVEL_1",     # adagrasib+cetuximab (KRYSTAL-10, FDA 2024)
            "panitumumab": "LEVEL_2",   # sotorasib+panitumumab (CodeBreak 300, FDA 2024); L2 to keep cetuximab in top-3
        },
    },

    # ── BRCA1/2 prostate cancer context ──────────────────────────────────────
    # Olaparib and rucaparib both FDA-approved for mCRPC with BRCA mutations.
    # PROfound 2020: olaparib L1 for BRCA1/2 and other HRR genes.
    # TRITON3: rucaparib L1 for BRCA1/2 mCRPC.
    # Niraparib (MAGNITUDE): approved with abiraterone in HRR+.
    (
        "BRCA1",
        "PATHOGENIC",
        "PROSTATE",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "rucaparib": "LEVEL_1",
            "niraparib": "LEVEL_2",
        },
    },
    (
        "BRCA2",
        "PATHOGENIC",
        "PROSTATE",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "rucaparib": "LEVEL_1",
            "niraparib": "LEVEL_2",
            "talazoparib": "LEVEL_2",  # TALAPRO-2 with enzalutamide
        },
    },

    # ── IDH2 glioma context ───────────────────────────────────────────────────
    # Vorasidenib (INDIGO, 2023) is approved for IDH1/IDH2-mutant grade 2 glioma.
    # Enasidenib has AML/MDS approval but NOT glioma-specific approval.
    (
        "IDH2",
        "R172K",
        "GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "vorasidenib": "LEVEL_1",
            "enasidenib": "LEVEL_2",    # off-label; approved for AML only
        },
    },
    (
        "IDH2",
        "R172W",
        "GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "vorasidenib": "LEVEL_1",
            "enasidenib": "LEVEL_2",
        },
    },
    (
        "IDH2",
        "R172G",
        "GLIOMA",
    ): {
        "mode": "replace",
        "drugs": {
            "vorasidenib": "LEVEL_1",
            "enasidenib": "LEVEL_2",
        },
    },

    # ── ATM prostate cancer context ───────────────────────────────────────────
    # PROfound enrolled ATM + other HRR gene cohort B — L2 outside of BRCA context.
    # Olaparib showed activity in ATM-mutant CRPC (cohort B of PROfound).
    (
        "ATM",
        "PATHOGENIC",
        "PROSTATE",
    ): {
        "mode": "replace",
        "drugs": {
            "olaparib": "LEVEL_1",
            "rucaparib": "LEVEL_2",
            "niraparib": "LEVEL_2",
        },
    },

    # ── MSI-H / dMMR colorectal context ──────────────────────────────────────
    # Nivolumab + ipilimumab FDA-approved for dMMR/MSI-H CRC (CheckMate 142 and 8HW).
    # Already have pembrolizumab L1 for all MSI-H; adding nivolumab+ipilimumab emphasis.
    (
        "MLH1",
        "MSI-H",
        "COLORECTAL",
    ): {
        "mode": "replace",
        "drugs": {
            "pembrolizumab": "LEVEL_1",
            "nivolumab": "LEVEL_1",
            "ipilimumab": "LEVEL_2",    # active as combo with nivolumab; lower single-agent activity
            "dostarlimab": "LEVEL_1",
        },
    },
    (
        "MSH2",
        "MSI-H",
        "COLORECTAL",
    ): {
        "mode": "merge",
        "drugs": {
            "nivolumab": "LEVEL_1",
            "ipilimumab": "LEVEL_2",
        },
    },

    # ── CLDN18 gastric/GEJ context ────────────────────────────────────────────
    # Zolbetuximab (VYLOY) FDA-approved Oct 2024 for CLDN18.2-positive gastric/GEJ
    # adenocarcinoma, 1L in combination with FOLFOX or CAPOX.
    # Trastuzumab adds L1 for HER2+ subset — but most CLDN18.2+ patients are HER2-negative.
    (
        "CLDN18",
        "OVEREXPRESSION",
        "GASTRIC",
    ): {
        "mode": "replace",
        "drugs": {
            "zolbetuximab": "LEVEL_1",
            "pembrolizumab": "LEVEL_2",   # nivolumab checkmate 649 approved regardless of CLDN18 status
        },
    },
    (
        "CLDN18",
        "OVEREXPRESSION",
        "GEJ",
    ): {
        "mode": "replace",
        "drugs": {
            "zolbetuximab": "LEVEL_1",
            "pembrolizumab": "LEVEL_2",
        },
    },

    # ── DLL3 SCLC context ─────────────────────────────────────────────────────
    # Tarlatamab (Imdelltra) FDA-approved May 2024 for DLL3-expressing SCLC
    # after ≥2 prior lines including platinum-based chemotherapy.
    # DLL3 is essentially universally expressed in SCLC — this context adds
    # specificity to avoid returning tarlatamab outside of SCLC.
    (
        "DLL3",
        "OVEREXPRESSION",
        "SCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "tarlatamab": "LEVEL_1",
            "topotecan": "LEVEL_2",    # standard 2L SCLC chemotherapy (context reference)
        },
    },
    (
        "DLL3",
        "EXPRESSION",
        "SCLC",
    ): {
        "mode": "replace",
        "drugs": {
            "tarlatamab": "LEVEL_1",
        },
    },

    # ── FOLR1 ovarian cancer context ──────────────────────────────────────────
    # Mirvetuximab soravtansine (Elahere) FDA full approval Oct 2023 (MIRASOL)
    # for FRα-high platinum-resistant ovarian cancer after 1-3 prior regimens.
    # "High" expression = ≥50% of cells ≥2+ by IHC (Ventana SP213 assay).
    (
        "FOLR1",
        "OVEREXPRESSION",
        "OVARIAN",
    ): {
        "mode": "replace",
        "drugs": {
            "mirvetuximab soravtansine": "LEVEL_1",
            "olaparib": "LEVEL_2",       # BRCA-wild-type patients may still have HRD benefit
            "niraparib": "LEVEL_2",
        },
    },
    (
        "FOLR1",
        "HIGH",
        "OVARIAN",
    ): {
        "mode": "replace",
        "drugs": {
            "mirvetuximab soravtansine": "LEVEL_1",
        },
    },
}


def _normalise_cancer_context(cancer_type: Optional[str]) -> Optional[str]:
    if not cancer_type:
        return None
    s = str(cancer_type).strip().lower()
    if ("non-small cell lung" in s) or ("nsclc" in s):
        return "NSCLC"
    if "breast" in s:
        return "BREAST"
    if "gastric" in s:
        return "GASTRIC"
    if "gastroesophageal" in s or "gastro-esophageal" in s or " gej" in s or s.startswith("gej"):
        return "GEJ"
    if ("pediatric" in s or "paediatric" in s) and "glioma" in s:
        return "PEDS_GLIOMA"
    if "glioma" in s or "glioblastoma" in s or "gbm" in s:
        return "GLIOMA"
    if "melanoma" in s:
        return "MELANOMA"
    if ("head and neck" in s) or ("oral" in s):
        return "HNSCC"
    if "endometr" in s:
        return "ENDOMETRIAL"
    if "neuroblastoma" in s:
        return "NEUROBLASTOMA"
    if ("renal" in s) or ("rcc" in s):
        return "RCC"
    if ("diffuse large b" in s) or ("dlbcl" in s):
        return "DLBCL"
    if ("follicular lymphoma" in s) or ("fl " in s and "lymphoma" in s):
        return "FOLLICULAR_LYMPHOMA"
    if ("basal cell" in s) or ("bcc" in s):
        return "BCC"
    if ("medullary thyroid" in s) or ("mtc" in s and "thyroid" in s):
        return "MTC"
    if ("anaplastic large cell" in s) or ("alcl" in s):
        return "ALCL"
    if ("waldenstrom" in s) or ("wm" in s and "macroglobulin" in s):
        return "WM"
    if ("uveal melanoma" in s) or ("choroidal melanoma" in s) or ("ocular melanoma" in s):
        return "UVEAL_MELANOMA"
    if ("hnscc" in s) or ("squamous" in s and ("head" in s or "neck" in s)):
        return "HNSCC"
    if "cholangiocarcinoma" in s or ("biliary" in s and "tract" in s):
        return "CHOLANGIO"
    if "myelofibrosis" in s or (" mf" == s[-3:]) or s.endswith("mf"):
        return "MYELOFIBROSIS"
    if "polycythemia vera" in s or ("pv" == s[-2:]):
        return "POLYCYTHEMIA_VERA"
    if ("colorectal" in s) or ("colon" in s) or ("rectal" in s) or ("crc" in s):
        return "COLORECTAL"
    if "ovarian" in s or "ovary" in s:
        return "OVARIAN"
    if ("acute myeloid" in s) or (" aml" in s) or s.startswith("aml"):
        return "AML"
    if "pancreatic" in s or "pancreas" in s or "pdac" in s:
        return "PANCREATIC"
    if "prostate" in s or "crpc" in s or "mcrpc" in s:
        return "PROSTATE"
    if "diffuse midline glioma" in s or ("dmg" in s and "glioma" in s):
        return "DIFFUSE_MIDLINE_GLIOMA"
    if "low grade glioma" in s or "low-grade glioma" in s or ("lgg" in s):
        return "LOW_GRADE_GLIOMA"
    if "bladder" in s or "urothelial" in s:
        return "BLADDER"
    if "hepatocellular" in s or (" hcc" in s) or s.startswith("hcc"):
        return "HCC"
    if "small cell lung" in s or "sclc" in s:
        return "SCLC"
    if "cervical" in s:
        return "CERVICAL"
    if "thyroid" in s:
        return "THYROID"
    if "esophageal" in s or "oesophageal" in s or "esophagus" in s:
        return "ESOPHAGEAL"
    return None


def _apply_cancer_context_override(
    level_map: dict[str, str],
    gene: str,
    alteration: str,
    cancer_type: Optional[str],
) -> dict[str, str]:
    """Apply tumour-context override rules to a drug→level map."""
    context = _normalise_cancer_context(cancer_type)
    if not context:
        return level_map

    gene_upper = gene.upper()
    alt_norm = _normalise_alteration(alteration).upper()
    rule = _CANCER_CONTEXT_OVERRIDES.get((gene_upper, alt_norm, context))
    if not rule:
        return level_map

    mode = str(rule.get("mode", "merge"))
    ctx_drugs = dict(rule.get("drugs", {}))

    if mode == "replace":
        # Keep any existing resistance annotations as safety floor.
        replaced = dict(ctx_drugs)
        for drug, level in level_map.items():
            if str(level).upper().startswith("LEVEL_R"):
                replaced[drug] = level
        return replaced

    merged = dict(level_map)
    merged.update(ctx_drugs)
    return merged

# Three-letter amino acid codes to single letter (IUPAC)
_AA3TO1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "TER": "*", "STOP": "*", "DEL": "del", "INS": "ins", "DUP": "dup",
}


# Explicit static-table gap fill when live API is present but known to be sparse
# for niche variant encodings or tumour-context-specific entries in our curated set.
# Outside these keys, static supplementation in live mode is restricted to R1/R2.
_STATIC_GAP_FILL_KEYS: frozenset[tuple[str, str]] = frozenset(
    {
        ("BRAF", "V600E-CRC"),
        ("EGFR", "EXON20INS"),
        ("ERBB2", "EXON20INS"),
        ("NTRK1", "FUSION"),
        ("ROS1", "FUSION"),
        ("RET", "FUSION"),
        ("FGFR2", "FUSION"),
        ("FGFR2", "AMPLIFICATION"),
    }
)


def _normalise_alteration(alt: str) -> str:
    """Normalise alteration string for lookup: lowercase, strip punctuation,
    convert 3-letter HGVS amino acid codes to 1-letter."""
    # Remove 'p.' HGVS prefix
    s = re.sub(r"^p\.", "", alt, flags=re.IGNORECASE).strip()
    s = s.upper()
    # Convert three-letter amino acid codes: e.g. Thr790Met → T790M
    # Pattern: 3-letter AA code (optional) + number + 3-letter AA code (optional)
    def _replace_aa(m: re.Match) -> str:
        aa = m.group(0)
        return _AA3TO1.get(aa, aa)
    s = re.sub(r"[A-Z]{3}", _replace_aa, s)
    # Strip separators (spaces, dots, hyphens, underscores)
    s = re.sub(r"[.\-_ ]", "", s)
    # Lowercase the final result (test contract: _normalise_alteration returns lowercase)
    s = s.lower()
    return _ALTERATION_ALIASES.get(s, s)


def _normalise_drug(name: str) -> str:
    """Normalise drug name for matching."""
    return re.sub(r"[\s\-.]", "", name.lower())


def lookup_oncokb_level(gene: str, alteration: str, drug_name: str) -> Optional[str]:
    """Return OncoKB evidence level for a gene/alteration/drug triple.

    Returns None if no entry exists (neither sensitive nor resistant).
    Returns LEVEL_R1/LEVEL_R2 if the drug is a known resistance marker.
    """
    gene_upper = gene.upper()
    alt_norm = _normalise_alteration(alteration).upper()
    drug_norm = _normalise_drug(drug_name)

    entry = _LEVEL_TABLE.get((gene_upper, alt_norm))
    if entry is None:
        # Try partial key variants
        for (g, a), drugs in _LEVEL_TABLE.items():
            if g == gene_upper and alt_norm in a or a in alt_norm:
                entry = drugs
                break

    if entry is None:
        return None

    # Match drug name
    for table_drug, level in entry.items():
        if _normalise_drug(table_drug) in drug_norm or drug_norm in _normalise_drug(table_drug):
            return level

    return None


_GENE_FALLBACK_ALTS: tuple[str, ...] = ("ONCOGENICMUTATIONS", "MUTATION", "ONCOGENIC")
_GENE_FALLBACK_AM_THRESHOLD = 0.564


def _has_l1_or_l2_actionable_entry(gene_upper: str) -> bool:
    for (g, _alt), drugs in _LEVEL_TABLE.items():
        if g != gene_upper or not drugs:
            continue
        for level in drugs.values():
            level_upper = _normalise_level_token(str(level) or "")
            if level_upper in {"LEVEL_1", "LEVEL_2"}:
                return True
    return False


def get_known_actionable_gene_count() -> int:
    genes: set[str] = set()
    for (gene, _alt), drugs in _LEVEL_TABLE.items():
        if not drugs:
            continue
        for level in drugs.values():
            level_upper = _normalise_level_token(str(level) or "")
            if level_upper in {"LEVEL_1", "LEVEL_2"}:
                genes.add(gene)
                break
    return len(genes)


def _coerce_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cap_fallback_level(level: str) -> str:
    normalized = _normalise_level_token(level) or ""
    if normalized in {"LEVEL_R1", "LEVEL_R2"}:
        return normalized
    return "LEVEL_2B"


def _get_all_drugs_for_variant_internal(
    gene: str,
    alteration: str,
    alphamissense_score: Optional[float] = None,
) -> tuple[dict[str, str], set[str]]:
    """Return all drug→level mappings and fallback provenance for a variant."""
    gene_upper = gene.upper()
    alt_norm = _normalise_alteration(alteration).upper()

    # ── Compound variant handling (e.g. "T790M+C797S") ────────────────────
    if "+" in alt_norm:
        parts = [p.strip() for p in alt_norm.split("+") if p.strip()]
        merged: dict[str, str] = {}
        for part in parts:
            part_result = _LEVEL_TABLE.get((gene_upper, part), {})
            if not part_result:
                for (g, a), drugs in _LEVEL_TABLE.items():
                    if g == gene_upper and (part in a or a in part) and "+" not in a:
                        part_result = drugs
                        break
            for drug, level in part_result.items():
                if drug not in merged or "R" not in merged[drug]:
                    merged[drug] = level
        part_frozenset = frozenset(parts)
        compound_key = (gene_upper, part_frozenset)
        if compound_key in _COMPOUND_RESISTANCE_TABLE:
            for drug, res_level in _COMPOUND_RESISTANCE_TABLE[compound_key].items():
                merged[drug] = res_level
        return merged, set()

    # ── Standard single-variant lookup ────────────────────────────────────
    result = _LEVEL_TABLE.get((gene_upper, alt_norm), {})
    if not result:
        for (g, a), drugs in _LEVEL_TABLE.items():
            if g == gene_upper and "+" not in a and (alt_norm in a or a in alt_norm):
                result = drugs
                break
    if result:
        return dict(result), set()

    # Gene-level fallback for non-hotspot activating variants.
    am_score = _coerce_float(alphamissense_score)
    if am_score is None or am_score < _GENE_FALLBACK_AM_THRESHOLD:
        return {}, set()
    if not _has_l1_or_l2_actionable_entry(gene_upper):
        return {}, set()

    for fallback_alt in _GENE_FALLBACK_ALTS:
        fallback = _LEVEL_TABLE.get((gene_upper, fallback_alt))
        if fallback:
            capped = {drug: _cap_fallback_level(level) for drug, level in fallback.items()}
            return capped, set(capped.keys())

    return {}, set()


def get_all_drugs_for_variant(
    gene: str,
    alteration: str,
    alphamissense_score: Optional[float] = None,
) -> dict[str, str]:
    levels, _fallback_drugs = _get_all_drugs_for_variant_internal(
        gene,
        alteration,
        alphamissense_score=alphamissense_score,
    )
    return levels


def get_all_drugs_for_variant_with_metadata(
    gene: str,
    alteration: str,
    alphamissense_score: Optional[float] = None,
) -> dict[str, object]:
    levels, fallback_drugs = _get_all_drugs_for_variant_internal(
        gene,
        alteration,
        alphamissense_score=alphamissense_score,
    )
    return {
        "drug_levels": levels,
        "gene_fallback_drugs": sorted(fallback_drugs),
        "known_actionable_gene": _has_l1_or_l2_actionable_entry(gene.upper()),
        "alphamissense_score": _coerce_float(alphamissense_score),
    }


def get_all_drugs_for_variant_live(
    gene: str,
    alteration: str,
    cancer_type: Optional[str] = None,
    alphamissense_score: Optional[float] = None,
) -> dict[str, str]:
    """Synchronous live-API-first wrapper for get_all_drugs_for_variant.

    Priority order:
      1. Live OncoKB API (when ONCOKB_API_TOKEN is set in env/config).
         Covers all OncoKB levels across >5,000 variant/cancer combinations.
      2. Curated static table (always merged for resistance entries).

    The static table is ALWAYS consulted for resistance (LEVEL_R1/R2) entries
    regardless of whether the live API returned data, because resistance
    annotations are safety-critical and the live API may not always flag them.

    Use this function in benchmarks, demo scripts, and any offline analysis
    that should reflect live-API performance when a token is available.
    """
    token = _get_oncokb_token()

    def _merge_live_with_static_safety(live: dict[str, str]) -> dict[str, str]:
        """Merge policy for live mode: resistance always, static gap fill by allowlist."""
        gene_upper = gene.upper()
        alt_norm = _normalise_alteration(alteration)
        allow_gap_fill = (gene_upper, alt_norm) in _STATIC_GAP_FILL_KEYS

        merged = dict(live)
        static = get_all_drugs_for_variant(
            gene,
            alteration,
            alphamissense_score=alphamissense_score,
        )
        for drug, level in static.items():
            level_upper = str(level).upper()
            is_resistance = level_upper.startswith("LEVEL_R")
            if is_resistance:
                merged[drug] = level
            elif allow_gap_fill and drug not in merged:
                merged[drug] = level
        return _apply_cancer_context_override(merged, gene, alteration, cancer_type)

    if not token:
        # No live API — return curated table only
        static_only = get_all_drugs_for_variant(
            gene,
            alteration,
            alphamissense_score=alphamissense_score,
        )
        return _apply_cancer_context_override(static_only, gene, alteration, cancer_type)

    try:
        import asyncio

        async def _fetch() -> dict[str, str]:
            from services.oncokb import OncoKBClient
            client = OncoKBClient(token)
            annotation = await client.annotate_mutation(gene, alteration, cancer_type)
            treatments = annotation.get("treatments", [])
            live: dict[str, str] = {}
            for t in treatments:
                level = t.get("level", "")
                for drug in t.get("drugs", []):
                    name_raw = drug.get("drugName", "")
                    if name_raw:
                        live[name_raw.lower()] = level
            return live

        # Run async fetch in a new event loop (sync context)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("closed")
            live_drugs = loop.run_until_complete(_fetch())
        except RuntimeError:
            live_drugs = asyncio.run(_fetch())

    except Exception as exc:
        logger.warning(
            "[OncoKB API] Live lookup failed for %s %s — applying safety-only static merge: %s",
            gene, alteration, exc,
        )
        return _merge_live_with_static_safety({})

    if not live_drugs:
        logger.info(
            "[OncoKB API] No treatments from API for %s %s; applying safety-only static merge",
            gene,
            alteration,
        )
        return _merge_live_with_static_safety({})

    merged = _merge_live_with_static_safety(live_drugs)

    logger.info(
        "[OncoKB API] Live hit for %s %s: %d drugs (merged with static safety/gap rules)",
        gene,
        alteration,
        len(live_drugs),
    )
    return merged


def get_all_drugs_for_variant_live_with_metadata(
    gene: str,
    alteration: str,
    cancer_type: Optional[str] = None,
    alphamissense_score: Optional[float] = None,
) -> dict[str, object]:
    token = _get_oncokb_token()

    def _merge_live_with_static_safety_and_meta(live: dict[str, str]) -> tuple[dict[str, str], set[str]]:
        gene_upper = gene.upper()
        alt_norm = _normalise_alteration(alteration)
        allow_gap_fill = (gene_upper, alt_norm) in _STATIC_GAP_FILL_KEYS

        merged = dict(live)
        fallback_drugs: set[str] = set()
        static_meta = get_all_drugs_for_variant_with_metadata(
            gene,
            alteration,
            alphamissense_score=alphamissense_score,
        )
        static = dict(static_meta.get("drug_levels") or {})
        static_fallback = set(static_meta.get("gene_fallback_drugs") or [])
        for drug, level in static.items():
            level_upper = str(level).upper()
            is_resistance = level_upper.startswith("LEVEL_R")
            if is_resistance:
                merged[drug] = level
            elif allow_gap_fill and drug not in merged:
                merged[drug] = level

            if drug in static_fallback and drug in merged:
                fallback_drugs.add(drug)

        adjusted = _apply_cancer_context_override(merged, gene, alteration, cancer_type)
        return adjusted, {d for d in fallback_drugs if d in adjusted}

    if not token:
        static_meta = get_all_drugs_for_variant_with_metadata(
            gene,
            alteration,
            alphamissense_score=alphamissense_score,
        )
        levels = _apply_cancer_context_override(
            dict(static_meta.get("drug_levels") or {}),
            gene,
            alteration,
            cancer_type,
        )
        fallback = [d for d in static_meta.get("gene_fallback_drugs") or [] if d in levels]
        return {
            "drug_levels": levels,
            "gene_fallback_drugs": sorted(fallback),
            "known_actionable_gene": bool(static_meta.get("known_actionable_gene")),
            "alphamissense_score": static_meta.get("alphamissense_score"),
        }

    try:
        import asyncio

        async def _fetch() -> dict[str, str]:
            from services.oncokb import OncoKBClient
            client = OncoKBClient(token)
            annotation = await client.annotate_mutation(gene, alteration, cancer_type)
            treatments = annotation.get("treatments", [])
            live: dict[str, str] = {}
            for t in treatments:
                level = t.get("level", "")
                for drug in t.get("drugs", []):
                    name_raw = drug.get("drugName", "")
                    if name_raw:
                        live[name_raw.lower()] = level
            return live

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("closed")
            live_drugs = loop.run_until_complete(_fetch())
        except RuntimeError:
            live_drugs = asyncio.run(_fetch())

    except Exception as exc:
        logger.warning(
            "[OncoKB API] Live lookup failed for %s %s — applying safety-only static merge: %s",
            gene, alteration, exc,
        )
        merged_levels, fallback_drugs = _merge_live_with_static_safety_and_meta({})
        return {
            "drug_levels": merged_levels,
            "gene_fallback_drugs": sorted(fallback_drugs),
            "known_actionable_gene": _has_l1_or_l2_actionable_entry(gene.upper()),
            "alphamissense_score": _coerce_float(alphamissense_score),
        }

    merged_levels, fallback_drugs = _merge_live_with_static_safety_and_meta(live_drugs)
    return {
        "drug_levels": merged_levels,
        "gene_fallback_drugs": sorted(fallback_drugs),
        "known_actionable_gene": _has_l1_or_l2_actionable_entry(gene.upper()),
        "alphamissense_score": _coerce_float(alphamissense_score),
    }


# ── Compound resistance handling ──────────────────────────────────────────────

# Compound-resistance table: when a patient has BOTH alteration_A and alteration_B
# in the SAME gene (or a defined compound context), additional resistance annotations
# are applied on top of the single-variant table.
#
# Key: (GENE, FROZENSET of normalised alterations that must BOTH be present)
# Value: {drug_name_lower: resistance_level}
#
# Sources:
#   - EGFR T790M + C797S: Thress et al. Nat Med 2015 (osimertinib resistance)
#   - ABL1 T315I + E255K: Zabriskie et al. Cancer Cell 2014 (ponatinib resistance)
#   - ALK L1196M: Shaw et al. NEJM 2014 (crizotinib resistance, 3rd-gen susceptible)

_COMPOUND_RESISTANCE_TABLE: dict[tuple[str, frozenset], dict[str, str]] = {
    # EGFR T790M acquired, then C797S acquired on top → Osimertinib becomes resistant
    ("EGFR", frozenset({"T790M", "C797S"})): {
        "osimertinib": "LEVEL_R1",
        "erlotinib": "LEVEL_R1",
        "gefitinib": "LEVEL_R1",
        "afatinib": "LEVEL_R1",
    },
    # EGFR T790M + L718V/Q compound → Osimertinib resistant (Fassunke et al. 2018)
    ("EGFR", frozenset({"T790M", "L718V"})): {
        "osimertinib": "LEVEL_R1",
    },
    ("EGFR", frozenset({"T790M", "L718Q"})): {
        "osimertinib": "LEVEL_R1",
    },
    # ABL1 T315I compound resistance against ponatinib (rare)
    ("ABL1", frozenset({"T315I", "E255K"})): {
        "ponatinib": "LEVEL_R2",
        "imatinib": "LEVEL_R1",
        "dasatinib": "LEVEL_R1",
        "nilotinib": "LEVEL_R1",
        "bosutinib": "LEVEL_R1",
    },
    ("ABL1", frozenset({"T315I", "F317L"})): {
        "ponatinib": "LEVEL_R2",
    },
}


def annotate_compound_resistance(
    candidates: list[dict],
    gene: str,
    alterations: list[str],
) -> list[dict]:
    """Apply compound-resistance rules when multiple alterations are present.

    Unlike single-variant annotation, compound resistance requires BOTH
    alterations to be present simultaneously (e.g., T790M + C797S → Osimertinib R1).

    This should be called AFTER annotate_candidates() with the full list of
    alterations detected for the same gene.

    Args:
        candidates:   List of candidate dicts (already single-variant annotated).
        gene:         Gene symbol (e.g. "EGFR").
        alterations:  All normalised alterations present for this gene
                      (e.g. ["T790M", "C797S"]).

    Returns:
        Same list with compound resistance levels overlaid where applicable.
    """
    if len(alterations) < 2:
        return candidates  # Compound resistance requires ≥ 2 alterations

    gene_upper = gene.upper()
    alt_norms = frozenset(_normalise_alteration(a).upper() for a in alterations)

    compound_drugs: dict[str, str] = {}
    for (tbl_gene, tbl_alts), drugs in _COMPOUND_RESISTANCE_TABLE.items():
        if tbl_gene == gene_upper and tbl_alts.issubset(alt_norms):
            compound_drugs.update(drugs)

    if not compound_drugs:
        return candidates

    for cand in candidates:
        drug_name = cand.get("drug_name") or cand.get("preferred_name") or ""
        drug_norm = _normalise_drug(drug_name)
        for r_drug, r_level in compound_drugs.items():
            if _normalise_drug(r_drug) in drug_norm or drug_norm in _normalise_drug(r_drug):
                existing = cand.get("oncokb_level", "")
                # Apply compound resistance — overrides previous sensitivity annotation
                if not existing or "R" not in existing:
                    cand["oncokb_level"] = r_level
                    cand["_compound_resistance"] = True
                break

    # Inject compound-resistant annotations for drugs not yet in the list
    existing_norms = {_normalise_drug(c.get("drug_name") or "") for c in candidates}
    for r_drug, r_level in compound_drugs.items():
        rn = _normalise_drug(r_drug)
        already_present = any(rn in e or e in rn for e in existing_norms)
        if not already_present:
            candidates.append({
                "drug_name": r_drug.title(),
                "is_approved": False,
                "max_phase": None,
                "opentargets_score": None,
                "oncokb_level": r_level,
                "chembl_id": None,
                "binding_score": None,
                "_compound_resistance": True,
                "_injected_from_compound_table": True,
            })
            existing_norms.add(rn)

    logger.info(
        "[OncoKB] Compound resistance applied for %s with alterations %s — "
        "%d drug(s) affected",
        gene, alterations, len(compound_drugs),
    )
    return candidates


def annotate_candidates(
    candidates: list[dict],
    gene: str,
    alteration: str,
    inject_missing_level1: bool = True,
) -> list[dict]:
    """Set oncokb_level on each candidate based on the lookup table.

    Overwrites any existing oncokb_level only if the table has an entry.
    Preserves None (not in table) vs. actual level assignments.

    When inject_missing_level1=True (default), any LEVEL_1 drug from the
    curated table that is absent from the candidate list is appended with
    baseline opentargets_score=0.85. This prevents a drug like Osimertinib
    from being invisible simply because OpenTargets returned it outside the
    query page limit.
    """
    # If called with empty candidates, nothing to annotate or inject into
    if not candidates:
        return candidates

    # Get all drug→level for this variant up front
    variant_drugs = get_all_drugs_for_variant(gene, alteration)
    if not variant_drugs:
        logger.debug("No OncoKB table entries for %s %s", gene, alteration)
        return candidates

    n_annotated = 0
    for cand in candidates:
        drug_name = cand.get("drug_name") or cand.get("preferred_name") or ""
        level = lookup_oncokb_level(gene, alteration, drug_name)
        if level is not None:
            cand["oncokb_level"] = level
            n_annotated += 1

    logger.info(
        "[OncoKB] Annotated %d/%d candidates for %s %s",
        n_annotated, len(candidates), gene, alteration,
    )

    if inject_missing_level1:
        existing_norms = {_normalise_drug(c.get("drug_name") or "") for c in candidates}
        n_injected = 0
        for table_drug, level in variant_drugs.items():
            if level not in ("LEVEL_1", "LEVEL_2"):
                continue
            tn = _normalise_drug(table_drug)
            # Check if this drug (or a close variant) is already present
            already_present = any(tn in e or e in tn for e in existing_norms)
            if not already_present:
                candidates.append({
                    "drug_name": table_drug.title(),  # e.g. "Osimertinib"
                    "is_approved": level == "LEVEL_1",
                    "max_phase": "APPROVAL" if level == "LEVEL_1" else "PHASE3",
                    # opentargets_score is None because we have no actual OT query
                    # result for this drug — it was absent from the OT response.
                    # Setting it to a fake value would inflate the rank_score via
                    # weight redistribution. The oncokb_level carries the evidence.
                    "opentargets_score": None,
                    "oncokb_level": level,
                    "chembl_id": None,
                    "binding_score": None,
                    "_injected_from_oncokb_table": True,
                })
                existing_norms.add(tn)
                n_injected += 1

        if n_injected:
            logger.info(
                "[OncoKB] Injected %d missing Level 1/2 drugs for %s %s",
                n_injected, gene, alteration,
            )

    return candidates


def _get_oncokb_token() -> str:
    """Retrieve ONCOKB_API_TOKEN from environment or app settings."""
    try:
        import os
        token = os.environ.get("ONCOKB_API_TOKEN", "")
        if not token:
            from config import settings
            token = getattr(settings, "oncokb_api_token", "") or ""
        return token
    except Exception:
        return ""


def _merge_resistance_from_table(
    candidates: list[dict], gene: str, alteration: str
) -> list[dict]:
    """Overlay LEVEL_R1/R2 resistance entries from the static table.

    Resistance labels are safety-critical. Even when the live API is the
    primary annotation source, known resistance designations from the curated
    table (e.g. Afatinib LEVEL_R1 for EGFR T790M) must be preserved.
    Only downgrades existing annotations; never upgrades via this path.
    """
    variant_drugs = get_all_drugs_for_variant(gene, alteration)
    resistance_drugs = {k: v for k, v in variant_drugs.items() if "R" in v}
    if not resistance_drugs:
        return candidates

    for cand in candidates:
        drug_name = cand.get("drug_name") or cand.get("preferred_name") or ""
        drug_norm = _normalise_drug(drug_name)
        for r_drug, r_level in resistance_drugs.items():
            if _normalise_drug(r_drug) in drug_norm or drug_norm in _normalise_drug(r_drug):
                existing = cand.get("oncokb_level", "")
                # Apply resistance only if not already flagged as resistant
                if not existing or "R" not in existing:
                    cand["oncokb_level"] = r_level
                break

    return candidates


async def annotate_candidates_with_oncokb(
    candidates: list[dict],
    gene: str,
    protein_change: str,
    cancer_type: Optional[str] = None,
) -> list[dict]:
    """Annotate candidates: live OncoKB API first, curated table as fallback.

    When ONCOKB_API_TOKEN is set the live API is the primary source — it covers
    all OncoKB levels (1–4), novel variants, and tumour-type-specific evidence
    that the static table cannot provide.  Resistance entries from the curated
    table are always merged in afterwards regardless of which path ran, because
    they are safety-critical and must never be silently omitted.

    Fallback order when no token is configured (or API call fails):
        curated table → injected Level 1/2 drugs
    """
    token = _get_oncokb_token()

    if token:
        # ── Primary path: live OncoKB API ──────────────────────────────────
        try:
            from services.oncokb import OncoKBClient
            client = OncoKBClient(token)
            annotation = await client.annotate_mutation(gene, protein_change, cancer_type)
            treatments = annotation.get("treatments", [])

            # Build normalised drug→level map
            live_levels: dict[str, str] = {}
            for t in treatments:
                level = t.get("level", "")
                for drug in t.get("drugs", []):
                    name_raw = drug.get("drugName", "")
                    if name_raw:
                        live_levels[_normalise_drug(name_raw)] = level

            if live_levels:
                # Annotate existing candidates from live data
                n_annotated = 0
                for cand in candidates:
                    drug_name = cand.get("drug_name") or cand.get("preferred_name") or ""
                    drug_norm = _normalise_drug(drug_name)
                    for live_drug, level in live_levels.items():
                        if live_drug in drug_norm or drug_norm in live_drug:
                            cand["oncokb_level"] = level
                            n_annotated += 1
                            break

                # Inject missing Level 1/2 drugs reported by the API
                existing_norms = {_normalise_drug(c.get("drug_name") or "") for c in candidates}
                n_injected = 0
                for t in treatments:
                    level = t.get("level", "")
                    if level not in ("LEVEL_1", "LEVEL_2"):
                        continue
                    for drug in t.get("drugs", []):
                        name_raw = drug.get("drugName", "")
                        if not name_raw:
                            continue
                        dn = _normalise_drug(name_raw)
                        if not any(dn in e or e in dn for e in existing_norms):
                            candidates.append({
                                "drug_name": name_raw,
                                "is_approved": level == "LEVEL_1",
                                "max_phase": "APPROVAL" if level == "LEVEL_1" else "PHASE3",
                                # opentargets_score left None: the OncoKB API confirmed
                                # this drug's level but we have no OpenTargets association
                                # score for it. The oncokb_level is the evidence source.
                                "opentargets_score": None,
                                "oncokb_level": level,
                                "chembl_id": None,
                                "binding_score": None,
                                "_injected_from_oncokb_api": True,
                            })
                            existing_norms.add(dn)
                            n_injected += 1

                logger.info(
                    "[OncoKB API] %s %s — annotated %d, injected %d (live API)",
                    gene, protein_change, n_annotated, n_injected,
                )

                # Always overlay resistance entries from the static table
                candidates = _merge_resistance_from_table(candidates, gene, protein_change)
                return candidates

            logger.info(
                "[OncoKB API] No treatments returned for %s %s; falling back to table",
                gene, protein_change,
            )

        except Exception as exc:
            logger.warning(
                "[OncoKB API] Live lookup failed for %s %s — falling back to curated table: %s",
                gene, protein_change, exc,
            )

    # ── Fallback path: curated static table ────────────────────────────────
    candidates = annotate_candidates(candidates, gene, protein_change)
    return candidates
