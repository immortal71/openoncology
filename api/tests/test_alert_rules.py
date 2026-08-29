"""
An alert rule must reference a metric something actually emits.

BACKLOG.md OO-13. `infra/prometheus.yml` set `rule_files: []` and
`alertmanagers: []`, so every metric was scraped and no alert could fire. Four
of its seven scrape jobs also pointed at exporters that exist nowhere in this
repository, which reported `up == 0` permanently and would have paged
continuously the moment any rule watched `up`.

A rule written against a metric nobody exports is the same defect as no rule at
all, and harder to notice, because the rule file looks like coverage. This
module fails the build when that happens.

The permitted set is deliberately small: Prometheus' own `up` and `scrape_*`
series, and the default metrics `prometheus_fastapi_instrumentator` installs in
`api/main.py`. Adding a metric to this list should mean adding the exporter that
emits it.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "infra"
PROM_CONFIG = INFRA / "prometheus.yml"
RULES_DIR = INFRA / "alerts"

# Emitted by Prometheus itself for every target.
PROMETHEUS_INTERNAL = {"up", "scrape_duration_seconds", "scrape_samples_scraped"}

# The default set installed by prometheus_fastapi_instrumentator, which
# api/main.py wires up. Suffixes are the Prometheus histogram/counter families.
INSTRUMENTATOR_BASE = {
    "http_requests_total",
    "http_request_duration_seconds",
    "http_request_duration_highr_seconds",
    "http_request_size_bytes",
    "http_response_size_bytes",
}
# Emitted by the exporters the chart deploys (OO-16). This list grows only
# alongside an exporter that actually produces the series: that is the whole
# point of the check below, and adding a name here to make a rule pass would
# reintroduce exactly the defect it exists to catch.
EXPORTER_METRICS = {
    # oliver006/redis_exporter. redis_key_size carries the Celery queue depths,
    # one series per key named in REDIS_EXPORTER_CHECK_KEYS.
    "redis_up",
    "redis_key_size",
    # danihodovic/celery-exporter. Requires worker_send_task_events and
    # task_send_sent_event, both set in api/workers/__init__.py.
    "celery_worker_up",
    "celery_task_failed_total",
    "celery_task_received_total",
    "celery_task_succeeded_total",
    "celery_task_runtime_seconds",
    # prometheuscommunity/postgres-exporter.
    "pg_up",
    "pg_stat_activity_count",
    "pg_settings_max_connections",
    # Custom queries from templates/exporter-queries.yaml (OO-17). Named for the
    # query block plus the column, which is how postgres_exporter composes them.
    "openoncology_evidence_results_last_hour",
    "openoncology_evidence_degraded_last_hour",
    "openoncology_evidence_withheld_last_hour",
}

# Declared in api/main.py and never incremented, for as long as they existed.
# They described work the Celery workers do, and workers are separate processes,
# so a counter registered in the API could never have carried their data. Both
# are removed; these names are kept here so a rule written against them fails
# loudly rather than evaluating against an absent series forever.
REMOVED_METRICS = {
    "openoncology_mutations_processed_total",
    "openoncology_genomic_pipeline_seconds",
}

_SUFFIXES = ("", "_bucket", "_count", "_sum", "_created")
ALLOWED_METRICS = PROMETHEUS_INTERNAL | EXPORTER_METRICS | {
    base + suffix
    for base in INSTRUMENTATOR_BASE | EXPORTER_METRICS
    for suffix in _SUFFIXES
}

# PromQL functions and keywords that appear where a metric name would, and are
# not metrics.
_PROMQL_TOKENS = {
    "sum", "rate", "irate", "avg", "min", "max", "count", "count_values", "by",
    "without", "on", "ignoring", "group_left", "group_right", "increase",
    "histogram_quantile", "clamp_min", "clamp_max", "le", "job", "instance",
    "status", "handler", "method", "and", "or", "unless", "offset", "bool",
    "absent", "time", "delta", "deriv", "topk", "bottomk", "quantile",
}


def _rule_files() -> list[Path]:
    return sorted(RULES_DIR.glob("*.rules.yml"))


def _rules() -> list[tuple[str, dict]]:
    out = []
    for path in _rule_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for group in doc.get("groups", []):
            for rule in group.get("rules", []):
                out.append((f"{path.name}:{group.get('name')}:{rule.get('alert')}", rule))
    return out


def _metric_names(expr: str) -> set[str]:
    """Identifiers in a PromQL expression that are used as metric selectors."""
    names = set()
    for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b(\s*[({\[]|\s|$)", expr):
        token, tail = match.group(1), match.group(2)
        if token in _PROMQL_TOKENS:
            continue
        # A bare identifier followed by ( is a function call, not a metric.
        if tail.strip().startswith("("):
            continue
        names.add(token)
    return names


# ── The wiring exists at all ─────────────────────────────────────────────────

def test_prometheus_config_loads_rule_files():
    config = yaml.safe_load(PROM_CONFIG.read_text(encoding="utf-8"))
    assert config.get("rule_files"), (
        "rule_files is empty, so no alert can fire regardless of what alerts/ contains"
    )


def test_rule_files_exist_and_are_not_empty():
    files = _rule_files()
    assert files, f"rule_files is set but {RULES_DIR} contains no *.rules.yml"
    assert _rules(), "rule files parsed but define no alerts"


def test_every_rule_file_is_valid_yaml_in_the_expected_shape():
    for path in _rule_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(doc, dict) and "groups" in doc, f"{path.name} has no groups"
        for group in doc["groups"]:
            assert group.get("name"), f"{path.name} has an unnamed group"
            assert group.get("rules"), f"{path.name}:{group.get('name')} has no rules"


# ── Rules reference metrics that exist ───────────────────────────────────────

@pytest.mark.parametrize("rule_id,rule", _rules(), ids=[r[0] for r in _rules()])
def test_rule_references_only_exported_metrics(rule_id, rule):
    """
    The defect this module exists for. A rule on a metric nothing emits never
    fires, and reads as coverage.
    """
    unknown = _metric_names(rule["expr"]) - ALLOWED_METRICS
    assert not unknown, (
        f"{rule_id} references metrics that nothing in this repository exports: "
        f"{sorted(unknown)}. Either add the exporter, or do not write the rule."
    )


@pytest.mark.parametrize("rule_id,rule", _rules(), ids=[r[0] for r in _rules()])
def test_rule_is_actionable(rule_id, rule):
    """Severity routes it; `for` stops a single scrape blip paging someone;
    a summary is what the person woken up actually reads."""
    assert rule.get("for"), f"{rule_id} has no `for`, so one bad scrape pages"
    assert rule.get("labels", {}).get("severity"), f"{rule_id} has no severity"
    assert rule.get("annotations", {}).get("summary"), f"{rule_id} has no summary"


# ── Scrape targets are real ──────────────────────────────────────────────────

def test_no_active_scrape_job_targets_an_undeployed_exporter():
    """
    Four jobs pointed at `db-exporter`, `redis-exporter` and `worker-*:9100`,
    none of which is deployed by docker-compose.yml or the Helm chart, and the
    workers start no metrics server. Each reported `up == 0` forever. With a rule
    watching `up` that pages continuously, which trains whoever is on call to
    ignore the one signal that matters.
    """
    config = yaml.safe_load(PROM_CONFIG.read_text(encoding="utf-8"))
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    helm = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (INFRA / "helm").rglob("*.yaml")
    )

    undeployed = []
    for job in config.get("scrape_configs", []):
        for static in job.get("static_configs", []):
            for target in static.get("targets", []):
                host = target.split(":")[0]
                if host in ("localhost", "127.0.0.1"):
                    continue
                if host not in compose and host not in helm:
                    undeployed.append(f"{job.get('job_name')} -> {target}")

    assert not undeployed, (
        "scrape jobs target hosts that no deployment defines: "
        f"{undeployed}. Comment the job out until its exporter is deployed."
    )


# ── Queue alerts need the exporter to be watching that queue ─────────────────

def test_every_alerted_queue_is_watched_by_the_redis_exporter():
    """
    `redis_key_size` only exists for keys named in REDIS_EXPORTER_CHECK_KEYS.
    An alert on a queue absent from that list is a rule that can never fire,
    which is the defect this module exists for, one layer further down.
    """
    values = yaml.safe_load((REPO_ROOT / "infra" / "helm" / "values.yaml").read_text(encoding="utf-8"))
    watched = set(
        values["exporters"]["instances"]["redis"]["env"]["REDIS_EXPORTER_CHECK_KEYS"].split(",")
    )
    alerted = set()
    for _, rule in _rules():
        alerted |= set(re.findall(r'redis_key_size\{key="([a-z]+)"\}', rule["expr"]))
    missing = sorted(alerted - watched)
    assert not missing, (
        f"alerts reference queue depths the exporter does not collect: {missing}"
    )


def test_the_exporter_watches_every_routed_queue():
    """The other direction: a queue Celery routes to and nothing measures."""
    values = yaml.safe_load((REPO_ROOT / "infra" / "helm" / "values.yaml").read_text(encoding="utf-8"))
    watched = set(
        values["exporters"]["instances"]["redis"]["env"]["REDIS_EXPORTER_CHECK_KEYS"].split(",")
    )
    source = (REPO_ROOT / "api" / "workers" / "__init__.py").read_text(encoding="utf-8")
    routed = set(re.findall(r'"queue":\s*"([a-z]+)"', source))
    assert routed <= watched, (
        f"queues Celery routes to that no exporter measures: {sorted(routed - watched)}"
    )


def test_celery_task_events_are_enabled():
    """
    celery-exporter reports nothing without them, so every celery_* rule above
    would evaluate against an absent series and stay silent.
    """
    source = (REPO_ROOT / "api" / "workers" / "__init__.py").read_text(encoding="utf-8")
    assert "worker_send_task_events=True" in source
    assert "task_send_sent_event=True" in source


# ── Metrics that were removed must not come back in a rule ───────────────────

@pytest.mark.parametrize("rule_id,rule", _rules(), ids=[r[0] for r in _rules()])
def test_no_rule_references_a_removed_metric(rule_id, rule):
    used = _metric_names(rule["expr"]) & REMOVED_METRICS
    assert not used, (
        f"{rule_id} references {sorted(used)}, which api/main.py declared and "
        "never incremented. They are removed; a rule on them can never fire."
    )


def test_the_removed_metrics_are_actually_gone_from_the_app():
    """The allowlist rejecting them is only meaningful while nothing emits them."""
    main = (REPO_ROOT / "api" / "main.py").read_text(encoding="utf-8")
    for name in REMOVED_METRICS:
        assert f'"{name}"' not in main, f"{name} is declared again in api/main.py"


# ── The degraded-evidence signal is queried, not counted in-process ──────────

def test_the_evidence_query_is_shipped_and_mounted():
    """
    OO-17. The worker's counter is a module global in a process nothing scrapes,
    and it resets on restart, which is exactly when a sustained run of fallbacks
    would look like it had stopped. The signal comes from the database instead.
    """
    queries = REPO_ROOT / "infra" / "helm" / "templates" / "exporter-queries.yaml"
    assert queries.exists()
    text = queries.read_text(encoding="utf-8")
    assert "evidence_provenance" in text
    assert "is_current" in text

    values = yaml.safe_load((REPO_ROOT / "infra" / "helm" / "values.yaml").read_text(encoding="utf-8"))
    pg = values["exporters"]["instances"]["postgres"]
    assert pg.get("queriesConfigMap") is True
    assert pg["env"].get("PG_EXPORTER_EXTEND_QUERY_PATH"), (
        "the query file is shipped but the exporter is not told to read it"
    )


def test_absent_provenance_is_treated_as_degraded():
    """
    A result predating provenance capture cannot be shown to have used current
    evidence, and the safe reading of absent is not-current. `coalesce(..., false)`
    is what makes null count; without it those rows would be silently excluded.
    """
    text = (REPO_ROOT / "infra" / "helm" / "templates" / "exporter-queries.yaml").read_text(encoding="utf-8")
    assert "coalesce" in text.lower()
