# Test fixtures

Synthetic files for exercising the real `POST /api/submit/` flow end-to-end
(not the `?demo=true` shortcut, which never hits the backend). Neither file
describes a real patient.

| File | Field | Real format constraint (api/routes/submit.py) |
|---|---|---|
| `biopsy_report_kras_g12c.pdf` | `biopsy_file` | `application/pdf`, ext `pdf`, ≤ 50MB |
| `dna_sample_kras_g12c.vcf` | `dna_file` | ext `vcf`, ≤ 500MB |

Both describe the same case: **KRAS p.Gly12Cys (c.34G>T), chr12:25398284
(GRCh38)**, Non-Small Cell Lung Cancer — the same variant/coordinate used
elsewhere in this app's demo/marketing copy (`web/app/page.tsx`,
`web/components/ui/genomic-stream.tsx`), so results are easy to sanity-check
against what the rest of the product already claims about this mutation.

The VCF also carries three supporting rows (TP53, CDKN2A, NRAS) so it isn't
a trivial single-variant file — same INFO/FORMAT schema as the existing
`samples/egfr_t790m_demo.vcf` fixture in this repo.

Regenerate the PDF with:
```
cd test-fixtures
python generate_biopsy_pdf.py
```
Requires `reportlab` (`pip install reportlab`).
