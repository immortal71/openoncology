# 01 · Content inventory

Captured 2026-11-27 from `/lab/atlas` (live page text), `/lab/results`, `web/lib/demo-data.ts` and `web/lib/workspace.ts`. This is the material that sets the hierarchy. Anything not listed here doesn't exist yet and can't go on the page.

## What the product actually is

- **Input:** tumour variant calls (VCF). Hosted workspace is *planned, not available*. Code is MIT and runs locally.
- **Output per case:** variants → ranked candidates grouped by OncoKB level → evidence per candidate → explicit gaps.
- **Status:** research prototype, not a medical device. Oncologist review is required. A score ranks drugs within one case and is not a response probability.
- **Proof available:** the hard benchmark gate (expected drugs in the top three for curated cases, zero false positives) and METHODS.md. There are no customers, deployments, testimonials or outcome data. None may be implied.
- **Open strategic question:** `reports/OpenOncology pivot brief.md` explores research coordinators who check that a biomarker result was available before treatment started. If that becomes the product, the primary user changes and so does this brief.

## Demo case (the only real data we have)

| Field | Value |
|---|---|
| Case | KRAS G12C · Non-Small Cell Lung Cancer · sample case, not a patient |
| Variants | KRAS p.Gly12Cys (G12C): Pathogenic, OncoKB Level 1, targetable. TP53 p.Arg175His (R175H): Pathogenic, Level 3B, not targetable |
| Candidate 1 | Sotorasib (Lumakras), CHEMBL4535757, FDA approved, score 0.9827 → 0.98, OpenTargets 0.90, sources OncoKB · OpenTargets · DiffDock · ClinicalPhase, alias AMG-510. Mechanism: covalent KRAS G12C inhibitor that locks the protein in its inactive GDP-bound state |
| Candidate 2 | Adagrasib (Krazati), CHEMBL4594350, FDA approved, score 0.9731 → 0.97, OpenTargets 0.88, alias MRTX849. Mechanism: irreversible KRAS G12C inhibitor with CNS penetration |
| Candidate 3 | Osimertinib, approved for a different indication (EGFR), 0.71, tier repurposed. Weaker or off-label evidence |
| Near-tie | Sotorasib and Adagrasib differ by 0.01 and are annotated as a near-tie |
| Gaps (10) | VAF missing, read depth missing, ClinVar review status, COSMIC count, cBioPortal cohort data, AlphaMissense class (per variant), evidence lookup source not stored, exact source records not stored, oncologist sign-off pending |
| Sources | Can query OncoKB, CIViC, ClinVar, OpenTargets, ChEMBL, AlphaMissense. This demo used OncoKB, OpenTargets, ClinVar |
| Next steps (patient copy) | Share with oncologist or tumour board; ask about KRAS + SHP2/mTOR combination trials; request full profiling if the VCF is partial |

## Copy that already works (keep and reuse)

- "Tumor mutations, matched to cancer drug evidence."
- "Why did Sotorasib rank first?"
- "Scores rank candidates within this case. They are not response probabilities."
- "Each source is checked separately. Gaps rarely get written down."
- "Every ranking follows a published rule."
- "Before you trust it."
- "Follow the evidence from variant to drug."

## Required states (the design must survive all of them)

1. **Near-tie:** two top candidates 0.01 apart. The design must not make #1 look decisively better.
2. **Missing fields:** VAF and depth absent. They must look absent, not like a loading or empty cell.
3. **Not recorded vs not assessed vs lookup failed:** three different meanings, already modelled in `workspace.ts`.
4. **Resistance (R1/R2):** blocks a drug, as with EGFR T790M and erlotinib. Not in the demo, but it is in the ladder.
5. **No targetable variant:** empty result, which escalates to Tier 2/3 repurposing or custom discovery.
6. **Long labels:** "Approved drugs, weaker or off-label evidence", "Non-Small Cell Lung Cancer", HGVS strings.
7. **Narrow viewport:** 320–390px.
8. **Pending review:** oncologist sign-off is not recorded.

## Pages and surfaces in scope

| Surface | Route | Current form |
|---|---|---|
| Marketing home | `/lab/atlas` | Hero with three-node pathway; horizontal dark product shot; three steps; lab VCF table; hospital checklist; workspace embed; OncoKB ladder; FAQ; closing |
| Case results | `/lab/results` | Dark header band; tabs (Variants 2, Candidates 3, Sources 2, Gaps 10); list on the left, detail on the right, joined by a connector |

## Prior design decisions (from `oo-art-direction` and the Codex design plan)

The palette, Inter, the evidence ribbon, "product proof from real components", and the rejected list (stock photos, H&E hero, floating card collages, icon grids, violet blooms, DNA helices, invented metrics) **still stand unless this brief overturns them with a reason.**

## Gaps in our material

- No real screen recording of the app yet.
- No user research: we haven't watched a lab director, oncologist or research coordinator use it.
- No second demo case covering resistance, no-target or long-list states, so the design can only be tested against KRAS.
- No photography or illustration assets beyond the ribbon.
