"""
AI Worker — AlphaMissense + OncoKB + COSMIC + cBioPortal + AlphaFold + DiffDock pipeline.

Steps:
  1. Load mutations from DB
  2. Run AlphaMissense to classify each mutation (lookup from pre-computed scores DB)
  3. Query OncoKB for actionability level
  4. COSMIC + cBioPortal enrichment for the top gene (population frequency context)
  5. For targetable mutations:
       a. Derive mutated protein sequence and submit to AlphaFold Server
       b. Resolve Ensembl gene ID via OpenTargets
       c. Fetch associated drugs from OpenTargets GraphQL
       d. Enrich each drug with ChEMBL properties (SMILES, phase, approval)
       e. Score protein-ligand binding with DiffDock using the mutated structure
       f. Compute composite rank_score via ranking.py
  6. Generate plain-language LLM summary for the patient
  7. Store results + repurposing candidates in DB
  8. Queue notify worker
"""
import logging
import asyncio
import sys
from pathlib import Path

# Allow importing from the ai/ package at repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workers import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.ai_worker.run_ai_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def run_ai_analysis(
    self,
    submission_id: str,
    patient_id: str,
    vcf_s3_key: str,
    cancer_type: str,
):
    from workers._db_sync import get_sync_session
    from models.submission import Submission, SubmissionStatus
    from models.mutation import Mutation, MutationClassification, OncoKBLevel
    from models.result import Result
    from models.repurposing import RepurposingCandidate

    logger.info(f"[ai] Starting AI analysis for submission {submission_id}")

    try:
        with get_sync_session() as db:
            from sqlalchemy import select
            mutations = db.execute(
                select(Mutation).where(Mutation.submission_id == submission_id)
            ).scalars().all()

            if not mutations:
                logger.warning(f"[ai] No mutations found for {submission_id}")
                return

            # Step 1: AlphaMissense classification
            for mutation in mutations:
                score = _run_alphamissense(mutation.gene, mutation.hgvs_notation)
                if score is not None:
                    mutation.alphamissense_score = score
                    from ai.alphamissense.classify import classifier
                    label = classifier.classify(score)
                    if label == "likely_pathogenic":
                        mutation.classification = MutationClassification.pathogenic
                    elif label == "likely_benign":
                        mutation.classification = MutationClassification.likely_benign
                    else:
                        mutation.classification = MutationClassification.uncertain

            # Step 2: OncoKB actionability
            targetable_mutations = []
            for mutation in mutations:
                oncokb_data = _query_oncokb(mutation.gene, mutation.hgvs_notation)
                if oncokb_data:
                    mutation.oncokb_level = oncokb_data.get("level", OncoKBLevel.unknown)
                    if mutation.oncokb_level in (
                        OncoKBLevel.level_1, OncoKBLevel.level_2, OncoKBLevel.level_3a
                    ):
                        mutation.is_targetable = True
                        targetable_mutations.append(mutation)

            db.commit()

        # Step 3: COSMIC + cBioPortal enrichment for the top mutated gene
        cosmic_sample_count = 0
        cbioportal_data: list[dict] = []

        # Determine top gene from all mutations (not just targetable) for enrichment
        enrich_gene = targetable_mutations[0].gene if targetable_mutations else (
            mutations[0].gene if mutations else None
        )

        if enrich_gene:
            try:
                cosmic_sample_count, cbioportal_data = asyncio.run(_enrich_from_databases(
                    enrich_gene, cancer_type
                ))
            except Exception as enrich_exc:
                logger.warning("[ai] Database enrichment failed for %s: %s", enrich_gene, enrich_exc)

        # Step 4: Drug repurposing for targetable mutations
        repurposing_candidates = []
        target_gene = None
        alphafold_pdb_path: str | None = None

        if targetable_mutations:
            top_mutation = targetable_mutations[0]
            target_gene = top_mutation.gene

            # Derive protein variant for AlphaFold (e.g. "L858R" from HGVS p.Leu858Arg)
            top_variant = _hgvs_to_short(top_mutation.hgvs_notation) if top_mutation.hgvs_notation else None

            # Query OpenTargets — passes variant to AlphaFold → DiffDock pipeline
            drugs, alphafold_pdb_path = _query_opentargets(
                target_gene, protein_variant=top_variant, submission_id=submission_id
            )

            # Score each drug using the composite ranking algorithm
            from api.ai.ranking import rank_candidates

            for drug in drugs[:10]:  # Process top 10 candidates
                drug["alphamissense_score"] = (
                    top_mutation.alphamissense_score if hasattr(top_mutation, "alphamissense_score") else None
                )
                drug["oncokb_level"] = (
                    top_mutation.oncokb_level.value if hasattr(top_mutation, "oncokb_level") else None
                )

            ranked = rank_candidates(drugs[:10])

            repurposing_candidates = [
                {
                    "drug_name": d.get("drug_name"),
                    "chembl_id": d.get("chembl_id"),
                    "binding_score": d.get("binding_score"),
                    "opentargets_score": d.get("opentargets_score"),
                    "rank_score": d.get("rank_score", 0.0),
                    "approval_status": "Approved" if d.get("is_approved") else f"Phase {d.get('max_phase', '?')}",
                    "mechanism": d.get("mechanism"),
                }
                for d in ranked
            ]

        # Step 5: Build result with LLM plain-language summary
        with get_sync_session() as db:
            has_target = len(targetable_mutations) > 0
            summary = _generate_summary(mutations, targetable_mutations, repurposing_candidates)

            # Generate patient-friendly plain-language summary (LLM or template fallback)
            top_drug = (
                repurposing_candidates[0].get("drug_name") if repurposing_candidates else None
            )
            mutations_for_llm = [
                {
                    "gene": m.gene,
                    "hgvs_notation": m.hgvs_notation,
                    "classification": m.classification.value if m.classification else "unknown",
                    "alphamissense_score": getattr(m, "alphamissense_score", None),
                }
                for m in mutations[:5]
            ]
            try:
                plain_summary = asyncio.run(_call_llm_explainer(
                    gene=enrich_gene,
                    has_target=has_target,
                    cancer_type=cancer_type,
                    mutations_summary=mutations_for_llm,
                    top_drug=top_drug,
                    cosmic_count=cosmic_sample_count,
                ))
            except Exception as llm_exc:
                logger.warning("[ai] LLM explainer failed: %s", llm_exc)
                plain_summary = None

            result = Result(
                submission_id=submission_id,
                has_targetable_mutation=has_target,
                target_gene=target_gene,
                summary_text=summary,
                plain_language_summary=plain_summary,
                cbioportal_data=cbioportal_data or None,
                cosmic_sample_count=str(cosmic_sample_count) if cosmic_sample_count else None,
            )
            db.add(result)
            db.flush()

            if alphafold_pdb_path and targetable_mutations:
                top_mut = db.get(Mutation, targetable_mutations[0].id)
                if top_mut:
                    top_mut.alphafold_structure_path = alphafold_pdb_path

            for c in repurposing_candidates[:5]:
                candidate = RepurposingCandidate(
                    result_id=result.id,
                    **c,
                )
                db.add(candidate)

            submission = db.get(Submission, submission_id)
            submission.status = SubmissionStatus.complete
            from datetime import datetime
            submission.completed_at = datetime.utcnow()
            db.commit()

        # Step 6: Notify patient
        from workers.notify_worker import notify_results_ready
        notify_results_ready.apply_async(
            args=[submission_id, patient_id],
            queue="notify",
        )

        logger.info(f"[ai] Analysis complete for {submission_id}")

    except Exception as exc:
        logger.error(f"[ai] Analysis failed for {submission_id}: {exc}")
        raise self.retry(exc=exc)


def _run_alphamissense(gene: str, hgvs: str | None) -> float | None:
    """Look up AlphaMissense pathogenicity score from pre-computed scores DB.

    Converts HGVS protein notation (p.Arg175His → R175H) before lookup.
    Falls back to None if the scores DB is not available.
    """
    from ai.alphamissense.classify import classifier

    if hgvs is None:
        return None

    # Strip "p." prefix and convert 3-letter AA codes to 1-letter
    protein_variant = _hgvs_to_short(hgvs)
    if protein_variant is None:
        return None

    # We need the UniProt ID — derive from gene name via a simple mapping.
    # In production this should be a full gene→UniProt lookup table.
    uniprot_id = _gene_to_uniprot(gene)
    if uniprot_id is None:
        return None

    score = classifier.score(uniprot_id, protein_variant)
    if score is not None:
        logger.info("[alphamissense] %s %s → %.3f", gene, protein_variant, score)
    return score


def _hgvs_to_short(hgvs_p: str) -> str | None:
    """Convert p.Arg175His → R175H, or pass through if already short form."""
    import re

    _AA3 = {
        "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
        "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
        "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
        "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
        "Ter": "*",
    }
    variant = hgvs_p.lstrip("p.")
    # Already short form e.g. "R175H"
    if re.match(r"^[A-Z\*]\d+[A-Z\*]$", variant):
        return variant
    # Three-letter form e.g. "Arg175His"
    m = re.match(r"^([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|\*)$", variant)
    if m:
        ref = _AA3.get(m.group(1))
        alt = _AA3.get(m.group(3), m.group(3))
        if ref:
            return f"{ref}{m.group(2)}{alt}"
    return None


def _gene_to_uniprot(gene: str) -> str | None:
    """Return UniProt accession for common cancer genes.

    This is a curated table for the most frequently targetable oncogenes.
    A production system would query UniProt REST API or use a full mapping file.
    """
    _MAP = {
        "TP53": "P04637", "KRAS": "P01116", "BRAF": "P15056",
        "EGFR": "P00533", "PIK3CA": "P42336", "PTEN": "P60484",
        "APC": "P25054",  "BRCA1": "P38398", "BRCA2": "P51587",
        "CDKN2A": "P42771", "RB1": "P06400", "MYC": "P01106",
        "ERBB2": "P04626", "VHL": "P40337", "MLH1": "P40692",
        "MTOR": "P42345", "IDH1": "O75874", "IDH2": "P48735",
        "FLT3": "P36888", "KIT": "P10721", "ABL1": "P00519",
        "BCR": "P11274", "ALK": "Q9UM73", "RET": "P07949",
        "MET": "P08581", "NRAS": "P01111", "HRAS": "P01112",
        "JAK2": "O60674", "NPM1": "P06748", "DNMT3A": "Q9Y6K1",
    }
    return _MAP.get(gene.upper())


def _query_oncokb(gene: str, hgvs: str | None) -> dict | None:
    """
    Query OncoKB API for clinical actionability level.
    Requires a free academic API token from oncokb.org.
    """
    import httpx
    from config import settings

    if not settings.oncokb_api_token:
        logger.warning("[oncokb] No API token configured — skipping")
        return None

    try:
        resp = httpx.get(
            f"https://www.oncokb.org/api/v1/annotate/mutations/byProteinChange",
            params={"hugoSymbol": gene, "alteration": hgvs or ""},
            headers={"Authorization": f"Bearer {settings.oncokb_api_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"level": data.get("highestSensitiveLevel", "unknown")}
    except Exception as exc:
        logger.warning(f"[oncokb] Query failed: {exc}")
        return None


def _query_opentargets(
    gene: str,
    protein_variant: str | None = None,
    submission_id: str = "unknown",
) -> tuple[list[dict], str | None]:
    """Query OpenTargets for drugs + ChEMBL SMILES, then run DiffDock scoring.

    When protein_variant is provided and AlphaFold Server is reachable, the
    mutated protein structure is folded first and passed to DiffDock for
    mutation-specific binding scores.

    Returns (drugs, alphafold_pdb_path) — pdb_path is None if AlphaFold failed.
    """
    from api.services.opentargets import get_target_id, get_drugs_for_target
    from api.services.chembl import get_molecule
    from ai.diffdock.score import score_binding

    async def _fetch() -> tuple[list[dict], str | None]:
        ensg_id = await get_target_id(gene)
        if not ensg_id:
            logger.warning("[opentargets] No Ensembl ID for gene %s", gene)
            return []

        drugs = await get_drugs_for_target(ensg_id, max_drugs=20)
        logger.info("[opentargets] %d drugs found for %s", len(drugs), gene)

        # ── AlphaFold: sequence → mutated structure ──────────────────────────
        # 1. get canonical protein sequence by gene name (UniProt REST search)
        # 2. apply this patient's specific mutation
        # 3. submit to AlphaFold Server, poll, download .cif → MinIO
        # 4. convert .cif → .pdb for DiffDock
        # All steps fall back gracefully; DiffDock uses EBI wild-type if any fail.
        pre_folded_pdb_key = None
        uniprot_id = _gene_to_uniprot(gene)
        if protein_variant:
            try:
                from ai.services.alphafold import (
                    get_uniprot_sequence,
                    apply_mutation,
                    fold_sequence,
                    cif_to_pdb,
                )
                canonical_seq = await get_uniprot_sequence(gene)
                mutated_seq = apply_mutation(canonical_seq, protein_variant)
                cif_path = await fold_sequence(mutated_seq, submission_id, gene)
                if cif_path:
                    from services.storage import _get_s3
                    s3 = _get_s3()
                    cif_bytes = s3.get_object(
                        Bucket="openoncology-vcf", Key=cif_path
                    )["Body"].read()
                    pre_folded_pdb_key = cif_to_pdb(cif_bytes, submission_id, gene)
                    if pre_folded_pdb_key:
                        logger.info("[alphafold] PDB ready for DiffDock: %s", pre_folded_pdb_key)
                    else:
                        logger.warning("[alphafold] CIF→PDB failed — DiffDock using EBI structure")
                else:
                    logger.info("[alphafold] Server unavailable — DiffDock will use EBI structure")
            except Exception as af_exc:
                logger.warning("[alphafold] Fold pipeline failed: %s", af_exc)

        # Enrich with ChEMBL SMILES + compute DiffDock binding scores
        for drug in drugs:
            chembl_id = drug.get("chembl_id")
            if not chembl_id:
                continue
            mol = await get_molecule(chembl_id)
            if mol:
                drug["smiles"] = mol.get("smiles")
                drug["max_phase"] = mol.get("max_phase") or drug.get("max_phase", 0)
                drug["is_approved"] = mol.get("is_approved", False)
                drug["ro5_pass"] = mol.get("ro5_pass", True)
            if drug.get("smiles") and uniprot_id:
                drug["binding_score"] = score_binding(
                    uniprot_id, drug["smiles"], chembl_id,
                    pre_folded_cif=pre_folded_pdb_key,
                )
        return drugs, pre_folded_pdb_key

    drugs, pdb_path = asyncio.run(_fetch())
    return drugs, pdb_path


def _run_diffdock(chembl_id: str | None, gene: str, hgvs: str | None) -> float | None:
    """DiffDock is now called inside _query_opentargets per drug. This stub is kept
    for backward compatibility but is no longer called directly."""
    return None


def _generate_summary(mutations, targetable, repurposing) -> str:
    """Generate a technical summary for oncologist review."""
    total = len(mutations)
    n_target = len(targetable)

    if n_target == 0:
        return (
            f"We analyzed your DNA sample and found {total} genetic variation(s). "
            "None of these mutations currently have known targeted treatment options. "
            "This does not mean treatment is unavailable — your oncologist can advise on other options."
        )

    drug_names = [r["drug_name"] for r in repurposing[:3] if r.get("drug_name")]
    drug_str = ", ".join(drug_names) if drug_names else "currently being analyzed"

    return (
        f"We found {n_target} targetable mutation(s) in genes: "
        f"{', '.join(m.gene for m in targetable)}. "
        f"These mutations may be treatable with existing or repurposed drugs. "
        f"Top candidate drugs: {drug_str}. "
        "Please review this report with a qualified oncologist before making any treatment decisions."
    )


async def _enrich_from_databases(gene: str, cancer_type: str) -> tuple[int, list[dict]]:
    """Async helper: call COSMIC + cBioPortal in parallel for *gene*."""
    from services.cosmic import get_cosmic_mutations
    from services.cbioportal import get_gene_panel_data
    import asyncio

    cosmic_task = asyncio.create_task(get_cosmic_mutations(gene, cancer_type))
    cbioportal_task = asyncio.create_task(get_gene_panel_data(gene))

    cosmic_records, cbioportal_data = await asyncio.gather(cosmic_task, cbioportal_task)

    cosmic_count = sum(r.get("sample_count", 0) for r in cosmic_records)
    logger.info("[enrich] COSMIC: %d samples, cBioPortal: %d studies for %s",
                cosmic_count, len(cbioportal_data), gene)
    return cosmic_count, cbioportal_data


async def _call_llm_explainer(
    gene, has_target, cancer_type, mutations_summary, top_drug, cosmic_count
) -> str:
    """Async helper: call the LLM explainer service."""
    from services.llm_explainer import generate_plain_language_summary
    return await generate_plain_language_summary(
        gene=gene,
        has_target=has_target,
        cancer_type=cancer_type,
        mutations_summary=mutations_summary,
        top_drug=top_drug,
        cosmic_count=cosmic_count,
    )
