"""A crashed report section must not read as an empty one.

`get_results` builds the patient summary and the oncologist report inside
try/except blocks that used to end in a bare `pass`. Any exception in either
generator produced a 200 response with `patient_summary: null` or
`oncologist_report: null`, and nothing anywhere said a failure had happened: no
log line, no field, no status change.

That is hazard H3 from docs/risk_analysis.md, "a lookup failure is presented as
a negative result", reaching the response a clinician reads. The generators are
still not allowed to fail the request, which is the right call, so the fix is to
name the failure in the payload instead of swallowing it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _boom(*_args, **_kwargs):
    raise RuntimeError("generator exploded")


class TestPatientSummaryFailure:
    async def test_a_crash_is_named_in_the_response(
        self, client, seeded_submission, monkeypatch
    ):
        monkeypatch.setattr(
            "services.patient_summary.generate_patient_summary", _boom
        )
        response = await client.get(f"/api/results/{seeded_submission.id}")

        assert response.status_code == 200, "generation must not fail the request"
        body = response.json()
        assert "patient_summary" in body["generation_errors"]

    async def test_the_normal_path_reports_no_errors(self, client, seeded_submission):
        response = await client.get(f"/api/results/{seeded_submission.id}")
        assert response.status_code == 200
        assert response.json()["generation_errors"] == []


class TestOncologistReportFailure:
    async def test_a_crash_is_named_in_the_response(
        self, client, seeded_submission, monkeypatch
    ):
        monkeypatch.setattr(
            "services.oncologist_report.generate_oncologist_report", _boom
        )
        response = await client.get(
            f"/api/results/{seeded_submission.id}?include_oncologist_report=true"
        )

        assert response.status_code == 200
        body = response.json()
        assert "oncologist_report" in body["generation_errors"]
        assert body["oncologist_report"] is None

    async def test_a_null_report_is_distinguishable_from_a_failed_one(
        self, client, seeded_submission, monkeypatch
    ):
        """The property that matters: the two cases must not look identical.

        Not requesting the report and requesting one that crashes both leave
        `oncologist_report: null`. Only generation_errors separates them.
        """
        not_requested = (
            await client.get(f"/api/results/{seeded_submission.id}")
        ).json()

        monkeypatch.setattr(
            "services.oncologist_report.generate_oncologist_report", _boom
        )
        crashed = (
            await client.get(
                f"/api/results/{seeded_submission.id}?include_oncologist_report=true"
            )
        ).json()

        assert not_requested["oncologist_report"] is None
        assert crashed["oncologist_report"] is None
        assert not_requested["generation_errors"] != crashed["generation_errors"]


class TestFailureIsLogged:
    async def test_the_exception_reaches_the_log(
        self, client, seeded_submission, monkeypatch, caplog
    ):
        """A bare `pass` left no trace at all; an operator needs the traceback."""
        monkeypatch.setattr(
            "services.patient_summary.generate_patient_summary", _boom
        )
        with caplog.at_level("ERROR", logger="routes.results"):
            await client.get(f"/api/results/{seeded_submission.id}")

        assert any("patient summary generation failed" in r.message for r in caplog.records)
