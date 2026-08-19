"""The `ai` package must hold both halves at once.

risk_analysis.md F15. `api/ai/` holds ranking.py; repo-root `ai/` holds
diffdock/, alphamissense/ and services/. Both carried an empty `__init__.py`,
which made each a regular package, and a regular package terminates the import
scan. Whichever directory came first on sys.path shadowed the other entirely,
so `ai` could never contain both halves in one process.

`_query_repurposing_candidates` imported `ai.diffdock.score` unguarded, so with
`api/` first the whole repurposing tier raised ModuleNotFoundError before doing
any work. The deployed container never hit it: api/Dockerfile merges both
directories into one /app/ai on disk. Nothing outside the container reproduced
that arrangement, so the tier was dead locally and the failure looked like a
capability with nothing to say rather than one that was not running.

Two properties are pinned here.

  1. Every `ai.*` module the worker imports resolves in a single process. If
     someone reintroduces an `__init__.py` in either directory, this fails.
  2. The repurposing path survives DiffDock being absent, because a docking
     score is an enrichment on a candidate rather than the reason the candidate
     exists.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _API_DIR.parent
for _p in (str(_API_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Every ai.* module imported anywhere in api/workers or api/services.
_REQUIRED = [
    "ai.ranking",
    "ai.diffdock.score",
    "ai.alphamissense.classify",
    "ai.services.alphafold",
]


class TestBothHalvesResolve:
    @pytest.mark.parametrize("module", _REQUIRED)
    def test_module_imports(self, module):
        assert importlib.import_module(module) is not None

    def test_all_of_them_in_one_process(self):
        """The property that actually broke: one at a time was never the problem."""
        for module in _REQUIRED:
            importlib.import_module(module)

    def test_ai_is_a_namespace_package_spanning_both_directories(self):
        import ai

        portions = {Path(p).resolve() for p in getattr(ai, "__path__", [])}
        assert (_API_DIR / "ai").resolve() in portions, (
            "api/ai is not part of the ai namespace package; a regular "
            "__init__.py has probably been reintroduced"
        )
        assert (_REPO_ROOT / "ai").resolve() in portions, (
            "repo-root ai is not part of the ai namespace package"
        )

    def test_neither_directory_has_an_init_file(self):
        """An __init__.py in either place re-shadows the other half."""
        for candidate in (_API_DIR / "ai" / "__init__.py", _REPO_ROOT / "ai" / "__init__.py"):
            assert not candidate.exists(), (
                f"{candidate} makes ai a regular package again and hides the "
                "other directory; see risk_analysis.md F15"
            )


class TestRepurposingSurvivesMissingDiffdock:
    def test_import_is_guarded(self):
        """Absent DiffDock must degrade a candidate, never delete the tier."""
        source = (_API_DIR / "workers" / "ai_worker.py").read_text(encoding="utf-8")
        start = source.index("def _query_repurposing_candidates")
        body = source[start : start + 4000]
        assert "from ai.diffdock.score import score_binding" in body
        guarded = body.index("from ai.diffdock.score import score_binding")
        preceding = body[:guarded]
        assert preceding.rstrip().endswith("try:"), (
            "the DiffDock import must sit under try/except ModuleNotFoundError, "
            "matching services/drug_discovery.py"
        )

    def test_score_binding_call_is_null_checked(self):
        source = (_API_DIR / "workers" / "ai_worker.py").read_text(encoding="utf-8")
        assert "score_binding is not None" in source, (
            "score_binding may be None when DiffDock is unavailable; the call "
            "site has to check before invoking it"
        )
