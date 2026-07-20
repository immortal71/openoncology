"""
Generates test-fixtures/biopsy_report_kras_g12c.pdf — a synthetic pathology
report used to exercise the real POST /api/submit/ biopsy_file field.
Not a real patient record. Matches the tone/structure of sample3_biopsy.txt
already in this repo, formatted as an actual PDF (application/pdf,
matching ALLOWED_BIOPSY_TYPES in api/routes/submit.py).
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT

OUT_PATH = "biopsy_report_kras_g12c.pdf"

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleX", parent=styles["Heading1"], fontSize=14, spaceAfter=4)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceBefore=12, spaceAfter=4)
body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_LEFT)
mono_small = ParagraphStyle("MonoSmall", parent=styles["Normal"], fontSize=8, textColor=colors.grey)

doc = SimpleDocTemplate(OUT_PATH, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
story = []

story.append(Paragraph("OpenOncology — Pathology / Biopsy Report (TEST FIXTURE)", title_style))
story.append(Paragraph("Synthetic record generated for local submission-flow testing only. Not a real patient.", mono_small))
story.append(Spacer(1, 12))

patient_table = Table(
    [
        ["Patient Alias", "TESTFIX-KRAS-G12C-01"],
        ["Specimen", "Core needle biopsy, right upper lobe lung lesion"],
        ["Collection Date", "2026-07-14"],
        ["Report Date", "2026-07-16"],
        ["Referring Diagnosis", "Non-Small Cell Lung Cancer (Adenocarcinoma)"],
        ["Ordering Physician", "Dr. A. Reyes, Pulmonology (test fixture)"],
    ],
    colWidths=[1.8 * inch, 4.2 * inch],
)
patient_table.setStyle(TableStyle([
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.lightgrey),
]))
story.append(patient_table)

story.append(Paragraph("Gross Description", h2))
story.append(Paragraph(
    "Received in formalin, three cores of tan-white tissue, aggregate size 1.4 x 0.3 x 0.3 cm. "
    "Entirely submitted in one cassette.", body))

story.append(Paragraph("Histopathology Summary", h2))
story.append(Paragraph(
    "Malignant epithelial neoplasm consistent with adenocarcinoma, acinar-predominant pattern. "
    "Moderate nuclear atypia with gland-forming architecture and focal mucin production. "
    "Tumor cellularity estimated at approximately 60%. No definitive lymphovascular invasion identified "
    "on the submitted sections.", body))

story.append(Paragraph("Immunohistochemistry (IHC)", h2))
ihc_table = Table(
    [
        ["Marker", "Result"],
        ["TTF-1", "Positive"],
        ["Napsin A", "Positive"],
        ["p40", "Negative"],
        ["PD-L1 (TPS)", "30%"],
    ],
    colWidths=[2.4 * inch, 2.4 * inch],
)
ihc_table.setStyle(TableStyle([
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
]))
story.append(ihc_table)

story.append(Paragraph("Clinical Notes", h2))
story.append(Paragraph(
    "Specimen forwarded for molecular profiling and somatic variant interpretation. "
    "Accompanying DNA sequencing submission (dna_sample_kras_g12c.vcf) identifies a pathogenic "
    "KRAS p.Gly12Cys (c.34G&gt;T) variant at chr12:25398284 (GRCh38), consistent with a "
    "well-characterised actionable driver in lung adenocarcinoma. Recommend correlation with "
    "targeted therapy planning per current NCCN guidance.", body))

story.append(Spacer(1, 16))
story.append(Paragraph(
    "This is a synthetic test biopsy file generated for local platform validation only. "
    "It does not describe a real patient, specimen, or diagnosis.", mono_small))

doc.build(story)
print(f"Wrote {OUT_PATH}")
