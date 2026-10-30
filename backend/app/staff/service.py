from typing import Any

from app.core.clock import utcnow

DEPARTMENT_NAMES = {
    "D-CSE": "Computer Science",
    "D-ECE": "Electronics and Communication",
    "D-ELEC": "Electrical Maintenance",
    "D-NET": "Network Operations",
}

OPEN_STATUSES = ("ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED")


def department_name(department_id: str | None) -> str:
    return DEPARTMENT_NAMES.get(department_id or "", "Shared")


def _shift_label(start_hour: int) -> str:
    return f"{start_hour:02d}:00 to {start_hour + 8:02d}:00"


async def technician_cards(db: Any, ids: list[str] | None = None) -> list[dict[str, Any]]:
    """The technician board: skills, shift, availability and live workload, from stored data."""
    query: dict[str, Any] = {} if ids is None else {"_id": {"$in": ids}}
    technicians = await db["technicians"].find(query).sort("_id", 1).to_list(length=200)
    open_orders = await db["work_orders"].find({"status": {"$in": list(OPEN_STATUSES)}}).to_list(length=1000)
    shifts = await db["shifts"].find({}).sort("startAt", -1).to_list(length=2000)
    shift_hour: dict[str, int] = {}
    for shift in shifts:
        # The latest shift of each technician tells us their usual hours, in campus local time.
        shift_hour.setdefault(shift["technicianId"], (shift["startAt"].hour * 60 + shift["startAt"].minute + 330) // 60 % 24)
    cards = []
    for tech in technicians:
        mine = [order for order in open_orders if order.get("assignedTechnicianId") == tech["_id"]]
        stored = tech.get("availability", "AVAILABLE")
        availability = "BUSY" if stored == "AVAILABLE" and mine else stored
        blocked = next((order for order in mine if order["status"] == "BLOCKED"), None)
        flagged = next((order for order in mine if order.get("needsReassignment")), None)
        current = None
        if flagged:
            current = f"{flagged['_id']} needs reassignment"
        elif blocked:
            current = f"{blocked['_id']} blocked on a part"
        elif mine:
            current = f"{mine[0]['_id']} {mine[0]['title'][:40]}"
        maximum = int(tech.get("maxConcurrentTasks", 3))
        cards.append(
            {
                "id": tech["_id"],
                "name": tech["name"],
                "department": department_name(tech.get("departmentId")),
                "skills": tech.get("skills", []),
                "availability": availability,
                "shift": _shift_label(shift_hour.get(tech["_id"], 8)),
                "openTasks": len(mine),
                "maxTasks": maximum,
                "workloadPercent": min(100, round(len(mine) / maximum * 100)),
                "currentTask": current,
                "needsReplacement": flagged is not None,
            }
        )
    return cards


async def faculty_list(db: Any) -> list[dict[str, Any]]:
    rows = await db["faculty"].find({}).sort("_id", 1).to_list(length=200)
    return [{"id": row["_id"], "name": row["name"], "department": department_name(row.get("departmentId")), "kind": row["kind"]} for row in rows]


def now_iso() -> str:
    return utcnow().isoformat()
