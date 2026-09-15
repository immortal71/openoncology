"""
Guards for the gap between what the images are built with and what the
deployment supplies them at runtime.

test_deployment_manifests.py checks that the manifests describe the workloads
they should. This module checks the other seam, and every defect it covers had
the same shape: the manifest was right, the application was right, and the value
did not survive the trip between them. None of it is visible to `helm lint`,
kubeconform, or a rendered-output grep, because in each case the string is
present and well formed and only wrong once something tries to use it.

  * The web Deployment probed `/api/health`, which the Next app did not serve.
    Liveness killed the container on its third 404 and readiness never admitted
    it to the Service, so the web tier could not come up at all.
  * `NEXT_PUBLIC_*` is a compile-time substitution. Both deployment paths set
    those variables at runtime, which reaches a bundle compiled inside
    `docker build` not at all: the published image carried
    `http://localhost:8000` as the API address and `undefined` as the Keycloak
    one, so the deployed site called an API on the visitor's own machine and
    nobody could log in.
  * `DATABASE_URL` sat in the ConfigMap containing `$(DB_PASSWORD)`. Kubernetes
    expands `$(VAR)` in a container's `env` entries and in its command and args,
    and nowhere else — a key read through `envFrom` is passed through byte for
    byte. Every pod received those seven characters as its password.
  * The chart ran no migration. The API bootstraps tables only when ENVIRONMENT
    is `development`, so a fresh install came up against an empty database while
    `/ready` — which round-trips Postgres with `SELECT 1`, something an empty
    database answers perfectly well — reported the pods healthy.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"
HELM = REPO_ROOT / "infra" / "helm"
K8S = REPO_ROOT / "infra" / "k8s"


# ── The web probes ask for something the app serves ──────────────────────────

def _web_probe_paths() -> list[str]:
    text = (HELM / "templates" / "web.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s*path:\s*(\S+)\s*$", text, flags=re.M)


def test_the_web_probes_request_a_route_the_app_serves():
    """
    A probe path maps to `app/<path>/route.ts` under the App Router. The chart
    asked for /api/health and only app/api/commits existed, so both probes took
    a 404 forever: CrashLoopBackOff on liveness and no Service endpoints on
    readiness, from a chart that rendered and linted clean.
    """
    paths = _web_probe_paths()
    assert paths, "web.yaml declares no probe paths; this guard would pass vacuously"
    for path in paths:
        route = WEB / "app" / path.lstrip("/") / "route.ts"
        assert route.exists(), (
            f"web.yaml probes {path}, which no route handler serves "
            f"(expected {route.relative_to(REPO_ROOT).as_posix()})"
        )


def test_the_web_dockerfile_healthcheck_agrees_with_the_probes():
    """`docker run` and Kubernetes should not disagree about what alive means."""
    dockerfile = (WEB / "Dockerfile").read_text(encoding="utf-8")
    for path in _web_probe_paths():
        assert path in dockerfile, (
            f"the chart probes {path} and the image's HEALTHCHECK does not"
        )


# ── Public settings are read at runtime, not compiled in ─────────────────────

CLIENT_SOURCE_ROOTS = ["app", "lib", "components"]
RUNTIME_CONFIG = WEB / "lib" / "runtime-config.ts"


def _client_sources() -> list[Path]:
    files: list[Path] = []
    for root in CLIENT_SOURCE_ROOTS:
        for pattern in ("**/*.ts", "**/*.tsx"):
            files.extend(
                p for p in (WEB / root).glob(pattern)
                if "node_modules" not in p.parts and "__tests__" not in p.parts
            )
    return files


def test_no_client_module_reads_a_public_setting_from_process_env():
    """
    `process.env.NEXT_PUBLIC_X` in client code is replaced by Next with the
    value present when `next build` ran. Inside `docker build` there is no such
    value, and neither the compose `environment:` block nor the Helm ConfigMap
    can reach a bundle that was already compiled.

    lib/runtime-config.ts is the one module allowed to name them, because it is
    where the fallback to the compiled-in value deliberately lives.
    """
    offenders = []
    for path in _client_sources():
        if path == RUNTIME_CONFIG:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "process.env.NEXT_PUBLIC_" in line:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{n}")
    assert not offenders, (
        "these read a NEXT_PUBLIC_ setting straight from process.env, which "
        "freezes it at build time; use publicEnv/publicEnvOr from "
        "lib/runtime-config instead:\n  " + "\n  ".join(offenders)
    )


def test_next_config_does_not_reintroduce_build_time_substitution():
    """
    An `env` block in next.config.js substitutes at compile time on the server
    side too, so it would sit in front of the runtime lookup and win. This is
    exactly what shipped `http://localhost:8000` into the published image.
    """
    text = (WEB / "next.config.js").read_text(encoding="utf-8")
    without_comments = re.sub(r"//[^\n]*", "", text)
    assert not re.search(r"^\s*env\s*:", without_comments, flags=re.M), (
        "next.config.js declares an `env` block; NEXT_PUBLIC_ settings are "
        "resolved at request time and a block here would override that"
    )


def test_the_runtime_config_route_exists_and_is_never_cached():
    """
    Statically rendered or cached, this endpoint answers with the values held
    when the image was built — which is the failure it exists to fix.
    """
    route = WEB / "app" / "env.js" / "route.ts"
    assert route.exists(), "no runtime configuration endpoint"
    text = route.read_text(encoding="utf-8")
    assert 'dynamic = "force-dynamic"' in text
    assert "no-store" in text


def test_the_layout_loads_the_runtime_config_before_hydration():
    """
    Client components read `window.__OO_ENV__` as soon as they run. An `async`
    or `defer` script would let hydration start first, and the failure is a
    silent fall-through to the compiled-in default rather than an error.
    """
    text = (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
    match = re.search(r"<script[^>]*src=\"/env\.js\"[^>]*/>", text)
    assert match, "the root layout does not load /env.js"
    assert "async" not in match.group(0) and "defer" not in match.group(0), (
        "the runtime config script must be blocking"
    )


def test_every_public_setting_the_chart_supplies_is_one_the_app_serves(  # noqa: D103
):
    """
    A NEXT_PUBLIC_ key in the ConfigMap that `PUBLIC_ENV_NAMES` does not list is
    a setting the operator configures and the browser never sees.
    """
    configmap = (HELM / "templates" / "configmap.yaml").read_text(encoding="utf-8")
    served = set(
        re.findall(
            r'"(NEXT_PUBLIC_[A-Z0-9_]+)"',
            RUNTIME_CONFIG.read_text(encoding="utf-8"),
        )
    )
    supplied = set(re.findall(r"^\s*(NEXT_PUBLIC_[A-Z0-9_]+):", configmap, flags=re.M))
    assert supplied, "the ConfigMap supplies no NEXT_PUBLIC_ settings at all"
    assert supplied <= served, (
        "the ConfigMap sets these and app/env.js never forwards them, so they "
        f"cannot reach the browser: {sorted(supplied - served)}"
    )


# ── $(VAR) is expanded where it is written, or not at all ────────────────────

def _helper_bodies() -> dict[str, str]:
    """Every `{{- define "name" -}}...{{- end }}` in _helpers.tpl, by name."""
    text = (HELM / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    return {
        name: body
        for name, body in re.findall(
            r'\{\{-?\s*define\s+"([^"]+)"\s*-?\}\}(.*?)\{\{-?\s*end\s*-?\}\}',
            text,
            flags=re.S,
        )
    }


def test_the_helm_configmap_holds_no_variable_reference():
    """
    Kubernetes substitutes `$(VAR)` in a container's `env` values and in its
    command and args. A ConfigMap key read through `envFrom` is not substituted,
    so a reference here arrives as literal text.

    Scanning the template alone would pass on the defect this exists for: the
    ConfigMap said `{{ include "openoncology.databaseUrl" . }}` and the
    `$(DB_PASSWORD)` was two files away in _helpers.tpl. So the includes are
    substituted first, which is as close to rendering as this can get without
    helm.
    """
    text = (HELM / "templates" / "configmap.yaml").read_text(encoding="utf-8")
    bodies = _helper_bodies()

    included = re.findall(r'\{\{-?\s*include\s+"([^"]+)"', text)
    assert included, "configmap.yaml includes no helper; this guard has drifted"
    for name in included:
        if name in bodies:
            text += "\n" + bodies[name]

    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert not re.search(r"\$\([A-Z_][A-Z0-9_]*\)", body), (
        "a ConfigMap value, or a helper it includes, references $(VAR); "
        "envFrom does not expand it"
    )


def test_the_k8s_configmap_holds_no_variable_reference():
    text = (K8S / "configmap.yaml").read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert not re.search(r"\$\([A-Z_][A-Z0-9_]*\)", body)


WORKLOADS_NEEDING_THE_DATABASE = [
    "api.yaml",
    "workers.yaml",
    "beat.yaml",
    "migrate-job.yaml",
]


@pytest.mark.parametrize("manifest", WORKLOADS_NEEDING_THE_DATABASE)
def test_database_url_is_defined_after_the_password_it_interpolates(manifest):
    """
    Expansion resolves against variables already defined earlier in the same
    `env` list. DATABASE_URL declared above DB_PASSWORD interpolates nothing,
    and fails exactly the way the ConfigMap version did.
    """
    text = (HELM / "templates" / manifest).read_text(encoding="utf-8")
    assert "DATABASE_URL" in text, f"{manifest} never defines DATABASE_URL"
    assert text.index("name: DB_PASSWORD") < text.index("name: DATABASE_URL"), (
        f"{manifest} defines DATABASE_URL before DB_PASSWORD, so $(DB_PASSWORD) "
        "expands to nothing"
    )


def test_the_standalone_k8s_deployment_defines_it_the_same_way():
    text = (K8S / "deployment.yaml").read_text(encoding="utf-8")
    assert "name: DATABASE_URL" in text
    assert text.index("name: DB_PASSWORD") < text.index("name: DATABASE_URL")


# ── The schema is created before anything queries it ─────────────────────────

def test_the_chart_migrates_the_schema():
    job = HELM / "templates" / "migrate-job.yaml"
    assert job.exists(), "the chart has no migration step"
    text = job.read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "pre-upgrade" in text, (
        "migrations must run before new pods roll, or new code meets an old schema"
    )


def test_migrations_are_on_by_default():
    values = yaml.safe_load((HELM / "values.yaml").read_text(encoding="utf-8"))
    assert values["migrations"]["enabled"] is True, (
        "a migration step that must be switched on is off in the deployment "
        "that needed it, and a Ready pod erroring on every request does not "
        "look like a missing migration"
    )


def test_the_migration_script_avoids_command_substitution():
    """
    Kubernetes runs its own `$(VAR)` pass over args before the shell sees them.
    `$(date +%s)` and friends collide with it, and which layer wins is not
    something to establish during a release.
    """
    text = (HELM / "templates" / "migrate-job.yaml").read_text(encoding="utf-8")
    args = text[text.index("args:"):text.index("envFrom:")]
    assert not re.search(r"\$\([^(]", args), (
        "the migration script uses $(...) command substitution"
    )


# ── The images agree with the security context imposed on them ───────────────

@pytest.mark.parametrize(
    ("dockerfile", "manifest"),
    [
        (REPO_ROOT / "api" / "Dockerfile", HELM / "templates" / "api.yaml"),
        (WEB / "Dockerfile", HELM / "templates" / "web.yaml"),
    ],
    ids=["api", "web"],
)
def test_the_image_runs_as_the_uid_the_chart_imposes(dockerfile, manifest):
    """
    Both images ran as root and the chart overrode that with `runAsUser`, so the
    identity the process actually had owned nothing the build had created. A
    declared USER makes the two answerable to each other.
    """
    declared = re.findall(r"^USER\s+(\d+)", dockerfile.read_text(encoding="utf-8"), flags=re.M)
    imposed = re.findall(r"runAsUser:\s*(\d+)", manifest.read_text(encoding="utf-8"))
    assert declared, f"{dockerfile.name} declares no USER; it runs as root"
    assert imposed, f"{manifest.name} sets no runAsUser"
    assert set(declared) == set(imposed), (
        f"{dockerfile.name} runs as uid {declared} and {manifest.name} imposes {imposed}"
    )


# ── The web image is reproducible ────────────────────────────────────────────

def test_the_web_image_installs_from_the_lockfile():
    """
    `npm install` against a manifest full of `^` ranges re-resolves every
    dependency at build time, so the image cannot be reproduced and is free to
    contain versions nothing here has run against. The lockfile was in the
    repository the whole time and the build never copied it.
    """
    text = (WEB / "Dockerfile").read_text(encoding="utf-8")
    assert "package-lock.json" in text, "the build does not copy the lockfile"
    assert "npm ci" in text
    assert not re.search(r"^\s*RUN\s+npm\s+install\b", text, flags=re.M)


def test_the_web_build_context_excludes_the_local_node_modules():
    """
    The build context is ./web, so the repository-root .dockerignore does not
    apply. Without one here, `COPY . .` in the builder copies the developer's
    node_modules over the ones installed for the image — Linux binaries replaced
    by whatever the host machine built.
    """
    ignore = WEB / ".dockerignore"
    assert ignore.exists(), "web/ has no .dockerignore"
    entries = {
        line.strip()
        for line in ignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert "node_modules" in entries
    assert ".next" in entries


# ── The sub-charts are pinned ────────────────────────────────────────────────

def test_the_chart_dependencies_are_locked():
    """
    Chart.yaml asks for `postgresql 15.5.x` and `redis 19.x.x`. `helm dependency
    update` resolves those against whatever Bitnami published most recently, so
    without a committed lock two installs of the same commit can run different
    sub-charts — and the pod labels the NetworkPolicy selectors match are among
    the things Bitnami has changed between versions. values.yaml says so itself.

    Same defect as `npm install` in the web image, in a different file.
    """
    lock = HELM / "Chart.lock"
    assert lock.exists(), (
        "infra/helm/Chart.lock is not committed, so the sub-chart versions a "
        "deploy gets are whatever the repository serves that day"
    )
    locked = yaml.safe_load(lock.read_text(encoding="utf-8"))
    chart = yaml.safe_load((HELM / "Chart.yaml").read_text(encoding="utf-8"))

    declared = {d["name"] for d in chart.get("dependencies") or []}
    pinned = {d["name"]: d["version"] for d in locked.get("dependencies") or []}
    assert declared, "Chart.yaml declares no dependencies; this guard has drifted"
    assert declared == set(pinned), (
        f"Chart.yaml and Chart.lock disagree: {sorted(declared ^ set(pinned))}"
    )
    for name, version in pinned.items():
        assert version.count(".") == 2 and "x" not in version, (
            f"{name} is locked to {version!r}, which is still a range"
        )


def test_ci_installs_the_locked_dependencies():
    """
    `helm dependency update` re-resolves the ranges and rewrites the lock, which
    makes committing it pointless. `build` installs exactly what is pinned and
    fails when the lock and Chart.yaml disagree.
    """
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    directives = [ln for ln in ci.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(directives)
    assert "helm dependency build" in body
    assert "helm dependency update" not in body, (
        "CI re-resolves the version ranges instead of installing the lock"
    )
