"""PDF export service — generates printable PDFs for the oncologist report
and patient summary letter.

Supports two backends (in priority order):
  1. WeasyPrint — produces well-formatted, CSS-styled PDFs.
  2. Fallback — returns the HTML as UTF-8 bytes with Content-Type text/html.

Install WeasyPrint:
    pip install weasyprint>=60.0

The caller receives ``bytes`` in both cases.  The Content-Type header should be
set by the API endpoint based on ``get_pdf_content_type()``.

Security note: HTML is constructed from trusted internal data structures only.
No user-supplied strings are ever inserted as raw HTML — all are escaped with
``html.escape()``.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_WEASYPRINT_AVAILABLE: Optional[bool] = None  # lazy check


def _weasyprint_available() -> bool:
    global _WEASYPRINT_AVAILABLE
    if _WEASYPRINT_AVAILABLE is None:
        try:
            import weasyprint  # noqa: F401
            _WEASYPRINT_AVAILABLE = True
        except ImportError:
            _WEASYPRINT_AVAILABLE = False
            logger.warning(
                "WeasyPrint not installed — PDF export will return HTML. "
                "Install: pip install weasyprint>=60.0"
            )
    return _WEASYPRINT_AVAILABLE


def get_pdf_content_type() -> str:
    """Return the correct Content-Type for the generated binary."""
    return "application/pdf" if _weasyprint_available() else "text/html; charset=utf-8"


def get_pdf_extension() -> str:
    return ".pdf" if _weasyprint_available() else ".html"


def _render_to_bytes(html_str: str) -> tuple[bytes, bool]:
    """Render HTML string to (bytes, is_pdf)."""
    if _weasyprint_available():
        try:
            import weasyprint
            return weasyprint.HTML(string=html_str).write_pdf(), True
        except Exception as exc:
            logger.exception("WeasyPrint render failed; falling back to HTML export: %s", exc)
    return html_str.encode("utf-8"), False


def generate_patient_letter_document(summary: dict) -> tuple[bytes, str, str]:
    """Return (bytes, media_type, extension) for patient letter download."""
    body = _build_patient_html(summary)
    rendered, is_pdf = _render_to_bytes(body)
    if is_pdf:
        return rendered, "application/pdf", ".pdf"
    return rendered, "text/html; charset=utf-8", ".html"


def generate_oncologist_report_document(report) -> tuple[bytes, str, str]:
    """Return (bytes, media_type, extension) for oncologist report download."""
    body = _build_oncologist_html(report)
    rendered, is_pdf = _render_to_bytes(body)
    if is_pdf:
        return rendered, "application/pdf", ".pdf"
    return rendered, "text/html; charset=utf-8", ".html"


# ---------------------------------------------------------------------------
# Patient letter PDF
# ---------------------------------------------------------------------------

def generate_patient_letter_pdf(summary: dict) -> bytes:
    """Generate a patient-readable PDF letter from a patient summary dict.

    ``summary`` is the dict returned by
    ``api.services.patient_summary.generate_patient_summary()``.

    Returns bytes (PDF or HTML fallback).
    """
    body = _build_patient_html(summary)
    return _render_to_bytes(body)[0]


def _build_patient_html(s: dict) -> str:
    """Build the patient letter HTML."""
    date_str = s.get("generated_at") or datetime.now().strftime("%d %B %Y")
    cancer = html.escape(str(s.get("cancer_type") or "Not specified"))
    patient_id = s.get("patient_id")

    drugs = s.get("top_drugs") or []
    explanation_raw = str(s.get("explanation") or "").strip()
    explanation_words = explanation_raw.split()
    if len(explanation_words) > 110:
      explanation_raw = " ".join(explanation_words[:110]) + " ..."
    explanation = html.escape(explanation_raw)

    what_next = list(s.get("what_next") or [])
    if not any("print this" in str(step).lower() and "oncologist" in str(step).lower() for step in what_next):
      what_next.append("Print this and discuss with your oncologist.")
    what_next = what_next[:5]
    important_notes = s.get("important_notes") or []
    limitations = s.get("limitations") or []

    drug_rows = ""
    for d in drugs:
        name = html.escape(str(d.get("drug_name") or "Unknown"))
        status = html.escape(str(d.get("approval_status") or ""))
        notes = html.escape(str(d.get("patient_note") or d.get("notes") or ""))
        drug_rows += f"""
        <tr>
          <td class="drug-name">{name}</td>
          <td>{status}</td>
          <td>{notes}</td>
        </tr>"""

    what_next_items = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in what_next
    )
    note_items = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in important_notes
    )
    limitation_items = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in limitations
    )

    patient_block = f"<p><strong>Patient Reference:</strong> {html.escape(str(patient_id))}</p>" if patient_id else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Your Personalised Cancer Analysis — OpenOncology</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: Georgia, serif; font-size: 13pt; color: #1a1a1a;
            max-width: 720px; margin: 40px auto; padding: 0 24px; line-height: 1.7; }}
    h1 {{ font-size: 22pt; color: #003366; border-bottom: 2px solid #003366; padding-bottom: 8px; }}
    h2 {{ font-size: 15pt; color: #003366; margin-top: 32px; }}
    .meta {{ color: #555; font-size: 11pt; margin-bottom: 24px; }}
    .box-info {{ background: #eef4ff; border-left: 4px solid #2255aa; padding: 14px 18px;
                 border-radius: 4px; margin: 20px 0; }}
    .box-warn {{ background: #fff8e1; border-left: 4px solid #f0a500; padding: 14px 18px;
                 border-radius: 4px; margin: 20px 0; }}
    .box-disc {{ background: #ffeaea; border-left: 4px solid #cc2200; padding: 14px 18px;
                 border-radius: 4px; margin: 20px 0; font-size: 11pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    th {{ background: #003366; color: #fff; padding: 10px 12px; text-align: left; font-size: 11pt; }}
    td {{ padding: 9px 12px; border-bottom: 1px solid #dde; font-size: 11pt; }}
    td.drug-name {{ font-weight: bold; color: #003366; }}
    ul {{ margin: 8px 0 8px 20px; }}
    li {{ margin-bottom: 6px; }}
    .footer {{ margin-top: 48px; border-top: 1px solid #ccc; padding-top: 16px;
               font-size: 10pt; color: #777; }}
    @media print {{
      body {{ margin: 24px; }}
      .box-disc {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <h1>Your Personalised Cancer Analysis</h1>
  <div class="meta">
    <p><strong>Date:</strong> {date_str} &nbsp;|&nbsp; <strong>Cancer type:</strong> {cancer}</p>
    {patient_block}
  </div>

  <div class="box-info">
    <strong>What is this letter?</strong><br>
    This is a summary of a computational analysis of your tumour's DNA.
    It is meant to help you understand and discuss the findings with your doctor.
    <strong>Please do not make any treatment decisions based on this letter alone.</strong>
  </div>

  <div class="box-disc">
    <strong>Safety & Transparency:</strong> This is an experimental open-source tool. Not clinically validated.<br>
    Current benchmark context (internal retrospective tests): Standard P@3 ~0.50, Hit@3 ~0.98.<br>
    <strong>All recommendations must be reviewed by a qualified oncologist.</strong>
  </div>

  {f'<h2>About Your Analysis</h2><p>{explanation}</p>' if explanation else ''}

  {f"""<h2>Potential Treatment Options for Your Doctor to Review</h2>
  <p>The analysis identified the following drugs as potentially relevant to your tumour's
  genetic profile. Your oncologist will assess whether any of these are appropriate for you.</p>
  <table>
    <thead>
      <tr><th>Drug Name</th><th>Approval Status</th><th>Notes</th></tr>
    </thead>
    <tbody>{drug_rows}</tbody>
  </table>""" if drugs else
  '<div class="box-warn"><strong>No specific treatment options were identified</strong> '
  'for this variant in the current database. This does not mean no treatment exists — '
  'your oncologist may know of other options including clinical trials.</div>'}

  {f"<h2>Recommended Next Steps</h2><ul>{what_next_items}</ul>" if what_next else ''}

  {f"<h2>Important Notes</h2><ul>{note_items}</ul>" if important_notes else ''}

  {f"""<h2>Limitations of This Analysis</h2>
  <div class="box-warn"><ul>{limitation_items}</ul></div>""" if limitations else ''}

  <div class="box-disc">
    <strong>IMPORTANT DISCLAIMER:</strong> This document is generated by an experimental
    computational research tool and is not a medical diagnosis or treatment instruction.
    All findings must be reviewed by a licensed oncologist before any clinical action.
  </div>

  <div class="footer">
    OpenOncology Research Platform — For Research Use Only<br>
    Generated: {date_str}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Oncologist report PDF
# ---------------------------------------------------------------------------

def generate_oncologist_report_pdf(report) -> bytes:
    """Generate the full oncologist / tumour board report as a PDF.

    ``report`` is an ``OncologistReport`` dataclass instance from
    ``api.services.oncologist_report``.

    Returns bytes (PDF or HTML fallback).
    """
    body = _build_oncologist_html(report)
    return _render_to_bytes(body)[0]


def _build_oncologist_html(r) -> str:
    """Build the oncologist report HTML from an OncologistReport."""
    date_str = getattr(r, "report_date", datetime.now().strftime("%d %B %Y"))
    cancer = html.escape(str(getattr(r, "cancer_type", "Unknown")))
    patient_id = getattr(r, "patient_id", None)

    # ── Executive summary
    exec_s = r.executive_summary or {}
    conclusion = html.escape(str(exec_s.get("conclusion") or ""))
    overall_conf = exec_s.get("overall_confidence", "LOW")
    conf_label = html.escape(str(exec_s.get("overall_confidence_label") or ""))
    recommended_actions_line = html.escape(str(exec_s.get("recommended_actions_line") or ""))
    top_3 = exec_s.get("top_3_recommendations") or []
    resistance_flagged = exec_s.get("resistance_flagged_drugs") or []
    no_drug = exec_s.get("no_drug_verdict") or {}
    bench = exec_s.get("benchmark_transparency") or {}
    how_to_use = exec_s.get("how_to_use_this_report") or []

    top3_rows = ""
    for rec in top_3:
        score = rec.get("rank_score")
        ci_lo = rec.get("rank_score_ci_low")
        ci_hi = rec.get("rank_score_ci_high")
        score_str = f"{score:.3f}" if score is not None else "N/A"
        ci_str = f"[{ci_lo:.3f}–{ci_hi:.3f}]" if ci_lo is not None else ""
        action = rec.get("clinical_action", {}).get("recommendation", "REVIEW")
        status = html.escape(str(rec.get("approval_status") or ""))
        drug = html.escape(str(rec.get("drug_name") or ""))
        conf_cell = html.escape(str(rec.get("confidence_level") or "LOW"))
        top3_rows += f"""
        <tr>
          <td><strong>{html.escape(str(rec.get('rank', '?')))}</strong></td>
          <td class="drug-name">{drug}</td>
          <td>{status}</td>
          <td>{score_str} {ci_str}</td>
          <td>{conf_cell}</td>
          <td>{html.escape(action)}</td>
        </tr>"""

    resist_block = ""
    if resistance_flagged:
        drugs_esc = ", ".join(html.escape(d) for d in resistance_flagged)
        resist_block = f'<div class="box-resist">⛔ RESISTANCE FLAGGED: {drugs_esc} — do NOT use for this variant.</div>'

    no_drug_block = ""
    if no_drug.get("status") in ("no_candidate", "weak"):
        msg = html.escape(str(no_drug.get("message") or ""))
        no_drug_block = f'<div class="box-warn"><strong>⚠ NO STRONG CANDIDATE:</strong> {msg}</div>'

    bench_block = ""
    if bench:
        p3 = bench.get("precision_at_3_standard")
        h3 = bench.get("hit_at_3")
        n = bench.get("total_gold_standard_cases")
        lims = bench.get("benchmark_limitations") or []
        lim_items = "".join(f"<li>{html.escape(str(lim))}</li>" for lim in lims[:4])
        bench_note = "This is an experimental open-source tool. Not clinically validated."
        bench_block = f"""
        <div class="box-disc">
          <strong>Safety & Transparency:</strong> {bench_note}<br>
          <strong>All recommendations must be reviewed by a qualified oncologist.</strong><br>
          {f'Current benchmark context: Standard P@3={p3:.3f}, Hit@3={h3:.3f}, n={n}.' if (p3 is not None and h3 is not None and n) else ''}
          {f'<ul>{lim_items}</ul>' if lim_items else ''}
        </div>"""

    # ── Drug recommendations
    drug_recs = r.drug_recommendations or []
    drug_rows = ""
    for rec in drug_recs:
        score = rec.get("rank_score")
        ci_lo = rec.get("rank_score_ci_low")
        ci_hi = rec.get("rank_score_ci_high")
        score_str = f"{score:.3f}" if score is not None else "N/A"
        ci_str = f"<br><small>[{ci_lo:.3f}–{ci_hi:.3f}]</small>" if ci_lo is not None else ""
        drug = html.escape(str(rec.get("drug_name") or ""))
        status = html.escape(str(rec.get("approval_status") or ""))
        okb = html.escape(str(rec.get("oncokb_label") or rec.get("oncokb_level") or ""))
        conf_cell = html.escape(str(rec.get("confidence_level") or ""))
        safety = html.escape(str(rec.get("key_safety_note") or ""))
        next_step = html.escape(str(rec.get("next_step_for_oncologist") or ""))
        evidence_short = html.escape(str(rec.get("evidence_note_short") or ""))
        bullets = rec.get("rationale_bullets") or []
        bullet_html = "".join(f"<li>{html.escape(str(b))}</li>" for b in bullets)
        resist = "⛔ RESISTANCE" if rec.get("is_resistance") else ""
        class_row = "resistance-row" if rec.get("is_resistance") else ""
        drug_rows += f"""
        <tr class="{class_row}">
          <td><strong>{html.escape(str(rec.get('rank', '?')))}</strong></td>
          <td class="drug-name">{drug} {resist}</td>
          <td>{status}</td>
          <td>{score_str}{ci_str}</td>
          <td>{conf_cell}</td>
          <td>{okb}<br><small>{evidence_short}</small><br><ul class="tight">{bullet_html}</ul></td>
          <td>{safety}</td>
          <td>{next_step}</td>
        </tr>"""

    # ── Genomic alterations
    genomic_rows = ""
    for alt in (r.genomic_alterations or []):
        gene = html.escape(str(alt.get("gene") or "?"))
        hgvs = html.escape(str(alt.get("hgvs_notation") or "N/A"))
        vaf = alt.get("vaf")
        vaf_str = f"{vaf:.1%}" if vaf is not None else "N/A"
        cls = html.escape(str(alt.get("classification") or "unknown"))
        okb = html.escape(str(alt.get("oncokb_level") or "—"))
        am = alt.get("alphamissense_score")
        am_str = f"{am:.3f}" if am is not None else "—"
        genomic_rows += f"""
        <tr>
          <td>{gene}</td>
          <td>{hgvs}</td>
          <td>{vaf_str}</td>
          <td>{cls}</td>
          <td>{okb}</td>
          <td>{am_str}</td>
        </tr>"""

    # ── Experimental candidates
    exp_html = ""
    for ec in (r.experimental_candidates or []):
        name = html.escape(str(ec.get("name") or ec.get("candidate_name") or ec.get("candidate_id") or "Unknown"))
        ens = ec.get("ensemble_score")
        tox = ec.get("toxicity_risk")
        synth = ec.get("synthesis_feasibility_score")
        rationale = html.escape(str(ec.get("target_rationale") or ec.get("biological_rationale") or ""))
        smiles = html.escape(str(ec.get("smiles") or ec.get("proposed_smiles") or "N/A"))
        steps = ec.get("suggested_next_steps") or []
        steps_html = "".join(
            f"<li><strong>{html.escape(str(s.get('step') or 'Step'))}</strong>: {html.escape(str(s.get('details') or ''))}</li>"
            for s in steps[:3]
        )
        exp_html += f"""
        <div class="exp-card">
          <h4>{name}</h4>
          <p><strong>Computational hypothesis only - no wet-lab data.</strong></p>
          <table class="exp-table">
            <tr><td>Ensemble score:</td><td>{f'{ens:.1f}/100' if ens else 'N/A'}</td></tr>
            <tr><td>Toxicity risk:</td><td>{f'{tox:.1f}/100 (lower=safer)' if tox else 'N/A'}</td></tr>
            <tr><td>Synthesis feasibility:</td><td>{f'{synth:.1f}/100' if synth else 'N/A'}</td></tr>
            <tr><td>SMILES:</td><td><code>{smiles}</code></td></tr>
          </table>
          {f'<p class="rationale"><strong>Biological rationale:</strong> {rationale}</p>' if rationale else ''}
          {f'<p><strong>Concrete next steps:</strong></p><ul class="tight">{steps_html}</ul>' if steps_html else ''}
        </div>"""

    patient_block = f"<p><strong>Patient ID:</strong> {html.escape(str(patient_id))} (anonymised)</p>" if patient_id else ""

    disclaimer_text = html.escape(getattr(r, "disclaimer", ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Oncologist Report — {cancer}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, sans-serif; font-size: 11pt; color: #111;
            max-width: 900px; margin: 32px auto; padding: 0 24px; line-height: 1.6; }}
    h1 {{ font-size: 18pt; color: #002060; border-bottom: 3px solid #002060; padding-bottom: 8px; }}
    h2 {{ font-size: 13pt; color: #002060; background: #eef2ff; padding: 6px 10px;
          border-left: 4px solid #002060; margin-top: 28px; }}
    h3 {{ font-size: 11pt; color: #333; margin-top: 18px; }}
    h4 {{ font-size: 11pt; color: #002060; margin-bottom: 4px; }}
    .meta {{ color: #555; font-size: 10pt; margin-bottom: 20px; }}
    .conf-badge {{
      display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: bold;
      font-size: 10pt; margin-left: 8px;
    }}
    .conf-HIGH {{ background: #c8f7c5; color: #145214; }}
    .conf-MEDIUM {{ background: #fff3cd; color: #7d5f00; }}
    .conf-LOW {{ background: #fde8e8; color: #7d0000; }}
    .box-info {{ background: #eef4ff; border-left: 4px solid #2255aa; padding: 12px 16px;
                 border-radius: 4px; margin: 16px 0; }}
    .box-warn {{ background: #fff8e1; border-left: 4px solid #f0a500; padding: 12px 16px;
                 border-radius: 4px; margin: 16px 0; }}
    .box-resist {{ background: #fde8e8; border-left: 4px solid #cc0000; padding: 12px 16px;
                   border-radius: 4px; margin: 16px 0; font-weight: bold; }}
    .box-disc {{ background: #fff0f0; border: 1px solid #cc0000; padding: 14px 18px;
                 border-radius: 4px; margin: 24px 0; font-size: 10pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }}
    th {{ background: #002060; color: #fff; padding: 8px 10px; text-align: left; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #dde; vertical-align: top; }}
    .drug-name {{ font-weight: bold; color: #002060; }}
    .resistance-row td {{ background: #fde8e8; }}
    ul.tight {{ margin: 4px 0 4px 16px; padding: 0; }}
    ul.tight li {{ margin-bottom: 2px; }}
    .exp-card {{ border: 1px solid #c8d8f0; border-radius: 6px; padding: 14px 18px;
                 margin: 12px 0; background: #f8faff; }}
    .exp-table {{ width: auto; margin: 6px 0; }}
    .exp-table td {{ padding: 3px 12px 3px 0; border: none; }}
    .exp-table td:first-child {{ font-weight: bold; color: #555; width: 200px; }}
    .rationale {{ font-style: italic; color: #444; margin-top: 8px; }}
    code {{ font-size: 9pt; background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }}
    .footer {{ margin-top: 48px; border-top: 1px solid #ccc; padding-top: 14px;
               font-size: 9pt; color: #777; }}
    @media print {{
      body {{ margin: 16px; }}
      h2 {{ break-after: avoid; }}
      .exp-card {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <h1>Oncologist / Molecular Tumour Board Report</h1>
  <div class="meta">
    <strong>Date:</strong> {date_str} &nbsp;|&nbsp;
    <strong>Cancer:</strong> {cancer} &nbsp;|&nbsp;
    <strong>Confidence:</strong>
    <span class="conf-badge conf-{overall_conf}">{overall_conf}</span>
    {patient_block}
  </div>

  <!-- ─── SECTION 1: Executive Summary ──────────────────────────────── -->
  <h2>Section 1 — Executive Summary</h2>
  <p>{conclusion}</p>
  {f'<p><em>{conf_label}</em></p>' if conf_label else ''}
  {f'<div class="box-info"><strong>Recommended Actions:</strong> {recommended_actions_line}</div>' if recommended_actions_line else ''}
  {resist_block}
  {no_drug_block}
  {bench_block}

  {f"""<h3>Top-3 Recommendations</h3>
  <table>
    <thead>
      <tr><th>#</th><th>Drug</th><th>Status</th><th>Score</th><th>Confidence</th><th>Action</th></tr>
    </thead>
    <tbody>{top3_rows}</tbody>
  </table>""" if top3_rows else '<p>No ranked drug candidates identified.</p>'}

  <!-- ─── SECTION 2: Genomic Alterations ───────────────────────────── -->
  <h2>Section 2 — Key Genomic Alterations</h2>
  {f"""<table>
    <thead>
      <tr><th>Gene</th><th>HGVS</th><th>VAF</th><th>Classification</th><th>OncoKB</th><th>AlphaMissense</th></tr>
    </thead>
    <tbody>{genomic_rows}</tbody>
  </table>""" if genomic_rows else '<p>No genomic alteration data provided.</p>'}

  <!-- ─── SECTION 3: Drug Recommendations ─────────────────────────── -->
  <h2>Section 3 — Drug Recommendations (Full Ranked List)</h2>
  {f"""<table>
    <thead>
      <tr><th>#</th><th>Drug</th><th>Status</th><th>Score</th><th>Conf.</th><th>Evidence</th><th>Key Safety Note</th><th>Next Step for Oncologist</th></tr>
    </thead>
    <tbody>{drug_rows}</tbody>
  </table>""" if drug_rows else '<p>No ranked drug candidates identified.</p>'}

  <!-- ─── SECTION 4: Experimental Candidates ───────────────────────── -->
  {f"""<h2>Section 4 — Experimental / Custom Drug Candidates</h2>
  <div class="box-warn">
    <strong>⚠ HIGHLY EXPERIMENTAL — Research Use Only.</strong> The following candidates
    are <em>computational hypotheses</em> generated by the de-novo drug discovery module.
    None have been tested in humans or animals. Computational hypothesis only - no wet-lab data.
    Independent docking validation, synthesis feasibility review, and medicinal chemistry consultation are required.
    Wet-lab validation is <strong>mandatory</strong> before any development.
    Do not discuss these with the patient.
  </div>
  {exp_html}""" if r.experimental_candidates else ''}

  {f"""<h2>Section 5 — How to Use This Report</h2>
  <ul>{''.join(f'<li>{html.escape(str(item))}</li>' for item in how_to_use)}</ul>""" if how_to_use else ''}

  <!-- ─── DISCLAIMER ─────────────────────────────────────────────── -->
  <div class="box-disc">
    <strong>MANDATORY DISCLAIMER:</strong> {disclaimer_text if disclaimer_text else
    'This report was produced by an automated computational research tool and does NOT '
    'constitute medical advice, diagnosis, or a treatment recommendation. '
    'It has not been cleared as a medical device. All findings require review and '
    'confirmation by a licensed oncologist before any clinical action.'}
  </div>

  <div class="footer">
    OpenOncology Research Platform — For Physician Review Only &nbsp;|&nbsp; {date_str}
  </div>
</body>
</html>"""
