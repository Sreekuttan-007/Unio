from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.errors import BulkWriteError

from app.audit.service import AuditDomain, AuditService
from app.bookings.slots import SlotClaims, SlotTaken, aligned, slot_id, slot_starts
from app.bookings.state import BOOKING_MACHINE, LIVE, BookingEvent, BookingStatus
from app.collision.models import Acknowledgement, ActionType
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import IST, ensure_utc, local_time, utcnow
from app.core.errors import conflict, forbidden, not_found, rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.core.permission import Permission as P
from app.core.scope import EntityType, scope_filter
from app.core.state import try_guarded_update

MIN_MINUTES = 15
MAX_HOURS = 12
MAX_DAYS_AHEAD = 120
OPEN_INCIDENT = ("SUBMITTED", "UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS")


def check_window(start: datetime, end: datetime, now: datetime) -> None:
    if not (aligned(start) and aligned(end)):
        raise rule("INVALID_WINDOW", "Bookings run in 15 minute steps, so choose times like 09:00 or 09:15.")
    if end - start < timedelta(minutes=MIN_MINUTES):
        raise rule("INVALID_WINDOW", "A booking must last at least 15 minutes.")
    if end - start > timedelta(hours=MAX_HOURS):
        raise rule("INVALID_WINDOW", f"A booking cannot be longer than {MAX_HOURS} hours. Split it into two.")
    if end <= now:
        raise rule("INVALID_WINDOW", "That time is already over.")
    if start > now + timedelta(days=MAX_DAYS_AHEAD):
        raise rule("INVALID_WINDOW", f"Bookings open {MAX_DAYS_AHEAD} days ahead.")


def local_day_bounds(day: str | None, now: datetime) -> tuple[datetime, datetime, str]:
    """The UTC span of one campus-local day, and its date as text."""
    if day:
        try:
            date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            raise rule("INVALID_DATE", "Use a date like 2026-11-02.") from None
    else:
        date = (ensure_utc(now) + IST).date()
    start = datetime(date.year, date.month, date.day, tzinfo=UTC) - IST
    return start, start + timedelta(days=1), date.isoformat()


class BookingService:
    def __init__(self, db: Any, collisions: CollisionService, audit: AuditService, outbox: OutboxService, campus_id: str) -> None:
        self._db = db
        self._collisions = collisions
        self._audit = audit
        self._outbox = outbox
        self._campus_id = campus_id
        self.slots = SlotClaims(db)

    # ---- timetable claims ----------------------------------------------------------------------------

    async def claim_sessions(self) -> int:
        """Gives every scheduled class a claim on its slots, so a booking cannot take a class's room.

        One bulk insert. If two classes share a room (bad data, which the collision check reports),
        the first to insert keeps the slot and the other simply does not hold it.
        """
        pending = await self._db["timetable_sessions"].find({"status": "SCHEDULED", "slotsClaimed": {"$ne": True}}).to_list(length=20000)
        if not pending:
            return 0
        documents = [
            {"_id": slot_id(session["roomId"], slot), "roomId": session["roomId"], "slotStart": slot, "ownerKind": "SESSION", "ownerId": session["_id"]}
            for session in pending
            for slot in slot_starts(ensure_utc(session["startAt"]), ensure_utc(session["endAt"]))
        ]
        for offset in range(0, len(documents), 1000):
            try:
                await self._db["room_slots"].insert_many(documents[offset : offset + 1000], ordered=False)
            except BulkWriteError:
                pass  # slots that already exist stay with their holder
        await self._db["timetable_sessions"].update_many({"_id": {"$in": [session["_id"] for session in pending]}}, {"$set": {"slotsClaimed": True}})
        return len(pending)

    # ---- views ---------------------------------------------------------------------------------------------

    async def _room(self, room_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        room = await self._db["rooms"].find_one({"_id": room_id}) or {"_id": room_id, "code": room_id, "type": "UNKNOWN", "buildingId": ""}
        building = await self._db["buildings"].find_one({"_id": room.get("buildingId")}) or {"name": ""}
        return room, building

    def _actions(self, booking: dict[str, Any], user: AuthUser, now: datetime) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        available: list[dict[str, str]] = []
        unavailable: list[dict[str, str]] = []
        mine = booking["requesterId"] == user.id
        live = booking["status"] in LIVE
        over = ensure_utc(booking["endAt"]) <= now
        for key, label, wider in (("booking.reschedule", "Reschedule", P.BOOKING_COORDINATE), ("booking.cancel", "Cancel", P.BOOKING_CANCEL_ANY)):
            hint = {"key": key, "label": label}
            if not live:
                unavailable.append({**hint, "reason": f"This booking is already {booking['status'].lower()}."})
            elif over:
                unavailable.append({**hint, "reason": "This booking is already over."})
            elif not (mine or user.has(wider)):
                unavailable.append({**hint, "reason": "Only the person who booked it, or Facilities, can change it."})
            else:
                available.append(hint)
        return available, unavailable

    async def view(self, booking: dict[str, Any], user: AuthUser) -> dict[str, Any]:
        room, building = await self._room(booking["roomId"])
        available, unavailable = self._actions(booking, user, utcnow())
        return {
            "id": booking["_id"],
            "roomCode": room.get("code", booking["roomId"]),
            "roomType": room.get("type", ""),
            "building": building.get("name", ""),
            "purpose": booking.get("purpose") or "Booking",
            "start": ensure_utc(booking["startAt"]).isoformat(),
            "end": ensure_utc(booking["endAt"]).isoformat(),
            "status": booking["status"],
            "requester": booking["requesterName"],
            "headcount": booking["headcount"],
            "impact": booking.get("academicImpact"),
            "rescheduledCount": len(booking.get("history", [])),
            "availableActions": available,
            "unavailableActions": unavailable,
        }

    async def list(self, user: AuthUser, status: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"$and": [scope_filter(user, EntityType.BOOKING)]}
        if status:
            query["$and"].append({"status": status})
        rows = await self._db["bookings"].find(query).sort([("startAt", -1), ("_id", -1)]).to_list(length=300)
        return [await self.view(row, user) for row in rows]

    async def get(self, user: AuthUser, booking_id: str) -> dict[str, Any]:
        row = await self._db["bookings"].find_one({"$and": [{"_id": booking_id}, scope_filter(user, EntityType.BOOKING)]})
        if row is None:
            raise not_found("Booking")
        return row

    # ---- checking ------------------------------------------------------------------------------------------

    @staticmethod
    def _payload(room_code: str, start: datetime, end: datetime, headcount: int, kind: str, purpose: str, features: list[str], exclude_booking_id: str | None = None) -> dict[str, Any]:
        return {
            "roomId": room_code.strip().upper(), "startAt": start.isoformat(), "endAt": end.isoformat(), "headcount": headcount, "kind": kind,
            "purpose": purpose, "requiredFeatures": features, "excludeBookingId": exclude_booking_id,
        }

    async def check(
        self, user: AuthUser, room_code: str, start: datetime, end: datetime, headcount: int, kind: str, purpose: str, features: list[str], expected_state_token: str | None = None,
    ) -> dict[str, Any]:
        start, end = ensure_utc(start), ensure_utc(end)
        check_window(start, end, utcnow())
        payload = self._payload(room_code, start, end, headcount, kind, purpose, features)
        result = await self._collisions.check(user, ActionType.BOOK_ROOM, payload, expected_state_token)
        in_the_way = await self._collisions.reader().room_occupancy(payload["roomId"], start, end)
        rooms = []
        for alternative in (item for item in result["alternatives"] if item["kind"] == "ROOM"):
            room, building = await self._room(alternative["roomId"])
            rooms.append({"roomCode": room["code"], "type": room["type"], "capacity": room["capacity"], "building": building.get("name", ""), "fit": alternative["reason"]})
        times = [
            {"label": item["label"], "start": item["apply"]["startAt"], "end": item["apply"]["endAt"], "reason": item["reason"]}
            for item in result["alternatives"]
            if item["kind"] == "TIME"
        ]
        return {
            "allowed": result["decision"] == "ALLOW",
            "decision": result["decision"],
            "findings": [{key: finding[key] for key in ("code", "severity", "message", "affected")} for finding in result["findings"]],
            "alternatives": rooms,
            "timeAlternatives": times,
            "affectedClasses": [
                {"course": item["label"], "group": item["detail"].split(",")[0] if item["kind"] == "SESSION" else item["detail"], "headcount": item["headcount"], "start": local_time(item["startAt"]), "end": local_time(item["endAt"]), "kind": item["kind"]}
                for item in in_the_way
            ],
            "requiresReason": result["requiresReason"],
            "requiresApproval": result["requiresApproval"],
            "stateToken": result["stateToken"],
            "checkId": result["checkId"],
        }

    # ---- creating ----------------------------------------------------------------------------------------------

    async def create(
        self, user: AuthUser, room_code: str, start: datetime, end: datetime, headcount: int, kind: str, purpose: str, features: list[str],
        acknowledgement: Acknowledgement | None, expected_state_token: str | None,
    ) -> dict[str, Any]:
        start, end = ensure_utc(start), ensure_utc(end)
        check_window(start, end, utcnow())
        payload = self._payload(room_code, start, end, headcount, kind, purpose, features)
        decision = await self._collisions.enforce(user, ActionType.BOOK_ROOM, payload, acknowledgement=acknowledgement, expected_state_token=expected_state_token)
        room_id = payload["roomId"]
        booking_id = await next_id(self._db, "BK", 2300)
        try:
            await self.slots.claim("BOOKING", booking_id, room_id, start, end)
        except SlotTaken:
            raise conflict("SLOT_TAKEN", f"{room_id} was just booked by someone else for part of that time. Check availability again.") from None
        now = utcnow()
        booking = {
            "_id": booking_id, "roomId": room_id, "requesterId": user.id, "requesterName": user.name, "departmentId": user.department_id, "campusId": self._campus_id,
            "startAt": start, "endAt": end, "purpose": purpose.strip(), "headcount": headcount, "academicImpact": kind, "status": BookingStatus.CONFIRMED.value,
            "history": [], "collisionCheckId": decision["checkId"], "version": 0, "createdAt": now, "updatedAt": now,
        }
        try:
            await self._db["bookings"].insert_one(booking)
        except BaseException:
            await self.slots.release(booking_id)
            raise
        await self._audit.record_as(
            user, action="booking.create", domain=AuditDomain.OPERATIONS, entity_type="BOOKING", entity_id=booking_id,
            after={"roomId": room_id, "startAt": start.isoformat(), "endAt": end.isoformat(), "collisionCheckId": decision["checkId"]},
        )
        await self._outbox.enqueue("booking.confirmed", {"bookingId": booking_id, "roomId": room_id, "recipientIds": [user.id]})
        return await self.view(booking, user)

    # ---- changing -------------------------------------------------------------------------------------------------

    def _may_change(self, booking: dict[str, Any], user: AuthUser, wider: P) -> None:
        if booking["requesterId"] != user.id and not user.has(wider):
            raise forbidden()

    async def cancel(self, user: AuthUser, booking_id: str) -> dict[str, Any]:
        booking = await self.get(user, booking_id)
        self._may_change(booking, user, P.BOOKING_CANCEL_ANY)
        current = BookingStatus(booking["status"])
        target = BOOKING_MACHINE.next(current, BookingEvent.CANCEL)
        if ensure_utc(booking["endAt"]) <= utcnow():
            raise rule("ALREADY_OVER", "This booking is already over, so there is nothing to cancel.")
        update = {"$set": {"status": target.value, "cancelledAt": utcnow(), "cancelledBy": user.id}}
        if not await try_guarded_update(self._db["bookings"], booking_id, booking["version"], current, update):
            raise conflict("VERSION_CONFLICT", "This booking changed. Reload it and try again.")
        await self.slots.release(booking_id)
        await self._audit.record_as(user, action="booking.cancel", domain=AuditDomain.OPERATIONS, entity_type="BOOKING", entity_id=booking_id, before={"status": current.value}, after={"status": target.value})
        await self._outbox.enqueue("booking.cancelled", {"bookingId": booking_id, "roomId": booking["roomId"], "recipientIds": sorted({booking["requesterId"], user.id})})
        return await self.view(await self._db["bookings"].find_one({"_id": booking_id}), user)

    async def reschedule(
        self, user: AuthUser, booking_id: str, room_code: str | None, start: datetime, end: datetime, headcount: int | None,
        acknowledgement: Acknowledgement | None, expected_state_token: str | None,
    ) -> dict[str, Any]:
        booking = await self.get(user, booking_id)
        self._may_change(booking, user, P.BOOKING_COORDINATE)
        current = BookingStatus(booking["status"])
        target = BOOKING_MACHINE.next(current, BookingEvent.RESCHEDULE)
        start, end = ensure_utc(start), ensure_utc(end)
        check_window(start, end, utcnow())
        room_id = (room_code or booking["roomId"]).strip().upper()
        people = headcount or booking["headcount"]
        payload = self._payload(room_id, start, end, people, booking.get("academicImpact") or "LECTURE", booking.get("purpose", ""), [], exclude_booking_id=booking_id)
        decision = await self._collisions.enforce(user, ActionType.BOOK_ROOM, payload, acknowledgement=acknowledgement, expected_state_token=expected_state_token)
        before_ids = {row["_id"] async for row in self._db["room_slots"].find({"ownerId": booking_id})}
        after_ids = {slot_id(room_id, slot) for slot in slot_starts(start, end)}
        try:
            await self.slots.claim("BOOKING", booking_id, room_id, start, end)
        except SlotTaken:
            raise conflict("SLOT_TAKEN", f"{room_id} was just booked by someone else for part of that time. Your original booking is unchanged.") from None
        history = {"roomId": booking["roomId"], "startAt": booking["startAt"], "endAt": booking["endAt"], "at": utcnow(), "by": user.id}
        update = {
            "$set": {"roomId": room_id, "startAt": start, "endAt": end, "headcount": people, "status": target.value, "collisionCheckId": decision["checkId"]},
            "$push": {"history": history},
        }
        if not await try_guarded_update(self._db["bookings"], booking_id, booking["version"], current, update):
            await self._db["room_slots"].delete_many({"_id": {"$in": sorted(after_ids - before_ids)}, "ownerId": booking_id})
            raise conflict("VERSION_CONFLICT", "This booking changed. Reload it and try again.")
        await self.slots.release(booking_id, keep=after_ids)
        await self._audit.record_as(
            user, action="booking.reschedule", domain=AuditDomain.OPERATIONS, entity_type="BOOKING", entity_id=booking_id,
            before={"roomId": booking["roomId"], "startAt": ensure_utc(booking["startAt"]).isoformat()}, after={"roomId": room_id, "startAt": start.isoformat(), "endAt": end.isoformat()},
        )
        await self._outbox.enqueue("booking.rescheduled", {"bookingId": booking_id, "roomId": room_id, "recipientIds": sorted({booking["requesterId"], user.id})})
        return await self.view(await self._db["bookings"].find_one({"_id": booking_id}), user)

    # ---- the timetable -----------------------------------------------------------------------------------------------

    async def _recipients(self, session: dict[str, Any]) -> list[str]:
        faculty = await self._db["faculty"].find_one({"_id": session["facultyId"]})
        group = await self._db["student_groups"].find_one({"_id": session["studentGroup"]})
        people = [(faculty or {}).get("userId"), *(group or {}).get("memberUserIds", [])]
        return sorted({person for person in people if person})

    async def move_session(
        self, user: AuthUser, session_id: str, room_code: str | None, start: datetime | None, end: datetime | None,
        acknowledgement: Acknowledgement | None, expected_state_token: str | None,
    ) -> dict[str, Any]:
        session = await self._db["timetable_sessions"].find_one({"_id": session_id, "campusId": self._campus_id})
        if session is None or session["status"] != "SCHEDULED":
            raise not_found("Session")
        old_start, old_end = ensure_utc(session["startAt"]), ensure_utc(session["endAt"])
        new_start, new_end = ensure_utc(start) if start else old_start, ensure_utc(end) if end else old_end
        room_id = (room_code or session["roomId"]).strip().upper()
        if (room_id, new_start, new_end) == (session["roomId"], old_start, old_end):
            raise rule("NOTHING_TO_MOVE", "The session is already there.")
        check_window(new_start, new_end, utcnow())
        payload = self._payload(room_id, new_start, new_end, session["headcount"], session["kind"], session["courseName"], [])
        payload["excludeSessionId"] = session_id
        decision = await self._collisions.enforce(user, ActionType.MOVE_SESSION, payload, acknowledgement=acknowledgement, expected_state_token=expected_state_token)
        before_ids = {row["_id"] async for row in self._db["room_slots"].find({"ownerId": session_id})}
        after_ids = {slot_id(room_id, slot) for slot in slot_starts(new_start, new_end)}
        try:
            await self.slots.claim("SESSION", session_id, room_id, new_start, new_end)
        except SlotTaken:
            raise conflict("SLOT_TAKEN", f"{room_id} was just taken for part of that time. The class has not moved.") from None
        moved = await self._db["timetable_sessions"].update_one(
            {"_id": session_id, "roomId": session["roomId"], "startAt": session["startAt"]},
            {"$set": {"roomId": room_id, "startAt": new_start, "endAt": new_end, "slotsClaimed": True, "movedFrom": {"roomId": session["roomId"], "startAt": old_start, "endAt": old_end, "at": utcnow(), "by": user.id}}},
        )
        if moved.modified_count != 1:
            await self._db["room_slots"].delete_many({"_id": {"$in": sorted(after_ids - before_ids)}, "ownerId": session_id})
            raise conflict("VERSION_CONFLICT", "This class was changed by someone else. Reload and try again.")
        await self.slots.release(session_id, keep=after_ids)
        recipients = await self._recipients(session)
        await self._audit.record_as(
            user, action="session.move", domain=AuditDomain.OPERATIONS, entity_type="SESSION", entity_id=session_id,
            before={"roomId": session["roomId"], "startAt": old_start.isoformat()}, after={"roomId": room_id, "startAt": new_start.isoformat(), "collisionCheckId": decision["checkId"]},
        )
        await self._outbox.enqueue(
            "session.moved",
            {"sessionId": session_id, "course": session["courseName"], "fromRoom": session["roomId"], "toRoom": room_id, "startAt": new_start.isoformat(), "recipientIds": recipients},
        )
        return {"id": session_id, "course": session["courseName"], "room": room_id, "start": local_time(new_start), "end": local_time(new_end), "notified": len(recipients)}

    async def disrupted_rooms(self) -> dict[str, str]:
        """Rooms that cannot be used as planned right now, with the reason in words."""
        reasons: dict[str, str] = {}
        for room in await self._db["rooms"].find({"status": {"$ne": "OPEN"}}).to_list(length=500):
            reasons[room["_id"]] = f"{room['code']} is {room['status'].lower()}."
        closed = {row["_id"]: row["name"] async for row in self._db["buildings"].find({"status": {"$ne": "OPEN"}})}
        if closed:
            for room in await self._db["rooms"].find({"buildingId": {"$in": list(closed)}}).to_list(length=500):
                reasons.setdefault(room["_id"], f"{closed[room['buildingId']]} is closed.")
        for incident in await self._db["incidents"].find({"status": {"$in": list(OPEN_INCIDENT)}, "priority": {"$in": ["P1", "P2"]}}).to_list(length=100):
            for code in set(incident.get("roomCodes", [])) | set(incident.get("impactRoomIds", [])):
                reasons.setdefault(code, f"{code} is affected by {incident['_id']}: {incident['title']}.")
        return reasons

    async def _sessions_for(self, user: AuthUser, start: datetime, end: datetime) -> list[dict[str, Any]]:
        window: dict[str, Any] = {"campusId": self._campus_id, "status": "SCHEDULED", "startAt": {"$gte": start, "$lt": end}}
        if user.has(P.BOOKING_READ_CAMPUS):
            scope: dict[str, Any] = {}
        elif user.managed_department_ids:
            scope = {"departmentId": {"$in": list(user.managed_department_ids)}}
        else:
            faculty = await self._db["faculty"].find_one({"userId": user.id})
            groups = [row["_id"] async for row in self._db["student_groups"].find({"memberUserIds": user.id})]
            options = ([{"facultyId": faculty["_id"]}] if faculty else []) + ([{"studentGroup": {"$in": groups}}] if groups else [])
            if not options:
                return []
            scope = {"$or": options}
        return await self._db["timetable_sessions"].find({**window, **scope}).sort([("startAt", 1), ("_id", 1)]).to_list(length=300)

    async def today(self, user: AuthUser, day: str | None = None) -> list[dict[str, Any]]:
        start, end, _ = local_day_bounds(day, utcnow())
        sessions = await self._sessions_for(user, start, end)
        disrupted = await self.disrupted_rooms()
        out = []
        for session in sessions:
            reason = disrupted.get(session["roomId"])
            alternative = await self.alternative_room(session, set(disrupted)) if reason else None
            out.append(
                {
                    "id": session["_id"], "course": session["courseName"], "room": session["roomId"], "start": local_time(session["startAt"]), "end": local_time(session["endAt"]),
                    "group": session["studentGroup"], "headcount": session["headcount"], "kind": session["kind"], "status": "AFFECTED" if reason else "NORMAL", "note": reason, "alternative": alternative,
                }
            )
        return out

    async def alternative_room(self, session: dict[str, Any], avoid: set[str]) -> dict[str, str] | None:
        """The best free room for a class whose own room is out, skipping rooms that are affected too."""
        action = self._collisions.build_action(None, ActionType.MOVE_SESSION, {**self._payload(session["roomId"], ensure_utc(session["startAt"]), ensure_utc(session["endAt"]), session["headcount"], session["kind"], session["courseName"], []), "excludeSessionId": session["_id"]}, None)
        for suggestion in await self._collisions.alternatives.rooms(action, self._collisions.reader(), await self._collisions.config()):
            if suggestion["roomId"] not in avoid:
                return {"roomCode": suggestion["roomId"], "note": suggestion["reason"].rstrip(".")}
        return None

    async def affected(self, room_ids: list[str], start: datetime, end: datetime) -> dict[str, Any]:
        """Classes that would lose their room if these rooms were unavailable in this window."""
        start, end = ensure_utc(start), ensure_utc(end)
        rows = await self._db["timetable_sessions"].find(
            {"roomId": {"$in": room_ids}, "status": "SCHEDULED", "startAt": {"$lt": end}, "endAt": {"$gt": start}, "campusId": self._campus_id}
        ).sort([("startAt", 1), ("_id", 1)]).to_list(length=300)
        sessions = []
        for row in rows:
            faculty = await self._db["faculty"].find_one({"_id": row["facultyId"]})
            sessions.append(
                {
                    "id": row["_id"], "course": row["courseName"], "group": row["studentGroup"], "headcount": row["headcount"], "room": row["roomId"], "kind": row["kind"],
                    "start": ensure_utc(row["startAt"]).isoformat(), "end": ensure_utc(row["endAt"]).isoformat(), "faculty": (faculty or {}).get("name", ""),
                }
            )
        return {
            "sessions": sessions,
            "totals": {"sessions": len(sessions), "exams": sum(1 for item in sessions if item["kind"] == "EXAM"), "people": sum(item["headcount"] for item in sessions)},
        }
