"""Pathway alteration context service.

Maps mutated genes to cancer-relevant signalling pathways to help oncologists
understand co-occurring pathway hits in a tumour profile.

Sources:
  - KEGG pathway database (cached gene→pathway map)
  - Reactome pathway hierarchy (cancer-relevant subset)
  - MSigDB Hallmark gene sets (used by GSEA/cancer genomics community)

The service exposes:
  - get_pathways_for_gene(gene)     — all pathways for a single gene
  - annotate_mutation_list(mutations) — enrich a mutation list with pathways
  - get_co_altered_pathway_summary(mutations) — which pathways are most hit

This data drives the "Pathway context" panel on the results page and helps
oncologists identify convergent pathway activation from multi-gene profiles.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
# Keys are Hugo gene symbols; values are lists of (pathway_id, pathway_name) tuples.
# This static map covers the ~300 most clinically relevant oncology genes.
# For full coverage, integrate the KEGG REST API (get_pathways_for_gene()).

_GENE_PATHWAY_MAP: dict[str, list[tuple[str, str]]] = {
    # ── RAS/MAPK pathway ──────────────────────────────────────────────────────
    "KRAS":  [("HALLMARK_KRAS_SIGNALING_UP", "KRAS Signalling (Up)"),
              ("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling"),
              ("REACTOME_RAS_SIGNALLING", "RAS Signalling")],
    "NRAS":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling"),
              ("REACTOME_RAS_SIGNALLING", "RAS Signalling")],
    "HRAS":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling"),
              ("REACTOME_RAS_SIGNALLING", "RAS Signalling")],
    "BRAF":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling"),
              ("HALLMARK_KRAS_SIGNALING_UP", "KRAS Signalling (Up)")],
    "RAF1":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "MAP2K1": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "MAP2K2": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "MAPK1": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "MAPK3": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],

    # ── PI3K/AKT/mTOR pathway ─────────────────────────────────────────────────
    "PIK3CA": [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling"),
               ("KEGG_PI3K_AKT_SIGNALING_PATHWAY", "PI3K-AKT Signalling")],
    "PIK3R1": [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling")],
    "AKT1":   [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling")],
    "AKT2":   [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling")],
    "AKT3":   [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling")],
    "MTOR":   [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling"),
               ("KEGG_MTOR_SIGNALING_PATHWAY", "mTOR Signalling")],
    "PTEN":   [("HALLMARK_PI3K_AKT_MTOR_SIGNALING", "PI3K/AKT/mTOR Signalling"),
               ("REACTOME_PI3K_CASCADE", "PI3K Cascade")],
    "TSC1":   [("KEGG_MTOR_SIGNALING_PATHWAY", "mTOR Signalling")],
    "TSC2":   [("KEGG_MTOR_SIGNALING_PATHWAY", "mTOR Signalling")],
    "RICTOR": [("KEGG_MTOR_SIGNALING_PATHWAY", "mTOR Signalling")],

    # ── EGFR / RTK pathway ────────────────────────────────────────────────────
    "EGFR":   [("REACTOME_SIGNALLING_BY_EGFR", "EGFR Signalling"),
               ("KEGG_ErbB_SIGNALING_PATHWAY", "ErbB Signalling")],
    "ERBB2":  [("KEGG_ErbB_SIGNALING_PATHWAY", "ErbB Signalling"),
               ("REACTOME_SIGNALLING_BY_ERBB2", "ERBB2 Signalling")],
    "ERBB3":  [("KEGG_ErbB_SIGNALING_PATHWAY", "ErbB Signalling")],
    "ERBB4":  [("KEGG_ErbB_SIGNALING_PATHWAY", "ErbB Signalling")],
    "MET":    [("KEGG_FOCAL_ADHESION", "Focal Adhesion"),
               ("REACTOME_SIGNALLING_BY_MET", "MET Signalling")],
    "FGFR1":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "FGFR2":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "FGFR3":  [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "ALK":    [("REACTOME_SIGNALLING_BY_ALK", "ALK Signalling")],
    "ROS1":   [("REACTOME_SIGNALLING_BY_ROS1", "ROS1 Signalling")],
    "RET":    [("REACTOME_SIGNALLING_BY_RET", "RET Signalling")],
    "KIT":    [("KEGG_CYTOKINE_CYTOKINE_RECEPTOR_INTERACTION", "Cytokine Signalling")],
    "PDGFRA": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "PDGFRB": [("KEGG_MAPK_SIGNALING_PATHWAY", "MAPK Signalling")],
    "FLT3":   [("REACTOME_SIGNALLING_BY_FLT3", "FLT3 Signalling")],
    "VEGFA":  [("KEGG_VEGF_SIGNALING_PATHWAY", "VEGF Signalling")],

    # ── TP53 / DNA damage response ────────────────────────────────────────────
    "TP53":   [("HALLMARK_P53_PATHWAY", "p53 Pathway"),
               ("REACTOME_TP53_REGULATION", "TP53 Regulation"),
               ("KEGG_P53_SIGNALING_PATHWAY", "p53 Signalling")],
    "MDM2":   [("HALLMARK_P53_PATHWAY", "p53 Pathway")],
    "MDM4":   [("HALLMARK_P53_PATHWAY", "p53 Pathway")],
    "CDKN2A": [("HALLMARK_P53_PATHWAY", "p53 Pathway"),
               ("KEGG_CELL_CYCLE", "Cell Cycle")],
    "ATM":    [("REACTOME_DNA_REPAIR", "DNA Repair"),
               ("HALLMARK_DNA_REPAIR", "DNA Repair")],
    "BRCA1":  [("REACTOME_HOMOLOGOUS_RECOMBINATION_REPAIR", "Homologous Recombination"),
               ("HALLMARK_DNA_REPAIR", "DNA Repair")],
    "BRCA2":  [("REACTOME_HOMOLOGOUS_RECOMBINATION_REPAIR", "Homologous Recombination"),
               ("HALLMARK_DNA_REPAIR", "DNA Repair")],
    "PALB2":  [("REACTOME_HOMOLOGOUS_RECOMBINATION_REPAIR", "Homologous Recombination")],
    "CHEK1":  [("REACTOME_DNA_REPAIR", "DNA Repair")],
    "CHEK2":  [("REACTOME_DNA_REPAIR", "DNA Repair")],

    # ── Cell cycle ────────────────────────────────────────────────────────────
    "CDK4":   [("KEGG_CELL_CYCLE", "Cell Cycle")],
    "CDK6":   [("KEGG_CELL_CYCLE", "Cell Cycle")],
    "CCND1":  [("KEGG_CELL_CYCLE", "Cell Cycle")],
    "CCND2":  [("KEGG_CELL_CYCLE", "Cell Cycle")],
    "CCNE1":  [("KEGG_CELL_CYCLE", "Cell Cycle")],
    "RB1":    [("KEGG_CELL_CYCLE", "Cell Cycle"),
               ("REACTOME_CELL_CYCLE_CHECKPOINTS", "Cell Cycle Checkpoints")],

    # ── Wnt / β-catenin ───────────────────────────────────────────────────────
    "CTNNB1": [("KEGG_WNT_SIGNALING_PATHWAY", "Wnt Signalling"),
               ("HALLMARK_WNT_BETA_CATENIN_SIGNALING", "Wnt/β-catenin Signalling")],
    "APC":    [("KEGG_WNT_SIGNALING_PATHWAY", "Wnt Signalling")],
    "AXIN1":  [("KEGG_WNT_SIGNALING_PATHWAY", "Wnt Signalling")],
    "AXIN2":  [("KEGG_WNT_SIGNALING_PATHWAY", "Wnt Signalling")],
    "RNF43":  [("KEGG_WNT_SIGNALING_PATHWAY", "Wnt Signalling")],

    # ── Hedgehog pathway ──────────────────────────────────────────────────────
    "PTCH1":  [("KEGG_HEDGEHOG_SIGNALING_PATHWAY", "Hedgehog Signalling")],
    "SMO":    [("KEGG_HEDGEHOG_SIGNALING_PATHWAY", "Hedgehog Signalling")],
    "GLI1":   [("KEGG_HEDGEHOG_SIGNALING_PATHWAY", "Hedgehog Signalling")],
    "GLI2":   [("KEGG_HEDGEHOG_SIGNALING_PATHWAY", "Hedgehog Signalling")],

    # ── Notch pathway ─────────────────────────────────────────────────────────
    "NOTCH1": [("KEGG_NOTCH_SIGNALING_PATHWAY", "Notch Signalling")],
    "NOTCH2": [("KEGG_NOTCH_SIGNALING_PATHWAY", "Notch Signalling")],

    # ── Chromatin / epigenetics ───────────────────────────────────────────────
    "ARID1A": [("REACTOME_CHROMATIN_ORGANIZATION", "Chromatin Organisation")],
    "SMARCA4": [("REACTOME_CHROMATIN_ORGANIZATION", "Chromatin Organisation")],
    "SMARCB1": [("REACTOME_CHROMATIN_ORGANIZATION", "Chromatin Organisation")],
    "KMT2A":  [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],
    "KMT2C":  [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],
    "KMT2D":  [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],
    "DNMT3A": [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],
    "IDH1":   [("REACTOME_EPIGENETICS", "Epigenetic Regulation"),
               ("KEGG_METABOLIC_PATHWAYS", "Metabolic Pathways")],
    "IDH2":   [("REACTOME_EPIGENETICS", "Epigenetic Regulation"),
               ("KEGG_METABOLIC_PATHWAYS", "Metabolic Pathways")],
    "TET2":   [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],
    "EZH2":   [("REACTOME_EPIGENETICS", "Epigenetic Regulation")],

    # ── Apoptosis ─────────────────────────────────────────────────────────────
    "BCL2":   [("HALLMARK_APOPTOSIS", "Apoptosis")],
    "BCL2L1": [("HALLMARK_APOPTOSIS", "Apoptosis")],
    "MCL1":   [("HALLMARK_APOPTOSIS", "Apoptosis")],
    "BAX":    [("HALLMARK_APOPTOSIS", "Apoptosis")],

    # ── Immune / immunotherapy ────────────────────────────────────────────────
    "CD274":  [("HALLMARK_IL6_JAK_STAT3_SIGNALING", "IL-6/JAK/STAT3 Signalling"),
               ("REACTOME_IMMUNE_SYSTEM", "Immune System")],
    "PDCD1LG2": [("REACTOME_IMMUNE_SYSTEM", "Immune System")],
    "PDCD1":  [("REACTOME_IMMUNE_SYSTEM", "Immune System")],
    "CTLA4":  [("REACTOME_IMMUNE_SYSTEM", "Immune System")],
    "JAK1":   [("HALLMARK_IL6_JAK_STAT3_SIGNALING", "IL-6/JAK/STAT3 Signalling")],
    "JAK2":   [("HALLMARK_IL6_JAK_STAT3_SIGNALING", "IL-6/JAK/STAT3 Signalling")],
    "STAT3":  [("HALLMARK_IL6_JAK_STAT3_SIGNALING", "IL-6/JAK/STAT3 Signalling")],

    # ── Haematologic malignancies ─────────────────────────────────────────────
    "ABL1":   [("REACTOME_SIGNALLING_BY_BCR_ABL1", "BCR-ABL1 Signalling")],
    "NPM1":   [("REACTOME_TRANSPORT_OF_MATURE_TRANSCRIPT", "mRNA Transport")],
    "FLT3":   [("REACTOME_SIGNALLING_BY_FLT3", "FLT3 Signalling")],
    "CEBPA":  [("REACTOME_TRANSCRIPTIONAL_REGULATION", "Transcriptional Regulation")],
}

# ── Pathway clinical action map ────────────────────────────────────────────────
# Links pathway IDs to approved or investigational inhibitors
_PATHWAY_DRUGS: dict[str, list[str]] = {
    "KEGG_MAPK_SIGNALING_PATHWAY": ["Trametinib", "Cobimetinib", "Binimetinib", "Vemurafenib", "Dabrafenib"],
    "HALLMARK_PI3K_AKT_MTOR_SIGNALING": ["Alpelisib", "Idelalisib", "Everolimus", "Temsirolimus"],
    "KEGG_MTOR_SIGNALING_PATHWAY": ["Everolimus", "Temsirolimus", "Sirolimus"],
    "REACTOME_SIGNALLING_BY_EGFR": ["Osimertinib", "Erlotinib", "Gefitinib", "Afatinib"],
    "KEGG_ErbB_SIGNALING_PATHWAY": ["Trastuzumab", "Pertuzumab", "Lapatinib", "Neratinib"],
    "HALLMARK_P53_PATHWAY": ["Idasanutlin", "APR-246 (eprenetapopt)"],
    "KEGG_CELL_CYCLE": ["Palbociclib", "Ribociclib", "Abemaciclib"],
    "KEGG_WNT_SIGNALING_PATHWAY": ["LGK-974", "ETC-159"],
    "KEGG_HEDGEHOG_SIGNALING_PATHWAY": ["Vismodegib", "Sonidegib"],
    "REACTOME_SIGNALLING_BY_ALK": ["Alectinib", "Brigatinib", "Lorlatinib", "Crizotinib"],
    "REACTOME_SIGNALLING_BY_RET": ["Selpercatinib", "Pralsetinib"],
    "REACTOME_SIGNALLING_BY_ROS1": ["Crizotinib", "Entrectinib"],
    "REACTOME_SIGNALLING_BY_BCR_ABL1": ["Imatinib", "Dasatinib", "Nilotinib", "Ponatinib"],
    "REACTOME_SIGNALLING_BY_FLT3": ["Midostaurin", "Gilteritinib", "Quizartinib"],
    "REACTOME_HOMOLOGOUS_RECOMBINATION_REPAIR": ["Olaparib", "Niraparib", "Rucaparib", "Talazoparib"],
    "HALLMARK_APOPTOSIS": ["Venetoclax", "Navitoclax"],
    "REACTOME_EPIGENETICS": ["Azacitidine", "Decitabine", "Enasidenib", "Ivosidenib"],
    "REACTOME_IMMUNE_SYSTEM": ["Pembrolizumab", "Nivolumab", "Atezolizumab", "Ipilimumab"],
    "HALLMARK_IL6_JAK_STAT3_SIGNALING": ["Ruxolitinib", "Baricitinib", "Tofacitinib"],
    "KEGG_VEGF_SIGNALING_PATHWAY": ["Bevacizumab", "Sunitinib", "Sorafenib", "Axitinib"],
}


# ── Public API ─────────────────────────────────────────────────────────────────

def get_pathways_for_gene(gene: str) -> list[dict]:
    """Return pathway annotations for a single gene.

    Returns a list of dicts:
        {pathway_id, pathway_name, targeted_drugs}
    """
    entries = _GENE_PATHWAY_MAP.get(gene.upper(), [])
    result = []
    for pathway_id, pathway_name in entries:
        drugs = _PATHWAY_DRUGS.get(pathway_id, [])
        result.append({
            "pathway_id": pathway_id,
            "pathway_name": pathway_name,
            "targeted_drugs": drugs,
        })
    return result


def annotate_mutation_list(mutations: list[dict]) -> list[dict]:
    """Add pathway context to each mutation in a list.

    Adds a ``pathways`` key to each mutation dict with a list of
    (pathway_id, pathway_name) dicts.  Mutations whose gene is not in the
    curated map receive an empty list.
    """
    annotated = []
    for m in mutations:
        gene = (m.get("gene") or "").upper()
        pathways = get_pathways_for_gene(gene)
        annotated.append({**m, "pathways": pathways})
    return annotated


def get_pathway_summary(mutations: list[dict]) -> list[dict]:
    """Summarise which pathways are hit across a multi-mutation profile.

    Returns a list of pathway hit summaries sorted by number of genes hit
    (descending), useful for the "Pathway context" panel on the results page.

    Each item:
        {pathway_id, pathway_name, genes_hit, targeted_drugs}
    """
    pathway_hits: dict[str, dict] = {}

    for m in mutations:
        gene = (m.get("gene") or "").upper()
        for pathway_id, pathway_name in _GENE_PATHWAY_MAP.get(gene, []):
            if pathway_id not in pathway_hits:
                pathway_hits[pathway_id] = {
                    "pathway_id": pathway_id,
                    "pathway_name": pathway_name,
                    "genes_hit": [],
                    "targeted_drugs": _PATHWAY_DRUGS.get(pathway_id, []),
                }
            if gene not in pathway_hits[pathway_id]["genes_hit"]:
                pathway_hits[pathway_id]["genes_hit"].append(gene)

    return sorted(
        pathway_hits.values(),
        key=lambda x: len(x["genes_hit"]),
        reverse=True,
    )


async def fetch_kegg_pathways_for_gene(gene: str) -> list[dict]:
    """Query the KEGG REST API for pathways containing a gene (live call).

    Falls back to the static map if the API is unavailable.  Results are
    not cached here; the caller is responsible for caching (see services/cache.py).

    Returns same format as get_pathways_for_gene().
    """
    try:
        import httpx
        url = f"https://rest.kegg.jp/link/pathway/hsa:{gene}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return get_pathways_for_gene(gene)

            results = []
            for line in resp.text.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                pathway_kegg_id = parts[1].strip()
                # Fetch pathway name
                name_resp = await client.get(f"https://rest.kegg.jp/list/{pathway_kegg_id}")
                pathway_name = pathway_kegg_id
                if name_resp.status_code == 200 and name_resp.text:
                    name_line = name_resp.text.strip().split("\t")
                    if len(name_line) >= 2:
                        pathway_name = name_line[1]
                results.append({
                    "pathway_id": pathway_kegg_id,
                    "pathway_name": pathway_name,
                    "targeted_drugs": _PATHWAY_DRUGS.get(pathway_kegg_id, []),
                })
            return results if results else get_pathways_for_gene(gene)
    except Exception as exc:
        logger.warning("[pathway] KEGG API failed for %s: %s", gene, exc)
        return get_pathways_for_gene(gene)
