"""LLM-based plain-language result explainer.

DEPRECATION NOTICE — Patient Summary Path
------------------------------------------
``generate_plain_language_summary()`` is DEPRECATED for patient-facing output.

Use ``generate_patient_summary()`` from ``api.services.patient_summary``
instead.  That module is:
  - Template-only (zero hallucination risk)
  - Written at 6th-to-8th-grade reading level
  - Structured sections with calm, empathetic language
  - Explicitly gates de-novo/experimental content away from patients
  - Consistent disclaimers on every render

The LLM path in this module will be removed in a future version.  It is
retained ONLY as an internal fallback for the ``plain_language_summary``
field in the legacy API response envelope, and ONLY when an OpenAI key is
configured AND the caller explicitly opts in.

For the oncologist / technical report use::

    from api.services.oncologist_report import generate_oncologist_report

----------------------------------------------------------------------

This module provides:

1. ``generate_plain_language_summary()`` — [DEPRECATED] short narrative
   paragraph using GPT-4o when available, falling back to a template.
   Kept for backward compatibility with the API response envelope.

2. ``generate_research_report()`` — [DEPRECATED] legacy audit report.
   Prefer ``generate_oncologist_report()`` from oncologist_report.py
   which provides a fully structured professional report.

Configuration
-------------
Set OPENAI_API_KEY in .env to enable AI-generated summaries.
Leave it empty (default) to use the built-in template-based fallback.

Safety notes
------------
- ``max_tokens`` is capped at 400 for the patient path.
- Temperature is set to 0.3 to minimise hallucination.
- Even so, LLM output for patients carries hallucination risk.
  Prefer the template path (patient_summary.py) for all patient output.
- All outputs must be reviewed by a qualified oncologist before acting.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _build_prompt(
    gene: Optional[str],
    has_target: bool,
    cancer_type: str,
    mutations_summary: list[dict],
    top_drug: Optional[str],
    cosmic_count: int,
) -> str:
    mutation_lines = "\n".join(
        f"  - {m.get('gene', '?')} {m.get('hgvs_notation', '')}: "
        f"classification={m.get('classification', 'unknown')}, "
        f"alphamissense_score={m.get('alphamissense_score', 'N/A')}"
        for m in mutations_summary[:5]
    )
    cosmic_note = (
        f"This mutation has been observed in {cosmic_count} tumour samples in the COSMIC database."
        if cosmic_count > 0
        else ""
    )
    drug_note = (
        f"The AI has identified {top_drug} as the best-matching existing drug for this mutation."
        if top_drug
        else "No closely matching existing drug was found in the repurposing analysis."
    )

    return f"""You are an AI assistant helping a cancer patient understand their genomic test results.
Write a SHORT, simple explanation (maximum 250 words total).
Use plain language — no jargon. Write at an 8th-grade reading level.
Do NOT predict whether a treatment will work. Do NOT say a drug "will" help.
Do NOT discuss experimental or custom molecules — only approved or late-stage drugs.
Always end with this exact sentence on its own line:
"This report is not medical advice. Please discuss these results with your oncologist."

Analysis data:
Cancer type: {cancer_type}
Targetable mutation found: {"Yes" if has_target else "No"}
Gene: {gene or "None identified"}
Mutations:
{mutation_lines}
{cosmic_note}
{drug_note}

Write THREE short sections only:
Section 1 (2-3 sentences): What we found — explain the mutation in plain words.
Section 2 (2-3 sentences): What this might mean — mention the drug only as something the doctor may discuss.
Section 3 (1-2 sentences): What to do next — see oncologist, do not self-medicate.

End with the required disclaimer sentence.
"""


async def generate_plain_language_summary(
    gene: Optional[str],
    has_target: bool,
    cancer_type: str,
    mutations_summary: list[dict],
    top_drug: Optional[str] = None,
    cosmic_count: int = 0,
) -> str:
    """[DEPRECATED] Generate a plain-language summary via LLM or template fallback.

    .. deprecated::
        Use ``generate_patient_summary()`` from ``api.services.patient_summary``
        for all patient-facing output.  That module is template-only (no LLM),
        uses simpler language, and contains no hallucination risk.

        This function is retained only for the legacy ``plain_language_summary``
        field in the API response envelope.  It will be removed in a future version.

    Tries OpenAI GPT-4o first; falls back to a template string if unavailable.
    Always returns a non-empty string (never raises).
    """
    import warnings
    warnings.warn(
        "generate_plain_language_summary() is deprecated. "
        "Use generate_patient_summary() from api.services.patient_summary instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from config import settings

    openai_key = getattr(settings, "openai_api_key", "")

    if openai_key:
        try:
            return await _openai_summary(
                openai_key, gene, has_target, cancer_type,
                mutations_summary, top_drug, cosmic_count,
            )
        except Exception as exc:
            logger.warning("[llm] OpenAI summary failed, using template fallback: %s", exc)

    return _template_summary(gene, has_target, cancer_type, top_drug, cosmic_count)


async def _openai_summary(
    api_key: str,
    gene: Optional[str],
    has_target: bool,
    cancer_type: str,
    mutations_summary: list[dict],
    top_drug: Optional[str],
    cosmic_count: int,
) -> str:
    import httpx

    prompt = _build_prompt(gene, has_target, cancer_type, mutations_summary, top_drug, cosmic_count)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,   # keep output short and simple
                "temperature": 0.3,  # lower temp = less hallucination risk
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def _template_summary(
    gene: Optional[str],
    has_target: bool,
    cancer_type: str,
    top_drug: Optional[str],
    cosmic_count: int,
) -> str:
    """Deterministic fallback summary template — no external calls needed."""
    if has_target and gene:
        drug_sentence = (
            f"Our AI identified {top_drug} as a possible existing medicine that already targets "
            f"this gene and may be repurposed for your case. This could potentially reduce "
            f"the cost and time normally required to develop brand-new treatments."
            if top_drug
            else "Our AI is searching for existing medicines that could be repurposed for your mutation."
        )
        cosmic_sentence = (
            f"This type of change in {gene} has been recorded in {cosmic_count:,} tumour samples "
            f"in the COSMIC database — the world's largest catalogue of cancer mutations — "
            f"which means it is a well-studied alteration."
            if cosmic_count > 0
            else ""
        )
        return (
            f"Your DNA test found a change in a gene called {gene}. "
            f"This is called a 'targetable mutation' — it means there may be medicines "
            f"that could target cancer cells with this specific change.\n\n"
            f"{cosmic_sentence}\n\n"
            f"{drug_sentence}\n\n"
            f"This report is not medical advice. "
            f"Please discuss these results with your oncologist."
        ).strip()
    else:
        return (
            "Your DNA test did not find a mutation that matches a targeted therapy "
            "in our research database. This does not mean there are no treatment options — "
            "your oncologist will consider many factors beyond this one test.\n\n"
            "Please share these results with your doctor as soon as possible.\n\n"
            "This report is not medical advice. "
            "Please discuss these results with your oncologist."
        )


def generate_research_report(
    ranked_candidates: list[dict],
    mutation_summary: list[dict],
    cancer_type: str,
    withdrawn_warnings: Optional[list[dict]] = None,
) -> dict:
    """[DEPRECATED] Assemble a structured research transparency report.

    .. deprecated::
        Use ``generate_oncologist_report()`` from ``api.services.oncologist_report``
        instead.  That function produces a fully structured, ESMO-inspired report
        with an executive summary, sample QC section, per-drug rationale bullets,
        ADME/toxicity notes, experimental candidate section with mandatory caveats,
        and a complete evidence audit trail.

    This legacy function is retained for backward compatibility only.
    Includes:
      - Per-drug evidence audit trail (source, raw_score, effective_weight)
      - Per-drug plain-language ranking rationale
      - Evidence completeness and confidence level for each candidate
      - System limitations and withdrawn-drug warnings
            - Missing evidence sources per drug
            - Interpretation guide for audit trail columns
    """

    from api.ai.ranking import get_system_limitations

    candidate_reports = []
    for i, c in enumerate(ranked_candidates[:10]):  # top-10 only for report brevity
        # Build a human-readable rationale for this drug's rank
        rationale_parts = []
        oncokb = c.get("oncokb_level")
        if oncokb and oncokb.startswith("LEVEL_R"):
            rationale_parts.append(
                f"⚠️ RESISTANCE: OncoKB designates this drug as {oncokb} for this variant — "
                "it should not be used; score is hard-capped."
            )
        elif oncokb == "LEVEL_1":
            rationale_parts.append("OncoKB Level 1 evidence: FDA-approved for this variant/tumour type.")
        elif oncokb == "LEVEL_2":
            rationale_parts.append("OncoKB Level 2 evidence: standard-of-care or strong clinical data.")
        elif oncokb in ("LEVEL_3A", "LEVEL_3B"):
            rationale_parts.append(f"OncoKB {oncokb} evidence: compelling pre-clinical or early clinical data.")
        elif oncokb == "LEVEL_4":
            rationale_parts.append("OncoKB Level 4: biological rationale only; no clinical data for this variant.")
        else:
            rationale_parts.append("No OncoKB evidence found for this drug-variant pair.")

        binding = c.get("binding_score")
        if binding is not None:
            if binding >= 0.7:
                rationale_parts.append(f"Strong predicted binding affinity (DiffDock score={binding:.2f}).")
            elif binding >= 0.4:
                rationale_parts.append(f"Moderate predicted binding affinity (DiffDock score={binding:.2f}).")
            else:
                rationale_parts.append(f"Low predicted binding affinity (DiffDock score={binding:.2f}).")
        else:
            rationale_parts.append("Binding score absent (DiffDock not run in default demo).")

        missing = c.get("missing_sources", [])
        if missing:
            rationale_parts.append(
                f"Missing evidence from {len(missing)} source(s): {', '.join(missing)}. "
                "Confidence interval is wider as a result."
            )

        ec = c.get("evidence_completeness")
        if ec is not None:
            rationale_parts.append(
                f"Evidence completeness: {ec:.0%} of sources provided data for this drug."
            )

        candidate_reports.append({
            "rank": i + 1,
            "drug_name": c.get("drug_name"),
            "chembl_id": c.get("chembl_id"),
            "oncokb_level": oncokb,
            "rank_score": c.get("rank_score"),
            "rank_score_ci_low": c.get("rank_score_ci_low"),
            "rank_score_ci_high": c.get("rank_score_ci_high"),
            "confidence_level": c.get("confidence_level"),
            "evidence_completeness": ec,
            "missing_sources": missing,
            "evidence_audit_trail": c.get("evidence_audit_trail", []),
            "immunotherapy_context": c.get("immunotherapy_context"),
            "ranking_rationale": " ".join(rationale_parts),
            "_injected": (
                c.get("_injected_from_oncokb_table")
                or c.get("_injected_from_oncokb_api")
                or c.get("_injected_from_ici_context")
            ),
        })

    interpretation_guide = {
        "rank_score": (
            "Weighted composite score in [0, 1]. Higher = stronger combined evidence. "
            "NOT a probability of clinical response."
        ),
        "rank_score_ci_low / ci_high": (
            "95% confidence interval half-width based on missing source uncertainty. "
            "Wide interval = fewer evidence sources available."
        ),
        "confidence_level": (
            "HIGH (≥0.80), MEDIUM (≥0.50), or LOW (<0.50) based on the rank_score value."
        ),
        "evidence_completeness": (
            "Fraction of the 6 evidence sources (DiffDock, OpenTargets, OncoKB, "
            "AlphaMissense, ClinicalPhase, CIViC) that provided data for this drug."
        ),
        "missing_sources": (
            "Evidence channels with no data for this drug. "
            "Binding score is missing in the default demo (DiffDock requires GPU pipeline)."
        ),
        "oncokb_level": (
            "OncoKB evidence tier: LEVEL_1=FDA-approved, LEVEL_2=standard-of-care, "
            "LEVEL_3A/B=investigational, LEVEL_4=biological rationale, "
            "LEVEL_R1/R2=RESISTANCE (drug should NOT be used)."
        ),
        "_injected": (
            "True if this drug was added by the OncoKB/CIViC evidence layer (not from "
            "OpenTargets association data). Injected drugs have higher clinical relevance "
            "but may have lower OpenTargets association scores."
        ),
    }

    return {
        "cancer_type": cancer_type,
        "mutations_analysed": len(mutation_summary),
        "candidates_evaluated": len(ranked_candidates),
        "top_candidates": candidate_reports,
        "withdrawn_drug_warnings": withdrawn_warnings or [],
        "system_limitations": get_system_limitations(),
        "interpretation_guide": interpretation_guide,
    }

