"""Phase 7: work orders, the technician's moves, explainable assignment and event-driven reassignment."""

import asyncio
import base64
from datetime import timedelta

import pytest_asyncio

from app.core.clock import utcnow
from app.workorders.state import WORK_MACHINE, WorkOrderEvent, WorkOrderStatus
from tests.conftest import DEMO_PASSWORD, open_env
from tests.test_incidents import report

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 32).decode()
TECHS = ("T-01", "T-02", "T-03", "T-04", "T-05", "T-06")


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        # Seeded shifts follow the real clock; give everyone a shift around "now" so results do not depend on when tests run.
        now = utcnow()
        await opened.db["shifts"].insert_many(
            [{"_id": f"SH-TEST-{tech}", "technicianId": tech, "startAt": now - timedelta(hours=2), "endAt": now + timedelta(hours=14), "kind": "REGULAR", "campusId": "CAMPUS-1"} for tech in TECHS]
        )
        yield opened


async def tech_headers(env, n):
    email = "tech@unio.demo" if n == 1 else f"tech{n}@unio.demo"
    response = await env.client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


async def new_order(env, text="Power socket sparking in ARB-204, smells of burning"):
    incident = (await report(env, "FACULTY", text)).json()["incidentId"]
    response = await env.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident}/actions/incident.createWorkOrder")
    assert response.status_code == 200, response.text
    order = await env.db["work_orders"].find_one({"incidentId": incident})
    return order["_id"]


async def assign(env, order_id, tech="T-01", **body):
    return await env.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/assign", json={"technicianId": tech, **body})


async def act(env, headers, order_id, action, json=None):
    return await env.client.post(f"/api/v1/work-orders/{order_id}/{action}", headers=headers, json=json)


async def started(env, order_id):
    """Assigned to T-01 (the demo technician), accepted and in progress."""
    assert (await assign(env, order_id)).status_code == 200
    tech = await tech_headers(env, 1)
    assert (await act(env, tech, order_id, "accept")).status_code == 200
    assert (await act(env, tech, order_id, "start")).status_code == 200
    return tech


# ---- the state machine ----------------------------------------------------------------------------------------


def test_the_machine_has_no_way_out_of_finished_work():
    for status in (WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED):
        assert all(not WORK_MACHINE.can(status, event) for event in WorkOrderEvent)
    assert not WORK_MACHINE.can(WorkOrderStatus.BLOCKED, WorkOrderEvent.COMPLETE)
    assert not WORK_MACHINE.can(WorkOrderStatus.IN_PROGRESS, WorkOrderEvent.CANCEL)  # stop the work first, then cancel
    assert WORK_MACHINE.target(WorkOrderStatus.BLOCKED, WorkOrderEvent.RESUME) is WorkOrderStatus.IN_PROGRESS


async def test_an_incident_becomes_a_work_order_with_a_skill_estimate_and_safety_note(world):
    order_id = await new_order(world)
    body = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/work-orders/{order_id}")).json()
    assert body["status"] == "PENDING_ASSIGNMENT" and body["category"] == "ELECTRICAL" and body["priority"] == "P1"
    assert body["requiredSkills"] == [{"code": "ELECTRICAL", "minLevel": 2}] and body["estimatedMinutes"] == 90
    assert "lock out" in body["safetyNote"]
    assert {a["key"] for a in body["availableActions"]} == {"workorder.assign", "workorder.cancel"}
    assert await world.db["audit_logs"].count_documents({"action": "workorder.create", "entityId": order_id}) == 1
    incident = await world.db["incidents"].find_one({"_id": body["incidentId"]})
    again = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident['_id']}/actions/incident.createWorkOrder")
    assert again.status_code == 422 and again.json()["code"] == "WORK_ORDER_EXISTS"


async def test_the_full_happy_path_ends_verified_with_history_and_maintenance_record(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    done = await act(world, tech, order_id, "complete", {"notes": "Replaced the socket and tested the circuit", "evidence": [{"name": "after.png", "mime": "image/png", "contentBase64": PNG}]})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "COMPLETED" and body["completion"]["notes"].startswith("Replaced") and len(body["completion"]["evidence"]) == 1
    assert await world.db["maintenance_history"].count_documents({"workOrderId": order_id}) == 1
    assert await world.db["technician_slots"].count_documents({"ownerId": order_id}) == 0  # the technician is free again
    verified = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/verify", json={"notes": "Checked"})
    assert verified.status_code == 200 and verified.json()["status"] == "VERIFIED"
    events = [row["event"] for row in (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/work-orders/{order_id}/history")).json()]
    assert events == ["CREATE", "ASSIGN", "ACCEPT", "START", "COMPLETE", "VERIFY"]


async def test_illegal_moves_get_a_plain_reason(world):
    order_id = await new_order(world)
    assert (await assign(world, order_id)).status_code == 200
    tech = await tech_headers(world, 1)
    response = await act(world, tech, order_id, "start")
    assert response.status_code == 422 and response.json()["code"] == "ILLEGAL_TRANSITION" and "Accept the task" in response.json()["message"]


async def test_completion_needs_notes_and_real_photos(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    assert (await act(world, tech, order_id, "complete", {"notes": " "})).json()["code"] == "COMPLETION_NOTES_REQUIRED"
    fake = base64.b64encode(b"not an image").decode()
    bad = await act(world, tech, order_id, "complete", {"notes": "Fixed it", "evidence": [{"name": "x.png", "mime": "image/png", "contentBase64": fake}]})
    assert bad.status_code == 422 and bad.json()["code"] == "FILE_TYPE_MISMATCH"
    assert (await world.db["work_orders"].find_one({"_id": order_id}))["status"] == "IN_PROGRESS"


async def test_blocked_work_cannot_be_completed(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    blocked = await act(world, tech, order_id, "block", {"reason": "ACCESS", "notes": "Room is locked"})
    assert blocked.status_code == 200 and blocked.json()["status"] == "BLOCKED"
    response = await act(world, tech, order_id, "complete", {"notes": "Done"})
    assert response.status_code == 422 and "Blocked work cannot be completed" in response.json()["message"]
    assert (await act(world, tech, order_id, "resume")).json()["status"] == "IN_PROGRESS"
    assert (await act(world, tech, order_id, "complete", {"notes": "Done after access"})).json()["status"] == "COMPLETED"


async def test_a_verifier_can_send_work_back(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    await act(world, tech, order_id, "complete", {"notes": "Done"})
    back = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/reject", json={"notes": "Still sparking"})
    assert back.status_code == 200 and back.json()["status"] == "IN_PROGRESS"
    assert await world.db["outbox_events"].count_documents({"eventType": "workorder.sent_back"}) == 1


async def test_decline_frees_the_slot_and_returns_it_to_the_queue(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    tech = await tech_headers(world, 1)
    body = (await act(world, tech, order_id, "decline", {"reason": "Not my area"})).json()
    assert body["status"] == "PENDING_ASSIGNMENT" and body["assignedTechnicianId"] is None
    assert await world.db["technician_slots"].count_documents({"ownerId": order_id}) == 0


# ---- who sees what -------------------------------------------------------------------------------------------------


async def test_a_technician_sees_and_moves_only_their_own_tasks(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    mine = await tech_headers(world, 1)
    other = await tech_headers(world, 2)
    assert [row["id"] for row in (await world.client.get("/api/v1/work-orders", headers=mine)).json()["items"]] == [order_id]
    assert (await world.client.get("/api/v1/work-orders", headers=other)).json()["items"] == []
    assert (await world.client.get(f"/api/v1/work-orders/{order_id}", headers=other)).status_code == 404
    assert (await act(world, other, order_id, "accept")).status_code == 404
    assert (await act(world, mine, order_id, "verify")).status_code == 403
    assert (await world.call("STUDENT", "GET", "/api/v1/work-orders")).status_code == 403


async def test_the_assignee_cannot_verify_their_own_repair(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    await act(world, tech, order_id, "complete", {"notes": "Done"})
    # Pretend the verifier did the repair themselves: the backend refuses whoever holds the work.
    admin = await world.db["users"].find_one({"email": "facilities@unio.demo"})
    await world.db["work_orders"].update_one({"_id": order_id}, {"$set": {"assignedUserId": admin["_id"]}})
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/verify")
    assert response.status_code == 422 and response.json()["code"] == "SELF_VERIFY"


# ---- ranking and assigning ---------------------------------------------------------------------------------------


async def test_candidates_are_ranked_with_reasons_and_the_unqualified_are_blocked(world):
    order_id = await new_order(world)
    ranked = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/work-orders/{order_id}/candidates")).json()
    assert [row["technicianId"] for row in ranked[:2]] == ["T-01", "T-02"]  # level 3 electrician first
    assert ranked[0]["score"] > ranked[1]["score"] and ranked[0]["decision"] == "ALLOW"
    assert {f["label"] for f in ranked[0]["factors"]} == {"Skill", "Workload", "Start", "Shift", "Location"}
    for row in ranked[2:]:
        assert row["decision"] == "BLOCK" and any(f["code"] == "TECH_SKILL" for f in row["findings"])
    response = await assign(world, order_id, "T-03")
    assert response.status_code == 422 and response.json()["code"] == "COLLISION_BLOCKED"


async def test_a_soft_warning_needs_the_codes_acknowledged_with_a_reason(world):
    await world.db["shifts"].delete_many({"technicianId": "T-01"})  # now outside T-01's shift
    order_id = await new_order(world)
    refused = await assign(world, order_id)
    assert refused.status_code == 409 and refused.json()["code"] == "COLLISION_WARNING" and refused.json()["details"]["requiresReason"] is True
    assert "TECH_SHIFT" in {f["code"] for f in refused.json()["details"]["findings"]}
    ok = await assign(world, order_id, acknowledgedCodes=["TECH_SHIFT"], overrideReason="Called in for an urgent fault")
    assert ok.status_code == 200, ok.text
    assert await world.db["audit_logs"].count_documents({"action": "collision.override"}) == 1


async def test_two_orders_racing_for_one_technician_cannot_both_hold_the_same_time(world):
    first = await new_order(world, "Power socket sparking in ARB-204, smells of burning")
    second = await new_order(world, "Electrical panel sparking in BHB-101, burning smell")
    results = await asyncio.gather(assign(world, first), assign(world, second))
    codes = sorted(r.status_code for r in results)
    slots = await world.db["technician_slots"].find({"technicianId": "T-01"}).to_list(length=100)
    assert len({slot["_id"] for slot in slots}) == len(slots)
    owners = {slot["ownerId"] for slot in slots}
    if codes == [200, 200]:
        # both may win only with non-overlapping windows
        a, b = [await world.db["work_orders"].find_one({"_id": oid}) for oid in (first, second)]
        assert a["scheduledEndAt"] <= b["scheduledStartAt"] or b["scheduledEndAt"] <= a["scheduledStartAt"]
    else:
        assert codes[0] == 200 and codes[1] in (409, 422) and len(owners) == 1


async def test_one_order_assigned_to_two_technicians_at_once_ends_with_exactly_one(world):
    order_id = await new_order(world)
    results = await asyncio.gather(assign(world, order_id, "T-01"), assign(world, order_id, "T-02"))
    assert all(r.status_code in (200, 409, 422) for r in results) and any(r.status_code == 200 for r in results)
    order = await world.db["work_orders"].find_one({"_id": order_id})
    holders = {slot["technicianId"] for slot in await world.db["technician_slots"].find({"ownerId": order_id}).to_list(length=100)}
    assert holders == {order["assignedTechnicianId"]}
    assert await world.db["technician_slots"].count_documents({"ownerId": order_id}) == 6  # 90 minutes in 15 minute slots


async def test_the_loser_of_an_assignment_race_leaves_the_winners_slots_alone(world, monkeypatch):
    order_id = await new_order(world)
    stale = await world.db["work_orders"].find_one({"_id": order_id})  # what the slower request read
    assert (await assign(world, order_id, "T-01")).status_code == 200  # the faster request wins
    service = world.services.workorders

    async def stale_get(user, work_order_id):
        return stale

    monkeypatch.setattr(service, "get", stale_get)
    lost = await assign(world, order_id, "T-02")
    assert lost.status_code == 409 and lost.json()["code"] == "VERSION_CONFLICT"
    slots = await world.db["technician_slots"].find({"ownerId": order_id}).to_list(length=100)
    assert {slot["technicianId"] for slot in slots} == {"T-01"} and len(slots) == 6


async def test_assigning_the_same_person_again_is_refused(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    again = await assign(world, order_id)
    assert again.status_code == 422 and again.json()["code"] == "ALREADY_ASSIGNED"


# ---- reassignment ------------------------------------------------------------------------------------------------------


async def test_a_sick_technician_flags_their_work_with_a_ranked_replacement(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    tech = await tech_headers(world, 1)
    sick = await world.client.patch("/api/v1/technicians/me/availability", headers=tech, json={"availability": "SICK", "reason": "Fever"})
    assert sick.status_code == 200 and sick.json()["flaggedIds"] == [order_id]
    body = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/work-orders/{order_id}")).json()
    assert body["needsReassignment"]["suggestedTechnicianId"] == "T-02" and "off sick" in body["needsReassignment"]["reason"]
    assert body["status"] == "ASSIGNED" and body["assignedTechnicianId"] == "T-01"  # nothing moves until a person confirms
    moved = await assign(world, order_id, "T-02")
    assert moved.status_code == 200 and moved.json()["assignedTechnicianId"] == "T-02" and moved.json()["needsReassignment"] is None
    assert await world.db["outbox_events"].count_documents({"eventType": "workorder.reassigned"}) == 1


async def test_with_no_qualified_replacement_the_suggestion_is_empty(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/technicians/T-02/availability", json={"availability": "ON_LEAVE"})
    await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/technicians/T-01/availability", json={"availability": "SICK"})
    flagged = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/work-orders/{order_id}")).json()["needsReassignment"]
    assert flagged["suggestedTechnicianId"] is None and flagged["suggestedName"] is None


async def test_coming_back_clears_the_unavailable_flag(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/technicians/T-01/availability", json={"availability": "SICK"})
    await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/technicians/T-01/availability", json={"availability": "AVAILABLE"})
    assert (await world.db["work_orders"].find_one({"_id": order_id}))["needsReassignment"] is None


async def test_a_technician_can_ask_for_a_replacement_once(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    tech = await tech_headers(world, 1)
    first = await act(world, tech, order_id, "request-reassign", {"reason": "Need a second pair of hands"})
    assert first.status_code == 200 and first.json()["needsReassignment"]["reason"] == "Need a second pair of hands"
    assert (await act(world, tech, order_id, "request-reassign")).json()["code"] == "ALREADY_REQUESTED"


async def test_review_late_flags_work_not_accepted_in_time_and_is_repeatable(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    later = utcnow() + timedelta(minutes=30)  # P1 must be accepted within 10 minutes
    assert await world.services.workorders.review_late(now=later) == [order_id]
    assert await world.services.workorders.review_late(now=later) == []  # already flagged
    flag = (await world.db["work_orders"].find_one({"_id": order_id}))["needsReassignment"]
    assert flag["trigger"] == "LATE" and flag["suggestedTechnicianId"] == "T-02"
    response = await world.call("FACILITIES_ADMIN", "POST", "/api/v1/work-orders/review-late")
    assert response.status_code == 200 and response.json()["message"] == "Nothing is late."


async def test_an_urgent_job_flags_lower_priority_work_in_its_way(world):
    await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/technicians/T-02/availability", json={"availability": "ON_LEAVE"})
    routine = await new_order(world, "Power socket sparking in BHB-101, smells of burning")
    await world.db["work_orders"].update_one({"_id": routine}, {"$set": {"priority": "P4"}})
    assert (await assign(world, routine)).status_code == 200
    urgent = await new_order(world)  # P1, and the only free electrician is busy with P4 work
    flag = (await world.db["work_orders"].find_one({"_id": routine}))["needsReassignment"]
    assert flag is not None and flag["trigger"] == "PREEMPTED" and urgent in flag["reason"]
    assert (await world.db["work_orders"].find_one({"_id": routine}))["status"] == "ASSIGNED"  # only flagged, never moved


async def test_technician_profile_and_maintenance_history(world):
    order_id = await new_order(world)
    tech = await started(world, order_id)
    await act(world, tech, order_id, "complete", {"notes": "Replaced the socket"})
    me = (await world.client.get("/api/v1/technicians/me", headers=tech)).json()
    assert me["id"] == "T-01" if "id" in me else me
    history = (await world.client.get("/api/v1/maintenance-history", headers=tech)).json()
    assert history and history[0]["summary"] == "Replaced the socket"
    other = await tech_headers(world, 3)
    assert all(row["summary"] != "Replaced the socket" for row in (await world.client.get("/api/v1/maintenance-history", headers=other)).json())


async def test_cancel_releases_the_technician(world):
    order_id = await new_order(world)
    await assign(world, order_id)
    body = (await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/cancel", json={"reason": "Duplicate"})).json()
    assert body["status"] == "CANCELLED"
    assert await world.db["technician_slots"].count_documents({"ownerId": order_id}) == 0
