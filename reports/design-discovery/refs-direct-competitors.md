# Reference study: how competitors present molecular result → therapy → evidence

Discovery question: should OpenOncology's hero visual and results view be a **portrait, vertically ordered report** rather than the current horizontal dark dashboard panel?

Method, 27 Nov 2026. Public sample reports were downloaded and their text extracted. FMI and Caris pages were also rendered to images with pdf.js so their visual layout could be checked. OncoKB, CIViC and cBioPortal were viewed live in a browser, using the demo variant (KRAS G12C, NSCLC) or a public de-identified TCGA case. No personal data was used in any search. Non-essential cookies were declined.

Labels used throughout:
- **OBSERVED** means something seen in the source.
- **INFERENCE** means our interpretation for OpenOncology.
- **Could not access** means it was not verified, and nothing in that area is invented.

Coverage:

| Product | Status |
|---|---|
| FoundationOne CDx sample report | Full. 32-page public PDF, pages 1, 3 and 4 rendered |
| Caris MI Profile sample report | Full. Public PDF (©2025), pages 1 and 3 rendered, all 6 pages read as text |
| OncoKB variant page | Full. Live page `KRAS G12C in NSCLC` |
| CIViC evidence item | Full. Live page `EID9431` (sotorasib, KRAS G12C, NSCLC) |
| cBioPortal patient view | Full. Live, public TCGA LUAD case with KRAS G12C |
| Guardant360 | Partial. The physician insert and interpretation guide were read, but **no sample report layout was available** |
| Tempus xT | **Could not access the report.** tempus.com answered HTTP 429 to automated fetches of the sample report and the report guide. Opening the sample PDF in the browser pane triggered a file-download dialog, which was not accepted. Only the marketing page was observed |
| Bio/YC software page (optional) | Not examined. Time went to the primary sources |

---

## Card 1: FoundationOne CDx (Foundation Medicine), sample report, NSCLC MET exon 14

- **Source / screen:** https://info.foundationmedicine.com/hubfs/Foundation_Medicine_eDetail/F1CDx_NSCLC_MET_Sample_Report.pdf, 32 pages in three parts: "FDA APPROVED CLAIMS" (2 pp), "PROFESSIONAL SERVICES" (20 pp) and "APPENDIX" (10 pp). Its NCCN notice is dated 2020, and the report itself says its claims "may not be up to date".
- **Task / state observed:** a reader receives a tissue CGP result for NSCLC with one companion-diagnostic (CDx) finding (MET exon 14 → capmatinib) and several other alterations. The document is a static, finished report.
- **What the design does (OBSERVED):**
  - **Format and frame.** Portrait US-letter. Every page repeats a header (brand mark top-left, then PATIENT / TUMOR TYPE / REPORT DATE / ORDERED TEST #) and a footer (signatures, CLIA numbers, "PAGE n of N" for each part). A diagonal light-grey "SAMPLE" watermark covers each page.
  - **Page 1, top to bottom:**
    - A three-column identity block (PATIENT / PHYSICIAN / SPECIMEN). Labels are small grey caps over values.
    - The H2 "Companion Diagnostic (CDx) Associated Findings".
    - A two-column claim table: an orange header "GENOMIC FINDINGS DETECTED" on the left, a grey header "FDA-APPROVED THERAPEUTIC OPTIONS" on the right, and one row: *MET* exon 14 splice site → Tabrecta (Capmatinib).
    - An orange-outlined callout: "For Microsatellite Instability (MSI) results, confirmatory testing using a validated orthogonal method should be performed."
    - A grey-bordered box "OTHER ALTERATIONS & BIOMARKERS IDENTIFIED". It opens with a disclaimer that these results are not prescriptive, then lists alterations in two columns. Gene names are bold italic. A § marker on each item points to "limitation statements" in the appendix, and a closing line sends the reader to the appendix for VUS.
  - **Professional services, page 1:**
    - A serif italic disclaimer at the top-left says the interpretive content is not FDA-reviewed.
    - A right-hand box holds orange serif headings "Biomarker Findings" and "Genomic Findings" with the alteration list.
    - Explicit negatives follow: "7 Disease relevant genes with no reportable alterations: ALK, BRAF, EGFR, ERBB2, KRAS, RET, ROS1".
    - Count lines read "11 Therapies with Clinical Benefit", "0 Therapies with Lack of Response" and "24 Clinical Trials".
    - An orange BIOMARKER FINDINGS column sits against a dark-slate ACTIONABILITY column ("No therapies or clinical trials.").
  - **Professional services, page 2 (the core claim → therapy → evidence view):**
    - A three-column table: orange "GENOMIC FINDINGS", then slate "THERAPIES WITH CLINICAL BENEFIT (IN PATIENT'S TUMOR TYPE)", then slate "… (IN OTHER TUMOR TYPE)".
    - Each drug carries a small outlined box with its **NCCN category** ("1", "2A") right next to it. A legend box reads "NCCN category".
    - Under each finding, a grey strip says "10 Trials see p. 14". An empty cell says "none" rather than being left blank.
    - A grey band "GENOMIC FINDINGS WITH NO REPORTABLE THERAPEUTIC OR CLINICAL TRIAL OPTIONS" lists alterations with dot leaders to page numbers.
    - Fine print states that neither therapies nor trials "are ranked in order of potential or predicted efficacy … nor … level of evidence".
  - **Detail pages:** one page per alteration, with GENE / ALTERATION in the left margin and prose sections POTENTIAL TREATMENT STRATEGIES, FREQUENCY & PROGNOSIS and FINDING SUMMARY. Superscript citation numbers resolve to an appendix reference list.
  - **Appendix:**
    - A VUS grid (gene in caps, variant beneath) introduced by a NOTE that the VUS are included "in the event that they become clinically meaningful in the future".
    - "QUALIFIED ALTERATION CALLS (EQUIVOCAL AND SUBCLONAL)": "subclonal" means <10% of the assayed tumour DNA.
    - "LEVEL OF EVIDENCE NOT PROVIDED".
    - A ranking rule: alphabetical within each NCCN category, patient's tumour type first.
    - Quality failures are reported in place: TMB and LOH show "Cannot Be Determined" when the sample is not of sufficient quality.
    - Level 2 / Level 3 classification definitions, limitations, and the genes assayed.
  - **Colour:** orange is used for findings and section accents only. Slate and grey mark therapy headers and secondary bands. Evidence tiers are **not** colour-coded; they are a typographic badge.
- **Why it may work for OpenOncology (INFERENCE):**
  - The reading order is identity → headline claim with its therapy → caveat callout → everything else, which matches a clinician's scan path.
  - Placing the evidence badge right next to the drug answers "how strong is this?" without a second panel.
  - The "no reportable alterations" line and the in-place "Cannot Be Determined" state are direct precedents for OpenOncology's explicit-gap display (missing VAF and depth).
- **Where it could fail for OpenOncology:**
  - FMI deliberately **does not rank**: it orders alphabetically to avoid implying efficacy. OpenOncology's core output *is* a ranking. Copying the table without a visible ranking rationale would hide the main thing we do, and adding a score column would invite reading it as a probability.
  - The patient, physician and CLIA signature furniture signals a regulated lab document. OpenOncology is a research prototype and must not look like a medical device.
  - At 32 pages, the format is built for print, not for exploring.
- **Principle to adapt:** put the evidence level in the same row as the claim it qualifies, and give "nothing found" and "could not determine" their own visible lines instead of omitting them.
- **Asset origin / reuse:** © Foundation Medicine, Inc. The PDF is public and not gated, carries a SAMPLE watermark, and contains NCCN content "referenced with permission". Reference only. Do not reuse layout art, the orange or slate palette, or the brand mark.

## Card 2: Caris MI Profile, sample report (gallbladder adenocarcinoma, ERBB2-positive)

- **Source / screen:** the "Download Sample Report" link on https://www.carislifesciences.com/physicians/physician-tests/mi-profile/, which resolves to https://d35ibn74wp9llh.cloudfront.net/000d31fd-e04b-4936-be1c-11acbe19e1ec/20dc70ea-8c7d-4b24-bb3b-3c5cc93973c9/20dc70ea-8c7d-4b24-bb3b-3c5cc93973c9_source__v.pdf. The report is 6 pages plus "Additional Results" pages, ©2025.
- **Task / state observed:** a finished multi-modal report (DNA, RNA and IHC) with one actionable biomarker (ERBB2 IHC 3+) and many negatives.
- **What the design does (OBSERVED):**
  - **Format and frame.** Portrait letter. "Final Report" sits top-right in thin light-blue type beside the logo. Section headings are large, thin, light-blue sans. A diagonal watermark reads "SAMPLE REPORT FOR ILLUSTRATIVE PURPOSES ONLY. NOT FOR CLINICAL USE."
  - **Page 1, top to bottom:**
    - Three headed columns: Patient / Specimen Information / Ordered By.
    - **"Results with Therapy Associations"** as the first content section. A table with a mid-blue header row in letter-spaced white caps has the columns BIOMARKER | METHOD | ANALYTE | RESULT | THERAPY ASSOCIATION | BIOMARKER LEVEL*.
    - In that table, a solid **green "BENEFIT" cell** spans the drug rows. Drug names in bold mark "the most clinically significant findings". The level appears as text ("Level 1", "Level 2") in the far-right column.
    - A footnote defines the levels: Level 1 is a companion diagnostic; Level 2 is strong evidence or guideline-endorsed; Level 3 is potential significance.
    - An "Important Note" callout on a pale-blue tint (trial eligibility, a pointer to the AI cancer-type section).
    - "Cancer-Type Relevant Biomarkers": two side-by-side tables listing positives in bold ("Amplified", "Likely Pathogenic Variant Exon 22 | p.R896C") and negatives in regular grey ("Mutation Not Detected", "Fusion Not Detected").
    - A footer with a liability statement about physician discretion.
  - **Page 2:**
    - "Genomic Signatures": MSI, then TMB on a Low–High scale bar (6 mut/Mb), then LOH shown as "High - 21% of tested genomic segments exhibited LOH (assay threshold is 16%)". The threshold is printed beside the result.
    - "Genes Tested with Pathogenic or Likely Pathogenic Alterations", with a Variant Frequency % column.
    - Then the notes "Variants of Uncertain Significance can be found in the MI Portal" and "Unclassified alterations … can be found in the MI Portal".
  - **Page 3:**
    - HLA genotype and IHC results.
    - "Genes Tested with **Indeterminate** Results by Tumor DNA Sequencing", a row of gene chips with the explanation "ruled indeterminate due to low coverage for some or all exons".
    - "Genes Tested with Intermediate CNA Results".
    - A paragraph saying the report was "curated to represent biomarkers most relevant for the submitted cancer type" and that normal findings and VUS are in the portal.
  - **Page 4:** "Notes of Significance", specimen and method details, and an adequacy note: "If the submitted specimen is inadequate, only a subset of the ordered testing may be reported."
  - **Pages 5–6:** "Clinical Trials Connector" (drug classes with trial counts), then the Disclaimer.
  - **Colour:** green only for BENEFIT. This sample had no lack-of-benefit row, so how lack of benefit is coloured **could not be verified**. Everything else is blue tints.
- **Why it may work for OpenOncology (INFERENCE):**
  - The page puts the answer first: the very first table is result → therapy → level, in one row.
  - Printing a threshold beside its value (LOH 21% vs 16%) is the right pattern for VAF and depth: show the measured value, the cut-off, and whether it was met.
  - The "Indeterminate due to low coverage" list is a near-exact analogue of OpenOncology's missing-data gaps.
- **Where it could fail for OpenOncology:**
  - Pushing VUS and normal findings to a separate portal works for a lab with a portal. For OpenOncology it would hide the very gaps we want visible.
  - A big green BENEFIT block reads as an endorsement. A research tool should not colour-code a recommendation.
  - Six separate tables per page are dense. That works on paper, but a hero image needs one focal claim.
- **Principle to adapt:** state each measurement next to the threshold it was judged against, and list what could not be assessed by name, in the main body.
- **Asset origin / reuse:** © Caris Life Sciences. The PDF is public and linked from the product page without a form, and is watermarked "not for clinical use". The disclaimer page asserts that report materials are Caris property. Reference only.

## Card 3: OncoKB, variant page (KRAS G12C in NSCLC)

- **Source / screen:** https://www.oncokb.org/gene/KRAS/somatic/G12C/NSCLC, live, "Last data update: 11/25/2026 (v7.8)".
- **Task / state observed:** look up the clinical actionability of one variant in one tumour type. A cookie banner appeared on load and was rejected.
- **What the design does (OBSERVED):**
  - **Frame.** Landscape web page, white background, blue top bar, single centred column. It reads as a document, not a dashboard.
  - **Top to bottom:**
    - The breadcrumb "GRCh37 / KRAS / G12C / Non-Small Cell Lung Cancer".
    - The H1 "KRAS G12C" with a "Somatic" pill, then "in" and a tumour-type **dropdown**, so the context is editable inside the title.
    - "Variant Overview": two plain sentences, with a "Show mutation effect description" toggle.
    - A row of summary cards: Oncogenicity "Oncogenic", Biological Effect "Gain-of-function", and a separate card with **Therapeutic level "1"** (filled green circle) and **FDA level "2"** (outlined black circle).
    - The H2 "Clinical Implications of This Biomarker in Non-Small Cell Lung Cancer (NSCLC)", with tabs "Therapeutic Implications" and "FDA-Recognized Biomarker".
    - A one-sentence summary: sotorasib and adagrasib are FDA-approved for KRAS G12C NSCLC.
    - The table "FDA-approved and/or NCCN-recommended drug association(s)", with columns Level of Evidence | Drugs | Alterations | Level-associated cancer types | Citations (a count) | Description (book icon). **Adagrasib is listed above Sotorasib**: both are Level 1, in alphabetical order. Daraxonrasib follows at Level 2 (blue circle).
    - A second table, "Investigational drug association(s)", follows at lower levels. The cBioPortal embed of the same data shows level-3-range badges in purple.
    - The footer: terms of use, a citation request, and the data version and date.
  - **Colour:** **level is colour-coded** (1 green, 2 blue, 3-range purple, FDA level as an outlined circle), always paired with the level number inside the badge.
- **Why it may work for OpenOncology (INFERENCE):**
  - OncoKB is our primary evidence source, so mirroring its *semantics* (the level as the first column, level-associated cancer type as its own column, a citation count) will read as familiar to anyone who checks our work.
  - Showing the version and date in the footer ("v7.8, 11/25/2026") is a cheap provenance signal we should copy in principle.
  - OncoKB's own alphabetical order for sotorasib and adagrasib shows the knowledge base treats them as equal. That supports annotating our 0.98/0.97 as a tie rather than presenting a winner.
- **Where it could fail for OpenOncology:**
  - OncoKB is about one variant. Our view is about one *case* (many variants, ranked drugs, gaps), so a single-variant page structure does not scale to the case.
  - Reusing OncoKB's exact level colours could imply affiliation or endorsement.
- **Principle to adapt:** put the evidence level first in each therapy row as a labelled badge (number plus colour, never colour alone), and print the evidence-source version and date wherever evidence is shown.
- **Asset origin / reuse:** © Memorial Sloan Kettering. Use is governed by the OncoKB Terms of Use, with licensing for commercial use. Level icons and colours are MSK's. Do not copy the badges; define our own.

## Card 4: CIViC, evidence item page (EID9431)

- **Source / screen:** https://civicdb.org/evidence/9431/summary. The item ID was found through the public CIViC GraphQL API (therapy = Sotorasib).
- **Task / state observed:** inspect one curated evidence statement supporting sotorasib in KRAS G12C NSCLC.
- **What the design does (OBSERVED):**
  - **Frame.** Landscape web app with a dark left sidebar (knowledge-base nav) and a white content card. The breadcrumb reads "Evidence / EID9431 / Summary", a parent chip "KRAS G12C" sits top-right, and tabs run Summary / Comments / Revisions / Flags / Activity.
  - **Left column:**
    - **"Statement"** comes first as prose: the CodeBreaK 100 phase II cohort, n=124, ORR 37.1% (95% CI 28.6–46.2), mPFS 6.8 months, OS 12.5 months. A Mode toggle switches between curies, names and tags.
    - Below the statement, an attribute table: Type "Predictive", Direction "Supports", Significance "Sensitivity / Response", Variant Origin "Somatic", **Level "A - Validated association"**, Rating (5 stars).
    - Then Source "PubMed: Skoulidis et al., 2021" and Clinical Trial "NCT03600883".
  - **Right column:**
    - Status as a green "Accepted" pill, with submitted and accepted dates and curator and editor usernames.
    - Molecular Profile, MP Expression, Disease, **Phenotype "Not specified"** (an empty value is stated explicitly), and Therapy.
  - **Bottom:** "EID9431 Assertions 0 of 0 displayed", with an empty table showing "No Data".
  - **Colour:** each entity type is a chip with its own icon colour. The evidence level is plain text ("A - …"), not a colour.
- **Why it may work for OpenOncology (INFERENCE):**
  - CIViC puts the **claim sentence first, with the actual numbers and confidence intervals**, and attributes second. That is the right order for a drug-row expansion in OpenOncology: what the evidence says, then its classification.
  - "Direction: Supports" separated from "Significance" is a useful split for showing contradicting or resistance evidence.
  - Explicit "Not specified" and "0 of 0" states are a clean pattern for gaps.
- **Where it could fail for OpenOncology:**
  - This is a curator's tool. Revision, flag and curator chrome would be noise for a reader of a case result.
  - Star ratings invite reading quality as a continuous score, which is close to the score-versus-probability confusion we must avoid.
- **Principle to adapt:** when evidence is expanded, lead with the claim stated in plain language with its effect size and source, then the classification fields, and show empty fields as "not specified" rather than hiding them.
- **Asset origin / reuse:** CIViC knowledgebase content is published as open data (CC0, per CIViC's "Data Licensing" page linked in the sidebar; re-check before reuse). The UI design is not ours to copy. Contributor usernames are visible on the page and are deliberately not reproduced here.

## Card 5: cBioPortal, patient view (public TCGA LUAD case with KRAS G12C)

- **Source / screen:** https://www.cbioportal.org/patient?studyId=luad_tcga_pan_can_atlas_2018&caseId=TCGA-05-4244. This is a public, de-identified TCGA research case, chosen through the public API because it carries KRAS G12C.
- **Task / state observed:** review one patient's mutations with their annotations. Two hover states were checked: the OncoKB icon on KRAS, and an empty annotation icon.
- **What the design does (OBSERVED):**
  - **Frame.** Landscape and wide. This is the most dashboard-like of the five.
  - **Header line:** patient ID, a demographics and diagnosis line, a sample chip, then tabs Summary / Pathways / Clinical Data / Pathology Report / Tissue Image / Slide Microscopy.
  - **Visual tracks:** a timeline track, then a genome-wide track (mutations, and CNA as 45.6% genome altered).
  - **Table "192 Mutations (page 1 of 20)":** the columns are Gene | Protein Change (bold italic) | **Annotation** (OncoKB, CIViC and hotspot-flame icons) | Mutation Type (green "Missense") | Allele Freq (0.35) | Copy # (red "Gain", blue "ShallowDel") | mRNA Expr. (dot on a line with a percentile).
  - **Default sort:** annotated mutations come first (KRAS G12C at the top, then CDK12 and KDM5C), followed by unannotated ones with **empty-circle icons**.
  - **Hover on KRAS's OncoKB icon** opens a popover document:
    - A blue header "KRAS p.G12C / Lung Adenocarcinoma".
    - A sub-bar "Oncogenic | Gain-of-function".
    - Two sentences of prose.
    - Tabs "Biological Effect" and "Therapeutic Implications [1]".
    - A table Level | Alteration(s) | Drug(s) | Level-associated cancer type(s): Adagrasib and Sotorasib at Level 1 (green), Daraxonrasib at Level 2, then purple level-3-range rows for colorectal combinations.
  - **Hover on an empty circle** says: "The gene is listed under OncoKB Cancer Gene List but hasn't been curated yet."
  - **Colour:** colour encodes data type (mutation class, copy-number direction), and evidence level appears only inside the OncoKB badge.
- **Why it may work for OpenOncology (INFERENCE):**
  - The sorting does the triage: actionable first, uncertain below, and nothing hidden. That is the exact behaviour our ranked list needs.
  - The empty-circle-with-explanation pattern turns "no evidence" into a visible, explained state instead of a blank.
  - The popover shows how a dashboard row can expand into a mini-report without leaving the case.
- **Where it could fail for OpenOncology:**
  - Density (20 pages of mutations, 7+ columns, genome tracks) suits power users. A first-time reader of a hero image would not know where to look.
  - It shows no single answer or headline. cBioPortal does not rank drugs at all.
  - Every value is the same type size, so nothing tells the reader "start here".
- **Principle to adapt:** sort by actionability so evidence-backed rows lead and uncertain rows follow visibly, and give every "no annotation" cell an explanation of why.
- **Asset origin / reuse:** cBioPortal is open-source software (AGPL-3.0). TCGA PanCancer Atlas data is public and de-identified. Patterns may be studied freely. We will not copy its icons or the embedded OncoKB badges.

## Card 6 (partial): Guardant360 CDx / Guardant360 Liquid

- **Source / screen:**
  - Physician insert: https://www.guardantcomplete.com/assets/pdf/Guardant360-CDx-Physician-Insert-US.pdf (LBL-000043 R4)
  - Interpretation guide: https://www.guardantcomplete.com/assets/pdf/Guardant360-Liquid-Report-Interpretation.pdf
  - **No sample report found.** The portfolio page (https://www.guardantcomplete.com/guardant-portfolio/cdx) links none, and a third-party one-pager on ce.mayo.edu returned 403.
- **Task / state observed:** how the report *classifies* and *qualifies* results, read from regulatory text. The visual layout **could not be accessed**.
- **What the design does (OBSERVED, from text only):**
  - **"Table 2. Category Definitions"** is a five-step ladder: Category 1 CDx, Category 2, Category 3A, Category 3B, Category 4 ("Other Biomarkers with Potential Clinical Significance"). Each step is scored on three separate yes/no columns: *Prescriptive Use for a Therapeutic Product*, *Guardant360 CDx Clinical Performance* and *Analytical Performance*. Evidence strength and assay reliability are therefore kept as separate axes.
  - **Limitations** print per-drug abundance floors. The one relevant to our demo reads "LUMAKRAS efficacy has not been established in patients with KRAS G12C biomarkers < 0.11% MAF". Others give similar floors for osimertinib, amivantamab and others.
  - **Negative results are qualified:**
    - "Biomarker Negative" carries a **confidence score**. Above 90%, concordance with tissue is 96%. Below 90%, there is a >10% chance of being positive, "consideration for further testing by tissue is recommended".
    - "Not Detected … does not preclude" presence.
    - "Not Evaluable" marks low-confidence samples.
    - Subtype confidence below 10% means "below the detection limit".
  - Per the patent and Mayo snippets returned by search, the report table shows % cfDNA in descending order. This is unverified and was not viewed.
- **Why it may work for OpenOncology (INFERENCE):**
  - Separating "how good is the evidence" from "how well did we measure it" maps directly onto OpenOncology's two kinds of uncertainty: the evidence level of a drug, and the data quality of the variant (VAF, depth).
  - The MAF floor on sotorasib is a ready-made example for our gap display. If VAF is missing, we cannot say whether a known efficacy floor applies.
- **Where it could fail for OpenOncology:** the ladder is tied to FDA claim status, and three yes/no columns per finding is heavy for a hero.
- **Principle to adapt:** show evidence strength and measurement confidence as two separate, labelled properties of a result, and qualify every negative or missing result with what it does not rule out.
- **Asset origin / reuse:** © Guardant Health. Both PDFs are public and not gated. Text was read for structure only.

## Note: Tempus xT (could not access the report)

- **Observed (marketing page only)**, https://www.tempus.com/solutions/xt-cdx/:
  - A light page with an in-page left nav (Overview, Additional Features, Specimen Requirements, …) in monospaced caps, and an AI chat panel on the right.
  - The report is described in prose: an **FDA-approved xT CDx report** plus a separate **"professional services report"**, which "isn't part of the FDA approval". The latter covers TMB, CNVs, therapy and trial matching, and "leverag[es] MSK's OncoKB database and NCCN Guidelines".
  - The page also states "The tumor must be at least 20% of the sample (30% for MSI evaluation)".
- **Could not access:** the sample report and report guide (https://www.tempus.com/wp-content/uploads/2022/09/Tempus-Onco_Clinical-Report-Sample.pdf, https://tempus.com/wp-content/uploads/2024/10/Tempus-Onco_Clinical-Report-Guide.pdf) returned HTTP 429. Nothing about Tempus report layout, typography or tier colours is claimed here.
- **INFERENCE:** Tempus, like FMI and Guardant, splits regulated claims from interpretive content. This is a sectioning convention OpenOncology can borrow honestly: "what the data say" versus "what our ranker infers".

---

## Portrait report vs dashboard: what the evidence says

- **OBSERVED:** All three clinical reports we could read (FMI, Caris, and Guardant per its insert) are portrait, top-to-bottom documents. In the two we saw, the order is the same: identity and specimen, then the **headline claim with its therapy and evidence level on page 1**, then caveats, then supporting detail, then the appendix. No clinical vendor result we saw is a horizontal dashboard.
- **OBSERVED:** The knowledge bases (OncoKB, CIViC) are landscape web pages but read as vertically ordered documents: title, plain-language statement, then a table. All five sources use light backgrounds. Only cBioPortal resembles a dashboard, and it is an exploration tool that never states an answer.
- **OBSERVED:** In every source, the evidence level sits **in the same row as the drug** (FMI's NCCN box, Caris's Level column, OncoKB's level as the first column). None of them puts evidence in a separate side panel. This is about adjacency, not orientation, and it is achievable in either layout.
- **OBSERVED:** Both FMI and OncoKB order same-level drugs **alphabetically** and refuse to imply efficacy order. FMI says so explicitly. **INFERENCE:** a large-number score dashboard amplifies false precision in 0.98 vs 0.97. A report-style row with a stated ranking rule and a tie annotation ("near-tie, within-case ranking, not a response probability") fits field norms better.
- **OBSERVED:** Gaps get their own lines in clinical reports: "Disease relevant genes with no reportable alterations", "Indeterminate due to low coverage", "Cannot Be Determined", thresholds printed beside values, and negatives qualified by confidence. VUS are pushed to an appendix (FMI) or a portal (Caris). **INFERENCE:** a vertical report gives gaps a natural place (a "Limitations / not assessed" block directly under the claim), whereas a dashboard tends to drop them into tooltips.
- **INFERENCE:** a portrait report is the more credible hero for OpenOncology's audience because it maps to an artefact oncologists and researchers already read. The main risk is **looking like a regulated lab report**: patient name fields, "Final Report", signature and CLIA blocks, a "SAMPLE" watermark. Use the reading order and row grammar, not the clinical furniture, and label it as a research summary.
- **INFERENCE:** the interactive results view need not choose one or the other. Report-first vertical order with cBioPortal-style progressive disclosure (a row that expands into a CIViC-style claim-first evidence card) covers both the scan and the inspection task.

## Report section order that recurs across clinical reports

From FMI and Caris (observed in full), with Guardant consistent with what its insert describes:

1. **Running header:** brand, report status or part ("Final Report", "Professional Services"), tumour type, report date, and page n of N on every page.
2. **Identity block** in three columns: patient / ordering physician / specimen (site, type, collection and receipt dates).
3. **Headline actionable results:** alteration → therapy → evidence level in one row, with companion-diagnostic or highest-level findings first.
4. **Caveat callout:** confirmatory testing advised, trial eligibility, pointers to limitations.
5. **Other findings and cancer-type-relevant biomarkers**, including **explicit negatives** ("Not Detected", "no reportable alterations").
6. **Genomic signatures** (MSI, TMB, LOH), each with its value and threshold or scale.
7. **Therapies by context:** in the patient's tumour type vs in another tumour type, plus findings with no therapeutic options.
8. **Per-alteration interpretation:** treatment strategies, frequency and prognosis, summary, with citations.
9. **Clinical trials.**
10. **Uncertain and unassessed:** VUS, indeterminate or low-coverage genes, equivocal or subclonal calls (in the appendix, or in a portal).
11. **Methods and limitations:** specimen adequacy, assay scope, level and category definitions, ranking rule.
12. **Disclaimer, references, sign-off.**
