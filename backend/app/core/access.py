import inspect
from collections.abc import Callable
from typing import Any, get_args

from fastapi import APIRouter, Depends, params

from app.core.authuser import AuthUser
from app.core.errors import forbidden
from app.core.identity import get_current_user
from app.core.permission import Permission

ACCESS_ATTR = "__unio_access__"
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# The only routes that may answer without a signed-in user. Adding a route here is a deliberate,
# reviewable decision, and tests keep their own copy so the two must be changed together.
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/demo-login"),
        ("GET", "/api/v1/auth/demo-accounts"),
        ("GET", "/api/v1/system/ping"),
    }
)


def _mark(dependency: Callable[..., Any], kind: str, permissions: tuple[Permission, ...] = ()) -> None:
    setattr(dependency, ACCESS_ATTR, (kind, permissions))


def _public() -> None:
    return None


async def _authenticated(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    return user


_mark(_public, "public")
_mark(_authenticated, "authenticated")

# Usage: dependencies=[public]   or   user: AuthUser = Depends(authenticated)
public = Depends(_public)
authenticated = _authenticated


def require(*permissions: Permission) -> Callable[..., Any]:
    """The caller must hold at least one of the listed permissions. Layer 1 of RBAC."""
    if not permissions:
        raise ValueError("require() needs at least one permission")

    async def _require(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not user.has_any(permissions):
            raise forbidden()
        return user

    _mark(_require, "permission", permissions)
    return _require


def _dependencies_of(call: Callable[..., Any]) -> list[Callable[..., Any]]:
    try:
        signature = inspect.signature(call)
    except (TypeError, ValueError):
        return []
    found: list[Callable[..., Any]] = []
    for parameter in signature.parameters.values():
        candidates = [parameter.default, *get_args(parameter.annotation)[1:]]
        found.extend(c.dependency for c in candidates if isinstance(c, params.Depends) and c.dependency)
    return found


def declares_access(call: Callable[..., Any]) -> bool:
    """True if the callable, or anything it depends on, is marked public, authenticated or permission."""
    pending, seen = [call], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if hasattr(current, ACCESS_ATTR):
            return True
        pending.extend(_dependencies_of(current))
    return False


class GuardedRouter(APIRouter):
    """A router that refuses to define a route with no declared access rule.

    Fails when the module is imported, so a forgotten guard stops the app from starting
    instead of shipping an open endpoint.
    """

    def add_api_route(self, path: str, endpoint: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        declared = [d.dependency for d in [*self.dependencies, *(kwargs.get("dependencies") or [])] if d.dependency]
        if not (declares_access(endpoint) or any(declares_access(call) for call in declared)):
            raise RuntimeError(
                f"Route {path} ({endpoint.__name__}) declares no access rule. "
                "Use require(...), authenticated or dependencies=[public]."
            )
        super().add_api_route(path, endpoint, *args, **kwargs)


def unguarded_routes(app: Any, prefix: str = "/api") -> list[str]:
    """Audits the published OpenAPI schema, which lists every route whatever router it came from.

    A route is fine if it requires a bearer token, or is on the explicit public allowlist.
    """
    missing: list[str] = []
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith(prefix):
            continue
        for method, operation in operations.items():
            verb = method.upper()
            if verb in HTTP_METHODS and "security" not in operation and (verb, path) not in PUBLIC_ROUTES:
                missing.append(f"{verb} {path}")
    return sorted(missing)


def assert_all_routes_guarded(app: Any) -> None:
    """Called at startup. An open route that is not on the public allowlist fails the boot."""
    missing = unguarded_routes(app)
    if missing:
        raise RuntimeError("Routes that are neither secured nor allowlisted as public: " + ", ".join(missing))
