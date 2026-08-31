"""
The oncologist report path, exercised the way the application runs it.

Three defects, all found by starting the API and requesting the report rather
than by any assertion. Each had been present for as long as the code existed and
each passed the suite.

  1. `oncologist_report.py` imported `from api.ai.ranking import ...` with no
     fallback. Backend modules import as if `api/` were the root, which is how
     uvicorn runs them; the `api.` prefix resolves only when the repository root
     is also on `sys.path`, which is true in the test harness and false in
     production. The report raised ModuleNotFoundError, and the route reported it
     in `generation_errors` correctly, to nobody.

  2. `_weasyprint_available()` caught `ImportError` alone. WeasyPrint is a Python
     package with native dependencies, and the ordinary failure is the package
     importing while libgobject is absent, which raises `OSError`. The HTML
     fallback the function exists to select never ran and the download returned
     500. `api/Dockerfile` installs none of the GTK stack, so the deployed image
     takes this path too.

  3. The oncologist report footed itself "For Physician Review Only", which says
     who should read it rather than what it is. It is the artefact most likely to
     be printed and filed, and it carried the weaker claim while the patient
     letter carried the stronger one. See F18.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def report():
    from services.oncologist_report import generate_oncologist_report

    return generate_oncologist_report(
        ranked_candidates=[],
        mutation_summary=[{
            "gene": "KRAS", "hgvs": "p.G12D",
            "classification": "likely_pathogenic", "oncokb_level": "4",
        }],
        cancer_type="Lung adenocarcinoma",
        qc_report=None,
        patient_id="test-patient",
    )


# ── 1. Imports resolve in the layout the app actually runs in ────────────────

def test_no_import_on_the_report_path_assumes_the_repo_root():
    """
    An unguarded `from api.x import y` works under pytest and fails under
    uvicorn, so the suite cannot see it by importing. This reads the source, the
    way `test_pipeline_config.py` does, because the property is about the source
    rather than about what happens to be importable here.
    """
    source = (REPO_ROOT / "api" / "services" / "oncologist_report.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(("from api.", "import api.")):
            window = "\n".join(lines[max(0, i - 4):i + 1])
            assert "except ModuleNotFoundError" in window or "try:" in window, (
                f"oncologist_report.py:{i + 1} imports {line.strip()!r} with no "
                "fallback. That resolves under pytest and not under uvicorn."
            )


def test_the_report_generates(report):
    """It raised ModuleNotFoundError before, and the route swallowed it."""
    assert report.sections
    assert "executive_summary" in report.sections


# ── 2. The download degrades instead of failing ──────────────────────────────

def test_the_weasyprint_probe_treats_a_missing_library_as_unavailable(monkeypatch):
    """
    A missing shared library must be handled like a missing package. Catching
    ImportError alone let OSError escape the probe, and since the probe is called
    outside the render's try block the request became a 500 rather than HTML.
    """
    import builtins

    from services.pdf_export import _weasyprint_available

    real_import = builtins.__import__

    def _raise_oserror(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real_import(name, *args, **kwargs)

    # Addressed by dotted path rather than by importing the module object, so
    # this file uses one import style throughout. Importing the same module both
    # as `import x` and `from x import y` is what CodeQL flags, and the cached
    # flag has to be cleared on the module itself for the probe to re-run.
    monkeypatch.setattr("services.pdf_export._WEASYPRINT_AVAILABLE", None)
    monkeypatch.setattr(builtins, "__import__", _raise_oserror)

    assert _weasyprint_available() is False, (
        "a missing native library still escapes the probe"
    )


def test_the_download_returns_something_either_way(report):
    """
    PDF when WeasyPrint works, HTML when it does not, and a correct content type
    for whichever happened. Never an exception.
    """
    from services.pdf_export import generate_oncologist_report_document

    body, content_type, extension = generate_oncologist_report_document(report)
    assert body
    if extension == ".pdf":
        assert body[:5] == b"%PDF-"
        assert content_type == "application/pdf"
    else:
        assert extension == ".html"
        assert content_type.startswith("text/html")


# ── 3. The printable report says what it is ──────────────────────────────────

def test_the_oncologist_report_carries_the_research_use_statement(report):
    """
    Unconditionally. The statement used to appear only inside the experimental
    candidates section, which renders only when de-novo candidates exist, so an
    ordinary report carried none.
    """
    from services.intended_use import RESEARCH_USE_STATEMENT
    from services.pdf_export import _build_oncologist_html

    # Asserted on the HTML the template produces, not on the rendered bytes.
    # Where WeasyPrint's native libraries are present, as on the CI runner, the
    # document comes back as compressed PDF and searching it for text finds
    # nothing. The claim is about the template's content either way.
    text = _build_oncologist_html(report)
    assert "RESEARCH USE ONLY" in text.upper(), (
        "the printable clinician report does not say it is research output"
    )
    assert RESEARCH_USE_STATEMENT.split(".")[0] in text, (
        "the report states it in its own words rather than from intended_use.py"
    )


def test_the_statement_comes_from_the_single_source():
    """Two copies drift, and the point of intended_use.py is that they cannot."""
    source = (REPO_ROOT / "api" / "services" / "pdf_export.py").read_text(encoding="utf-8")
    assert "RESEARCH_USE_STATEMENT" in source


def test_the_patient_letter_still_carries_its_own_disclaimer():
    """
    Tuned to a sixth-to-eighth grade reading level and deliberately different
    from the clinician wording. Adding the clinician statement must not have
    replaced it.
    """
    from services.patient_summary import DISCLAIMER

    assert "NOT medical advice" in DISCLAIMER


# ── 4. The module can be imported on the Python the image runs ───────────────
#
# `api/Dockerfile` is `FROM python:3.11-slim` and CI pins 3.11. A triple-quoted
# f-string nested inside another f-string is legal on 3.12, which is what a
# developer machine may have, and a SyntaxError on 3.11.
#
# pdf_export.py had nine of them, so it could not be imported in production at
# all. Nothing in the suite imported the module and `results.py` imports it
# lazily inside the handler, so the app started normally and only the two
# download endpoints raised. Both had been broken for as long as the file
# existed.

# Only the same-quote family breaks on 3.11. The outer templates are delimited
# with triple double quotes, so a nested f-string using double quotes collides
# with them; one using single quotes does not, and several of those are
# pre-existing and fine. Flagging them too would make this guard something
# people disable.
_PY311_HOSTILE = ('{f"""', '{f"')


def test_no_nested_f_strings_in_the_report_templates():
    """
    Detected by pattern rather than by compiling, because the interpreter
    running these tests may be the one that accepts them. Checking on 3.12 that
    3.12 accepts it proves nothing about the image.
    """
    for name in ("pdf_export.py", "oncologist_report.py", "patient_summary.py"):
        source = (REPO_ROOT / "api" / "services" / name).read_text(encoding="utf-8")
        offenders = [
            (i + 1, line.strip())
            for i, line in enumerate(source.splitlines())
            if any(tok in line for tok in _PY311_HOSTILE)
        ]
        assert not offenders, (
            f"{name} nests an f-string inside an f-string, which is a SyntaxError "
            f"on the Python 3.11 the Dockerfile runs: {offenders[:3]}"
        )


def test_the_dockerfile_python_matches_what_ci_tests():
    """
    The guard above is calibrated to 3.11. If the image moves and CI does not,
    or the reverse, this is checking the wrong thing.
    """
    dockerfile = (REPO_ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python:3.11" in dockerfile, "the image no longer runs 3.11"
    assert 'python-version: "3.11"' in workflow, "CI no longer tests on 3.11"


def test_both_documents_render(report):
    """The hoisting must not have changed what the templates produce."""
    from services.pdf_export import _build_oncologist_html, _build_patient_html

    onc = _build_oncologist_html(report)
    assert "<h2>" in onc
    assert "Section 2" in onc

    from services.patient_summary import generate_patient_summary

    letter = _build_patient_html(generate_patient_summary(
        ranked_candidates=[],
        mutation_summary=[{"gene": "KRAS", "hgvs": "p.G12D"}],
        cancer_type="Lung adenocarcinoma",
        gene="KRAS",
    ).sections)
    assert "<h1>" in letter
