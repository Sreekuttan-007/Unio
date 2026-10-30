from datetime import UTC, datetime

from app.audit.service import AuditDomain
from app.core.actions import ActionResolver, ActionRule
from app.core.authuser import AuthUser
from app.core.permission import Permission
from app.users.actions import UserActionResolver


def actor(permissions: set[Permission], user_id: str = "U-ADMIN") -> AuthUser:
    return AuthUser(
        id=user_id, name="A", email="a@unio.demo", role_key="X", campus_id="C", department_id=None,
        managed_department_ids=(), approval_limit_paise=0, permissions=frozenset(permissions), scopes={},
        token_id="j", token_expires_at=datetime.now(UTC),
    )


ACTIVE = {"_id": "U-2", "status": "ACTIVE"}


def test_actions_the_caller_may_not_use_are_not_even_mentioned():
    result = UserActionResolver().resolve(ACTIVE, actor(set()))
    assert result.available_actions == [] and result.unavailable_actions == []


def test_permitted_actions_are_listed_for_an_active_user():
    result = UserActionResolver().resolve(ACTIVE, actor({Permission.ADMIN_USERS}))
    assert [a.key for a in result.available_actions] == ["user.deactivate", "user.changeRole"]
    assert [a.key for a in result.unavailable_actions] == ["user.activate"]
    assert result.unavailable_actions[0].reason == "This account is already active."


def test_blocked_actions_say_why():
    own = {"_id": "U-ADMIN", "status": "ACTIVE"}
    result = UserActionResolver().resolve(own, actor({Permission.ADMIN_USERS}))
    reasons = {a.key: a.reason for a in result.unavailable_actions}
    assert reasons["user.deactivate"] == "You cannot deactivate your own account."
    assert reasons["user.changeRole"] == "You cannot change your own role."


def test_state_changes_which_actions_are_offered():
    inactive = {"_id": "U-2", "status": "INACTIVE"}
    result = UserActionResolver().resolve(inactive, actor({Permission.ADMIN_USERS}))
    assert [a.key for a in result.available_actions] == ["user.activate", "user.changeRole"]


def test_a_custom_resolver_follows_the_same_rules():
    class Resolver(ActionResolver[dict]):
        rules = (ActionRule("x.go", "Go", (Permission.ADMIN_SEED,), lambda entity, user: None),)

    assert Resolver().resolve({}, actor({Permission.ADMIN_SEED})).available_actions[0].key == "x.go"
    assert Resolver().resolve({}, actor(set())).available_actions == []


async def test_the_admin_user_list_carries_server_driven_actions(env):
    response = await env.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/users?size=50")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    mine = items["U-SYSADMIN"]
    assert "user.deactivate" not in [a["key"] for a in mine["availableActions"]]
    assert "user.deactivate" in [a["key"] for a in mine["unavailableActions"]]
    other = items["U-TECH"]
    assert "user.deactivate" in [a["key"] for a in other["availableActions"]]
    assert all("passwordHash" not in item for item in items.values())


async def _write_audit(env, domain: AuditDomain, action: str) -> None:
    await env.services.audit.record(
        actor_id="U-X", actor_role="X", action=action, domain=domain, entity_type="THING", entity_id="T1"
    )


async def test_each_audience_sees_only_its_own_audit_domain(env):
    await _write_audit(env, AuditDomain.OPERATIONS, "ops.event")
    await _write_audit(env, AuditDomain.PROCUREMENT, "proc.event")
    await _write_audit(env, AuditDomain.SYSTEM, "sys.event")

    def actions(response) -> set[str]:
        return {item["action"] for item in response.json()["items"]}

    facilities = await env.call("FACILITIES_ADMIN", "GET", "/api/v1/audit")
    procurement = await env.call("PROCUREMENT_APPROVER", "GET", "/api/v1/audit")
    system = await env.call("SYSTEM_ADMIN", "GET", "/api/v1/audit?size=100")
    assert actions(facilities) == {"ops.event"}
    assert actions(procurement) == {"proc.event"}
    assert {"ops.event", "proc.event", "sys.event"} <= actions(system)
    assert (await env.call("TECHNICIAN", "GET", "/api/v1/audit")).status_code == 403
    assert (await env.call("STUDENT", "GET", "/api/v1/audit")).status_code == 403


async def test_audit_entries_are_newest_first_and_paged(env):
    for number in range(5):
        await _write_audit(env, AuditDomain.OPERATIONS, f"ops.{number}")
    page = await env.call("FACILITIES_ADMIN", "GET", "/api/v1/audit?page=0&size=2")
    body = page.json()
    assert body["total"] == 5 and body["size"] == 2 and len(body["items"]) == 2
    assert [item["action"] for item in body["items"]] == ["ops.4", "ops.3"]
    assert (await env.call("FACILITIES_ADMIN", "GET", "/api/v1/audit?size=0")).status_code == 400
    assert (await env.call("FACILITIES_ADMIN", "GET", "/api/v1/audit?size=101")).status_code == 400
