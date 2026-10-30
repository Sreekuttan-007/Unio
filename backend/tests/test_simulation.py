"""Phase 9: plans compared on a frozen copy, judged by the same rules, executed only if nothing changed."""

import ast
import hashlib
import json
import pathlib
from datetime import timedelta

import pytest_asyncio

from app.core.clock import ensure_utc, utcnow
from tests.conftest import open_env
from tests.test_incidents import report

LIVE = ("timetable_sessions", "bookings", "work_orders", "rooms", "technicians", "room_slots", "technician_slots", "incidents", "audit_logs", "inventory_balances")


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        now = utcnow()
        await opened.db["shifts"].insert_many(
            [{"_id": f"SH-SIM-{t}", "technicianId": t, "startAt": now - timedelta(hours=2), "endAt": now + timedelta(hours=14), "kind": "REGULAR", "campusId": "CAMPUS-1"} for t in ("T-01", "T-02")]
        )
        yield opened


async def live_hash(db):
    dump = {name: await db[name].find({}).sort("_id", 1).to_list(length=50_000) for name in LIVE}
    return hashlib.sha256(json.dumps(dump, sort_keys=True, default=str).encode()).hexdigest()


def next_daytime_slot():
    """The next 10:00 or 15:00 campus time (UTC+5:30) at least an hour away: always inside the 24 hour window, never after closing."""
    now = utcnow()
    local = now + timedelta(hours=5, minutes=30)
    for day in (0, 1):
        for hour in (10, 15):
            start = local.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day) - timedelta(hours=5, minutes=30)
            if start > now + timedelta(hours=1):
                return start
    raise AssertionError("unreachable")


async def incident_with_class(env):
    """An urgent incident in the room of a lecture placed at the next daytime slot, with nothing else in that room."""
    session = await env.db["timetable_sessions"].find_one({"kind": "LECTURE", "roomId": {"$regex": "^ARB-"}}, sort=[("_id", 1)])
    start = next_daytime_slot()
    await env.db["timetable_sessions"].update_many({"_id": {"$ne": session["_id"]}, "roomId": session["roomId"]}, {"$set": {"status": "CANCELLED"}})
    await env.db["timetable_sessions"].update_one({"_id": session["_id"]}, {"$set": {"startAt": start, "endAt": start + timedelta(hours=1)}})
    session = await env.db["timetable_sessions"].find_one({"_id": session["_id"]})
    incident_id = (await report(env, "FACULTY", f"Power socket sparking in {session['roomId']}, smells of burning")).json()["incidentId"]
    return incident_id, session


async def simulate(env, incident_id):
    response = await env.call("FACILITIES_ADMIN", "POST", "/api/v1/simulations", json={"incidentId": incident_id})
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_simulation_compares_three_plans_and_writes_nothing_live(world):
    incident_id, session = await incident_with_class(world)
    await world.token("FACILITIES_ADMIN")  # signing in is audited; take the picture after it
    before = await live_hash(world.db)
    run = await simulate(world, incident_id)
    assert await live_hash(world.db) == before  # the only write is the run itself
    assert await world.db["simulation_runs"].count_documents({}) == 1
    assert [plan["id"] for plan in run["plans"]] == ["A", "B", "C", "D", "E"] and run["snapshotHash"]
    assert all(any(metric["label"] == "SLA margin" for metric in plan["metrics"]) for plan in run["plans"])
    b = run["plans"][1]
    assert b["feasible"] and any(session["roomId"] in step and "Move" in step for step in b["actions"])
    assert run["recommendedPlanId"] in ("A", "B")
    labels = {metric["label"] for metric in b["metrics"]}
    assert {"Classes affected", "Students moved"} <= labels


async def test_the_repair_plan_is_blocked_with_a_reason_when_no_work_order_exists(world):
    incident_id, _ = await incident_with_class(world)
    run = await simulate(world, incident_id)
    c = run["plans"][2]
    assert c["feasible"] is False and "work order" in c["findings"][0]["message"] and c["findings"][0]["severity"] == "HARD"


async def test_the_next_window_plan_waits_past_a_busy_slot_the_now_plan_cannot_fill(world):
    incident_id, _ = await incident_with_class(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident_id}/actions/incident.createWorkOrder")
    now = utcnow()
    busy_end = now + timedelta(minutes=90)
    # Both technicians with a shift in this world are already busy right now, but free again well inside their shift.
    await world.db["work_orders"].insert_many(
        [
            {"_id": "WO-BUSY-1", "assignedTechnicianId": "T-01", "status": "ASSIGNED", "scheduledStartAt": now, "scheduledEndAt": busy_end},
            {"_id": "WO-BUSY-2", "assignedTechnicianId": "T-02", "status": "ASSIGNED", "scheduledStartAt": now, "scheduledEndAt": busy_end},
        ]
    )
    run = await simulate(world, incident_id)
    c = next(plan for plan in run["plans"] if plan["id"] == "C")
    d = next(plan for plan in run["plans"] if plan["id"] == "D")
    assert c["feasible"] is False and "No qualified technician is free to start" in c["findings"][0]["message"]
    assert d["feasible"] is True and d["actions"] and "starting" in d["actions"][0]
    wait = next(metric["value"] for metric in d["metrics"] if metric["label"] == "Wait before start (minutes)")
    assert int(wait) >= 90  # it genuinely waited past the busy block, not just copied plan C


async def test_stock_vs_buy_plan_separates_available_from_needs_purchase(world):
    incident_id, _ = await incident_with_class(world)
    await world.db["inventory_balances"].update_many({"itemId": "ITM-MCB-16A-1P"}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": "ITM-MCB-16A-1P", "locationId": "LOC-MAIN"}, {"$set": {"onHand": 5}})
    now = utcnow()
    await world.db["work_orders"].insert_one(
        {
            "_id": "WO-SIM-E", "incidentId": incident_id, "title": "Replace breakers", "status": "BLOCKED", "blockReason": "WAITING_FOR_PARTS", "priority": "P2", "category": "ELECTRICAL",
            "partRequirements": [
                {"itemId": "ITM-MCB-16A-1P", "sku": "MCB-16A-1P", "name": "MCB 16A single pole", "qty": 1, "state": "SHORT", "reservationId": None},
                {"itemId": "ITM-MCB-32A-3P", "sku": "MCB-32A-3P", "name": "MCB 32A three pole", "qty": 2, "state": "SHORT", "reservationId": None},
            ],
            "version": 0, "createdAt": now, "updatedAt": now,
        }
    )
    run = await simulate(world, incident_id)
    e = next(plan for plan in run["plans"] if plan["id"] == "E")
    metrics = {metric["label"]: metric["value"] for metric in e["metrics"]}
    assert metrics["Parts short"] == "2" and metrics["Available from stock"] == "1" and metrics["Needs a purchase"] == "1"
    assert metrics["Estimated purchase cost"] != "₹0"
    assert e["feasible"] is True  # a needed purchase is a finding, not a block
    assert "MCB 32A three pole" in e["findings"][0]["message"]


async def test_a_plan_never_moves_a_class_into_another_affected_room(world):
    incident_id, _session = await incident_with_class(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/cascading/impact/{incident_id}/recompute", json={"rootAssetIds": ["AST-TR-ARB"]})
    run = await simulate(world, incident_id)
    a = run["plans"][0]
    assert a["feasible"] is False and any("No free room in the same building" in f["message"] for f in a["findings"])  # the whole block is dark
    b = run["plans"][1]
    assert b["feasible"] and all("to ARB-" not in step for step in b["actions"])


async def test_executing_a_valid_plan_moves_the_class_through_the_normal_service(world):
    incident_id, session = await incident_with_class(world)
    run = await simulate(world, incident_id)
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/simulations/{run['id']}/plans/B/execute")
    assert response.status_code == 200 and response.json()["status"] == "EXECUTED", response.text
    moved = await world.db["timetable_sessions"].find_one({"_id": session["_id"]})
    assert moved["roomId"] != session["roomId"] and moved["movedFrom"]["roomId"] == session["roomId"]
    assert await world.db["audit_logs"].count_documents({"action": "session.move"}) == 1
    assert await world.db["audit_logs"].count_documents({"action": "simulation.execute"}) == 1
    again = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/simulations/{run['id']}/plans/B/execute")
    assert again.status_code == 409  # a run applies once


async def test_a_change_after_the_simulation_makes_the_plan_stale(world):
    incident_id, session = await incident_with_class(world)
    run = await simulate(world, incident_id)
    b = next(plan for plan in run["plans"] if plan["id"] == "B")
    target = b["actions"][0].split(" to ")[-1]
    # Someone books the target room for that class's time in the meantime.
    start, end = ensure_utc(session["startAt"]), ensure_utc(session["endAt"])
    await world.db["bookings"].insert_one({"_id": "BK-LATE", "roomId": target, "status": "CONFIRMED", "startAt": start, "endAt": end, "headcount": 5, "purpose": "Meeting"})
    before = await live_hash(world.db)
    result = (await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/simulations/{run['id']}/plans/B/execute")).json()
    assert result["status"] == "STALE" and "changed" in result["message"]
    assert (await world.db["timetable_sessions"].find_one({"_id": session["_id"]}))["roomId"] == session["roomId"]
    assert await live_hash(world.db) == before  # refusing changed nothing


async def test_a_blocked_plan_cannot_be_executed(world):
    incident_id, _ = await incident_with_class(world)
    run = await simulate(world, incident_id)
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/simulations/{run['id']}/plans/C/execute")
    assert response.status_code == 422 and response.json()["code"] == "PLAN_BLOCKED"


async def test_only_facilities_can_simulate(world):
    incident_id, _ = await incident_with_class(world)
    for role in ("STUDENT", "FACULTY", "TECHNICIAN", "PROCUREMENT_APPROVER", "DEPARTMENT_MANAGER"):
        assert (await world.call(role, "POST", "/api/v1/simulations", json={"incidentId": incident_id})).status_code == 403


def test_the_planner_and_snapshot_cannot_write_or_reach_live_services():
    """Import boundary: the code that builds plans holds no write path to live data."""
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "simulation"
    writes = {"insert_one", "insert_many", "update_one", "update_many", "replace_one", "delete_one", "delete_many", "find_one_and_update", "bulk_write", "drop"}
    for name in ("snapshot.py", "planner.py"):
        tree = ast.parse((root / name).read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
        assert not [module for module in imports if module.endswith(".service") or module.endswith(".router")], (name, imports)
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not (calls & writes), (name, calls & writes)
