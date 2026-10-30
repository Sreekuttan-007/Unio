"""Phase 11: SLA escalation, notifications, signed webhooks and analytics with known answers."""

import json
from datetime import timedelta

import pytest_asyncio

from app.core.clock import ensure_utc, utcnow
from app.notify.service import INTERNAL_RECEIVER, sign
from app.sla.service import evaluate
from tests.conftest import open_env
from tests.test_incidents import report

NOW = utcnow().replace(microsecond=0)


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        yield opened


def instance(**extra):
    return {"startedAt": NOW, "resolutionMinutes": 100, "pauses": [], "pausedMinutes": 0, "atRiskPercent": 75, **extra}


# ---- SLA arithmetic --------------------------------------------------------------------------------------------


def test_sla_boundaries():
    assert evaluate(instance(), NOW + timedelta(minutes=74))["state"] == "ON_TRACK"
    assert evaluate(instance(), NOW + timedelta(minutes=75))["state"] == "AT_RISK"
    assert evaluate(instance(), NOW + timedelta(minutes=99))["state"] == "AT_RISK"
    assert evaluate(instance(), NOW + timedelta(minutes=100))["state"] == "BREACHED"
    assert evaluate(instance(resolvedAt=NOW + timedelta(minutes=100)), NOW + timedelta(days=1))["state"] == "MET"
    assert evaluate(instance(resolvedAt=NOW + timedelta(minutes=101)), NOW + timedelta(days=1))["state"] == "BREACHED"


def test_paused_time_does_not_count():
    paused = instance(pausedMinutes=30, pauses=[{"from": NOW, "to": NOW + timedelta(minutes=30)}])
    at = evaluate(paused, NOW + timedelta(minutes=100))
    assert at["state"] == "ON_TRACK" and at["percentElapsed"] == 70
    assert at["dueAt"] == (NOW + timedelta(minutes=130)).isoformat()
    running = instance(pauses=[{"from": NOW + timedelta(minutes=10), "to": None, "reason": "Waiting for parts"}])
    assert evaluate(running, NOW + timedelta(hours=10))["state"] == "PAUSED"


# ---- escalation and notifications --------------------------------------------------------------------------------


async def test_an_overdue_incident_escalates_once_to_the_right_people(world):
    incident_id = (await report(world, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()["incidentId"]
    board = world.services.sla_board
    later = utcnow() + timedelta(hours=5)  # past 100% of the 3 hour P1 electrical target
    fired = await board.sweep(later)
    assert len(fired) == 2 and all(key.endswith((":1", ":2")) for key in fired)
    assert await board.sweep(later) == [] and await board.sweep(later + timedelta(hours=1)) == []
    assert await world.db["outbox_events"].count_documents({"eventType": "sla.escalated"}) == 2
    await world.services.outbox.dispatch_due()
    told = {row["userId"] async for row in world.db["notifications"].find({"eventType": "sla.escalated"})}
    assert "U-FACILITIES" in told
    incident = await world.db["incidents"].find_one({"_id": incident_id})
    managers = {row["_id"] async for row in world.db["users"].find({"roleKey": "DEPARTMENT_MANAGER", "managedDepartmentIds": incident["departmentId"]})}
    assert managers <= told
    assert not told & {"U-STUDENT", "U-TECH", "U-PROCURE", "U-SYSADMIN"}  # nobody outside the ladder
    other_managers = {row["_id"] async for row in world.db["users"].find({"roleKey": "DEPARTMENT_MANAGER"})} - managers
    assert not told & other_managers


async def test_a_paused_clock_does_not_escalate(world):
    incident_id = (await report(world, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()["incidentId"]
    await world.services.sla.pause(incident_id, "Waiting for parts")
    assert await world.services.sla_board.sweep(utcnow() + timedelta(hours=5)) == []


async def test_a_redelivered_event_notifies_each_person_once(world):
    await world.services.outbox.enqueue("approval.submitted", {"approvalId": "APR-1", "recipientIds": ["U-PROCURE"]})
    event = await world.db["outbox_events"].find_one({"eventType": "approval.submitted"})
    await world.services.notifications.handle(event)
    await world.services.notifications.handle(event)
    rows = await world.db["notifications"].find({"userId": "U-PROCURE"}).to_list(length=10)
    assert len(rows) == 1 and rows[0]["title"] == "Request waiting for you" and rows[0]["body"] == "APR-1 needs a decision."


async def test_the_notification_centre_lists_and_marks_read(world):
    await world.services.outbox.enqueue("workorder.assigned", {"workOrderId": "WO-9", "recipientIds": ["U-TECH"]})
    await world.services.outbox.dispatch_due()
    body = (await world.call("TECHNICIAN", "GET", "/api/v1/notifications")).json()
    assert body["unread"] == 1 and body["items"][0]["title"] == "New task assigned"
    assert (await world.call("TECHNICIAN", "GET", "/api/v1/me/badges")).json()["notifications.unread"] == 1
    assert (await world.call("STUDENT", "GET", "/api/v1/notifications")).json()["items"] == []  # only your own
    assert (await world.call("TECHNICIAN", "POST", "/api/v1/notifications/read", json={})).json()["marked"] == 1
    assert (await world.call("TECHNICIAN", "GET", "/api/v1/notifications")).json()["unread"] == 0


# ---- webhooks -----------------------------------------------------------------------------------------------------


async def test_webhooks_are_signed_logged_and_replays_are_ignored(world):
    hook = await world.db["webhooks"].find_one({"url": INTERNAL_RECEIVER})
    tested = await world.call("SYSTEM_ADMIN", "POST", f"/api/v1/admin/webhooks/{hook['_id']}/test")
    assert tested.status_code == 200 and tested.json()["status"] == 200 and tested.json()["signed"]
    await world.services.outbox.enqueue("workorder.blocked", {"workOrderId": "WO-7", "reason": "ACCESS"})
    await world.services.outbox.dispatch_due()
    delivered = await world.db["webhook_deliveries"].find_one({"eventType": "workorder.blocked"})
    assert delivered["status"] == 200
    event = await world.db["outbox_events"].find_one({"eventType": "workorder.blocked"})
    again = await world.services.webhooks.deliver(hook, str(event["_id"]), "workorder.blocked", event["payload"])
    assert again["_id"] == delivered["_id"]  # the same event is never sent twice
    assert await world.db["webhook_received"].count_documents({"type": "workorder.blocked"}) == 1


async def test_the_receiver_refuses_a_bad_signature():
    async with open_env() as env:
        await env.services.webhooks.ensure_default("CAMPUS-1")
        body = json.dumps({"id": "e1", "type": "x", "data": {}}).encode()
        assert await env.services.webhooks._receive_internally(body, "sha256=forged") == 401
        hook = await env.db["webhooks"].find_one({})
        assert await env.services.webhooks._receive_internally(body, sign(hook["secret"], body)) == 200


async def test_managing_webhooks_create_update_and_a_disabled_hook_gets_nothing(world):
    created = await world.call("SYSTEM_ADMIN", "POST", "/api/v1/admin/webhooks", json={"url": "https://example.test/hook", "events": ["workorder.*"]})
    assert created.status_code == 201, created.text
    webhook_id = created.json()["id"]
    assert created.json()["enabled"] is True

    disabled = await world.call("SYSTEM_ADMIN", "PATCH", f"/api/v1/admin/webhooks/{webhook_id}", json={"enabled": False})
    assert disabled.status_code == 200 and disabled.json()["enabled"] is False

    await world.services.outbox.enqueue("workorder.blocked", {"workOrderId": "WO-7", "reason": "ACCESS"})
    await world.services.outbox.dispatch_due()
    assert await world.db["webhook_deliveries"].count_documents({"webhookId": webhook_id}) == 0  # disabled gets nothing

    enabled = await world.call("SYSTEM_ADMIN", "PATCH", f"/api/v1/admin/webhooks/{webhook_id}", json={"enabled": True})
    assert enabled.status_code == 200 and enabled.json()["enabled"] is True
    await world.services.outbox.enqueue("workorder.blocked", {"workOrderId": "WO-8", "reason": "ACCESS"})
    await world.services.outbox.dispatch_due()
    assert await world.db["webhook_deliveries"].count_documents({"webhookId": webhook_id}) == 1

    only_student_lists = await world.call("STUDENT", "GET", "/api/v1/admin/webhooks")
    assert only_student_lists.status_code == 403


async def test_replaying_a_delivery_resends_it_but_changes_nothing(world):
    hook = await world.db["webhooks"].find_one({"url": INTERNAL_RECEIVER})
    await world.services.outbox.enqueue("workorder.blocked", {"workOrderId": "WO-9", "reason": "ACCESS"})
    await world.services.outbox.dispatch_due()
    delivered = await world.db["webhook_deliveries"].find_one({"webhookId": hook["_id"], "eventType": "workorder.blocked"})
    before = await world.db["webhook_received"].count_documents({})

    replayed = await world.call("SYSTEM_ADMIN", "POST", f"/api/v1/admin/webhooks/{hook['_id']}/deliveries/{delivered['eventId']}/replay")
    assert replayed.status_code == 200 and replayed.json()["status"] == 200
    assert await world.db["webhook_received"].count_documents({}) == before  # the receiver's dedup key: nothing changed

    log = (await world.call("SYSTEM_ADMIN", "GET", f"/api/v1/admin/webhooks/{hook['_id']}/deliveries")).json()
    assert any(row["eventId"] == delivered["eventId"] for row in log)

    missing = await world.call("SYSTEM_ADMIN", "POST", f"/api/v1/admin/webhooks/{hook['_id']}/deliveries/NOPE/replay")
    assert missing.status_code == 404


async def test_a_failing_webhook_is_retried_by_the_outbox():
    async with open_env() as env:
        await env.db["webhooks"].insert_one({"_id": "WH-BAD", "url": "http://127.0.0.1:9/nowhere", "events": ["*"], "enabled": True, "secret": "s"})
        await env.services.outbox.enqueue("workorder.blocked", {"workOrderId": "WO-1"})
        assert await env.services.outbox.dispatch_due() == 0
        event = await env.db["outbox_events"].find_one({})
        assert event["dispatchedAt"] is None and event["lastError"] and ensure_utc(event["nextAttemptAt"]) > utcnow()
        assert (await env.db["webhook_deliveries"].find_one({"webhookId": "WH-BAD"}))["status"] == 0


# ---- analytics against a fixture -------------------------------------------------------------------------------------


async def test_analytics_match_a_fixture_with_known_answers():
    async with open_env() as env:
        db = env.db
        base = {"campusId": "CAMPUS-1", "createdAt": NOW, "duplicateOf": None}
        await db["incidents"].insert_many(
            [
                {**base, "_id": "I1", "status": "ACKNOWLEDGED", "category": "ELECTRICAL", "departmentId": "D-CSE"},
                {**base, "_id": "I2", "status": "IN_PROGRESS", "category": "ELECTRICAL", "departmentId": "D-CSE"},
                {**base, "_id": "I3", "status": "ASSIGNED", "category": "NETWORK", "departmentId": "D-ECE"},
                {**base, "_id": "I4", "status": "CLOSED", "category": "PLUMBING", "departmentId": "D-CSE"},
            ]
        )
        sla = {"pauses": [], "pausedMinutes": 0, "atRiskPercent": 75, "resolutionMinutes": 60, "startedAt": NOW - timedelta(hours=3), "campusId": "CAMPUS-1"}
        await db["sla_instances"].insert_many(
            [
                {**sla, "_id": "S1", "subjectId": "I1", "priority": "P1", "resolvedAt": NOW - timedelta(hours=2, minutes=30), "departmentId": "D-CSE"},
                {**sla, "_id": "S2", "subjectId": "I2", "priority": "P1", "resolvedAt": NOW - timedelta(minutes=30), "departmentId": "D-CSE"},
                {**sla, "_id": "S3", "subjectId": "I3", "priority": "P2", "resolvedAt": NOW - timedelta(hours=2, minutes=10), "departmentId": "D-CSE"},
                {**sla, "_id": "S4", "subjectId": "I4", "priority": "P2", "resolvedAt": NOW - timedelta(hours=2, minutes=20), "departmentId": "D-CSE"},
            ]
        )
        await db["inventory_items"].insert_many(
            [{"_id": "ITM-A", "name": "Part A", "reorderThreshold": 5}, {"_id": "ITM-B", "name": "Part B", "reorderThreshold": 2}]
        )
        await db["inventory_balances"].insert_many([{"_id": "BA", "itemId": "ITM-A", "onHand": 3, "reserved": 1}, {"_id": "BB", "itemId": "ITM-B", "onHand": 9, "reserved": 0}])
        await db["maintenance_history"].insert_many(
            [{"_id": f"MH{n}", "category": "HVAC", "roomId": "ARB-101", "completedAt": NOW - timedelta(days=n * 10)} for n in range(1, 4)]
            + [{"_id": "MH9", "category": "PLUMBING", "roomId": "ARB-102", "completedAt": NOW - timedelta(days=5)}]
        )
        body = (await env.call("FACILITIES_ADMIN", "GET", "/api/v1/analytics/overview")).json()
        assert body["open"]["total"] == 3
        assert {row["label"]: row["value"] for row in body["open"]["byCategory"]} == {"Electrical": 2, "Network": 1}
        assert body["sla"]["rate"] == 75  # S1, S3, S4 met (30, 50, 40 min); S2 breached (150 min)
        assert {row["label"]: row["value"] for row in body["sla"]["byPriority"]} == {"P1": 50, "P2": 100}
        assert body["shortages"] == [{"name": "Part A", "onHand": 2, "threshold": 5, "blocked": 0}]
        assert body["recurring"] == [{"name": "Hvac faults", "location": "ARB-101", "count": 3, "last": (NOW - timedelta(days=10)).date().isoformat()}]
        assert sum(row["value"] for row in body["daily"]) == 4 and len(body["daily"]) == 14
        dept = (await env.call("DEPARTMENT_MANAGER", "GET", "/api/v1/analytics/overview")).json()
        assert dept["open"]["total"] == 2  # only D-CSE, the department they manage


# ---- the rest of the operational surface ------------------------------------------------------------------------------


async def test_sla_lists_are_scoped(world):
    await report(world, "FACULTY", "Power socket sparking in ARB-204, smells of burning")
    assert len((await world.call("FACILITIES_ADMIN", "GET", "/api/v1/sla/instances")).json()) == 1
    assert len((await world.call("FACULTY", "GET", "/api/v1/sla/instances")).json()) == 1  # they reported it
    assert (await world.call("STUDENT", "GET", "/api/v1/sla/instances")).json() == []
    summary = (await world.call("FACILITIES_ADMIN", "GET", "/api/v1/sla/summary")).json()
    assert summary["onTrack"] + summary["atRisk"] + summary["breached"] + summary["paused"] == 1


async def test_badges_count_what_each_person_can_act_on(world):
    order = (await report(world, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{order['incidentId']}/actions/incident.createWorkOrder")
    wo = await world.db["work_orders"].find_one({"incidentId": order["incidentId"]})
    now = utcnow()
    await world.db["shifts"].insert_one({"_id": "SH-B", "technicianId": "T-01", "startAt": now - timedelta(hours=1), "endAt": now + timedelta(hours=10), "kind": "REGULAR"})
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{wo['_id']}/assign", json={"technicianId": "T-01"})
    assert (await world.call("TECHNICIAN", "GET", "/api/v1/me/badges")).json()["workorder.open"] == 1
    assert "workorder.open" not in (await world.call("STUDENT", "GET", "/api/v1/me/badges")).json()


async def test_admin_health_integrations_and_policies(world):
    health = (await world.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/system/health")).json()
    assert health["database"]["status"] == "UP" and health["ai"]["status"] in ("UP", "DEGRADED", "OFF") and health["dataQuality"][0]["ok"]
    state = (await world.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/integrations")).json()
    key = state["ai"]["features"][0]["key"]
    switched = (await world.call("SYSTEM_ADMIN", "PATCH", f"/api/v1/admin/integrations/features/{key}", json={"enabled": False})).json()
    assert switched["ai"]["features"][0]["enabled"] is False and switched["ai"]["features"][0]["mode"] == "RULES"
    assert (await world.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/integrations/features/nope", json={"enabled": False})).status_code == 404
    policies = (await world.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/sla-policies")).json()
    assert any(row["category"] == "ELECTRICAL" and row["priority"] == "P1" and row["resolutionMinutes"] == 180 for row in policies)
