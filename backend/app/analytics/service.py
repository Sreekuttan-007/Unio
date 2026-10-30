"""Operational analytics, counted from stored records only. Nothing here is estimated or invented."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.core.authuser import AuthUser
from app.bookings.service import local_day_bounds
from app.core.clock import ensure_utc, utcnow
from app.core.permission import Permission as P
from app.sla.service import evaluate

OPEN = ("SUBMITTED", "UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS")
OPEN_HOURS = 14  # 07:00 to 21:00, the academic buildings' opening hours
RECURRING_DAYS = 90


def _pct(part: float, whole: float) -> int:
    return round(part / whole * 100) if whole else 0


def _overlap_minutes(start: datetime, end: datetime, lo: datetime, hi: datetime) -> float:
    return max(0.0, (min(ensure_utc(end), hi) - max(ensure_utc(start), lo)).total_seconds() / 60)


def local_day_start(now: datetime) -> datetime:
    return local_day_bounds(None, now)[0]


class AnalyticsService:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def overview(self, user: AuthUser, now: datetime | None = None) -> dict[str, Any]:
        now = ensure_utc(now or utcnow())
        scope: dict[str, Any] = {}
        if not user.has_any((P.ANALYTICS_READ_CAMPUS, P.ANALYTICS_READ_SYSTEM, P.ANALYTICS_READ_PROCUREMENT)):
            scope = {"departmentId": {"$in": list(user.managed_department_ids)}}
        incidents = await self._db["incidents"].find({**scope, "duplicateOf": None}).to_list(length=5000)
        open_rows = [row for row in incidents if row["status"] in OPEN]

        sla_rows = await self._db["sla_instances"].find(scope).to_list(length=5000)
        closed = [row for row in sla_rows if row.get("resolvedAt")]
        met = [row for row in closed if evaluate(row)["state"] == "MET"]
        trend = []
        for back in range(6, -1, -1):
            day = local_day_start(now) - timedelta(days=back)
            within = [row for row in closed if day <= ensure_utc(row["resolvedAt"]) < day + timedelta(days=1)]
            trend.append(_pct(sum(1 for row in within if evaluate(row)["state"] == "MET"), len(within)) if within else None)
        by_priority = []
        for priority in ("P1", "P2", "P3", "P4"):
            mine = [row for row in closed if row["priority"] == priority]
            if mine:
                by_priority.append({"label": priority, "value": _pct(sum(1 for row in mine if evaluate(row)["state"] == "MET"), len(mine))})

        day_start = local_day_start(now)
        day_end = day_start + timedelta(days=1)
        rooms = await self._db["rooms"].find({"bookable": True}).to_list(length=2000)
        buildings = {row["_id"]: row["name"] async for row in self._db["buildings"].find({})}
        per_building = Counter(room["buildingId"] for room in rooms)
        room_building = {room["_id"]: room["buildingId"] for room in rooms}
        used: Counter[str] = Counter()
        for name in ("timetable_sessions", "bookings"):
            async for row in self._db[name].find({"startAt": {"$lt": day_end}, "endAt": {"$gt": day_start}, "status": {"$in": ["SCHEDULED", "CONFIRMED", "RESCHEDULED"]}}):
                if row["roomId"] in room_building:
                    used[room_building[row["roomId"]]] += _overlap_minutes(row["startAt"], row["endAt"], day_start, day_end)
        room_use = sorted(
            ({"label": buildings.get(b, b), "value": _pct(used[b], per_building[b] * OPEN_HOURS * 60)} for b in per_building), key=lambda item: -item["value"]
        )[:6]

        technicians = await self._db["technicians"].find({}).sort("_id", 1).to_list(length=100)
        tech_use = []
        for tech in technicians:
            shift = sum([_overlap_minutes(row["startAt"], row["endAt"], day_start, day_end) async for row in self._db["shifts"].find({"technicianId": tech["_id"], "startAt": {"$lt": day_end}, "endAt": {"$gt": day_start}})])
            busy = sum(
                [
                    _overlap_minutes(row["scheduledStartAt"], row["scheduledEndAt"], day_start, day_end)
                    async for row in self._db["work_orders"].find({"assignedTechnicianId": tech["_id"], "scheduledStartAt": {"$ne": None, "$lt": day_end}, "scheduledEndAt": {"$gt": day_start}})
                ]
            )
            tech_use.append({"label": tech["name"], "value": _pct(busy, shift)})

        items = {row["_id"]: row async for row in self._db["inventory_items"].find({})}
        on_hand: Counter[str] = Counter()
        async for row in self._db["inventory_balances"].find({}):
            on_hand[row["itemId"]] += row["onHand"] - row["reserved"]
        blocked: Counter[str] = Counter()
        async for order in self._db["work_orders"].find({"status": "BLOCKED"}):
            for part in order.get("partRequirements", []):
                if part["state"] == "SHORT":
                    blocked[part["itemId"]] += 1
        shortages = sorted(
            ({"name": item["name"], "onHand": max(0, on_hand[item_id]), "threshold": item["reorderThreshold"], "blocked": blocked[item_id]} for item_id, item in items.items() if on_hand[item_id] <= item["reorderThreshold"]),
            key=lambda row: (-row["blocked"], row["onHand"] - row["threshold"], row["name"]),
        )[:8]

        since = now - timedelta(days=RECURRING_DAYS)
        repeats: Counter[tuple[str, str]] = Counter()
        last: dict[tuple[str, str], datetime] = {}
        async for row in self._db["maintenance_history"].find({"completedAt": {"$gte": since}, "roomId": {"$ne": None}}):
            key = (row["category"], row["roomId"])
            repeats[key] += 1
            last[key] = max(last.get(key, ensure_utc(row["completedAt"])), ensure_utc(row["completedAt"]))
        recurring = [
            {"name": f"{category.title()} faults", "location": room, "count": count, "last": last[(category, room)].date().isoformat()}
            for (category, room), count in repeats.most_common() if count >= 2
        ][:8]

        daily = []
        for back in range(13, -1, -1):
            day = local_day_start(now) - timedelta(days=back)
            daily.append({"label": (day + timedelta(hours=6)).strftime("%d %b"), "value": sum(1 for row in incidents if day <= ensure_utc(row["createdAt"]) < day + timedelta(days=1))})

        return {
            "open": {
                "total": len(open_rows),
                "byStatus": [{"label": status.replace("_", " ").title(), "value": count} for status, count in Counter(row["status"] for row in open_rows).most_common()],
                "byCategory": [{"label": category.title(), "value": count} for category, count in Counter(row["category"] for row in open_rows).most_common()],
            },
            "sla": {"rate": _pct(len(met), len(closed)) if closed else 100, "trend": [value for value in trend if value is not None], "byPriority": by_priority},
            "utilisation": {"rooms": room_use, "technicians": tech_use},
            "shortages": shortages,
            "recurring": recurring,
            "daily": daily,
        }
