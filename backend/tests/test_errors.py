import re

ERROR_KEYS = {"code", "message", "details", "correlationId"}


async def test_a_missing_token_gets_the_standard_error_shape(env):
    response = await env.client.get("/api/v1/me/bootstrap")
    assert response.status_code == 401
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "UNAUTHENTICATED"
    assert body["correlationId"] == response.headers["X-Correlation-Id"]


async def test_a_permission_failure_uses_the_same_shape(env):
    response = await env.call("STUDENT", "GET", "/api/v1/admin/users")
    assert response.status_code == 403
    assert set(response.json()) == ERROR_KEYS
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_validation_errors_are_400_and_name_the_fields(env):
    response = await env.client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    fields = {item["field"] for item in body["details"]["fields"]}
    assert {"email", "password"} <= fields


async def test_malformed_json_is_a_400_not_a_500(env):
    response = await env.client.post(
        "/api/v1/auth/login", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_FAILED"


async def test_unknown_routes_and_methods_use_the_shape(env):
    missing = await env.client.get("/api/v1/nope")
    wrong_method = await env.client.delete("/api/v1/system/ping")
    assert missing.status_code == 404 and missing.json()["code"] == "NOT_FOUND"
    assert wrong_method.status_code == 405 and wrong_method.json()["code"] == "METHOD_NOT_ALLOWED"
    assert set(missing.json()) == ERROR_KEYS


async def test_unbuilt_endpoints_say_which_phase_delivers_them(env):
    response = await env.call("FACILITIES_ADMIN", "POST", "/api/v1/simulations", json={})
    assert response.status_code == 501
    assert response.json()["code"] == "NOT_BUILT_YET"
    assert "Phase 9" in response.json()["message"]


async def test_a_valid_correlation_id_is_echoed_and_a_bad_one_replaced(env):
    good = await env.client.get("/api/v1/system/ping", headers={"X-Correlation-Id": "trace-1234-abcd"})
    assert good.headers["X-Correlation-Id"] == "trace-1234-abcd"
    bad = await env.client.get("/api/v1/system/ping", headers={"X-Correlation-Id": "<script>alert(1)</script>"})
    assert re.fullmatch(r"[0-9a-f-]{36}", bad.headers["X-Correlation-Id"])


async def test_api_responses_carry_security_headers(env):
    response = await env.client.get("/api/v1/system/ping")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


async def test_ping_is_public_and_reports_the_database(env):
    response = await env.client.get("/api/v1/system/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "unio-backend" and body["database"] == "UP"
    assert "serverTime" in body


async def test_responses_are_camel_case_on_the_wire(env):
    response = await env.call("TECHNICIAN", "GET", "/api/v1/me/bootstrap")
    body = response.json()
    assert "landingPath" in body and "featureFlags" in body
    assert "landing_path" not in body


async def test_cors_allows_the_configured_origin_only(env):
    allowed = await env.client.options(
        "/api/v1/me/bootstrap",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    denied = await env.client.options(
        "/api/v1/me/bootstrap",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
