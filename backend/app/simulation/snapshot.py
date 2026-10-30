"""A frozen, in-memory copy of the facts the collision rules read.

SnapshotReader is the live reader pointed at this copy, so a simulated action is judged on exactly
the same facts, in exactly the same shape, by exactly the same rules as a real one. Changing the
copy (apply_move, apply_assignment) lets later steps of a plan see earlier ones. Nothing in this
module can reach the live database after load() has read it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import operator
from datetime import datetime, timedelta
from typing import Any

from app.collision.reader import LiveStateReader
from app.core.clock import ensure_utc

# The collections the rules read, each limited to what a recovery plan for the next day can touch.
WINDOWED = ("timetable_sessions", "bookings", "shifts")
WHOLE = (
    "rooms", "buildings", "assets", "technicians", "work_orders", "inventory_items", "inventory_balances", "stock_locations", "reservations", "users", "approvals", "incidents", "collision_rules",
    "sla_instances",
)
WINDOW_HOURS = 48

_COMPARE = {"$lt": operator.lt, "$lte": operator.le, "$gt": operator.gt, "$gte": operator.ge}


def _norm(value: Any) -> Any:
    return ensure_utc(value) if isinstance(value, datetime) else value


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    """The small part of the MongoDB query language the readers use: equality, $in, $nin, $ne and ranges."""
    for key, condition in query.items():
        value = _norm(doc.get(key))
        if isinstance(condition, dict) and any(name.startswith("$") for name in condition):
            for name, operand in condition.items():
                if name == "$in" and value not in operand:
                    return False
                if name == "$nin" and value in operand:
                    return False
                if name == "$ne" and value == _norm(operand):
                    return False
                if name in _COMPARE and (value is None or not _COMPARE[name](value, _norm(operand))):
                    return False
        elif value != _norm(condition):
            return False
    return True


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def sort(self, key: str | list[tuple[str, int]], direction: int = 1) -> _Cursor:
        keys = [(key, direction)] if isinstance(key, str) else key
        for field, way in reversed(keys):
            self._rows.sort(key=lambda row: (row.get(field) is None, _norm(row.get(field))), reverse=way < 0)
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return [copy.deepcopy(row) for row in self._rows[:length]]

    def __aiter__(self) -> Any:
        async def rows() -> Any:
            for row in self._rows:
                yield copy.deepcopy(row)

        return rows()


class _Collection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def find(self, query: dict[str, Any] | None = None) -> _Cursor:
        return _Cursor([row for row in self.rows if _matches(row, query or {})])

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next((copy.deepcopy(row) for row in self.rows if _matches(row, query)), None)


class MemoryDb:
    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self._collections = {name: _Collection(rows) for name, rows in data.items()}

    def __getitem__(self, name: str) -> _Collection:
        return self._collections.setdefault(name, _Collection([]))


class Snapshot:
    """The copied facts, with a version and a hash so a run can say exactly what it was judged on."""

    def __init__(self, data: dict[str, list[dict[str, Any]]], taken_at: datetime) -> None:
        self.data = data
        self.taken_at = taken_at
        self.hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]

    @classmethod
    async def load(cls, db: Any, now: datetime) -> Snapshot:
        data: dict[str, list[dict[str, Any]]] = {}
        horizon = now + timedelta(hours=WINDOW_HOURS)
        for name in WHOLE:
            data[name] = await db[name].find({}).to_list(length=20_000)
        for name in WINDOWED:
            data[name] = await db[name].find({"endAt": {"$gt": now - timedelta(hours=12)}, "startAt": {"$lt": horizon}}).to_list(length=20_000)
        return cls(data, now)

    def reader(self, closed_rooms: set[str] | None = None) -> SnapshotReader:
        """A working copy: what one plan does to it is invisible to every other plan."""
        working = copy.deepcopy(self.data)
        for room in working["rooms"]:
            if room["_id"] in (closed_rooms or set()):
                room["status"] = "CLOSED"  # the incident has taken it out of use, for planning purposes
        return SnapshotReader(MemoryDb(working))


class SnapshotReader(LiveStateReader):
    def __init__(self, db: MemoryDb) -> None:
        super().__init__(db)
        self.memory = db

    def apply_move(self, session_id: str, room_id: str) -> None:
        for row in self.memory["timetable_sessions"].rows:
            if row["_id"] == session_id:
                row["roomId"] = room_id

    def apply_assignment(self, work_order_id: str, technician_id: str, start: datetime, end: datetime) -> None:
        for row in self.memory["work_orders"].rows:
            if row["_id"] == work_order_id:
                row.update({"assignedTechnicianId": technician_id, "status": "ASSIGNED", "scheduledStartAt": start, "scheduledEndAt": end})
