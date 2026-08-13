"""Every Celery task should have something that dispatches it.

This is F10's lesson stated generally. `sample_qc` was implemented, unit-tested
and benchmarked, and no code path called it, so the control was inert while
looking finished. `notify_worker.py` is in the same state: five tasks, each with
templates and retry policy, and three of them have no caller anywhere in the
repository.

The test works on source text rather than by importing the worker. Dispatch is
what is being checked, and dispatch is a static property of the code: importing
Celery tasks needs a broker and tells us nothing about whether anyone calls them.

`_KNOWN_UNWIRED` is deliberately an explicit list rather than a skip. Adding to
it is a visible, reviewable act with a reason attached, in the same spirit as
api/.pip-audit-ignore. A newly added task that nobody dispatches fails here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_API_DIR = _REPO_ROOT / "api"
_NOTIFY_WORKER = _API_DIR / "workers" / "notify_worker.py"

# Tasks with no dispatcher today. Each entry is a defect, not an exemption:
# the feature it belongs to does not happen. Kept here so the gap is recorded
# in code rather than only in a report, and so the list can only shrink under
# review.
#
#   notify_order_confirmed   Stripe confirms an order and the buyer is not told.
#                            webhook.py:_handle_succeeded is where it belongs.
#   notify_pharma_approved   pharma_admin.py verifies a company and sends nothing.
#   notify_review_complete   oncologist.py accepts a review and the patient is
#                            never notified. Its Result lookup was also broken
#                            (db.get by primary key against a non-PK column);
#                            that is fixed, so wiring it up now works.
#
# Wiring these changes which emails real users receive, so it is a product
# decision rather than a cleanup, and is tracked separately.
_KNOWN_UNWIRED = {
    "notify_order_confirmed",
    "notify_pharma_approved",
    "notify_review_complete",
}

_TASK_DEF = re.compile(r"^def (notify_\w+)\(", re.M)
_DISPATCH = re.compile(r"\b(\w+)\.(?:apply_async|delay)\s*\(")


def _task_names() -> set[str]:
    return set(_TASK_DEF.findall(_NOTIFY_WORKER.read_text(encoding="utf-8")))


def _dispatched_names() -> set[str]:
    """Task names dispatched anywhere in api/, excluding the worker and tests."""
    dispatched: set[str] = set()
    for path in _API_DIR.rglob("*.py"):
        if path == _NOTIFY_WORKER or "tests" in path.parts or "__pycache__" in path.parts:
            continue
        dispatched.update(_DISPATCH.findall(path.read_text(encoding="utf-8")))
    return dispatched


class TestTaskWiring:
    def test_the_scan_finds_the_tasks(self):
        """Guard the guard: an empty scan would make every assertion vacuous."""
        names = _task_names()
        assert len(names) >= 5, f"expected the notify tasks, found {names}"

    def test_the_scan_finds_at_least_one_dispatcher(self):
        assert "notify_results_ready" in _dispatched_names(), (
            "the dispatch scan found nothing it should have; the regex is wrong"
        )

    def test_no_undocumented_task_lacks_a_dispatcher(self):
        undocumented = sorted(_task_names() - _dispatched_names() - _KNOWN_UNWIRED)
        assert not undocumented, (
            f"these Celery tasks are defined and never dispatched: {undocumented}. "
            "Wire them up, delete them, or add them to _KNOWN_UNWIRED with a reason."
        )

    def test_the_unwired_list_is_accurate(self):
        """Stop the list outliving the problem: a wired task must leave it."""
        wired_but_listed = sorted(_KNOWN_UNWIRED & _dispatched_names())
        assert not wired_but_listed, (
            f"these are dispatched now and should be removed from "
            f"_KNOWN_UNWIRED: {wired_but_listed}"
        )


class TestMilestoneDispatcherIsReachable:
    """A dispatcher that nothing calls is the same defect one level up.

    notify_campaign_milestone does have a dispatcher, so the wiring test above
    passes it. But that dispatcher, campaign._check_milestone, is itself never
    called, and webhook._handle_succeeded increments raised_usd without going
    near it. Milestone emails therefore cannot fire.
    """

    def _milestone_call_count(self) -> int:
        sources = "".join(
            (_API_DIR / "routes" / name).read_text(encoding="utf-8")
            for name in ("campaign.py", "webhook.py")
        )
        assert "def _check_milestone(" in sources, "_check_milestone moved; update this test"
        return len(re.findall(r"(?<!def )_check_milestone\s*\(", sources))

    @pytest.mark.xfail(
        reason=(
            "known gap: nothing calls _check_milestone, so notify_campaign_milestone "
            "is unreachable. webhook.py:_handle_succeeded is where raised_usd is "
            "incremented and where the call belongs. Wiring it changes which emails "
            "users receive, so it is a product decision tracked separately."
        ),
        strict=True,
    )
    def test_check_milestone_is_called_somewhere(self):
        assert self._milestone_call_count() > 0
