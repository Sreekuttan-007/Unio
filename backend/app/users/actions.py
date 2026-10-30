from typing import Any

from app.core.actions import ActionResolver, ActionRule
from app.core.authuser import AuthUser
from app.core.permission import Permission


def _deactivate_blocked(user: dict[str, Any], actor: AuthUser) -> str | None:
    if user["_id"] == actor.id:
        return "You cannot deactivate your own account."
    return None if user["status"] == "ACTIVE" else "This account is already inactive."


def _activate_blocked(user: dict[str, Any], actor: AuthUser) -> str | None:
    return "This account is already active." if user["status"] == "ACTIVE" else None


def _change_role_blocked(user: dict[str, Any], actor: AuthUser) -> str | None:
    return "You cannot change your own role." if user["_id"] == actor.id else None


class UserActionResolver(ActionResolver[dict[str, Any]]):
    rules = (
        ActionRule("user.deactivate", "Deactivate", (Permission.ADMIN_USERS,), _deactivate_blocked),
        ActionRule("user.activate", "Activate", (Permission.ADMIN_USERS,), _activate_blocked),
        ActionRule("user.changeRole", "Change role", (Permission.ADMIN_USERS,), _change_role_blocked),
    )
