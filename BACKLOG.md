# OpenOncology Backlog

Git-tracked project state. Agents read this at session start and update it at
session end, so work survives context compaction, restarts, and closed laptops.

Sections are ordered by pipeline position. `/next` pulls from the top of
`## Ready`. Nothing pulls from `## Needs human decision`.

---

## Ready

### Frontend documentation note, November 5
- Placement follow-up: moved the interface-update note to the closing Build with us section, below the contribution links. Wording unchanged.
- Added a README note explaining temporary differences between frontend experiments, website visuals and documentation. Feature documentation should track implementation, with planned features labelled. Invites mismatch reports and design feedback through the existing maintainer email. Documentation only; no feature, ranking or benchmark changes.
- Publication: [PR #216](https://github.com/immortal71/openoncology/pull/216). README media audit and diff checks passed; merging remains manual.

<!-- Populate with /groom "<objective>". Entries use this shape:

### OO-N: Consolidate design tokens into globals.css
- **Why**: Tailwind autocomplete keeps reintroducing generic purple and blue, drifting from the green/cream system
- **Files**: web/app/globals.css, web/tailwind.config.js
- **Acceptance**:
  - Every color in tailwind.config.js references a CSS variable, no literals
  - #0F6E56, #FAFAF8, #16181D, #E4E2DB defined once in globals.css
  - Grep for `purple-`, `blue-`, `cyan-` across web/ returns nothing
  - Build passes, no visual regression on the homepage
- **Out of scope**: component markup, marketplace modal
- **Risk**: low
-->

### OO-37: Expose sequencing evidence and the justifying variant in the results API
- **Why**: The redesigned Results page has a variant drawer and therapy groups, following the conventions of genomic reports. Pathologists look at VAF first: a TP53 variant near 50% raises the germline question. The drawer has to say "Not in this result" for VAF, depth, ClinVar and COSMIC, although `api/models/mutation.py` already stores `vaf`, `depth`, `clinvar_id` and `cosmic_id`. Drug rows also can't say which variant and OncoKB level justify them, so in a multi-variant case a Level 1 drug's alteration is unclear.
- **Files**: api/routes/results.py (serialisers around lines 104, 227, 332 and 387), api/tests for the results routes, web/lib/api.ts types, web/components/results/variant-drawer.tsx
- **Acceptance**:
  - Each serialised mutation includes `vaf`, `depth`, `clinvar_id` and `cosmic_id` (null when absent)
  - Route tests assert the new keys and their null behaviour
  - The drawer shows VAF and depth when present, and links ClinVar and COSMIC by ID
  - Separately scoped: decide whether each repurposing candidate can carry the variant and OncoKB level that justified it. That touches the ranking output, so it needs a human decision.
- **Out of scope**: changing `api/ai/**`, ranking, or how any value is computed
- **Risk**: low for the serialiser fields; scientific for the per-candidate justification

### OO-6: Pin the pipeline's container images by digest
- **Why**: `pipeline/modules/*.nf` pin containers by tag (`broadinstitute/gatk:4.5.0.0`, `etal/cnvkit:0.9.10`, `docker.io/szarate/manta:1.6.0`, two biocontainers). A tag is mutable. The variant-calling validation gate asks which pipeline produced a call set, and a tag cannot answer it: the same tag six months apart is a different image and possibly different calls. `nextflow.config` now declares `gatk_version` once, so the GATK pair can no longer diverge, but neither is pinned to an immutable reference.
- **Files**: pipeline/nextflow.config, pipeline/modules/*.nf, api/tests/test_pipeline_config.py
- **Acceptance**:
  - Every `container` directive resolves to a `name@sha256:...` reference
  - Digests are recorded with the date and the tag they resolved from, so a later bump is auditable
  - A test asserts no `container` directive uses a bare tag
  - The conda specs stay pinned to the same tool versions the digests correspond to
- **Out of scope**: the conda-only modules, which pin exact versions already; choosing different tool versions
- **Risk**: low

### OO-12: There is no backup of patient data, and the compliance checklist said there was
- **Why**: Nothing in this repository backs up the application database or object storage. No `archive_mode`, `archive_command` or `wal_level`; no MinIO versioning; no `pg_dump`, pgBackRest, wal-g or Velero anywhere. The Bitnami `postgresql` sub-chart has persistence, and persistence is not backup: a deleted PVC, a bad migration or a ransomware event loses every submission, mutation and result permanently, with no recovery path. `HIPAA_COMPLIANCE.md` carried ✅ against §164.308 contingency planning, citing "PostgreSQL WAL + MinIO versioning (see `infra/helm/postgres.yaml`)", and that file is Keycloak's database rather than the application's. The claim has been corrected; the gap it was covering is this entry.
- **Files**: infra/helm/values.yaml, infra/helm/values.production.yaml, infra/helm/templates/, docs/HIPAA_COMPLIANCE.md, docs/SETUP.md
- **Acceptance**:
  - The application database has scheduled backups with a stated retention, and object storage has versioning or an equivalent
  - A **restore** has been performed into a scratch namespace and the result checked, because an unexercised backup is a belief rather than a control
  - RPO and RTO are written down, even if the numbers are modest
  - `HIPAA_COMPLIANCE.md` moves to ✅ only after that restore, and names what was restored and when
- **Out of scope**: choosing a managed database, which is a hosting decision
- **Progress 2026-08-29**: nightly `pg_dump` CronJob added to the chart, enabled by default, writing to object storage with a manifest and 30 day retention, plus `docs/RUNBOOK_BACKUP_RESTORE.md`. The entry **stays open**: its acceptance requires an exercised restore, and nobody has run one. Object storage versioning is still absent, so a database-only restore yields rows referencing missing files, and Keycloak's database is still unbacked.
- **Risk**: high while open. This is the one entry where the failure mode is unrecoverable rather than merely wrong. Lower than it was, since a dump now exists; not closed, because a backup nobody has restored is a belief about a file.

### OO-15: Two governance controls the compliance guard exposed
- **Why**: `api/tests/test_compliance_claims.py` failed against two further rows once it existed. **Security officer**: the row cited a CODEOWNERS file, and no such file exists at the root, under `.github/` or under `docs/`, so the role is unassigned rather than assigned somewhere else. **Automatic log-off**: the row quoted "30 min idle / 8 hr max" and nothing in this repository sets `ssoSessionIdleTimeout` or `ssoSessionMaxLifespan`, so sessions run at the Keycloak image's defaults, which do not match the figure quoted. Both rows are corrected; these are the gaps behind them.
- **Files**: .github/CODEOWNERS, infra/helm/templates/keycloak.yaml, docs/HIPAA_COMPLIANCE.md
- **Acceptance**:
  - A CODEOWNERS file exists naming a responsible owner, or the row is rewritten to describe how the role is actually held
  - Session lifetimes are set explicitly in the realm configuration the chart deploys, at values someone has chosen, rather than inherited
  - Both rows return to implemented only once `test_compliance_claims.py` passes with them marked so
- **Out of scope**: who the security officer is, which is the maintainer's decision and not a code change
- **Progress 2026-08-29**: session lifetimes are applied by `infra/helm/templates/keycloak-session-policy.yaml`, a post-install and post-upgrade Job running `kcadm`, at the 1800s / 28800s the checklist had been quoting without setting. That half is closed and the row is back to implemented. `.github/CODEOWNERS` now exists, naming review ownership for every guard-protected path and every risk document.
- **Still open**: the security-officer half. A file naming a code owner is not a person accepting the §164.308(a)(2) role. That is an appointment, and it stays at not-implemented until it is recorded somewhere a reviewer can check. Nothing an agent does can close it.
- **Risk**: low to implement. Worth noting that assigning an owner in a file is not the same as a person accepting the role, and the checklist can only ever check the first.

### OO-19: Pin the deployed image tags once images exist
- **Why**: `values.yaml` uses `latest` for the api and web images. That is mutable: a pod restart can change the running version, and nothing records which code produced a given result. For software whose output is clinical evidence this is the same defect as the mutable pipeline container tags in OO-6, on the images that run the ranking. #151 added `publish-images`, which emits an immutable `sha-<short>` on every push to main and a `v*` tag on a git tag, so the tags to pin will exist after the first merge.
- **Not done in #151 on purpose**: no image has been published yet, and pinning a tag that does not exist is worse than pinning a mutable one. It has to follow the first successful publish rather than accompany it.
- **Files**: infra/helm/values.staging.yaml, infra/helm/values.production.yaml, api/tests/test_deployment_manifests.py
- **Acceptance**:
  - `values.staging.yaml` pins `api.image.tag` and `web.image.tag` to a `sha-` tag that exists in the registry
  - `values.production.yaml` pins a `v*` tag
  - A test fails if either file uses `latest`, or omits a tag and so inherits it
  - `values.yaml` may keep `latest`, since it is the base and is never deployed from alone
- **Out of scope**: digest pinning for these two images, which is stricter again and belongs with OO-6's decision about how digests get refreshed
- **Risk**: low. Worth noting the first pin cannot be verified from this repository: whether the tag resolves is a property of the registry.

---

## In progress


<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

---

## In review

### Current product documentation (November 5, 2026)
- Scope: lab interpretation first, hospitals next; hosted evaluation and local availability/affordability planned. Documentation and homepage copy only.
- Draft presentation: product-first README, original SVG banner/workflow, real production-frontend screenshots, seven-second evidence-review GIF, Vision, Code of Conduct, contributor guide, issue forms and PR template. Skills used: find-skills, readme-blueprint-generator, documentation, humanizer, webapp-testing and video-to-gif.
- Validation: production build passed; 46 frontend unit tests and 5 documentation/coverage consistency tests passed; relative documentation links, SVG XML, issue-form structure and media loading checked. GIF is 930x410, 7 seconds and 160,393 bytes. Visual README and Vision navigation reviewed in browser. No scientific code, scripts, data, result artifacts or PAPER.md changed.
- Publication: [PR #214](https://github.com/immortal71/openoncology/pull/214) is open against main from `docs/yc-current-product`. Repository About description was updated separately. Commits are authored and committed by immortal71, without co-author attribution. Merging remains manual.
- Validation: preserve ranking code, benchmark scripts, datasets, saved results and the historical published paper. Describe CHORD's treatment-conditioned input selection and separate lookup runner explicitly.
- Scientific follow-up: reconcile the baseline protocol, review shared-map coupling and broad ground-truth rules, and evaluate the complete application without outcome-based input selection. These require scientific review rather than wording changes.
- README showcase refresh, November 5: replaces the banner and repeated screenshots with a ten-second HeroUI presentation using current demo content. Selectable drug rows show Rank 1/2/3, separate illustrative scores and the off-label warning. Includes GIF, MP4, poster and editable Remotion source with library notices. Both preprints and DOI links appear near the top of the README; the benchmark DOI is also linked in `docs/RESEARCH.md`. The presentation is explicitly labelled as a mockup, distinct from the running frontend.
- Showcase validation: TypeScript, five documentation consistency tests, README media audit and diff checks pass. Browser playback and candidate selection were inspected. GIF: 1280�740, 150 frames, 1,064,631 bytes, matching decoded first/last frames. Scientific code and demo fixtures are unchanged. Publication: [PR #215](https://github.com/immortal71/openoncology/pull/215); merging remains manual.

<!-- Entry plus PR URL. Cleared by hand when merged. -->

---

## Needs human decision

<!-- Anything an agent declined to do unattended: guard-hook blocks, validator
     BLOCKs, mis-scoped entries, and anything the planner marked
     Risk: scientific. This section is the safety valve. When it grows, that is
     the system working, not failing. -->

### OO-39: Wrong ChEMBL ID (and likely wrong SMILES) for sotorasib in the backend lookup table
- **Why**: Found by the marketing-page clinical review (2026-11-18) and checked against ChEMBL. Sotorasib is CHEMBL4535757, but `api/services/chembl.py:177` maps it to CHEMBL4523582, and the SMILES on that line does not look like sotorasib's structure (ChEMBL's is `C=CC(=O)N1CCN(c2nc(=O)n(-c3c(C)ccnc3C(C)C)c3nc(-c4c(O)cccc4F)c(F)cc23)[C@@H](C)C1`). The same wrong ID appears in `validation_results/kras_g12c_real_output.json` and `docs/design/data-inventory.md`. The web demo also had adagrasib as CHEMBL4741767; ChEMBL lists it as CHEMBL4594350.
- **Files**: api/services/chembl.py, validation_results/kras_g12c_real_output.json (guard-protected, do not route around the hook), docs/design/data-inventory.md
- **The actual decision**: correct the ID and SMILES in the fallback table, check every other entry in that table against ChEMBL, and decide whether the stored validation output should be regenerated or annotated.
- **Interim**: `web/lib/demo-data.ts` now uses CHEMBL4535757 and CHEMBL4594350, so the demo's ChEMBL links resolve to the right compounds.
- **Risk**: scientific. Wrong identifiers and structures can feed docking and any downstream lookup.

### OO-38: `test-fixtures/dna_sample_kras_g12c.vcf` coordinates look wrong and mix genome builds
- **Why**: Flagged by the marketing-page design review (2026-11-16) and not yet verified against a reference genome.
  - KRAS line `12:25398284 C>A` with `HGVS_P=p.Gly12Cys`: on GRCh37, c.34G>T (G12C) is reported at 25398285, and 25398284 C>A would be c.35G>T (G12V).
  - TP53 line `17:7673803` with `p.Arg175His`: this looks like a GRCh38 codon-273 position, not R175H.
  - NRAS line `1:115256529 C>A` with `p.Gln61Lys`: the reference base and position look inconsistent with Q61K.
  - The header declares no build, and the positions appear to mix GRCh37 and GRCh38.
- **Files**: test-fixtures/dna_sample_kras_g12c.vcf, plus whatever tests read it (guard-protected, do not route around the hook)
- **The actual decision**: confirm each position against GRCh37/GRCh38, pick one build, add a `##reference=` header, and check whether any test or the demo pipeline depends on the current positions. Also decide whether a KRAS G12C plus NRAS Q61K co-occurrence belongs in a sample meant to look realistic.
- **Interim**: the `/lab/atlas` marketing page no longer shows the fixture. It shows only GENE, HGVS_P and the protein change for the two variants in the demo result.
- **Risk**: scientific. It's a sample input that people can load and read.

### OO-23: PAPER.md title/abstract frame discovery as co-equal to evidence matching; YC pitch does not
- **Why**: Asked (2026-11-04) to check the GitHub docs against the YC W27 application for drift. README.md has now been edited to lead with evidence matching as the current product and mark custom drug discovery/marketplace/crowdfunding as a separate research-stage track (see the "Where this stands today" line under "What is OpenOncology?" and the Roadmap table). PAPER.md cannot be brought into line the same way: its title is "...Evidence-Based Drug Matching **and** De Novo Custom Drug Discovery...", giving the two equal billing, and it mirrors an already-published Research Square DOI abstract (10.21203/rs.3.rs-9707913/v1) that the file itself flags as not to be silently edited.
- **Files**: PAPER.md (guard-protected, do not route around the hook)
- **The actual decision**: whether the gap between "paper describes a two-stage evidence+discovery platform" and "YC pitch and current README describe an evidence-matching product with discovery as a future research track" needs anything — an explicit erratum/scope note on Research Square, a line added to PAPER.md's existing "Version Note" by hand, or nothing, since a published preprint describing a broader research agenda than today's productized scope is not unusual and may not need correcting.
- **Out of scope**: editing PAPER.md's title, abstract, or citation block — none of that should change without the same erratum process already used for the dedup-bug and circularity retractions in this file.
- **Risk**: scientific. Touches a published DOI's framing.

### OO-36: AlphaMissense classes are collapsed, and unscored variants default to "uncertain"
- **Why**: Found by the redesign's clinical re-review (2026-11-15); the code was checked.
  - `api/workers/ai_worker.py:83-88` stores AlphaMissense's `likely_pathogenic` as `MutationClassification.pathogenic`, a class the model never outputs and a word that reads as a curated ACMG call.
  - `api/models/mutation.py` defaults `classification` to `uncertain`, so a variant that was never scored (no protein change, model unavailable) looks as if AlphaMissense called it ambiguous.
  - `web/lib/demo-data.ts` shows "Pathogenic" with no `alphamissense_score`.
- **Files**: api/workers/ai_worker.py, api/models/mutation.py (plus a migration if the enum or default changes), web/lib/demo-data.ts
- **The actual decision**: store AlphaMissense's own classes (`likely_pathogenic`, `ambiguous`, `likely_benign`), make `classification` nullable with no default, and decide what the demo should show.
- **Interim**: the frontend shows an AlphaMissense class only when `alphamissense_score` is a number, maps `pathogenic` to "Likely pathogenic" and `uncertain` to "Ambiguous", and otherwise says "Not scored in this result". The demo therefore shows "Not scored".
- **Risk**: scientific. It's a pathogenicity label shown to clinicians.

### OO-35: `classify_drug_tier` can label an unconfirmed or unapproved drug as approved
- **Why**: Found by the redesign's clinical-patterns review (2026-11-15); the code was checked.
  - `api/ai/ranking.py:190-192`: Level 1/2 evidence with unknown approval status still returns `fda_approved`, so the UI's "FDA approved" badge can assert an approval nobody confirmed.
  - `api/ai/ranking.py:195-196`: `"approved" in _approval_str` also matches "not approved" and "unapproved", which would put an unapproved drug in the `repurposed` tier ("approved for a different indication").
- **Files**: api/ai/ranking.py (protected), plus the ranking tests.
- **The actual decision**: whether Level 1/2 drugs with unknown approval need their own tier (for example `level_1_2_unconfirmed`), and a word-boundary or negation-aware approval check. Tier labels feed the benchmark, so the gate must be re-run.
- **Interim**: the redesigned Results page names the first group "OncoKB Level 1–2 (standard care)" with the note "Approval status as reported on each row", and hides the per-row tier pill when grouped. The approval line on each row still comes from `approval_status`.
- **Risk**: scientific. It's on the ranking path.

### OO-34: Landing page evaluation section shows no metric
- **Why**: Two redesign reviews (2026-11-09 and 2026-11-15) flagged that the landing's "How it's evaluated, and what that doesn't show" section gives a caveat and a link, but no number, sample size or denominator.
- **Files**: web/app/lab/landing/page.tsx (the `#evidence` section); source figures in docs/BENCHMARK.md.
- **The actual decision**: which locked metric, if any, the public page may state, with its n and caveat (for example MSK CHORD evidence-lookup Hit@3 or P@3). The headline claims still need the owner's sign-off, so no agent should pick a number.
- **Interim**: the section is titled as an evaluation method, not as results, so it doesn't promise numbers it can't show.
- **Risk**: scientific. It's a public claim about the product.

### OO-33: KRAS G12C test fixture and demo sample carry G12V coordinates or cDNA
- **Why**: Found by the redesign's round-3 devil's-advocate review (2026-11-09), and checked against the repo.
  - `test-fixtures/dna_sample_kras_g12c.vcf` has `12 25398284 C A` annotated `HGVS_C=c.34G>T;HGVS_P=p.Gly12Cys`. KRAS is on the minus strand: on GRCh37, 25398284 C>A is c.35G>T (p.Gly12Val), and c.34G>T (p.Gly12Cys) is 25398285 C>A.
  - The repo's own `samples/real/*.vcf` files label 25398284 C>A as G12V.
  - `samples/demo_output_sample3_nsclc.json` contains both `c.34G>T` and `c.35G>T` next to p.Gly12Cys. c.35G>T is G12V.
  - Whatever reads POS/REF/ALT gets G12V, while whatever reads the INFO annotation gets G12C. Annotation tools that re-derive the protein change (for example VEP) will disagree with the fixture label.
- **Files**: test-fixtures/dna_sample_kras_g12c.vcf, samples/demo_output_sample3_nsclc.json (`test-fixtures/**` is protected).
- **The actual decision**: correct POS to 25398285 (or change the label to G12V), check whether any test or benchmark depends on the current record, and fix the c.35G>T entries in the sample JSON.
- **Interim**: the redesigned landing page shows only the fixture's annotation fields (GENE, HGVS_C, HGVS_P), not its coordinates.
- **Risk**: scientific. It's the canonical demo variant.

### OO-32: Demo labels TP53 p.Arg175His "OncoKB LEVEL_3B" while also marking it not targetable
- **Why**: Found by the redesign's second Results-page review (2026-11-09).
  - `web/lib/demo-data.ts` gives TP53 p.Arg175His `oncokb_level: "LEVEL_3B"` and `is_targetable: false`.
  - An OncoKB therapeutic level of 3B means a drug has clinical evidence for that alteration in another tumour type, which contradicts "not targetable" on the same row.
  - The reviewer did not believe OncoKB assigns R175H a therapeutic level at all.
  - The redesigned page shows "OncoKB Level 3B · not targetable" side by side, so the contradiction is visible to clinicians.
- **Files**: web/lib/demo-data.ts
- **The actual decision**:
  - check the current OncoKB annotation for TP53 R175H;
  - set the demo's level to match it (likely none, or an oncogenicity label rather than a therapeutic level);
  - or explain why 3B is right.
- **Related content issue (not scientific)**: the demo's first suggested next step says "Share this report with your oncologist", but the redesigned page has no report download or share action yet.
- **Risk**: scientific. It's an evidence level shown to users.

### OO-31: Demo ranks Osimertinib (EGFR inhibitor) #3 for a KRAS G12C tumour with no EGFR variant
- **Why**: Found by the redesign's devil's-advocate review of the Results page (2026-11-09).
  - `web/lib/demo-data.ts` lists Osimertinib third in `DEMO_REPURPOSING`: rank_score 0.71, tier `repurposed`, sources OncoKB and ClinVar, mechanism "EGFR T790M inhibitor — included as combination therapy candidate".
  - The demo case has KRAS p.Gly12Cys and TP53 p.Arg175His and no EGFR variant.
  - An "OncoKB" source chip on that row reads as KRAS-specific evidence.
  - `samples/demo_output_sample3_nsclc.json` contains no Osimertinib, so this row was written for the demo rather than produced by the ranking.
  - An oncologist reviewing the demo will flag it first.
  - Round-2 landing review (2026-11-09) added two points. ClinVar is variant-pathogenicity evidence, not drug evidence, so it can't support a drug's rank. The row carries `opentargets_score: 0.61` while `evidence_sources` omits OpenTargets, so the score and the source list disagree and the UI can't show that score.
  - The row now also appears in the landing page hero, the first thing a visitor sees.
- **Files**: web/lib/demo-data.ts
- **The actual decision**: does the demo's ranked list reflect what the pipeline would actually output for this case?
  - **If not:** regenerate the demo candidates from a real run.
  - **If it does:** the combination-therapy rationale needs to be shown as such, and the OncoKB source on that row needs explaining.
- **Interim**:
  - The redesigned Results page shows the row unchanged.
  - The collapsed row says "Approved for a different indication".
  - The expanded row shows the approval qualifier and mechanism.
  - `demo-data.ts` is unchanged.
- **Risk**: scientific. It's a ranking shown to clinicians.

### OO-30: Frontend demo lists DiffDock as evidence while the system's own limitations say DiffDock is not run in the demo
- **Why**: Found during the frontend redesign (2026-11-09). `web/lib/demo-data.ts` lines 71 and 84 list `"DiffDock"` in `evidence_sources` for Sotorasib and Adagrasib, mirroring `samples/demo_output_sample3_nsclc.json`, which lists it ten times. `api/ai/ranking.py` (the limitations list, around line 705) says: "AlphaFold structure prediction and DiffDock docking are NOT run in the default demo; binding_score is absent unless the optional AI pipeline is configured." The demo therefore shows a source the product says it didn't use. Related to OO-24, which covers the paper's DiffDock and AlphaFold claims; this entry is about what the product UI displays.
- **Files**: web/lib/demo-data.ts, samples/demo_output_sample3_nsclc.json (read-only reference), api/ai/ranking.py (guard-protected, read-only)
- **The actual decision**: was the sample generated with the optional AI pipeline configured? If so, the demo should say so. If not, remove `"DiffDock"` from the demo's `evidence_sources`, and from the sample if it is regenerated.
- **Interim**: the redesign's hero storyboards (`/lab/hero`) leave DiffDock out of displayed sources until this is decided. `demo-data.ts` is unchanged.
- **Risk**: scientific. It's an evidence claim shown to users.

### OO-24: Published paper's ranking weights and AlphaFold completion claim are unsubstantiated by the repo — surface it, nothing in BACKLOG tracked it
- **Why**: While checking the repo against the YC application (2026-11-04), re-read `docs/PAPER_VS_CURRENT_STATE.md`, an existing reconciliation doc in this repo that nothing in BACKLOG.md referenced. It already found, with git history as evidence: (1) the deployed ranking weights (`api/ai/ranking_config.py`, six signals, OncoKB 40%/DiffDock 15%/CIViC 10%) diverged from the published paper's Methods table (five signals, OncoKB 25%/DiffDock 30%, no CIViC) **before** the paper was even posted — the weight change landed 2026-05-03, the paper posted 2026-05-18; (2) the paper's claim that AlphaFold structure generation completed for 178/185 cases with the 7 failures caused by "AlphaFold Server rate limiting" cannot be reproduced from this repo: no `ALPHAFOLD_API_KEY` was ever set at any commit on any branch, and no DiffDock model directory has ever existed in the repo. This is a materially bigger issue than any README wording — it's a specific, falsifiable claim in an already-published, DOI'd paper that the code as committed cannot explain.
- **Files**: PAPER.md, docs/PAPER_VS_CURRENT_STATE.md (read-only reference; PAPER.md is guard-protected)
- **The actual decision**: whether this needs a Research Square erratum (same process as the dedup-bug and circularity retractions already in this file), or whether the AlphaFold/DiffDock run happened in an environment with credentials that were simply never committed here (in which case it's a documentation gap, not a fabrication, but still needs a note). Not something an agent should guess at or resolve by editing a published abstract.
- **Out of scope**: changing `api/ai/ranking_config.py` to match the paper, or vice versa — that's an algorithm decision with benchmark consequences, not a docs fix.
- **Risk**: scientific. Touches a published DOI's reproducibility.

### OO-22: Run the variant-calling gate on this pipeline (roadmap 2.1)
- **Why**: The single blocking clinical gate that needs no partner, IRB or regulator, and the cheapest item left on the critical path. `REGULATORY_FRAMEWORK.md` 3.1 wants sensitivity >= 99% and PPV >= 95% against an orthogonal truth set. The only measurement in the repository is of a *published NIST call set*, correctly recorded as `satisfies_regulatory_gate_3_1: false`.
- **Blocked on a host, not on code.** Needs ~32 GB RAM, 8-16 vCPU, 150 GB disk, and `nextflow`, `java`, `bwa-mem2`, `gatk`, `samtools`. A developer workstation does not qualify: the BWA-MEM2 index build alone wants 12 GB.
- **Pre-flight done 2026-09-07**, so a rented host starts from a known-good position:
  - All five downloads verified live: GIAB truth VCF (0.15 GB), its index, the confident BED, GRCh38 primary assembly (0.82 GB), dbSNP 151 (15.23 GB).
  - The `<HG002_GRCh38.bam>` placeholder in the runbook is resolved to a real URL, and it is the BGIseq 2x150 100x run — the same dataset the existing reference figure used, which is what makes the comparison like for like.
  - **That BAM is 390 GB**, against the runbook's own 150 GB disk budget, so route A as previously written could not have been followed. The server supports range requests and a `.bai` exists, so `samtools` streams the region instead: **8.86 GB**, measured from the index (chr20 is reference 19, bytes 367,105,864,800 to 376,620,505,623), not estimated from chromosome length. The real bins and the pseudo-bin agree.
  - Two late-failing traps written down: `samtools` must be built with libcurl, and the BAM uses `chr20` naming across 595 references.
- **Acceptance**:
  - `scripts/validate_variant_calling.py` run with `--from-repo-pipeline` against output of `pipeline/main.nf`, scope chr20 in the NIST confident regions
  - Route A (BAM in, caller measured) first, then route B, with the gap between them recorded — that gap is the cost of the single-end FASTQ path
  - `--query-label` states what was measured; route A is not end-to-end accuracy and must not be described as such
  - The result is compared against `variant_calling_reference_gatk4.json`, which is stock GATK4 at 95.82% sensitivity — under the 99% gate
- **Out of scope**: the two known pipeline limitations the runbook documents (single-end FASTQ handling, BWA-MEM2 index rebuilt per task). Both change what route B means; neither blocks the measurement.
- **Risk**: scientific. This produces a number that goes into a regulatory gate, and `validation_results/**` is guard-protected. A human runs it and records it; an agent must not.

### OO-7: Decide whether `civic_supplement_enabled` should default to True
- **Why**: Asked as "how do we raise the benchmark", and the measurements already
  in the repository answer it in a way that rules ranking work out. In
  `hard_benchmark_results.json`, three of five difficulty buckets sit exactly on
  their own ceiling — MULTI_DRUG 0.9792/0.9792, LOW_PURITY 0.7778/0.7778,
  REFRACTORY 0.5476/0.5476. A ceiling is the best any reordering of the existing
  candidate pool could score, so for those buckets a better ranker scores
  identically. The only headroom left is 0.033 in CONFLICTING_EVIDENCE and 0.024
  in RARE_OR_COMPLEX, under a point of aggregate P@3.

  What moves the ceiling is evidence coverage, and
  `validation_results/civic_coverage_gain.json` has already measured the one
  lever that exists: loading CIViC level A/B predictive evidence makes 3 of the
  13 missed NCI-MATCH arms reachable and leaves 10 absent. The flag exists and
  is off.

  Not an agent's call. Widening the actionability table changes which drugs the
  system can recommend, `candidate_pool_policy` is `evidence_first` so the table
  decides the pool wherever it has an answer, and the audit's own caveat is that
  reachable is not correct. It is also the wrong metric to optimise against
  alone: open action 2 is still the unresolved question, and P@3 against a
  curated key shares sources with the table being widened.
- **Risk**: scientific
- **Evidence to weigh**: `validation_results/civic_coverage_gain.json`,
  `hard_benchmark_results.json` `by_difficulty` ceilings, risk_analysis.md §7 and
  open action 2. The holdout-50 set scores standard P@3 0.5083 against the hard
  benchmark's 0.8009; whichever way this goes, both numbers should move together
  or the gap needs explaining.

### OO-8: `require_current_evidence` must be True before any clinical deployment
- **Why**: `api/config.py` says so in its own comment — "It MUST be True for any
  clinical deployment" — and it defaults False, correctly, because this is
  research-use software. Recorded here so the flip is a decision someone makes
  rather than one someone forgets. It pairs with the new production requirement
  for `KEYCLOAK_AUDIENCE`: both are settings whose safe research default is the
  unsafe clinical one.
- **Risk**: scientific / policy — this is a hazard control, not a config tidy

### OO-21: VCF ingestion feeds coding notation to a lookup keyed on protein notation
- **Why**: `_parse_and_annotate_vcf` stores `INFO/HGVS_C` as `mutations.hgvs_notation`. The evidence table is keyed on protein alterations: `_normalise_alteration("p.Thr790Met")` gives `t790m`, and `_normalise_alteration("c.2369C>T")` gives `c2369c>t`, which matches nothing. Measured directly against the shipped table:

  ```
  get_all_drugs_for_variant("EGFR", "T790M")     -> 7 drugs  ['osimertinib', 'erlotinib', 'gefitinib', ...]
  get_all_drugs_for_variant("EGFR", "c.2369C>T") -> 0 drugs  []
  ```

  So a VCF carrying EGFR T790M, which the table knows maps to seven drugs, yields no recommendation. Submitting `samples/egfr_t790m_demo.vcf` end to end produces `recommendation_state: no_targetable_mutation`, with both EGFR and TP53 stored as `classification: uncertain`, `is_targetable: 0`, `oncokb_level: unknown`.

  Three things make it look deliberate until you check. `INFO/HGVS_P` is present in the sample VCFs and is read nowhere in the application. The `mutations.hgvs_p` column existed in `0001_initial_schema` and was dropped by `a8bf7eb4833c`. And `ai_worker._hgvs_to_short(hgvs_p: str)` names its parameter for protein notation, does `hgvs_p.lstrip("p.")`, and is passed `mutation.hgvs_notation`, which holds the coding form.

  This is hazard H2, an actionable variant present and not surfaced, and it is F2's shape reaching the same outcome by a different route. The benchmarks do not see it because they feed protein notation straight to the ranker and never pass through VCF ingestion, which is why the suite reports P@3 0.80 while the ingestion path returns nothing.
- **Risk**: scientific. Changing which notation reaches the evidence table changes which drugs are recommended for every submission, so it is not an agent's call, and it wants a decision about whether to store both notations, prefer `HGVS_P`, or derive protein from coding.
- **Files to consider**: api/workers/genomic_worker.py `_parse_and_annotate_vcf`, api/models/mutation.py, a migration restoring a protein column, api/workers/ai_worker.py `_hgvs_to_short`
- **Worth checking alongside**: whether any real submission has ever produced a recommendation, and whether the concordance and holdout numbers were computed through ingestion or around it.
- **Decided and done (2026-10-22): prefer protein notation.** `_parse_and_annotate_vcf` now reads `HGVS_P`, then the plain `HGVS` field the `samples/real/` VCFs use (`HGVS=L858R`), and falls back to `HGVS_C` only when neither is present, with a warning that the lookup will not match it. `HGVS_C` is kept as `hgvs_c` and stored in the existing `codon_change` column, so no migration. A comma-separated isoform list takes its first entry. Deriving protein from coding (option B) was not done.
  - Before this, the `samples/real/` patient VCFs reached the lookup with no notation at all, since they carry neither `HGVS_C` nor `HGVS_P`.
  - `test_shipped_vcfs_reach_the_evidence_table` now runs `samples/egfr_t790m_demo.vcf` and a real L858R VCF through the parser into the evidence table. The five hotspot tests in `test_vcf_real_data.py` that asserted coding notation in `hgvs` now read `hgvs_c`.
  - **Still blocking an end-to-end recommendation**: see OO-27.

### OO-25: The concordance pilot blames timing for misses that timing does not explain
- **Why**: `docs/REAL_PATIENT_CONCORDANCE_PILOT_2026-07-28.md` explains the low concordance mainly as temporal mismatch (about 11 VHL patients scored against records that predate belzutifan) plus passenger genes. Rescoring all 69 patients against HemOncKB V54 (2026-08-28), asking what was valid for that cancer, in that setting, in the year each patient was first treated, does not support the timing half:

  | Era-aware label | Patients | Pilot label |
  |---|---|---|
  | MATCH, received the pick | 8 | 7 EXACT, 1 CLASS |
  | ERA_VALID, valid then but not received | 2 | MISS |
  | NOT_YET_AVAILABLE, valid today, not then | 4 | MISS |
  | MISS, not valid for that cancer and setting even today | 39 | 38 MISS, 1 CLASS |
  | NO_PREDICTION | 16 | NO_PREDICTION |

  Timing accounts for at most 4 patients, and cleanly for 2. Of the 11 VHL patients, 9 were at a first-line metastatic decision; belzutifan is still not a first-line option for sporadic clear cell RCC (FDA 2023-12-14 requires prior PD-1/PD-L1 and VEGF-TKI, LITESPARK-005), and the 2021-08-13 approval is for germline von Hippel-Lindau disease, not the somatic VHL mutations in TCGA-KIRC. The 2 that hold up (TCGA-CZ-4861, TCGA-CJ-5676) were in a curative setting, and belzutifan with pembrolizumab became adjuvant-approved on 2026-06-12 (LITESPARK-022), as a combination. The doc's description of belzutifan as "the objectively correct, current, FDA-approved drug for VHL-driven RCC" overstates both approvals.

  The 6 MATCHes in breast are TP53 patients given generic platinum/anthracycline picks that were in their regimen, which is concordance with routine chemotherapy rather than evidence the mutation-driven ranking works.
- **Risk**: scientific. This changes a reported claim about the system's accuracy and, if adopted, the concordance metric itself. The pilot doc and `validation_results/**` are a human's call, and `scripts/**` is guard-protected.
- **Decisions needed**:
  - ~~Correct the pilot doc's temporal-mismatch section, or annotate it with the rescoring~~ Done 2026-10-22: corrected in place with a dated notice, and the rescoring summarised in the doc's "Era-aware rescoring" section; the raw results table is unchanged
  - Whether era-aware labels (valid then / valid now / never valid) become part of the concordance benchmark, and if so, where the HemOncKB snapshot lives given its CC BY-NC-SA 4.0 licence
  - Whether imputed treatment intent is acceptable: 44 of 69 settings are imputed from M1 stage or progressive/recurrent disease status, 14 are unknown and scored leniently
- **Evidence to weigh**: the analysis lives outside the repository in `openoncology-era/` (`era_score.py`, `era_scores_pilot69.csv`, `era_scores_pilot69_picks.csv`, `RESULTS_pilot69.md`, `RESULTS_vhl11.md`). TCGA timelines come from the GDC API. HemOncKB covers 128 of the 193 drugs patients actually received. Dr. Warner (HemOnc) suggested the relevance-by-year approach and noted TCGA's missing intent can be worked around or imputed; a review call is planned once results are in.

### OO-26: The ranker recommends by gene, ignoring cancer type, line of therapy and alteration type
- **Why**: The 39 era-aware MISSes in OO-25 are wrong for that cancer and setting today, not just then, and they share four causes:
  - **Gene-to-drug across cancer types.** Avapritinib for KIT/PDGFRA/CBL, sonidegib for PTCH1/SMO, alpelisib for PIK3CA and afatinib for EGFR in kidney cancer; afatinib for EGFR in glioblastoma; cisplatin in colorectal. None has evidence for that cancer in HemOncKB.
  - **No line or intent.** Belzutifan ranks first for VHL kidney cancer at a first-line metastatic decision, where it is not indicated.
  - **Alteration type ignored.** Alectinib and brigatinib for an ALK point mutation (H1475Q) when both need an ALK fusion; adagrasib for KRAS G12V when it is G12C-only; cetuximab and panitumumab for a KRAS-mutant colorectal cancer that their FDA labels exclude; somatic VHL treated as germline VHL disease.
  - **Non-oncology drugs in the top 3.** Atenolol, alfuzosin, fenofibrate, ascorbic acid, balsalazide, acetyldigitoxin, glycerol phenylbutyrate. Abarelix, withdrawn from the US market in 2006, ranked for a patient treated in 2013.
- **Risk**: scientific. Every fix here changes which drugs are recommended, through `api/ai/**` and `_LEVEL_TABLE` / `_CANCER_CONTEXT_OVERRIDES` in `api/services/oncokb_evidence.py`.
- **Decisions needed**: whether cancer-type gating applies to Tier 1 and Tier 2 alike; whether the ranker takes line of therapy and intent as inputs at all; how fusion-only and variant-specific indications are encoded; whether non-oncology repurposing candidates may appear in a top 3 shown to a clinician.
- **Worth checking alongside**: OO-21, since the concordance numbers here were computed from protein notation and never passed through VCF ingestion.
- **Progress on non-oncology drugs (2026-10-22)**:
  - The production Tier 2 path already drops them through `services/oncology_atc.py` (added 2026-08-12, after the pilot). `scripts/concordance_pilot_run_pipeline.py` `run_tier2` never calls that gate, so the pilot's top 3s overstate what the app shows. Wiring it in touches `scripts/**` and changes the pilot's reported numbers, so it is a human call.
  - The gate missed salt forms, because the ATC cache is keyed by parent molecule. `atc_codes()` now retries with trailing salt and formulation words stripped, after the full name misses. That removes alfuzosin hydrochloride, doxazosin mesylate, balsalazide disodium and fenofibrate micronized, and classifies afatinib dimaleate, doxorubicin hydrochloride and similar as oncology. Hard gate unchanged.
  - Still getting through: meclofenamate sodium (the cache has `meclofenamic acid`, not `meclofenamate`; the fix is a cache entry in `validation_results/atc_cache.json`, which is protected), capromab (a diagnostic imaging agent with no ATC in the cache), and abarelix (L02, so it passes, but withdrawn from the US market in 2006; needs a withdrawn-drug check).
  - Salt forms of one drug still take separate top-3 slots (afatinib and afatinib dimaleate, alectinib and alectinib hydrochloride). `parent_name()` makes deduplicating them straightforward, but that changes ranking output.
- **Indication gate (2026-10-23), on branch `fix/oo-26-indication-gate`, not merged**:
  - `services/indication_gate.py` drops a candidate only on positive evidence that its indication does not cover the gene, alteration, cancer or line: (gene, drug) rules for ALK, ROS1, NTRK1-3, RET, MET, KRAS, NRAS, EGFR, SMO, PTCH1, PIK3CA, AKT1, PTEN, ESR1, KIT, PDGFRA, VHL, IDH1/2, FGFR2/3, BRCA1/2. No rule, keep. Unknown cancer type, keep with a note, unless the alteration itself disqualifies the drug (a point mutation for a fusion-only drug, a non-G12C variant for a G12C inhibitor). Withheld drugs go to `excluded_candidates` with the reason.
  - Wired into `ai_worker.run_ai_analysis` after `_apply_candidate_pool_policy`, so it covers Tier 1 and Tier 2. `run_ai_analysis` takes optional `line_of_therapy` and `treatment_intent`; nothing passes them yet, so belzutifan in RCC is kept with a note until something does.
  - `scripts/concordance_pilot_run_pipeline.py --indication-gate [--settings settings.json]` applies it to the pilot. Off by default, so the published numbers reproduce unchanged.
  - Measured offline against the stored pilot top 3s: 37 picks withheld across 15 patients, 10 of whom move from a wrong pick to no prediction. The rerun with live Tier 2 and the era rescoring has to happen where the APIs and HemOncKB are.
  - Hard gate is unaffected (the benchmark calls the lookup and ranker directly, not the worker). Checked every `known_drugs` entry in all four benchmark lists against the gate: 1,745 checks, 9 withheld, all adagrasib for KRAS G12V, which the benchmark scores as LEVEL_3B. Adagrasib is a covalent G12C inhibitor; those entries look wrong and are a human call.
  - Where the benchmark asserts an off-label use (alpelisib in cervical, endometrial and colorectal; erlotinib and gefitinib in glioma; afatinib in HNSCC; capivasertib in NSCLC and endometrial; IDH inhibitors outside their labels; FGFR2 amplification), the rules follow the benchmark and say so in their `basis`. Each is worth a second look.
  - Not covered: BRAF V600 (tumour-agnostic), ERBB2, MTOR/TSC1/TSC2.

### OO-27: Without an OncoKB token, the worker marks every VCF variant untargetable
- **Why**: Step 2 of `ai_worker.run_ai_analysis` decides targetability only through `_query_oncokb_with_status`, which calls the live OncoKB API and returns `(None, not_attempted)` when `ONCOKB_API_TOKEN` is unset. No variant becomes targetable, so Step 4 never runs and every submission ends in `no_targetable_mutation`, even with OO-21's notation fixed. The curated `_LEVEL_TABLE`, which CLAUDE.md calls a supported mode rather than a degraded one, is consulted later in `_apply_candidate_pool_policy` but never at the targetability gate. The benchmarks call `get_all_drugs_for_variant_live` directly, which does fall back to the table, so they never see this.
- **Risk**: scientific. Letting the static table decide targetability changes which submissions get recommendations at all.
- **Decisions needed**: whether Step 2 falls back to `get_all_drugs_for_variant_live` (which already merges live and static) when no token is set; which table levels count as targetable (today LEVEL_1, 2 and 3A from the live API); and how the report marks that the static table, not live OncoKB, served the result.
- **Files to consider**: api/workers/ai_worker.py `_query_oncokb_with_status` and Step 2 of `run_ai_analysis`, api/services/oncokb_evidence.py
- **Decided and done (2026-10-23): fall back to the live-plus-static lookup when there is no token.** `_query_oncokb_with_status` now calls `_query_static_table`, which asks `get_all_drugs_for_variant_live` with the submission's cancer type and returns the same shape as a live answer. Targetable levels are unchanged (1, 2, 3A). Both Step 2 and the repurposing step's OncoKB call use it.
  - The variant records `evidence_lookup_status = static_table`, a new value (migration 0018, Postgres `ALTER TYPE ... ADD VALUE`), and the report prints "Actionability from the built-in evidence table, not live OncoKB". The result-level `evidence_provenance` already recorded which table answered and its date.
  - A variant with no protein change is not looked up and stays `not_attempted`, so the table's gene-level fallback cannot mark every variant in a gene targetable. A table with no entry is a checked negative, not a failure.
  - Probed with no token: EGFR T790M from `samples/egfr_t790m_demo.vcf` becomes LEVEL_1 targetable with osimertinib; TP53 R175H, EGFR A597P, KRAS G12V and ALK H1475Q stay untargetable. Hard gate unchanged.
  - Not done: a token that is set but failing (`unavailable`) still gets no fallback, so a network outage stays visible as a failed lookup rather than quietly switching source. Migration 0018 was not run against Postgres locally (no Postgres here); CI's `alembic upgrade head` on postgres:16 is its first real run.

### OO-29: A MSK-CHORD benchmark that can actually measure mutation matching
- **Why**: The 69-patient TCGA pilot cannot measure a mutation ranker: most patients received chemotherapy chosen by cancer type, and 45 of 69 had kidney cancer treated without genomic guidance. MSK-CHORD (Nature 2024) has 24,950 patients with IMPACT panel data, treatment timelines, and modern targeted-drug use. This replaces the pilot as the mutation-matching benchmark.
- **Done (2026-10-26), on branch `fix/oo-29-mskchord-benchmark`, not merged**:
  - `scripts/mskchord/fetch_mskchord.py` pulls the 5,377 MSK-CHORD patients who received a targeted therapy, plus their mutations and discrete CNAs for 56 actionable genes, via the cBioPortal API and the datahub timeline tables.
  - `scripts/mskchord/targeted_drug_targets.py` is the per-drug map of the alterations that justify each targeted drug under its FDA label (EGFR TKIs → any EGFR mutation, sotorasib → KRAS G12C, trastuzumab → ERBB2 amplification, PARP inhibitors → BRCA/HRR). This is the ground truth; the ranker does not substitute it.
  - `scripts/mskchord/score_mskchord.py` reports ground-truth coverage and, with `--results`, the ranker's top-3 hit rate on the benchmarkable subset.
  - `validation_results/msk_chord_targeted_cohort.json` is the pre-fetched cohort as of 2026-10-26.
- **Numbers (2026-10-27, after fusions, CIViC filter and insertion-order ranking)**:
  - 5,190 patients with targeted-therapy events + alteration data.
  - **2,505 benchmarkable** (alteration matches the drug they received under its label).
  - 53 unevaluable (receptor-driven drugs with no genomic indication under the label).
  - 2,632 miss (CDK4/6 inhibitors, mTOR inhibitors and similar receptor-driven drugs; correctly outside the mutation ranker's scope).
  - Per-drug coverage of the benchmarkable set: osimertinib 1035, erlotinib 461, alectinib 237, alpelisib 209, afatinib 146, olaparib 128, crizotinib 128, tucatinib 94, sotorasib 92, encorafenib 83, trametinib 83, dabrafenib 74.
- **Ranker results (offline, static table + CIViC fallback, 2026-10-27)**:
  - Static only (2026-10-26): 1,697 of 2,222 benchmarkable; 63.5% exact / 100% same-class.
  - CIViC nightly fallback added (2026-10-27, morning): 1,960 of 2,222; 62.1% exact / 96.9% same-class.
  - With fusions + CIViC target-filter + preserved OncoKB clinical order (2026-10-27, afternoon): 2,236 of 2,505 benchmarkable; 91.3% exact / 100.0% same-class on ran-on.
  - **With CNA path (ERBB2 amplification, CDKN2A deep deletion) wired into the qualifying-alteration emitter (2026-10-27, evening): 2,466 of 2,505 benchmarkable (98.4% coverage); 84.9% top-3 exact / 100.0% top-3 same-class on ran-on; 70.6% top-1 exact / 99.5% top-1 same-class.**
  - Head-to-head vs an OncoKB-only baseline (same scorer, same cohort, same qualifying-alteration logic, only the CIViC fallback stripped): coverage 85.9% → 98.4% (+12.6 pp); top-3 exact 73.7% → 83.6% (+9.9 pp); top-3 class 85.9% → 98.4% (+12.6 pp).
  - Fusions: 389 patients in the targeted cohort carry an actionable fusion, pulled via cBioPortal `/structural-variant/fetch`; stored in `validation_results/msk_chord_fusions.json`.
  - Runner: `scripts/mskchord/run_openoncology_on_mskchord.py`; CIViC data: `validation_results/civic_actionable_evidence.json`; metrics dump: `validation_results/msk_chord_scored_metrics.json`.
- **Preprint**: `preprints/msk_chord_benchmark.md` is a Research-Square-ready 3-page tech note describing the cohort, scorer, head-to-head and per-cancer breakdown. Not yet submitted.
- **Known residual limit**: the ranker is not line-of-therapy aware. The 221 ERBB2-amp breast patients on later-line HER2 drugs (lapatinib, neratinib, tucatinib, trastuzumab emtansine) correctly match on class (100%) but miss on exact drug because OncoKB ranks trastuzumab/pertuzumab first. This is the chief driver of breast-cancer top-3 exact being 64% while class is 100%. A follow-up could rank by first-vs-later line.
- **Follow-ups**: live OncoKB token would cover the remaining 39 unmatched benchmarkable patients (mostly rare TSC1/TSC2 missense).

---

## Done


<!-- Merged entries, newest first. Trim periodically. -->

### OO-20: The deployed image renders a PDF
Merged in [#164](https://github.com/immortal71/openoncology/pull/164). `api/Dockerfile`
installed gcc, libpq-dev and curl and none of WeasyPrint's native dependencies, so
`import weasyprint` raised OSError in the container and every oncologist report and
patient letter fell back to HTML. The route is named `oncologist-report.pdf` and it
returned `text/html`, at a 200, without saying so.

Pango brings glib, harfbuzz and fontconfig with it; cairo and gdk-pixbuf have not been
needed since WeasyPrint v53. `fonts-dejavu-core` is separate and still required, because
fontconfig with no font installed lays the text out correctly and draws every glyph as a
box.

The suite could not have caught this: it runs where those libraries are present, so every
assertion about PDF generation passed while the image took the other branch. ci.yml now
builds the image, renders a report inside it, and fails unless the bytes are a PDF;
`publish-images` depends on that job, so an image that cannot render one is not published.

### OO-15: Session lifetimes applied; security officer still unassigned
Half closed in [#148](https://github.com/immortal71/openoncology/pull/148). A
`kcadm` Job applies `ssoSessionIdleTimeout` 1800s and `ssoSessionMaxLifespan`
28800s on install and upgrade, which are the figures HIPAA_COMPLIANCE.md had been
quoting without setting. `.github/CODEOWNERS` now exists.

The entry stays in Ready. A file naming a code owner is not a person accepting
the §164.308(a)(2) role, and nothing in a pull request can record an appointment.

### OO-17: The degraded-evidence condition is alertable
Merged in [#147](https://github.com/immortal71/openoncology/pull/147). A counter
beside the log call could not work: the fallback count is a module global in the
ai worker, a separate process from the API with no metrics endpoint, and it
resets on restart, which is when a sustained run would look like it had stopped.
The signal is read from `results.evidence_provenance` by a postgres_exporter
query instead. Two metrics declared in `api/main.py` and never incremented were
removed rather than wired up.

### OO-9: Keycloak's database sized from its own values
Merged in [#146](https://github.com/immortal71/openoncology/pull/146). It read
the application sub-chart's values, so production gave a realm database a 200Gi
volume and resizing one silently resized the other. `volumeClaimTemplates` is
immutable, so applying this to an existing cluster needs a recreate; the runbook
records that next to the note that this database is not backed up.

### OO-16: Exporters deployed, queue depth alertable
Merged in [#145](https://github.com/immortal71/openoncology/pull/145).
`redis_key_size{key="gdpr"}` is the number of erasure requests waiting. Celery
task events had to be enabled for any task metric to exist at all, which is
guarded, because without them every `celery_*` rule evaluates against an absent
series and stays silent.

### OO-18: The chart deploys the object storage it pointed at
Merged in [#144](https://github.com/immortal71/openoncology/pull/144).
`MINIO_ENDPOINT` named `{release}-minio:9000` and nothing created it, so every
upload, report write and object deletion failed, as did the backup job. Found
while scoping OO-5, because a policy cannot grant egress to a pod nothing
creates.

### OO-5: Network policies for the chart, off by default
Merged in [#143](https://github.com/immortal71/openoncology/pull/143). Not a port
of the `infra/k8s` set: that selects on a label `_helpers.tpl` never emits, uses
equality where workers render four component values, and points at Keycloak's
database rather than the application's. All three fail closed and render clean.

### OO-14: A compliance mark must cite something that exists
Merged in [#138](https://github.com/immortal71/openoncology/pull/138).
`api/tests/test_compliance_claims.py` fails the build when a row in
`HIPAA_COMPLIANCE.md` claims implementation and cites a path or mechanism that is
absent. It found two more the moment it existed: the security officer row cited a
CODEOWNERS file that does not exist, and automatic log-off quoted session
timeouts nothing sets. Both corrected; the gaps behind them are OO-15.

The check had two defects of its own before merge, both recorded in the PR. It
read only backticked tokens, so it missed CODEOWNERS entirely. And its evidence
search covered `api/`, so it matched its own pattern list and reported a backup
mechanism present that was not. A check that passes by reading its own source is
the pathology it exists to catch, one level up.

### OO-13: Prometheus rules that can fire, against targets that exist
Merged in [#140](https://github.com/immortal71/openoncology/pull/140).
`rule_files: []` and `alertmanagers: []` meant every metric was collected and no
alert could fire. Adding rules first required correcting the scrape config: four
of seven jobs pointed at exporters deployed nowhere and reported `up == 0`
permanently, which pages continuously once anything watches `up`.

Alertmanager's address is deliberately still unset. A wrong one fails silently.

### OO-12: Nightly database backup, restore not yet exercised
Partially addressed in [#141](https://github.com/immortal71/openoncology/pull/141).
The entry **stays open** in Ready. A `pg_dump` CronJob and
`docs/RUNBOOK_BACKUP_RESTORE.md` exist; nobody has restored from one, so
`HIPAA_COMPLIANCE.md` keeps §164.308 at not-implemented.

### OO-11: BWA-MEM2 rebuilt the reference index every task
Merged in [#139](https://github.com/immortal71/openoncology/pull/139). The
process staged the FASTA and none of the index files beside it, so it rebuilt
what setup had already built, at roughly 30 minutes and 12 GB per task. A missing
index now fails up front naming `download_references.sh`, instead of being
silently absorbed.

### OO-10: Paired-end reads carried from upload to aligner
Merged in [#136](https://github.com/immortal71/openoncology/pull/136). The FASTQ
path processed paired-end data as single-end at every stage and `POST /api/submit`
accepted one of the two files a sequencer produces. Read groups also carried a
constant `SM:patient`, so every BAM claimed the same sample name.

This changes what the pipeline computes, so variant-calling measurements taken
before it are not comparable with any taken after.

### Runbook for closing the variant-calling accuracy gate
Merged in [#134](https://github.com/immortal71/openoncology/pull/134).
`docs/RUNBOOK_VARIANT_CALLING_VALIDATION.md`, scoped to chr20 in NIST confident
regions to match the existing reference figure. Writing it is what found OO-10
and OO-11.

### HIPAA checklist corrected, four controls were never implemented
Merged in [#137](https://github.com/immortal71/openoncology/pull/137) and
[#138](https://github.com/immortal71/openoncology/pull/138). Contingency planning
cited WAL archiving and object-store versioning, neither configured, pointing at
Keycloak's database rather than the application's. Data-at-rest cited PostgreSQL
checksums, which are off.

### OO-4: Refresh the stale figures in the pyproject coverage comment
Merged in [#132](https://github.com/immortal71/openoncology/pull/132). Rebased
onto main after #130 and #131, and re-measured: the figures the branch was
carrying had themselves gone stale by two merges while it sat open. The comment
now carries its date as part of the number, because `fail_under` can be pinned by
a test and a measurement of a moving suite cannot.

### Intended use stated on every output path
Merged in [#131](https://github.com/immortal71/openoncology/pull/131), recorded as
F18 in [risk_analysis.md](docs/risk_analysis.md). The FHIR export carried no
research-use marker and reported `status: final`, which in FHIR R4 means complete
and verified; the only thing verified was that the pipeline had finished. Unreviewed
reports are now `preliminary`. The results payload's only disclaimer lived inside
`patient_summary`, which fails to None, so it vanished exactly when generation went
wrong and the response still carried drug names and OncoKB levels. `intended_use` is
now a top-level typed field with conservative defaults.

Labelling is not validation. Nothing here moves a gate in `REGULATORY_FRAMEWORK.md`
section 3.

### Deployment path: unconsumed gdpr queue, missing beat, readiness probe, JWKS auth
Merged in [#130](https://github.com/immortal71/openoncology/pull/130). Four absences
that no check could catch because every check asserted a positive about something
present. `task_routes` sent erasure tasks to a `gdpr` queue nothing consumed, so
`DELETE /api/me` promised deletion within 30 days and the message sat in Redis. The
chart had no Celery Beat, so neither periodic task had ever fired in Kubernetes. The
readiness probe asked `/health`, which answers 200 unconditionally. Auth refetched
one Keycloak key per request and passed `audience` with `verify_aud: False`.

A `validate-manifests` job now renders the chart through kubeconform. Its first
version passed in eight seconds having rendered nothing: helm's dependency error went
to stderr, kubeconform read empty stdin and reported "Valid: 0", and the pipe returned
kubeconform's status. Fixed in the same PR under `pipefail` with assertions on the
rendered output, which is the section 7 lesson arriving inside the commit that was
about the same failure.

### OO-3: Add a drift guard test for the coverage threshold
Merged in [#128](https://github.com/immortal71/openoncology/pull/128).
`api/tests/test_coverage_threshold_consistency.py` reads `fail_under` from
`pyproject.toml` and fails the build if the README badge, the `CONTRIBUTING.md`
prose, or a `--cov-fail-under` literal in `Makefile` or `ci.yml` disagrees with it.

The badge is checked in both representations it carries on one line, URL-escaped
and ASCII. Verified by breaking only the URL form and leaving the alt text correct:
a check written against a single representation passes that edit with the badge
visibly wrong, which is the shape the original 62 drift took.

### OO-2 follow-up: CONTRIBUTING.md falls out of step with CI
Merged in [#127](https://github.com/immortal71/openoncology/pull/127) alongside OO-2
itself, plus `CONTRIBUTING.md:306` in the reconcile that followed. The entry was
raised because `CONTRIBUTING.md` sat outside OO-2's declared **Files** list, and
widening scope silently is what that list exists to prevent. Both mentions now point
at `pyproject.toml` as the source of the number instead of quoting a flag CI no longer
passes.

### OO-2: Single-source the backend coverage threshold in pyproject.toml
Merged in [#127](https://github.com/immortal71/openoncology/pull/127) as `ba6c04a`.
`[tool.coverage.report] fail_under = 52` now declares the gate once; `Makefile` and
`ci.yml` inherit it, and the api-suite invocation keeps its explicit
`--cov-fail-under=0` because coverage is only complete after the second run appends.
Verified locally at 1102 + 42 tests passing, 61% total against the 52 gate.

One consequence to remember: any `pytest --cov=...` run now inherits the gate unless
it opts out, so a single suite on its own reports around 14% and exits non-zero with
every test passing. `CONTRIBUTING.md` documents this.

### OO-1: Correct the stale 62% coverage figures in README and CONTRIBUTING
Merged in [#124](https://github.com/immortal71/openoncology/pull/124) as `fd2bf89`.
The README badge and both `CONTRIBUTING.md` mentions moved from 62 to 52, in every
representation the badge carries (the URL-escaped `%E2%89%A5` segment and the ASCII
`>=` alt text). The `0.625` Precision@3 ceiling elsewhere in the docs is an unrelated
number and was confirmed untouched.


### Results workspace revision, November 20
- Redesigned the four /lab/results views on redesign/phase-0. The review workspace has a case header, keyboard-accessible tabs, searchable candidate inspector, protein track, source ledger, gap filters, and candidate PDF export. Browser checks covered desktop and mobile layouts.

- Revised the Submit form hierarchy to put the cancer type and required files before the demo link.
- Polished the Submit header, nested corners and file controls, including selected-file feedback.
- Grouped the required case files into two upload rows. Verified genomic file selection and replacement at mobile and desktop widths.
- Applied shared typography, keyboard-focus, reduced-motion and control refinements, and aligned the analysis screen with case intake.
- Unified the upload and analysis progress indicator and respected reduced motion during analysis.
- Removed the demo results link below the Submit form.
- Polished the candidate inspector and placed citation availability beside the provider names and source inspection action.
- Refined variant selection, provider column alignment and gap filter states across the results workspace.
- Replaced the variant sidebar with an inline variant selector above the full-width inspector.
- Replaced the inline variant selector with an initially collapsed comparison table and inline evidence disclosures.
- Refined the Atlas hero reading order and condensed its mobile demo pathway.
