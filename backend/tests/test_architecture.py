import pytest
from fastapi import APIRouter, Depends, FastAPI

from app.core.access import GuardedRouter, assert_all_routes_guarded, authenticated, public, unguarded_routes
from app.main import create_app
from tests.conftest import make_settings

# A separate copy of the public allowlist. Adding a public route means changing both lists.
EXPECTED_PUBLIC = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/demo-login"),
    ("GET", "/api/v1/auth/demo-accounts"),
    ("GET", "/api/v1/system/ping"),
}


def _api_operations(app) -> set[tuple[str, str]]:
    operations = set()
    for path, methods in app.openapi()["paths"].items():
        if path.startswith("/api"):
            operations |= {(method.upper(), path) for method in methods}
    return operations


def test_the_real_app_exposes_routes_and_every_one_is_secured_or_public():
    app = create_app(make_settings(), db=object())
    operations = _api_operations(app)
    assert len(operations) > 20, "the audit must be looking at real routes, not an empty list"
    assert unguarded_routes(app) == []


def test_exactly_the_expected_routes_are_public():
    app = create_app(make_settings(), db=object())
    secured = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api")
        for method, operation in methods.items()
        if "security" in operation
    }
    assert _api_operations(app) - secured == EXPECTED_PUBLIC


def test_a_route_with_no_access_rule_cannot_even_be_defined():
    router = GuardedRouter()
    with pytest.raises(RuntimeError, match="declares no access rule"):

        @router.get("/api/v1/forgotten")
        async def forgotten() -> dict:
            return {}


def test_access_declared_on_the_router_or_the_route_is_accepted():
    GuardedRouter(dependencies=[public]).get("/api/v1/a")(lambda: {})  # router-level
    router = GuardedRouter()

    @router.get("/api/v1/b", dependencies=[public])
    async def route_level() -> dict:
        return {}

    @router.get("/api/v1/c")
    async def parameter_level(user=Depends(authenticated)) -> dict:
        return {}


def test_the_boot_audit_catches_a_route_that_bypassed_the_guarded_router():
    app = FastAPI()
    plain = APIRouter()

    @plain.get("/api/v1/sneaky")
    async def sneaky() -> dict:
        return {}

    app.include_router(plain)
    assert unguarded_routes(app) == ["GET /api/v1/sneaky"]
    with pytest.raises(RuntimeError, match="sneaky"):
        assert_all_routes_guarded(app)


def test_marking_a_route_public_is_not_enough_it_must_also_be_allowlisted():
    app = FastAPI()
    router = GuardedRouter()

    @router.get("/api/v1/leaky", dependencies=[public])
    async def leaky() -> dict:
        return {}

    app.include_router(router)
    assert unguarded_routes(app) == ["GET /api/v1/leaky"]


def test_demo_routes_are_absent_when_demo_mode_is_off():
    app = create_app(make_settings(demo_mode_enabled=False), db=object())
    paths = {path for _, path in _api_operations(app)}
    assert "/api/v1/auth/demo-login" not in paths
    assert "/api/v1/auth/demo-accounts" not in paths
    assert "/api/v1/auth/login" in paths
