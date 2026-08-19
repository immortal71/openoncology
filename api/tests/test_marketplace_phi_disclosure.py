"""Drug-request detail must not hand a patient's genomic profile to the public.

Found by the S2 sweep in risk_analysis.md section 8.1: walking every mounted
route and asking which ones require no credential, rather than checking that the
guarded ones are guarded.

`GET /api/marketplace/drug-requests/{request_id}` took no authentication and
returned `cancer_type`, `target_gene` and `mutation_profile`, where
mutation_profile is up to 12 HGVS variant notations built by
services/drug_discovery.py. That is a diagnosis plus a genomic profile.

It was not protected by obscurity either. `GET /api/marketplace/drug-requests`
is also unauthenticated and lists every open request id, so the ids needed for
the detail call were being published by the endpoint next to it.

The route sits under `/api/marketplace`, which IS in `_PHI_PREFIXES`, so every
one of those reads was being written to the audit log as a PHI access. The
system recorded the disclosure faithfully while permitting it, which is the
inverse of F11: there the control was missing, here it was present and
reporting on an access that should never have been allowed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

_PHI_FIELDS = ("mutation_profile", "cancer_type", "target_gene")


def _detail_route():
    from main import app

    def walk(routes):
        for route in routes:
            path = getattr(route, "path", None)
            if isinstance(path, str) and path.endswith("/drug-requests/{request_id}"):
                yield route
            inner = getattr(route, "original_router", None) or route
            nested = getattr(inner, "routes", None)
            if nested and inner is not route:
                yield from walk(nested)

    found = list(walk(app.routes))
    assert found, "drug-request detail route is not mounted; the walk is broken"
    return found[0]


def _dependency_names(route) -> set[str]:
    names: set[str] = set()
    dependant = getattr(route, "dependant", None)
    stack = [dependant] if dependant is not None else []
    while stack:
        node = stack.pop()
        call = getattr(node, "call", None)
        name = getattr(call, "__name__", None)
        if name:
            names.add(name)
        stack.extend(getattr(node, "dependencies", []) or [])
    return names


class TestDrugRequestDetailRequiresACredential:
    def test_route_is_mounted(self):
        assert _detail_route() is not None

    def test_detail_route_demands_authentication(self):
        """The regression that matters: no credential, no patient genomics."""
        names = _dependency_names(_detail_route())
        assert "get_current_patient" in names, (
            "GET /api/marketplace/drug-requests/{request_id} returns cancer_type "
            "and mutation_profile and must not be reachable anonymously"
        )


class TestPublicListingCarriesNoPhi:
    """The listing stays public so pharma can find open work. It must stay clean."""

    def test_listing_route_is_public_by_design(self):
        from main import app

        def walk(routes):
            for route in routes:
                path = getattr(route, "path", None)
                if isinstance(path, str) and path.endswith("/drug-requests"):
                    yield route
                inner = getattr(route, "original_router", None) or route
                nested = getattr(inner, "routes", None)
                if nested and inner is not route:
                    yield from walk(nested)

        assert list(walk(app.routes)), "listing route missing"

    def test_listing_source_does_not_emit_a_mutation_profile(self):
        """A future edit that adds genomics to the public listing fails here."""
        source = (_API_DIR / "routes" / "marketplace.py").read_text(encoding="utf-8")
        start = source.index("async def list_drug_requests")
        end = source.index("async def get_drug_request_detail")
        listing = source[start:end]
        assert "mutation_profile" not in listing, (
            "the public listing must not expose a patient's variant profile"
        )


class TestEveryPhiPrefixedRouteIsAuthenticated:
    """Generalise the finding instead of fixing one route and moving on.

    A route under a PHI prefix that anyone can call is the defect class this
    file exists for. Anything intentionally public under those prefixes has to
    be named here with a reason, so the exemption is a decision on the record
    rather than an omission nobody noticed.
    """

    _INTENTIONALLY_PUBLIC = {
        # Stripe redirects the pharma's browser here with no Authorization
        # header, so it cannot require a token. Hardened in F13 to return the
        # same shape for every id and disclose only whether onboarding finished.
        "/api/stripe/connect/return/{pharma_id}",
        # Public listing of open synthesis work. Asserted PHI-free above.
        "/api/marketplace/drug-requests",
        # Public directory of pharma companies and their application form.
        # Company records, not patient records.
        "/api/marketplace/pharma",
        "/api/marketplace/nearby-pharmacies",
        "/api/pharma/",
        "/api/pharma/apply",
        "/api/pharma/{company_id}",
        # A campaign page the patient chose to publish. The query filters on
        # is_public and is_active, so only campaigns deliberately made public
        # are served: a consented disclosure, not an access-control gap.
        "/api/crowdfund/{slug}",
        # Donation intent. Returns a Stripe client_secret and no patient data,
        # and must stay open so anyone can give without an account.
        "/api/crowdfund/{slug}/donate",
    }

    def test_no_unlisted_phi_route_is_anonymous(self):
        from main import app
        from middleware.audit import _PHI_PREFIXES

        guards = {
            "get_current_patient",
            "_require_admin",
            "_require_oncologist",
            "get_current_user",
        }
        offenders = []

        def walk(routes):
            for route in routes:
                path = getattr(route, "path", None)
                methods = getattr(route, "methods", None)
                if isinstance(path, str) and methods:
                    if any(path.startswith(p) for p in _PHI_PREFIXES):
                        if path not in self._INTENTIONALLY_PUBLIC:
                            if not (_dependency_names(route) & guards):
                                offenders.append(path)
                inner = getattr(route, "original_router", None) or route
                nested = getattr(inner, "routes", None)
                if nested and inner is not route:
                    walk(nested)

        walk(app.routes)
        assert not sorted(set(offenders)), (
            "PHI-prefixed routes reachable with no credential: "
            f"{sorted(set(offenders))}"
        )
