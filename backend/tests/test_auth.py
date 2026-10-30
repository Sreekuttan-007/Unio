from tests.conftest import DEMO_PASSWORD, open_env


async def test_password_login_returns_a_working_token(env):
    response = await env.client.post(
        "/api/v1/auth/login", json={"email": "student@unio.demo", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]
    me = await env.client.get("/api/v1/me/bootstrap", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"]["key"] == "STUDENT"


async def test_wrong_password_and_unknown_email_give_the_same_error(env):
    wrong = await env.client.post("/api/v1/auth/login", json={"email": "student@unio.demo", "password": "nope"})
    unknown = await env.client.post("/api/v1/auth/login", json={"email": "ghost@unio.demo", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["message"] == unknown.json()["message"]


async def test_repeated_failures_are_rate_limited():
    async with open_env(login_max_failures=3) as env:
        body = {"email": "student@unio.demo", "password": "nope"}
        for _ in range(3):
            assert (await env.client.post("/api/v1/auth/login", json=body)).status_code == 401
        blocked = await env.client.post("/api/v1/auth/login", json=body)
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "TOO_MANY_ATTEMPTS"
        # even the correct password is refused while the window is full
        good = await env.client.post(
            "/api/v1/auth/login", json={"email": "student@unio.demo", "password": DEMO_PASSWORD}
        )
        assert good.status_code == 429


async def test_logout_revokes_the_token(env):
    headers = await env.headers("TECHNICIAN")
    assert (await env.client.get("/api/v1/me/bootstrap", headers=headers)).status_code == 200
    assert (await env.client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    after = await env.client.get("/api/v1/me/bootstrap", headers=headers)
    assert after.status_code == 401
    # a second logout with the dead token is simply unauthenticated, never a crash
    assert (await env.client.post("/api/v1/auth/logout", headers=headers)).status_code == 401


async def test_a_forged_or_tampered_token_is_rejected(env):
    token = await env.token("STUDENT")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    for bad in (tampered, "not-a-jwt", ""):
        response = await env.client.get("/api/v1/me/bootstrap", headers={"Authorization": f"Bearer {bad}"})
        assert response.status_code == 401


async def test_deactivating_a_user_takes_effect_immediately(env):
    tech_headers = await env.headers("TECHNICIAN")
    assert (await env.client.get("/api/v1/me/bootstrap", headers=tech_headers)).status_code == 200
    response = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/users/U-TECH/status", json={"status": "INACTIVE"})
    assert response.status_code == 200
    assert (await env.client.get("/api/v1/me/bootstrap", headers=tech_headers)).status_code == 401
    login = await env.client.post("/api/v1/auth/login", json={"email": "tech@unio.demo", "password": DEMO_PASSWORD})
    assert login.status_code == 401


async def test_changing_a_role_takes_effect_immediately(env):
    tech_headers = await env.headers("TECHNICIAN")
    before = await env.client.get("/api/v1/me/bootstrap", headers=tech_headers)
    assert before.json()["role"]["key"] == "TECHNICIAN"
    changed = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/users/U-TECH/role", json={"roleKey": "STUDENT"})
    assert changed.status_code == 200
    after = await env.client.get("/api/v1/me/bootstrap", headers=tech_headers)
    assert after.json()["role"]["key"] == "STUDENT"
    assert (await env.client.get("/api/v1/work-orders", headers=tech_headers)).status_code == 403


async def test_an_administrator_cannot_lock_themselves_out(env):
    own_status = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/users/U-SYSADMIN/status", json={"status": "INACTIVE"})
    own_role = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/users/U-SYSADMIN/role", json={"roleKey": "STUDENT"})
    assert own_status.status_code == own_role.status_code == 422
    assert own_status.json()["code"] == own_role.json()["code"] == "SELF_MODIFICATION"


async def test_demo_mode_off_means_no_demo_accounts_and_no_one_tap_login():
    async with open_env(demo_mode_enabled=False) as env:
        response = await env.client.post("/api/v1/auth/demo-login", json={"email": "student@unio.demo"})
        assert response.status_code == 404
        assert await env.db["users"].count_documents({}) == 0
        assert await env.db["roles_permissions"].count_documents({}) == 7


async def test_demo_accounts_lists_one_chip_per_role(env):
    response = await env.client.get("/api/v1/auth/demo-accounts")
    assert response.status_code == 200
    assert sorted(account["roleKey"] for account in response.json()) == sorted(
        ["STUDENT", "FACULTY", "DEPARTMENT_MANAGER", "FACILITIES_ADMIN", "PROCUREMENT_APPROVER", "TECHNICIAN", "SYSTEM_ADMIN"]
    )
    assert all("password" not in account and "passwordHash" not in account for account in response.json())


async def test_admin_creates_a_user_who_can_sign_in(env):
    created = await env.call(
        "SYSTEM_ADMIN",
        "POST",
        "/api/v1/admin/users",
        json={"name": "New Tech", "email": "New.Tech@unio.demo", "password": "a-long-password", "roleKey": "TECHNICIAN"},
    )
    assert created.status_code == 201
    assert created.json()["email"] == "new.tech@unio.demo"
    assert "passwordHash" not in created.text
    login = await env.client.post(
        "/api/v1/auth/login", json={"email": "new.tech@unio.demo", "password": "a-long-password"}
    )
    assert login.status_code == 200
    duplicate = await env.call(
        "SYSTEM_ADMIN",
        "POST",
        "/api/v1/admin/users",
        json={"name": "Dup", "email": "new.tech@unio.demo", "password": "a-long-password", "roleKey": "TECHNICIAN"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "EMAIL_TAKEN"
    unknown_role = await env.call(
        "SYSTEM_ADMIN",
        "POST",
        "/api/v1/admin/users",
        json={"name": "X", "email": "x@unio.demo", "password": "a-long-password", "roleKey": "WIZARD"},
    )
    assert unknown_role.status_code == 422
    assert unknown_role.json()["code"] == "UNKNOWN_ROLE"
