import asyncio

NEW_USER = {"name": "Retry Tester", "email": "retry@unio.demo", "password": "a-long-password", "roleKey": "TECHNICIAN"}


async def _users_named(env, email):
    return await env.db["users"].count_documents({"email": email})


async def test_a_retried_write_returns_the_first_result_and_runs_once(env):
    headers = {"Idempotency-Key": "create-retry-0001"}
    first = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER)
    second = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER)
    assert first.status_code == second.status_code == 201
    assert second.headers.get("Idempotent-Replay") == "true"
    assert "Idempotent-Replay" not in first.headers
    assert first.json() == second.json()
    assert await _users_named(env, "retry@unio.demo") == 1
    created = await env.db["audit_logs"].count_documents({"action": "user.create"})
    assert created == 1, "the replay must not run the handler or audit twice"


async def test_without_a_key_a_repeat_is_judged_on_its_merits(env):
    first = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", json=NEW_USER)
    second = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", json=NEW_USER)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "EMAIL_TAKEN"


async def test_reusing_a_key_for_a_different_request_is_refused(env):
    headers = {"Idempotency-Key": "shared-key-000001"}
    first = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER)
    other = await env.call(
        "SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json={**NEW_USER, "email": "other@unio.demo"}
    )
    assert first.status_code == 201
    assert other.status_code == 409
    assert other.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await _users_named(env, "other@unio.demo") == 0


async def test_a_failed_request_does_not_poison_its_key(env):
    headers = {"Idempotency-Key": "fix-and-retry-001"}
    bad = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json={**NEW_USER, "password": "x"})
    assert bad.status_code == 400
    good = await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER)
    assert good.status_code == 201
    assert "Idempotent-Replay" not in good.headers


async def test_simultaneous_duplicates_create_exactly_one_record(env):
    headers = {"Idempotency-Key": "double-tap-000001"}
    responses = await asyncio.gather(
        *[env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER) for _ in range(6)]
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses.count(201) >= 1
    assert set(statuses) <= {201, 409}
    assert await _users_named(env, "retry@unio.demo") == 1


async def test_keys_do_not_leak_between_users(env):
    key = {"Idempotency-Key": "same-key-for-all-1"}
    mine = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/me/profile", headers=key, json={"name": "Sam One"})
    other = await env.call("STUDENT", "PATCH", "/api/v1/me/profile", headers=key, json={"name": "Asha Two"})
    assert mine.status_code == other.status_code == 200
    assert other.json()["user"]["name"] == "Asha Two"
    assert "Idempotent-Replay" not in other.headers


async def test_an_unsigned_request_never_reads_a_cached_response(env):
    headers = {"Idempotency-Key": "anon-attempt-0001"}
    await env.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers=headers, json=NEW_USER)
    anonymous = await env.client.post("/api/v1/admin/users", headers=headers, json=NEW_USER)
    assert anonymous.status_code == 401
    assert "Idempotent-Replay" not in anonymous.headers


async def test_an_oversized_key_is_rejected(env):
    response = await env.call(
        "SYSTEM_ADMIN", "POST", "/api/v1/admin/users", headers={"Idempotency-Key": "k" * 200}, json=NEW_USER
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IDEMPOTENCY_KEY"


async def test_reads_ignore_the_key(env):
    response = await env.call("STUDENT", "GET", "/api/v1/me/bootstrap", headers={"Idempotency-Key": "read-with-key-001"})
    assert response.status_code == 200
    assert await env.db["idempotency_keys"].count_documents({}) == 0
