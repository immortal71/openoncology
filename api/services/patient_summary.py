"""Patient-facing plain-language summary generator.

Produces a short, warm, human-readable letter for cancer patients to read
before meeting their oncologist.  Written at a 6th-to-8th-grade reading level.

Design principles
-----------------
- Template-driven only. No LLM generation in the patient path — hallucination
  risk is unacceptable when a person is reading about their own cancer.
- Maximum ~250 words of body text (roughly one printed page).
- De-novo / experimental compounds are NEVER shown in the patient letter.
  They appear only in the separate oncologist_report.py output.
- Resistance-flagged and withdrawn drugs are never shown as recommendations.
- No medical jargon: no "repurposing", "de-novo", "audit trail", "VAF",
  "HGVS", "LEVEL_R1", "OncoKB", "AlphaMissense", etc.
- Every drug mention is framed as "worth asking your doctor about" —
  never "this drug will help you".
- Warnings are presented calmly — not as alarming "red flags".

Output format
-------------
Returns a ``PatientSummary`` dataclass with:
  - ``plain_text``       – printable plain-text letter (UTF-8)
  - ``sections``         – structured dict for UI rendering
  - ``has_denovo``       – True when de-novo compounds exist (for oncologist
                           report only; not exposed in patient letter)
  - ``top_repurposing``  – up to 3 approved/late-stage drug candidates
  - ``top_denovo``       – de-novo candidates (oncologist report only)
  - ``warnings``         – list of calm plain-language warning strings
  - ``disclaimer``       – the mandatory disclaimer string
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "This report is NOT medical advice.\n\n"
    "It was made by a computer program that has not been approved by the FDA "
    "or any health authority. No doctor has reviewed it.\n\n"
    "Please bring this to your next appointment and ask your cancer doctor "
    "what it means for you. Do not start, stop, or change any treatment "
    "based on this report alone."
)

# NOTE: De-novo / experimental compound details are intentionally kept OUT of
# the patient letter. They are included only in the oncologist_report.py output.
DENOVO_EXTRA_WARNING = (
    "Your test results suggest there may be early-stage research ideas that "
    "could be explored further. Your doctor has access to a separate technical "
    "report that describes these in detail. Please ask your oncologist if they "
    "would like to review that report."
)

_ONCOKB_PATIENT_LABELS = {
    "LEVEL_1": "already approved by doctors for this type of DNA change",
    "LEVEL_2": "used as a standard cancer treatment in some medical guidelines",
    "LEVEL_3A": "currently being studied in clinical trials for similar cases",
    "LEVEL_3B": "has early research support for similar DNA changes",
    "LEVEL_4": "has a scientific reason to be explored (very early research stage)",
    "LEVEL_R1": None,   # resistance — never shown to patient
    "LEVEL_R2": None,   # resistance — never shown to patient
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class PatientSummary:
    """Structured patient-facing summary."""

    # Key boolean flags
    targetable_mutation_found: bool
    has_denovo: bool

    # Core sections
    what_we_found: str
    top_repurposing: list[dict]   # each: {name, why, oncokb_label, is_approved}
    top_denovo: list[dict]        # each: {name, why} — oncologist report only, not in patient letter
    warnings: list[str]           # calm warnings to tell the doctor (renamed from red_flags)
    next_steps: str
    disclaimer: str = field(default=DISCLAIMER)
    denovo_extra_warning: Optional[str] = None

    # Plain-text render
    plain_text: str = field(default="", init=False)
    sections: dict = field(default_factory=dict, init=False)

    # Backward-compat alias so existing callers using .red_flags still work
    @property
    def red_flags(self) -> list[str]:
        return self.warnings

    def __post_init__(self) -> None:
        self.plain_text = _render_plain_text(self)
        self.sections = _render_sections(self)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_patient_summary(
    ranked_candidates: list[dict],
    mutation_summary: list[dict],
    cancer_type: str,
    gene: Optional[str] = None,
    withdrawn_warnings: Optional[list[dict]] = None,
) -> PatientSummary:
    """Build a patient-facing summary from ranked drug candidates.

    Parameters
    ----------
    ranked_candidates:
        Output of ``rank_candidates()`` — list of dicts, highest score first.
    mutation_summary:
        List of mutation dicts from the analysis pipeline.
    cancer_type:
        Human-readable cancer type string (e.g. ``"Non-small cell lung cancer"``).
    gene:
        Primary gene of interest (e.g. ``"EGFR"``), optional.
    withdrawn_warnings:
        Output of ``check_withdrawn_status()`` — list of warning dicts.
    """
    withdrawn_names: set[str] = set()
    if withdrawn_warnings:
        for w in withdrawn_warnings:
            name = w.get("drug_name") or w.get("name") or ""
            if name:
                withdrawn_names.add(name.lower())

    # Split candidates into approved-drug repurposing vs de-novo
    repurposing: list[dict] = []
    denovo: list[dict] = []

    for c in ranked_candidates:
        # Skip resistance-flagged drugs entirely from the patient view
        oncokb = c.get("oncokb_level", "")
        if oncokb in ("LEVEL_R1", "LEVEL_R2"):
            continue

        # Skip withdrawn drugs from positive recommendations
        drug_name = c.get("drug_name", "")
        if drug_name.lower() in withdrawn_names:
            continue

        if _is_denovo(c):
            denovo.append(c)
        else:
            repurposing.append(c)

    top_repurposing = [_format_repurposing_entry(c) for c in repurposing[:3]]
    top_denovo = [_format_denovo_entry(c) for c in denovo[:2]]  # max 2 — oncologist report only

    targetable = bool(top_repurposing or top_denovo)

    what_we_found = _build_what_we_found(
        gene=gene,
        cancer_type=cancer_type,
        targetable=targetable,
        mutation_summary=mutation_summary,
    )

    warnings = _build_warnings(
        ranked_candidates=ranked_candidates,
        withdrawn_names=withdrawn_names,
        has_denovo=bool(top_denovo),
    )

    next_steps = _build_next_steps(targetable=targetable, gene=gene)

    return PatientSummary(
        targetable_mutation_found=targetable,
        has_denovo=bool(top_denovo),
        what_we_found=what_we_found,
        top_repurposing=top_repurposing,
        top_denovo=top_denovo,
        warnings=warnings,
        next_steps=next_steps,
        # Only show denovo_extra_warning if there are no approved repurposing candidates
        denovo_extra_warning=DENOVO_EXTRA_WARNING if (top_denovo and not top_repurposing) else None,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_denovo(candidate: dict) -> bool:
    """Return True if this candidate is a novel / de-novo molecule."""
    if candidate.get("is_denovo"):
        return True
    # Heuristic: no ChEMBL ID and max_phase < 1 → treat as experimental
    if not candidate.get("chembl_id") and not candidate.get("pubchem_cid"):
        phase = candidate.get("max_phase", -1)
        if phase is None or phase < 1:
            return True
    return False


def _format_repurposing_entry(c: dict) -> dict:
    drug_name = c.get("drug_name") or c.get("name") or "Unknown medicine"
    oncokb = c.get("oncokb_level")
    label = _ONCOKB_PATIENT_LABELS.get(oncokb) if oncokb else None

    # Build a single, short "why" sentence in plain everyday language
    if label:
        why = f"This medicine is {label}."
    else:
        phase = c.get("max_phase")
        if phase and phase >= 3:
            why = "This medicine is in advanced studies for cancers with similar DNA changes."
        elif phase and phase >= 1:
            why = "This medicine is being tested in research studies."
        else:
            why = "Research suggests this medicine may work on the DNA change found in your test."

    is_approved = (
        (c.get("max_phase") or 0) >= 4
        or oncokb in ("LEVEL_1", "LEVEL_2")
        or bool(c.get("approved"))
    )

    return {
        "name": drug_name,
        "why": why,
        "oncokb_label": label,
        "is_approved": is_approved,
    }


def _format_denovo_entry(c: dict) -> dict:
    """Format a de-novo entry for the ONCOLOGIST REPORT only.

    This is never shown in the patient letter.  The name and details are kept
    here so oncologist_report.py can include them in its dedicated section.
    """
    drug_name = c.get("drug_name") or c.get("name") or "Unnamed experimental compound"
    return {
        "name": drug_name,
        "smiles": c.get("smiles") or c.get("canonical_smiles"),
        "binding_score": c.get("binding_score"),
        "ensemble_score": c.get("ensemble_score"),
        "oral_exposure_score": c.get("oral_exposure_score"),
        "toxicity_risk": c.get("toxicity_risk"),
        "synthesis_feasibility_score": c.get("synthesis_feasibility_score"),
        "adme_flags": c.get("adme_flags", []),
        "toxicity_flags": c.get("toxicity_flags", []),
        "rationale": (
            "Computational hypothesis only. Has NOT been tested in humans or animals. "
            "Requires synthesis feasibility study, full in-vitro safety panel (Ames, "
            "hERG patch-clamp, HLM stability), and regulatory review before any "
            "in-vivo experiment or IND filing."
        ),
    }


def _build_what_we_found(
    gene: Optional[str],
    cancer_type: str,
    targetable: bool,
    mutation_summary: list[dict],
) -> str:
    gene_part = f" in a gene called {gene}" if gene else ""

    if targetable:
        return (
            f"Your DNA test found a specific change{gene_part} that is connected to "
            f"{cancer_type}. This kind of change is one that doctors have seen before, "
            f"and there are medicines that may be able to target cancer cells that carry "
            f"it. The options listed below are a starting point to explore with your "
            f"cancer doctor — they know your full situation far better than any computer."
        )
    else:
        return (
            f"Your DNA test was analysed for changes connected to {cancer_type}. "
            f"Right now, our research database did not find a medicine that closely "
            f"matches the specific change found. Please know that this does not mean "
            f"there are no good options — your cancer doctor has access to many more "
            f"treatments, clinical trials, and specialist resources than what this "
            f"computer can show. Bring this report to your next appointment and ask "
            f"your doctor what they recommend for your specific situation."
        )


def _build_warnings(
    ranked_candidates: list[dict],
    withdrawn_names: set[str],
    has_denovo: bool,
) -> list[str]:
    """Build a calm, plain-language list of things the patient should tell their doctor."""
    warnings: list[str] = []

    for c in ranked_candidates:
        oncokb = c.get("oncokb_level", "")
        drug_name = c.get("drug_name", "a medicine in this report")

        if oncokb in ("LEVEL_R1", "LEVEL_R2"):
            warnings.append(
                f"Tell your doctor: medical research suggests that {drug_name} may "
                f"not be effective for your specific DNA change. Always ask your "
                f"oncologist before starting any new medicine."
            )

        if drug_name.lower() in withdrawn_names:
            warnings.append(
                f"Tell your doctor: {drug_name} has been removed from the market in "
                f"some countries due to safety concerns. Do not take it without "
                f"explicit guidance from your cancer doctor."
            )

    # De-novo compounds: only add a brief, non-scary note if no approved drug was found
    # Full details are in the oncologist report — patients do not need to see them
    if has_denovo and not any(
        c.get("oncokb_level") not in ("LEVEL_R1", "LEVEL_R2", None)
        for c in ranked_candidates
    ):
        warnings.append(
            "Your doctor may have access to early-stage research ideas that could "
            "be explored. Ask your oncologist to review the full technical report."
        )

    return warnings


def _build_next_steps(targetable: bool, gene: Optional[str]) -> str:
    if targetable:
        gene_str = f"the {gene} change" if gene else "the DNA change"
        return (
            f"1. Print or save this report and bring it to your next cancer doctor visit.\n"
            f"2. Ask your doctor: 'Are any of these medicines a good fit for {gene_str}?'\n"
            f"3. Ask whether your case can be reviewed by a team of cancer specialists "
            f"together — this is called a \u2018tumour board\u2019 and many hospitals offer it.\n"
            f"4. Ask about clinical trials at clinicaltrials.gov that may match your "
            f"profile — your doctor or nurse can help you search.\n"
            f"5. Do not start or stop any medicine before talking to your doctor.\n"
            f"6. You do not have to face this alone. Ask your care team about support "
            f"groups or counselling if you need extra help."
        )
    else:
        return (
            "1. Bring this report to your next cancer doctor visit.\n"
            "2. Ask about all treatment options available for your cancer type.\n"
            "3. Ask if a team of cancer specialists can review your case together.\n"
            "4. Ask your doctor or nurse about clinical trials and support groups.\n"
            "5. Do not start or stop any medicine before talking to your doctor."
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_plain_text(s: PatientSummary) -> str:
    """Render the patient letter as a clean, human-readable plain-text string.

    De-novo / experimental compounds are intentionally excluded from the
    patient letter.  They appear only in the oncologist report.
    """
    lines: list[str] = []

    lines.append("=" * 62)
    lines.append("  YOUR TEST RESULT SUMMARY")
    lines.append("  OpenOncology Research Tool  —  For your oncologist visit")
    lines.append("=" * 62)
    lines.append("")
    lines.append("Dear Patient or Family Member,")
    lines.append("")
    lines.extend(textwrap.wrap(
        "We know that receiving a cancer diagnosis — and going through "
        "all the tests that come with it — is incredibly hard. "
        "This short report was made to give you something useful "
        "to bring to your next conversation with your cancer doctor. "
        "Please read it with your doctor or a family member, and do not "
        "hesitate to ask your care team to explain anything that is unclear.",
        width=62,
    ))
    lines.append("")

    lines.append("WHAT YOUR TEST FOUND")
    lines.append("-" * 42)
    lines.extend(textwrap.wrap(s.what_we_found, width=62))
    lines.append("")

    if s.top_repurposing:
        lines.append("MEDICINES WORTH ASKING YOUR DOCTOR ABOUT")
        lines.append("-" * 42)
        for i, entry in enumerate(s.top_repurposing, 1):
            status = "(already approved)" if entry["is_approved"] else "(in clinical studies)"
            lines.append(f"  {i}. {entry['name']}  {status}")
            lines.extend(
                textwrap.wrap(f"     {entry['why']}", width=62, subsequent_indent="     ")
            )
        lines.append("")
        lines.extend(textwrap.wrap(
            "These are medicines that already exist. Doctors use them for "
            "other conditions or for cancers with similar DNA changes. "
            "Whether any of them is right for you is a decision only your "
            "cancer doctor can make.",
            width=62,
        ))
        lines.append("")

    # De-novo compounds are NOT shown here — oncologist report only

    if s.warnings:
        lines.append("IMPORTANT: TELL YOUR DOCTOR")
        lines.append("-" * 42)
        for warning in s.warnings:
            lines.extend(textwrap.wrap(f"• {warning}", width=62, subsequent_indent="  "))
        lines.append("")

    lines.append("YOUR NEXT STEPS")
    lines.append("-" * 42)
    lines.append(s.next_steps)
    lines.append("")

    lines.extend(textwrap.wrap(
        "Thank you for trusting OpenOncology. We hope this information "
        "helps you have a useful conversation with your care team. "
        "You are not alone in this.",
        width=62,
    ))
    lines.append("")

    lines.append("=" * 62)
    lines.extend(textwrap.wrap(s.disclaimer, width=62))
    lines.append("=" * 62)

    return "\n".join(lines)


def _render_sections(s: PatientSummary) -> dict:
    """Return structured sections for UI rendering.

    Note: ``top_denovo`` is included for use by the oncologist report component
    of the UI (behind a 'View Full Technical Details' toggle). It is NOT shown
    in the patient-facing summary section.
    """
    return {
        "what_we_found": s.what_we_found,
        "top_repurposing": s.top_repurposing,
        # top_denovo: for oncologist report only — do not display in patient view
        "top_denovo": s.top_denovo,
        "warnings": s.warnings,
        "red_flags": s.warnings,   # backward-compat alias
        "next_steps": s.next_steps,
        "disclaimer": s.disclaimer,
        "denovo_extra_warning": s.denovo_extra_warning,
        "has_denovo": s.has_denovo,
        "targetable_mutation_found": s.targetable_mutation_found,
    }
