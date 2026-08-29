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


# ── Network policies ─────────────────────────────────────────────────────────
#
# OO-5. infra/k8s/namespace.yaml carried a default-deny set and the chart carried
# none. It could not be ported verbatim: `allow-workers-egress` selects on
# `app.kubernetes.io/part-of`, a label _helpers.tpl never emits, so the rule
# matched nothing and a default-deny alongside it would have severed every
# worker from Postgres and Redis while rendering and linting clean.
#
# The rendered check lives in the validate-manifests CI job, which can run helm.
# These assert the properties that are visible in the template.

NETPOL = HELM / "templates" / "networkpolicy.yaml"


def test_the_chart_has_network_policies():
    assert NETPOL.exists()


def test_network_policies_are_off_by_default(helm_values):
    """
    A NetworkPolicy fails closed and nothing here can test one against a real
    cluster. On by default means the first person to discover a wrong selector
    is whoever deploys it.
    """
    assert helm_values["networkPolicy"]["enabled"] is False


def test_dns_egress_is_allowed():
    """
    The rule everything else depends on. Under default-deny, egress to kube-dns
    must be explicit or every lookup fails, and the symptom is every dependency
    appearing to be down at once.
    """
    text = NETPOL.read_text(encoding="utf-8")
    assert "allow-dns" in text
    assert "port: 53" in text
    assert "protocol: UDP" in text


def _netpol_without_comments() -> str:
    """
    Helm comment blocks explain why the k8s copy could not be ported, and quote
    the label that made it unusable. Scanning them as if they were selectors is
    how the first version of this test failed on its own documentation.
    """
    return re.sub(r"\{\{/\*.*?\*/\}\}", "", NETPOL.read_text(encoding="utf-8"), flags=re.S)


def test_no_policy_selects_on_a_label_the_chart_never_emits():
    """
    The specific defect that made the k8s copy unusable here.
    `app.kubernetes.io/part-of` is selected on there and emitted nowhere.
    """
    text = _netpol_without_comments()
    emitted = (HELM / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    # component is set inline by each template rather than by the helper.
    known = set(re.findall(r"(app\.kubernetes\.io/[a-z-]+):", emitted)) | {
        "app.kubernetes.io/component"
    }
    # Two forms, and missing the second is how the first version of this guard
    # passed a deliberately broken policy: matchLabels writes `label: value`,
    # matchExpressions writes `key: label`.
    selectors = set(re.findall(r"(app\.kubernetes\.io/[a-z-]+):", text))
    selectors |= set(re.findall(r"key:\s*(app\.kubernetes\.io/[a-z-]+)", text))
    unknown = sorted(selectors - known)
    assert not unknown, f"policies select on labels no template emits: {unknown}"


def test_workers_are_matched_by_expression_not_equality(helm_values):
    """
    workers.yaml renders one Deployment per queue, each with its own component
    value, so a single equality selector cannot reach them all.
    """
    text = NETPOL.read_text(encoding="utf-8")
    assert "matchExpressions" in text
    assert "operator: In" in text
    assert len(helm_values["workers"]) >= 4


def test_the_gdpr_worker_keeps_its_keycloak_egress():
    """
    erase_patient_data calls Keycloak's admin API to delete the user. A policy
    modelled on the other three workers breaks erasure silently, which is the
    obligation #130 restored.
    """
    text = NETPOL.read_text(encoding="utf-8")
    assert "worker-gdpr" in text
    gdpr = text[text.index("worker-gdpr-keycloak"):]
    assert "component: keycloak" in gdpr


def test_datastore_selectors_are_values_not_literals(helm_values):
    """
    Bitnami has changed these labels between chart majors, and a wrong one
    denies the database while rendering perfectly.
    """
    stores = helm_values["networkPolicy"]["datastores"]
    assert set(stores) >= {"postgresql", "redis", "objectStore"}
    text = NETPOL.read_text(encoding="utf-8")
    assert "$np.datastores.postgresql" in text


def test_the_application_database_is_not_confused_with_keycloaks():
    """
    `component: postgres` is Keycloak's StatefulSet. The application uses the
    Bitnami sub-chart. An egress rule on the former allows the wrong database
    and denies the right one.
    """
    text = NETPOL.read_text(encoding="utf-8")
    api_policy = text[text.index("-api\n"):text.index("-web\n")]
    assert "$np.datastores.postgresql" in api_policy
    assert "component: postgres\n" not in api_policy


# ── Every service the ConfigMap names is actually created ────────────────────
#
# OO-18. `MINIO_ENDPOINT` pointed at `{release}-minio:9000` and no template
# created a MinIO, so a helm install produced an application configured to reach
# object storage that did not exist. Every upload, report write and GDPR object
# deletion failed, as did the backup job, which writes through `mc`.
#
# This is the general form: an endpoint the application is told to dial must be
# something the chart creates, something a declared dependency creates, or an
# external address the operator supplies deliberately.

def _chart_service_names() -> set[str]:
    """Service and StatefulSet names the templates define, with Helm's two name
    expressions reduced to markers."""
    names = set()
    for path in (HELM / "templates").glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"name:\s*(\{\{[^}]*\}\}[-a-z0-9]*)", text):
            token = match.group(1)
            token = re.sub(r"\{\{[^}]*fullname[^}]*\}\}", "FULLNAME", token)
            token = re.sub(r"\{\{[^}]*Release\.Name[^}]*\}\}", "RELEASE", token)
            names.add(token.strip())
    return names


def test_minio_is_deployed_by_the_chart(helm_values):
    minio = HELM / "templates" / "minio.yaml"
    assert minio.exists(), (
        "the ConfigMap points the application at MinIO and nothing creates one"
    )
    assert helm_values["minio"]["enabled"] is True


def test_the_minio_service_name_matches_the_endpoint_the_app_dials():
    """
    The Service must be named `{release}-minio` because that is what
    `openoncology.minioEndpoint` resolves to. Both read the same helper now, so
    they cannot drift; this asserts the name itself has not moved.
    """
    minio = (HELM / "templates" / "minio.yaml").read_text(encoding="utf-8")
    helpers = (HELM / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    assert "{{ .Release.Name }}-minio" in minio
    assert "minioEndpoint" in helpers
    configmap = (HELM / "templates" / "configmap.yaml").read_text(encoding="utf-8")
    assert "openoncology.minioEndpoint" in configmap, (
        "the ConfigMap builds the endpoint itself instead of using the helper"
    )


def test_disabling_minio_requires_an_external_endpoint():
    """Turning it off must not silently leave the application dialling nothing."""
    helpers = (HELM / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    assert "required" in helpers and "externalEndpoint" in helpers


def test_minio_keeps_its_data_on_a_volume():
    """It is the store for patient genomic files, not a cache."""
    minio = (HELM / "templates" / "minio.yaml").read_text(encoding="utf-8")
    assert "kind: StatefulSet" in minio
    assert "volumeClaimTemplates" in minio


def test_the_object_store_image_is_pinned():
    """`latest` on an object store means the version changes on a pod restart."""
    minio = (HELM / "templates" / "minio.yaml").read_text(encoding="utf-8")
    values = yaml.safe_load((HELM / "values.yaml").read_text(encoding="utf-8"))
    assert values["minio"]["image"]["tag"] != "latest"


def test_the_backup_job_creates_its_bucket():
    """
    `mc cp` into a bucket that does not exist fails. The application creates its
    own three on demand and knows nothing about the backup bucket.
    """
    text = (HELM / "templates" / "backup-cronjob.yaml").read_text(encoding="utf-8")
    assert "mc mb --ignore-existing" in text


def test_the_network_policy_can_select_the_object_store(helm_values):
    """
    The egress rule added in OO-5 pointed at a selector that matched nothing,
    because nothing was deployed. It has to match what minio.yaml now labels.
    """
    selector = helm_values["networkPolicy"]["datastores"]["objectStore"]
    minio = (HELM / "templates" / "minio.yaml").read_text(encoding="utf-8")
    # No substring fallback. The first version of this accepted `value in minio`,
    # which passed on the word "minio" appearing anywhere in the file and let a
    # selector through that matched no pod.
    for key, value in selector.items():
        assert f"{key}: {value}" in minio, (
            f"networkPolicy objectStore selector {key}={value} matches no label "
            f"minio.yaml sets. Its pods carry the chart selectorLabels plus "
            f"component: minio, so app.kubernetes.io/name is the chart name."
        )


# ── The two databases are configured separately ──────────────────────────────
#
# OO-9. templates/postgres.yaml is Keycloak's database; the application uses the
# Bitnami postgresql sub-chart. The first read `postgresql.primary.persistence`
# and `postgresql.primary.resources`, which belong to the second, so production
# gave a realm database holding a few megabytes a 200Gi volume and resizing one
# silently resized the other.
#
# The confusion has caused two defects already: HIPAA_COMPLIANCE.md cited this
# file as evidence of a backup for patient data, and the OO-5 network policy
# nearly granted the application egress to this database rather than its own.

KEYCLOAK_DB = HELM / "templates" / "postgres.yaml"


def test_keycloak_database_is_sized_by_its_own_value(helm_values):
    assert "keycloakDatabase" in helm_values
    text = KEYCLOAK_DB.read_text(encoding="utf-8")
    assert "keycloakDatabase.persistence.size" in text
    assert "postgresql.primary.persistence" not in text


def test_keycloak_database_does_not_borrow_the_application_resources():
    text = KEYCLOAK_DB.read_text(encoding="utf-8")
    assert "keycloakDatabase.resources" in text
    assert "postgresql.primary.resources" not in text


def test_the_two_databases_are_sized_independently(helm_values):
    """
    Equal sizes would pass the assertions above while still meaning nobody chose
    either number.
    """
    app = helm_values["postgresql"]["primary"]["persistence"]["size"]
    keycloak = helm_values["keycloakDatabase"]["persistence"]["size"]
    assert app != keycloak, (
        "both databases request the same volume size, which suggests one is "
        "still inheriting the other's number"
    )


def test_the_template_says_which_database_it_is():
    """
    A reader arriving at a file called postgres.yaml reasonably assumes it is
    the application's. Two defects came from exactly that assumption.
    """
    text = KEYCLOAK_DB.read_text(encoding="utf-8")
    head = text[: text.index("apiVersion")]
    assert "KEYCLOAK" in head.upper()
    assert "not the application" in head.lower()
