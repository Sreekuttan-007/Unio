import pytest_asyncio

from app.users.seed import seed_roles
from tests.conftest import open_env


@pytest_asyncio.fixture(scope="module")
async def campus_env():
    async with open_env(seed_campus=True) as opened:
        yield opened


async def test_a_student_gets_the_public_map_with_no_operational_detail(campus_env):
    body = (await campus_env.call("STUDENT", "GET", "/api/v1/campus/map")).json()
    assert body["view"] == "PUBLIC"
    assert body["markers"] == []
    assert len(body["regions"]) == 8
    assert all("badge" not in overlay for overlay in body["overlays"].values())
    assert body["viewBox"] == {"w": 1200, "h": 760}


async def test_facilities_gets_the_operational_map(campus_env):
    body = (await campus_env.call("FACILITIES_ADMIN", "GET", "/api/v1/campus/map")).json()
    assert body["view"] == "OPERATIONAL"
    assert body["overlays"]["bld-arb"]["state"] == "OPEN"  # nothing is wrong until something is reported


async def test_procurement_has_no_map(campus_env):
    assert (await campus_env.call("PROCUREMENT_APPROVER", "GET", "/api/v1/campus/map")).status_code == 403


async def test_building_detail_shows_rooms_to_staff_only(campus_env):
    public = (await campus_env.call("STUDENT", "GET", "/api/v1/campus/buildings/bld-arb")).json()
    staff = (await campus_env.call("FACILITIES_ADMIN", "GET", "/api/v1/campus/buildings/B-ARB")).json()
    assert public["name"] == staff["name"] == "Aryabhata Block"
    assert public["rooms"] == [] and public["assetCount"] is None and public["incidents"] == []
    assert len(staff["rooms"]) == 24 and staff["assetCount"] > 20
    assert {room["code"] for room in staff["rooms"]} >= {"ARB-204", "ARB-304"}
    assert (await campus_env.call("STUDENT", "GET", "/api/v1/campus/buildings/nope")).status_code == 404


async def test_the_room_directory_is_for_people_who_can_book_or_manage(campus_env):
    assert (await campus_env.call("STUDENT", "GET", "/api/v1/campus/rooms")).status_code == 403
    rooms = (await campus_env.call("FACULTY", "GET", "/api/v1/campus/rooms?bookable=true")).json()
    assert rooms and all(room["type"] in ("CLASSROOM", "LAB", "SEMINAR", "HALL") for room in rooms)
    everything = (await campus_env.call("FACILITIES_ADMIN", "GET", "/api/v1/campus/rooms")).json()
    assert len(everything) > len(rooms)
    assert {"code", "type", "capacity", "building", "features", "status", "closedReason"} <= set(rooms[0])


async def test_closing_a_room_marks_its_building_affected_and_is_audited():
    async with open_env(seed_campus=True) as env:
        refused = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/campus/rooms/ARB-204/status", json={"status": "CLOSED"})
        assert refused.status_code == 422 and refused.json()["code"] == "REASON_REQUIRED"
        done = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/campus/rooms/ARB-204/status", json={"status": "CLOSED", "reason": "No power"})
        assert done.status_code == 200
        student = (await env.call("STUDENT", "GET", "/api/v1/campus/map")).json()
        assert student["overlays"]["bld-arb"] == {"state": "AFFECTED", "caption": "Some rooms closed"}
        rooms = (await env.call("FACULTY", "GET", "/api/v1/campus/rooms?bookable=true")).json()
        assert next(room for room in rooms if room["code"] == "ARB-204")["status"] == "CLOSED"
        audit = (await env.call("FACILITIES_ADMIN", "GET", "/api/v1/audit")).json()
        assert any(item["action"] == "room.status.update" and item["entityId"] == "ARB-204" for item in audit["items"])
        reopened = await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/campus/rooms/ARB-204/status", json={"status": "OPEN"})
        assert reopened.json()["closedReason"] is None
        assert (await env.call("STUDENT", "GET", "/api/v1/campus/map")).json()["overlays"]["bld-arb"]["state"] == "OPEN"


async def test_a_closed_building_shows_hatched_closed_with_its_reason():
    async with open_env(seed_campus=True) as env:
        await env.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/campus/buildings/bld-caf/status", json={"status": "CLOSED", "reason": "Deep cleaning"})
        overlay = (await env.call("STUDENT", "GET", "/api/v1/campus/map")).json()["overlays"]["bld-caf"]
        assert overlay == {"state": "CLOSED", "caption": "Deep cleaning"}


async def test_a_department_manager_sees_only_their_own_departments_rooms(campus_env):
    body = (await campus_env.call("DEPARTMENT_MANAGER", "GET", "/api/v1/campus/resources")).json()
    assert body["department"] == "Computer Science"
    assert body["rooms"] and all(room["code"].startswith("ARB-") for room in body["rooms"])
    assert body["assets"] and all(asset["id"].startswith(("AST-TR-ARB", "AST-DB-ARB", "AST-SW-ARB", "AST-SW-CORE")) for asset in body["assets"])
    assert len(body["technicians"]) == 6


async def test_facilities_resources_cover_every_academic_department(campus_env):
    body = (await campus_env.call("FACILITIES_ADMIN", "GET", "/api/v1/campus/resources")).json()
    prefixes = {room["code"][:3] for room in body["rooms"]}
    assert {"ARB", "BHB", "RLB"} <= prefixes


async def test_technician_cards_carry_skills_shift_and_workload(campus_env):
    cards = (await campus_env.call("FACILITIES_ADMIN", "GET", "/api/v1/technicians")).json()
    assert len(cards) == 6
    ravi = next(card for card in cards if card["id"] == "T-01")
    assert ravi["name"] == "Ravi Kumar" and ravi["skills"] == [{"code": "ELECTRICAL", "level": 3}]
    assert ravi["shift"] == "08:00 to 16:00" and ravi["availability"] == "AVAILABLE" and ravi["maxTasks"] == 3
    assert next(card for card in cards if card["id"] == "T-04")["shift"] == "12:00 to 20:00"
    assert (await campus_env.call("TECHNICIAN", "GET", "/api/v1/technicians")).status_code == 403


async def test_the_admin_summary_proves_every_building_is_on_the_map(campus_env):
    body = (await campus_env.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/campus/summary")).json()
    assert body["totals"]["buildings"] == 8 and body["totals"]["rooms"] >= 100
    assert all(building["regionBound"] for building in body["buildings"])
    staff = (await campus_env.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/staff")).json()
    assert len(staff["technicians"]) == 6 and len(staff["faculty"]) == 20


async def test_a_new_permission_reaches_an_existing_role_but_removed_ones_stay_removed():
    async with open_env() as env:
        roles = env.db["roles_permissions"]
        # simulate a database seeded before campus.read existed, where an admin also removed a permission
        legacy = [p for p in (await roles.find_one({"_id": "FACILITIES_ADMIN"}))["permissions"] if p not in ("campus.read", "map.read.operational")]
        baseline = [p for p in legacy]
        await roles.update_one({"_id": "FACILITIES_ADMIN"}, {"$set": {"permissions": legacy, "seedBaseline": baseline + ["map.read.operational"]}})
        await seed_roles(env.services)
        role = await roles.find_one({"_id": "FACILITIES_ADMIN"})
        assert "campus.read" in role["permissions"]
        assert "map.read.operational" not in role["permissions"]
