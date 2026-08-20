"""A stable identifier for the algorithm that produced a recommendation.

REGULATORY_FRAMEWORK.md section 2.3 requires a locked algorithm version with a
change-control procedure before this system can be submitted under a De Novo or
CE IVD-R pathway. A regulator's question is not "what does this system
recommend"; it is "what exactly produced this recommendation, and can you show
it has not silently changed since".

The repository can already answer where the evidence came from
(results.evidence_provenance, migration 0013) and whether a variant's lookup
succeeded (mutations.evidence_lookup_status, migration 0014). Neither says which
scoring behaviour ran. Two recommendations built from identical evidence can
differ because a weight moved, and nothing recorded that.

WHAT GOES INTO THE FINGERPRINT
------------------------------
Everything that can change the ordering of drugs for fixed inputs:

  * every evidence weight and the ranking configuration around it
  * the candidate-pool policy, which decides what is eligible to be ranked
  * whether the CIViC supplement is merged into the evidence table
  * the degraded-evidence policy, which decides whether output is withheld

WHAT DOES NOT
-------------
The evidence table's contents. Its identity belongs to
`results.evidence_provenance`, which already records the path and snapshot date,
and folding it in here would make the algorithm version change every time an
OncoKB dump refreshed. Those are different questions: which rules ran, and which
evidence they ran against. A regulator asks both, and answering them in one
field answers neither.

Nor the code. A hash over source would change on a comment, so a semantic
version is declared in `ALGORITHM_VERSION` and moved by hand when behaviour
changes. That is the change-control part, and it is deliberately manual.

WHAT THIS DOES NOT DO
---------------------
It does not stop the algorithm changing, and it is not a lock in the regulatory
sense on its own. It makes a change visible: a stored result carries the
fingerprint of the rules that produced it, and a test fails when the fingerprint
moves without the declared version moving with it. Locking is a procedure that
this makes checkable, not a thing code can do by itself.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

# Moved by hand when ranking behaviour changes in a way a reader would notice.
# The fingerprint below moves on its own; when the two disagree, a test fails
# and someone has to say which of the two is wrong.
ALGORITHM_VERSION = "1.0.0"


def _plain(value: Any) -> Any:
    """Reduce a config object to something with a stable JSON form.

    Sets are sorted rather than stringified. The ranking config holds six of
    them, in `resistance.levels` and `co_mutation.pathway_groups`, and Python
    randomises set iteration order per process, so falling through to `str()`
    produced a different fingerprint on every run. A version identifier that
    changes when nothing changed is worse than none: it would make the
    change-control check fail constantly and train everyone to update the
    expected value without looking.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in sorted(asdict(value).items())}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _ranking_inputs() -> dict[str, Any]:
    try:
        from ai.ranking_config import DEFAULT_CONFIG

        return _plain(DEFAULT_CONFIG)
    except Exception as exc:  # pragma: no cover - import guard
        # A fingerprint that silently omits the ranking config would claim more
        # stability than it has, so the failure is recorded inside it instead.
        return {"unavailable": str(exc)}


def _policy_inputs() -> dict[str, Any]:
    try:
        from config import settings
    except Exception as exc:  # pragma: no cover - import guard
        return {"unavailable": str(exc)}
    return {
        "candidate_pool_policy": getattr(settings, "candidate_pool_policy", None),
        "civic_supplement_enabled": bool(
            getattr(settings, "civic_supplement_enabled", False)
        ),
        "require_current_evidence": bool(
            getattr(settings, "require_current_evidence", False)
        ),
        "degraded_evidence_alert_after": getattr(
            settings, "degraded_evidence_alert_after", None
        ),
    }


def algorithm_fingerprint() -> str:
    """Short hash over everything that can reorder drugs for fixed inputs."""
    payload = {
        "declared_version": ALGORITHM_VERSION,
        "ranking": _ranking_inputs(),
        "policy": _policy_inputs(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def get_algorithm_version() -> dict[str, Any]:
    """The block stamped onto a result at the moment it is produced.

    Stamped rather than computed at read time, for the same reason evidence
    provenance is: settings can change between producing a recommendation and
    reading it, and the question a reader has is which rules produced *this*
    one.
    """
    return {
        "version": ALGORITHM_VERSION,
        "fingerprint": algorithm_fingerprint(),
        "components": {
            "ranking": _ranking_inputs(),
            "policy": _policy_inputs(),
        },
        "note": (
            "Identifies the scoring rules, not the evidence they ran against. "
            "See evidence_provenance for the evidence snapshot."
        ),
    }


def describe_for_report() -> str:
    """One line an oncologist report can carry without explaining hashing."""
    return f"Algorithm {ALGORITHM_VERSION} (build {algorithm_fingerprint()})"
