"""Phase 6: room bookings that cannot double-book, affected classes, alternatives, and the timetable."""

import asyncio
from datetime import timedelta

import pytest
import pytest_asyncio

from app.bookings.slots import SlotClaims, SlotTaken, slot_id
from app.core.clock import utcnow
from tests.conftest import open_env

BASE = (utcnow() + timedelta(days=45)).replace(hour=4, minute=0, second=0, microsecond=0)  # 09:30 campus time


def at(hours: float) -> str:
    return (BASE + timedelta(hours=hours)).isoformat()


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        yield opened


def request(room="ARB-204", start=0, end=2, **extra):
    return {"roomCode": room, "start": at(start), "end": at(end), "headcount": 30, "purpose": "Revision class", **extra}


async def book(env, role="FACULTY", **kwargs):
    return await env.call(role, "POST", "/api/v1/bookings", json=request(**kwargs))


async def next_session(env, **query):
    row = await env.db["timetable_sessions"].find_one({"startAt": {"$gt": utcnow() + timedelta(hours=1)}, "kind": "LECTURE", **query}, sort=[("startAt", 1)])
    assert row is not None
    return row


# ---- checking ------------------------------------------------------------------------------------------------------


async def test_a_free_room_is_allowed(world):
    body = (await world.call("FACULTY", "POST", "/api/v1/bookings/check", json=request())).json()
    assert body["allowed"] is True and body["findings"] == [] and body["affectedClasses"] == [] and body["stateToken"]


async def test_a_clash_with_a_class_shows_the_class_the_reason_and_alternatives(world):
    session = await next_session(world)
    start = session["startAt"].replace(tzinfo=None) + timedelta(minutes=15)
    body = (
        await world.call(
            "FACULTY", "POST", "/api/v1/bookings/check",
            json={"roomCode": session["roomId"], "start": (start.isoformat() + "+00:00"), "end": ((start + timedelta(minutes=30)).isoformat() + "+00:00"), "headcount": 20, "purpose": "Extra revision"},
        )
    ).json()
    assert body["allowed"] is False and body["decision"] == "BLOCK"
    assert body["findings"][0]["code"] == "ROOM_OVERLAP" and session["courseName"] in body["findings"][0]["message"]
    assert body["affectedClasses"][0]["course"] == session["courseName"] and body["affectedClasses"][0]["group"] == session["studentGroup"]
    assert body["alternatives"] and all(room["roomCode"] != session["roomId"] for room in body["alternatives"])
    assert body["timeAlternatives"]


@pytest.mark.parametrize(
    ("start", "end", "phrase"),
    [(0.1, 2, "15 minute"), (0, 0.25 - 0.25, "least 15"), (0, 13, "longer than 12"), (-100000, -99999, "already over"), (24 * 200, 24 * 200 + 1, "days ahead")],
)
async def test_unreasonable_times_are_refused_with_a_clear_message(world, start, end, phrase):
    response = await world.call("FACULTY", "POST", "/api/v1/bookings/check", json=request(start=start, end=end))
    assert response.status_code in (400, 422)
    if response.status_code == 422:
        assert phrase in response.json()["message"]


async def test_the_end_must_be_after_the_start(world):
    assert (await world.call("FACULTY", "POST", "/api/v1/bookings/check", json=request(start=2, end=1))).status_code == 422


async def test_students_and_technicians_cannot_book(world):
    for role in ("STUDENT", "TECHNICIAN", "PROCUREMENT_APPROVER", "SYSTEM_ADMIN"):
        assert (await book(world, role)).status_code == 403


# ---- creating ------------------------------------------------------------------------------------------------------------


async def test_a_booking_is_confirmed_listed_and_audited(world):
    response = await book(world)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"].startswith("BK-") and body["status"] == "CONFIRMED" and body["roomCode"] == "ARB-204" and body["building"] == "Aryabhata Block"
    assert {a["key"] for a in body["availableActions"]} == {"booking.reschedule", "booking.cancel"}
    listed = (await world.call("FACULTY", "GET", "/api/v1/bookings")).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == body["id"]
    audit = await world.db["audit_logs"].find_one({"action": "booking.create"})
    assert audit["entityId"] == body["id"] and audit["after"]["collisionCheckId"].startswith("CC-")  # every commit-time check is kept
    assert await world.db["outbox_events"].count_documents({"eventType": "booking.confirmed"}) == 1
    slots = await world.db["room_slots"].count_documents({"ownerId": body["id"]})
    assert slots == 8  # two hours in 15 minute slots


async def test_a_second_booking_for_the_same_time_is_refused_and_touching_ones_are_not(world):
    assert (await book(world, start=0, end=2)).status_code == 201
    clash = await book(world, "DEPARTMENT_MANAGER", start=1, end=3)
    assert clash.status_code == 422 and clash.json()["code"] == "COLLISION_BLOCKED"
    assert (await book(world, "DEPARTMENT_MANAGER", start=2, end=3)).status_code == 201
    assert (await book(world, "DEPARTMENT_MANAGER", start=-1, end=0)).status_code == 201


async def test_a_booking_cannot_take_a_classes_room(world):
    session = await next_session(world)
    start = session["startAt"].replace(tzinfo=None)
    response = await world.call(
        "FACULTY", "POST", "/api/v1/bookings",
        json={"roomCode": session["roomId"], "start": start.isoformat() + "+00:00", "end": (start + timedelta(minutes=45)).isoformat() + "+00:00", "headcount": 10, "purpose": "Extra tutorial"},
    )
    assert response.status_code == 422 and response.json()["code"] == "COLLISION_BLOCKED"
    assert await world.db["bookings"].count_documents({}) == 0


async def test_twenty_simultaneous_requests_for_one_room_make_exactly_one_booking(world):
    responses = await asyncio.gather(*[book(world, role) for role in ("FACULTY", "DEPARTMENT_MANAGER", "FACILITIES_ADMIN") * 7][:20])
    statuses = sorted(response.status_code for response in responses)
    assert statuses.count(201) == 1, statuses
    assert all(code in (409, 422) for code in statuses if code != 201)
    assert await world.db["bookings"].count_documents({"status": "CONFIRMED"}) == 1
    assert await world.db["room_slots"].count_documents({"roomId": "ARB-204", "ownerKind": "BOOKING"}) == 8


async def test_the_slot_claim_alone_stops_a_double_hold_even_if_every_other_check_is_skipped(world):
    claims = SlotClaims(world.db)
    results = await asyncio.gather(*[claims.claim("BOOKING", f"BK-X{n}", "ARB-204", BASE, BASE + timedelta(hours=1)) for n in range(20)], return_exceptions=True)
    assert sum(1 for item in results if isinstance(item, int)) == 1
    assert all(isinstance(item, SlotTaken) for item in results if not isinstance(item, int))
    assert await world.db["room_slots"].count_documents({"ownerKind": "BOOKING"}) == 4  # losers left nothing behind


async def test_overlapping_requests_in_different_order_cannot_both_hold_half(world):
    claims = SlotClaims(world.db)
    windows = [(0, 2), (1, 3), (2, 4), (0.5, 2.5)]
    results = await asyncio.gather(*[claims.claim("BOOKING", f"BK-Y{n}", "ARB-203", BASE + timedelta(hours=a), BASE + timedelta(hours=b)) for n, (a, b) in enumerate(windows)], return_exceptions=True)
    winners = [n for n, item in enumerate(results) if isinstance(item, int)]
    assert winners, "someone must win"
    rows = await world.db["room_slots"].find({"roomId": "ARB-203", "ownerKind": "BOOKING"}).to_list(length=100)
    assert {row["ownerId"] for row in rows} == {f"BK-Y{n}" for n in winners}  # a loser holds nothing, not even half
    assert len(rows) == sum(int((windows[n][1] - windows[n][0]) * 4) for n in winners)  # every winner holds all of its window
    assert len({row["_id"] for row in rows}) == len(rows)


async def test_a_lost_race_is_a_clear_conflict(world):
    await SlotClaims(world.db).claim("BOOKING", "BK-OTHER", "ARB-204", BASE, BASE + timedelta(hours=2))  # held, but not yet visible as a booking
    response = await book(world)
    assert response.status_code == 409 and response.json()["code"] == "SLOT_TAKEN"
    assert await world.db["bookings"].count_documents({}) == 0


async def test_retrying_with_the_same_idempotency_key_books_once(world):
    key = {"Idempotency-Key": "booking-attempt-0001"}
    first = await world.call("FACULTY", "POST", "/api/v1/bookings", json=request(), headers=key)
    second = await world.call("FACULTY", "POST", "/api/v1/bookings", json=request(), headers=key)
    assert first.status_code == second.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert await world.db["bookings"].count_documents({}) == 1


async def test_a_purpose_is_required_to_book(world):
    assert (await world.call("FACULTY", "POST", "/api/v1/bookings", json={**request(), "purpose": ""})).status_code == 400


# ---- warnings and overrides ----------------------------------------------------------------------------------------------------


async def lab(env):
    return await env.db["rooms"].find_one({"type": "LAB", "bookable": True, "status": "OPEN"})


async def test_a_warning_needs_a_reason_and_then_proceeds_and_is_audited(world):
    room = await lab(world)
    check = (await world.call("FACULTY", "POST", "/api/v1/bookings/check", json=request(room["_id"], kind="LECTURE", headcount=10))).json()
    assert check["decision"] == "WARN" and check["allowed"] is False and check["requiresReason"] is True
    refused = await world.call("FACULTY", "POST", "/api/v1/bookings", json=request(room["_id"], kind="LECTURE", headcount=10))
    assert refused.status_code == 409 and refused.json()["code"] == "COLLISION_WARNING" and refused.json()["details"]["requiresReason"] is True
    ok = await world.call(
        "FACULTY", "POST", "/api/v1/bookings",
        json=request(room["_id"], kind="LECTURE", headcount=10, acknowledgedCodes=["ROOM_TYPE"], overrideReason="All classrooms are taken that hour"),
    )
    assert ok.status_code == 201, ok.text
    override = await world.db["audit_logs"].find_one({"action": "collision.override"})
    assert override["reason"] == "All classrooms are taken that hour"


async def test_a_booking_late_in_the_evening_warns_about_opening_hours(world):
    late = (BASE + timedelta(hours=14)).isoformat(), (BASE + timedelta(hours=15)).isoformat()  # 23:30 to 00:30 campus time
    body = (await world.call("FACULTY", "POST", "/api/v1/bookings/check", json={**request(), "start": late[0], "end": late[1]})).json()
    assert body["decision"] == "WARN" and body["findings"][0]["code"] == "OUTSIDE_HOURS" and "07:00 to 21:00" in body["findings"][0]["message"]


async def test_a_preview_goes_stale_if_the_room_is_taken_in_between(world):
    token = (await world.call("FACULTY", "POST", "/api/v1/bookings/check", json=request())).json()["stateToken"]
    assert (await book(world, "DEPARTMENT_MANAGER", start=1, end=2)).status_code == 201
    response = await world.call("FACULTY", "POST", "/api/v1/bookings", json={**request(start=3, end=4), "expectedStateToken": token})
    assert response.status_code == 409 and response.json()["code"] == "STALE_STATE"


# ---- cancelling and rescheduling ---------------------------------------------------------------------------------------------------------


async def test_cancelling_frees_the_room_for_someone_else(world):
    made = (await book(world)).json()
    cancelled = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert {a["key"] for a in cancelled.json()["unavailableActions"]} == {"booking.reschedule", "booking.cancel"}
    assert await world.db["room_slots"].count_documents({"ownerId": made["id"]}) == 0
    assert (await book(world, "DEPARTMENT_MANAGER")).status_code == 201


async def test_cancelling_twice_applies_once(world):
    made = (await book(world)).json()
    first = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/cancel")
    second = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/cancel")
    assert first.status_code == 200 and second.status_code == 422 and second.json()["code"] == "ILLEGAL_TRANSITION"
    assert await world.db["audit_logs"].count_documents({"action": "booking.cancel"}) == 1


async def test_only_the_owner_or_facilities_can_cancel(world):
    made = (await book(world)).json()
    assert (await world.call("DEPARTMENT_MANAGER", "POST", f"/api/v1/bookings/{made['id']}/cancel")).status_code == 403
    assert (await world.call("STUDENT", "POST", f"/api/v1/bookings/{made['id']}/cancel")).status_code == 403
    assert (await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/bookings/{made['id']}/cancel")).status_code == 200


async def test_a_manager_who_can_see_a_booking_still_cannot_cancel_it_unless_it_is_theirs(world):
    made = (await book(world)).json()
    seen = (await world.call("DEPARTMENT_MANAGER", "GET", "/api/v1/bookings")).json()["items"]
    assert [item["id"] for item in seen] == [made["id"]]  # same department
    cancel = next(a for a in seen[0]["unavailableActions"] if a["key"] == "booking.cancel")
    assert "Only the person who booked it" in cancel["reason"]
    assert (await world.call("DEPARTMENT_MANAGER", "POST", f"/api/v1/bookings/{made['id']}/cancel")).status_code == 403


async def test_a_booking_that_is_over_cannot_be_cancelled(world):
    await world.db["bookings"].insert_one(
        {"_id": "BK-OLD", "roomId": "ARB-204", "requesterId": "U-FACULTY", "requesterName": "Dr. Kiran Rao", "departmentId": "D-CSE", "campusId": world.services.settings.campus_id,
         "startAt": utcnow() - timedelta(hours=3), "endAt": utcnow() - timedelta(hours=1), "purpose": "Old", "headcount": 5, "status": "CONFIRMED", "history": [], "version": 0, "createdAt": utcnow(), "updatedAt": utcnow()}
    )
    row = (await world.call("FACULTY", "GET", "/api/v1/bookings/BK-OLD")).json()
    assert row["availableActions"] == [] and "already over" in row["unavailableActions"][0]["reason"]
    assert (await world.call("FACULTY", "POST", "/api/v1/bookings/BK-OLD/cancel")).json()["code"] == "ALREADY_OVER"


async def test_rescheduling_moves_the_booking_and_its_slots(world):
    made = (await book(world, start=0, end=2)).json()
    moved = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/reschedule", json={"start": at(1), "end": at(3)})
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["status"] == "RESCHEDULED" and body["rescheduledCount"] == 1 and body["start"].startswith(at(1)[:16])
    held = {row["_id"] async for row in world.db["room_slots"].find({"ownerId": made["id"]})}
    assert held == {slot_id("ARB-204", BASE + timedelta(hours=1) + timedelta(minutes=15 * n)) for n in range(8)}
    assert (await book(world, "DEPARTMENT_MANAGER", start=0, end=1)).status_code == 201  # the freed hour is free again


async def test_rescheduling_into_a_clash_changes_nothing(world):
    made = (await book(world, start=0, end=2)).json()
    assert (await book(world, "DEPARTMENT_MANAGER", start=3, end=5)).status_code == 201
    response = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/reschedule", json={"start": at(2.5), "end": at(4)})
    assert response.status_code == 422
    stored = await world.db["bookings"].find_one({"_id": made["id"]})
    assert stored["status"] == "CONFIRMED" and stored["history"] == []
    assert await world.db["room_slots"].count_documents({"ownerId": made["id"]}) == 8


async def test_rescheduling_to_another_room(world):
    made = (await book(world)).json()
    moved = (await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/reschedule", json={"roomCode": "ARB-203", "start": at(0), "end": at(2)})).json()
    assert moved["roomCode"] == "ARB-203"
    assert await world.db["room_slots"].count_documents({"roomId": "ARB-204", "ownerKind": "BOOKING"}) == 0


async def test_a_cancelled_booking_cannot_be_rescheduled(world):
    made = (await book(world)).json()
    await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/cancel")
    response = await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/reschedule", json={"start": at(1), "end": at(2)})
    assert response.status_code == 422 and response.json()["code"] == "ILLEGAL_TRANSITION"


# ---- who sees what ---------------------------------------------------------------------------------------------------------------------------


async def test_each_role_sees_only_the_bookings_in_its_scope(world):
    mine = (await book(world, "FACULTY", room="ARB-204", start=0, end=1)).json()
    theirs = (await book(world, "FACILITIES_ADMIN", room="ARB-203", start=0, end=1)).json()
    ids = lambda body: {item["id"] for item in body["items"]}  # noqa: E731
    assert ids((await world.call("FACULTY", "GET", "/api/v1/bookings")).json()) == {mine["id"]}
    assert ids((await world.call("FACILITIES_ADMIN", "GET", "/api/v1/bookings")).json()) == {mine["id"], theirs["id"]}
    assert ids((await world.call("DEPARTMENT_MANAGER", "GET", "/api/v1/bookings")).json()) == {mine["id"]}  # facilities is a different department
    assert (await world.call("FACULTY", "GET", f"/api/v1/bookings/{theirs['id']}")).status_code == 404
    assert (await world.call("STUDENT", "GET", "/api/v1/bookings")).status_code == 403


async def test_the_list_can_be_filtered_by_status(world):
    made = (await book(world)).json()
    await world.call("FACULTY", "POST", f"/api/v1/bookings/{made['id']}/cancel")
    assert (await world.call("FACULTY", "GET", "/api/v1/bookings", params={"status": "CONFIRMED"})).json()["total"] == 0
    assert (await world.call("FACULTY", "GET", "/api/v1/bookings", params={"status": "CANCELLED"})).json()["total"] == 1
    assert (await world.call("FACULTY", "GET", "/api/v1/bookings", params={"status": "NONSENSE"})).status_code == 400


# ---- moving a class ----------------------------------------------------------------------------------------------------------------------------


async def free_room_like(env, session):
    original = await env.db["rooms"].find_one({"_id": session["roomId"]})
    candidates = await env.db["rooms"].find({"buildingId": original["buildingId"], "type": original["type"], "capacity": {"$gte": session["headcount"]}, "bookable": True}).to_list(length=50)
    for room in candidates:
        if room["_id"] != session["roomId"] and not await env.db["timetable_sessions"].find_one({"roomId": room["_id"], "startAt": {"$lt": session["endAt"]}, "endAt": {"$gt": session["startAt"]}}):
            return room
    raise AssertionError("the seeded campus should have a free room")


async def test_facilities_moves_a_class_and_the_right_people_are_told(world):
    session = await next_session(world)
    target = await free_room_like(world, session)
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/timetable/sessions/{session['_id']}/move", json={"roomCode": target["_id"]})
    assert response.status_code == 200, response.text
    assert response.json()["room"] == target["_id"] and response.json()["notified"] >= 1
    stored = await world.db["timetable_sessions"].find_one({"_id": session["_id"]})
    assert stored["roomId"] == target["_id"] and stored["movedFrom"]["roomId"] == session["roomId"]
    assert await world.db["room_slots"].count_documents({"ownerId": session["_id"], "roomId": session["roomId"]}) == 0
    assert await world.db["room_slots"].count_documents({"ownerId": session["_id"], "roomId": target["_id"]}) > 0
    event = await world.db["outbox_events"].find_one({"eventType": "session.moved"})
    assert event["payload"]["toRoom"] == target["_id"] and set(event["payload"]["recipientIds"]) <= {"U-FACULTY", "U-STUDENT"}
    assert (await world.db["audit_logs"].find_one({"action": "session.move"}))["after"]["roomId"] == target["_id"]
    # the room it left can now be booked, and the room it entered cannot
    start = session["startAt"].replace(tzinfo=None)
    window = {"start": start.isoformat() + "+00:00", "end": (start + timedelta(minutes=30)).isoformat() + "+00:00", "headcount": 5, "purpose": "Use of the freed room"}
    assert (await world.call("FACULTY", "POST", "/api/v1/bookings", json={**window, "roomCode": session["roomId"]})).status_code == 201
    assert (await world.call("FACILITIES_ADMIN", "POST", "/api/v1/bookings", json={**window, "roomCode": target["_id"]})).status_code == 422


async def test_a_class_cannot_be_moved_into_a_room_that_is_in_use_or_too_small(world):
    session = await next_session(world)
    other = await world.db["timetable_sessions"].find_one({"startAt": session["startAt"], "_id": {"$ne": session["_id"]}})
    busy = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/timetable/sessions/{session['_id']}/move", json={"roomCode": other["roomId"]})
    assert busy.status_code == 422 and busy.json()["code"] == "COLLISION_BLOCKED"
    small = await world.db["rooms"].find_one({"capacity": {"$lt": session["headcount"]}, "bookable": True})
    assert (await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/timetable/sessions/{session['_id']}/move", json={"roomCode": small["_id"]})).json()["code"] == "COLLISION_BLOCKED"
    assert (await world.db["timetable_sessions"].find_one({"_id": session["_id"]}))["roomId"] == session["roomId"]


async def test_only_facilities_can_move_a_class_and_it_must_say_where(world):
    session = await next_session(world)
    for role in ("FACULTY", "DEPARTMENT_MANAGER", "STUDENT"):
        assert (await world.call(role, "POST", f"/api/v1/timetable/sessions/{session['_id']}/move", json={"roomCode": "ARB-203"})).status_code == 403
    assert (await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/timetable/sessions/{session['_id']}/move", json={})).json()["code"] == "NOTHING_TO_MOVE"
    assert (await world.call("FACILITIES_ADMIN", "POST", "/api/v1/timetable/sessions/NOPE/move", json={"roomCode": "ARB-203"})).status_code == 404


# ---- the timetable ------------------------------------------------------------------------------------------------------------------------------


async def day_of(env, **query):
    row = await env.db["timetable_sessions"].find_one({"kind": "LECTURE", **query}, sort=[("startAt", 1)])
    return (row["startAt"] + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d"), row


async def test_faculty_see_their_own_classes_for_a_day(world):
    day, _ = await day_of(world, facultyId="FAC-01")
    rows = (await world.call("FACULTY", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    assert rows and all(row["status"] == "NORMAL" for row in rows)
    ids = {row["id"] async for row in world.db["timetable_sessions"].find({"facultyId": "FAC-01"}) for row in [{"id": row["_id"]}]}
    assert {row["id"] for row in rows} <= ids
    assert {"id", "course", "room", "start", "end", "group", "headcount", "kind", "status", "note", "alternative"} <= set(rows[0])
    assert rows == sorted(rows, key=lambda row: row["start"])


async def test_students_see_their_groups_classes_and_staff_without_classes_see_none(world):
    day, _ = await day_of(world, studentGroup="CSE-3A")
    rows = (await world.call("STUDENT", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    assert rows and {row["group"] for row in rows} == {"CSE-3A"}
    assert (await world.call("TECHNICIAN", "GET", "/api/v1/timetable/today", params={"date": day})).json() == []
    everything = (await world.call("FACILITIES_ADMIN", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    assert len(everything) > len(rows)
    cse = (await world.call("DEPARTMENT_MANAGER", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    assert 0 < len(cse) < len(everything)


async def test_a_closed_room_marks_the_classes_in_it_as_affected_with_a_room_to_go_to(world):
    day, session = await day_of(world, studentGroup="CSE-3A")
    await world.db["rooms"].update_one({"_id": session["roomId"]}, {"$set": {"status": "CLOSED"}})
    rows = (await world.call("STUDENT", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    hit = [row for row in rows if row["room"] == session["roomId"]]
    assert hit and all(row["status"] == "AFFECTED" and "closed" in row["note"] for row in hit)
    assert all(row["alternative"] and row["alternative"]["roomCode"] != session["roomId"] for row in hit)


async def test_a_serious_open_incident_marks_its_rooms_as_affected(world):
    day, session = await day_of(world, studentGroup="CSE-3A")
    now = utcnow()
    await world.db["incidents"].insert_one(
        {"_id": "INC-9", "title": "Power failure", "status": "ACKNOWLEDGED", "priority": "P1", "roomCodes": [session["roomId"]], "version": 0, "createdAt": now, "updatedAt": now}
    )
    rows = (await world.call("STUDENT", "GET", "/api/v1/timetable/today", params={"date": day})).json()
    hit = next(row for row in rows if row["room"] == session["roomId"])
    assert hit["status"] == "AFFECTED" and "INC-9" in hit["note"]


async def test_a_bad_date_is_refused(world):
    assert (await world.call("FACULTY", "GET", "/api/v1/timetable/today", params={"date": "tomorrow"})).json()["code"] == "INVALID_DATE"


async def test_affected_classes_for_rooms_in_a_window(world):
    session = await next_session(world)
    start = session["startAt"].replace(tzinfo=None)
    body = (
        await world.call(
            "FACILITIES_ADMIN", "GET", "/api/v1/timetable/affected",
            params={"rooms": f"{session['roomId']},ZZZ-999", "start": start.isoformat() + "+00:00", "end": (start + timedelta(hours=1)).isoformat() + "+00:00"},
        )
    ).json()
    assert body["totals"]["sessions"] >= 1 and body["sessions"][0]["id"] == session["_id"]
    assert body["totals"]["people"] == sum(item["headcount"] for item in body["sessions"])
    assert body["sessions"][0]["faculty"]


# ---- timetable claims ---------------------------------------------------------------------------------------------------------------------------------


async def test_every_seeded_class_holds_its_slots_and_claiming_again_does_nothing(world):
    sessions = await world.db["timetable_sessions"].find({"status": "SCHEDULED"}).to_list(length=1000)
    expected = sum(int((s["endAt"] - s["startAt"]).total_seconds() // 900) for s in sessions)
    assert await world.db["room_slots"].count_documents({"ownerKind": "SESSION"}) == expected
    assert await world.services.bookings.claim_sessions() == 0
