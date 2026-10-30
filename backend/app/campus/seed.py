"""A deterministic, fictional campus. The same anchor date always yields identical data.

Everything here is invented (PS constraint C2). The generator is a pure function, so tests can
check its integrity (no double-booked rooms, no dangling references) without a database.
"""

import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.campus.layout import REGION_ID_FOR_BUILDING, build_map_document
from app.core.bulk import insert_missing
from app.core.clock import utcnow

SEED_VERSION = 1
RANDOM_SEED = 20261030
IST = timedelta(hours=5, minutes=30)

# id, code, name, kind, department, floors, rooms per floor
# Display names are the real SRM Easwari Engineering College (EEC) block each one is bound to on
# the map (see app/campus/layout.py). _id and code are unchanged from the original fictional
# campus on purpose: every room code, asset id and dependency edge is derived from `code`, and
# this app's whole test suite references those codes as literal strings (ARB-204, AST-TR-ARB...).
BUILDINGS: tuple[tuple[str, str, str, str, str | None, int, int], ...] = (
    ("B-ARB", "ARB", "EEC Main Block", "ACADEMIC", "D-CSE", 4, 6),
    ("B-BHB", "BHB", "Electronics Block 2", "ACADEMIC", "D-ECE", 3, 6),
    ("B-RMB", "RMB", "Academic Block 1", "ACADEMIC", None, 3, 6),
    ("B-RLB", "RLB", "Electronics Block 1", "LAB", "D-ECE", 2, 5),
    ("B-LIB", "LIB", "Institute of Science & Technology", "LIBRARY", None, 2, 3),
    ("B-ADM", "ADM", "New BMS Block", "ADMIN", None, 2, 4),
    ("B-CAF", "CAF", "Workshop", "COMMON", None, 1, 3),
    ("B-KLH", "KLH", "Boys Hostel", "HOSTEL", None, 3, 6),
)

# group id, department, size, home classroom
GROUPS: tuple[tuple[str, str, int, str], ...] = (
    ("CSE-3A", "D-CSE", 58, "ARB-204"),
    ("CSE-3B", "D-CSE", 56, "ARB-205"),
    ("CSE-2A", "D-CSE", 57, "ARB-104"),
    ("CSE-4A", "D-CSE", 52, "ARB-304"),
    ("ECE-3A", "D-ECE", 55, "BHB-201"),
    ("ECE-3B", "D-ECE", 54, "BHB-202"),
    ("ECE-2A", "D-ECE", 58, "BHB-101"),
    ("ECE-4A", "D-ECE", 50, "BHB-301"),
)

COURSES = (
    "Data Structures", "Digital Electronics", "Operating Systems", "Signals and Systems",
    "Computer Networks", "Database Systems", "Control Systems", "Embedded Systems",
    "Discrete Mathematics", "Machine Learning", "VLSI Design", "Software Engineering",
)

# (start, end) in campus local time. Periods 4 and 5 merge into one two-hour practical.
PERIODS = (((9, 0), (10, 0)), ((10, 0), (11, 0)), ((11, 15), (12, 15)), ((13, 30), (14, 30)), ((14, 30), (15, 30)))

SKILLS = ("ELECTRICAL", "NETWORK", "PLUMBING", "HVAC", "CARPENTRY", "GENERAL")

# technician id, user id, name, department, skills (code, level), shift start hour
TECHNICIANS: tuple[tuple[str, str, str, str, tuple[tuple[str, int], ...], int], ...] = (
    ("T-01", "U-TECH", "Ravi Kumar", "D-ELEC", (("ELECTRICAL", 3),), 8),
    ("T-02", "U-TECH2", "Meena Das", "D-ELEC", (("ELECTRICAL", 2), ("HVAC", 2)), 8),
    ("T-03", "U-TECH3", "Joseph Paul", "D-NET", (("NETWORK", 3),), 8),
    ("T-04", "U-TECH4", "Lakshmi Bose", "D-NET", (("NETWORK", 2), ("GENERAL", 2)), 12),
    ("T-05", "U-TECH5", "Hari Menon", "D-ELEC", (("PLUMBING", 3), ("CARPENTRY", 2)), 8),
    ("T-06", "U-TECH6", "Sneha Joshi", "D-ELEC", (("HVAC", 3), ("GENERAL", 2)), 12),
)

LOCATIONS = (
    {"_id": "LOC-MAIN", "name": "Central Store", "departmentId": None},
    {"_id": "LOC-ELEC", "name": "Electrical Store", "departmentId": "D-ELEC"},
    {"_id": "LOC-NET", "name": "Network Store", "departmentId": "D-NET"},
)

# sku, name, category, unit, reorder threshold, critical, unit cost in rupees
ITEMS: tuple[tuple[str, str, str, str, int, bool, int], ...] = (
    ("MCB-16A-1P", "MCB 16A single pole", "ELECTRICAL", "EA", 6, False, 180),
    ("MCB-32A-3P", "MCB 32A three pole", "ELECTRICAL", "EA", 4, True, 1450),
    ("MCB-63A-4P", "MCB 63A four pole", "ELECTRICAL", "EA", 2, True, 3200),
    ("CONTACTOR-25A", "Contactor 25A", "ELECTRICAL", "EA", 3, False, 950),
    ("RELAY-24V", "Relay 24V", "ELECTRICAL", "EA", 5, False, 220),
    ("CABLE-2.5MM", "Copper cable 2.5mm", "ELECTRICAL", "M", 100, False, 38),
    ("CABLE-6MM", "Copper cable 6mm", "ELECTRICAL", "M", 60, False, 92),
    ("FUSE-10A", "Fuse 10A", "ELECTRICAL", "EA", 20, False, 25),
    ("LED-TUBE-18W", "LED tube light 18W", "ELECTRICAL", "EA", 15, False, 260),
    ("LED-PANEL-36W", "LED panel 36W", "ELECTRICAL", "EA", 8, False, 780),
    ("SWITCH-6A", "Switch 6A", "ELECTRICAL", "EA", 12, False, 45),
    ("SOCKET-16A", "Socket 16A", "ELECTRICAL", "EA", 12, False, 85),
    ("DB-8WAY", "Distribution board 8 way", "ELECTRICAL", "EA", 2, False, 2400),
    ("ELCB-40A", "ELCB 40A", "ELECTRICAL", "EA", 3, True, 2100),
    ("CAP-FAN-2.5", "Fan capacitor 2.5uF", "ELECTRICAL", "EA", 10, False, 60),
    ("CEILING-FAN", "Ceiling fan 1200mm", "ELECTRICAL", "EA", 3, False, 2300),
    ("TERMINAL-BLOCK", "Terminal block", "ELECTRICAL", "EA", 25, False, 30),
    ("AP-WIFI6", "Wi-Fi 6 access point", "NETWORK", "EA", 3, True, 9800),
    ("SWITCH-24P", "24 port managed switch", "NETWORK", "EA", 1, True, 24500),
    ("SWITCH-8P", "8 port switch", "NETWORK", "EA", 3, False, 3200),
    ("PATCH-1M", "Patch cord 1m", "NETWORK", "EA", 30, False, 90),
    ("PATCH-3M", "Patch cord 3m", "NETWORK", "EA", 20, False, 140),
    ("CAT6-BOX", "Cat6 cable box 305m", "NETWORK", "EA", 2, False, 7400),
    ("SFP-10G", "SFP+ 10G module", "NETWORK", "EA", 4, True, 6200),
    ("RJ45-CONN", "RJ45 connector pack", "NETWORK", "PK", 10, False, 320),
    ("POE-INJECTOR", "PoE injector", "NETWORK", "EA", 5, False, 1900),
    ("UPS-1KVA", "UPS 1kVA", "NETWORK", "EA", 1, False, 8900),
    ("TAP-15MM", "Tap 15mm", "PLUMBING", "EA", 8, False, 210),
    ("VALVE-GATE-25", "Gate valve 25mm", "PLUMBING", "EA", 5, False, 480),
    ("PIPE-PVC-40", "PVC pipe 40mm", "PLUMBING", "M", 40, False, 120),
    ("PIPE-CPVC-20", "CPVC pipe 20mm", "PLUMBING", "M", 40, False, 95),
    ("ELBOW-PVC-40", "PVC elbow 40mm", "PLUMBING", "EA", 20, False, 35),
    ("FLUSH-VALVE", "Flush valve", "PLUMBING", "EA", 4, False, 760),
    ("WATER-PUMP-1HP", "Water pump 1HP", "PLUMBING", "EA", 1, True, 11200),
    ("TEFLON-TAPE", "Teflon tape", "PLUMBING", "EA", 30, False, 15),
    ("COMPRESSOR-1.5T", "AC compressor 1.5 ton", "HVAC", "EA", 1, True, 14800),
    ("CAP-AC-35", "AC run capacitor 35uF", "HVAC", "EA", 8, False, 340),
    ("FILTER-AC", "AC filter", "HVAC", "EA", 12, False, 220),
    ("GAS-R32", "Refrigerant R32 cylinder", "HVAC", "EA", 2, False, 5600),
    ("THERMOSTAT", "Thermostat", "HVAC", "EA", 4, False, 640),
    ("FAN-MOTOR-AC", "AC fan motor", "HVAC", "EA", 2, False, 2900),
    ("HINGE-4IN", "Door hinge 4 inch", "CARPENTRY", "EA", 20, False, 55),
    ("LOCK-MORTISE", "Mortise lock", "CARPENTRY", "EA", 6, False, 780),
    ("PLY-18MM", "Plywood 18mm sheet", "CARPENTRY", "EA", 4, False, 2100),
    ("SCREWS-PACK", "Wood screws pack", "CARPENTRY", "PK", 15, False, 90),
    ("WHITEBOARD", "Whiteboard 4x6", "CARPENTRY", "EA", 2, False, 3400),
    ("DESK-BENCH", "Classroom bench", "CARPENTRY", "EA", 6, False, 2800),
    ("PROJ-LAMP", "Projector lamp", "EQUIPMENT", "EA", 4, True, 5400),
    ("HDMI-5M", "HDMI cable 5m", "EQUIPMENT", "EA", 10, False, 480),
    ("VGA-5M", "VGA cable 5m", "EQUIPMENT", "EA", 8, False, 260),
    ("PROJECTOR-FULL", "Projector 4000 lumen", "EQUIPMENT", "EA", 1, True, 38000),
    ("SPEAKER-PA", "PA speaker", "EQUIPMENT", "EA", 2, False, 4200),
    ("MIC-WIRELESS", "Wireless microphone", "EQUIPMENT", "EA", 2, False, 6800),
    ("CLICKER", "Presentation clicker", "EQUIPMENT", "EA", 5, False, 900),
    ("BATTERY-AA", "AA battery pack", "EQUIPMENT", "PK", 20, False, 140),
    ("EXTENSION-4M", "Extension board 4m", "EQUIPMENT", "EA", 10, False, 420),
    ("BROOM-SET", "Cleaning broom set", "HOUSEKEEPING", "EA", 10, False, 180),
    ("BIN-LINER", "Bin liners pack", "HOUSEKEEPING", "PK", 20, False, 120),
    ("SANITIZER-5L", "Sanitizer 5L", "HOUSEKEEPING", "EA", 6, False, 640),
    ("MOP-KIT", "Mop kit", "HOUSEKEEPING", "EA", 5, False, 520),
)

# Scenario C: this critical part is out of stock everywhere.
OUT_OF_STOCK_SKU = "MCB-32A-3P"


def _ist(day: date, hour: int, minute: int) -> datetime:
    """Campus local time to UTC, which is how everything is stored."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC) - IST


def _room_types(kind: str, floor: int, index: int) -> tuple[str, int, list[str]]:
    if kind == "ACADEMIC":
        if index == 6:
            return "OFFICE", 12, ["WHITEBOARD"]
        if floor == 4 and index <= 2:
            return "SEMINAR", 100, ["PROJECTOR", "SOUND", "AIR_CONDITIONING"]
        return "CLASSROOM", 60, ["PROJECTOR", "WHITEBOARD"]
    if kind == "LAB":
        return "LAB", 30, ["WORKSTATIONS", "AIR_CONDITIONING"]
    if kind == "LIBRARY":
        return ("HALL", 150, ["WIFI", "AIR_CONDITIONING"]) if index == 1 else ("COMMON", 40, ["WIFI"])
    if kind == "ADMIN":
        if floor == 1 and index == 1:
            return "SEMINAR", 200, ["PROJECTOR", "SOUND", "AIR_CONDITIONING"]
        return "OFFICE", 10, []
    if kind == "COMMON":
        return "COMMON", 120, []
    return ("COMMON", 30, ["WIFI"]) if index == 6 else ("HOSTEL", 4, [])


def generate_campus(anchor: date, campus_id: str = "CAMPUS-1") -> dict[str, list[dict[str, Any]]]:
    """anchor is the Monday of the first timetable week."""
    rng = random.Random(RANDOM_SEED)
    now_marker = datetime(anchor.year, anchor.month, anchor.day, tzinfo=UTC)
    buildings: list[dict[str, Any]] = []
    floors: list[dict[str, Any]] = []
    rooms: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def asset(asset_id: str, name: str, category: str, building_id: str, room_id: str | None, criticality: int) -> None:
        assets.append(
            {
                "_id": asset_id,
                "assetCode": asset_id,
                "name": name,
                "category": category,
                "buildingId": building_id,
                "roomId": room_id,
                "campusId": campus_id,
                "status": "OK",
                "criticality": criticality,
                "installedAt": now_marker - timedelta(days=rng.randint(200, 1800)),
                "lastServicedAt": now_marker - timedelta(days=rng.randint(10, 300)),
            }
        )

    def edge(from_id: str, to_type: str, to_id: str, relation: str) -> None:
        edges.append(
            {
                "_id": f"E-{from_id}-{to_id}-{relation}",
                "fromType": "ASSET",
                "fromId": from_id,
                "toType": to_type,
                "toId": to_id,
                "relation": relation,
                "active": True,
                "source": "SEED",
                "campusId": campus_id,
            }
        )

    core_switch = "AST-SW-CORE"
    for building_id, code, name, kind, department, floor_count, per_floor in BUILDINGS:
        buildings.append(
            {
                "_id": building_id,
                "code": code,
                "name": name,
                "kind": kind,
                "departmentId": department,
                "campusId": campus_id,
                "floors": floor_count,
                "mapRegionId": REGION_ID_FOR_BUILDING[building_id],
                "status": "OPEN",
                "openingHours": "07:00-21:00" if kind != "HOSTEL" else "24 hours",
            }
        )
        transformer = f"AST-TR-{code}"
        asset(transformer, f"{name} transformer", "ELECTRICAL", building_id, None, 5)
        building_switch = f"AST-SW-{code}"
        asset(building_switch, f"{name} network switch", "NETWORK", building_id, None, 4)
        edge(transformer, "ASSET", building_switch, "POWERS")
        if building_id != "B-ADM":
            edge(core_switch, "ASSET", building_switch, "CONNECTS")

        for floor in range(1, floor_count + 1):
            floor_id = f"F-{code}-{floor}"
            floors.append({"_id": floor_id, "buildingId": building_id, "number": floor, "name": f"Floor {floor}"})
            panel = f"AST-DB-{code}-F{floor}"
            floor_switch = f"AST-SW-{code}-F{floor}"
            asset(panel, f"{name} floor {floor} power panel", "ELECTRICAL", building_id, None, 4)
            asset(floor_switch, f"{name} floor {floor} switch", "NETWORK", building_id, None, 3)
            edge(transformer, "ASSET", panel, "POWERS")
            edge(panel, "ASSET", floor_switch, "POWERS")
            edge(building_switch, "ASSET", floor_switch, "CONNECTS")

            floor_rooms: list[str] = []
            for index in range(1, per_floor + 1):
                room_type, capacity, features = _room_types(kind, floor, index)
                room_id = f"{code}-{floor}{index:02d}"
                floor_rooms.append(room_id)
                rooms.append(
                    {
                        "_id": room_id,
                        "code": room_id,
                        "buildingId": building_id,
                        "floorId": floor_id,
                        "type": room_type,
                        "capacity": capacity,
                        "features": features,
                        "departmentId": department if kind in ("ACADEMIC", "LAB") else None,
                        "campusId": campus_id,
                        "status": "OPEN",
                        "bookable": room_type in ("CLASSROOM", "LAB", "SEMINAR", "HALL"),
                    }
                )
                edge(panel, "ROOM", room_id, "POWERS")
                if "PROJECTOR" in features:
                    asset(f"AST-PR-{room_id}", f"Projector {room_id}", "EQUIPMENT", building_id, room_id, 2)
                if "AIR_CONDITIONING" in features:
                    asset(f"AST-AC-{room_id}", f"Air conditioner {room_id}", "HVAC", building_id, room_id, 2)

            for k, slot in enumerate(range(0, len(floor_rooms), 2), start=1):
                access_point = f"AST-AP-{code}-F{floor}-{k}"
                asset(access_point, f"Wi-Fi access point {code} floor {floor} #{k}", "NETWORK", building_id, floor_rooms[slot], 3)
                edge(floor_switch, "ASSET", access_point, "CONNECTS")
                for room_id in floor_rooms[slot : slot + 2]:
                    edge(access_point, "ROOM", room_id, "SERVES")

    # The campus core switch lives in the administration block and feeds every building switch.
    asset(core_switch, "Campus core switch", "NETWORK", "B-ADM", "ADM-103", 5)
    edge("AST-SW-ADM", "ASSET", core_switch, "CONNECTS")

    labs = [room["_id"] for room in rooms if room["type"] == "LAB"]
    faculty = [
        {
            "_id": f"FAC-{number:02d}",
            "name": name,
            "departmentId": "D-CSE" if number <= 6 else "D-ECE" if number <= 12 else ("D-CSE" if number % 2 else "D-ECE"),
            "kind": "FACULTY" if number <= 12 else "LAB_INSTRUCTOR",
            "userId": "U-FACULTY" if number == 1 else None,
            "campusId": campus_id,
        }
        for number, name in enumerate(
            (
                "Dr. Kiran Rao", "Prof. Anita Desai", "Dr. Suresh Pillai", "Prof. Meghna Rao", "Dr. Farhan Ali",
                "Prof. Lata Krishnan", "Dr. Vivek Menon", "Prof. Radha Iyer", "Dr. Tarun Bhat", "Prof. Sunita Nair",
                "Dr. Arvind Shah", "Prof. Pooja Verma", "Lab Instructor Dev", "Lab Instructor Isha", "Lab Instructor Jay",
                "Lab Instructor Kavya", "Lab Instructor Lalit", "Lab Instructor Maya", "Lab Instructor Nikhil",
                "Lab Instructor Om",
            ),
            start=1,
        )
    ]

    groups: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    for g, (group_id, department, size, home_room) in enumerate(GROUPS):
        groups.append(
            {
                "_id": group_id,
                "departmentId": department,
                "size": size,
                "homeRoomId": home_room,
                "memberUserIds": ["U-STUDENT"] if group_id == "CSE-3A" else [],
                "campusId": campus_id,
            }
        )
        for week in range(2):
            for weekday in range(5):
                day = anchor + timedelta(days=week * 7 + weekday)
                exam_day = week == 0 and weekday == 2 and group_id == "CSE-3A"
                if exam_day:
                    sessions.append(_session(group_id, department, size, home_room, "FAC-02", "Operating Systems end semester", "EXAM", day, (9, 0), (12, 0), campus_id))
                for period, (start, end) in enumerate(PERIODS):
                    if exam_day and period <= 2:
                        continue
                    practical_day = weekday == g % 5
                    if period >= 3 and practical_day:
                        if period == 3:
                            sessions.append(
                                _session(group_id, department, (size + 1) // 2, labs[g], f"FAC-{13 + g:02d}", f"{COURSES[(g + weekday) % len(COURSES)]} lab (batch A)", "PRACTICAL", day, PERIODS[3][0], PERIODS[4][1], campus_id)
                            )
                        continue
                    # Latin square: for a fixed day and period, no two groups share a lecturer.
                    lecturer = f"FAC-{(g + period + weekday + week) % 12 + 1:02d}"
                    course = COURSES[(g * 3 + weekday + period) % len(COURSES)]
                    sessions.append(_session(group_id, department, size, home_room, lecturer, course, "LECTURE", day, start, end, campus_id))

    technicians: list[dict[str, Any]] = []
    shifts: list[dict[str, Any]] = []
    for tech_id, user_id, name, department, skills, start_hour in TECHNICIANS:
        technicians.append(
            {
                "_id": tech_id,
                "userId": user_id,
                "name": name,
                "departmentId": department,
                "skills": [{"code": code, "level": level} for code, level in skills],
                "availability": "AVAILABLE",
                "maxConcurrentTasks": 3,
                "campusId": campus_id,
                "version": 0,
            }
        )
        for offset in range(14):
            day = anchor + timedelta(days=offset)
            if day.weekday() == 6:
                continue
            shifts.append(
                {
                    "_id": f"SH-{tech_id}-{day.isoformat()}",
                    "technicianId": tech_id,
                    "startAt": _ist(day, start_hour, 0),
                    "endAt": _ist(day, start_hour + 8, 0),
                    "kind": "REGULAR",
                    "campusId": campus_id,
                }
            )

    items = [
        {
            "_id": f"ITM-{sku}",
            "sku": sku,
            "name": name,
            "category": category,
            "unit": unit,
            "reorderThreshold": threshold,
            "critical": critical,
            "unitCostPaise": rupees * 100,
        }
        for sku, name, category, unit, threshold, critical, rupees in ITEMS
    ]
    balances: list[dict[str, Any]] = []
    for item in items:
        category = item["category"]
        stores = ["LOC-MAIN"] + (["LOC-ELEC"] if category in ("ELECTRICAL", "HVAC", "PLUMBING", "CARPENTRY") else []) + (["LOC-NET"] if category == "NETWORK" else [])
        for location in stores:
            on_hand = 0 if item["sku"] == OUT_OF_STOCK_SKU else rng.randint(max(item["reorderThreshold"] - 2, 0), item["reorderThreshold"] * 4)
            balances.append(
                {
                    "_id": f"BAL-{item['sku']}-{location}",
                    "itemId": item["_id"],
                    "locationId": location,
                    "onHand": on_hand,
                    "reserved": 0,
                    "campusId": campus_id,
                    "version": 0,
                }
            )

    history = _maintenance_history(rng, anchor, rooms, assets, campus_id)

    return {
        "buildings": buildings,
        "floors": floors,
        "rooms": rooms,
        "assets": assets,
        "dependency_edges": edges,
        "faculty": faculty,
        "student_groups": groups,
        "timetable_sessions": sessions,
        "technicians": technicians,
        "shifts": shifts,
        "stock_locations": [dict(location) for location in LOCATIONS],
        "inventory_items": items,
        "inventory_balances": balances,
        "maintenance_history": history,
        "campus_map": [build_map_document()],
    }


def _session(
    group_id: str, department: str, size: int, room_id: str, faculty_id: str, course: str, kind: str,
    day: date, start: tuple[int, int], end: tuple[int, int], campus_id: str,
) -> dict[str, Any]:
    start_at = _ist(day, *start)
    return {
        "_id": f"SES-{group_id}-{start_at.strftime('%Y%m%dT%H%M')}",
        "courseName": course,
        "kind": kind,
        "roomId": room_id,
        "facultyId": faculty_id,
        "departmentId": department,
        "studentGroup": group_id,
        "headcount": size,
        "startAt": start_at,
        "endAt": _ist(day, *end),
        "status": "SCHEDULED",
        "campusId": campus_id,
    }


def _maintenance_history(
    rng: random.Random, anchor: date, rooms: list[dict[str, Any]], assets: list[dict[str, Any]], campus_id: str
) -> list[dict[str, Any]]:
    """Six months of closed work, with deliberate repeat offenders so recurring-incident analytics has something to find."""
    room_building = {room["_id"]: room["buildingId"] for room in rooms}
    asset_by_id = {item["_id"]: item for item in assets}
    base = datetime(anchor.year, anchor.month, anchor.day, tzinfo=UTC)
    technicians = {"ELECTRICAL": "T-01", "NETWORK": "T-03", "HVAC": "T-06", "EQUIPMENT": "T-04", "PLUMBING": "T-05", "CARPENTRY": "T-05"}

    # (asset, room, category, summary, times)
    repeats = (
        ("AST-AP-ARB-F2-2", "ARB-203", "NETWORK", "Access point drops clients and reboots", 6),
        ("AST-PR-ARB-204", "ARB-204", "EQUIPMENT", "Projector lamp failed or image flickers", 4),
        ("AST-DB-BHB-F1", "BHB-103", "ELECTRICAL", "MCB trips when several rooms load at once", 3),
        (None, "KLH-304", "PLUMBING", "Bathroom tap leaking", 4),
        ("AST-AC-RLB-102", "RLB-102", "HVAC", "Lab air conditioner not cooling", 3),
    )
    records: list[dict[str, Any]] = []

    def add(asset_id: str | None, room_id: str | None, category: str, summary: str, days_ago: int) -> None:
        number = len(records) + 1
        item = asset_by_id.get(asset_id) if asset_id else None
        building = (item or {}).get("buildingId") or room_building.get(room_id or "", "B-ARB")
        records.append(
            {
                "_id": f"MH-{number:04d}",
                "assetId": asset_id,
                "roomId": room_id,
                "buildingId": building,
                "category": category,
                "summary": summary,
                "workOrderId": f"WO-H-{number:04d}",
                "technicianId": technicians.get(category, "T-01"),
                "completedAt": base - timedelta(days=days_ago, hours=rng.randint(0, 8)),
                "partsUsed": [],
                "costPaise": rng.choice((0, 0, 35000, 120000, 450000)),
                "campusId": campus_id,
            }
        )

    for asset_id, room_id, category, summary, times in repeats:
        for n in range(times):
            add(asset_id, room_id, category, summary, 12 + n * rng.randint(18, 40))

    generic = (
        ("ELECTRICAL", "Replaced faulty tube light"), ("ELECTRICAL", "Repaired loose socket"),
        ("NETWORK", "Replaced patch cord"), ("PLUMBING", "Cleared blocked drain"),
        ("HVAC", "Serviced air conditioner filter"), ("CARPENTRY", "Fixed door hinge"),
        ("EQUIPMENT", "Replaced HDMI cable"),
    )
    academic_rooms = [room["_id"] for room in rooms if room["buildingId"] in ("B-ARB", "B-BHB", "B-RMB", "B-RLB")]
    while len(records) < 150:
        category, summary = rng.choice(generic)
        add(None, rng.choice(academic_rooms), category, summary, rng.randint(2, 178))
    records.sort(key=lambda record: record["completedAt"])
    return records


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def seed_campus(db: Any, campus_id: str, anchor: date | None = None) -> bool:
    """Seeds once per SEED_VERSION. Returns True if it wrote anything."""
    state = await db["seed_state"].find_one({"_id": "campus"})
    if state and state.get("version") == SEED_VERSION:
        return False
    data = generate_campus(anchor or monday_of(utcnow().date()), campus_id)
    for collection, documents in data.items():
        await insert_missing(db[collection], documents)
    await db["seed_state"].replace_one(
        {"_id": "campus"}, {"_id": "campus", "version": SEED_VERSION, "seededAt": utcnow()}, upsert=True
    )
    return True


REGION_IDS = tuple(REGION_ID_FOR_BUILDING.values())
