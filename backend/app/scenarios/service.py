"""One-click demo resets. Wipes operational data, reseeds the campus with times moved to now, then stages
the chosen scenario through the normal services, as the demo users would.

Only for demo deployments: it refuses unless demo mode is on, and it keeps the audit trail.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.audit.service import AuditDomain
from app.campus.seed import monday_of, seed_campus
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import not_found, rule

SCENARIOS = (
    {"id": "A", "title": "Scenario A: exam room lost", "description": "A power fault closes the room of a morning exam. Bookings collide, the simulator compares recovery plans, and only the affected people are told.", "covers": ["M5", "Cascading impact", "Simulator"]},
    {"id": "B", "title": "Scenario B: Wi-Fi outage", "description": "Reports arrive by form and email. They merge into one incident with a summary, and a replayed webhook changes nothing.", "covers": ["M1", "M2", "C4", "C5"]},
    {"id": "C", "title": "Scenario C: critical part out of stock", "description": "A technician flags a missing part, work is blocked, a purchase is approved by someone other than the requester, and an invoice is checked before stock is posted once.", "covers": ["M6", "M7", "Invoice to inventory"]},
    {"id": "D", "title": "Scenario D: technician unavailable", "description": "A technician marks themselves sick. Their work is flagged, an unqualified replacement is refused, and a qualified one is proposed.", "covers": ["M4", "Collision engine"]},
)

# Everything a demo changes. Users, roles, rules, policies and the audit trail are kept.
OPERATIONAL = (
    "incidents", "reports", "ai_suggestions", "inbound_emails", "sla_instances", "sla_escalations", "work_orders", "work_order_events", "technician_slots",
    "room_slots", "bookings", "collision_checks", "impact_snapshots", "simulation_runs", "reservations", "stock_ledger", "approvals", "purchase_orders",
    "invoices", "goods_receipts", "file_objects", "file_blobs", "notifications", "outbox_events", "webhook_deliveries", "webhook_received", "idempotency_keys",
    "counters", "maintenance_history", "job_runs", "notices",
)
SEEDED = ("buildings", "floors", "rooms", "assets", "dependency_edges", "faculty", "student_groups", "timetable_sessions", "technicians", "shifts", "stock_locations", "inventory_items", "inventory_balances", "campus_map")
IST = timedelta(hours=5, minutes=30)


class ScenarioService:
    def __init__(self, services: Any) -> None:
        self._s = services

    def list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in SCENARIOS]

    async def _as(self, user_id: str) -> AuthUser:
        user = await self._s.db["users"].find_one({"_id": user_id})
        roles = self._s.roles
        return AuthUser(
            id=user["_id"], name=user["name"], email=user["email"], role_key=user["roleKey"], campus_id=user["campusId"], department_id=user.get("departmentId"),
            managed_department_ids=tuple(user.get("managedDepartmentIds", [])), approval_limit_paise=int(user.get("approvalLimitPaise", 0)),
            permissions=roles.permissions_of(user), scopes=roles.scopes_of(user["roleKey"]), token_id="scenario-reset", token_expires_at=utcnow() + timedelta(minutes=5),
        )

    async def reset(self, actor: AuthUser, scenario_id: str) -> dict[str, Any]:
        if not self._s.settings.demo_mode_enabled:
            raise rule("NOT_A_DEMO", "Resetting wipes live data, so it only works on a demo deployment.")
        if scenario_id not in {item["id"] for item in SCENARIOS}:
            raise not_found("Scenario")
        db = self._s.db
        for name in OPERATIONAL + SEEDED:
            await db[name].delete_many({})
        await db["seed_state"].delete_many({"_id": "campus"})
        await seed_campus(db, self._s.settings.campus_id, monday_of((utcnow() + IST).date()))
        await self._s.bookings.claim_sessions()
        await self._s.webhooks.ensure_default(self._s.settings.campus_id)
        now = utcnow()
        # Seeded shifts follow the calendar; give every technician one around now so the demo works at any hour.
        await db["shifts"].insert_many(
            [{"_id": f"SH-DEMO-{tech['_id']}", "technicianId": tech["_id"], "startAt": now - timedelta(hours=1), "endAt": now + timedelta(hours=10), "kind": "REGULAR", "campusId": tech["campusId"]} async for tech in db["technicians"].find({})]
        )
        detail = await getattr(self, f"_stage_{scenario_id.lower()}")()
        await self._s.audit.record_as(actor, action="scenario.reset", domain=AuditDomain.SYSTEM, entity_type="SCENARIO", entity_id=scenario_id, after={"detail": detail})
        return {"ok": True, "message": f"The campus is back to Scenario {scenario_id}. Times were moved to now. {detail}"}

    # ---- staging, through the normal services --------------------------------------------------------------------

    async def _incident(self, user_id: str, text: str, channel: str = "FORM") -> str:
        user = await self._as(user_id)
        extraction = await self._s.ml.extract(text)
        return (await self._s.incidents.submit(user.id, user.name, text, extraction, channel, actor_role=user.role_key))["incidentId"]  # type: ignore[no-any-return]

    async def _next_exam_slot(self) -> None:
        """Moves the CSE-3A exam to the next 09:00 campus time at least an hour away, so it is in the affected window."""
        now = utcnow()
        local = now + IST
        start = local.replace(hour=9, minute=0, second=0, microsecond=0) - IST
        if start < now + timedelta(hours=1):
            start += timedelta(days=1)
        exam = await self._s.db["timetable_sessions"].find_one({"kind": "EXAM"})
        if exam:
            await self._s.db["timetable_sessions"].update_many({"roomId": exam["roomId"], "startAt": {"$lt": start + timedelta(hours=3)}, "endAt": {"$gt": start}, "_id": {"$ne": exam["_id"]}}, {"$set": {"status": "CANCELLED"}})
            await self._s.db["timetable_sessions"].update_one({"_id": exam["_id"]}, {"$set": {"startAt": start, "endAt": start + timedelta(hours=3)}})
            await self._s.db["room_slots"].delete_many({"ownerId": exam["_id"]})
            await self._s.bookings.claim_sessions()

    async def _stage_a(self) -> str:
        await self._next_exam_slot()
        incident_id = await self._incident("U-FACULTY", "Power cut in ARB-204, the floor 2 panel tripped and the exam room is dark")
        await self._s.cascade.recompute(await self._as("U-FACILITIES"), incident_id, ["AST-DB-ARB-F2"])
        return f"{incident_id} is a power fault on the ARB floor 2 panel; the CSE-3A exam is affected."

    async def _stage_b(self) -> str:
        first = await self._incident("U-STUDENT", "Wi-Fi is down in Aryabhata Block, nothing loads")
        await self._incident("U-FACULTY", "The Wi-Fi in Aryabhata Block is down, cannot take attendance")
        await self._s.inbox.receive("hod.cse@unio.demo", "Wi-Fi outage in ARB", "The wifi in Aryabhata Block is not working on any floor.", message_id="<demo-b-1@unio.demo>", in_reply_to=None)
        return f"Reports joined {first}; one email waits in the Intake Inbox."

    async def _stage_c(self) -> str:
        incident_id = await self._incident("U-FACULTY", "The 32A breaker on the ARB floor 2 panel keeps tripping, room ARB-204 has no power")
        facilities, tech = await self._as("U-FACILITIES"), await self._as("U-TECH")
        await self._s.workorders.create_from_incident(facilities, incident_id)
        order = await self._s.db["work_orders"].find_one({"incidentId": incident_id})
        await self._s.workorders.assign(facilities, order["_id"], "T-01")
        await self._s.workorders.accept(tech, order["_id"])
        await self._s.workorders.start(tech, order["_id"])
        await self._s.workorders.block(tech, order["_id"], "WAITING_FOR_PARTS", "The breaker is burnt out", [{"item_id": "ITM-MCB-32A-3P", "qty": 2}])
        return f"{order['_id']} is blocked on 2 x MCB 32A three pole; the purchase request waits in the Procurement queue."

    async def _stage_d(self) -> str:
        incident_id = await self._incident("U-FACULTY", "Sockets sparking in ARB-205, burning smell near the front desk")
        facilities, tech = await self._as("U-FACILITIES"), await self._as("U-TECH")
        await self._s.workorders.create_from_incident(facilities, incident_id)
        order = await self._s.db["work_orders"].find_one({"incidentId": incident_id})
        await self._s.workorders.assign(facilities, order["_id"], "T-01")
        await self._s.workorders.accept(tech, order["_id"])
        return f"{order['_id']} is with Ravi Kumar. Sign in as the technician and mark yourself sick to see it flagged."
