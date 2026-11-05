# Contributing

OpenOncology welcomes bug fixes, documentation improvements and evidence review. Start with the [README](README.md), [product scope](docs/PRODUCT_SCOPE.md) and [code of conduct](CODE_OF_CONDUCT.md).

## Choose a contribution

Use [issues](https://github.com/immortal71/openoncology/issues) to report bugs or propose changes. Explain the problem, who it affects and what would improve it. Discuss substantial changes before implementing them, especially changes to evidence handling or evaluation.

Use synthetic examples in public reports. Do not attach patient records, secrets or private correspondence. Report community concerns using the contact in the code of conduct.

## Set up the project

The [setup guide](docs/SETUP.md) covers Docker, local services, environment variables and Windows instructions. The source is split into:

| Directory | Purpose |
|:--|:--|
| `web/` | Next.js interface and frontend tests |
| `api/` | FastAPI services, workers and application tests |
| `ai/` | Separate research package and tests |
| `pipeline/` | Nextflow genomic preprocessing |
| `docs/` | Product, developer and evaluation documentation |

Match the conventions in the surrounding files. Keep the change focused and avoid unrelated formatting or dependency updates.

## Run checks

From the repository root, `make help` lists the available commands. The Makefile uses a POSIX shell; use Git Bash on Windows.

```bash
make lint
make test-frontend
make test-backend
make test-e2e
```

For frontend-only work:

```bash
cd web
npm ci
npm run type-check
npm run lint -- --max-warnings 0
npm run test:run
```

The API and top-level AI test suites run in separate Python processes because both packages use the import name `ai`. Run backend checks through `make test-backend` so coverage is combined correctly. The coverage gate comes from `fail_under` in `pyproject.toml`, currently 52. Do not duplicate or lower the threshold in a command to make a check pass.

Frontend E2E tests use demo mode. They do not establish that a backend deployment or clinical workflow has been validated.

## Changes to scientific behavior

Ranking rules, evidence tables, benchmark cases, cohort selection, scoring and published claims need explicit scientific review. Describe the evidence for a proposed change and how it will be evaluated. Keep the original evaluation artifacts available.

Do not tune against a holdout, inspect output to manufacture an answer key, or count a research escalation as a successful treatment match. A higher score alone is not evidence that a change is better.

Repository instructions protect scientific paths. Do not bypass those controls through a worktree, alternate script or file copy. If a proposed change is blocked, record it in `BACKLOG.md` under `Needs human decision`. Changes to a published preprint require an explicit correction process rather than a silent edit.

See [methods](docs/METHODS.md), [benchmark reference](docs/BENCHMARK.md) and [paper reconciliation](docs/PAPER_VS_CURRENT_STATE.md) before proposing a scientific change.

## Documentation and media

Put user instructions, technical reference and research history on the appropriate pages in [the documentation guide](docs/README.md). Keep the README focused on the product and a reader's next step. Distinguish implemented features from planned work.

Use demonstration data for screenshots. Caption the interface and identify mock or saved outputs. Keep GIFs short, include a static alternative and follow the [media guide](docs/MEDIA.md).

## Submit a pull request

Create a focused branch from the latest `main`. Explain the user-visible problem, what changed and which checks passed. Note any limitations. Add screenshots for visible interface changes and link related issues.

Do not include generated caches, local credentials, patient files or unrelated edits. Maintainers review the change and its checks before merging. Merging is manual.
