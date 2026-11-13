"""
Drift guard for the root `.env.example`.

The file is the contributor's only map of what can be configured, and the README
Quick Start tells them to copy it. Nothing tied it to `api/config.py`, so it had
quietly fallen behind: a dozen Settings fields (DATABASE_URL, REDIS_URL, the
Keycloak client, CANDIDATE_POOL_POLICY, ...) were undocumented, and the S3/AWS
block described variables nothing reads.

A variable counts as documented whether it is set (`NAME=value`) or shown as an
optional override (`# NAME=value`).
"""
import re
from pathlib import Path

from config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

_ASSIGNMENT = re.compile(r"^(?:#\s*)?([A-Z][A-Z0-9_]*)=", re.MULTILINE)

# Variables that are not Settings fields but are read elsewhere: docker-compose.yml
# interpolation, the ai/ package, services reading os.environ directly, and the
# Next.js frontend.
_NON_SETTINGS = {
    "DB_PASSWORD",
    "GRAFANA_PASSWORD",
    "FLOWER_USER",
    "FLOWER_PASSWORD",
    "ALPHAFOLD_API_KEY",
    "ALPHAFOLD_STRUCTURE_BUCKET",
    "DIFFDOCK_DIR",
    "DIFFDOCK_PYTHON",
    "ONCOKB_PUBLIC_DUMP_TOKEN",
    "SIGPROFILER_ENABLED",
    "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY",
}


def _documented() -> set[str]:
    return set(_ASSIGNMENT.findall(ENV_EXAMPLE.read_text(encoding="utf-8")))


def test_every_settings_field_is_documented():
    expected = {name.upper() for name in Settings.model_fields}
    missing = sorted(expected - _documented())
    assert not missing, f".env.example does not document: {', '.join(missing)}"


def test_no_variable_is_documented_that_nothing_reads():
    known = {name.upper() for name in Settings.model_fields} | _NON_SETTINGS
    unknown = sorted(_documented() - known)
    assert not unknown, (
        f".env.example lists variables that are not Settings fields or known "
        f"direct readers: {', '.join(unknown)}"
    )
