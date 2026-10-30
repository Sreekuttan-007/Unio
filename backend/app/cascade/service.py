"""What an incident breaks: assets, rooms, classes and people, each with the reason it is affected.

Everything in an impact chain is a stored record reached through a stored dependency edge or a
timetable entry. Nothing is guessed. Snapshots are derived data and can be recomputed at any time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.bookings.service import OPEN_INCIDENT, BookingService
from app.cascade.graph import Reached, walk
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, local_time, utcnow
from app.core.errors import not_found, rule
from app.core.permission import Permission as P
from app.incidents.service import IncidentService

# How far ahead an outage is assumed to disturb the timetable, and how old a snapshot may get before a read refreshes it.
HORIZON_HOURS = 24
STALE_AFTER = timedelta(minutes=15)
RELATION_WORDS = {"POWERS": "powered by", "CONNECTS": "connected through", "SERVES": "covered by"}
OUTCOME = {"POWERS": "loses power", "CONNECTS": "loses its network", "SERVES": "loses Wi-Fi"}
EMPTY_TOTALS = {"rooms": 0, "sessions": 0, "exams": 0, "people": 0, "workOrders": 0}


def severity(criticality: int) -> str:
    return "HIGH" if criticality >= 4 else "MEDIUM" if criticality == 3 else "LOW"


def rank_sessions(sessions: list[dict[str, Any]], room_depth: dict[str, int]) -> list[dict[str, Any]]:
    """Exams first, then the most directly affected, then the most people, then the soonest."""
    return sorted(sessions, key=lambda row: (row["kind"] != "EXAM", room_depth.get(row["roomId"], 99), -row["headcount"], ensure_utc(row["startAt"]), row["_id"]))


class CascadeService:
    def __init__(self, db: Any, incidents: IncidentService, bookings: BookingService, audit: AuditService, campus_id: str) -> None:
        self._db = db
        self._incidents = incidents
        self._bookings = bookings
        self._audit = audit
        self._campus_id = campus_id

    # ---- computing --------------------------------------------------------------------------------------------

    async def compute(self, incident: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        now = ensure_utc(now or utcnow())
        incident_id = incident["_id"]
        if incident["status"] not in OPEN_INCIDENT:
            return {"incidentId": incident_id, "chain": [], "totals": dict(EMPTY_TOTALS), "affectedSessions": [], "affectedRegionIds": [], "roomIds": [], "recipientUserIds": [], "computedAt": now}
        roots = [("ASSET", asset_id) for asset_id in incident.get("assetIds", [])] + [("ROOM", code) for code in incident.get("roomCodes", [])]
        edges = await self._db["dependency_edges"].find({"campusId": self._campus_id, "active": True}).to_list(length=20_000)
        reached = walk(edges, roots)
        asset_ids = [node.id for node in reached if node.kind == "ASSET"]
        room_depth = {node.id: node.depth for node in reached if node.kind == "ROOM"}
        assets = {row["_id"]: row async for row in self._db["assets"].find({"_id": {"$in": asset_ids}})}
        rooms = {row["_id"]: row async for row in self._db["rooms"].find({"_id": {"$in": list(room_depth)}})}
        # Only what exists is reported; an edge to a missing record is dropped, never invented.
        reached = [node for node in reached if (node.kind == "ASSET" and node.id in assets) or (node.kind == "ROOM" and node.id in rooms)]
        room_depth = {room_id: depth for room_id, depth in room_depth.items() if room_id in rooms}

        sessions = await self._db["timetable_sessions"].find(
            {"campusId": self._campus_id, "status": "SCHEDULED", "roomId": {"$in": list(room_depth)}, "endAt": {"$gt": now}, "startAt": {"$lt": now + timedelta(hours=HORIZON_HOURS)}}
        ).to_list(length=1000)
        sessions = rank_sessions(sessions, room_depth)
        orders = await self._db["work_orders"].find({"incidentId": incident_id, "status": {"$nin": ["COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"]}}).sort("_id", 1).to_list(length=20)

        chain = self._chain(incident, reached, assets, rooms, sessions, orders)
        affected = []
        for row in sessions[:40]:
            affected.append(
                {
                    "id": row["_id"], "course": row["courseName"], "group": row["studentGroup"], "room": row["roomId"], "start": local_time(row["startAt"]), "end": local_time(row["endAt"]),
                    "startAt": ensure_utc(row["startAt"]).isoformat(), "kind": row["kind"], "headcount": row["headcount"], "facultyId": row.get("facultyId"), "departmentId": row.get("departmentId"),
                    "alternative": await self._bookings.alternative_room(row, set(room_depth)),
                }
            )
        buildings = {row["buildingId"] for row in rooms.values()} | {row["buildingId"] for row in assets.values()}
        regions = sorted({row["mapRegionId"] async for row in self._db["buildings"].find({"_id": {"$in": sorted(buildings)}})})
        return {
            "incidentId": incident_id,
            "chain": chain,
            "totals": {
                "rooms": len(room_depth), "sessions": len(sessions), "exams": sum(1 for row in sessions if row["kind"] == "EXAM"),
                "people": sum(row["headcount"] for row in sessions), "workOrders": len(orders),
            },
            "affectedSessions": affected,
            "affectedRegionIds": regions,
            "roomIds": sorted(room_depth),
            "recipientUserIds": await self._recipients(sessions),
            "computedAt": now,
        }

    def _chain(
        self, incident: dict[str, Any], reached: list[Reached], assets: dict[str, Any], rooms: dict[str, Any], sessions: list[dict[str, Any]], orders: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        depth_of: dict[str, int] = {}
        for node in reached:
            if node.kind != "ASSET":
                continue
            asset = assets[node.id]
            depth_of[node.id] = node.depth
            if node.depth == 0:
                chain.append({"id": node.id, "depth": 0, "kind": "Fault", "title": f"{asset['name']} ({node.id})", "detail": f"Root of {incident['_id']}", "severity": severity(asset.get("criticality", 3))})
            else:
                parent = assets.get(node.via_id or "", {}).get("name", node.via_id)
                chain.append(
                    {"id": node.id, "depth": node.depth, "kind": "Asset", "title": f"{asset['name']} {OUTCOME.get(node.relation or '', 'is affected')}", "detail": node.id,
                     "severity": severity(asset.get("criticality", 3)), "reason": f"{RELATION_WORDS.get(node.relation or '', 'depends on')} {parent}"}
                )
        # Rooms are grouped by what reached them, so a transformer fault is a handful of lines, not a hundred.
        groups: dict[tuple[str | None, str | None, int], list[str]] = {}
        for node in reached:
            if node.kind == "ROOM":
                groups.setdefault((node.via_id, node.relation, node.depth), []).append(node.id)
        for (via, relation, depth), codes in sorted(groups.items(), key=lambda item: (item[0][2], item[0][0] or "")):
            codes.sort()
            if via is None:
                chain.append({"id": f"rooms-reported-{depth}", "depth": 0, "kind": "Rooms", "title": f"{', '.join(codes)} reported", "detail": f"{len(codes)} {'room' if len(codes) == 1 else 'rooms'}", "severity": "MEDIUM"})
                continue
            parent = assets.get(via, {}).get("name", via)
            title = codes[0] if len(codes) == 1 else f"{codes[0]} to {codes[-1]}" if len(codes) > 3 else ", ".join(codes)
            chain.append(
                {"id": f"rooms-{via}-{relation}", "depth": depth, "kind": "Rooms", "title": f"{title} {OUTCOME.get(relation or '', 'affected').replace('loses', 'lose')}",
                 "detail": f"{len(codes)} {'room' if len(codes) == 1 else 'rooms'}", "severity": "HIGH" if relation == "POWERS" else "MEDIUM", "reason": f"{RELATION_WORDS.get(relation or '', 'depends on')} {parent}"}
            )
        deepest_room = max((node.depth for node in reached if node.kind == "ROOM"), default=0)
        for row in sessions:
            if row["kind"] == "EXAM":
                chain.append(
                    {"id": row["_id"], "depth": deepest_room + 1, "kind": "Exam", "title": f"{row['studentGroup']} {row['courseName']} exam, {row['roomId']}, {local_time(row['startAt'])} to {local_time(row['endAt'])}",
                     "detail": f"{row['headcount']} students", "severity": "HIGH", "reason": "scheduled in an affected room"}
                )
        classes = [row for row in sessions if row["kind"] != "EXAM"]
        if classes:
            people = sum(row["headcount"] for row in classes)
            chain.append(
                {"id": "sessions", "depth": deepest_room + 1, "kind": "Sessions", "title": f"{len(classes)} {'class' if len(classes) == 1 else 'classes'} in the next {HORIZON_HOURS} hours",
                 "detail": f"{people} students", "severity": "MEDIUM", "reason": "scheduled in affected rooms"}
            )
        for order in orders:
            chain.append(
                {"id": order["_id"], "depth": deepest_room + 2, "kind": "Work", "title": f"{order['_id']} {order['title']}", "detail": order["status"].replace("_", " ").lower(),
                 "severity": "HIGH" if order["status"] == "BLOCKED" else "LOW", "reason": "needed to restore service"}
            )
        return chain

    async def _recipients(self, sessions: list[dict[str, Any]]) -> list[str]:
        """Only the people in those classes: their lecturers and the students in their groups."""
        faculty_ids = sorted({row["facultyId"] for row in sessions if row.get("facultyId")})
        groups = sorted({row["studentGroup"] for row in sessions})
        users = {row["userId"] async for row in self._db["faculty"].find({"_id": {"$in": faculty_ids}}) if row.get("userId")}
        async for group in self._db["student_groups"].find({"_id": {"$in": groups}}):
            users.update(group.get("memberUserIds", []))
        return sorted(users)

    # ---- snapshots ---------------------------------------------------------------------------------------------

    async def refresh(self, incident_id: str, now: datetime | None = None) -> dict[str, Any]:
        incident = await self._db["incidents"].find_one({"_id": incident_id})
        if incident is None:
            raise not_found("Incident")
        snapshot = await self.compute(incident, now)
        await self._db["impact_snapshots"].replace_one({"_id": incident_id}, {"_id": incident_id, **snapshot}, upsert=True)
        totals = snapshot["totals"]
        # impactRoomIds keeps rooms affected by this incident out of booking and move suggestions.
        await self._db["incidents"].update_one(
            {"_id": incident_id},
            {"$set": {"impact": {key: totals[key] for key in ("rooms", "sessions", "exams", "people")}, "impactRoomIds": snapshot["roomIds"]}},
        )
        return snapshot

    async def impact(self, user: AuthUser, incident_id: str) -> dict[str, Any]:
        await self._incidents.get(user, incident_id)  # the caller must be able to see the incident
        snapshot = await self._db["impact_snapshots"].find_one({"_id": incident_id})
        if snapshot is None or utcnow() - ensure_utc(snapshot["computedAt"]) > STALE_AFTER:
            snapshot = await self.refresh(incident_id)
        return self.view(snapshot)

    @staticmethod
    def view(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "incidentId": snapshot["incidentId"], "chain": snapshot["chain"], "totals": snapshot["totals"], "affectedRegionIds": snapshot["affectedRegionIds"],
            "affectedSessions": [{key: value for key, value in row.items() if key not in ("facultyId", "departmentId", "startAt")} for row in snapshot["affectedSessions"]],
            "computedAt": ensure_utc(snapshot["computedAt"]).isoformat(),
        }

    async def recompute(self, user: AuthUser, incident_id: str, root_asset_ids: list[str] | None) -> dict[str, Any]:
        """Recomputes now. Triage may also name the faulty asset, which is what makes the chain reach beyond the reported rooms."""
        incident = await self._incidents.get(user, incident_id)
        if root_asset_ids is not None:
            found = {row["_id"] async for row in self._db["assets"].find({"_id": {"$in": root_asset_ids}, "campusId": self._campus_id})}
            missing = sorted(set(root_asset_ids) - found)
            if missing:
                raise rule("UNKNOWN_ASSET", f"There is no asset {missing[0]}.")
            await self._db["incidents"].update_one({"_id": incident_id}, {"$set": {"assetIds": sorted(found), "updatedAt": utcnow()}, "$inc": {"version": 1}})
            await self._audit.record_as(
                user, action="incident.root_assets", domain=AuditDomain.OPERATIONS, entity_type="INCIDENT", entity_id=incident_id,
                before={"assetIds": incident.get("assetIds", [])}, after={"assetIds": sorted(found)},
            )
        return self.view(await self.refresh(incident_id))

    async def academic(self, user: AuthUser) -> list[dict[str, Any]]:
        """Classes hit by open incidents, limited to the classes this person teaches, manages or attends."""
        scope: dict[str, Any] | None = None
        if not user.has(P.BOOKING_READ_CAMPUS):
            if user.managed_department_ids:
                departments = set(user.managed_department_ids)
                scope = {"departments": departments}
            else:
                faculty = await self._db["faculty"].find_one({"userId": user.id})
                groups = {row["_id"] async for row in self._db["student_groups"].find({"memberUserIds": user.id})}
                scope = {"faculty": (faculty or {}).get("_id"), "groups": groups}
        out = []
        open_ids = [row["_id"] async for row in self._db["incidents"].find({"status": {"$in": list(OPEN_INCIDENT)}}, {"_id": 1})]
        async for snapshot in self._db["impact_snapshots"].find({"_id": {"$in": open_ids}}).sort("_id", 1):
            rows = snapshot["affectedSessions"]
            if scope is not None:
                rows = [
                    row for row in rows
                    if row.get("departmentId") in scope.get("departments", set()) or (scope.get("faculty") and row.get("facultyId") == scope["faculty"]) or row["group"] in scope.get("groups", set())
                ]
            if rows:
                incident = await self._db["incidents"].find_one({"_id": snapshot["_id"]}, {"title": 1, "priority": 1})
                out.append({"incidentId": snapshot["_id"], "title": (incident or {}).get("title", ""), "priority": (incident or {}).get("priority"), "sessions": self.view({**snapshot, "affectedSessions": rows})["affectedSessions"]})
        return out
