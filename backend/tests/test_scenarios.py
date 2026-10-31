"""Phase 13: one-click scenario resets stage each demo through the normal services."""

import pytest
import pytest_asyncio

from tests.conftest import open_env


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        yield opened


async def reset(env, scenario):
    response = await env.call("SYSTEM_ADMIN", "POST", f"/api/v1/admin/scenarios/{scenario}/reset")
    assert response.status_code == 200, response.text
    return response.json()


async def test_scenarios_are_listed_for_the_administrator_only(world):
    assert [row["id"] for row in (await world.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/scenarios")).json()] == ["A", "B", "C", "D"]
    assert (await world.call("FACILITIES_ADMIN", "POST", "/api/v1/admin/scenarios/A/reset")).status_code == 403


async def test_a_reset_wipes_old_work_but_keeps_the_audit_trail(world):
    await world.call("FACULTY", "POST", "/api/v1/bookings", json={"roomCode": "ARB-204", "start": "2030-01-07T04:30:00Z", "end": "2030-01-07T05:30:00Z", "headcount": 10, "purpose": "Old booking"})
    audits = await world.db["audit_logs"].count_documents({})
    body = await reset(world, "D")
    assert body["ok"] and "Scenario D" in body["message"]
    assert await world.db["bookings"].count_documents({}) == 0
    assert await world.db["audit_logs"].count_documents({}) > audits
    assert await world.db["audit_logs"].count_documents({"action": "scenario.reset"}) == 1
    assert await world.db["rooms"].count_documents({}) > 0 and await world.db["users"].count_documents({}) > 0


async def test_scenario_a_puts_the_exam_in_the_impact(world):
    await reset(world, "A")
    incident = await world.db["incidents"].find_one({})
    snapshot = await world.db["impact_snapshots"].find_one({"_id": incident["_id"]})
    assert incident["assetIds"] == ["AST-DB-ARB-F2"] and snapshot["totals"]["exams"] == 1


async def test_scenario_b_merges_reports_and_leaves_an_email(world):
    await reset(world, "B")
    assert await world.db["incidents"].count_documents({"category": "NETWORK"}) == 1
    assert await world.db["reports"].count_documents({}) == 2
    assert await world.db["inbound_emails"].count_documents({}) == 1


async def test_scenario_c_blocks_work_on_a_missing_part_with_a_purchase_request(world):
    await reset(world, "C")
    order = await world.db["work_orders"].find_one({})
    assert order["status"] == "BLOCKED" and order["partRequirements"][0]["state"] == "SHORT"
    approval = await world.db["approvals"].find_one({})
    assert approval["status"] == "SUBMITTED" and approval["requesterId"] == "U-TECH"
    queue = (await world.call("PROCUREMENT_APPROVER", "GET", "/api/v1/approvals")).json()["items"]
    assert queue[0]["id"] == approval["_id"] and queue[0]["availableActions"][0]["key"] == "approval.approve"


async def test_scenario_d_then_the_technician_goes_sick(world):
    await reset(world, "D")
    order = await world.db["work_orders"].find_one({})
    assert order["status"] == "ACCEPTED" and order["assignedTechnicianId"] == "T-01"
    sick = await world.call("TECHNICIAN", "PATCH", "/api/v1/technicians/me/availability", json={"availability": "SICK"})
    assert sick.json()["flaggedIds"] == [order["_id"]]
    flagged = (await world.db["work_orders"].find_one({"_id": order["_id"]}))["needsReassignment"]
    assert flagged["suggestedTechnicianId"] == "T-02"


@pytest.mark.parametrize("scenario", ["A", "B", "C", "D"])
async def test_every_scenario_resets_twice_in_a_row(world, scenario):
    first = await reset(world, scenario)
    second = await reset(world, scenario)
    assert first["ok"] and second["ok"]


async def test_a_reset_is_refused_outside_demo_mode():
    async with open_env(demo_mode_enabled=False) as env:
        services = env.services
        from app.scenarios.service import ScenarioService

        try:
            await ScenarioService(services).reset(None, "A")  # type: ignore[arg-type]
        except Exception as error:
            assert getattr(error, "code", "") == "NOT_A_DEMO"
        else:
            raise AssertionError("a reset must be refused outside demo mode")
