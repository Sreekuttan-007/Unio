"""Where the rules get their facts.

The engine only ever sees a StateReader. The live one reads the database, and a simulator can hand
in a snapshot held in memory instead, so the same rules judge a real action and an imagined one.
Nothing here can write: every method is a read.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Protocol

from app.core.clock import ensure_utc

OPEN_TASKS = ("ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED")
SCHEDULED_TASKS = ("ASSIGNED", "ACCEPTED", "IN_PROGRESS")
LIVE_BOOKINGS = ("CONFIRMED", "PENDING", "RESCHEDULED")


class StateReader(Protocol):
    async def room(self, room_id: str) -> dict[str, Any] | None: ...
    async def building(self, building_id: str) -> dict[str, Any] | None: ...
    async def room_assets(self, room_id: str) -> list[dict[str, Any]]: ...
    async def room_occupancy(
        self, room_id: str, start: datetime, end: datetime, *, exclude_session_id: str | None = None, exclude_booking_id: str | None = None
    ) -> list[dict[str, Any]]: ...
    async def technician(self, technician_id: str) -> dict[str, Any] | None: ...
    async def technician_shifts(self, technician_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]: ...
    async def technician_tasks(self, technician_id: str, *, scheduled_only: bool = False, exclude_work_order_id: str | None = None) -> list[dict[str, Any]]: ...
    async def item(self, item_id: str) -> dict[str, Any] | None: ...
    async def stock(self, item_id: str) -> list[dict[str, Any]]: ...
    async def active_reservations(self, work_order_id: str, item_id: str) -> list[dict[str, Any]]: ...
    async def user(self, user_id: str) -> dict[str, Any] | None: ...
    async def approval(self, approval_id: str) -> dict[str, Any] | None: ...
    async def incident(self, incident_id: str) -> dict[str, Any] | None: ...
    async def candidate_rooms(self, building_id: str | None) -> list[dict[str, Any]]: ...
    async def all_technicians(self) -> list[dict[str, Any]]: ...
    def token(self) -> str: ...


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


class RecordingReader:
    """Remembers a digest of everything it was asked, so the facts a decision rested on can be compared later.

    The token changes if any fact a rule read has changed. Comparing the token from a preview with
    the one at commit is how a stale decision is caught.
    """

    def __init__(self) -> None:
        self._reads: dict[str, str] = {}

    def _note(self, name: str, arguments: Any, result: Any) -> Any:
        self._reads[f"{name}:{json.dumps(arguments, sort_keys=True, default=str)}"] = _digest(result)
        return result

    def token(self) -> str:
        return _digest(sorted(self._reads.items()))


class LiveStateReader(RecordingReader):
    def __init__(self, db: Any) -> None:
        super().__init__()
        self._db = db

    async def _one(self, collection: str, doc_id: str, name: str) -> dict[str, Any] | None:
        return self._note(name, doc_id, await self._db[collection].find_one({"_id": doc_id}))  # type: ignore[no-any-return]

    async def room(self, room_id: str) -> dict[str, Any] | None:
        return await self._one("rooms", room_id, "room")

    async def building(self, building_id: str) -> dict[str, Any] | None:
        return await self._one("buildings", building_id, "building")

    async def room_assets(self, room_id: str) -> list[dict[str, Any]]:
        rows = await self._db["assets"].find({"roomId": room_id}).sort("_id", 1).to_list(length=50)
        return self._note("room_assets", room_id, [{"_id": row["_id"], "name": row.get("name"), "category": row.get("category"), "status": row.get("status")} for row in rows])  # type: ignore[no-any-return]

    async def room_occupancy(
        self, room_id: str, start: datetime, end: datetime, *, exclude_session_id: str | None = None, exclude_booking_id: str | None = None
    ) -> list[dict[str, Any]]:
        start, end = ensure_utc(start), ensure_utc(end)
        sessions = await self._db["timetable_sessions"].find(
            {"roomId": room_id, "status": "SCHEDULED", "startAt": {"$lt": end}, "endAt": {"$gt": start}, "_id": {"$ne": exclude_session_id}}
        ).sort("startAt", 1).to_list(length=50)
        bookings = await self._db["bookings"].find(
            {"roomId": room_id, "status": {"$in": list(LIVE_BOOKINGS)}, "startAt": {"$lt": end}, "endAt": {"$gt": start}, "_id": {"$ne": exclude_booking_id}}
        ).sort("startAt", 1).to_list(length=50)
        found = [
            {
                "kind": "SESSION", "id": row["_id"], "label": row["courseName"], "detail": f"{row['studentGroup']}, {row['headcount']} people",
                "sessionKind": row["kind"], "startAt": ensure_utc(row["startAt"]), "endAt": ensure_utc(row["endAt"]), "headcount": row["headcount"],
            }
            for row in sessions
        ] + [
            {
                "kind": "BOOKING", "id": row["_id"], "label": row.get("purpose") or "A booking", "detail": f"{row.get('headcount', 0)} people",
                "sessionKind": row.get("academicImpact"), "startAt": ensure_utc(row["startAt"]), "endAt": ensure_utc(row["endAt"]), "headcount": row.get("headcount", 0),
            }
            for row in bookings
        ]
        return self._note("room_occupancy", [room_id, start, end, exclude_session_id, exclude_booking_id], found)  # type: ignore[no-any-return]

    async def technician(self, technician_id: str) -> dict[str, Any] | None:
        row = await self._db["technicians"].find_one({"_id": technician_id})
        return self._note("technician", technician_id, row)  # type: ignore[no-any-return]

    async def technician_shifts(self, technician_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        start, end = ensure_utc(start), ensure_utc(end)
        rows = await self._db["shifts"].find({"technicianId": technician_id, "startAt": {"$lt": end}, "endAt": {"$gt": start}}).sort("startAt", 1).to_list(length=10)
        found = [{"startAt": ensure_utc(row["startAt"]), "endAt": ensure_utc(row["endAt"]), "kind": row.get("kind")} for row in rows]
        return self._note("technician_shifts", [technician_id, start, end], found)  # type: ignore[no-any-return]

    async def technician_tasks(self, technician_id: str, *, scheduled_only: bool = False, exclude_work_order_id: str | None = None) -> list[dict[str, Any]]:
        statuses = SCHEDULED_TASKS if scheduled_only else OPEN_TASKS
        rows = await self._db["work_orders"].find(
            {"assignedTechnicianId": technician_id, "status": {"$in": list(statuses)}, "_id": {"$ne": exclude_work_order_id}}
        ).sort("_id", 1).to_list(length=100)
        found = [
            {
                "id": row["_id"], "title": row.get("title", row["_id"]), "status": row["status"],
                "startAt": ensure_utc(row["scheduledStartAt"]) if row.get("scheduledStartAt") else None,
                "endAt": ensure_utc(row["scheduledEndAt"]) if row.get("scheduledEndAt") else None,
            }
            for row in rows
        ]
        return self._note("technician_tasks", [technician_id, scheduled_only, exclude_work_order_id], found)  # type: ignore[no-any-return]

    async def item(self, item_id: str) -> dict[str, Any] | None:
        return await self._one("inventory_items", item_id, "item")

    async def stock(self, item_id: str) -> list[dict[str, Any]]:
        rows = await self._db["inventory_balances"].find({"itemId": item_id}).sort("_id", 1).to_list(length=20)
        names = {row["_id"]: row["name"] async for row in self._db["stock_locations"].find({})}
        found = [
            {"locationId": row["locationId"], "locationName": names.get(row["locationId"], row["locationId"]), "onHand": row["onHand"], "reserved": row["reserved"], "available": row["onHand"] - row["reserved"], "version": row.get("version", 0)}
            for row in rows
        ]
        return self._note("stock", item_id, found)  # type: ignore[no-any-return]

    async def active_reservations(self, work_order_id: str, item_id: str) -> list[dict[str, Any]]:
        rows = await self._db["reservations"].find({"workOrderId": work_order_id, "itemId": item_id, "status": "ACTIVE"}).to_list(length=20)
        return self._note("active_reservations", [work_order_id, item_id], [{"id": row["_id"], "qty": row["qty"]} for row in rows])  # type: ignore[no-any-return]

    async def user(self, user_id: str) -> dict[str, Any] | None:
        row = await self._db["users"].find_one({"_id": user_id})
        slim = None if row is None else {"_id": row["_id"], "name": row["name"], "roleKey": row["roleKey"], "approvalLimitPaise": row.get("approvalLimitPaise", 0)}
        return self._note("user", user_id, slim)  # type: ignore[no-any-return]

    async def approval(self, approval_id: str) -> dict[str, Any] | None:
        return await self._one("approvals", approval_id, "approval")

    async def incident(self, incident_id: str) -> dict[str, Any] | None:
        row = await self._db["incidents"].find_one({"_id": incident_id})
        slim = None if row is None else {"_id": row["_id"], "status": row["status"], "causedById": row.get("causedById"), "version": row.get("version", 0)}
        return self._note("incident", incident_id, slim)  # type: ignore[no-any-return]

    async def candidate_rooms(self, building_id: str | None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"bookable": True, "status": "OPEN"}
        rows = await self._db["rooms"].find(query).sort("_id", 1).to_list(length=300)
        if building_id:
            rows.sort(key=lambda row: (row["buildingId"] != building_id, row["_id"]))
        return rows  # not recorded: it only suggests places to look, and each candidate is judged on its own facts

    async def all_technicians(self) -> list[dict[str, Any]]:
        return await self._db["technicians"].find({}).sort("_id", 1).to_list(length=100)  # type: ignore[no-any-return]
