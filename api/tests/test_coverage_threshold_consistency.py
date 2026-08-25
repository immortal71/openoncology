"""The backend coverage gate is declared once. These tests fail if it stops being.

`pyproject.toml` `[tool.coverage.report] fail_under` is the only place the number
lives. `Makefile` and `.github/workflows/ci.yml` inherit it by omitting
`--cov-fail-under` on the invocation that enforces it, and README and CONTRIBUTING
quote it as prose.

Prose has no compiler, which is the whole problem. Before the number was
consolidated it had drifted twice: 62 in `Makefile` against 63 in `ci.yml`, so a
local `make test-backend` passed what CI rejected; and later the README badge and
CONTRIBUTING sat at 62 for four commits while the enforced gate moved 62, 40, 63,
69, 52 underneath them. Nothing failed, because nothing was checking.

These tests are the check. They are deliberately literal about representation: the
README badge carries the number twice on one line, once URL-escaped inside the
shields.io path and once as ASCII in the `alt` text, and an earlier sweep that
matched only one of those forms would have reported clean with the other stale.

Hermetic by construction: file reads only, no network, no subprocess, and every
path resolved from `__file__` rather than the working directory, so the suite
behaves the same under `pytest api/tests/` and a bare `pytest` from the repo root.
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Files that quote the gate. Anything added here is covered by the sweep below.
MAKEFILE = "Makefile"
CI_WORKFLOW = ".github/workflows/ci.yml"
README = "README.md"
CONTRIBUTING = "CONTRIBUTING.md"

# `--cov-fail-under=0` is not a second source of truth. It is an explicit opt-out on
# the api-suite invocation, which runs before the ai suite has appended its coverage
# and would otherwise fail on a partial total. Only nonzero literals are drift.
COV_FAIL_UNDER = re.compile(r"--cov-fail-under=(\d+)")

# The badge encodes U+2265 (>=) as %E2%89%A5 and the trailing percent as %25.
BADGE_URL_FORM = re.compile(r"coverage-%E2%89%A5(\d+)%25")
BADGE_ALT_FORM = re.compile(r"Backend coverage >= (\d+)%")

# CONTRIBUTING names pyproject as the source and quotes the current value beside it.
CONTRIBUTING_PROSE = re.compile(
    r"`fail_under` in `pyproject\.toml`, currently (\d+)"
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def configured_threshold() -> int:
    """The single source of truth, read the way coverage itself reads it."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)
    return config["tool"]["coverage"]["report"]["fail_under"]


def test_pyproject_declares_the_threshold():
    """Removing the declaration must fail loudly, not silently drop the gate."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)

    report = config.get("tool", {}).get("coverage", {}).get("report", {})
    assert "fail_under" in report, (
        "pyproject.toml has no [tool.coverage.report] fail_under. That section is "
        "the only place the backend coverage gate is declared; without it, neither "
        "make test-backend nor CI enforces any threshold at all."
    )
    assert isinstance(report["fail_under"], int), (
        f"pyproject.toml fail_under is {report['fail_under']!r}, expected an int"
    )


def test_readme_badge_matches_configured_threshold():
    """Both representations on the badge line, not just whichever one a grep found."""
    expected = configured_threshold()
    readme = _read(README)

    url_match = BADGE_URL_FORM.search(readme)
    assert url_match is not None, (
        f"{README}: no coverage badge matching {BADGE_URL_FORM.pattern}. If the badge "
        "was reworded, update this test rather than deleting it, or the number goes "
        "back to being unchecked."
    )
    assert int(url_match.group(1)) == expected, (
        f"{README}: coverage badge URL says {url_match.group(1)}, but "
        f"pyproject.toml [tool.coverage.report] fail_under is {expected}. "
        "The badge advertises a gate the project does not enforce."
    )

    alt_match = BADGE_ALT_FORM.search(readme)
    assert alt_match is not None, (
        f"{README}: coverage badge has no alt text matching "
        f"{BADGE_ALT_FORM.pattern}. Screen readers would get no number at all."
    )
    assert int(alt_match.group(1)) == expected, (
        f"{README}: coverage badge alt text says {alt_match.group(1)}, but "
        f"pyproject.toml fail_under is {expected}. The rendered badge and its alt "
        "text disagree, which a check on either one alone would miss."
    )


def test_contributing_matches_configured_threshold():
    expected = configured_threshold()
    contributing = _read(CONTRIBUTING)

    prose_match = CONTRIBUTING_PROSE.search(contributing)
    assert prose_match is not None, (
        f"{CONTRIBUTING}: no passage matching {CONTRIBUTING_PROSE.pattern}. That "
        "sentence is what tells a contributor where the number comes from; if it "
        "was reworded, update this pattern so the value stays checked."
    )
    assert int(prose_match.group(1)) == expected, (
        f"{CONTRIBUTING}: prose says the gate is {prose_match.group(1)}, but "
        f"pyproject.toml fail_under is {expected}. A contributor reading the docs "
        "would expect a different threshold than CI applies."
    )


def test_no_nonzero_cov_fail_under_survives_in_makefile_or_ci():
    """The flag must not reappear. A literal there is a second source of truth."""
    expected = configured_threshold()

    for relative_path in (MAKEFILE, CI_WORKFLOW):
        for match in COV_FAIL_UNDER.finditer(_read(relative_path)):
            value = int(match.group(1))
            if value == 0:
                continue
            raise AssertionError(
                f"{relative_path}: found --cov-fail-under={value}. The threshold is "
                f"declared once in pyproject.toml (currently {expected}) and inherited "
                "here. Passing it on the command line reintroduces the duplication "
                "that let Makefile and ci.yml drift apart (62 against 63), so a local "
                "make test-backend passed what CI rejected. Drop the flag; only the "
                "explicit =0 opt-out on the api-suite invocation belongs."
            )


def test_any_documented_threshold_flag_agrees_with_config():
    """Docs may show the flag. If they do, the value has to be right."""
    expected = configured_threshold()

    for relative_path in (README, CONTRIBUTING):
        for match in COV_FAIL_UNDER.finditer(_read(relative_path)):
            value = int(match.group(1))
            if value == 0:
                continue
            assert value == expected, (
                f"{relative_path}: documents --cov-fail-under={value}, but "
                f"pyproject.toml fail_under is {expected}. Anyone pasting that "
                "command runs a different gate than CI does."
            )
