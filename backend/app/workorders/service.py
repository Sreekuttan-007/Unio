from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.bookings.slots import SlotClaims, SlotTaken, slot_id, slot_starts
from app.collision.models import Acknowledgement, ActionType
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, local_time, utcnow
from app.core.correlation import correlation_id
from app.core.errors import conflict, not_found, rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.core.permission import Permission as P
from app.core.scope import EntityType, scope_filter
from app.core.state import try_guarded_update
from app.files.service import FileStore, decode_base64
from app.incidents.service import IncidentService
from app.incidents.state import IncidentEvent
from app.sla.service import SlaService
from app.staff.service import technician_cards
from app.workorders.policy import ESTIMATE_MINUTES, LATE_GRACE_MINUTES, NOT_ACCEPTED_MINUTES, PLANNING_HORIZON_HOURS, PRIORITY_RANK, SAFETY_NOTE, SKILL_FOR, URGENT
from app.workorders.scoring import ceil_slot, plan_window, round_minutes, score_candidate
from app.workorders.state import DONE, HELD_BY_TECHNICIAN, OPEN, WORK_MACHINE, WorkOrderEvent, WorkOrderStatus

ASSIGNERS = (P.WORKORDER_ASSIGN_DEPARTMENT, P.WORKORDER_ASSIGN_CAMPUS)
BLOCK_REASONS = ("WAITING_FOR_PARTS", "ACCESS", "SKILL_MISMATCH")
MAX_EVIDENCE = 4
STATUS_RANK = {"IN_PROGRESS": 0, "ACCEPTED": 1, "ASSIGNED": 2, "BLOCKED": 3, "PENDING_ASSIGNMENT": 4, "COMPLETED": 5, "VERIFIED": 6, "CLOSED": 7, "CANCELLED": 8}
DECISION_RANK = {"ALLOW": 0, "WARN": 1, "BLOCK": 2}

FRIENDLY: dict[tuple[WorkOrderStatus, WorkOrderEvent], str] = {
    (WorkOrderStatus.BLOCKED, WorkOrderEvent.COMPLETE): "Blocked work cannot be completed. Resume it once the blocker is cleared.",
    (WorkOrderStatus.BLOCKED, WorkOrderEvent.START): "This task is blocked. Resume it when the blocker is cleared.",
    (WorkOrderStatus.ASSIGNED, WorkOrderEvent.START): "Accept the task before starting it.",
    (WorkOrderStatus.ASSIGNED, WorkOrderEvent.COMPLETE): "Start the task before completing it.",
    (WorkOrderStatus.ACCEPTED, WorkOrderEvent.COMPLETE): "Start the task before completing it.",
    (WorkOrderStatus.COMPLETED, WorkOrderEvent.COMPLETE): "This task is already completed.",
    (WorkOrderStatus.COMPLETED, WorkOrderEvent.START): "This task is already completed.",
    (WorkOrderStatus.IN_PROGRESS, WorkOrderEvent.ACCEPT): "You have already started this task.",
    (WorkOrderStatus.ACCEPTED, WorkOrderEvent.ACCEPT): "You have already accepted this task.",
}


def next_status(status: WorkOrderStatus, event: WorkOrderEvent) -> WorkOrderStatus:
    """The next state, with a plain sentence when the move does not fit."""
    target = WORK_MACHINE.target(status, event)
    if target is None:
        raise rule("ILLEGAL_TRANSITION", FRIENDLY.get((status, event)) or f"Cannot {event.name.lower().replace('_', ' ')} while the status is {status.name.lower().replace('_', ' ')}.")
    return target


def friendly_status(status: str) -> str:
    return status.lower().replace("_", " ")


class WorkOrderService:
    def __init__(
        self, db: Any, collisions: CollisionService, incidents: IncidentService, sla: SlaService, audit: AuditService, outbox: OutboxService, files: FileStore, campus_id: str
    ) -> None:
        self._db = db
        self._collisions = collisions
        self._incidents = incidents
        self._sla = sla
        self._audit = audit
        self._outbox = outbox
        self._files = files
        self._campus_id = campus_id
        self.slots = SlotClaims(db, "technician_slots", "technicianId")
        self.inventory: Any = None  # set by build_services: reserves parts and reports shortages

    # ---- reading ---------------------------------------------------------------------------------------

    async def _free_stock(self, item_ids: list[str]) -> dict[str, int]:
        free: dict[str, int] = {}
        if not item_ids:
            return free
        async for row in self._db["inventory_balances"].find({"itemId": {"$in": item_ids}}):
            free[row["itemId"]] = free.get(row["itemId"], 0) + row["onHand"] - row["reserved"]
        return free

    def _actions(self, order: dict[str, Any], user: AuthUser) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """What this person can do with this work order now, and why not for the moves that matter."""
        available: list[dict[str, str]] = []
        unavailable: list[dict[str, str]] = []
        status = WorkOrderStatus(order["status"])
        short = any(part["state"] == "SHORT" for part in order.get("partRequirements", []))

        def offer(key: str, label: str, event: WorkOrderEvent, *, reason: str | None = None) -> None:
            hint = {"key": f"workorder.{key}", "label": label}
            if reason:
                unavailable.append({**hint, "reason": reason})
            elif WORK_MACHINE.can(status, event):
                available.append(hint)
            elif (status, event) in FRIENDLY:
                unavailable.append({**hint, "reason": FRIENDLY[(status, event)]})

        if user.has(P.WORKORDER_EXECUTE) and order.get("assignedUserId") == user.id:
            offer("accept", "Accept", WorkOrderEvent.ACCEPT)
            offer("decline", "Decline", WorkOrderEvent.DECLINE)
            offer("start", "Start work", WorkOrderEvent.START)
            offer("block", "Report a blocker", WorkOrderEvent.BLOCK)
            hold = "Waiting for a part that has not arrived yet." if status is WorkOrderStatus.BLOCKED and order.get("blockReason") == "WAITING_FOR_PARTS" and short else None
            offer("resume", "Resume", WorkOrderEvent.RESUME, reason=hold)
            offer("complete", "Complete", WorkOrderEvent.COMPLETE)
            if status.value in HELD_BY_TECHNICIAN:
                if order.get("needsReassignment"):
                    unavailable.append({"key": "workorder.request-reassign", "label": "Ask for a replacement", "reason": "A replacement has already been asked for."})
                else:
                    available.append({"key": "workorder.request-reassign", "label": "Ask for a replacement"})
        if user.has_any(ASSIGNERS):
            if status is WorkOrderStatus.PENDING_ASSIGNMENT:
                offer("assign", "Assign", WorkOrderEvent.ASSIGN)
            else:
                offer("assign", "Reassign", WorkOrderEvent.REASSIGN)
            if WORK_MACHINE.can(status, WorkOrderEvent.CANCEL):
                available.append({"key": "workorder.cancel", "label": "Cancel work order"})
        if user.has(P.WORKORDER_VERIFY) and status is WorkOrderStatus.COMPLETED:
            available.append({"key": "workorder.verify", "label": "Verify the repair"})
            available.append({"key": "workorder.reject", "label": "Send back"})
        return available, unavailable

    async def view(self, order: dict[str, Any], user: AuthUser, *, stock: dict[str, int] | None = None) -> dict[str, Any]:
        sla = await self._sla.view(order["incidentId"]) if order.get("incidentId") else {"state": "ON_TRACK", "percentElapsed": 0, "remaining": "No timer", "dueAt": utcnow().isoformat()}
        free = stock if stock is not None else await self._free_stock([part["itemId"] for part in order.get("partRequirements", [])])
        available, unavailable = self._actions(order, user)
        flagged = order.get("needsReassignment")
        completion = order.get("completion")
        return {
            "id": order["_id"],
            "incidentId": order.get("incidentId", ""),
            "title": order["title"],
            "category": order["category"],
            "priority": order["priority"],
            "status": order["status"],
            "location": order.get("location", ""),
            "asset": order.get("assetName"),
            "requiredSkills": order.get("requiredSkills", []),
            "assignedTechnicianId": order.get("assignedTechnicianId"),
            "assignedTechnicianName": order.get("assignedTechnicianName"),
            "estimatedMinutes": order.get("estimatedMinutes", 60),
            "scheduledStart": ensure_utc(order["scheduledStartAt"]).isoformat() if order.get("scheduledStartAt") else None,
            "scheduledEnd": ensure_utc(order["scheduledEndAt"]).isoformat() if order.get("scheduledEndAt") else None,
            "blockReason": order.get("blockReason"),
            "parts": [
                {"sku": part["sku"], "name": part["name"], "qty": part["qty"], "state": part["state"], "available": max(0, free.get(part["itemId"], 0))}
                for part in order.get("partRequirements", [])
            ],
            "sla": sla,
            "safetyNote": order.get("safetyNote"),
            "needsReassignment": (
                {"reason": flagged["reason"], "suggestedTechnicianId": flagged.get("suggestedTechnicianId"), "suggestedName": flagged.get("suggestedName")} if flagged else None
            ),
            "approvalId": (order.get("approvalIds") or [None])[0],
            "createdAt": ensure_utc(order["createdAt"]).isoformat(),
            "completion": (
                {"notes": completion["notes"], "completedAt": ensure_utc(completion["completedAt"]).isoformat(), "evidence": completion.get("evidence", [])} if completion else None
            ),
            "availableActions": available,
            "unavailableActions": unavailable,
        }

    async def list(self, user: AuthUser, status: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"$and": [scope_filter(user, EntityType.WORK_ORDER)]}
        if status:
            query["$and"].append({"status": status})
        rows = await self._db["work_orders"].find(query).to_list(length=500)
        rows.sort(key=lambda row: (PRIORITY_RANK.get(row["priority"], 9), STATUS_RANK.get(row["status"], 9), row["_id"]))
        stock = await self._free_stock(sorted({part["itemId"] for row in rows for part in row.get("partRequirements", [])}))
        return [await self.view(row, user, stock=stock) for row in rows]

    async def get(self, user: AuthUser, work_order_id: str) -> dict[str, Any]:
        row = await self._db["work_orders"].find_one({"$and": [{"_id": work_order_id}, scope_filter(user, EntityType.WORK_ORDER)]})
        if row is None:
            raise not_found("Work order")
        return row  # type: ignore[no-any-return]

    async def open_count(self, user: AuthUser) -> int:
        return await self._db["work_orders"].count_documents({"$and": [scope_filter(user, EntityType.WORK_ORDER), {"status": {"$in": list(OPEN)}}]})

    async def _log(self, order_id: str, event: str, before: str | None, after: str | None, actor_id: str, actor_role: str, notes: str | None = None) -> None:
        await self._db["work_order_events"].insert_one(
            {"workOrderId": order_id, "eventType": event, "fromStatus": before, "toStatus": after, "actorId": actor_id, "actorRole": actor_role, "notes": notes, "at": utcnow(), "correlationId": correlation_id.get()}
        )

    async def history(self, user: AuthUser, work_order_id: str) -> list[dict[str, Any]]:
        await self.get(user, work_order_id)
        rows = await self._db["work_order_events"].find({"workOrderId": work_order_id}).sort([("at", 1), ("_id", 1)]).to_list(length=200)
        return [{"event": row["eventType"], "from": row["fromStatus"], "to": row["toStatus"], "by": row["actorId"], "role": row["actorRole"], "notes": row["notes"], "at": ensure_utc(row["at"]).isoformat()} for row in rows]

    # ---- creating -----------------------------------------------------------------------------------------

    async def create_from_incident(self, user: AuthUser, incident_id: str) -> str:
        incident = await self._incidents.get(user, incident_id)
        order = await self.create(incident, user.id, user.role_key)
        return f"{order['_id']} was created and is waiting for a technician."

    async def create(self, incident: dict[str, Any], actor_id: str, actor_role: str) -> dict[str, Any]:
        status = incident["status"]
        if status == "NEEDS_CLARIFICATION":
            raise rule("WAITING_FOR_REPORTER", "The reporter has not said where the problem is yet, so there is nothing to send a technician to.")
        if status in ("RESOLVED", "CLOSED"):
            raise rule("INCIDENT_CLOSED", "This incident is already resolved.")
        existing = await self._db["work_orders"].find_one({"incidentId": incident["_id"], "status": {"$nin": list(DONE)}})
        if existing:
            raise rule("WORK_ORDER_EXISTS", f"{existing['_id']} already covers this incident.")
        if status in ("SUBMITTED", "UNDER_REVIEW"):
            await self._incidents.advance(incident["_id"], IncidentEvent.ACKNOWLEDGE, actor_id, actor_role)
        room = await self._db["rooms"].find_one({"code": (incident.get("roomCodes") or [None])[0]}) if incident.get("roomCodes") else None
        asset = await self._db["assets"].find_one({"_id": (incident.get("assetIds") or [None])[0]}) if incident.get("assetIds") else None
        category = incident["category"]
        skill, level = SKILL_FOR.get(category, SKILL_FOR["OTHER"])
        now = utcnow()
        where = ", ".join(part for part in ((room or {}).get("code"), incident.get("buildingName")) if part)
        order = {
            "_id": await next_id(self._db, "WO", 105),
            "incidentId": incident["_id"],
            "title": incident["title"],
            "category": category,
            "priority": incident["priority"],
            "status": WorkOrderStatus.PENDING_ASSIGNMENT.value,
            "blockReason": None,
            "location": where or "Location to be confirmed",
            "roomId": (room or {}).get("_id"),
            "buildingId": incident.get("buildingId"),
            "assetId": (asset or {}).get("_id"),
            "assetName": (asset or {}).get("name"),
            "departmentId": incident.get("departmentId"),
            "campusId": self._campus_id,
            "requiredSkills": [{"code": skill, "minLevel": level}],
            "estimatedMinutes": ESTIMATE_MINUTES.get(category, 60),
            "scheduledStartAt": None,
            "scheduledEndAt": None,
            "assignedTechnicianId": None,
            "assignedTechnicianName": None,
            "assignedUserId": None,
            "assignmentScore": None,
            "partRequirements": [],
            "approvalIds": [],
            "safetyNote": SAFETY_NOTE.get(category),
            "needsReassignment": None,
            "declinedBy": [],
            "completion": None,
            "version": 0,
            "createdAt": now,
            "updatedAt": now,
        }
        await self._db["work_orders"].insert_one(order)
        await self._log(order["_id"], "CREATE", None, order["status"], actor_id, actor_role, f"From {incident['_id']}")
        await self._audit.record(
            actor_id=actor_id, actor_role=actor_role, action="workorder.create", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=order["_id"],
            after={"incidentId": incident["_id"], "priority": order["priority"], "category": category},
        )
        await self._incidents.note(incident["_id"], "Repair work scheduled", "accent", "A technician is being chosen.")
        await self._outbox.enqueue("workorder.created", {"workOrderId": order["_id"], "incidentId": incident["_id"], "priority": order["priority"], "roles": ["FACILITIES_ADMIN"]})
        if order["priority"] in URGENT:
            ranked = await self.rank(order)
            soonest = next((candidate for candidate in ranked if candidate["decision"] != "BLOCK"), None)
            if soonest is None or datetime.fromisoformat(soonest["window"]["startAt"]) - now > timedelta(minutes=15):
                await self.propose_preemption(order, ranked, now)
        return order

    # ---- ranking ------------------------------------------------------------------------------------------------

    @staticmethod
    def _payload(order: dict[str, Any], technician_id: str, start: datetime, end: datetime) -> dict[str, Any]:
        return {
            "technicianId": technician_id, "workOrderId": order["_id"], "startAt": start.isoformat(), "endAt": end.isoformat(),
            "requiredSkills": [{"code": need["code"], "minLevel": need["minLevel"]} for need in order.get("requiredSkills", [])],
        }

    async def _window(self, order: dict[str, Any], technician_id: str, now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[datetime, datetime, bool]]:
        reader = self._collisions.reader()
        tasks = await reader.technician_tasks(technician_id, exclude_work_order_id=order["_id"])
        shifts = await reader.technician_shifts(technician_id, now, now + timedelta(hours=PLANNING_HORIZON_HOURS))
        scheduled = [task for task in tasks if task["startAt"] and task["endAt"]]
        return tasks, shifts, plan_window(now, order["estimatedMinutes"], scheduled, shifts, urgent=order["priority"] in URGENT)

    async def rank(self, order: dict[str, Any], *, exclude: str | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
        """Every technician, each with an explainable score and the collision engine's verdict, best first."""
        now = now or utcnow()
        config = await self._collisions.config()
        ranked: list[dict[str, Any]] = []
        names = {row["_id"]: row["name"] async for row in self._db["departments"].find({})}
        for tech in await self._collisions.reader().all_technicians():
            if tech["_id"] == exclude:
                continue
            tasks, shifts, window = await self._window(order, tech["_id"], now)
            scored = score_candidate(order, tech, tasks, shifts, window, now)
            action = self._collisions.build_action(None, ActionType.ASSIGN_TECHNICIAN, self._payload(order, tech["_id"], window[0], window[1]), None)
            verdict = await self._collisions.evaluate(action, self._collisions.reader(), with_alternatives=False)
            decision = {"REQUIRE_APPROVAL": "BLOCK"}.get(verdict.decision.value, verdict.decision.value)
            ranked.append(
                {
                    "technicianId": tech["_id"],
                    "name": tech["name"],
                    "department": names.get(tech.get("departmentId"), "Shared"),
                    "score": scored["total"],
                    "factors": scored["factors"],
                    "decision": decision,
                    "findings": [finding.to_dict() for finding in verdict.findings],
                    "window": {"startAt": window[0].isoformat(), "endAt": window[1].isoformat(), "label": f"{local_time(window[0])} to {local_time(window[1])}"},
                    "openTasks": len(tasks),
                }
            )
        ranked.sort(key=lambda item: (DECISION_RANK[item["decision"]], -item["score"], item["name"]))
        return ranked

    async def candidates(self, user: AuthUser, work_order_id: str) -> list[dict[str, Any]]:
        order = await self.get(user, work_order_id)
        if order["status"] in DONE:
            raise rule("ILLEGAL_TRANSITION", f"This work order is {friendly_status(order['status'])}, so nobody can be assigned.")
        ranked = await self.rank(order)
        for candidate in ranked:
            if candidate["technicianId"] == order.get("assignedTechnicianId"):
                candidate["current"] = True
        return ranked

    # ---- assigning ----------------------------------------------------------------------------------------------

    async def assign(
        self, user: AuthUser, work_order_id: str, technician_id: str, *, acknowledgement: Acknowledgement | None = None, expected_state_token: str | None = None, start_at: datetime | None = None
    ) -> dict[str, Any]:
        order = await self.get(user, work_order_id)
        status = WorkOrderStatus(order["status"])
        event = WorkOrderEvent.ASSIGN if status is WorkOrderStatus.PENDING_ASSIGNMENT else WorkOrderEvent.REASSIGN
        target = next_status(status, event)
        if order.get("assignedTechnicianId") == technician_id and not order.get("needsReassignment"):
            raise rule("ALREADY_ASSIGNED", f"{order['_id']} is already assigned to {order.get('assignedTechnicianName')}.")
        tech = await self._db["technicians"].find_one({"_id": technician_id})
        if tech is None:
            raise not_found("Technician")
        now = utcnow()
        tasks, shifts, window = await self._window(order, technician_id, now)
        start, end, inside = window
        if start_at is not None:
            start = ensure_utc(start_at)
            end = start + timedelta(minutes=round_minutes(order["estimatedMinutes"]))
            inside = any(ensure_utc(shift["startAt"]) <= start and ensure_utc(shift["endAt"]) >= end for shift in shifts)
        payload = self._payload(order, technician_id, start, end)
        check = await self._collisions.enforce(user, ActionType.ASSIGN_TECHNICIAN, payload, acknowledgement=acknowledgement, expected_state_token=expected_state_token)
        old_slots = self._slot_ids(order)
        try:
            await self.slots.claim("WORK_ORDER", order["_id"], technician_id, start, end)
        except SlotTaken:
            raise conflict("TECH_OVERLAP", f"{tech['name']} was just given other work for that time. Choose someone else, or another time.") from None
        score = score_candidate(order, tech, tasks, shifts, (start, end, inside), now)
        update: dict[str, Any] = {
            "$set": {
                "status": target.value, "assignedTechnicianId": technician_id, "assignedTechnicianName": tech["name"], "assignedUserId": tech["userId"],
                "scheduledStartAt": start, "scheduledEndAt": end, "assignedAt": now, "needsReassignment": None,
                "assignmentScore": {"total": score["total"], "factors": score["factors"]}, "lastCollisionCheckId": check["checkId"],
            }
        }
        if not await try_guarded_update(self._db["work_orders"], order["_id"], order["version"], status, update):
            await self.slots.release(order["_id"], keep=old_slots)
            raise conflict("VERSION_CONFLICT", "This work order changed while you were assigning it. Reload it and try again.")
        wanted = {slot_id(technician_id, slot) for slot in slot_starts(start, end)}
        await self.slots.release(order["_id"], keep=wanted)
        previous = order.get("assignedTechnicianId")
        await self._log(order["_id"], event.value, status.value, target.value, user.id, user.role_key, f"{tech['name']}, {local_time(start)} to {local_time(end)}")
        await self._audit.record_as(
            user, action="workorder.reassign" if previous else "workorder.assign", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=order["_id"],
            before={"technicianId": previous, "status": status.value}, after={"technicianId": technician_id, "status": target.value, "window": [start.isoformat(), end.isoformat()], "collisionCheckId": check["checkId"]},
            reason=(check.get("override") or {}).get("reason"),
        )
        await self._incidents.note_assignment(order["incidentId"], tech["userId"], tech["name"], user.id, user.role_key)
        await self._sla.mark_responded(order["incidentId"])
        recipients = [tech["userId"]] + ([old["userId"]] if previous and (old := await self._db["technicians"].find_one({"_id": previous})) else [])
        await self._outbox.enqueue("workorder.reassigned" if previous else "workorder.assigned", {"workOrderId": order["_id"], "recipientIds": sorted(set(recipients)), "technicianId": technician_id})
        return await self._db["work_orders"].find_one({"_id": order["_id"]})  # type: ignore[return-value]

    def _slot_ids(self, order: dict[str, Any]) -> set[str]:
        if not (order.get("assignedTechnicianId") and order.get("scheduledStartAt") and order.get("scheduledEndAt")):
            return set()
        return {slot_id(order["assignedTechnicianId"], slot) for slot in slot_starts(order["scheduledStartAt"], order["scheduledEndAt"])}

    # ---- the technician's moves -----------------------------------------------------------------------------------

    async def _mine(self, user: AuthUser, work_order_id: str) -> dict[str, Any]:
        order = await self.get(user, work_order_id)
        if order.get("assignedUserId") != user.id:
            raise not_found("Work order")
        return order

    async def _move(
        self, order: dict[str, Any], event: WorkOrderEvent, actor_id: str, actor_role: str, sets: dict[str, Any] | None = None, *, unset: list[str] | None = None, notes: str | None = None
    ) -> dict[str, Any]:
        status = WorkOrderStatus(order["status"])
        target = next_status(status, event)
        update: dict[str, Any] = {"$set": {"status": target.value, **(sets or {})}}
        if unset:
            update["$unset"] = {key: "" for key in unset}
        if not await try_guarded_update(self._db["work_orders"], order["_id"], order["version"], status, update):
            raise conflict("VERSION_CONFLICT", "This work order changed. Reload it and try again.")
        await self._log(order["_id"], event.value, status.value, target.value, actor_id, actor_role, notes)
        await self._audit.record(
            actor_id=actor_id, actor_role=actor_role, action=f"workorder.{event.value.lower()}", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=order["_id"],
            before={"status": status.value}, after={"status": target.value}, reason=notes,
        )
        return await self._db["work_orders"].find_one({"_id": order["_id"]})  # type: ignore[return-value]

    async def accept(self, user: AuthUser, work_order_id: str) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        moved = await self._move(order, WorkOrderEvent.ACCEPT, user.id, user.role_key, {"acceptedAt": utcnow()})
        await self._outbox.enqueue("workorder.accepted", {"workOrderId": order["_id"], "roles": ["FACILITIES_ADMIN"]})
        return moved

    async def decline(self, user: AuthUser, work_order_id: str, reason: str | None) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        technician = order["assignedTechnicianId"]
        entry = {"technicianId": technician, "at": utcnow(), "reason": (reason or "").strip() or None}
        moved = await self._move(
            order, WorkOrderEvent.DECLINE, user.id, user.role_key,
            {"assignedTechnicianId": None, "assignedTechnicianName": None, "assignedUserId": None, "scheduledStartAt": None, "scheduledEndAt": None, "assignmentScore": None, "declinedBy": [*order.get("declinedBy", []), entry]},
            notes=entry["reason"],
        )
        await self.slots.release(order["_id"])
        await self._incidents.note_assignment(order["incidentId"], None, None, user.id, user.role_key)
        await self._outbox.enqueue("workorder.declined", {"workOrderId": order["_id"], "roles": ["FACILITIES_ADMIN"], "technicianId": technician})
        return moved

    async def start(self, user: AuthUser, work_order_id: str) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        moved = await self._move(order, WorkOrderEvent.START, user.id, user.role_key, {"startedAt": utcnow()})
        await self._incidents.advance(order["incidentId"], IncidentEvent.START, user.id, user.role_key)
        await self._incidents.note(order["incidentId"], "Work has started", "accent")
        return moved

    async def block(self, user: AuthUser, work_order_id: str, reason: str, notes: str | None, parts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if reason not in BLOCK_REASONS:
            raise rule("UNKNOWN_BLOCK_REASON", "Say what is stopping the work: a missing part, access, or a different skill.")
        order = await self._mine(user, work_order_id)
        if reason == "WAITING_FOR_PARTS" and parts and self.inventory is not None:
            await self.inventory.request_parts(user, order, parts)
            order = await self._db["work_orders"].find_one({"_id": order["_id"]})  # type: ignore[assignment]
        moved = await self._move(order, WorkOrderEvent.BLOCK, user.id, user.role_key, {"blockReason": reason, "blockNotes": (notes or "").strip() or None, "blockedAt": utcnow()}, notes=(notes or reason))
        if reason == "WAITING_FOR_PARTS":
            await self._sla.pause(order["incidentId"], "Waiting for parts")
            await self._incidents.note(order["incidentId"], "Waiting for a part", "warning", "The repair is paused until the part arrives.")
        elif reason == "SKILL_MISMATCH":
            await self.flag(moved, "The technician says this needs a different skill", "SKILL_MISMATCH", exclude=order["assignedTechnicianId"])
        await self._outbox.enqueue("workorder.blocked", {"workOrderId": order["_id"], "reason": reason, "roles": ["FACILITIES_ADMIN"]})
        return await self._db["work_orders"].find_one({"_id": order["_id"]})  # type: ignore[return-value]

    async def resume(self, user: AuthUser, work_order_id: str) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        if order.get("blockReason") == "WAITING_FOR_PARTS" and any(part["state"] == "SHORT" for part in order.get("partRequirements", [])):
            raise rule("PARTS_NOT_HERE", "The part you asked for has not arrived yet. This resumes by itself when it does.")
        return await self.resume_work(order, user.id, user.role_key)

    async def resume_work(self, order: dict[str, Any], actor_id: str, actor_role: str) -> dict[str, Any]:
        moved = await self._move(order, WorkOrderEvent.RESUME, actor_id, actor_role, {"blockReason": None, "blockNotes": None, "resumedAt": utcnow()})
        await self._sla.resume(order["incidentId"])
        await self._incidents.note(order["incidentId"], "Work has resumed", "accent")
        if moved.get("assignedUserId"):
            await self._outbox.enqueue("workorder.resumed", {"workOrderId": order["_id"], "recipientIds": [moved["assignedUserId"]], "roles": ["FACILITIES_ADMIN"]})
        return moved

    async def complete(self, user: AuthUser, work_order_id: str, notes: str, evidence: list[dict[str, str]] | None = None) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        notes = (notes or "").strip()
        if len(notes) < 3:
            raise rule("COMPLETION_NOTES_REQUIRED", "Add a short note about what you did before completing.")
        if len(evidence or []) > MAX_EVIDENCE:
            raise rule("TOO_MANY_PHOTOS", f"Attach at most {MAX_EVIDENCE} photos.")
        next_status(WorkOrderStatus(order["status"]), WorkOrderEvent.COMPLETE)  # refuse before storing anything
        saved = []
        for item in evidence or []:
            meta = await self._files.save(owner=user, purpose="EVIDENCE", name=item["name"], mime=item["mime"], data=decode_base64(item["content_base64"]), entity=("WORK_ORDER", order["_id"]))
            saved.append(self._files.view(meta))
        now = utcnow()
        moved = await self._move(order, WorkOrderEvent.COMPLETE, user.id, user.role_key, {"completion": {"notes": notes, "evidence": saved, "completedAt": now, "completedBy": user.id}, "completedAt": now}, notes=notes)
        await self.slots.release(order["_id"])
        parts_used = [{"itemId": part["itemId"], "qty": part["qty"]} for part in order.get("partRequirements", []) if part["state"] in ("RESERVED", "ISSUED")]
        if self.inventory is not None and parts_used:
            await self.inventory.issue_for_completion(user, order, parts_used)
        await self._db["maintenance_history"].update_one(
            {"_id": f"MH-{order['_id']}"},
            {
                "$setOnInsert": {
                    "assetId": order.get("assetId"), "roomId": order.get("roomId"), "workOrderId": order["_id"], "category": order["category"], "summary": notes,
                    "technicianId": order["assignedTechnicianId"], "completedAt": now, "partsUsed": parts_used, "costPaise": order.get("estimatedCostPaise", 0), "campusId": self._campus_id,
                }
            },
            upsert=True,
        )
        await self._incidents.note(order["incidentId"], "Repair completed", "success", "It is being checked.")
        await self._outbox.enqueue("workorder.completed", {"workOrderId": order["_id"], "incidentId": order["incidentId"], "roles": ["FACILITIES_ADMIN"]})
        return moved

    async def request_reassign(self, user: AuthUser, work_order_id: str, reason: str | None) -> dict[str, Any]:
        order = await self._mine(user, work_order_id)
        if order["status"] not in HELD_BY_TECHNICIAN:
            raise rule("ILLEGAL_TRANSITION", f"A {friendly_status(order['status'])} work order cannot be handed over.")
        if order.get("needsReassignment"):
            raise rule("ALREADY_REQUESTED", "A replacement has already been asked for.")
        flagged = await self.flag(order, (reason or "").strip() or f"{order['assignedTechnicianName']} asked to be replaced", "REQUESTED", exclude=order["assignedTechnicianId"], actor=(user.id, user.role_key))
        return flagged

    # ---- the managers' moves --------------------------------------------------------------------------------------------

    async def verify(self, user: AuthUser, work_order_id: str, approve: bool, notes: str | None) -> dict[str, Any]:
        order = await self.get(user, work_order_id)
        if order.get("assignedUserId") == user.id:
            raise rule("SELF_VERIFY", "You did this repair, so someone else must check it.")
        event = WorkOrderEvent.VERIFY if approve else WorkOrderEvent.REJECT_COMPLETION
        moved = await self._move(order, event, user.id, user.role_key, {"completion.verifiedBy": user.id, "completion.verifiedAt": utcnow()} if approve else {}, notes=notes)
        if not approve and moved.get("assignedUserId"):
            await self._outbox.enqueue("workorder.sent_back", {"workOrderId": order["_id"], "recipientIds": [moved["assignedUserId"]], "notes": notes})
        return moved

    async def cancel(self, user: AuthUser, work_order_id: str, reason: str | None) -> dict[str, Any]:
        order = await self.get(user, work_order_id)
        moved = await self._move(order, WorkOrderEvent.CANCEL, user.id, user.role_key, {"cancelReason": (reason or "").strip() or None}, notes=reason)
        await self.slots.release(order["_id"])
        if self.inventory is not None:
            await self.inventory.release_for_work_order(order["_id"], user.id, user.role_key)
        if order.get("assignedUserId"):
            await self._outbox.enqueue("workorder.cancelled", {"workOrderId": order["_id"], "recipientIds": [order["assignedUserId"]]})
        return moved

    async def close_for_incident(self, incident_id: str, actor_id: str, actor_role: str) -> int:
        closed = 0
        for order in await self._db["work_orders"].find({"incidentId": incident_id, "status": WorkOrderStatus.VERIFIED.value}).to_list(length=20):
            await self._move(order, WorkOrderEvent.CLOSE, actor_id, actor_role)
            closed += 1
        return closed

    # ---- reassignment ----------------------------------------------------------------------------------------------------

    async def flag(
        self, order: dict[str, Any], reason: str, trigger: str, *, exclude: str | None, actor: tuple[str, str] = ("system", "SYSTEM"), ranked: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Marks a work order as needing a new technician and proposes one. It moves nothing: a person decides."""
        options = ranked if ranked is not None else await self.rank(order, exclude=exclude)
        pick = next((item for item in options if item["decision"] == "ALLOW" and item["technicianId"] != exclude), None) or next(
            (item for item in options if item["decision"] == "WARN" and item["technicianId"] != exclude), None
        )
        flag = {
            "reason": reason, "trigger": trigger, "flaggedAt": utcnow(), "previousTechnicianId": order.get("assignedTechnicianId"),
            "suggestedTechnicianId": pick["technicianId"] if pick else None, "suggestedName": pick["name"] if pick else None, "suggestedScore": pick["score"] if pick else None,
        }
        await self._db["work_orders"].update_one({"_id": order["_id"]}, {"$set": {"needsReassignment": flag, "updatedAt": utcnow()}, "$inc": {"version": 1}})
        await self._log(order["_id"], "FLAGGED", order["status"], order["status"], actor[0], actor[1], reason)
        await self._audit.record(
            actor_id=actor[0], actor_role=actor[1], action="workorder.flag_reassignment", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=order["_id"],
            after={"trigger": trigger, "suggested": flag["suggestedTechnicianId"]}, reason=reason,
        )
        await self._outbox.enqueue("workorder.reassignment_proposed", {"workOrderId": order["_id"], "reason": reason, "suggested": flag["suggestedName"], "roles": ["FACILITIES_ADMIN"]})
        return await self._db["work_orders"].find_one({"_id": order["_id"]})  # type: ignore[return-value]

    async def technician_unavailable(self, technician_id: str, reason: str, actor: tuple[str, str]) -> list[str]:
        """Their open work is flagged, each with the best replacement. Nothing is moved until a person confirms."""
        flagged: list[str] = []
        orders = await self._db["work_orders"].find({"assignedTechnicianId": technician_id, "status": {"$in": list(HELD_BY_TECHNICIAN)}, "needsReassignment": None}).sort("_id", 1).to_list(length=50)
        for order in orders:
            await self.flag(order, reason, "UNAVAILABLE", exclude=technician_id, actor=actor)
            flagged.append(order["_id"])
        return flagged

    async def technician_available_again(self, technician_id: str) -> int:
        result = await self._db["work_orders"].update_many(
            {"assignedTechnicianId": technician_id, "needsReassignment.trigger": "UNAVAILABLE"}, {"$set": {"needsReassignment": None}, "$inc": {"version": 1}}
        )
        return int(result.modified_count)

    async def review_late(self, now: datetime | None = None) -> list[str]:
        """Flags work that was not picked up in time or is running past its slot. Safe to run as often as you like."""
        now = ensure_utc(now or utcnow())
        flagged: list[str] = []
        rows = await self._db["work_orders"].find({"status": {"$in": ["ASSIGNED", "ACCEPTED", "IN_PROGRESS"]}, "needsReassignment": None}).sort("_id", 1).to_list(length=200)
        for order in rows:
            reason = None
            if order["status"] == "ASSIGNED" and order.get("assignedAt"):
                waited = (now - ensure_utc(order["assignedAt"])).total_seconds() / 60
                if waited > NOT_ACCEPTED_MINUTES.get(order["priority"], 120):
                    reason = f"{order['assignedTechnicianName']} has not accepted this for {round(waited)} minutes"
            elif order.get("scheduledEndAt"):
                over = (now - ensure_utc(order["scheduledEndAt"])).total_seconds() / 60
                if over > LATE_GRACE_MINUTES:
                    reason = f"This is running {round(over)} minutes past its slot"
            if reason:
                await self.flag(order, reason, "LATE", exclude=order["assignedTechnicianId"])
                flagged.append(order["_id"])
        return flagged

    async def propose_preemption(self, order: dict[str, Any], ranked: list[dict[str, Any]], now: datetime | None = None) -> list[str]:
        """An urgent job that would have to wait behind lower-priority work: flag that work for reassignment.

        It picks the qualified, available technician who would need the fewest tasks moved. Nothing is
        moved here. Once a person reassigns the flagged work, the urgent job can start straight away.
        """
        if order["priority"] not in URGENT:
            return []
        now = ensure_utc(now or utcnow())
        length = timedelta(minutes=round_minutes(order["estimatedMinutes"]))
        start = ceil_slot(now)
        fit = [item for item in ranked if not any(finding["code"] in ("TECH_SKILL", "TECH_UNAVAILABLE", "TECH_UNKNOWN") for finding in item["findings"])]
        plans: list[tuple[int, int, str, list[str]]] = []
        for item in fit:
            tasks = await self._collisions.reader().technician_tasks(item["technicianId"], scheduled_only=True, exclude_work_order_id=order["_id"])
            in_the_way = [task for task in tasks if task["startAt"] and task["endAt"] and task["startAt"] < start + length and task["endAt"] > start]
            if in_the_way and all(PRIORITY_RANK.get(task["priority"] or "P4", 4) > PRIORITY_RANK[order["priority"]] and task["status"] != "IN_PROGRESS" for task in in_the_way):
                plans.append((len(in_the_way), -item["score"], item["technicianId"], [task["id"] for task in in_the_way]))
        if not plans:
            return []
        _, _, technician_id, task_ids = min(plans)
        name = next(item["name"] for item in fit if item["technicianId"] == technician_id)
        flagged: list[str] = []
        for task_id in task_ids:
            row = await self._db["work_orders"].find_one({"_id": task_id, "needsReassignment": None})
            if row:
                await self.flag(row, f"Making room for {order['_id']} ({order['priority']}), which needs {name}", "PREEMPTED", exclude=technician_id)
                flagged.append(task_id)
        return flagged

    # ---- technicians -------------------------------------------------------------------------------------------------------------

    async def technician_for(self, user: AuthUser) -> dict[str, Any]:
        row = await self._db["technicians"].find_one({"userId": user.id})
        if row is None:
            raise not_found("Technician profile")
        return row  # type: ignore[no-any-return]

    async def me(self, user: AuthUser) -> dict[str, Any]:
        row = await self.technician_for(user)
        card = (await technician_cards(self._db, [row["_id"]]))[0]
        return {**card, "leave": row.get("leave", [])}

    async def set_availability(self, actor: AuthUser, technician_id: str, availability: str, reason: str | None) -> dict[str, Any]:
        tech = await self._db["technicians"].find_one({"_id": technician_id})
        if tech is None:
            raise not_found("Technician")
        before = tech.get("availability", "AVAILABLE")
        if before != availability:
            result = await self._db["technicians"].update_one({"_id": technician_id, "version": tech.get("version", 0)}, {"$set": {"availability": availability, "availabilityChangedAt": utcnow()}, "$inc": {"version": 1}})
            if result.modified_count != 1:
                raise conflict("VERSION_CONFLICT", "That technician's record changed. Try again.")
            await self._audit.record_as(actor, action="technician.availability", domain=AuditDomain.OPERATIONS, entity_type="TECHNICIAN", entity_id=technician_id, before={"availability": before}, after={"availability": availability}, reason=reason)
        flagged: list[str] = []
        if availability in ("SICK", "ON_LEAVE") and before != availability:
            words = "off sick" if availability == "SICK" else "on leave"
            flagged = await self.technician_unavailable(technician_id, f"{tech['name']} is {words}", (actor.id, actor.role_key))
        elif availability == "AVAILABLE":
            await self.technician_available_again(technician_id)
        return {"availability": availability, "flaggedWorkOrders": len(flagged), "flaggedIds": flagged}

    async def maintenance_history(self, user: AuthUser, limit: int = 60) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if not user.has(P.WORKORDER_READ_CAMPUS):
            tech = await self._db["technicians"].find_one({"userId": user.id})
            query = {"technicianId": tech["_id"] if tech else "none"}
        rows = await self._db["maintenance_history"].find(query).sort([("completedAt", -1), ("_id", -1)]).to_list(length=limit)
        return [{"id": str(row["_id"]), "summary": row["summary"], "roomId": row.get("roomId"), "category": row["category"], "completedAt": ensure_utc(row["completedAt"]).isoformat()} for row in rows]
