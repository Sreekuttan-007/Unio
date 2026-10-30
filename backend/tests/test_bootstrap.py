import pytest

from app.users.navigation import CATALOG
from tests.conftest import ROLES

WORKSPACE_PREFIX = {
    "STUDENT": ("student", "student."),
    "FACULTY": ("faculty", "faculty."),
    "DEPARTMENT_MANAGER": ("department", "dept."),
    "FACILITIES_ADMIN": ("facilities", "fac."),
    "PROCUREMENT_APPROVER": ("procurement", "proc."),
    "TECHNICIAN": ("technician", "tech."),
    "SYSTEM_ADMIN": ("system", "sys."),
}


async def _bootstrap(env, role):
    response = await env.call(role, "GET", "/api/v1/me/bootstrap")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_gets_only_its_own_workspace(shared_env, role):
    workspace, prefix = WORKSPACE_PREFIX[role]
    body = await _bootstrap(shared_env, role)
    assert body["role"]["workspace"] == workspace
    assert body["navigation"], "every role must have a sidebar"
    for item in body["navigation"]:
        assert item["key"].startswith(prefix), f"{role} was shown {item['key']}"
        assert item["path"].startswith(f"/w/{workspace}/")
    assert body["landingPath"] == body["navigation"][0]["path"]


@pytest.mark.parametrize("role", ROLES)
async def test_the_role_holds_every_permission_its_own_sidebar_needs(shared_env, role):
    """If roles.json drops a permission, a nav item silently vanishes. This catches it."""
    workspace, _ = WORKSPACE_PREFIX[role]
    body = await _bootstrap(shared_env, role)
    assert [item["key"] for item in body["navigation"]] == [entry.key for entry in CATALOG[workspace]]


async def test_roles_never_share_a_navigation_key(shared_env):
    seen: dict[str, str] = {}
    for role in ROLES:
        for item in (await _bootstrap(shared_env, role))["navigation"]:
            assert item["key"] not in seen, f"{item['key']} appears for {seen[item['key']]} and {role}"
            seen[item["key"]] = role


async def test_a_technician_never_sees_procurement_or_admin_screens(shared_env):
    keys = [item["key"] for item in (await _bootstrap(shared_env, "TECHNICIAN"))["navigation"]]
    assert keys == ["tech.tasks", "tech.parts", "tech.availability", "tech.history", "tech.map"]


async def test_each_role_has_its_own_accent(shared_env):
    accents = [(await _bootstrap(shared_env, role))["theme"]["accent"] for role in ROLES]
    assert len(set(accents)) == len(ROLES)


async def test_bootstrap_describes_the_caller(shared_env):
    body = await _bootstrap(shared_env, "TECHNICIAN")
    assert body["user"]["email"] == "tech@unio.demo"
    assert body["user"]["avatarInitials"] == "RK"
    assert body["department"]["id"] == "D-ELEC"
    assert body["scopes"]["WORK_ORDER"] == "ASSIGNED"
    assert body["permissions"] == sorted(body["permissions"])
    assert "workorder.execute" in body["permissions"]
    assert "approval.decide.purchase" not in body["permissions"]
    assert body["featureFlags"]["mlTriage"] is False


async def test_a_student_payload_has_no_staff_permissions(shared_env):
    body = await _bootstrap(shared_env, "STUDENT")
    assert not [p for p in body["permissions"] if p.startswith(("workorder", "inventory", "approval", "admin"))]


async def test_updating_the_profile_renames_and_audits(env):
    response = await env.call("STUDENT", "PATCH", "/api/v1/me/profile", json={"name": "  Asha K Nair "})
    assert response.status_code == 200
    assert response.json()["user"]["name"] == "Asha K Nair"
    assert response.json()["user"]["avatarInitials"] == "AK"
    again = await _bootstrap(env, "STUDENT")
    assert again["user"]["name"] == "Asha K Nair"
