"""Phase 8: what an incident breaks, traced through stored dependencies and the timetable only."""

from datetime import timedelta

import pytest_asyncio

from app.cascade.graph import walk
from app.cascade.service import rank_sessions
from app.core.clock import ensure_utc
from tests.conftest import open_env
from tests.test_incidents import report


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        yield opened


def edge(a, b, relation="POWERS", to_type="ASSET"):
    return {"fromType": "ASSET", "fromId": a, "toType": to_type, "toId": b, "relation": relation, "active": True}


async def socket_incident(env):
    body = (await report(env, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()
    return body["incidentId"]


async def exam(env):
    return await env.db["timetable_sessions"].find_one({"kind": "EXAM", "roomId": "ARB-204"})


# ---- the walk ----------------------------------------------------------------------------------------------------


def test_a_cycle_terminates_and_each_node_appears_once():
    reached = walk([edge("A", "B"), edge("B", "C"), edge("C", "A")], [("ASSET", "A")])
    assert [(node.id, node.depth) for node in reached] == [("A", 0), ("B", 1), ("C", 2)]


def test_the_depth_limit_stops_a_long_chain():
    chain = [edge(f"N{i}", f"N{i + 1}") for i in range(20)]
    reached = walk(chain, [("ASSET", "N0")], max_depth=3)
    assert [node.id for node in reached] == ["N0", "N1", "N2", "N3"]


def test_inactive_edges_are_ignored_and_the_reason_is_kept():
    reached = walk([edge("T", "P"), {**edge("P", "R1", to_type="ROOM"), "active": False}, edge("P", "R2", to_type="ROOM")], [("ASSET", "T")])
    assert [(n.kind, n.id, n.via_id, n.relation) for n in reached] == [("ASSET", "T", None, None), ("ASSET", "P", "T", "POWERS"), ("ROOM", "R2", "P", "POWERS")]


def test_exams_rank_first_then_directness_then_headcount():
    now = ensure_utc(__import__("datetime").datetime(2026, 1, 1))
    rows = [
        {"_id": "a", "kind": "LECTURE", "roomId": "R2", "headcount": 90, "startAt": now},
        {"_id": "b", "kind": "LECTURE", "roomId": "R1", "headcount": 30, "startAt": now},
        {"_id": "c", "kind": "EXAM", "roomId": "R2", "headcount": 10, "startAt": now},
        {"_id": "d", "kind": "LECTURE", "roomId": "R1", "headcount": 60, "startAt": now},
    ]
    assert [row["_id"] for row in rank_sessions(rows, {"R1": 1, "R2": 2})] == ["c", "d", "b", "a"]


# ---- known fixtures, exact answers -------------------------------------------------------------------------------


async def test_a_room_report_affects_exactly_that_room(world):
    incident_id = await socket_incident(world)
    body = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/cascading/impact/{incident_id}")).json()
    assert body["incidentId"] == incident_id and body["totals"]["rooms"] == 1
    assert body["chain"][0]["kind"] == "Rooms" and body["chain"][0]["title"] == "ARB-204 reported"
    assert body["affectedRegionIds"] == ["bld-arb"]
    stored = await world.db["incidents"].find_one({"_id": incident_id})
    assert stored["impactRoomIds"] == ["ARB-204"]  # bookings now avoid this room


async def test_a_transformer_fault_reaches_every_room_the_exam_and_its_students(world):
    incident_id = await socket_incident(world)
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-TR-ARB"]})
    assert response.status_code == 200, response.text
    the_exam = await exam(world)
    incident = await world.db["incidents"].find_one({"_id": incident_id})
    snapshot = await world.services.cascade.compute(incident, now=ensure_utc(the_exam["startAt"]) - timedelta(hours=1))
    arb_rooms = {row["_id"] async for row in world.db["rooms"].find({"buildingId": "B-ARB"})}
    assert set(snapshot["roomIds"]) == arb_rooms and snapshot["totals"]["rooms"] == 24
    assert snapshot["chain"][0] == {"id": "AST-TR-ARB", "depth": 0, "kind": "Fault", "title": "Aryabhata Block transformer (AST-TR-ARB)", "detail": f"Root of {incident_id}", "severity": "HIGH"}
    exams = [row for row in snapshot["chain"] if row["kind"] == "Exam"]
    assert len(exams) == 1 and "CSE-3A" in exams[0]["title"] and exams[0]["detail"] == "58 students"
    assert snapshot["affectedSessions"][0]["kind"] == "EXAM" and snapshot["totals"]["exams"] == 1
    assert "U-STUDENT" in snapshot["recipientUserIds"]  # a member of CSE-3A
    sessions = await world.db["timetable_sessions"].find({"roomId": {"$in": snapshot["roomIds"]}, "endAt": {"$gt": ensure_utc(the_exam["startAt"]) - timedelta(hours=1)}}).to_list(length=2000)
    faculty_users = {f["userId"] async for f in world.db["faculty"].find({"_id": {"$in": [s["facultyId"] for s in sessions]}}) if f.get("userId")}
    members = {u async for g in world.db["student_groups"].find({"_id": {"$in": [s["studentGroup"] for s in sessions]}}) for u in g.get("memberUserIds", [])}
    assert set(snapshot["recipientUserIds"]) <= faculty_users | members
    assert "U-FACILITIES" not in snapshot["recipientUserIds"] and "U-SYSADMIN" not in snapshot["recipientUserIds"]
    alternative = snapshot["affectedSessions"][0]["alternative"]
    assert alternative is None or alternative["roomCode"] not in arb_rooms  # never another room on the dead transformer
    assert await world.db["audit_logs"].count_documents({"action": "incident.root_assets", "entityId": incident_id}) == 1


async def test_the_chain_contains_only_records_that_exist(world):
    incident_id = await socket_incident(world)
    await world.db["dependency_edges"].insert_one({"_id": "E-BOGUS", **edge("AST-TR-ARB", "NOWHERE-999", to_type="ROOM"), "campusId": "CAMPUS-1"})
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-TR-ARB"]})
    body = (await world.call("FACILITIES_ADMIN", "GET", f"/api/v1/cascading/impact/{incident_id}")).json()
    text = str(body)
    assert "NOWHERE-999" not in text
    asset_ids = {row["id"] for row in body["chain"] if row["kind"] in ("Fault", "Asset")}
    assert asset_ids and all([await world.db["assets"].find_one({"_id": asset_id}) for asset_id in asset_ids])


async def test_an_unknown_asset_is_refused(world):
    incident_id = await socket_incident(world)
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-MADE-UP"]})
    assert response.status_code == 422 and response.json()["code"] == "UNKNOWN_ASSET"


async def test_a_resolved_incident_affects_nothing(world):
    incident_id = await socket_incident(world)
    await world.db["incidents"].update_one({"_id": incident_id}, {"$set": {"status": "RESOLVED"}})
    snapshot = await world.services.cascade.refresh(incident_id)
    assert snapshot["totals"]["rooms"] == 0 and snapshot["chain"] == [] and snapshot["recipientUserIds"] == []


async def test_creating_a_work_order_adds_it_to_the_chain(world):
    incident_id = await socket_incident(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident_id}/actions/incident.createWorkOrder")
    snapshot = await world.db["impact_snapshots"].find_one({"_id": incident_id})
    assert snapshot["totals"]["workOrders"] == 1 and any(row["kind"] == "Work" for row in snapshot["chain"])


# ---- who sees what -------------------------------------------------------------------------------------------------


async def test_academic_impact_is_limited_to_the_callers_classes(world):
    incident_id = await socket_incident(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-TR-ARB"]})
    the_exam = await exam(world)
    incident = await world.db["incidents"].find_one({"_id": incident_id})
    snapshot = await world.services.cascade.compute(incident, now=ensure_utc(the_exam["startAt"]) - timedelta(hours=1))
    await world.db["impact_snapshots"].replace_one({"_id": incident_id}, {"_id": incident_id, **snapshot})
    everyone = (await world.call("FACILITIES_ADMIN", "GET", "/api/v1/cascading/academic")).json()
    assert everyone and everyone[0]["incidentId"] == incident_id
    mine = (await world.call("FACULTY", "GET", "/api/v1/cascading/academic")).json()
    taught = {row["_id"] async for row in world.db["timetable_sessions"].find({"facultyId": "FAC-01"})}
    assert all(row["id"] in taught for item in mine for row in item["sessions"])
    assert all(row["id"] != the_exam["_id"] for item in mine for row in item["sessions"])  # FAC-02 sets that exam
    assert (await world.call("STUDENT", "GET", "/api/v1/cascading/academic")).status_code == 403


async def test_impact_is_scoped_like_the_incident(world):
    incident_id = await socket_incident(world)
    assert (await world.call("FACULTY", "GET", f"/api/v1/cascading/impact/{incident_id}")).status_code == 200  # they reported it
    assert (await world.call("TECHNICIAN", "GET", f"/api/v1/cascading/impact/{incident_id}")).status_code == 403
    assert (await world.call("FACULTY", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute")).status_code == 403


async def test_the_map_lights_up_buildings_reached_through_a_shared_dependency(world):
    incident_id = await socket_incident(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-SW-CORE"]})
    snapshot = await world.db["impact_snapshots"].find_one({"_id": incident_id})
    assert len(snapshot["affectedRegionIds"]) > 1  # the core switch feeds every building switch
    from app.campus.service import region_overlays

    overlays = await region_overlays(world.db, operational=True)
    assert all(overlays[region]["state"] in ("AFFECTED", "CLOSED", "MAINTENANCE") for region in snapshot["affectedRegionIds"])
