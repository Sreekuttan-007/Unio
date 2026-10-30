"""Phase 5: the Collision Engine, one case per row of the plan's test matrix, plus the gate and the alternatives."""

import re
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from app.collision.models import Acknowledgement, ActionType, fingerprint, rupees
from app.collision.payloads import jsonable, parse_payload
from app.core.clock import utcnow
from app.core.errors import ApiException
from tests.conftest import open_env

BASE = (utcnow() + timedelta(days=45)).replace(hour=4, minute=0, second=0, microsecond=0)  # 09:30 campus time, clear of seeded sessions


def at(hours: float) -> str:
    return (BASE + timedelta(hours=hours)).isoformat()


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        yield opened


async def actor(env, role):
    user = await env.services.identity.authenticate(await env.token(role))
    assert user is not None
    return user


async def room_where(env, **query):
    row = await env.db["rooms"].find_one({"bookable": True, "status": "OPEN", **query})
    assert row is not None
    return row


def book(room_id, start=0, end=2, **extra):
    return {"roomId": room_id, "startAt": at(start), "endAt": at(end), "headcount": 20, "kind": "LECTURE", **extra}


async def preview(env, role, action_type, payload, token=None):
    user = await actor(env, role)
    return await env.services.collisions.check(user, ActionType(action_type), payload, token)


async def codes(env, role, action_type, payload):
    return {finding["code"] for finding in (await preview(env, role, action_type, payload))["findings"]}


async def add_session(env, room_id, start, end, **extra):
    document = {
        "_id": f"SES-T-{room_id}-{start}", "courseName": "Operating Systems end semester", "kind": "EXAM", "roomId": room_id, "studentGroup": "CSE-3A",
        "headcount": 58, "startAt": BASE + timedelta(hours=start), "endAt": BASE + timedelta(hours=end), "status": "SCHEDULED", **extra,
    }
    await env.db["timetable_sessions"].insert_one(document)
    return document


async def add_work_order(env, wo_id, tech_id, start, end, status="ASSIGNED"):
    await env.db["work_orders"].insert_one(
        {"_id": wo_id, "title": f"Job {wo_id}", "assignedTechnicianId": tech_id, "status": status, "scheduledStartAt": BASE + timedelta(hours=start), "scheduledEndAt": BASE + timedelta(hours=end)}
    )


def assign(tech, start=0, end=2, skills=(("ELECTRICAL", 1),), work_order="WO-NEW"):
    return {"technicianId": tech, "workOrderId": work_order, "startAt": at(start), "endAt": at(end), "requiredSkills": [{"code": code, "minLevel": level} for code, level in skills]}


async def give_shift(env, tech, start=-1, end=8):
    await env.db["shifts"].insert_one({"_id": f"SH-T-{tech}-{start}", "technicianId": tech, "startAt": BASE + timedelta(hours=start), "endAt": BASE + timedelta(hours=end), "kind": "REGULAR"})


# ---- rooms: the matrix ---------------------------------------------------------------------------------------------


async def test_same_room_overlapping_time_is_blocked_and_names_what_is_in_the_way(world):
    await add_session(world, "ARB-204", 0, 3)
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2))
    assert result["decision"] == "BLOCK"
    finding = result["findings"][0]
    assert finding["code"] == "ROOM_OVERLAP" and finding["severity"] == "HARD"
    assert "Operating Systems end semester" in finding["message"] and "CSE-3A" in finding["message"] and "58" in finding["message"]


async def test_touching_end_and_start_is_allowed(world):
    await add_session(world, "ARB-204", 0, 3)
    assert (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 3, 5)))["decision"] == "ALLOW"
    assert (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", -2, 0)))["decision"] == "ALLOW"


async def test_a_confirmed_booking_blocks_but_a_cancelled_one_does_not(world):
    await world.db["bookings"].insert_one({"_id": "BK-1", "roomId": "ARB-204", "status": "CONFIRMED", "startAt": BASE, "endAt": BASE + timedelta(hours=2), "headcount": 30, "purpose": "Revision"})
    assert "ROOM_OVERLAP" in await codes(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 3))
    await world.db["bookings"].update_one({"_id": "BK-1"}, {"$set": {"status": "CANCELLED"}})
    assert await codes(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 3)) == set()


async def test_moving_a_session_ignores_its_own_slot(world):
    await add_session(world, "ARB-204", 0, 3)
    own = (await preview(world, "DEPARTMENT_MANAGER", "MOVE_SESSION", book("ARB-204", 0, 3, excludeSessionId="SES-T-ARB-204-0")))
    assert own["decision"] == "ALLOW"


@pytest.mark.parametrize("state", ["CLOSED", "MAINTENANCE"])
async def test_a_closed_room_is_blocked(world, state):
    await world.db["rooms"].update_one({"_id": "ARB-204"}, {"$set": {"status": state}})
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204"))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "ROOM_CLOSED"
    assert state.lower() in result["findings"][0]["message"]


async def test_a_room_in_a_closed_building_is_blocked(world):
    await world.db["buildings"].update_one({"_id": "B-ARB"}, {"$set": {"status": "CLOSED"}})
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204"))
    assert result["findings"][0]["code"] == "ROOM_CLOSED" and "Aryabhata Block" in result["findings"][0]["message"]


async def test_headcount_above_capacity_is_blocked(world):
    room = await room_where(world, type="CLASSROOM")
    result = await preview(world, "FACULTY", "BOOK_ROOM", book(room["_id"], headcount=room["capacity"] + 1))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "ROOM_CAPACITY"
    assert str(room["capacity"]) in result["findings"][0]["message"]
    assert (await preview(world, "FACULTY", "BOOK_ROOM", book(room["_id"], headcount=room["capacity"])))["decision"] == "ALLOW"


async def test_a_practical_in_a_plain_classroom_is_a_warning(world):
    room = await room_where(world, type="CLASSROOM")
    result = await preview(world, "FACULTY", "BOOK_ROOM", book(room["_id"], kind="PRACTICAL"))
    assert result["decision"] == "WARN" and result["findings"][0]["code"] == "ROOM_TYPE" and result["findings"][0]["severity"] == "SOFT"


async def test_a_lecture_in_a_lab_is_a_warning(world):
    lab = await room_where(world, type="LAB")
    assert "ROOM_TYPE" in await codes(world, "FACULTY", "BOOK_ROOM", book(lab["_id"], kind="LECTURE"))
    assert await codes(world, "FACULTY", "BOOK_ROOM", book(lab["_id"], kind="PRACTICAL")) == set()


async def test_unknown_and_unbookable_rooms_are_blocked(world):
    assert "ROOM_UNKNOWN" in await codes(world, "FACULTY", "BOOK_ROOM", book("ZZZ-999"))
    office = await world.db["rooms"].find_one({"bookable": False})
    assert "ROOM_NOT_BOOKABLE" in await codes(world, "FACULTY", "BOOK_ROOM", book(office["_id"]))


async def test_a_broken_projector_blocks_a_booking_that_needs_one(world):
    await world.db["assets"].update_one({"_id": "AST-PR-ARB-204"}, {"$set": {"status": "DOWN"}})
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", requiredFeatures=["PROJECTOR"]))
    assert result["findings"][0]["code"] == "ASSET_DOWN" and "projector" in result["findings"][0]["message"]
    assert await codes(world, "FACULTY", "BOOK_ROOM", book("ARB-204")) == set()


# ---- technicians ------------------------------------------------------------------------------------------------------


async def test_a_technician_without_the_skill_is_blocked(world):
    await give_shift(world, "T-03")
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-03", skills=(("ELECTRICAL", 1),)))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "TECH_SKILL"
    assert "Joseph Paul" in result["findings"][0]["message"] and "ELECTRICAL" in result["findings"][0]["message"]


async def test_a_technician_whose_level_is_too_low_is_blocked(world):
    await give_shift(world, "T-02")
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-02", skills=(("ELECTRICAL", 3),)))
    assert result["findings"][0]["code"] == "TECH_SKILL" and "level 2" in result["findings"][0]["message"]


async def test_the_right_technician_on_shift_is_allowed(world):
    await give_shift(world, "T-01")
    assert (await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", skills=(("ELECTRICAL", 3),))))["decision"] == "ALLOW"


@pytest.mark.parametrize(("state", "phrase"), [("ON_LEAVE", "on leave"), ("SICK", "off sick")])
async def test_a_technician_who_is_away_is_blocked(world, state, phrase):
    await give_shift(world, "T-01")
    await world.db["technicians"].update_one({"_id": "T-01"}, {"$set": {"availability": state}})
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01"))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "TECH_UNAVAILABLE" and phrase in result["findings"][0]["message"]


async def test_work_outside_the_shift_is_a_warning(world):
    await give_shift(world, "T-01", -1, 8)
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 9, 11))
    assert result["decision"] == "WARN" and result["findings"][0]["code"] == "TECH_SHIFT"
    partly = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 7, 9))
    assert partly["decision"] == "WARN"


async def test_a_technician_with_no_shift_that_day_is_outside_shift(world):
    assert "TECH_SHIFT" in await codes(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01"))


async def test_overlapping_assignments_are_blocked_and_touching_ones_are_not(world):
    await give_shift(world, "T-01")
    await add_work_order(world, "WO-1", "T-01", 0, 2)
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 1, 3))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "TECH_OVERLAP" and "WO-1" in result["findings"][0]["message"]
    assert "TECH_OVERLAP" not in await codes(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 2, 4))


async def test_a_blocked_job_does_not_hold_the_technicians_time(world):
    await give_shift(world, "T-01")
    await add_work_order(world, "WO-1", "T-01", 0, 2, status="BLOCKED")
    assert "TECH_OVERLAP" not in await codes(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 1, 3))


async def test_reassigning_a_job_to_the_same_technician_does_not_collide_with_itself(world):
    await give_shift(world, "T-01")
    await add_work_order(world, "WO-NEW", "T-01", 0, 2)
    assert (await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 0, 2, work_order="WO-NEW")))["decision"] == "ALLOW"


async def test_a_technician_over_their_workload_limit_is_a_warning_and_the_limit_is_configurable(world):
    await give_shift(world, "T-01", -1, 100)
    for index in range(3):
        await add_work_order(world, f"WO-{index}", "T-01", 10 + index * 2, 11 + index * 2)
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 0, 1))
    assert result["decision"] == "WARN" and result["findings"][0]["code"] == "TECH_WORKLOAD" and "3 of 3" in result["findings"][0]["message"]
    admin = await actor(world, "SYSTEM_ADMIN")
    await world.services.collisions.update_rule(admin, "TECH-003", None, {"maxConcurrent": 5})
    assert (await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", 0, 1)))["decision"] == "ALLOW"


# ---- stock ----------------------------------------------------------------------------------------------------------------


def parts(*lines, work_order="WO-212"):
    return {"workOrderId": work_order, "lines": [{"itemId": item, "qty": qty} for item, qty in lines]}


async def test_short_stock_is_blocked_with_the_exact_shortage(world):
    result = await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-32A-3P", 4)))
    finding = result["findings"][0]
    assert result["decision"] == "BLOCK" and finding["code"] == "STOCK_SHORT"
    assert finding["data"]["free"] == 0 and finding["data"]["shortBy"] == 4 and "MCB 32A three pole" in finding["message"]


async def test_reserved_stock_is_not_free(world):
    await world.db["inventory_balances"].update_many({"itemId": "ITM-MCB-16A-1P"}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": "ITM-MCB-16A-1P", "locationId": "LOC-MAIN"}, {"$set": {"onHand": 5, "reserved": 3}})
    short = await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 3)))
    assert short["findings"][0]["data"]["free"] == 2 and "3 are reserved" in short["findings"][0]["message"]
    assert (await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 2))))["decision"] == "ALLOW"


async def test_stock_is_counted_across_all_stores(world):
    await world.db["inventory_balances"].update_many({"itemId": "ITM-MCB-16A-1P"}, {"$set": {"onHand": 2, "reserved": 0}})
    count = await world.db["inventory_balances"].count_documents({"itemId": "ITM-MCB-16A-1P"})
    assert (await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 2 * count))))["decision"] == "ALLOW"


async def test_an_unknown_item_is_blocked(world):
    assert "ITEM_UNKNOWN" in await codes(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-NOPE", 1)))


async def test_the_same_part_cannot_be_reserved_twice_for_one_work_order(world):
    await world.db["reservations"].insert_one({"_id": "RSV-1", "itemId": "ITM-MCB-16A-1P", "workOrderId": "WO-212", "qty": 1, "status": "ACTIVE"})
    result = await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 1)))
    assert result["findings"][0]["code"] == "DUPLICATE_RESERVATION"
    await world.db["reservations"].update_one({"_id": "RSV-1"}, {"$set": {"status": "RELEASED"}})
    assert "DUPLICATE_RESERVATION" not in await codes(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 1)))
    assert "DUPLICATE_RESERVATION" in await codes(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 1), ("ITM-MCB-16A-1P", 1)))


# ---- approvals --------------------------------------------------------------------------------------------------------------


def decide(requester="U-FACULTY", amount=100_000, decision="APPROVE"):
    return {"approvalId": "APR-610", "requesterId": requester, "amountPaise": amount, "decision": decision}


async def test_nobody_approves_their_own_request(world):
    result = await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(requester="U-DEPT"))
    assert result["decision"] == "BLOCK" and result["findings"][0]["code"] == "SELF_APPROVAL"
    assert "APR-610" in result["findings"][0]["message"]


async def test_an_amount_above_the_approvers_limit_needs_a_higher_approver(world):
    result = await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(amount=3_000_000))
    assert result["decision"] == "REQUIRE_APPROVAL" and result["requiresApproval"]
    assert result["findings"][0]["code"] == "APPROVAL_LIMIT" and "₹30,000" in result["findings"][0]["message"] and "₹25,000" in result["findings"][0]["message"]
    assert (await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(amount=2_500_000)))["decision"] == "ALLOW"
    assert (await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(amount=3_000_000, decision="REJECT")))["decision"] == "ALLOW"
    assert (await preview(world, "PROCUREMENT_APPROVER", "DECIDE_APPROVAL", decide(amount=3_000_000)))["decision"] == "ALLOW"


async def test_a_system_administrator_cannot_decide_spending_even_if_asked(world):
    service = world.services.collisions
    admin = await actor(world, "SYSTEM_ADMIN")
    result = await service.evaluate(service.build_action(admin, ActionType.DECIDE_APPROVAL, decide(), None))
    assert result.findings[0].code == "SEPARATION_OF_DUTIES"


async def test_whoever_raised_or_received_an_order_cannot_verify_its_receipt(world):
    payload = {"receiptId": "GR-92", "requesterId": "U-PROCURE", "receivedBy": "U-TECH"}
    assert (await preview(world, "PROCUREMENT_APPROVER", "VALIDATE_RECEIPT", payload))["findings"][0]["code"] == "SEPARATION_OF_DUTIES"
    assert (await preview(world, "PROCUREMENT_APPROVER", "VALIDATE_RECEIPT", {**payload, "requesterId": "U-DEPT", "receivedBy": "U-TECH"}))["decision"] == "ALLOW"


async def test_a_consequence_cannot_be_resolved_before_its_cause(world):
    now = utcnow()
    for ident, status, cause in (("INC-A", "ACKNOWLEDGED", None), ("INC-B", "ACKNOWLEDGED", "INC-A")):
        await world.db["incidents"].insert_one({"_id": ident, "status": status, "causedById": cause, "version": 0, "createdAt": now, "updatedAt": now})
    result = await preview(world, "DEPARTMENT_MANAGER", "RESOLVE_INCIDENT", {"incidentId": "INC-B"})
    assert result["findings"][0]["code"] == "DEPENDENCY_ORDER" and "INC-A" in result["findings"][0]["message"]
    await world.db["incidents"].update_one({"_id": "INC-A"}, {"$set": {"status": "RESOLVED"}})
    assert (await preview(world, "DEPARTMENT_MANAGER", "RESOLVE_INCIDENT", {"incidentId": "INC-B"}))["decision"] == "ALLOW"


# ---- stale state ----------------------------------------------------------------------------------------------------------------


async def test_a_decision_is_refused_when_the_facts_changed_since_the_preview(world):
    user = await actor(world, "FACULTY")
    first = await world.services.collisions.check(user, ActionType.BOOK_ROOM, book("ARB-204", 0, 2))
    assert first["decision"] == "ALLOW"
    await add_session(world, "ARB-206", 0, 1)  # unrelated room: the facts this decision rested on are unchanged
    still = await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, book("ARB-204", 0, 2), expected_state_token=first["stateToken"])
    assert still["canProceed"]
    await add_session(world, "ARB-204", 1, 3)  # someone took the room after the preview
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, book("ARB-204", 5, 6), expected_state_token=first["stateToken"])
    assert caught.value.status == 409 and caught.value.code == "STALE_STATE"
    assert any(f["code"] == "STALE_STATE" for f in caught.value.details["findings"])


async def test_without_an_expected_token_staleness_is_not_checked(world):
    user = await actor(world, "FACULTY")
    assert (await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, book("ARB-204")))["canProceed"]


async def test_the_state_token_is_stable_for_unchanged_facts_and_differs_after_a_change(world):
    one = (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204")))["stateToken"]
    two = (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204")))["stateToken"]
    await world.db["rooms"].update_one({"_id": "ARB-204"}, {"$set": {"capacity": 5}})
    three = (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204")))["stateToken"]
    assert one == two != three


# ---- the gate: overrides ----------------------------------------------------------------------------------------------------------


async def practical_in_classroom(world):
    room = await room_where(world, type="CLASSROOM")
    return room, book(room["_id"], kind="PRACTICAL")


async def test_a_soft_finding_with_a_reason_proceeds_and_is_audited(world):
    user = await actor(world, "DEPARTMENT_MANAGER")
    _, payload = await practical_in_classroom(world)
    ack = Acknowledgement(reason="No lab free this week and the batch is small", codes=("ROOM_TYPE",))
    result = await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, payload, acknowledgement=ack)
    assert result["canProceed"] and result["override"]["reason"].startswith("No lab free")
    check = await world.db["collision_checks"].find_one({"_id": result["checkId"]})
    assert check["stage"] == "COMMIT" and check["override"]["by"] == user.name
    audit = await world.db["audit_logs"].find_one({"action": "collision.override"})
    assert audit["actorId"] == user.id and audit["reason"] == ack.reason and audit["entityId"] == result["checkId"]


@pytest.mark.parametrize(
    "ack",
    [None, Acknowledgement(reason="", codes=("ROOM_TYPE",)), Acknowledgement(reason="ok", codes=("ROOM_TYPE",)), Acknowledgement(reason="A proper reason here", codes=()), Acknowledgement(reason="A proper reason here", codes=("SOMETHING_ELSE",))],
)
async def test_a_soft_finding_without_a_proper_acknowledgement_is_refused(world, ack):
    user = await actor(world, "DEPARTMENT_MANAGER")
    _, payload = await practical_in_classroom(world)
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, payload, acknowledgement=ack)
    assert caught.value.status == 409 and caught.value.code == "COLLISION_WARNING" and caught.value.details["requiresReason"] is True


async def test_a_hard_finding_stays_blocked_whatever_is_supplied(world):
    await add_session(world, "ARB-204", 0, 3)
    user = await actor(world, "FACILITIES_ADMIN")
    await world.db["approvals"].insert_one({"_id": "APR-1", "type": "OVERRIDE", "status": "APPROVED", "requesterId": user.id, "subject": {"actionFingerprint": fingerprint("BOOK_ROOM", jsonable(parse_payload(ActionType.BOOK_ROOM, book("ARB-204", 1, 2))))}})
    ack = Acknowledgement(reason="The principal said so, trust me", codes=("ROOM_OVERLAP",), override_approval_id="APR-1")
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.enforce(user, ActionType.BOOK_ROOM, book("ARB-204", 1, 2), acknowledgement=ack)
    assert caught.value.status == 422 and caught.value.code == "COLLISION_BLOCKED"
    assert await world.db["audit_logs"].count_documents({"action": "collision.override"}) == 0


async def over_limit_action(world, **approval):
    user = await actor(world, "DEPARTMENT_MANAGER")
    payload = decide(amount=3_000_000)
    fp = fingerprint("DECIDE_APPROVAL", jsonable(parse_payload(ActionType.DECIDE_APPROVAL, payload)))
    base = {"_id": "APR-OVR", "type": "OVERRIDE", "status": "APPROVED", "requesterId": user.id, "subject": {"actionFingerprint": fp}}
    await world.db["approvals"].insert_one({**base, **approval})
    return user, payload


async def test_an_approval_finding_needs_an_approved_override_bound_to_this_exact_action(world):
    user, payload = await over_limit_action(world)
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.enforce(user, ActionType.DECIDE_APPROVAL, payload)
    assert caught.value.status == 409 and caught.value.code == "APPROVAL_REQUIRED"
    done = await world.services.collisions.enforce(user, ActionType.DECIDE_APPROVAL, payload, acknowledgement=Acknowledgement(override_approval_id="APR-OVR"))
    assert done["canProceed"] and done["override"]["approvalId"] == "APR-OVR"


@pytest.mark.parametrize("change", [{"status": "UNDER_REVIEW"}, {"status": "REJECTED"}, {"type": "PURCHASE"}, {"requesterId": "U-SOMEONE-ELSE"}, {"subject": {"actionFingerprint": "0" * 32}}])
async def test_an_override_that_is_not_approved_not_an_override_or_for_something_else_does_not_count(world, change):
    user, payload = await over_limit_action(world, **change)
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.enforce(user, ActionType.DECIDE_APPROVAL, payload, acknowledgement=Acknowledgement(override_approval_id="APR-OVR"))
    assert caught.value.code == "APPROVAL_REQUIRED"


async def test_an_override_for_a_different_amount_is_refused(world):
    user, payload = await over_limit_action(world)
    with pytest.raises(ApiException):
        await world.services.collisions.enforce(user, ActionType.DECIDE_APPROVAL, {**payload, "amountPaise": 9_000_000}, acknowledgement=Acknowledgement(override_approval_id="APR-OVR"))


# ---- aggregation --------------------------------------------------------------------------------------------------------------------


async def test_a_hard_and_a_soft_finding_together_block_and_list_the_hard_one_first(world):
    room = await room_where(world, type="CLASSROOM")
    await add_session(world, room["_id"], 0, 3)
    result = await preview(world, "FACULTY", "BOOK_ROOM", book(room["_id"], 1, 2, kind="PRACTICAL"))
    assert result["decision"] == "BLOCK"
    assert [f["severity"] for f in result["findings"]] == ["HARD", "SOFT"]


async def test_several_problems_are_all_reported_not_just_the_first(world):
    await add_session(world, "ARB-204", 0, 3)
    room = await world.db["rooms"].find_one({"_id": "ARB-204"})
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2, headcount=room["capacity"] + 5))
    assert {f["code"] for f in result["findings"]} >= {"ROOM_OVERLAP", "ROOM_CAPACITY"}


async def test_every_finding_reads_as_a_complete_sentence(world):
    await add_session(world, "ARB-204", 0, 3)
    await world.db["technicians"].update_one({"_id": "T-01"}, {"$set": {"availability": "ON_LEAVE"}})
    results = [
        await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2, kind="PRACTICAL", headcount=500)),
        await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-01", skills=(("HVAC", 2),))),
        await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-32A-3P", 4))),
        await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(requester="U-DEPT", amount=9_000_000)),
    ]
    messages = [f["message"] for result in results for f in result["findings"]]
    assert len(messages) >= 7
    for message in messages:
        assert re.search(r"[A-Za-z].*[.]$", message), message
        assert not re.search(r"None|\{|\}|\bnull\b|undefined", message), message


def test_money_is_written_the_indian_way():
    assert rupees(0) == "₹0" and rupees(10_000_000) == "₹1,00,000" and rupees(2_500_000) == "₹25,000" and rupees(123_456_700) == "₹12,34,567"
    assert rupees(150) == "₹1.50"


# ---- rules configuration ---------------------------------------------------------------------------------------------------------------


async def test_the_catalogue_is_seeded_once_and_edits_survive(world):
    rows = await world.services.collisions.rules()
    assert {row["code"] for row in rows} >= {"ROOM_OVERLAP", "TECH_SKILL", "STOCK_SHORT", "SELF_APPROVAL", "STALE_STATE"}
    admin = await actor(world, "SYSTEM_ADMIN")
    await world.services.collisions.update_rule(admin, "ROOM-004", False, None)
    await world.services.collisions.ensure_rules()
    assert next(row for row in await world.services.collisions.rules() if row["id"] == "ROOM-004")["enabled"] is False


async def test_a_locked_rule_cannot_be_switched_off_and_still_runs_if_the_row_says_otherwise(world):
    admin = await actor(world, "SYSTEM_ADMIN")
    with pytest.raises(ApiException) as caught:
        await world.services.collisions.update_rule(admin, "ROOM-001", False, None)
    assert caught.value.code == "RULE_LOCKED"
    await world.db["collision_rules"].update_one({"_id": "ROOM-001"}, {"$set": {"enabled": False}})  # tampering at the database level
    await add_session(world, "ARB-204", 0, 3)
    assert "ROOM_OVERLAP" in await codes(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2))


async def test_a_soft_rule_can_be_switched_off_and_the_change_is_audited(world):
    admin = await actor(world, "SYSTEM_ADMIN")
    room, payload = await practical_in_classroom(world)
    assert (await preview(world, "FACULTY", "BOOK_ROOM", payload))["decision"] == "WARN"
    await world.services.collisions.update_rule(admin, "ROOM-004", False, None)
    assert (await preview(world, "FACULTY", "BOOK_ROOM", payload))["decision"] == "ALLOW"
    entry = await world.db["audit_logs"].find_one({"action": "rule.update"})
    assert entry["before"] == {"enabled": True} and entry["after"] == {"enabled": False} and entry["domain"] == "SYSTEM"


async def test_rule_parameters_are_validated(world):
    admin = await actor(world, "SYSTEM_ADMIN")
    for bad in ({"colour": 3}, {"maxConcurrent": -1}, {"maxConcurrent": True}, {"maxConcurrent": 5000}):
        with pytest.raises(ApiException):
            await world.services.collisions.update_rule(admin, "TECH-003", None, bad)
    with pytest.raises(ApiException):
        await world.services.collisions.update_rule(admin, "ROOM-004", None, {"anything": 1})  # that rule has no settings


# ---- alternatives -------------------------------------------------------------------------------------------------------------------------


async def test_a_blocked_room_booking_comes_with_rooms_and_times_that_would_work(world):
    await add_session(world, "ARB-204", 0, 3)
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2))
    kinds = {alt["kind"] for alt in result["alternatives"]}
    assert kinds == {"ROOM", "TIME"}
    for alternative in result["alternatives"]:
        patched = {**book("ARB-204", 1, 2), **alternative["apply"]}
        assert (await preview(world, "FACULTY", "BOOK_ROOM", patched))["decision"] == "ALLOW", alternative
    assert "ARB-204" not in {alt.get("roomId") for alt in result["alternatives"] if alt["kind"] == "ROOM"}


async def test_room_alternatives_respect_capacity_and_prefer_the_same_building(world):
    await add_session(world, "ARB-204", 0, 3)
    result = await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204", 1, 2, headcount=40))
    rooms = [alt for alt in result["alternatives"] if alt["kind"] == "ROOM"]
    assert rooms and all(alt["roomId"].startswith("ARB") for alt in rooms)
    for alt in rooms:
        assert (await world.db["rooms"].find_one({"_id": alt["roomId"]}))["capacity"] >= 40


async def test_a_practical_is_only_offered_labs(world):
    lab = await room_where(world, type="LAB")
    await add_session(world, lab["_id"], 0, 3)
    result = await preview(world, "FACULTY", "BOOK_ROOM", book(lab["_id"], 1, 2, kind="PRACTICAL", headcount=10))
    for alt in result["alternatives"]:
        if alt["kind"] == "ROOM":
            assert (await world.db["rooms"].find_one({"_id": alt["roomId"]}))["type"] == "LAB"


async def test_a_wrong_technician_comes_with_technicians_who_would_work(world):
    for tech in ("T-01", "T-02", "T-03"):
        await give_shift(world, tech)
    result = await preview(world, "FACILITIES_ADMIN", "ASSIGN_TECHNICIAN", assign("T-03", skills=(("ELECTRICAL", 2),)))
    assert [alt["technicianId"] for alt in result["alternatives"]] == ["T-01", "T-02"]
    assert "ELECTRICAL" in result["alternatives"][0]["reason"]


async def test_short_stock_offers_a_purchase_request_and_a_partial_reservation(world):
    await world.db["inventory_balances"].update_many({"itemId": "ITM-MCB-16A-1P"}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": "ITM-MCB-16A-1P", "locationId": "LOC-MAIN"}, {"$set": {"onHand": 2}})
    result = await preview(world, "FACILITIES_ADMIN", "RESERVE_PARTS", parts(("ITM-MCB-16A-1P", 5)))
    by_kind = {alt["kind"]: alt for alt in result["alternatives"]}
    assert by_kind["PURCHASE_REQUEST"]["apply"]["qty"] == 3 and by_kind["PARTIAL"]["apply"]["qty"] == 2


async def test_an_allowed_action_has_no_alternatives(world):
    assert (await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204")))["alternatives"] == []


# ---- persistence and the review list ---------------------------------------------------------------------------------------------------------


async def test_blocked_and_warned_previews_are_recorded_and_clean_ones_are_not(world):
    await preview(world, "FACULTY", "BOOK_ROOM", book("ARB-204"))
    assert await world.db["collision_checks"].count_documents({}) == 0
    room, payload = await practical_in_classroom(world)
    shown = await preview(world, "FACULTY", "BOOK_ROOM", payload)
    stored = await world.db["collision_checks"].find_one({"_id": shown["checkId"]})
    assert stored["stage"] == "PREVIEW" and stored["decision"] == "WARN" and stored["actorId"] == "U-FACULTY" and stored["stateToken"] == shown["stateToken"]


async def test_the_review_list_shows_newest_first_with_actor_and_override(world):
    manager = await actor(world, "DEPARTMENT_MANAGER")
    _, payload = await practical_in_classroom(world)
    await world.services.collisions.enforce(manager, ActionType.BOOK_ROOM, payload, acknowledgement=Acknowledgement(reason="No lab free this week", codes=("ROOM_TYPE",)))
    await preview(world, "DEPARTMENT_MANAGER", "DECIDE_APPROVAL", decide(requester="U-DEPT"))
    rows = (await world.call("FACILITIES_ADMIN", "GET", "/api/v1/collisions")).json()
    assert [row["decision"] for row in rows] == ["BLOCK", "WARN"]
    assert rows[0]["actor"] == manager.name and rows[0]["findings"][0]["affected"] == "APR-610"
    assert rows[1]["override"] == {"by": manager.name, "reason": "No lab free this week"}
    assert rows[0]["summary"] == "Approve APR-610"


# ---- the HTTP surface ---------------------------------------------------------------------------------------------------------------------------


async def test_check_over_http_returns_the_full_explanation(world):
    await add_session(world, "ARB-204", 0, 3)
    response = await world.call("FACULTY", "POST", "/api/v1/collisions/check", json={"actionType": "BOOK_ROOM", "payload": book("ARB-204", 1, 2)})
    body = response.json()
    assert response.status_code == 200 and body["decision"] == "BLOCK" and body["canProceed"] is False
    assert body["findings"][0]["affectedEntities"][0] == {"type": "ROOM", "id": "ARB-204"}
    assert body["fingerprint"] and body["stateToken"] and body["alternatives"]


async def test_a_preview_cannot_be_used_to_look_at_things_the_caller_may_not_see(world):
    # faculty hold collision.check, which covers rooms, but not technician rosters, stock, approvals or receipts
    for action, payload in (
        ("ASSIGN_TECHNICIAN", assign("T-01")),
        ("RESERVE_PARTS", parts(("ITM-MCB-32A-3P", 1))),
        ("DECIDE_APPROVAL", decide()),
        ("VALIDATE_RECEIPT", {"receiptId": "GR-1"}),
        ("RESOLVE_INCIDENT", {"incidentId": "INC-1"}),
        ("MOVE_SESSION", book("ARB-204")),
    ):
        response = await world.call("FACULTY", "POST", "/api/v1/collisions/check", json={"actionType": action, "payload": payload})
        assert response.status_code == 403, action


async def test_invalid_requests_are_refused_with_a_readable_reason(world):
    bad_window = await world.call("FACULTY", "POST", "/api/v1/collisions/check", json={"actionType": "BOOK_ROOM", "payload": {**book("ARB-204"), "startAt": at(3), "endAt": at(1)}})
    assert bad_window.status_code == 422 and bad_window.json()["code"] == "INVALID_ACTION"
    missing = await world.call("FACULTY", "POST", "/api/v1/collisions/check", json={"actionType": "BOOK_ROOM", "payload": {"roomId": "ARB-204"}})
    assert missing.status_code == 422
    unknown = await world.call("FACULTY", "POST", "/api/v1/collisions/check", json={"actionType": "LAUNCH_ROCKET", "payload": {}})
    assert unknown.status_code == 400


async def test_only_the_system_administrator_edits_rules_over_http(world):
    assert (await world.call("FACILITIES_ADMIN", "PATCH", "/api/v1/admin/rules/ROOM-004", json={"enabled": False})).status_code == 403
    done = await world.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/rules/ROOM-004", json={"enabled": False})
    assert done.status_code == 200 and done.json()["enabled"] is False
    locked = await world.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/rules/ROOM-001", json={"enabled": False})
    assert locked.status_code == 422 and locked.json()["code"] == "RULE_LOCKED"
    assert (await world.call("SYSTEM_ADMIN", "PATCH", "/api/v1/admin/rules/NOPE", json={"enabled": False})).status_code == 404
    listed = (await world.call("SYSTEM_ADMIN", "GET", "/api/v1/admin/rules")).json()
    assert next(r for r in listed if r["id"] == "TECH-003")["parameter"] == "Each technician's own limit"


# ---- the engine cannot write ----------------------------------------------------------------------------------------------------------------------

PURE = ("models.py", "rules.py", "engine.py", "alternatives.py", "reader.py", "payloads.py")
WRITE_CALLS = re.compile(r"\.(insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many|bulk_write|find_one_and_update|find_one_and_delete|find_one_and_replace|create_index|drop)\(")


def test_the_engine_and_its_reader_contain_no_write_calls():
    root = Path(__file__).parent.parent / "app" / "collision"
    for name in PURE:
        source = (root / name).read_text(encoding="utf-8")
        assert not WRITE_CALLS.search(source), f"{name} must only read"


def test_the_engine_does_not_depend_on_the_database_or_the_services():
    root = Path(__file__).parent.parent / "app" / "collision"
    for name in ("rules.py", "engine.py", "alternatives.py", "models.py"):
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", (root / name).read_text(encoding="utf-8"), re.MULTILINE)
        forbidden = [module for module in imports if module.startswith(("motor", "pymongo", "app.services", "app.db", "app.audit")) or module == "app.collision.service"]
        assert not forbidden, f"{name} imports {forbidden}"
