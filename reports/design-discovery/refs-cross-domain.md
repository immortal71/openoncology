# Cross-domain references: claim beside evidence, for a skeptical reader

Design discovery, OpenOncology. Prepared 2026-11-27.

**Core task these references serve:** "Trace a ranked therapy back to the evidence behind it, and see what is missing."

**Working hypothesis being tested:** the product shot and results page should become a portrait, vertically ordered report (a document a reader scans top to bottom and could share), not a horizontal dark dashboard.

**Method and honesty notes**

- Every URL below was loaded in this session, either with a fetch tool or in a real browser pane, unless the card says otherwise.
- `OBSERVED` means seen on the page or read in its text/DOM. `INFERENCE` means my judgment about OpenOncology. They are kept in separate blocks.
- Where a page was blocked or only partly readable, the card says so.
- Cookie banners: optional cookies were rejected (OWID). The eLife banner was hidden locally in the inspection pane to read the page; no consent was given.
- No personal data was used in any search.
- Not used, and why: Nature's formatting guide redirected to a sign-in wall, so no figure-legend card. The eCFR site blocked automated fetching, so the FDA rule text comes from the Cornell LII mirror of 21 CFR 201.57. Linear's changelog was loaded, but its text-only extraction showed no claim/evidence pairing worth a card. The Stripe annual letter and Stripe/Vercel docs were not loaded, so they are not cited.

---

## Card 1. eLife Reviewed Preprint: assessment with an ordinal evidence scale

**Source and exact screen**
https://elifesciences.org/reviewed-preprints/94985 (Reviewed Preprint v2, "Molecular identification of wide-field amacrine cells in mouse retina that encode stimulus orientation"). Vocabulary definitions: https://elifesciences.org/inside-elife/db24dd46/elife-s-new-model-what-is-an-elife-assessment

**Task and state observed**
A reader decides how much to trust a paper before reading it. State: first screen of the article, then the assessment block opened with "Read more about this assessment".

**What the design does (OBSERVED)**
- The **eLife Assessment** sits *above* the abstract in a light grey tinted panel. It is a short sans-serif paragraph. The abstract below it is set in a serif face, so the two voices (editors' verdict vs. authors' claims) are told apart by typeface as well as position.
- The two rating words appear **in bold inside the prose**: "valuable" (significance) and "convincing" (strength of evidence). The verdict is a sentence, not a badge.
- The assessment has its own DOI (`…94985.2.sa4`), so the verdict can be cited separately from the paper.
- Expanding it shows two labelled rows, "Significance of findings" and "Strength of evidence". Each shows **the whole ordinal scale as a row of small chips**, and the chosen value is a filled blue chip:
  - Significance: Landmark, Fundamental, Important, **Valuable**, Useful
  - Evidence: Exceptional, Compelling, **Convincing**, Solid, Incomplete, Inadequate
  The chosen term repeats above its row with a one-line definition (for example "Convincing: Appropriate and validated methodology in line with current state-of-the-art").
- A right rail carries status with a coloured vertical bar: "Reviewed Preprint", "v2 · November 26, 2026", "Revised by authors", plus "Show previous version". Tabs read "Full text / Figures and data / Peer review".
- The scale includes negative values ("Incomplete", "Inadequate"). The vocabulary article says these are standard terms editors use "when appropriate".

**Why it may work for OpenOncology (INFERENCE)**
- Our evidence tiers (OncoKB LEVEL_1 to 4, R1/R2, `fda_approved` / `repurposed`) are an ordinal scale too. Showing the full scale with one value filled answers "how strong compared with what?" without a legend lookup. A lone badge cannot do that.
- "Verdict above the claim, in a different voice" maps to placing a short, plain-language evidence summary above each ranked drug's detail.
- A versioned, dated status rail fits a report that is re-run when knowledge bases update.

**Where it could fail for OpenOncology**
- eLife's verdict is written by human editors. Ours is computed. Bold adjectives in prose could read as editorial judgment we did not make. The generated sentence has to say where the level came from (e.g. "OncoKB Level 1").
- Two parallel scales (significance and evidence) would be too much per row in a 10-drug list. It may fit only the expanded detail of a candidate.
- Chip rows take horizontal space, which is tight in a portrait column at mobile width.

**Principle to adapt**
Show the evidence level as a position on the whole visible scale, with its one-line definition next to it, not as an isolated badge.

**Asset origin / reuse terms**
eLife article content is generally published CC BY 4.0. The site's UI design and chip styling belong to eLife and are not reusable. Use this as a pattern reference only; no screenshots in shipped work.

---

## Card 2. Cochrane / GRADE "Summary of findings" table: certainty as a graded symbol plus footnoted reasons

**Source and exact screen**
Cochrane Handbook, Chapter 14 (Completing "Summary of findings" tables and grading the certainty of the evidence): https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14 (text read; Figures 14.1.a and 14.1.b described in the text).

**Task and state observed**
A clinician or guideline panel scans what an intervention does to each outcome and how far to trust each number. State: reference description of the standard table and its alternative layout.

**What the design does (OBSERVED)**
- **One row per outcome, at most seven, ordered by importance.**
- Columns, roughly: outcomes, illustrative comparator risk, absolute and relative effect with 95% CI, number of participants (studies), **certainty of the evidence (GRADE)**, comments. Population, setting, intervention and comparison sit in a header above the table.
- Certainty uses a four-step symbol string *plus* the word: ⊕⊕⊕⊕ High, ⊕⊕⊕◯ Moderate, ⊕⊕◯◯ Low, ⊕◯◯◯ Very low. The empty circles show what is missing from a full rating.
- **Lettered footnotes** (a, b, c) attached to a rating explain each downgrade, e.g. "Due to risk of bias", "Due to imprecision and inconsistency". A serious concern drops one level, a very serious one drops two, and at most three levels can be lost.
- The alternative format pairs certainty with hedged verbs in the effect statement: moderate with "probably decreases", low with "may decrease" or "there may be little or no difference".
- Five named domains (risk of bias, inconsistency, imprecision, indirectness, publication bias) are the only allowed reasons for downgrading, and the Results section has to report the reason for each outcome.

**Why it may work for OpenOncology (INFERENCE)**
- This is the closest existing match to our task. A ranked row is a claim; the certainty mark plus lettered footnotes is "trace it back and see what is missing" in a format oncologists already know from guideline work.
- Filled/empty marks put *missing* evidence on screen as empty slots, not as absence. That fits our rule that missing data is shown explicitly (e.g. no OpenTargets score, no CIViC entry).
- The seven-row cap and ordering by importance argue for a short, opinionated first page with a "more" section, not an endless table.
- Hedged verbs tied to certainty give us a copy system: tier 1 "approved for", lower tiers "may respond", with the hedge decided by data, not by the copywriter.

**Where it could fail for OpenOncology**
- GRADE rates a *body of evidence for an outcome*. OncoKB levels rate *a biomarker-drug pair*. Borrowing ⊕ symbols could suggest a GRADE assessment we never did, which would mislead a methodologist. We need our own glyph, not GRADE's.
- Lettered footnotes depend on the reader looking down the page. In a scrolling web report, footnotes far from the row are easy to miss, so they need to sit next to the row they qualify.
- Wide tables do not fit a portrait column on a phone. The row may have to become a stacked block.

**Principle to adapt**
Give every ranked claim a graded certainty mark whose empty slots show what is missing, and attach a short lettered reason for every point it lost.

**Asset origin / reuse terms**
Cochrane Handbook text is copyright Cochrane. ⊕ notation is a GRADE Working Group convention. Reference the pattern only; do not reproduce GRADE symbols as our own rating, and do not copy tables.

---

## Card 3. FDA prescribing information "Highlights": dense hierarchy with section cross-references, explicit "None", revision dates

**Source and exact screen**
- Live instance, chosen because it matches our KRAS G12C demo case: LUMAKRAS (sotorasib) label on DailyMed, https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c80a362c-7ac3-4894-a076-0691e68ef8c1 (Highlights section read in a browser).
- Format rule: 21 CFR 201.57, read via Cornell LII, https://www.law.cornell.edu/cfr/text/21/201.57 (eCFR blocked automated fetch).

**Task and state observed**
A prescriber needs the decision-critical facts about a drug in one glance and must be able to jump to the full evidence. State: Highlights block at the top of the current label.

**What the design does (OBSERVED)**
- Opens with a required **limitation statement**: the highlights "do not include all the information needed" and point to the full prescribing information. The summary declares itself partial, up front.
- Fixed section order: name and route, "Initial U.S. Approval: 2021", RECENT MAJOR CHANGES (each with its section number and month/year, e.g. "Indications and Usage (1) 01/2025"), INDICATIONS AND USAGE, DOSAGE AND ADMINISTRATION, DOSAGE FORMS AND STRENGTHS, CONTRAINDICATIONS, WARNINGS AND PRECAUTIONS, and so on, ending with a revision date.
- **Every claim ends with a parenthetical cross-reference** to the full-label section that supports it: "(1.1)", "(2.2)", "(2.3, 5.1)".
- **Empty sections are stated, not omitted**: "CONTRAINDICATIONS — None. (4)".
- **Evidence strength is stated in the claim's own paragraph**: the NSCLC indication is "approved under accelerated approval based on overall response rate (ORR) and duration of response (DOR)", and continued approval "may be contingent upon" a confirmatory trial. The mCRC indication carries no such caveat. The caveat is attached to the claim it limits.
- Formatting rules in 201.57(d): bold headings, horizontal rules between sections, headings centred on a rule, minimum 8-point type, Highlights (boxed warning excluded) limited to half a page in two columns, and a **vertical line in the left margin** marking recently changed text.

**Why it may work for OpenOncology (INFERENCE)**
- The parenthetical cross-reference is the cheapest possible "trace it back": every line in our summary could end with a pointer (e.g. "(E2, E5)") to numbered evidence items further down the same report. Readers can check any claim without leaving the document.
- "None. (4)" is exactly our "missing data shown explicitly" rule, in a document clinicians already trust.
- Accelerated approval vs. full approval is a real distinction for our top-ranked drugs (sotorasib in NSCLC). Following the label's convention of putting the caveat inside the indication line keeps us honest and uses the regulator's own wording.
- A "recent changes" margin rule plus a revision date suits a report that re-ranks when OncoKB or CIViC data changes.

**Where it could fail for OpenOncology**
- The label is famously dense and is written for compliance as much as for reading. Copying its density would undo the craft goal.
- All-caps centred headings on rules look regulatory and dated next to a Mercury/Linear-quality marketing page.
- The label is about one drug; our report compares many drugs for one patient. The cross-reference idea carries over; the section skeleton does not.

**Principle to adapt**
End every summary claim with a cross-reference to the numbered evidence that supports it, print "None" where a section is empty, and put the limitation statement first.

**Asset origin / reuse terms**
US FDA labeling text is a US government work and the label content is public. DailyMed is an NLM service. Do not imply FDA endorsement or reproduce label pages as product imagery; quoting short label phrases with attribution is fine.

---

## Card 4. Auditor's report (PCAOB AS 3101): opinion first, basis second, judgment-heavy items called out with their own disclaimer

**Source and exact screen**
PCAOB AS 3101, "The Auditor's Report on an Audit of Financial Statements When the Auditor Expresses an Unqualified Opinion": https://pcaobus.org/oversight/standards/auditing-standards/details/AS3101 (text read in a browser; the fetch tool got a 403).

**Task and state observed**
A sceptical investor reads an independent expert's verdict on a set of numbers and needs to know where judgment entered. State: the standard's required sections and its illustrative report language.

**What the design does (OBSERVED)**
- **Fixed order with mandated titles.** Para .08: the *first* section is titled "Opinion on the Financial Statements". Para .09: the *second* is titled "Basis for Opinion". Critical audit matters (CAMs) follow under "Critical Audit Matters".
- Para .11: a CAM is a matter that is material and "involved especially challenging, subjective, or complex auditor judgment."
- Para .14: for **each** CAM the auditor must (1) identify it, (2) describe the principal considerations that made it a CAM, (3) describe how it was addressed in the audit, and (4) refer to the relevant accounts or disclosures. Every hard call is tied to the place in the statements it concerns.
- The illustrative CAM preamble states the scope limit: communicating CAMs "does not alter in any way our opinion" and the auditor is not "providing separate opinions" on them.
- A note forbids language that could be read as disclaiming or minimising responsibility, so caveats are structured, not hedged prose.

**Why it may work for OpenOncology (INFERENCE)**
- Same reading posture as ours: an expert reader who distrusts the producer. The verdict-then-basis order supports a portrait report: ranked list (opinion) first, then "Basis for this ranking" (inputs, knowledge-base versions, what was and was not checked), then "Where the ranking depended on judgment" (resistance gates, co-mutation penalties, fuzzy matches, redistributed weights).
- The four-part CAM template (what, why it was hard, how it was handled, where it touches the result) is a ready-made structure for each non-obvious ranking decision, e.g. "Erlotinib excluded: EGFR T790M resistance gate; source OncoKB R1; affects ranks 3-5."
- A fixed scope statement ("this report ranks evidence; it is not a treatment recommendation") placed where the reader meets the verdict is better than a footer disclaimer.

**Where it could fail for OpenOncology**
- Audit reports are visually plain, legalistic prose. The structure carries over; the look should not.
- Patients and caregivers may also read our report. "Critical audit matter" style is cold for them, so section names need plainer words.
- If every penalty becomes a CAM-style block, the important ones get lost. The standard limits CAMs to material, judgment-heavy matters, and we would need a similar threshold.

**Principle to adapt**
Order the report verdict, then basis, then "where judgment entered", and give each judgment-heavy ranking decision a four-part block that points to the rows it affected.

**Asset origin / reuse terms**
PCAOB standard text is public regulatory material. Reference the structure only; no PCAOB branding or imagery.

---

## Card 5. Our World in Data chart page: source line under the figure, metadata strip, key caveats, then full provenance

**Source and exact screen**
https://ourworldindata.org/grapher/life-expectancy (loaded in a browser after rejecting optional cookies; also read via fetch).

**Task and state observed**
A journalist or researcher reuses a chart and needs to know where the numbers came from, how fresh they are, and what traps to avoid. State: default chart view, scrolled to the panel below the chart.

**What the design does (OBSERVED)**
- Title in a serif display face, then a one-sentence plain definition directly under it. The defined term "Period life expectancy" is dotted-underlined (hover/expand definition).
- **A source line is part of the chart image** under the axes: "Data source: Riley (2005); Zijdeman et al. (2015); HMD (2025); UN WPP (2024)", then the canonical URL and "| CC BY". If the chart is screenshotted, its provenance travels with it.
- Below the chart, a tinted panel titled "Life expectancy — Long-run data" holds a **metadata strip**: Data source (with "with major processing by Our World in Data" as a link), Unit, Date range "1543-2023", Last updated "2025-10-22", **Next expected update "2026-12-27"**, and a named "Managed by" person.
- Three short **key-point bullets** follow, including caveats (e.g. large drops from famines and pandemics), then "Show more" for definitions and how crisis deaths are recorded.
- Further down: an FAQ on processing ("Notes on our processing step for this indicator"), "Data sources" with one collapsible entry per source (retrieval details, original citation), "How to cite this page / this data", downloads (CSV plus metadata JSON plus README), and a Data API.
- Licence: OWID's own charts and data are CC BY 4.0. Third-party data stays under each provider's terms.

**Why it may work for OpenOncology (INFERENCE)**
- A shared or screenshotted ranked list loses its context. A source-and-version line *inside* the report header (knowledge-base names, versions, run date, "static table, no OncoKB token") would travel with every screenshot and PDF.
- "Last updated / Next expected update / Managed by" maps to knowledge-base snapshot dates and pipeline version, and makes staleness visible.
- The layering (one-line definition, then three key caveats, then full provenance on demand) is a good model for what goes above the fold vs. what lives under disclosure.
- "With major processing by" is an honest phrase for our composite score: the sources are named, and so is our transformation of them.

**Where it could fail for OpenOncology**
- OWID has one indicator per page. We have many drugs, each with its own sources. A per-drug provenance block repeated ten times would be noisy, so provenance probably has to be split between report level and drug level.
- The page gets long. A clinician looking for the top three options must not scroll past provenance first.
- The chart-first layout assumes a visual quantity. Our core object is a ranked list, not a chart.

**Principle to adapt**
Put a compact, versioned source line inside the shareable unit itself, and give snapshot date and next refresh their own labelled fields.

**Asset origin / reuse terms**
OWID charts, data and code are CC BY 4.0 (credit required). Third-party data in the charts keeps its original licence. The OWID interface is a pattern reference; no reuse of their UI or brand.

---

## Card 6. Mercury marketing site: numbered footnote markers on claims, collected disclosures at the end

**Source and exact screen**
https://mercury.com/ (home page, read in a browser; DOM inspected for footnote markup). The full-page footer screenshot rendered blank in the inspection pane, so the visual treatment of the footnote list is from DOM values, not from a picture.

**Task and state observed**
A founder evaluates bold financial claims (yield, FDIC coverage, cashback) and needs to know the conditions. State: home page, default.

**What the design does (OBSERVED)**
- Footnote markers sit **directly after the claim they qualify**, including the hero headline ("…experience banking", linked to `#footnote-business-not-a-bank-2026`) and figures like "earn up to 4.31% yield", "1.5% cashback", "1 in 3 Startups choose Mercury".
- The markers are `<sup aria-hidden="true">` elements **numbered by a CSS counter**, so the numbers follow reading order automatically and repeat when one disclosure covers several claims. Each marker is a link to an anchored footnote.
- A short general disclaimer sits directly under the hero sign-up form.
- Disclosures are collected in an **ordered list of 8 items** under "Disclaimers and footnotes" at the very end of the page, after the footer links, in 12px light text on a dark ground. The first item begins "Mercury is a fintech company, not an FDIC-insured bank."

**Why it may work for OpenOncology (INFERENCE)**
- It is the founder's stated craft benchmark, and it shows that a premium marketing page can carry dense caveats without visual noise: small numbered superscripts, auto-numbered, linked.
- A marketing claim like "every drug traced to its evidence" or a benchmark figure (Hit@3, P@3) needs exactly this treatment: a numbered note pointing to the method and holdout definition.
- Automatic counter numbering means caveats cannot drift out of order as copy changes, which matters because our benchmark claims are protected and must stay accurate.

**Where it could fail for OpenOncology**
- Mercury's footnotes are legal compliance, placed far from the claims and in low-contrast small type. For a clinical-evidence tool, moving caveats to the bottom in 12px grey would contradict "missing data shown explicitly". It suits marketing claims, not report content.
- `aria-hidden` markers mean screen-reader users may never meet the link to the caveat. We should not copy that.

**Principle to adapt**
On the marketing page, attach an auto-numbered, linked note to every quantitative or clinical claim, but inside the report itself keep caveats next to the row they limit.

**Asset origin / reuse terms**
Mercury's site design, copy and brand are proprietary. Pattern reference only; no copying of layout, type, or copy.

---

## Editorial / typographic references: portrait document as a marketing hero

### E1. Granola home page hero: a portrait note card as the product shot

**Source:** https://www.granola.ai/ (loaded in a browser, first screen at roughly 800px wide).

**OBSERVED**
- Two columns. Left: a large serif display headline ("The AI notepad for back-to-back meetings") over two short sans lines, one primary button, and a platform note.
- Right: the product shot is **a single portrait card, taller than it is wide**, on a warm off-white ground with minimal window chrome (three dots). Inside: a serif document title ("Q3 GTM sync"), a small metadata chip row (date, attendee count), a couple of short note lines, a caret, and a quiet "Transcribing" pill at the bottom.
- The card overlaps a saturated abstract artwork behind it on the right edge, and two video-call thumbnails overlap its lower right corner, which adds depth without a dashboard.
- Most of the card is empty space. The document is shown being written, not as a finished report.

**INFERENCE for OpenOncology**
- Shows that a portrait "paper" card can carry a premium hero on its own, with serif title, metadata chips and a lot of air, and that it reads as a document, not an app.
- Our version would be a single report page: case header (KRAS G12C, tumour type, run date, sources), a short ranked list, one expanded evidence trace. The overlapping secondary element could be one evidence item pulled out of the page.
- Risk: Granola's empty card works because note-taking is light. Our report is dense, so the card has to be cropped to the top third (header plus top three ranks) or it turns into a wall of text at hero size.

**Reuse terms:** Granola's design, artwork and photography are proprietary. Composition reference only.

### E2. Elicit home page hero: a research output sheet with inline citation chips

**Source:** https://elicit.com/ (loaded in a browser; the hero is an animated loop).

**OBSERVED**
- Serif headline ("AI for Scientific Research") centred over a short sans subline and one button.
- Below it, a large rounded panel with a pale green stippled texture holds the product. The loop: a prompt box ("What is the competitive landscape for oral GLP-1 agonists"), then a white document sheet appears with a table (drug, company, mechanism, status). **Cells carry small inline source chips** such as "Wharton 2025" placed right after the statement they support. Then the result collapses into an attachment ("Oral GLP-1 receptor agonist competitive landscape — Table") and the next prompt begins.
- The output sheet is white on the tinted ground, so it reads as paper inside a frame.

**INFERENCE for OpenOncology**
- The closest marketing-hero precedent for "claim with its source attached, at hero scale": the citation chip is visible even at marketing size, which proves the trace is not hidden.
- The prompt-then-document sequence maps to our VCF-in, report-out story and could justify a two-beat hero (file in, then report page).
- Caveat: Elicit's output is a **landscape table**, not a portrait page, so it supports the citation-chip idea more than the portrait hypothesis. It is also an animated loop. A still capture loses the story, and motion has to respect reduced-motion settings.

**Reuse terms:** Elicit's design and content are proprietary. Pattern reference only.

**Gallery note:** A search for report-style heroes on Land-book, Siteinspire and Godly returned no results from those galleries, and Dribbble was not tried, so both editorial references are live sites loaded directly.

---

## Principles that should change our layout decisions

1. **Order the report verdict, then basis, then judgment calls** (Card 4, auditor's report). The portrait report should open with the ranked list, follow with "Basis for this ranking" (inputs, knowledge-base versions, what was not checked), then a short "Where the ranking depended on judgment" section. This supports the portrait hypothesis directly: the order is a reading order, which a horizontal dashboard cannot enforce.

2. **Every summary line ends with a pointer to numbered evidence in the same document** (Card 3, FDA Highlights). Give evidence items stable numbers (E1, E2…) further down the page and end each ranked claim with "(E2, E5)". That is the minimum trace-back mechanism, and it survives print, PDF and screenshot, unlike hover or side panels.

3. **Show evidence strength as a position on the whole scale, not a lone badge** (Card 1, eLife; Card 2, GRADE). Use our own glyph (not GRADE's ⊕) with filled and empty slots across the OncoKB tiers, plus a one-line definition. Empty slots make missing evidence visible in the row itself.

4. **Missing sections print "None" or "Not available", with the reason, and are never left out** (Card 3, "Contraindications: None. (4)"; Card 2, footnoted downgrades). Fixed slots per drug (approval status, resistance, trial evidence, pathway support) are always present. That makes a portrait layout with a repeating per-drug block a structural requirement, not a style preference.

5. **Caveats sit inside the claim they limit; footnotes are for marketing claims only** (Card 3, accelerated-approval sentence; Card 6, Mercury). In the report, "accelerated approval based on ORR/DOR" belongs in the sotorasib row. On the marketing page, benchmark numbers (Hit@3, P@3) get auto-numbered, linked notes to the method, and unlike Mercury's markers those notes are reachable by screen readers.

6. **The shareable unit carries its own provenance line** (Card 5, OWID). The report header, and the hero product shot, should include a compact line: knowledge-base names and snapshot dates, pipeline version, run date, static-table vs. live mode, and a scope statement ("ranks evidence; not a treatment recommendation", Card 4). A screenshot of the top third must still say where it came from.

7. **Cap the first page at about seven ranked rows, ordered by importance, with the rest behind "more"** (Card 2, GRADE seven-outcome limit). This keeps the portrait report scannable and gives the hero a natural crop: header plus top three.

8. **Hero: one portrait paper page, cropped, with one evidence item pulled out beside it** (E1, Granola; E2, Elicit). Use a light, off-white page with a serif title and metadata chips on a quiet ground, show one inline source chip at legible hero size, and make one detached element the evidence trace. Do not use a full dark dashboard. Unless the founder asks for motion, prefer a still composition: a still image works in a shared screenshot, and a loop does not.
