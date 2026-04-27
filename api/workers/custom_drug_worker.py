"""Custom drug discovery worker.

Generates the structured discovery brief asynchronously after a DrugRequest is created.
This persists job state so the frontend can poll without holding an HTTP request open.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from workers import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async code from sync task context, even if an event loop is already active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


async def _ensure_mutation_structure(
    target_gene: str,
    mutation_hgvs: list[str],
    submission_id: str | None,
    existing_path: str | None,
) -> str | None:
    if existing_path:
        return existing_path
    if not mutation_hgvs or not submission_id:
        return None

    try:
        from ai.services.alphafold import (
            get_uniprot_sequence,
            apply_mutation,
            fold_sequence,
            cif_to_pdb,
        )
        from services.storage import _get_s3
    except ModuleNotFoundError:
        logger.warning("[custom-drug] AlphaFold service package unavailable; continuing without mutation-specific structure")
        return None

    variant = mutation_hgvs[0]
    short_variant = variant.replace("p.", "") if variant else None
    if not short_variant:
        return None

    try:
        canonical = await get_uniprot_sequence(target_gene)
        mutated = apply_mutation(canonical, variant)
        cif_key = await fold_sequence(mutated, submission_id, target_gene)
        if not cif_key:
            return None

        s3 = _get_s3()
        cif_bytes = s3.get_object(Bucket="openoncology-vcf", Key=cif_key)["Body"].read()
        return cif_to_pdb(cif_bytes, submission_id, target_gene)
    except Exception as exc:
        logger.warning("[custom-drug] AlphaFold structure generation failed, continuing without folded structure: %s", exc)
        return None


def _brief_to_drug_spec(brief: dict) -> str:
    leads = brief.get("lead_candidates", [])
    return "\n".join(
        [
            f"Custom discovery request for target gene: {brief.get('target_gene')}",
            f"Cancer type: {brief.get('cancer_type')}",
            f"Reason: {brief.get('reason')}",
            "",
            "Mutation profile:",
            *[f"- {m}" for m in (brief.get("mutation_profile") or [])],
            "",
            "Lead candidates:",
            *[
                f"- {lead.get('drug_name') or 'Unknown'} ({lead.get('chembl_id') or 'N/A'}) phase={lead.get('max_phase')} score={lead.get('opentargets_score')}"
                for lead in leads[:10]
            ],
        ]
    )


@celery_app.task(
    name="workers.custom_drug_worker.build_custom_drug_brief",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def build_custom_drug_brief(self, drug_request_id: str):
    from workers._db_sync import get_sync_session
    from models.bid import DrugRequest, DiscoveryStatus
    from models.result import Result
    from models.submission import Submission
    from services.drug_discovery import build_custom_discovery_brief

    logger.info("[custom-drug] starting brief generation for request %s", drug_request_id)

    try:
        with get_sync_session() as db:
            req = db.get(DrugRequest, drug_request_id)
            if not req:
                logger.warning("[custom-drug] request %s not found", drug_request_id)
                return

            req.discovery_status = DiscoveryStatus.running
            req.discovery_started_at = datetime.utcnow()
            req.discovery_error = None
            db.flush()

            result = None
            submission = None
            if req.result_id:
                result = db.execute(
                    select(Result)
                    .options(selectinload(Result.repurposing_candidates))
                    .where(Result.id == req.result_id)
                ).scalar_one_or_none()
            if result:
                submission = db.execute(
                    select(Submission)
                    .options(selectinload(Submission.mutations))
                    .where(Submission.id == result.submission_id)
                ).scalar_one_or_none()

            target_gene = req.target_gene or (result.target_gene if result else None) or (
                submission.mutations[0].gene if submission and submission.mutations else None
            )
            if not target_gene:
                raise ValueError("No target gene found for custom discovery.")

            mutation_hgvs = [m.hgvs_notation for m in submission.mutations if m.hgvs_notation] if submission and submission.mutations else []
            existing_structure_path = None
            if submission and submission.mutations:
                for m in submission.mutations:
                    if (m.gene or "").upper() == (target_gene or "").upper() and m.alphafold_structure_path:
                        existing_structure_path = m.alphafold_structure_path
                        break

            structure_path = _run_async(
                _ensure_mutation_structure(
                    target_gene=target_gene,
                    mutation_hgvs=mutation_hgvs,
                    submission_id=submission.id if submission else None,
                    existing_path=existing_structure_path,
                )
            )

            if structure_path and submission and submission.mutations:
                for m in submission.mutations:
                    if (m.gene or "").upper() == (target_gene or "").upper() and not m.alphafold_structure_path:
                        m.alphafold_structure_path = structure_path
                        break
            repurposing_candidates = [
                {
                    "rank_score": c.rank_score,
                    "binding_score": c.binding_score,
                    "opentargets_score": c.opentargets_score,
                    "drug_name": c.drug_name,
                    "chembl_id": c.chembl_id,
                    "mechanism": c.mechanism,
                    "approval_status": c.approval_status,
                    "evidence_sources": c.evidence_sources or [],
                    "matched_terms": c.matched_terms or [],
                }
                for c in (result.repurposing_candidates if result and result.repurposing_candidates else [])
            ]
            cancer_type = submission.cancer_type if submission else "Unknown"

            brief = _run_async(
                build_custom_discovery_brief(
                    target_gene=target_gene,
                    cancer_type=cancer_type,
                    mutation_hgvs=mutation_hgvs,
                    repurposing_candidates=repurposing_candidates,
                    pre_folded_structure_path=structure_path,
                )
            )

            req.discovery_brief = brief
            req.drug_spec = _brief_to_drug_spec(brief)
            req.discovery_status = DiscoveryStatus.complete
            req.discovery_completed_at = datetime.utcnow()
            db.flush()

        logger.info("[custom-drug] completed brief generation for request %s", drug_request_id)
    except Exception as exc:
        logger.exception("[custom-drug] generation failed for request %s", drug_request_id)
        with get_sync_session() as db:
            req = db.get(__import__('models.bid', fromlist=['DrugRequest']).DrugRequest, drug_request_id)
            if req:
                req.discovery_status = __import__('models.bid', fromlist=['DiscoveryStatus']).DiscoveryStatus.failed
                req.discovery_error = str(exc)
                req.discovery_completed_at = datetime.utcnow()
                db.flush()
        raise self.retry(exc=exc)
