import csv
from pathlib import Path

import pytest

from tests.conftest import ROLES

ROWS = list(csv.DictReader((Path(__file__).parent / "permission_matrix.csv").open(encoding="utf-8")))


def _cases() -> list[tuple[str, str, str, str]]:
    return [(row["method"], row["path"], role, row[role]) for row in ROWS for role in ROLES]


@pytest.mark.parametrize(("method", "path", "role", "expected"), _cases())
async def test_matrix(shared_env, method, path, role, expected):
    response = await shared_env.call(role, method, path, json={})
    if expected == "ALLOW":
        assert response.status_code not in (401, 403), f"{role} should reach {method} {path}: {response.text}"
    else:
        assert response.status_code == 403, f"{role} must be refused {method} {path}, got {response.status_code}"
        assert response.json()["code"] == "PERMISSION_DENIED"


async def test_matrix_covers_every_guarded_route(shared_env):
    """Every non-public /api route must have a row in the matrix, so new endpoints cannot skip it."""
    public = {"/api/v1/system/ping", "/api/v1/auth/login", "/api/v1/auth/demo-login", "/api/v1/auth/demo-accounts"}
    authenticated_only = {"/api/v1/auth/logout"}
    routes = set()
    for path, methods in shared_env.app.openapi()["paths"].items():
        if path.startswith("/api") and path not in public | authenticated_only:
            routes |= {(method.upper(), path) for method in methods}
    assert len(routes) >= 15, "the coverage check must be looking at real routes, not an empty list"

    def normalise(path: str) -> str:
        return "/".join("x" if part.startswith("{") else part for part in path.split("/"))

    covered = {(row["method"], row["path"]) for row in ROWS}
    missing = sorted((method, path) for method, path in routes if (method, normalise(path)) not in covered)
    assert not missing, f"Add these to permission_matrix.csv: {missing}"
    stale = sorted(covered - {(method, normalise(path)) for method, path in routes})
    assert not stale, f"These matrix rows no longer match a route: {stale}"
