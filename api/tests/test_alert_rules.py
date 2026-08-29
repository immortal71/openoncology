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
_SUFFIXES = ("", "_bucket", "_count", "_sum", "_created")
ALLOWED_METRICS = PROMETHEUS_INTERNAL | {
    base + suffix for base in INSTRUMENTATOR_BASE for suffix in _SUFFIXES
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
