"""
A compliance control marked as implemented must cite something that exists.

BACKLOG.md OO-14. `docs/HIPAA_COMPLIANCE.md` is the artefact a compliance
reviewer would be handed, and it carried a satisfied mark against controls that
were never implemented. The contingency-plan row cited WAL archiving and MinIO
versioning, neither configured anywhere, and pointed at Keycloak's database
rather than the application's. The data-at-rest row cited PostgreSQL checksums,
which are off. The security-officer row cited a CODEOWNERS file that does not
exist.

Each of those read as verified for exactly as long as nobody checked, which is
the same shape as F11, F14 and F18 in the risk analysis: every assertion in the
suite was a positive about something present, and these were absences.

This module makes the citation carry weight. A row claiming implementation must
either cite a repository path that exists and a mechanism that is actually
present, or be named in EXEMPT with the reason it cannot be checked
mechanically. The exemption list is the same device
`test_marketplace_phi_disclosure.py` uses for anonymous routes: the unverifiable
set stays visible rather than implied.

What this does not do is assess HIPAA compliance, which is a legal question. It
checks that the document describes this repository accurately.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "docs" / "HIPAA_COMPLIANCE.md"
DOC_TEXT = DOC.read_text(encoding="utf-8")

IMPLEMENTED = "✅"
NOT_IMPLEMENTED = "⬜"

# Controls whose implementation is real but lives outside this repository, so no
# search here can confirm it. Each needs a reason, and the reason has to be about
# where the evidence lives rather than about it being inconvenient to check.
EXEMPT = {
    "Facility access controls":
        "A property of the hosting provider. No artefact in this repository can "
        "evidence it.",
    "Encryption + decryption":
        "TLS termination and disk encryption are provided by the ingress "
        "controller and the cloud provider. The chart requests TLS; the cipher "
        "suite and the disk are not configured here.",
    "Encryption in transit":
        "Same as above. The ssl-redirect annotation is asserted below; the "
        "negotiated TLS version is not something this repository decides.",
    "Access management policy":
        "Realm roles are defined in Keycloak, not here. The enforcement of the "
        "oncologist role is asserted below, but the policy itself is external.",
}

# Tokens that are worth grepping for, mapped to where they must appear. A row
# citing one of these is claiming a specific mechanism, so the mechanism has to
# be findable.
MECHANISMS = {
    "HSTS": (["infra/helm/values.production.yaml"], "Strict-Transport-Security"),
    "ssl-redirect": (["infra/helm/values.production.yaml"], "ssl-redirect"),
    "AuditMiddleware": (["api/middleware/audit.py"], "class AuditMiddleware"),
    "GET /api/me/export": (["api/routes/gdpr.py"], '"/export"'),
    "DELETE /api/me": (["api/routes/gdpr.py"], "erase_patient_data"),
    "oncologist": (["api/routes/oncologist.py"], "oncologist"),
}


def _rows() -> list[tuple[str, str, str]]:
    """(control, status, implementation) for every status row in the document."""
    found = []
    pattern = re.compile(
        rf"^\|\s*(?P<control>[^|]+?)\s*\|\s*(?P<status>{IMPLEMENTED}|{NOT_IMPLEMENTED})\s*\|"
        r"\s*(?P<impl>.*?)\s*\|\s*$",
        re.M,
    )
    for m in pattern.finditer(DOC_TEXT):
        found.append((m.group("control"), m.group("status"), m.group("impl")))
    return found


def _claimed() -> list[tuple[str, str]]:
    return [(c, impl) for c, status, impl in _rows() if status == IMPLEMENTED]


# Repository artefacts that get referred to by bare name rather than in
# backticks. CODEOWNERS is here because the security-officer row cited it in
# plain prose, which is how a citation of a file that does not exist survived a
# check that only read backticks.
_BARE_ARTEFACTS = ("CODEOWNERS", "LICENSE", "CONTRIBUTING.md", "SECURITY.md")


def _cited_paths(impl: str) -> list[str]:
    """Repository paths an Implementation cell names, backticked or not."""
    paths = []
    for token in re.findall(r"`([^`]+)`", impl):
        token = token.strip()
        if "/" in token and not token.startswith(("http", "GET ", "POST ", "DELETE ")):
            paths.append(token.split()[0].rstrip(".,;"))
    words = {w.strip('`.,;()').upper() for w in impl.split()}
    for artefact in _BARE_ARTEFACTS:
        if artefact.upper() in words:
            paths.append(artefact)
    return paths


def _exists(rel: str) -> bool:
    """CODEOWNERS is valid at the root, in .github/ or in docs/."""
    if rel in _BARE_ARTEFACTS:
        return any(
            (REPO_ROOT / prefix / rel).exists() for prefix in ("", ".github", "docs")
        )
    return (REPO_ROOT / rel).exists()


# ── The document still has the shape these tests assume ──────────────────────

def test_the_document_parses_into_rows():
    """A guard over an empty set proves nothing."""
    rows = _rows()
    assert len(rows) >= 25, f"only {len(rows)} status rows parsed; the table format changed"
    assert _claimed(), "no rows claim implementation, which cannot be right"


# ── Every cited path exists ──────────────────────────────────────────────────

@pytest.mark.parametrize("control,impl", _claimed(), ids=lambda v: v[:40] if isinstance(v, str) else v)
def test_cited_paths_exist(control, impl):
    """
    The security-officer row cited CODEOWNERS, which does not exist. The
    contingency-plan row cited infra/helm/postgres.yaml, which exists but is a
    different database; a path check cannot catch that second kind of error, and
    the mechanism checks below are what covers it.
    """
    missing = [p for p in _cited_paths(impl) if not _exists(p)]
    assert not missing, (
        f"control {control!r} is marked implemented and cites paths that do not "
        f"exist: {missing}"
    )


# ── Every cited mechanism is actually present ────────────────────────────────

@pytest.mark.parametrize("token,spec", sorted(MECHANISMS.items()))
def test_cited_mechanisms_are_present(token, spec):
    files, needle = spec
    if not any(token.lower() in impl.lower() for _, impl in _claimed()):
        pytest.skip(f"no implemented row cites {token!r}")
    hits = []
    for rel in files:
        path = REPO_ROOT / rel
        if path.exists() and needle.lower() in path.read_text(encoding="utf-8").lower():
            hits.append(rel)
    assert hits, (
        f"a control claims {token!r} but {needle!r} appears in none of {files}"
    )


# ── Claims that name a backup or an integrity mechanism ──────────────────────

def _search(patterns: list[str], roots: list[str]) -> list[str]:
    hits = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        for f in files:
            if f.suffix.lower() not in {".yaml", ".yml", ".py", ".sh", ".tpl", ".toml", ".cfg"}:
                continue
            # This module names every pattern it searches for, so without this
            # it finds itself and reports the mechanism as present. A check that
            # passes by reading its own source is the same pathology it exists
            # to catch, one level up.
            if "tests" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for pat in patterns:
                if pat.lower() in text:
                    hits.append(f"{f.relative_to(REPO_ROOT)}:{pat}")
    return hits


def test_a_backup_claim_requires_a_backup_mechanism():
    """
    The row that started this. It claimed WAL archiving and MinIO versioning and
    neither exists, so the claim survived only because nothing looked.
    """
    backup_rows = [
        (c, impl) for c, impl in _claimed()
        if "backup" in c.lower() or "contingency" in c.lower()
    ]
    if not backup_rows:
        pytest.skip("no control currently claims a backup")

    evidence = _search(
        ["archive_mode", "archive_command", "wal_level", "pg_dump", "pgbackrest",
         "wal-g", "velero", "versioning"],
        ["infra", "api", "docker-compose.yml", "Makefile"],
    )
    assert evidence, (
        f"{[c for c, _ in backup_rows]} claims a contingency plan, and no backup "
        "mechanism is configured anywhere in infra/, api/, docker-compose.yml or "
        "the Makefile"
    )


def test_a_checksum_claim_requires_checksums_to_be_enabled():
    checksum_rows = [
        (c, impl) for c, impl in _claimed() if "checksum" in impl.lower()
    ]
    if not checksum_rows:
        pytest.skip("no implemented control currently claims PostgreSQL checksums")

    evidence = _search(["data_checksums", "data-checksums"], ["infra", "docker-compose.yml"])
    assert evidence, (
        f"{[c for c, _ in checksum_rows]} claims PostgreSQL checksums, and "
        "data_checksums is set nowhere. PostgreSQL 16 defaults it off."
    )


def test_a_session_timeout_claim_requires_the_timeout_to_be_configured():
    """
    Relying on an upstream default is not the same as configuring it, and the
    document quoted specific numbers. If nothing here sets them, the row is
    describing Keycloak's defaults rather than this deployment.
    """
    rows = [
        (c, impl) for c, impl in _claimed()
        if "log-off" in c.lower() or "session timeout" in impl.lower()
    ]
    if not rows:
        pytest.skip("no implemented control currently claims a session timeout")

    evidence = _search(
        ["ssosessionidletimeout", "ssosessionmaxlifespan", "sso_session_idle",
         "sso_session_max"],
        ["infra", "docker-compose.yml"],
    )
    assert evidence, (
        f"{[c for c, _ in rows]} quotes specific session timeouts and no realm "
        "setting configures them anywhere"
    )


# ── The exemption list stays honest ──────────────────────────────────────────

def test_every_exemption_still_corresponds_to_a_claimed_control():
    """An exemption for a row that no longer claims implementation is dead weight
    that makes the list look more considered than it is."""
    claimed = {c for c, _ in _claimed()}
    stale = sorted(set(EXEMPT) - claimed)
    assert not stale, f"EXEMPT names controls that no longer claim implementation: {stale}"


def test_exemptions_carry_a_reason():
    for control, reason in EXEMPT.items():
        assert len(reason.strip()) > 40, f"exemption for {control!r} needs a real reason"
