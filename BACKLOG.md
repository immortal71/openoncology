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

---

## In progress

<!-- One entry maximum. An entry stranded here means a session died mid-work;
     /standup will surface it. -->

### OO-4: Refresh the stale figures in the pyproject coverage comment
- **Why**: The comment moved into `[tool.coverage.report]` by OO-2 cites 53.93% over 8,353 production statements with 844 api tests. The suite has grown since: it now measures about 61% over 8,798 statements with 1,102 api tests. Anyone reading the comment concludes the gate sits a point below the measured total, when it actually sits nine points below, so the gate catches less than the comment claims it does.
- **Files**: pyproject.toml
- **Acceptance**:
  - The comment cites the current measured coverage, statement count and api test count, taken from an actual local run rather than copied from this entry
  - The narrative explaining why the number moved 63, 69, 52 is preserved, not replaced
  - `fail_under` itself is unchanged at 52
  - `make test-backend` still passes
  - `pytest api/tests/test_coverage_threshold_consistency.py` still passes
- **Out of scope**: changing the threshold; the `omit` list; README and CONTRIBUTING, which quote the gate rather than the measurement.
- **Risk**: low

---

## In review

<!-- Entry plus PR URL. Cleared by hand when merged. -->

---

## Needs human decision

<!-- Anything an agent declined to do unattended: guard-hook blocks, validator
     BLOCKs, mis-scoped entries, and anything the planner marked
     Risk: scientific. This section is the safety valve. When it grows, that is
     the system working, not failing. -->

---

## Done

<!-- Merged entries, newest first. Trim periodically. -->

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
