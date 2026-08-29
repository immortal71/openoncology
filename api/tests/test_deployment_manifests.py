"""
Drift guards for the deployment manifests.

Two classes of defect motivated this module, and neither was visible to any
check that existed. Both have the shape the risk analysis keeps finding: every
assertion in CI was a positive about something present, and these were absences.

  * `task_routes` sent `workers.gdpr_worker.*` to a `gdpr` queue that no
    deployment consumed. `DELETE /api/me` enqueued an erasure task, returned a
    confirmation promising deletion within 30 days, and the message stayed in
    Redis. Every producer saw success.
  * The chart had no Celery Beat, so `gdpr-enforce-retention-daily` and
    `sweep-stale-submissions-hourly` had never fired in Kubernetes.

The third guard is a divergence rather than an absence: the readiness probe in
the Helm chart pointed at `/health`, which answers 200 unconditionally, while
`infra/k8s/deployment.yaml` correctly used `/ready`, which round-trips Postgres
and Redis. Two manifests for the same service, and nothing compared them.

These parse the manifests as text and data rather than rendering them. The
`infra-manifests` job in ci.yml does the real render with helm and kubeconform;
this module is what fails locally, offline, and in the suite everyone runs.
"""
import ast
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HELM = REPO_ROOT / "infra" / "helm"
K8S = REPO_ROOT / "infra" / "k8s"
COMPOSE = REPO_ROOT / "docker-compose.yml"
CELERY_APP = REPO_ROOT / "api" / "workers" / "__init__.py"


def _conf_update_kwargs() -> dict[str, ast.expr]:
    """
    The keyword arguments of the `celery_app.conf.update(...)` call, unevaluated.

    Read from source rather than by importing the app. `test_ai_worker_helpers`
    and `test_genomic_worker_qc_persistence` both install a MagicMock over
    `sys.modules["workers"].celery_app` to keep task decorators inert, so in a
    full-suite run `from workers import celery_app` hands back a mock whose
    `conf.task_routes` is empty. Reading the declaration is also the more honest
    thing for a drift guard to do: what ships is the source, not whatever the
    interpreter was left holding.
    """
    tree = ast.parse(CELERY_APP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "update"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "conf"
        ):
            return {kw.arg: kw.value for kw in node.keywords if kw.arg}
    raise AssertionError("no celery_app.conf.update(...) call found")


@pytest.fixture(scope="module")
def task_routes() -> dict[str, dict]:
    return ast.literal_eval(_conf_update_kwargs()["task_routes"])


@pytest.fixture(scope="module")
def scheduled_tasks() -> dict[str, str]:
    """Beat entry name → dotted task path. `schedule` holds `crontab(...)`
    calls, which are not literals, so only the task path is extracted."""
    schedule = _conf_update_kwargs()["beat_schedule"]
    entries = {}
    for name_node, entry in zip(schedule.keys, schedule.values):
        name = ast.literal_eval(name_node)
        for key, value in zip(entry.keys, entry.values):
            if ast.literal_eval(key) == "task":
                entries[name] = ast.literal_eval(value)
    return entries


@pytest.fixture(scope="module")
def routed_queues(task_routes) -> set[str]:
    return {route["queue"] for route in task_routes.values()}


@pytest.fixture(scope="module")
def helm_values() -> dict:
    return yaml.safe_load((HELM / "values.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _compose_consumed_queues(compose: dict) -> set[str]:
    queues = set()
    for service in compose["services"].values():
        command = service.get("command")
        if not command:
            continue
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        for match in re.finditer(r"-Q\s+([A-Za-z0-9_,-]+)", command):
            queues.update(match.group(1).split(","))
    return queues


# ── Every routed queue has a consumer ────────────────────────────────────────

def test_helm_defines_a_worker_for_every_routed_queue(routed_queues, helm_values):
    """
    workers.yaml renders one Deployment per key under `workers`, consuming
    `-Q <key>`. A routed queue with no key has no consumer in the cluster.
    """
    declared = set(helm_values["workers"])
    assert routed_queues <= declared, (
        f"queues routed by task_routes with no worker in the chart: "
        f"{sorted(routed_queues - declared)}"
    )


def test_compose_runs_a_worker_for_every_routed_queue(routed_queues, compose):
    consumed = _compose_consumed_queues(compose)
    assert routed_queues <= consumed, (
        f"queues routed by task_routes with no worker in docker-compose: "
        f"{sorted(routed_queues - consumed)}"
    )


def test_no_worker_consumes_a_queue_nothing_routes_to(routed_queues, helm_values):
    """The other direction: a worker burning a pod on an always-empty queue."""
    declared = set(helm_values["workers"])
    assert declared <= routed_queues, (
        f"workers in the chart for queues task_routes never targets: "
        f"{sorted(declared - routed_queues)}"
    )


# ── Scheduled tasks can actually reach a worker ──────────────────────────────

def test_scheduled_tasks_route_to_a_consumed_queue(scheduled_tasks, task_routes, helm_values):
    declared = set(helm_values["workers"])
    assert scheduled_tasks, "no beat entries found; this guard would pass vacuously"
    for name, task in scheduled_tasks.items():
        module = task.rsplit(".", 1)[0]
        queue = task_routes.get(f"{module}.*", {}).get("queue")
        assert queue is not None, f"beat entry {name!r} routes to no queue"
        assert queue in declared, (
            f"beat entry {name!r} enqueues onto {queue!r}, which no worker consumes"
        )


def test_helm_chart_runs_celery_beat():
    """
    Without this Deployment the GDPR retention sweep and the stale-submission
    recovery sweep have no trigger at all in Kubernetes.
    """
    beat = HELM / "templates" / "beat.yaml"
    assert beat.exists(), "the chart has no Celery Beat deployment"
    text = beat.read_text(encoding="utf-8")
    assert "beat" in text and "-A" in text
    assert "replicas: 1" in text, "beat must be a single replica"
    assert "type: Recreate" in text, (
        "two beats against one schedule enqueue every periodic task twice"
    )


def test_compose_runs_celery_beat(compose):
    commands = " ".join(
        str(svc.get("command", "")) for svc in compose["services"].values()
    )
    assert "beat" in commands


# ── Probes ask the question their kind is for ────────────────────────────────

def _probe_paths(text: str) -> dict[str, list[str]]:
    """
    Map each probe kind to the paths it requests, by walking the raw manifest.

    Helm templates are not valid YAML, so this reads structure from indentation
    rather than parsing. Crude, and it only has to survive the two files here.
    """
    found: dict[str, list[str]] = {"livenessProbe": [], "readinessProbe": []}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        for kind in found:
            if stripped.startswith(f"{kind}:"):
                current = kind
        if current and stripped.startswith("path:"):
            found[current].append(stripped.split("path:", 1)[1].strip())
            current = None
    return found


@pytest.mark.parametrize(
    "manifest",
    [HELM / "templates" / "api.yaml", K8S / "deployment.yaml"],
    ids=["helm", "k8s"],
)
def test_api_readiness_probe_checks_dependencies(manifest):
    """
    /health returns 200 whenever the process is running. /ready round-trips
    Postgres and Redis and returns 503 when either is gone. A readiness probe
    pointed at /health sends traffic to a pod that cannot serve it.
    """
    probes = _probe_paths(manifest.read_text(encoding="utf-8"))
    assert probes["readinessProbe"] == ["/ready"], (
        f"{manifest.name} readiness probe requests {probes['readinessProbe']}, not /ready"
    )
    assert probes["livenessProbe"] == ["/health"], (
        f"{manifest.name} liveness probe requests {probes['livenessProbe']}, not /health"
    )


# ── Settings the API refuses to boot without ─────────────────────────────────

def test_chart_supplies_every_setting_production_requires(helm_values):
    """
    `Settings._validate_production_settings` raises rather than starting with an
    unsafe value. That is the right behaviour and it makes the chart's env a
    hard dependency: a setting added to that validator and not to the ConfigMap
    turns into a CrashLoopBackOff on the next deploy, with the reason only in
    the pod log.
    """
    from config import Settings

    api_env = helm_values["api"]["env"]
    assert api_env["ENVIRONMENT"] == "production", (
        "this assertion is about the production validator; the chart no longer targets it"
    )

    configmap = (HELM / "templates" / "configmap.yaml").read_text(encoding="utf-8")
    kwargs = {
        "environment": "production",
        "secret_key": "x" * 64,
        "minio_secret_key": "not-the-default",
        "sentry_dsn": "https://example@sentry.invalid/1",
    }
    for field in Settings.model_fields:
        if not field.startswith("keycloak_"):
            continue
        key = field.upper()
        if key not in api_env:
            continue
        kwargs[field] = api_env[key]
        assert key in configmap, f"{key} is set in values.yaml but never reaches the ConfigMap"

    Settings(**kwargs)


def test_production_audience_is_wired_through_the_configmap(helm_values):
    configmap = (HELM / "templates" / "configmap.yaml").read_text(encoding="utf-8")
    assert "KEYCLOAK_AUDIENCE" in configmap
    assert helm_values["api"]["env"]["KEYCLOAK_AUDIENCE"].strip()


# ── Shutdown is given time to be graceful ────────────────────────────────────

def test_api_termination_grace_exceeds_prestop_sleep(helm_values):
    """SIGKILL landing mid-preStop defeats the point of having one."""
    api = helm_values["api"]
    assert api["terminationGracePeriodSeconds"] > api["preStopSleepSeconds"]


def test_workers_declare_a_grace_period(routed_queues, helm_values):
    """
    SIGTERM is a warm shutdown for Celery only if Kubernetes waits for it. At
    the 30-second default a long genomic task is killed on every deploy; it is
    `acks_late` so it is redelivered, but it restarts from the beginning.
    """
    for queue, cfg in helm_values["workers"].items():
        grace = cfg.get("terminationGracePeriodSeconds")
        assert grace is not None, f"worker {queue!r} has no terminationGracePeriodSeconds"
        assert grace > 30, f"worker {queue!r} grace period {grace}s is at or below the default"


# ── The database is backed up ────────────────────────────────────────────────
#
# OO-12. Nothing backed the application database up, and HIPAA_COMPLIANCE.md
# claimed otherwise, citing WAL archiving that was never configured. Persistence
# is not backup: losing the PVC took every submission and result with it.

def test_the_chart_defines_a_database_backup(helm_values):
    backup = HELM / "templates" / "backup-cronjob.yaml"
    assert backup.exists(), "the chart has no database backup"
    assert helm_values["backup"]["enabled"] is True, (
        "a backup that must be switched on is off in the deployment that needed it"
    )


def test_the_backup_targets_the_application_database_not_keycloaks():
    """
    The chart runs two PostgreSQL instances. `{release}-postgresql` is the
    Bitnami sub-chart the application uses; `{fullname}-postgres` is Keycloak's.
    The compliance document previously cited the second while describing the
    first.
    """
    text = (HELM / "templates" / "backup-cronjob.yaml").read_text(encoding="utf-8")
    assert "-postgresql" in text
    assert 'openoncology.fullname" . }}-postgres"' not in text


def test_the_backup_fails_loudly():
    """
    A backup that fails quietly is worse than none, because it is believed. No
    `|| true` on the dump or the upload, and a size floor so an empty dump is an
    error rather than a small file.
    """
    text = (HELM / "templates" / "backup-cronjob.yaml").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "backup aborted" in text, "no size floor on the dump"
    script = text[text.index("set -euo pipefail"):]
    dump_line = [ln for ln in script.splitlines() if "pg_dump" in ln]
    assert dump_line and "|| true" not in dump_line[0]


def test_the_backup_writes_a_manifest():
    """A restore is verified against recorded bytes, not against a file existing;
    a zero-byte object is also a file."""
    text = (HELM / "templates" / "backup-cronjob.yaml").read_text(encoding="utf-8")
    assert "manifest.json" in text
    assert '"bytes"' in text


def test_a_restore_procedure_is_documented():
    """
    OO-12's acceptance requires an exercised restore. The runbook is the
    prerequisite for that, and it states plainly that the drill has not been run.
    """
    runbook = REPO_ROOT / "docs" / "RUNBOOK_BACKUP_RESTORE.md"
    assert runbook.exists()
    text = runbook.read_text(encoding="utf-8")
    assert "alembic_version" in text, "a restore is not verified without a schema check"
    assert "Restore drill" in text
