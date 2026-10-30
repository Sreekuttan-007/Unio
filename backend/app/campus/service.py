from collections import Counter
from typing import Any

from app.core.authuser import AuthUser
from app.core.errors import not_found
from app.core.permission import Permission
from app.core.scope import EntityType, scope_filter
from app.staff.service import department_name, technician_cards

CLOSED_INCIDENT = ("RESOLVED", "CLOSED")

CATEGORY_WORD = {
    "ELECTRICAL": "Power",
    "NETWORK": "Wi-Fi",
    "PLUMBING": "Plumbing",
    "HVAC": "Cooling",
    "EQUIPMENT": "Equipment",
    "CARPENTRY": "Repairs",
    "SAFETY": "Safety",
    "HOUSEKEEPING": "Cleaning",
    "OTHER": "Maintenance",
}


def is_operational(user: AuthUser) -> bool:
    return user.has(Permission.MAP_READ_OPERATIONAL) or user.has(Permission.ADMIN_CAMPUS)


def _join_words(words: list[str]) -> str:
    unique = list(dict.fromkeys(words))
    return " and ".join([", ".join(unique[:-1]), unique[-1]] if len(unique) > 2 else unique)


async def open_incidents(db: Any) -> list[dict[str, Any]]:
    return await db["incidents"].find({"status": {"$nin": list(CLOSED_INCIDENT)}}).to_list(length=500)


async def region_overlays(db: Any, operational: bool) -> dict[str, dict[str, Any]]:
    buildings = await db["buildings"].find({}).to_list(length=100)
    closed_rooms = Counter(room["buildingId"] for room in await db["rooms"].find({"status": "CLOSED"}).to_list(length=1000))
    incidents = await open_incidents(db)
    # Buildings reached through dependencies (a shared transformer or switch) light up too, from the impact snapshots.
    urgent = [item["_id"] for item in incidents if item["priority"] in ("P1", "P2")]
    reached = {region async for snapshot in db["impact_snapshots"].find({"_id": {"$in": urgent}}) for region in snapshot.get("affectedRegionIds", [])}
    overlays: dict[str, dict[str, Any]] = {}
    for building in buildings:
        here = [item for item in incidents if item.get("buildingId") == building["_id"]]
        status = building.get("status", "OPEN")
        if status == "CLOSED":
            state = "CLOSED"
        elif status == "MAINTENANCE":
            state = "MAINTENANCE"
        elif closed_rooms[building["_id"]] or any(item["priority"] in ("P1", "P2") for item in here) or building["mapRegionId"] in reached:
            state = "AFFECTED"
        else:
            state = "OPEN"
        overlay: dict[str, Any] = {"state": state}
        if operational:
            if here:
                overlay["badge"] = len(here)
            if state in ("CLOSED", "MAINTENANCE"):
                overlay["caption"] = building.get("operationalNote") or building.get("publicNote")
            elif here and state == "AFFECTED":
                overlay["caption"] = _join_words([CATEGORY_WORD.get(item["category"], "Maintenance") for item in here if item["priority"] in ("P1", "P2")])
        else:
            if state in ("CLOSED", "MAINTENANCE"):
                overlay["caption"] = building.get("publicNote")
            elif state == "AFFECTED":
                overlay["caption"] = "Some rooms closed" if closed_rooms[building["_id"]] else "Disruption"
        overlays[building["mapRegionId"]] = {key: value for key, value in overlay.items() if value is not None}
    return overlays


async def map_payload(db: Any, user: AuthUser) -> dict[str, Any]:
    operational = is_operational(user)
    campus_map = await db["campus_map"].find_one({})
    if campus_map is None:
        raise not_found("Campus map")
    markers: list[dict[str, Any]] = []
    if operational:
        regions = {region["regionId"]: region["shape"] for region in campus_map["regions"]}
        for index, incident in enumerate(sorted(await open_incidents(db), key=lambda item: item["priority"])):
            shape = regions.get(incident.get("regionId", ""))
            if not shape:
                continue
            markers.append(
                {
                    "id": incident["_id"],
                    "x": shape["x"] + shape["w"] / 2 - 40 + (index % 5) * 22,
                    "y": shape["y"] + shape["h"] / 2 + 24,
                    "label": f"{incident['_id']} {incident['title']}",
                    "tone": "danger" if incident["priority"] == "P1" else "warning",
                }
            )
    return {
        "viewBox": campus_map["viewBox"],
        "decor": campus_map["decor"],
        "regions": campus_map["regions"],
        "overlays": await region_overlays(db, operational),
        "markers": markers,
        "view": "OPERATIONAL" if operational else "PUBLIC",
    }


async def building_detail(db: Any, user: AuthUser, ident: str) -> dict[str, Any]:
    building = await db["buildings"].find_one({"$or": [{"_id": ident}, {"mapRegionId": ident}]})
    if building is None:
        raise not_found("Building")
    operational = is_operational(user)
    rooms = await db["rooms"].find({"buildingId": building["_id"]}).sort("_id", 1).to_list(length=300)
    overlay = (await region_overlays(db, operational)).get(building["mapRegionId"], {"state": "OPEN"})
    incidents = [item for item in await open_incidents(db) if item.get("buildingId") == building["_id"]]
    asset_count = await db["assets"].count_documents({"buildingId": building["_id"]}) if operational else None
    return {
        "id": building["_id"],
        "name": building["name"],
        "code": building["code"],
        "kind": building["kind"],
        "status": overlay["state"],
        "openingHours": building["openingHours"],
        "floors": building["floors"],
        "department": department_name(building.get("departmentId")),
        "assetCount": asset_count,
        "roomCount": len(rooms),
        "rooms": [
            {"code": room["_id"], "type": room["type"], "capacity": room["capacity"], "features": room.get("features", []), "status": room["status"], "note": room.get("closedReason")}
            for room in rooms
        ]
        if operational
        else [],
        "incidents": [{"id": item["_id"], "title": item["title"], "priority": item["priority"], "status": item["status"]} for item in incidents] if operational else [],
    }


async def room_directory(db: Any, bookable_only: bool) -> list[dict[str, Any]]:
    buildings = {item["_id"]: item["name"] for item in await db["buildings"].find({}).to_list(length=100)}
    query: dict[str, Any] = {"bookable": True} if bookable_only else {}
    rooms = await db["rooms"].find(query).sort("_id", 1).to_list(length=500)
    return [
        {
            "code": room["_id"],
            "type": room["type"],
            "capacity": room["capacity"],
            "building": buildings.get(room["buildingId"], ""),
            "features": room.get("features", []),
            "status": room["status"],
            "closedReason": room.get("closedReason"),
        }
        for room in rooms
    ]


async def resources(db: Any, user: AuthUser) -> dict[str, Any]:
    scope = scope_filter(user, EntityType.RESOURCE)
    rooms = await db["rooms"].find({"$and": [scope, {"departmentId": {"$ne": None}}]}).sort("_id", 1).to_list(length=500)
    buildings = {item["_id"]: item for item in await db["buildings"].find({}).to_list(length=100)}
    building_ids = sorted({room["buildingId"] for room in rooms})
    assets = await db["assets"].find({"buildingId": {"$in": building_ids}, "criticality": {"$gte": 4}}).sort("_id", 1).to_list(length=300)
    managed = user.managed_department_ids
    return {
        "department": department_name(managed[0]) if managed else "Campus",
        "rooms": [
            {"code": room["_id"], "type": room["type"], "capacity": room["capacity"], "building": buildings[room["buildingId"]]["name"], "status": room["status"]}
            for room in rooms
        ],
        "assets": [{"id": asset["_id"], "name": asset["name"], "category": asset["category"], "status": "FAULT" if asset["status"] == "FAULT" else "OK"} for asset in assets],
        "technicians": await technician_cards(db),
    }


async def admin_summary(db: Any) -> dict[str, Any]:
    buildings = await db["buildings"].find({}).sort("_id", 1).to_list(length=100)
    rooms = Counter(room["buildingId"] for room in await db["rooms"].find({}).to_list(length=1000))
    assets = Counter(asset["buildingId"] for asset in await db["assets"].find({}).to_list(length=2000))
    regions = {region["regionId"] for region in ((await db["campus_map"].find_one({})) or {}).get("regions", [])}
    return {
        "totals": {"buildings": len(buildings), "rooms": sum(rooms.values()), "assets": sum(assets.values())},
        "buildings": [
            {
                "id": item["_id"],
                "code": item["code"],
                "name": item["name"],
                "kind": item["kind"],
                "floors": item["floors"],
                "rooms": rooms[item["_id"]],
                "assets": assets[item["_id"]],
                "regionBound": item["mapRegionId"] in regions,
                "status": item.get("status", "OPEN"),
            }
            for item in buildings
        ],
    }
