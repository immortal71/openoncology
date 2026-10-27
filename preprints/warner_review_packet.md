# OpenOncology ranker — 20-case review for Dr. Jeremy Warner

**For:** Jeremy Warner, MD, MS <br>
**From:** Aashish Kharel (aashish@oncopurpose.com) <br>
**Date:** 2026-10-27 · Scheduled call: Friday 8:45 PM Kathmandu / 11:00 AM Eastern

## What this is

A 20-case packet from the MSK CHORD benchmark (2,505 patients, Memorial Sloan Kettering, Nature 2024) where OpenOncology, an open-source variant-to-drug ranker, scored its top three against the drug the patient actually received. On this cohort the ranker's top three contained a drug of the correct molecular class for 2,466 of 2,466 scored patients (100%) and the exact drug the patient received for 2,094 of 2,466 (85%). The scorer, cohort filter, and OncoKB-only baseline comparison are at github.com/immortal71/openoncology.

I would like your read on 20 cases, grouped as:

- **10 exact hits** across six genes and five cancer types. The question: is the top-ranked drug clinically reasonable, or is a different drug in the class the better pick?
- **5 class-only hits** (top three in the right class but not the exact drug the patient received). The question: is OpenOncology's pick clinically wrong, or is MSK's pick a later-line or combination choice that a first-line decision support tool should not try to mimic?
- **5 drop-outs** (benchmarkable patients where the ranker returned nothing). The question: for a rare TSC/MET/CDK6/BRAF point mutation, what should a decision support tool return — "no recommendation" or a cautious off-label suggestion with lower confidence?

Grades are freeform. The format I would find most useful: for each case, one of {reasonable, debatable, wrong} plus a sentence of why. All 20 should fit in 15 minutes of your time if you want to batch it, less if you prefer to skim.

## Scoring key (so I can tally)

- **reasonable** — you would be comfortable with this top-three in front of a tumor board, as information.
- **debatable** — the top-three is defensible but not what you would pick first in 2026.
- **wrong** — the top-three would lead a non-specialist clinician in the wrong direction.

## The 20 cases

### Group A — exact hits (10)

| # | Patient | Cancer | Qualifying alteration | Received | OpenOncology top-3 | Your grade |
|---|---|---|---|---|---|---|
| 1 | P-0000036 | NSCLC | ROS1-SLC34A2 fusion | CRIZOTINIB | crizotinib, entrectinib, lorlatinib |  |
| 2 | P-0000205 | NSCLC | EGFR L858R | ERLOTINIB | osimertinib, erlotinib, gefitinib |  |
| 3 | P-0000289 | NSCLC | MET exon 14 splice | CRIZOTINIB | capmatinib, tepotinib, crizotinib |  |
| 4 | P-0000557 | NSCLC | ALK-EML4 fusion | ALECTINIB (also CRIZOTINIB, ERLOTINIB) | alectinib, brigatinib, crizotinib |  |
| 5 | P-0000584 | Breast | BRCA2 S1982Rfs*22 | OLAPARIB (+ PALBOCICLIB) | olaparib, niraparib, rucaparib |  |
| 6 | P-0000830 | Breast | PIK3CA H1047L | ALPELISIB (+ PALBOCICLIB) | alpelisib, fulvestrant, inavolisib |  |
| 7 | P-0000933 | CRC | BRAF G469A | DABRAFENIB + TRAMETINIB | trametinib, encorafenib, binimetinib |  |
| 8 | P-0002079 | NSCLC | MTOR L2383F | EVEROLIMUS | everolimus, temsirolimus, sapanisertib |  |
| 9 | P-0002273 | Prostate | ATM C633fs | OLAPARIB | olaparib, niraparib, rucaparib |  |
| 10 | P-0002382 | Prostate | BRCA1 X71 splice | OLAPARIB | olaparib, niraparib, rucaparib |  |

### Group B — class-only hits (5)

| # | Patient | Cancer | Qualifying alteration | Received | OpenOncology top-3 | Your grade |
|---|---|---|---|---|---|---|
| 11 | P-0000058 | Breast | ERBB2 amplification | LAPATINIB (+ ABEMACICLIB) | trastuzumab, pertuzumab, trastuzumab deruxtecan |  |
| 12 | P-0000165 | NSCLC | EGFR L861Q | ERLOTINIB | osimertinib, afatinib, dacomitinib |  |
| 13 | P-0000208 | NSCLC | KIF5B-RET fusion | CABOZANTINIB | selpercatinib, pralsetinib, vandetanib |  |
| 14 | P-0000616 | CRC | BRAF V600E | VEMURAFENIB | encorafenib + cetuximab, trametinib, dabrafenib |  |
| 15 | P-0007076 | Pancreatic | KIT S239F | SUNITINIB | imatinib, regorafenib, ripretinib |  |

### Group C — drop-outs (5)

| # | Patient | Cancer | Qualifying alteration | Received | OpenOncology top-3 | Your grade |
|---|---|---|---|---|---|---|
| 16 | P-0000731 | NSCLC | MET S204Ifs*12 (frameshift) | CRIZOTINIB | — (no prediction) |  |
| 17 | P-0001313 | Pancreatic | TSC1 T578S | EVEROLIMUS | — (no prediction) |  |
| 18 | P-0001372 | Breast | TSC2 A289V | EVEROLIMUS | — (no prediction) |  |
| 19 | P-0007997 | CRC | BRAF P403Lfs*8 (frameshift) | DABRAFENIB + TRAMETINIB | — (no prediction) |  |
| 20 | P-0030800 | Breast | CDK6 R46Q | PALBOCICLIB | — (no prediction) |  |

## What I will do with your grades

I will add a line to the deck and the Research Square preprint of the shape "Jeremy Warner, MD, MS reviewed 20 benchmark cases; agreed with the top-three as a reasonable decision-support surface in X of 20." I will share the exact wording with you for sign-off before I use it anywhere. If you prefer not to be named, I will fold your feedback into methodological changes to the ranker and credit you in the acknowledgements only.

## What I am not asking

I am not asking you to endorse OpenOncology for clinical use. I am not asking you to recommend it to anyone. I am asking you to tell me where it fails on the cases above, so the next version is better and the deck represents its limits honestly.

Thank you for the time.
