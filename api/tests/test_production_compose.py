"""
docker-compose.prod.yml is a production stack, and these assert the ways it
differs from the development one.

Every property here is an absence — no bind mount, no `--reload`, no datastore
listening on a public interface, nothing querying the database before the
migration has run. `docker compose config` cannot see any of them: it resolves
variables and validates the schema, and a file that starts the development stack
under a production name passes it perfectly.

The failure mode this guards against is not a broken deploy, which announces
itself. It is a deploy that works, on a host where `/docs` is public, the
database accepts connections from the internet, and Keycloak forgets the realm
whenever the container restarts.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROD = REPO_ROOT / "docker-compose.prod.yml"
DEV = REPO_ROOT / "docker-compose.yml"
CELERY_APP = REPO_ROOT / "api" / "workers" / "__init__.py"

# Compose interpolates these. yaml.safe_load does not, so `${VAR:?...}` arrives
# as a literal string, which is exactly what most of these assertions want to
# look at.
DATASTORES = {"db", "keycloak-db", "redis", "storage"}


@pytest.fixture(scope="module")
def prod() -> dict:
    return yaml.safe_load(PROD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def services(prod) -> dict:
    return prod["services"]


def _env(service: dict) -> dict[str, str]:
    """
    Compose accepts `environment:` as a mapping or as a list of `KEY=value`
    strings, and this file uses the mapping form throughout. Normalising anyway
    so that switching form makes a guard fail with its own message rather than
    crash with a TypeError, which reads like a broken test rather than a
    finding.
    """
    env = service.get("environment") or {}
    if isinstance(env, list):
        pairs = (str(item).split("=", 1) for item in env)
        return {k: (v[0] if v else "") for k, *v in pairs}
    return {str(k): str(v) for k, v in env.items()}


def _command(service: dict) -> str:
    command = service.get("command")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command or "")


def _api_image_services(services: dict) -> dict:
    """
    Every service running the API image: the API itself, the workers, beat and
    the migration.

    It asserts rather than returning empty. Selecting on `image:` means a
    production file rewritten to use `build:` would match nothing, and both
    callers would then iterate over nothing and pass — the exact shape of a
    guard that reports green because it checked no cases.
    """
    matched = {
        name: svc
        for name, svc in services.items()
        if "openoncology/api" in str(svc.get("image", ""))
    }
    assert matched, (
        "no service runs the published API image; production must deploy a "
        "built, tagged image rather than building from the working tree"
    )
    return matched


# ── It is not the development stack ──────────────────────────────────────────

def test_the_production_stack_exists_and_is_a_separate_file():
    assert PROD.exists()
    assert DEV.exists(), "the development stack is still the one people run locally"


def test_no_service_mounts_the_source_tree(services):
    """
    The development stack bind-mounts ./api and ./web over /app so edits are
    live. In production that replaces the code that was built, tested and
    published with whatever happens to be in the directory the operator ran
    `docker compose` from — and the image tag then describes nothing.
    """
    offenders = []
    for name, svc in services.items():
        for volume in svc.get("volumes") or []:
            source = volume.split(":")[0] if isinstance(volume, str) else volume.get("source", "")
            if source.startswith("."):
                # A read-only config file is not a source mount. Prometheus
                # needs its scrape config and its rules from the repository.
                if isinstance(volume, str) and volume.endswith(":ro"):
                    continue
                offenders.append(f"{name}: {volume}")
    assert not offenders, "these bind-mount host paths read-write:\n  " + "\n  ".join(offenders)


def test_nothing_runs_with_autoreload(services):
    for name, svc in services.items():
        assert "--reload" not in _command(svc), (
            f"{name} runs with --reload, which watches the filesystem and "
            "restarts on change"
        )


def test_the_environment_is_production_everywhere_it_is_set(services):
    """
    `development` is not a label here, it is a switch. It bootstraps the schema
    with create_all instead of migrations, seeds demo patient data, serves /docs
    and /redoc, and turns off every guard in Settings that refuses an unsafe
    value.
    """
    seen = 0
    for name, svc in services.items():
        env = _env(svc)
        if "ENVIRONMENT" not in env:
            continue
        seen += 1
        assert env["ENVIRONMENT"] == "production", f"{name} runs as {env['ENVIRONMENT']!r}"
    assert seen, "no service sets ENVIRONMENT; the API would default to development"


def test_keycloak_is_not_started_in_development_mode(services):
    """
    `start-dev` runs an in-memory H2 database. The realm — every user, client,
    role and the audience mapper the API requires — is discarded when the
    container restarts, and hostname and HTTPS checks are disabled.
    """
    keycloak = services["keycloak"]
    command = _command(keycloak)
    assert "start-dev" not in command, "Keycloak is in development mode"
    assert command.strip().startswith("start")
    env = _env(keycloak)
    assert env.get("KC_DB") == "postgres", "Keycloak has no persistent database"


def test_keycloak_has_its_own_database(services):
    """
    Two Postgres instances, as in the chart. They hold unrelated data and a
    restore of one must not touch the other.
    """
    assert "keycloak-db" in services
    app_db = _env(services["db"])["POSTGRES_DB"]
    kc_db = _env(services["keycloak-db"])["POSTGRES_DB"]
    assert app_db != kc_db


# ── Nothing internal is exposed ──────────────────────────────────────────────

def _published(svc: dict) -> list[str]:
    return [p for p in (svc.get("ports") or []) if isinstance(p, str)]


@pytest.mark.parametrize("name", sorted(DATASTORES))
def test_datastores_are_not_reachable_from_outside(services, name):
    """
    The development stack publishes Postgres on 5432, Redis on 6379 and MinIO on
    9000 so a developer can reach them. On a host with a public IP that is a
    database, a cache and an object store on the internet.
    """
    for port in _published(services[name]):
        assert port.startswith("127.0.0.1:"), (
            f"{name} publishes {port} on every interface"
        )


def test_every_published_port_is_local_or_deliberately_public(services):
    """
    The three the reverse proxy needs are the only ones allowed to bind
    anywhere, and even those are bound to the loopback here — TLS terminates in
    front of them.
    """
    offenders = []
    for name, svc in services.items():
        for port in _published(svc):
            if not port.startswith("127.0.0.1:"):
                offenders.append(f"{name}: {port}")
    assert not offenders, (
        "these bind to every interface, and nothing in this file terminates "
        "TLS:\n  " + "\n  ".join(offenders)
    )


def test_flower_requires_a_password(services):
    """It lists task arguments, which for this system means patient identifiers."""
    auth = _env(services["flower"])["FLOWER_BASIC_AUTH"]
    assert ":?" in auth, "the Flower password has a default; it must be required"


# ── The schema exists before anything queries it ─────────────────────────────

def test_a_migration_service_runs_alembic(services):
    assert "migrate" in services, "the production stack does not migrate the schema"
    assert "alembic upgrade head" in _command(services["migrate"])
    assert services["migrate"].get("restart") == "no", (
        "a one-shot migration with a restart policy loops"
    )


def test_everything_that_touches_the_database_waits_for_the_migration(services):
    """
    An API that starts against an empty database answers 500 from every route
    that reads one. A Celery worker that does is worse: it consumes the task,
    raises, and the task is retried — so the failure is asynchronous and the
    producer saw success.
    """
    for name, svc in _api_image_services(services).items():
        if name == "migrate":
            continue
        depends = svc.get("depends_on") or {}
        assert "migrate" in depends, f"{name} does not wait for the migration"
        assert depends["migrate"]["condition"] == "service_completed_successfully", (
            f"{name} waits for the migration to start, not to succeed"
        )


def test_the_migration_itself_waits_for_the_database(services):
    depends = services["migrate"]["depends_on"]
    assert depends["db"]["condition"] == "service_healthy"


# ── Every queue has a consumer, as in the chart and the dev stack ────────────

@pytest.fixture(scope="module")
def routed_queues() -> set[str]:
    """Read from source rather than by importing: other modules in the suite
    install a MagicMock over `workers.celery_app`, and in a full-suite run the
    import hands back a mock whose task_routes is empty."""
    import ast

    tree = ast.parse(CELERY_APP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "conf"
        ):
            routes = next(kw.value for kw in node.keywords if kw.arg == "task_routes")
            return {r["queue"] for r in ast.literal_eval(routes).values()}
    raise AssertionError("no celery_app.conf.update(...) call found")


def test_the_production_stack_consumes_every_routed_queue(services, routed_queues):
    consumed: set[str] = set()
    for svc in services.values():
        for match in re.finditer(r"-Q\s+([A-Za-z0-9_,-]+)", _command(svc)):
            consumed.update(match.group(1).split(","))
    assert routed_queues <= consumed, (
        "queues task_routes sends work to with no consumer in production: "
        f"{sorted(routed_queues - consumed)}"
    )


def test_the_production_stack_runs_exactly_one_beat(services):
    """Two beats against one schedule enqueue every periodic task twice, which
    for the GDPR retention sweep means two concurrent deletion passes over the
    same rows."""
    beats = [n for n, s in services.items() if " beat " in f" {_command(s)} "]
    assert len(beats) == 1, f"expected one beat service, found {beats}"


def test_workers_are_given_time_to_shut_down(services, routed_queues):
    """
    SIGTERM is a warm shutdown for Celery only if something waits for it. At
    compose's 10-second default a long genomic task is killed on every deploy;
    it is acks_late so it is redelivered, but it restarts from the beginning and
    repeats whatever side effect it had already performed.
    """
    for name, svc in services.items():
        if "-Q " not in _command(svc):
            continue
        grace = svc.get("stop_grace_period")
        assert grace, f"{name} has no stop_grace_period"
        assert int(str(grace).rstrip("s")) > 10, f"{name} grace period {grace} is at the default"


# ── The version being run is knowable ────────────────────────────────────────

def test_no_image_is_pinned_to_a_mutable_tag(services):
    """
    `latest` moves. A container restart can change the running version, and this
    system's output is clinical evidence whose provenance has to be answerable.
    The application images take a required IMAGE_TAG; the third-party ones are
    pinned literally.
    """
    offenders = []
    for name, svc in services.items():
        image = str(svc.get("image", ""))
        if not image:
            continue
        tag = image.rsplit(":", 1)[-1] if ":" in image.rsplit("/", 1)[-1] else ""
        if not tag or tag == "latest":
            offenders.append(f"{name}: {image or '<no image>'}")
    assert not offenders, "unpinned images:\n  " + "\n  ".join(offenders)


def test_the_application_image_tag_has_no_default(services):
    for name, svc in _api_image_services(services).items():
        assert ":?" in str(svc["image"]), (
            f"{name} defaults its tag; a deploy should have to name the version"
        )


# ── The example file lists what the stack requires ───────────────────────────

def test_every_required_variable_appears_in_the_example_env():
    """
    A `${VAR:?}` missing from the example is a variable whose absence is only
    discovered when compose refuses to start, with the operator holding a file
    that was supposed to be complete.
    """
    text = PROD.read_text(encoding="utf-8")
    required = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*):\?", text))
    example = (REPO_ROOT / ".env.production.example").read_text(encoding="utf-8")
    declared = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", example, flags=re.M))
    assert required, "no required variables found; this guard has drifted"
    assert required <= declared, (
        "required by docker-compose.prod.yml and absent from "
        f".env.production.example: {sorted(required - declared)}"
    )


def test_the_production_env_file_cannot_be_committed():
    """
    `.env` does not match `.env.production`, and that file holds the real
    SECRET_KEY and database password.
    """
    patterns = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    assert ".env.*" in patterns
    assert "!.env.production.example" in patterns, (
        "the example is ignored along with the real file and would not be committed"
    )


# ── The environment it supplies is one the API will actually boot in ─────────
#
# The two halves of this file have been checked separately until here: compose
# resolves it, and the guards above read it. Neither asks the question that
# matters on the morning of a deploy — whether `Settings` accepts what comes out.
#
# It is a real question because production is where the validators bite.
# `Settings` refuses the default SECRET_KEY, refuses the literal MinIO password,
# and refuses an empty KEYCLOAK_AUDIENCE; `main.py`'s lifespan then refuses a
# CORS list containing localhost. Every one of those is a container that starts,
# logs a traceback and exits, and the operator sees CrashLoopBackOff.

_INTERPOLATION = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::([?-])([^}]*))?\}")


def _interpolate(value: str, supplied: dict[str, str]) -> str:
    """
    Compose's `${VAR}`, `${VAR:-default}` and `${VAR:?message}`, enough of it to
    resolve this file. Done here rather than by shelling out to `docker compose
    config` so the guard runs in the same places the rest of the suite does.
    """
    def one(m: re.Match) -> str:
        name, op, arg = m.group(1), m.group(2), m.group(3)
        if name in supplied:
            return supplied[name]
        if op == "-":
            return arg
        raise AssertionError(f"required variable {name} has no value")
    return _INTERPOLATION.sub(one, value)


def test_the_api_accepts_the_environment_the_stack_gives_it(services, monkeypatch):
    from config import Settings, is_hardened

    # What an operator would put in .env.production. Real enough to pass the
    # validators: the point is to exercise them, not to defeat them.
    supplied = {
        "IMAGE_TAG": "sha-0000000",
        "PUBLIC_WEB_URL": "https://openoncology.example.org",
        "PUBLIC_API_URL": "https://api.openoncology.example.org",
        "PUBLIC_KEYCLOAK_URL": "https://auth.openoncology.example.org",
        "SECRET_KEY": "a" * 64,
        "DB_PASSWORD": "not-the-default",
        "KC_DB_PASSWORD": "not-the-default",
        "MINIO_ACCESS_KEY": "openoncology",
        "MINIO_SECRET_KEY": "not-the-default",
        "KEYCLOAK_AUDIENCE": "openoncology-api",
        "KEYCLOAK_ADMIN_PASSWORD": "not-the-default",
        "GRAFANA_PASSWORD": "not-the-default",
        "FLOWER_PASSWORD": "not-the-default",
    }

    # Set as environment variables rather than passed as keyword arguments.
    # pydantic-settings JSON-decodes complex fields only on its env source, so
    # CORS_ALLOW_ORIGINS as a kwarg arrives as the string '["https://..."]' and
    # is rejected for not being a list. Going through the environment is also
    # the path the container takes, which is the one worth exercising.
    for key, value in _env(services["api"]).items():
        monkeypatch.setenv(key, _interpolate(value, supplied))

    settings = Settings(_env_file=None)

    assert is_hardened(settings.environment), (
        "the stack does not put the API in a hardened environment, so none of "
        "the validators below actually ran"
    )

    # The two checks main.py makes on startup, before it will serve anything.
    assert settings.secret_key != "dev-secret-key-change-in-production"
    localhost = [
        origin for origin in settings.cors_allow_origins
        if "localhost" in origin or "127.0.0.1" in origin
    ]
    assert not localhost, f"lifespan would raise: CORS allows {localhost}"

    # The issuer the API expects has to be the one Keycloak signs with, which is
    # built from the public hostname and the realm. Getting this wrong is a 401
    # on every request with nothing in the log saying why.
    assert settings.keycloak_issuer == (
        supplied["PUBLIC_KEYCLOAK_URL"] + "/realms/" + settings.keycloak_realm
    )


def test_the_migration_gets_the_same_environment_as_the_api(services):
    """
    alembic/env.py imports `config.settings`, so the migration Job constructs
    Settings too — and in a hardened environment that construction is where
    SECRET_KEY, MINIO_SECRET_KEY and KEYCLOAK_AUDIENCE are enforced. A migration
    running with less than the API gets fails before it opens a connection.
    """
    api = _env(services["api"])
    migrate = _env(services["migrate"])
    missing = set(api) - set(migrate)
    assert not missing, (
        f"the migration is missing what the API is given: {sorted(missing)}"
    )
