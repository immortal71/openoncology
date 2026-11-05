# Project status

Reviewed November 5, 2026 against published main at `cdff27f`.

OpenOncology is a research prototype. The first planned offering is treatment-evidence interpretation for sequencing labs, followed by hospitals without molecular tumor boards. The code is public; no paying customers or hospital deployments are reported.

## Working components

The repository contains a Next.js interface, FastAPI API, genomic-file upload, VCF parsing, evidence services, a composite drug ranker and report generation. Celery, PostgreSQL, Redis and MinIO support the workflow. Some components require external services, data credentials or local resources.

Latest main CI [run 41783696590](https://github.com/immortal71/openoncology/actions/runs/41783696590) passed backend tests, frontend checks and demo E2E tests, migration checks, deployment-manifest checks and a container PDF-render check. These checks establish tested software behavior, not a clinically validated deployment. The E2E tests use demo mode.

## Benchmark status

The October 27 CHORD artifacts contain 2,505 benchmarkable patients and 2,466 predictions. Exact top-three agreement is 83.6% over all benchmarkable patients, or 84.9% among predictions. The runner selects input alterations using the received treatment and uses evidence-level ordering rather than the application's composite ranker. See [benchmark scope](docs/BENCHMARK.md#msk-chord-evidence-lookup-benchmark).

The latest main CI hard gate printed standard P@3 of 0.801, Hit@3 of 100% and zero false positives. That curated regression gate differs from CHORD and the frozen 50-case holdout. The [earlier engineering inventory and benchmark history](https://github.com/immortal71/openoncology/blob/cdff27f20ce86c651be3cb0944f7ec755b6e2cb1/PROJECT_COMPLETION_STATUS.md) remain available; their figures should not be presented as current results.

## Integration and validation work

- The main application candidate path starts with the first targetable mutation. A complete patient-wide ranking workflow needs further work and evaluation.
- Copy-number and fusion support in the benchmark is not validation of the normal application upload path.
- Treatment-line rules exist, but normal submissions do not collect and forward treatment-line data.
- No dedicated local availability or affordability layer is implemented.
- A self-hosted prototype and frontend demo exist. The planned hosted lab service and site validation are not complete.
- Prospective clinical validation, local generalisation and deployment readiness remain unestablished. See the [clinical-use roadmap](docs/ROADMAP_TO_CLINICAL_USE.md).

## Product priorities

Build a hosted evaluation workspace, fit the genomic-report workflow used by labs, add local drug access and cost information, and evaluate results with oncologists before site deployment. The proposed lab price is $25 per report; hospitals are the next segment.

## Separate experiments

Discovery briefs, a pharma marketplace and crowdfunding modules remain in the codebase. Tests and routes for those modules do not make them part of the initial product or establish manufacturing or treatment capability. See [product scope](docs/PRODUCT_SCOPE.md).
