"""LLM-based plain-language result explainer.

Converts technical mutation analysis output into patient-friendly plain English
using OpenAI GPT-4o (or falls back to a deterministic template when no API key
is configured, so the pipeline never blocks).

Configuration
-------------
Set OPENAI_API_KEY in .env to enable AI-generated summaries.
Leave it empty to use the built-in template-based fallback (no cost, no AI).

The prompt is specifically designed to:
  - Use plain language a non-scientist can understand
  - Avoid instilling panic or false hope
  - Always recommend consulting a licensed oncologist
  - Stay compliant with medical device communication guidelines
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

    return f"""You are an AI assistant helping a cancer patient understand their genomic analysis results.
Write a clear, compassionate explanation in plain language that a person without a medical background can understand.
Do NOT use technical jargon without explaining it.
Always end by strongly recommending the patient discusses these results with a licensed oncologist before making any medical decision.

Here are the analysis results:

Cancer type submitted: {cancer_type}
Targetable mutation found: {"Yes" if has_target else "No"}
Primary gene of interest: {gene or "None identified"}
Mutations detected:
{mutation_lines}
{cosmic_note}
{drug_note}

Write a 3–5 paragraph explanation covering:
1. What the test found (in plain language)
2. What "targetable mutation" means and why it matters
3. The drug repurposing finding (what the drug does, what it might mean)
4. What the patient should do next
5. A reassuring closing that emphasises this is a tool to help, not a final diagnosis
"""


async def generate_plain_language_summary(
    gene: Optional[str],
    has_target: bool,
    cancer_type: str,
    mutations_summary: list[dict],
    top_drug: Optional[str] = None,
    cosmic_count: int = 0,
) -> str:
    """Generate a patient-friendly plain-language summary of the analysis result.

    Tries OpenAI GPT-4o first; falls back to a template string if unavailable.
    Always returns a non-empty string (never raises).
    """
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
                "max_tokens": 600,
                "temperature": 0.4,
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
            f"Your genomic analysis found a specific change (mutation) in a gene called {gene}. "
            f"This is known as a 'targetable mutation', which means there may be medicines or "
            f"treatments designed to specifically address this type of change in cancer cells.\n\n"
            f"{cosmic_sentence}\n\n"
            f"{drug_sentence}\n\n"
            f"While this result is promising, it is very important that you share these findings "
            f"with a licensed oncologist (cancer specialist doctor) before making any decisions "
            f"about your treatment. This analysis is a tool to help guide conversations — it is "
            f"not a medical diagnosis or a prescription."
        ).strip()
    else:
        return (
            f"Your genomic analysis for {cancer_type} did not find a mutation that current AI tools "
            f"can directly match to a targeted therapy. This does not mean treatment options are "
            f"unavailable — it means standard treatment pathways (general oncology) remain the "
            f"recommended next step.\n\n"
            f"Cancer treatment is highly individual. A licensed oncologist will consider your full "
            f"medical history, imaging, and pathology results alongside this genomic data to "
            f"provide you with a personalised treatment plan.\n\n"
            f"Please share these results with your doctor as soon as possible."
        )
