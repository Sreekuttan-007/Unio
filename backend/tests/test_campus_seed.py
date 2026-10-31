import itertools
from collections import defaultdict
from datetime import date

from app.campus.layout import BUILDING_REGIONS
from app.campus.seed import OUT_OF_STOCK_SKU, generate_campus, seed_campus
from tests.conftest import open_env

ANCHOR = date(2026, 1, 5)
DATA = generate_campus(ANCHOR)


def test_the_generator_is_deterministic():
    assert generate_campus(ANCHOR) == generate_campus(ANCHOR)


def test_a_different_week_shifts_the_dates_but_not_the_structure():
    other = generate_campus(date(2026, 3, 2))
    assert {name: len(rows) for name, rows in other.items()} == {name: len(rows) for name, rows in DATA.items()}
    assert [r["_id"] for r in other["rooms"]] == [r["_id"] for r in DATA["rooms"]]
    assert other["timetable_sessions"][0]["startAt"] != DATA["timetable_sessions"][0]["startAt"]


def test_every_collection_has_unique_ids():
    for name, rows in DATA.items():
        assert len({row["_id"] for row in rows}) == len(rows), name


def test_the_campus_is_the_size_the_plan_promises():
    assert len(DATA["buildings"]) == 8
    assert len(DATA["rooms"]) >= 100
    assert len(DATA["assets"]) >= 150
    assert len(DATA["inventory_items"]) >= 60 - 5
    assert len(DATA["maintenance_history"]) >= 150


def test_every_reference_points_at_something_that_exists():
    rooms = {room["_id"] for room in DATA["rooms"]}
    buildings = {item["_id"] for item in DATA["buildings"]}
    assets = {item["_id"] for item in DATA["assets"]}
    floors = {item["_id"] for item in DATA["floors"]}
    assert all(room["buildingId"] in buildings and room["floorId"] in floors for room in DATA["rooms"])
    assert all(asset["buildingId"] in buildings and (asset["roomId"] is None or asset["roomId"] in rooms) for asset in DATA["assets"])
    for edge in DATA["dependency_edges"]:
        assert edge["fromId"] in assets
        assert edge["toId"] in (rooms if edge["toType"] == "ROOM" else assets)
    assert all(session["roomId"] in rooms for session in DATA["timetable_sessions"])
    assert all(group["homeRoomId"] in rooms for group in DATA["student_groups"])
    items = {item["_id"] for item in DATA["inventory_items"]}
    assert all(balance["itemId"] in items for balance in DATA["inventory_balances"])


def _overlaps(key: str) -> int:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for session in DATA["timetable_sessions"]:
        grouped[session[key]].append(session)
    clashes = 0
    for sessions in grouped.values():
        sessions.sort(key=lambda item: item["startAt"])
        clashes += sum(1 for a, b in itertools.pairwise(sessions) if b["startAt"] < a["endAt"])
    return clashes


def test_the_timetable_has_no_double_booking_of_rooms_lecturers_or_groups():
    assert _overlaps("roomId") == 0
    assert _overlaps("facultyId") == 0
    assert _overlaps("studentGroup") == 0


def test_a_session_never_holds_more_students_than_the_room_seats():
    capacity = {room["_id"]: room["capacity"] for room in DATA["rooms"]}
    assert all(session["headcount"] <= capacity[session["roomId"]] for session in DATA["timetable_sessions"])


def test_there_is_exactly_one_exam_and_it_is_the_scenario_a_exam():
    exams = [session for session in DATA["timetable_sessions"] if session["kind"] == "EXAM"]
    assert [(exam["roomId"], exam["studentGroup"], exam["headcount"]) for exam in exams] == [("ARB-204", "CSE-3A", 58)]


def test_every_room_is_powered_by_a_panel_that_traces_back_to_a_transformer():
    powered_by = {edge["toId"]: edge["fromId"] for edge in DATA["dependency_edges"] if edge["relation"] == "POWERS"}
    for room in DATA["rooms"]:
        node = room["_id"]
        for _ in range(6):
            node = powered_by.get(node, "")
            if node.startswith("AST-TR-"):
                break
        assert node.startswith("AST-TR-"), room["_id"]


def test_the_power_and_network_graph_has_no_cycles():
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in DATA["dependency_edges"]:
        graph[edge["fromId"]].append(edge["toId"])
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return False
        if state.get(node) == 2:
            return True
        state[node] = 1
        ok = all(visit(child) for child in graph.get(node, []))
        state[node] = 2
        return ok

    assert all(visit(node) for node in list(graph))


def test_every_room_has_wifi_coverage():
    served = {edge["toId"] for edge in DATA["dependency_edges"] if edge["relation"] == "SERVES"}
    assert {room["_id"] for room in DATA["rooms"]} <= served


def test_every_building_has_a_region_on_the_map():
    region_ids = {region[0] for region in BUILDING_REGIONS}
    assert {building["mapRegionId"] for building in DATA["buildings"]} == region_ids
    bound = {region["entityId"] for region in DATA["campus_map"][0]["regions"]}
    assert bound == {building["_id"] for building in DATA["buildings"]}


def test_map_regions_do_not_overlap_each_other():
    rects = [(r["shape"]["x"], r["shape"]["y"], r["shape"]["w"], r["shape"]["h"]) for r in DATA["campus_map"][0]["regions"]]
    for index, (ax, ay, aw, ah) in enumerate(rects):
        for bx, by, bw, bh in rects[index + 1 :]:
            assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay


def test_technicians_have_skills_and_a_shift_every_working_day():
    shifts: dict[str, int] = defaultdict(int)
    for shift in DATA["shifts"]:
        shifts[shift["technicianId"]] += 1
        assert shift["endAt"] > shift["startAt"]
    assert all(tech["skills"] for tech in DATA["technicians"])
    assert all(shifts[tech["_id"]] == 12 for tech in DATA["technicians"])


def test_the_scenario_c_part_is_out_of_stock_everywhere():
    balances = [b for b in DATA["inventory_balances"] if b["itemId"] == f"ITM-{OUT_OF_STOCK_SKU}"]
    assert balances and all(balance["onHand"] == 0 for balance in balances)


def test_maintenance_history_contains_the_recurring_offenders():
    counts: dict[str, int] = defaultdict(int)
    for record in DATA["maintenance_history"]:
        counts[record["assetId"] or record["roomId"]] += 1
    assert counts["AST-AP-ARB-F2-2"] >= 6
    assert counts["AST-PR-ARB-204"] >= 4


async def test_seeding_writes_once_and_never_overwrites_runtime_changes():
    async with open_env() as env:
        db = env.db
        assert await seed_campus(db, "CAMPUS-1", ANCHOR) is True
        assert await db["rooms"].count_documents({}) == len(DATA["rooms"])
        await db["rooms"].update_one({"_id": "ARB-204"}, {"$set": {"status": "CLOSED"}})
        assert await seed_campus(db, "CAMPUS-1", ANCHOR) is False
        assert (await db["rooms"].find_one({"_id": "ARB-204"}))["status"] == "CLOSED"
        # even a forced re-run only inserts what is missing
        await db["seed_state"].delete_many({})
        assert await seed_campus(db, "CAMPUS-1", ANCHOR) is True
        assert (await db["rooms"].find_one({"_id": "ARB-204"}))["status"] == "CLOSED"
        assert await db["timetable_sessions"].count_documents({}) == len(DATA["timetable_sessions"])
