"""Migration chain gate.

Purpose:
- Enforce the migration-chain properties that CAN be checked today, blocking.

`alembic check` (model-vs-migration drift) is a different, stronger check, and
it currently reports substantial pre-existing drift that needs a dedicated
reconciliation migration rather than a rushed autogenerate. It therefore runs
non-blocking in CI and is tracked as open action 8 in docs/risk_analysis.md.

That left nothing at all gating migrations. This is the part that can gate now:
a divergent chain, a duplicate revision id, or a dangling down_revision breaks
`alembic upgrade head` for every deployment, and none of those need a database
or a resolved drift to detect. Two developers adding a migration on parallel
branches is the common way it happens, and the merge that causes it looks clean.

Usage:
    .venv\\Scripts\\python.exe scripts\\check_migration_chain.py

Exit codes:
    0 -> chain is single-headed, connected and unambiguous
    1 -> chain is broken
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_DIR = os.path.join(ROOT, "api", "alembic", "versions")

_REVISION_RE = re.compile(r"^revision\s*(?::\s*str\s*)?=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN_RE = re.compile(r"^down_revision\s*(?::[^=]+)?=\s*(?:['\"]([^'\"]+)['\"]|None)", re.M)


def _load_revisions() -> list[tuple[str, str, str | None]]:
    """Return (filename, revision, down_revision) for every migration script."""
    revisions: list[tuple[str, str, str | None]] = []
    for name in sorted(os.listdir(VERSIONS_DIR)):
        if not name.endswith(".py") or name.startswith("__"):
            continue
        path = os.path.join(VERSIONS_DIR, name)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()

        rev_match = _REVISION_RE.search(source)
        if not rev_match:
            print(f"FAIL: {name} defines no `revision`")
            sys.exit(1)

        down_match = _DOWN_RE.search(source)
        down = down_match.group(1) if down_match else None
        revisions.append((name, rev_match.group(1), down))
    return revisions


def main() -> int:
    revisions = _load_revisions()
    if not revisions:
        print("FAIL: no migration scripts found")
        return 1

    problems: list[str] = []
    by_revision: dict[str, list[str]] = {}
    for name, rev, _down in revisions:
        by_revision.setdefault(rev, []).append(name)

    for rev, files in by_revision.items():
        if len(files) > 1:
            problems.append(f"duplicate revision id {rev!r} in: {', '.join(files)}")

    known = set(by_revision)
    parents: dict[str, list[str]] = {}
    roots: list[str] = []
    for name, rev, down in revisions:
        if down is None:
            roots.append(rev)
            continue
        if down not in known:
            problems.append(f"{name}: down_revision {down!r} does not exist")
        parents.setdefault(down, []).append(rev)

    # A revision that two others both claim as parent is a fork: `upgrade head`
    # becomes ambiguous and Alembic refuses to run it.
    for parent, children in parents.items():
        if len(children) > 1:
            problems.append(
                f"revision {parent!r} has {len(children)} children ({', '.join(sorted(children))}) "
                "— the chain forks and `alembic upgrade head` will be ambiguous"
            )

    heads = sorted(known - set(parents))
    if len(heads) > 1:
        problems.append(f"{len(heads)} heads: {', '.join(heads)} — expected exactly one")

    if len(roots) > 1:
        problems.append(f"{len(roots)} root revisions: {', '.join(sorted(roots))} — expected exactly one")

    if problems:
        print("Migration chain gate FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"Migration chain OK: {len(revisions)} revisions, "
        f"single root {roots[0]!r} -> single head {heads[0]!r}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
