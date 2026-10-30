from app.users.roles import BUSINESS_AUTHORITY, SYSTEM_ADMIN_ROLE


async def test_system_admin_holds_no_business_authority_by_default(env):
    body = (await env.call("SYSTEM_ADMIN", "GET", "/api/v1/me/bootstrap")).json()
    held = set(body["permissions"]) & {permission.value for permission in BUSINESS_AUTHORITY}
    assert held == set()


async def test_system_admin_cannot_approve_anything(env):
    for path in ("/api/v1/approvals/x/decide", "/api/v1/invoices", "/api/v1/goods-receipts/x/validate"):
        response = await env.call("SYSTEM_ADMIN", "POST", path, json={})
        assert response.status_code == 403, path


async def test_the_role_editor_cannot_give_system_admin_approval_rights(env):
    current = (await env.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/roles")).json()
    admin_role = next(role for role in current if role["key"] == SYSTEM_ADMIN_ROLE)
    response = await env.call(
        "SYSTEM_ADMIN",
        "PUT",
        f"/api/v1/admin/roles/{SYSTEM_ADMIN_ROLE}",
        json={"permissions": [*admin_role["permissions"], "approval.decide.purchase"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SEPARATION_OF_DUTIES"
    after = (await env.call("SYSTEM_ADMIN", "GET", "/api/v1/me/bootstrap")).json()
    assert "approval.decide.purchase" not in after["permissions"]


async def test_the_role_editor_will_not_remove_its_own_access(env):
    response = await env.call(
        "SYSTEM_ADMIN", "PUT", f"/api/v1/admin/roles/{SYSTEM_ADMIN_ROLE}", json={"permissions": ["admin.users"]}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ROLE_LOCKOUT"


async def test_unknown_permissions_are_rejected(env):
    response = await env.call("SYSTEM_ADMIN", "PUT", "/api/v1/admin/roles/TECHNICIAN", json={"permissions": ["made.up"]})
    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_PERMISSION"


async def test_editing_another_role_changes_the_sidebar_and_is_audited(env):
    tech = (await env.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/roles")).json()
    technician = next(role for role in tech if role["key"] == "TECHNICIAN")
    before = (await env.call("TECHNICIAN", "GET", "/api/v1/me/bootstrap")).json()
    assert "tech.parts" in [item["key"] for item in before["navigation"]]

    reduced = [p for p in technician["permissions"] if p != "inventory.read.reserved"]
    response = await env.call("SYSTEM_ADMIN", "PUT", "/api/v1/admin/roles/TECHNICIAN", json={"permissions": reduced})
    assert response.status_code == 200
    assert response.json()["version"] == 1

    after = (await env.call("TECHNICIAN", "GET", "/api/v1/me/bootstrap")).json()
    assert "tech.parts" not in [item["key"] for item in after["navigation"]]

    audit = (await env.call("SYSTEM_ADMIN", "GET", "/api/v1/audit")).json()
    entry = next(item for item in audit["items"] if item["action"] == "role.permissions.update")
    assert entry["entityId"] == "TECHNICIAN"
    assert "inventory.read.reserved" in entry["before"]["permissions"]
    assert "inventory.read.reserved" not in entry["after"]["permissions"]
    assert entry["actorRole"] == "SYSTEM_ADMIN"
