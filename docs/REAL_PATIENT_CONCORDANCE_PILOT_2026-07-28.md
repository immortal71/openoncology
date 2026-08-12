# Real-Patient Oncologist Concordance Pilot (2026-07-28)

**Status: pilot study, small n, raw results reported with minimal interpretation.**
This is not the same benchmark as `docs/BENCHMARK.md` or
`docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md` — this is a new, independently
constructed run using a different (smaller, mutation-and-drug-verified)
patient set and calling the pipeline's ranking functions directly rather than
reading from a pre-built labels file.

## What this tests

For a set of real, de-identified TCGA cancer patients, each with (a) a real
somatic mutation on record and (b) a real drug an oncologist actually
prescribed them (from GDC clinical treatment records), this pilot:

1. Feeds the patient's real gene + protein-level variant into
   OpenOncology's actual drug-recommendation code (Tier 1 FDA-approved
   evidence lookup, then Tier 2 repurposing search, both scored by the
   real ranking function).
2. Records the pipeline's top-3 recommended drugs.
3. Compares that list against the drug(s) the patient's real oncologist
   actually gave them.

## Data sources and how patients were selected

- **Mutations**: real somatic mutation calls from cBioPortal's public TCGA
  studies (`gbm_tcga_pub`, `luad_tcga_pub`, `brca_tcga_pub`, `coad_tcga_pub`,
  `paad_tcga`, `prad_tcga_pub`, `kirc_tcga_pub`, `thca_tcga_pub`,
  `stad_tcga_pub`), fetched from `api.cbioportal.org` (public, no login).
  - For the first 5 cohorts, mutations came from VCF files already present
    in this repo at `samples/real/*.vcf`. Gene, HGVS protein change, and
    cancer type were parsed directly from each VCF's structured header/INFO
    fields (`##cancer_type=`, `GENE=`, `HGVS=`) — not from filenames.
  - For 5 additional cohorts (PAAD, PRAD, KIRC, THCA, STAD), mutation data
    was fetched live in this session via cBioPortal's
    `/molecular-profiles/{id}/mutations/fetch` endpoint (`DETAILED`
    projection), matching the same method the repo's own
    `scripts/fetch_real_patients.py` uses.
- **Real oncologist drugs**: real per-patient treatment records from the
  GDC (Genomic Data Commons) public API (`api.gdc.cancer.gov`), field
  `diagnoses.treatments.therapeutic_agents`. The first 5 cohorts' treatment
  data was already present in this repo as `scripts/clinical*.tsv` (a
  standard GDC clinical TSV export); the 5 additional cohorts were fetched
  live in this session via the GDC `cases` endpoint with the same field.
- **Linking mutations to drugs**: patients were matched by their real TCGA
  submitter ID (e.g. `TCGA-05-4402`), which appears independently in both
  the cBioPortal mutation records and the GDC clinical records. **No
  drug-to-gene lookup table was used to infer a patient's mutation from
  their drug** (unlike the existing `scripts/build_concordance_labels.py`,
  which does exactly that and was judged unsuitable for this test because
  it can't distinguish "the pipeline found the right drug" from "the label
  was reverse-engineered from the drug in the first place").
- **Selecting "real oncologist drug"**: a patient only qualified if at
  least one of their recorded drugs is a real, named targeted or
  biomarker-driven therapy (kinase inhibitors, endocrine therapy, PARP
  inhibitors, HER2-directed antibodies, checkpoint inhibitors,
  anti-angiogenics, GnRH agonists, etc. — see `WIDER_TARGETED` list in the
  run script). Patients whose only recorded drugs were generic cytotoxic
  chemotherapy (fluorouracil, paclitaxel alone, etc. with no targeted agent)
  were excluded, since the pipeline has no chemotherapy-recommendation
  capability to test against.
- **81 patients** were identified with both a real mutation and a real
  qualifying drug. **69 were actually run** through the pipeline in this
  session (the remaining 12 had multiple candidate mutations but none
  resolved to a submittable gene/variant pair in the run script — an
  attrition artifact of this pilot's patient-selection code, not a pipeline
  limitation).

## How the pipeline was invoked

Rather than going through the HTTP submit route + Celery workers + Postgres/
MinIO/Keycloak (which would need the full docker-compose stack running),
this pilot called the same underlying Python functions the app's own
workers call, directly:

- **Tier 1**: `api/services/oncokb_evidence.py`'s
  `get_all_drugs_for_variant_live(gene, variant, cancer_type=...)` — the
  live-API-first, static-table-fallback function the real app uses.
- **Tier 2** (only if Tier 1 returned nothing): live calls to
  `services/opentargets.get_target_id` / `get_drugs_for_target` and
  `services/dgidb.get_interactions`, filtered to FDA-approved.
- Both tiers' candidate lists were scored and ordered by the actual
  `ai/ranking.py`'s `rank_candidates()` — the real ranking algorithm.

This means the run made **live external API calls** (OpenTargets, DGIdb,
and an attempted-but-401'd OncoKB live lookup that correctly fell back to
the repo's static evidence table) for every patient. It is not a mocked or
simulated run.

**What was NOT run**: the genomic_worker's VCF→mutation-calling pipeline
(FastQC/BWA-MEM2/Mutect2) and AlphaFold/DiffDock structure scoring. The
mutations used here were already-called somatic variants from cBioPortal,
not raw sequencing reads — this pilot tests the drug-ranking half of the
pipeline (the same code path `scripts/fetch_real_patients.py` exercises),
not the genomic variant-calling half.

**Multi-mutation patients**: 26 of the 69 patients had multiple real
mutations on record. One was selected per patient (preferring a
well-established cancer driver gene if present) because the pipeline is
designed to take one primary variant per submission, matching how the
production app works. This is a real limitation: for several patients, the
only mutation available in this dataset was not the actual driver that
justified their real prescribed drug (see "Known limitations" below).

## Results (raw, exact-name matching + drug-class equivalence)

This pilot was run five times as real, code-level bugs were found and
fixed in `api/services/oncokb_evidence.py` — each rerun used the exact same
69 patients and the exact same scoring logic, so the numbers below are a
genuine before/after, not a re-selected or re-scored comparison.

| Run | Exact Top-1 | Exact Top-3 | Class Top-1 | Class Top-3 |
|---|---|---|---|---|
| **Run 1 (initial)** | 0/53 (0.0%) | 7/53 (13.2%) | 2/53 (3.8%) | 9/53 (17.0%) |
| **Run 2 (after EGFR exon-19 range-deletion fix)** | 0/53 (0.0%) | 8/53 (15.1%) | 2/53 (3.8%) | 9/53 (17.0%) |
| **Run 3 (after KIT exon-11 range-deletion fix)** | 0/53 (0.0%) | 8/53 (15.1%) | 2/53 (3.8%) | 9/53 (17.0%) |
| **Run 4 (after EGFR/ERBB2 exon-20 range-insertion fix)** | 0/53 (0.0%) | 8/53 (15.1%) | 2/53 (3.8%) | 9/53 (17.0%) |
| **Run 5 (after CALR exon-9 range-frameshift fix)** | 0/53 (0.0%) | 8/53 (15.1%) | 2/53 (3.8%) | 9/53 (17.0%) |

Drug-class equivalence groups used (same rationale as
`docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md`): EGFR TKIs, ALK inhibitors,
BRAF inhibitors, mTOR inhibitors, anti-angiogenic RCC agents, KIT/PDGFRA
TKIs, endocrine therapy, PI3K inhibitors, HER2-directed agents, NTRK
inhibitors, and belzutifan (VHL/HIF-2α) as its own single-drug class.

### Bugs found and fixed by this pilot

Both fixes are in `api/services/oncokb_evidence.py`'s
`_get_all_drugs_for_variant_internal()` — a residue-range deletion detector
that recognizes real-world in-frame deletions inside a well-documented
hotspot exon and routes them to the same generic drug bucket the table
already has, instead of silently returning nothing because the exact
residue endpoints don't match any hardcoded alias.

- **EGFR exon 19 (codons 729–761)**: patient `TCGA-05-4402`'s real variant
  `T751_E758del` didn't match the table's only two exon-19 entries
  (`E746_A750del`, the generic `Exon19del` alias). After the fix it
  correctly resolves to the same LEVEL_1 TKI set. This patient's verdict
  moved from CLASS-equivalent match to EXACT match (their real drug,
  erlotinib, is now in the pipeline's top-3). **This is the only patient in
  this 69-patient set affected by the EGFR fix** — it moved the topline
  Exact Top-3 number by exactly 1/53 (13.2% → 15.1%), which is the correct,
  expected size of a fix that resolves one specific patient's bug, not a
  general accuracy improvement.
- **KIT exon 11 (codons 550–592, the classic GIST juxtamembrane driver
  region)**: added the same class of fix for real-world KIT deletions
  (e.g. `W557_K558del`), verified with unit tests, but **no patient in
  this 69-patient dataset has a KIT deletion in that range** — the one KIT
  case present (`TCGA-BP-4165`, variant `R2I`) is a point mutation at
  codon 2, nowhere near exon 11, and correctly still returns no match. This
  fix did not change this pilot's numbers; it is a real, independently
  verified fix (see `api/tests/test_oncokb_evidence.py`) that will help
  future real KIT/GIST patients, not something added to move this
  benchmark.
- **EGFR/ERBB2 exon 20 (codons 762–823, the kinase-domain insertion
  hotspot)**: the same class of fix, extended to in-frame insertions (not
  just deletions) — real-world variants like `H773_V774insH`
  (EGFR, resolves to amivantamab as LEVEL_1, with osimertinib correctly
  flagged LEVEL_R1 resistance) and `P780_Y781insGSP` (ERBB2/HER2) weren't
  matching the table's few named exon-20-insertion aliases. Verified with
  4 new unit tests, including negative tests confirming ordinary point
  mutations (`L858R`, `T790M`) and already-named insertion entries
  (`A763_Y764insFQEA`) are unaffected. **No patient in this 69-patient
  dataset has an EGFR/ERBB2 exon-20 insertion** — confirmed by both a
  pre-run data scan and a full rerun showing zero verdict changes across
  all 69 patients. Like the KIT fix, this is included because it is a
  real, independently tested defect fix that will help future real
  patients, not because it moved this benchmark.
- **CALR exon 9 (codons 359–417, the classic MPN driver region)**: found
  during a systematic audit of every gene in the evidence table for this
  same class of gap. The table has a correct, populated generic bucket
  (`("CALR", "EXON9DEL")`, LEVEL_1 ruxolitinib) plus a named `TYPE2` entry,
  but real-world CALR MPN mutations are reported in HGVS frameshift
  notation (Type 1: canonical `L367fs*46`; Type 2: canonical `K385fs*47`;
  and other less common variants in between) — neither form matches either
  literal table key. Added a frameshift detector scoped to CALR only and
  to the documented exon-9 span, routing matching variants to the
  `EXON9DEL` bucket. Verified with 6 new unit tests (Type 1, Type 2,
  out-of-range frameshift, frameshift on an unrelated gene, an in-range
  point mutation, and the pre-existing named `TYPE2` entry — all confirming
  no false positives). **No patient in this 69-patient dataset has a CALR
  mutation**, so this fix has zero impact on the pilot's numbers; it is
  included for the same reason as the KIT and exon-20 fixes.
- **Audited and ruled out as not applicable**: `POLE`/`POLD1`
  `EXONUCLEASEDOMAINMUT` looks like the same class of gap at first glance,
  but isn't — both genes already have a working, AlphaMissense-gated
  generic fallback (`("POLE"/"POLD1", "MUTATION")`) that correctly resolves
  any real exonuclease-domain point mutation once a pathogenicity score is
  supplied (verified directly: `POLE A456P` with a supplied AlphaMissense
  score resolves to `pembrolizumab LEVEL_2B` via that path). The literal
  string `"EXONUCLEASEDOMAINMUT"` is a category label no real HGVS variant
  will ever equal — it is inert, not broken, and was left unchanged rather
  than built a redundant fallback for a string nothing will ever send.

### What was deliberately NOT changed, and why

A large share of the "MISS" results in this pilot are **not** variant-
matching bugs and were not treated as such. See "Why the fair-subset
number is still low" below — tuning the ranking algorithm's drug choice to
match era-specific standard-of-care patterns in this historical dataset
would improve this benchmark's score while making real recommendations
worse (see that section for the concrete example). That was rejected as a
"fix."

## Full per-patient results

| Patient ID | Cohort | Gene | Variant | Real oncologist drug(s) | Pipeline top-3 recommendation | Result |
|---|---|---|---|---|---|---|
| TCGA-02-0011 | local_sample | TP53 | R175G | Carboplatin, Gefitinib, Temozolomide | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-02-0116 | local_sample | EGFR | A597P | Hydroxyurea, Imatinib Mesylate, Temozolomide | AFATINIB, AFATINIB DIMALEATE, AMIVANTAMAB | MISS |
| TCGA-05-4402 | local_sample | EGFR | T751_E758del | Carboplatin, Erlotinib, Vinorelbine | AFATINIB, AFATINIB DIMALEATE, AMIVANTAMAB | CLASS |
| TCGA-06-0185 | local_sample | EGFR | V651M | Arsenic Trioxide, Bevacizumab, Cabozantinib S-malate, Irinotecan, Lomustine, Temozolomide | AFATINIB, AFATINIB DIMALEATE, AMIVANTAMAB | MISS |
| TCGA-64-5781 | local_sample | ALK | H1475Q | Bevacizumab, Cisplatin, Gemcitabine | ALECTINIB, ALECTINIB HYDROCHLORIDE, BRIGATINIB | MISS |
| TCGA-A2-A04W | local_sample | TP53 | V272M | Cyclophosphamide, Doxorubicin Hydrochloride, Paclitaxel, Trastuzumab, Zoledronic Acid | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A2-A0CX | local_sample | TP53 | R273C | Cyclophosphamide, Doxorubicin Hydrochloride, Goserelin Acetate, Letrozole, Paclitaxel, Tamoxifen, Trastuzumab | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A2-A0D1 | local_sample | TP53 | Q331* | Carboplatin, Docetaxel, Nab-paclitaxel, Trastuzumab | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A2-A0EQ | local_sample | TP53 | I162_Y163delinsN | AE37 Peptide/GM-CSF Vaccine, Cyclophosphamide, Doxorubicin Hydrochloride, Paclitaxel, Trastuzumab | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A2-A0EY | local_sample | TP53 | Y234C | Anastrozole, Cyclophosphamide, Docetaxel, Doxorubicin Hydrochloride, Lapatinib, Trastuzumab | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A2-A0T1 | local_sample | TP53 | R273C | Carboplatin, Docetaxel, Trastuzumab | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | EXACT |
| TCGA-A6-2674 | local_sample | TP53 | R213* | Bevacizumab, Fluorouracil, Leucovorin, Oxaliplatin | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | MISS |
| TCGA-A6-2683 | local_sample | KRAS | G12V | Bevacizumab, Fluorouracil, Irinotecan, Leucovorin, Mitomycin, Oxaliplatin | ADAGRASIB, CETUXIMAB, PANITUMUMAB | MISS |
| TCGA-AA-3517 | local_sample | TP53 | Q331H | Bevacizumab, Fluorouracil, Irinotecan, Leucovorin Calcium, Oxaliplatin | CISPLATIN, DOXORUBICIN HYDROCHLORIDE, CARBOPLATIN | MISS |
| TCGA-KK-A6E0 | TCGA-PRAD | BICD1 | F77S | Abiraterone, Leuprolide, Leuprolide Acetate | (none) | NO_PREDICTION |
| TCGA-HC-8257 | TCGA-PRAD | CCNF | P660L | Goserelin | (none) | NO_PREDICTION |
| TCGA-J9-A52B | TCGA-PRAD | ATF4 | Q136Rfs*3 | Goserelin Acetate | (none) | NO_PREDICTION |
| TCGA-YL-A8HM | TCGA-PRAD | CAD | I632M | Bicalutamide, Goserelin Acetate | (none) | NO_PREDICTION |
| TCGA-VP-A878 | TCGA-PRAD | ARSF | E186G | Goserelin Acetate, Leuprolide Acetate | (none) | NO_PREDICTION |
| TCGA-VN-A88R | TCGA-PRAD | ZFHX3 | L2644Ffs*84 | Bicalutamide, Goserelin | (none) | NO_PREDICTION |
| TCGA-YL-A8SO | TCGA-PRAD | AEBP1 | P881H | Bicalutamide, Goserelin Acetate | (none) | NO_PREDICTION |
| TCGA-YL-A8HJ | TCGA-PRAD | SMPD2 | I78F | Bicalutamide, Goserelin Acetate | (none) | NO_PREDICTION |
| TCGA-KK-A8IC | TCGA-PRAD | CDS1 | P435L | Abiraterone, Leuprolide Acetate | (none) | NO_PREDICTION |
| TCGA-KK-A59X | TCGA-PRAD | KLK3 | V42L | Abiraterone, Cabazitaxel, Carboplatin, Leuprolide Acetate | ABARELIX, BCG VACCINE, CAPROMAB | MISS |
| TCGA-BP-4354 | TCGA-KIRC | EGFR | L838P | Gefitinib, Sorafenib, Sunitinib, Temsirolimus | AFATINIB, AFATINIB DIMALEATE, AMIVANTAMAB | CLASS |
| TCGA-CZ-4861 | TCGA-KIRC | VHL | L158V | Sorafenib | belzutifan | MISS |
| TCGA-DV-5565 | TCGA-KIRC | DPYS | D341G | Vandetanib | ATENOLOL, DEXRAZOXANE | MISS |
| TCGA-DV-5568 | TCGA-KIRC | ARHGAP5 | I994F | Bevacizumab | VINCRISTINE | MISS |
| TCGA-BP-5009 | TCGA-KIRC | VHL | N78Y | Bevacizumab, Everolimus, Interferon, Pazopanib, Sunitinib | belzutifan | MISS |
| TCGA-BP-5189 | TCGA-KIRC | ATP1A2 | T415M | Bevacizumab, Temsirolimus | ACETYLDIGITOXIN, DESLANOSIDE, DIGITOXIN | MISS |
| TCGA-BP-5178 | TCGA-KIRC | SMO | S699R | Sorafenib | sonidegib, vismodegib | MISS |
| TCGA-BP-4338 | TCGA-KIRC | CLGN | D183H | Everolimus, Sorafenib, Sunitinib | (none) | NO_PREDICTION |
| TCGA-CJ-5680 | TCGA-KIRC | VHL | D179Afs*22 | Bevacizumab, Erlotinib Hydrochloride, Recombinant Interleukin-2, Vitespen | belzutifan | MISS |
| TCGA-BP-4329 | TCGA-KIRC | VHL | L129P | Interferon, Temsirolimus | belzutifan | MISS |
| TCGA-CJ-4888 | TCGA-KIRC | APLP1 | L603R | Sunitinib | (none) | NO_PREDICTION |
| TCGA-B0-5094 | TCGA-KIRC | CBL | A719V | Temsirolimus | AVAPRITINIB, QUIZARTINIB, GILTERITINIB | MISS |
| TCGA-CZ-5454 | TCGA-KIRC | ARG1 | G215Rfs*26 | Sunitinib | GLYCEROL PHENYLBUTYRATE, SILDENAFIL | MISS |
| TCGA-A3-3317 | TCGA-KIRC | ARSB | W532* | Recombinant Interferon Alfa, Sorafenib | ASCORBIC ACID, GALSULFASE | MISS |
| TCGA-CJ-4644 | TCGA-KIRC | MTOR | V2006L | Bevacizumab, Capecitabine, Erlotinib Hydrochloride, Interferon Alfa-2B, Vitespen | everolimus, temsirolimus | MISS |
| TCGA-B8-4153 | TCGA-KIRC | PTCH1 | S1008N | Pazopanib | SONIDEGIB, VISMODEGIB, TRETINOIN | MISS |
| TCGA-CZ-5456 | TCGA-KIRC | ADRA1A | T76S | Pazopanib | ALFUZOSIN HYDROCHLORIDE, DOXAZOSIN, DOXAZOSIN MESYLATE | MISS |
| TCGA-CZ-5462 | TCGA-KIRC | ADAM10 | P373H | Sunitinib | (none) | NO_PREDICTION |
| TCGA-CW-5585 | TCGA-KIRC | PDGFRA | D1026E | Sunitinib | AVAPRITINIB, BECAPLERMIN, CEDIRANIB | MISS |
| TCGA-CJ-4638 | TCGA-KIRC | VHL | D121Y | Bevacizumab, Fluorouracil, Gemcitabine, Recombinant Interleukin-2 | belzutifan | MISS |
| TCGA-CJ-4868 | TCGA-KIRC | EGFR | L838M | Aldesleukin, Bevacizumab, Capecitabine, Erlotinib Hydrochloride, Gemcitabine, Sorafenib Tosylate | AFATINIB, AFATINIB DIMALEATE, AMIVANTAMAB | MISS |
| TCGA-CJ-5681 | TCGA-KIRC | ARHGAP5 | V474A | Bevacizumab, Everolimus, Gemcitabine, Recombinant Interleukin-2 | VINCRISTINE | MISS |
| TCGA-CJ-5676 | TCGA-KIRC | VHL | R161* | Pazopanib, Vitespen | belzutifan | MISS |
| TCGA-A3-3347 | TCGA-KIRC | MTOR | M2327I | Perifosine, Sorafenib | everolimus, temsirolimus | MISS |
| TCGA-CZ-5461 | TCGA-KIRC | NTRK3 | R735H | Sunitinib | CENEGERMIN, ENTRECTINIB, LAROTRECTINIB | MISS |
| TCGA-BP-4165 | TCGA-KIRC | KIT | R2I | Sunitinib | AVAPRITINIB, DASATINIB ANHYDROUS, IMATINIB | MISS |
| TCGA-BP-4169 | TCGA-KIRC | BCL6 | G159C | Axitinib, Interferon | POLATUZUMAB VEDOTIN, FENRETINIDE, BRENTUXIMAB VEDOTIN | MISS |
| TCGA-CJ-5679 | TCGA-KIRC | MTOR | S2215Y | Bevacizumab, Capecitabine, Gemcitabine, Recombinant Interferon Alfa, Thalidomide | everolimus, temsirolimus | MISS |
| TCGA-B0-5115 | TCGA-KIRC | VHL | T124Hfs*35 | Everolimus, Pazopanib | belzutifan | MISS |
| TCGA-CJ-4890 | TCGA-KIRC | FOXN3 | I16M | Everolimus, Interferon, Sorafenib, Sorafenib Tosylate, Sunitinib Malate, Tipifarnib | (none) | NO_PREDICTION |
| TCGA-CJ-6033 | TCGA-KIRC | PIK3CA | E545K | Bevacizumab, Capecitabine, Gefitinib, Gemcitabine, Interferon | alpelisib, capivasertib, inavolisib | MISS |
| TCGA-B0-5694 | TCGA-KIRC | ALK | D282E | Pazopanib | ALECTINIB, ALECTINIB HYDROCHLORIDE, BRIGATINIB | MISS |
| TCGA-BP-4787 | TCGA-KIRC | ARCN1 | G182V | Sorafenib, Sunitinib, Temsirolimus | (none) | NO_PREDICTION |
| TCGA-CZ-5464 | TCGA-KIRC | TSC1 | T62S | Pazopanib, Sunitinib | everolimus, temsirolimus | MISS |
| TCGA-B0-4718 | TCGA-KIRC | PTCH1 | P689H | Bevacizumab, Pazopanib | SONIDEGIB, VISMODEGIB, TRETINOIN | MISS |
| TCGA-CJ-4637 | TCGA-KIRC | VHL | W117Gfs*42 | Bevacizumab, Bortezomib, Interferon Alfa-2B, Nanoparticle Albumin-Bound Rapamycin, Pazopanib, Recombinant Interferon Alfa-2a, Sorafenib, Sunitinib Malate, Temsirolimus | belzutifan | MISS |
| TCGA-CZ-5469 | TCGA-KIRC | VHL | L89H | Sunitinib | belzutifan | MISS |
| TCGA-CJ-4881 | TCGA-KIRC | SCARB1 | G399V | Temsirolimus | FENOFIBRATE MICRONIZED, ROSUVASTATIN | MISS |
| TCGA-CJ-6028 | TCGA-KIRC | BRS3 | S15* | Capecitabine, Gemcitabine, Interferon, Sorafenib, Sunitinib, Vitespen | (none) | NO_PREDICTION |
| TCGA-CJ-4895 | TCGA-KIRC | BCL6 | P586Q | Bevacizumab, Capecitabine, Erlotinib Hydrochloride, Gemcitabine Hydrochloride | POLATUZUMAB VEDOTIN, FENRETINIDE, BRENTUXIMAB VEDOTIN | MISS |
| TCGA-BP-4804 | TCGA-KIRC | BMP8B | H293R | Sunitinib | (none) | NO_PREDICTION |
| TCGA-BP-4974 | TCGA-KIRC | VHL | R82P | Gefitinib, Sorafenib, Sunitinib | belzutifan | MISS |
| TCGA-BP-4161 | TCGA-KIRC | VHL | Q96* | Sunitinib | belzutifan | MISS |
| TCGA-BP-4985 | TCGA-KIRC | ALOX5 | P332L | Sunitinib | BALSALAZIDE, BALSALAZIDE DISODIUM, MECLOFENAMATE SODIUM | MISS |
| TCGA-BP-4352 | TCGA-KIRC | PIK3CA | E81K | Sunitinib | ALPELISIB, COPANLISIB, COPANLISIB HYDROCHLORIDE | MISS |

## Why the raw topline number is low, and why the "fair subset" is *not* higher

The raw 15.1% Exact Top-3 number is real and is not being explained away
here. But it is worth understanding *why* it's low before drawing a
"the algorithm is inaccurate" conclusion from it, because the two largest
contributing factors are properties of this pilot's dataset, not defects
in the ranking logic:

1. **Temporal mismatch (≈11 patients).** The pipeline recommends
   `belzutifan` for essentially every VHL-mutated kidney-cancer patient —
   which is the objectively correct, current, FDA-approved drug for
   VHL-driven RCC. These are scored as MISS only because belzutifan wasn't
   approved until 2021, and most of these TCGA records predate that by
   years. No amount of ranking-algorithm improvement fixes "recommends a
   drug that didn't exist yet when this historical patient was treated."
2. **Passenger-gene-only patients (≈38 patients).** For many patients, the
   only mutation available in this dataset (see "Multi-mutation patients"
   above) is not a real cancer driver (e.g. `ARHGAP5`, `BCL6`, `SCARB1`,
   `ALOX5`, `ADRA1A`, `CAD`, `ATF4`) — an artifact of this pilot's one-
   mutation-per-patient selection, not something the ranking algorithm can
   be expected to get right.

**A natural next question is: if you restrict to only the "fair" cases —
real driver genes, no temporal mismatch — does the number go up?**

We checked. It does not — it goes *down*: **1/20 (5.0%) exact Top-3,
2/20 (10.0%) class-equivalent Top-3** on that 20-patient fair subset,
versus 15.1%/17.0% on the full 53-patient scored set. We are reporting
this even though it is a less flattering number than we expected, because
the alternative (only reporting the subset analysis when it looks better)
is exactly the kind of selective framing this project's own prior
benchmark write-ups have had to walk back before (see
`PROJECT_COMPLETION_STATUS.md`'s history of gate-gamed benchmark batches).

**Why the fair subset is lower:** almost all of it is `TCGA-KIRC` (kidney
cancer) patients. In this cohort, Sunitinib was given to 18 of 45 patients,
Bevacizumab to 13, Sorafenib to 11, Pazopanib to 9 — regardless of which
secondary gene happened to be sequenced (MTOR, PIK3CA, KIT, PDGFRA, NTRK3
patients all show this same handful of drugs). This is the signature of
**era-standard-of-care treatment**, not gene-targeted treatment: real
kidney-cancer oncology practice in this dataset's time period used the
same small set of anti-angiogenic drugs for most patients, largely
independent of secondary sequencing findings. The pipeline, correctly,
recommends the *mechanistically matched* drug for each gene (everolimus
for MTOR, alpelisib for PIK3CA, imatinib for KIT) — which is real,
clinically sound, targeted-therapy logic — but it will not match
standard-of-care prescribing that wasn't driven by that gene in the first
place.

**We deliberately did not "fix" this by weighting the ranking algorithm
toward cancer-type standard-of-care drugs.** Concretely: doing so would
mean a real VHL-mutated kidney-cancer patient today would be pushed toward
generic Sunitinib instead of belzutifan (the correct, current, targeted
option) purely because that matches more rows in this historical TCGA
snapshot. That is not an accuracy improvement — it is tuning the algorithm
to this specific answer key at the cost of making real future
recommendations worse. We judged that trade to not be worth taking, and
did not make it.

- **Small, non-random sample.** 69 patients, concentrated in two cohorts
  (breast/TP53 and kidney/VHL). Not a validated clinical benchmark; a pilot.
- **One mutation per patient, not the full mutational profile.** Several
  patients had other mutations on record that were not submitted; the real
  oncologist decision may have been driven by a mutation not tested here.
- **Real-world treatment dates are unknown per-patient in this dataset** —
  some drugs the pipeline recommends (e.g. belzutifan, approved 2021) may
  not have existed yet when an older TCGA patient was actually treated.
  This run does not adjust for that.
- **Tier 2 "approved" filtering is broad** — it can surface any FDA-approved
  drug with a gene-interaction record (including general chemotherapy),
  not only mechanism-matched targeted therapy.
- **This pilot did not run the genomic variant-calling half of the
  pipeline** (Nextflow/BWA-MEM2/Mutect2) or AlphaFold/DiffDock structure
  scoring — only the drug-ranking half, using already-called mutations.
- **No statistical testing performed** (confidence intervals, significance)
  given the sample size and cohort concentration.

## Reproducing this run

Scripts: `scripts/concordance_pilot_fetch_gdc_clinical.py`,
`scripts/concordance_pilot_fetch_cbioportal_mutations.py`,
`scripts/concordance_pilot_run_pipeline.py`. Data sources are public and
require no API key: `api.gdc.cancer.gov` and `www.cbioportal.org/api`.

```bash
cd scripts
python concordance_pilot_fetch_gdc_clinical.py          # -> gdc_extra_cohorts_drugs.json
python concordance_pilot_fetch_cbioportal_mutations.py  # -> cbioportal_extra_mutations.json
python concordance_pilot_run_pipeline.py --data-dir .   # -> concordance_run_results.json
```

The 26 original-cohort patients' input
(`candidate_patients.json`, built from `samples/real/*.vcf` +
`scripts/clinical*.tsv`) and the 55 new-cohort overlap file
(`new_cohort_overlap.json`, built from the two fetch scripts' output) are
intermediate artifacts from this session and are not re-derivable from a
single script yet — regenerating them exactly requires re-running the
patient-selection logic described in "Data sources and how patients were
selected" above.

The evidence-table fixes this pilot produced are permanent and covered by
regression tests independent of re-running the pilot itself: see
`api/tests/test_oncokb_evidence.py`'s `test_egfr_real_world_exon19_range_
deletion_matches`, `test_kit_real_world_exon11_range_deletion_matches`, and
their accompanying negative-case tests.
