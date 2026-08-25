# OpenOncology Backlog

Git-tracked project state. Agents read this at session start and update it at
session end, so work survives context compaction, restarts, and closed laptops.

Sections are ordered by pipeline position. `/next` pulls from the top of
`## Ready`. Nothing pulls from `## Needs human decision`.

---

## Ready

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

### OO-2: Single-source the backend coverage threshold in pyproject.toml
- **Why**: The number 52 is currently duplicated across `Makefile` and `ci.yml` with a comment recording that they already drifted once (62 vs 63), letting a local `make test-backend` pass what CI rejected; declaring it once removes the failure mode instead of re-synchronising after it happens.
- **Files**: pyproject.toml, Makefile, .github/workflows/ci.yml
- **Acceptance**:
  - `pyproject.toml` gains a `[tool.coverage.report]` section with `fail_under = 52` and a short comment naming it the single source of truth, replacing the history comment currently parked at `ci.yml:210-225` (move that history into pyproject rather than deleting it)
  - The second pytest invocation in both `Makefile` (`test-backend`, `coverage`) and `ci.yml` ("Run backend tests (ai suite)") no longer passes `--cov-fail-under` at all; the first invocation keeps its explicit `--cov-fail-under=0`, which still overrides the config value
  - `rg -n 'cov-fail-under=[1-9]' -- Makefile .github/workflows/ci.yml` returns nothing, so the only `--cov-fail-under` literal left in either file is the explicit `=0` on the first pytest invocation (rg has no lookaround — do not reach for `(?!0)`, it is a parse error, not a zero-match)
  - Temporarily editing `fail_under` to `99` makes `make coverage` fail with pytest-cov's "Coverage failure: total of ... is less than fail-under" message; restoring `52` makes it pass — verified before the change is committed
  - The Makefile "keep --cov-fail-under in step with ci.yml" comment at `Makefile:30-32` is replaced by one pointing at `pyproject.toml`, and `CONTRIBUTING.md:240-243` still reproduces the exact commands CI runs
- **Out of scope**: changing the threshold value itself; `[tool.coverage.run]` `omit` list; adding coverage reporting services or badge automation; `api/tests/**`.
- **Risk**: medium

### OO-3: Add a drift guard test for the coverage threshold
- **Why**: OO-2 removes today's duplication, but nothing stops the next contributor from reintroducing a hardcoded `--cov-fail-under` or quoting a different number in the docs; a cheap test fails the PR that does it.
- **Files**: api/tests/test_coverage_threshold_consistency.py (new)
- **Acceptance**:
  - The test reads `fail_under` from `pyproject.toml` via `tomllib` and asserts that the README badge line, both `CONTRIBUTING.md` mentions, and any `--cov-fail-under=<nonzero>` occurrence in `Makefile` / `.github/workflows/ci.yml` agree with it (the README check must decode the URL-escaped `%E2%89%A5` form)
  - The test asserts that no nonzero `--cov-fail-under` literal survives in `Makefile` or `.github/workflows/ci.yml`, so the config stays the only source
  - The test is hermetic: no network, no subprocess, paths resolved relative to the repo root rather than the CWD, and it passes under both `pytest api/tests/` and a bare `pytest` from the repo root
  - Hand-editing the README badge to a different number makes the test fail with a message naming the offending file and the two disagreeing values
- **Out of scope**: enforcing the number in any other repo (`docs/**` prose currently carries no threshold figure — do not add one); asserting the reported coverage percentage, only the configured gate; touching the existing test suite or conftest.
- **Risk**: low

---

## In progress

<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

---

## In review

<!-- Entry plus PR URL. Cleared by hand when merged. -->

### OO-1: Correct the stale 62% coverage figures in README and CONTRIBUTING
- **PR**: https://github.com/immortal71/openoncology/pull/124
- **Branch**: `docs/coverage-threshold-52`, cut from `main`, one commit `651c654`
- **Validator**: PASS. Diff confined to the two files, gates still 52 at `Makefile:35`, `Makefile:47`, `ci.yml:228`. Suites green (877+1 xfail api, 42 ai), coverage 54.70%. The `0.625` Precision@3 ceiling confirmed unchanged.
- **Reviewer**: Approve, no blocking findings.
- **Why**: The README badge and CONTRIBUTING both advertise a 62% backend coverage gate that no longer exists; a contributor copying the documented pytest command gets a stricter gate than CI enforces and a local failure CI would have passed.
- **Files**: README.md, CONTRIBUTING.md
- **Acceptance**:
  - `README.md:10` badge renders "coverage ≥52%" — both the shields.io path segment (`coverage-%E2%89%A552%25`) and the `alt` text are updated; badge colour, style and position in the block are unchanged
  - `CONTRIBUTING.md:242` reads `--cov-fail-under=52`, matching the second pytest invocation in `Makefile` and `.github/workflows/ci.yml` character for character apart from the leading `PYTHONPATH=.`
  - `CONTRIBUTING.md:295` prose reads `--cov-fail-under=52`
  - `rg -n '62' -- README.md CONTRIBUTING.md docs/` deliberately over-matches; inspect every hit and confirm none of them refers to the backend coverage gate in any representation (`62%`, the rendered `≥62%`, the URL-escaped `%E2%89%A562`, `cov-fail-under=62`). A narrower pattern can exit clean while a stale form survives, so a few false positives to eyeball is the point, not a defect in the check.
  - No file outside README.md and CONTRIBUTING.md is modified; no `--cov-fail-under` value in `Makefile` or `ci.yml` changes
- **Out of scope**: the actual gate value in `Makefile` / `ci.yml` (52 stays 52); the `0.62` structural-ceiling numbers in `PROJECT_COMPLETION_STATUS.md` (unrelated benchmark metric); `CLAUDE.md:56-63`, whose "CONTRIBUTING.md still says 62 and the README badge says 62%" note goes stale with this change but is the repo owner's file to edit; frontend Vitest coverage.
- **Risk**: low

---

## Needs human decision

<!-- Anything an agent declined to do unattended: guard-hook blocks, validator
     BLOCKs, mis-scoped entries, and anything the planner marked
     Risk: scientific. This section is the safety valve. When it grows, that is
     the system working, not failing. -->

---

## Done

<!-- Merged entries, newest first. Trim periodically. -->
