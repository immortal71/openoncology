"""
Email notification templates for OpenOncology.

All templates use inline CSS for maximum email client compatibility.
Call render_*(data) to get (subject, html_body) tuples for use with Resend.
"""
from __future__ import annotations

from datetime import datetime

# ── Shared layout ─────────────────────────────────────────────────────────────

_BRAND = "#1d4ed8"  # blue-700
_BG = "#f8fafc"
_CARD = "#ffffff"
_TEXT = "#1e293b"
_MUTED = "#64748b"
_border = "#e2e8f0"

def _layout(title: str, body: str) -> str:
    year = datetime.utcnow().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:40px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
        <!-- Header -->
        <tr>
          <td style="padding:0 0 24px 0;">
            <span style="font-size:20px;font-weight:700;color:{_BRAND};">OpenOncology</span>
            <span style="font-size:13px;color:{_MUTED};margin-left:8px;">Precision Cancer Medicine</span>
          </td>
        </tr>
        <!-- Card -->
        <tr>
          <td style="background:{_CARD};border:1px solid {_border};border-radius:12px;padding:32px;">
            {body}
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="padding:24px 0 0 0;text-align:center;font-size:12px;color:{_MUTED};">
            © {year} OpenOncology. Open-source precision cancer medicine.<br/>
            This message was sent automatically. Please do not reply to this email.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _h1(text: str) -> str:
    return f'<h1 style="margin:0 0 16px 0;font-size:22px;font-weight:700;color:{_TEXT};">{text}</h1>'

def _p(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:{_TEXT};">{text}</p>'

def _muted(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;font-size:13px;line-height:1.6;color:{_MUTED};">{text}</p>'

def _button(label: str, url: str) -> str:
    return f'''
<table cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr>
    <td style="background:{_BRAND};border-radius:8px;">
      <a href="{url}" style="display:inline-block;padding:12px 28px;font-size:15px;
         font-weight:600;color:#ffffff;text-decoration:none;">{label}</a>
    </td>
  </tr>
</table>'''

def _divider() -> str:
    return f'<hr style="border:none;border-top:1px solid {_border};margin:24px 0;" />'

def _stat(label: str, value: str) -> str:
    return f'''
<td style="padding:12px 16px;background:#f1f5f9;border-radius:8px;text-align:center;width:50%;">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:{_MUTED};">{label}</div>
  <div style="font-size:20px;font-weight:700;color:{_TEXT};margin-top:4px;">{value}</div>
</td>'''


# ─────────────────────────────────────────────────────────────────────────────
# 1. Results ready
# ─────────────────────────────────────────────────────────────────────────────

def render_results_ready(
    submission_id: str,
    mutation_count: int,
    targetable_count: int,
    top_drugs: list[str],
    results_url: str,
) -> tuple[str, str]:
    drug_list = ""
    if top_drugs:
        items = "".join(f'<li style="margin-bottom:4px;">{d}</li>' for d in top_drugs[:3])
        drug_list = f'''
{_divider()}
{_p("<strong>Top repurposing candidates:</strong>")}
<ul style="margin:0 0 16px 0;padding-left:20px;font-size:15px;color:{_TEXT};line-height:1.8;">{items}</ul>'''

    body = f"""
{_h1("Your genomic analysis is ready")}
{_p("We've finished analysing your DNA sample. Here's a summary of what we found:")}
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:8px 0;margin-bottom:16px;">
  <tr>
    {_stat("Mutations found", str(mutation_count))}
    {_stat("Targetable", str(targetable_count))}
  </tr>
</table>
{drug_list}
{_button("View Full Results", results_url)}
{_divider()}
{_muted(f"Submission ID: {submission_id}")}
{_muted("These results are for informational purposes only. Please consult a qualified oncologist before making any treatment decisions.")}
"""
    return "Your OpenOncology results are ready", _layout("Results Ready", body)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Campaign milestone
# ─────────────────────────────────────────────────────────────────────────────

def render_campaign_milestone(
    campaign_title: str,
    percent: int,
    raised_usd: float,
    goal_usd: float,
    campaign_url: str,
) -> tuple[str, str]:
    bar_width = min(percent, 100)
    body = f"""
{_h1(f"Your campaign reached {percent}% of its goal! 🎉")}
{_p(f"Great news — <strong>{campaign_title}</strong> just crossed the <strong>{percent}% milestone</strong>.")}
<div style="background:#e2e8f0;border-radius:999px;height:12px;margin:0 0 8px 0;">
  <div style="background:{_BRAND};border-radius:999px;height:12px;width:{bar_width}%;"></div>
</div>
<p style="margin:0 0 24px 0;font-size:13px;color:{_MUTED};">
  ${raised_usd:,.2f} raised of ${goal_usd:,.2f} goal
</p>
{"<p style='font-size:15px;color:#16a34a;font-weight:600;'>🏆 Goal reached! Funds will be released to the manufacturer shortly.</p>" if percent >= 100 else _p("Keep sharing your campaign link to reach your goal faster.")}
{_button("View Campaign", campaign_url)}
"""
    subject = f"Campaign milestone: {percent}% funded — {campaign_title}"
    return subject, _layout("Campaign Milestone", body)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Order confirmation
# ─────────────────────────────────────────────────────────────────────────────

def render_order_confirmed(
    order_id: str,
    drug_name: str,
    pharma_name: str,
    amount_usd: float,
    dashboard_url: str,
) -> tuple[str, str]:
    body = f"""
{_h1("Order confirmed")}
{_p(f"Your order has been confirmed and payment received. The manufacturer has been notified.")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {_border};border-radius:8px;margin-bottom:24px;">
  <tr><td style="padding:12px 16px;border-bottom:1px solid {_border};">
    <span style="font-size:12px;color:{_MUTED};">Drug</span><br/>
    <strong style="font-size:15px;">{drug_name}</strong>
  </td></tr>
  <tr><td style="padding:12px 16px;border-bottom:1px solid {_border};">
    <span style="font-size:12px;color:{_MUTED};">Manufacturer</span><br/>
    <strong style="font-size:15px;">{pharma_name}</strong>
  </td></tr>
  <tr><td style="padding:12px 16px;">
    <span style="font-size:12px;color:{_MUTED};">Amount paid</span><br/>
    <strong style="font-size:15px;">${amount_usd:,.2f}</strong>
  </td></tr>
</table>
{_button("View Dashboard", dashboard_url)}
{_divider()}
{_muted(f"Order ID: {order_id}")}
"""
    return f"Order confirmed — {drug_name}", _layout("Order Confirmed", body)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pharma verification approved
# ─────────────────────────────────────────────────────────────────────────────

def render_pharma_approved(
    company_name: str,
    onboarding_url: str,
) -> tuple[str, str]:
    body = f"""
{_h1("Your company has been approved")}
{_p(f"Congratulations — <strong>{company_name}</strong> has been verified on OpenOncology.")}
{_p("You can now receive orders from patients and get paid via Stripe. Complete your Stripe onboarding to enable payouts:")}
{_button("Complete Stripe Onboarding", onboarding_url)}
{_divider()}
{_muted("Once onboarding is complete, you will appear in the marketplace and can receive orders.")}
"""
    return f"{company_name} is now verified on OpenOncology", _layout("Company Approved", body)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Oncologist review complete
# ─────────────────────────────────────────────────────────────────────────────

def render_review_complete(
    submission_id: str,
    approved: bool,
    oncologist_notes: str,
    results_url: str,
) -> tuple[str, str]:
    status_html = (
        '<span style="background:#dcfce7;color:#16a34a;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600;">Approved</span>'
        if approved else
        '<span style="background:#fee2e2;color:#dc2626;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600;">Flagged for review</span>'
    )
    notes_section = ""
    if oncologist_notes:
        notes_section = f'''
{_divider()}
<p style="font-size:13px;font-weight:600;color:{_MUTED};margin:0 0 8px 0;">Oncologist notes</p>
<p style="font-size:14px;color:{_TEXT};line-height:1.6;margin:0;">{oncologist_notes}</p>'''

    body = f"""
{_h1("An oncologist has reviewed your results")}
{_p("A volunteer oncologist on OpenOncology has reviewed your genomic analysis.")}
<p style="margin:0 0 24px 0;">Review status: {status_html}</p>
{notes_section}
{_button("View Results", results_url)}
{_divider()}
{_muted(f"Submission ID: {submission_id}")}
{_muted("Oncologist reviews are voluntary second opinions and do not constitute medical advice.")}
"""
    subject = (
        "Oncologist review complete — results approved"
        if approved
        else "Oncologist review complete — please read notes"
    )
    return subject, _layout("Oncologist Review", body)
