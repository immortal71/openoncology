# 02 · Design brief: OpenOncology home hero and case results

Status: **draft for review**. Nothing gets designed until a human picks a direction in §8.
Inputs: [01-content-inventory.md](01-content-inventory.md), [refs-direct-competitors.md](refs-direct-competitors.md), [refs-cross-domain.md](refs-cross-domain.md), [refs-motion-and-tooling.md](refs-motion-and-tooling.md).

## 1. Product brief

- **Surfaces.** The hero product shot on `/lab/atlas`, and the case results view (`/lab/results`) it previews.
- **Primary reader (assumed, see §8).** A molecular lab director or oncology team lead judging an open-source tool. They are expert, skeptical, and already receive a clinical genomic report (FoundationOne, Caris) for every case.
- **The one task.** *Trace a ranked therapy back to the evidence behind it, and see what is missing.*
- **They must leave knowing:**
  1. what goes in (a VCF);
  2. what comes out (ranked drugs, each with its evidence and gaps);
  3. that it's a research prototype that needs oncologist review.
- **Success (observable).**
  - In 5 seconds, a first-time reader can say what the product does.
  - In 20 seconds, they can name the evidence behind #1 and one missing item.
  - They notice that #1 and #2 are a near-tie.

## 2. Content that sets the hierarchy

Only the KRAS G12C demo case exists:

- variants: KRAS G12C (Level 1) and TP53 R175H (3B)
- candidates: Sotorasib 0.98, Adagrasib 0.97, Osimertinib 0.71
- 10 gaps
- 3 sources used

Required states:

- near-tie
- a missing field, which must read as missing and not as loading
- not recorded vs not assessed vs lookup failed
- resistance
- no target
- long labels
- 320px wide
- review pending

## 3. What the competitive teardown established (observed)

- **Every clinical genomic report studied is a portrait document read top to bottom.** These were FMI, Caris and Guardant, plus OncoKB and CIViC pages. Only cBioPortal is a dashboard, and it never states an answer.
- **Evidence sits in the same row as the drug in every source.** None of them puts it in a separate panel. That makes our current split (list on the left, evidence summary on the right) the odd one out.
- **FMI and OncoKB order drugs of the same level alphabetically, and FMI says outright that therapies are not ranked by efficacy.** A 0.98 vs 0.97 ranking therefore needs a visible rule and a tie label. Big score tiles would contradict the field's norm.
- **Gaps get their own printed lines:** "Cannot Be Determined", "Indeterminate due to low coverage", or a threshold printed beside the value. Guardant's insert says sotorasib efficacy is not established below 0.11% MAF. That is a real reason our "VAF missing" matters, worth one sentence of copy (cite it).
- **Two kinds of uncertainty are kept apart:** how strong the evidence is vs how well the variant was measured. For us that means the OncoKB level vs VAF and depth.

## 4. References that changed a decision

| Card | Decision it changes |
|---|---|
| FMI / Caris section order | The report reads in this order: header, then headline result row, then caveat, then other findings and explicit negatives, then detail, then methods. |
| FDA Highlights (LUMAKRAS) | Each drug gets **fixed slots that print "None" or "Not available"** instead of disappearing. That makes the repeating portrait block a structural need. |
| PCAOB auditor's report | **Verdict first, basis second**, and judgment calls such as the tie and the ranking rule get their own short block. |
| GRADE / Cochrane | Show evidence strength as a **position on the full scale** (1, 2, 3A, 3B, 4, R1, R2 with this one filled), using our own glyph. Hedge the wording to match. |
| eLife assessment | A tinted verdict panel sits above the detail, set in a different voice. |
| Our World in Data | A provenance line sits inside the figure, so a screenshot or shared crop still says "Demo case · sources · date". |
| Mercury footnotes | Numbered markers suit marketing claims. **Don't use them for report content**: small, low-contrast and skipped by screen readers. |
| Guardant | Keep "evidence level" and "measurement quality" in separate columns. |
| Granola / Elicit heroes | A single portrait sheet works as a product hero. Pull one evidence chip out beside it instead of scattering cards. |

## 5. Point of view

Most tools hand a clinician a ranked list and ask for trust. OpenOncology hands them **the working**: each drug printed with the same fixed slots, the evidence it cites, and the blanks it couldn't fill. The product is a document that admits what it doesn't know. The design should look like that document, a calm portrait report, not a dashboard performing intelligence.

## 6. Directions (they differ in what they make easy)

### A · The Report (report-first, portrait)

- **Organising idea.** The hero is page 1 of the case report, portrait 4:5, on paper. The results view is the same document, interactive.
- **Skeleton, top to bottom:**
  1. provenance header (Demo case · NSCLC · sources · date)
  2. verdict panel ("2 approved options, near-tie")
  3. candidate blocks, each with fixed slots (Variant · Evidence level on the full scale · Sources · Missing · Refs E1–E3)
  4. other findings, including TP53 3B and explicit negatives
  5. gaps section
  6. method and limits footer
- **Makes easy:** reading in order, sharing, seeing limitations right next to the claim.
- **Makes hard:** comparing many candidates side by side; a portrait sheet shrinks fast at hero size.
- **Motion job:** on load the page **prints in reading order**: header, verdict, Sotorasib block, then its missing slots fill in amber. A short clip shows a click on "E2" opening the evidence card beside the page.
- **Risk:** looking like a regulated lab report. Avoid patient-identity blocks, "Final Report", CLIA signatures.

### B · The Trace (claim-first, audit trail)

- **Organising idea.** Start from one claim, "Sotorasib ranked 1 of 3", and walk it backwards to its sources the way an auditor writes "basis for opinion".
- **Skeleton:**
  1. claim line
  2. ranking rule (level group, then weighted score, then near-tie)
  3. evidence record (OncoKB Level 1 on the scale, OpenTargets 0.90)
  4. source records ("exact record not stored")
  5. what's missing (VAF, depth, and why it matters)
  6. who decides (oncologist, pending)
- **Makes easy:** answering "why should I trust this?"; a story told by scrolling.
- **Makes hard:** getting the overview of the whole case; marketing-only, as it doesn't map to the daily results view.
- **Motion job:** scroll-driven. Each step pulls the next record out of the one before, one per screen.
- **Risk:** it's the current page's three-node pathway at a larger scale. It must earn the difference with real records, not decoration.

### C · The Bench (comparison-first, summary-of-findings table)

- **Organising idea.** Drugs as columns, fixed evidence slots as rows, GRADE-style. The near-tie and the gaps sit side by side.
- **Skeleton:**
  1. case header
  2. table with columns Sotorasib · Adagrasib · Osimertinib and rows Level (scale) · Variant matched · Sources · Score + tie · Missing · Resistance
  3. footnoted reasons
  4. expand a column to see the evidence
- **Makes easy:** comparing candidates, seeing the tie, scanning which slots are empty across drugs.
- **Makes hard:** a first-time visitor's 5-second read; mobile (it collapses to stacked cards).
- **Motion job:** hovering a row highlights that slot across all drugs; the clip shows sorting or expanding a column.
- **Risk:** reads as a spreadsheet; weaker as a marketing hero.

**Recommendation (to be tested, not assumed).**

- **A** for the hero and the results view.
- **B's trace** as the interaction inside A: clicking an evidence ref opens its record.
- **C** as the comparison mode in the results view once a case has more than three candidates.

## 6b. Motion and the demo clip (from refs-motion-and-tooling.md)

- **Cal.com /workflows is the closest pattern.** A pinned product panel sits beside text steps that scroll and go pending → active → done. It fits A (the page prints in order) and B (one record per step).
- **Mercury runs short tabbed MP4 loops** of 8–11 s at about 1 MB each. They play only in view, pause off-screen, have a visible play/pause control, and swap in a still under reduced motion.
- **Linear has no video**; the product is rebuilt as real DOM.
- **No site checked uses GIF, so GIF is rejected**: 256 colours, large files, no pause, no poster.
- **Recommended pipeline:**
  - Record the real `/lab/results` in demo mode with Playwright `page.screencast`, which needs Playwright 1.64 or later (the repo has 1.63).
  - Output 1080×1350 (4:5), 30 fps, a 12 s seamless loop.
  - Encode with ffmpeg (not installed yet) to WebM ≤1.2 MB plus an H.264 MP4 fallback ≤2 MB.
  - Use an AVIF poster ≤80 KB showing the final frame (evidence open, gaps in amber). The same image serves as the reduced-motion still.
- **Playback rules:**
  - No `autoplay` attribute: play only when in view and when reduced motion isn't requested.
  - A visible pause control, which is required for motion over 5 s.
- **Storyboard:**
  - Keep Adagrasib 0.97 in frame next to Sotorasib 0.98.
  - Keep "Sample case, not a patient" in frame.
  - The recording script lives under `web/`, because `scripts/**` is protected.
- **Remotion is not recommended:** a paid licence for companies with more than 3 people, and it redraws the UI instead of recording the real app.

## 7. Evaluation plan

- **Tasks**, run on each skeleton with the same content:
  1. a 5-second test: what does it do, and who is it for?
  2. find the evidence behind #1 and one missing item;
  3. is #1 clearly better than #2? (correct answer: no, near-tie);
  4. repeat tasks 1–3 at 390px.
- **Stress content:** long labels, an empty-target case, and a resistance row. We need a second demo case for these; inventing clinical values is not allowed, so it must come from a real benchmark case.
- **Criteria:**
  - task success and time;
  - wrong picks;
  - whether gaps are noticed without prompting;
  - whether anyone mistakes it for a regulated lab report.
- **Abandon A if:**
  - at hero size the portrait page is illegible without zoom; or
  - readers miss the gaps; or
  - readers read it as a clinical report from an accredited lab.
- **Open assumptions:**
  - the primary reader (§8);
  - that a recorded clip beats live DOM animation;
  - that the dark theme is no longer needed (every studied report is light).

## 8. Decisions needed from a human

1. **Primary reader.** Lab director / oncology team (current site), or the research coordinator who checks biomarker-before-treatment dates (`reports/OpenOncology pivot brief.md`)? The hero changes if the pivot happens.
2. **Pick a direction** (A, B or C) to take into Figma at higher fidelity. The skeletons for all three are drawn first.
3. **Light report vs current dark panel.** The research favours light; the current product shot is dark.
