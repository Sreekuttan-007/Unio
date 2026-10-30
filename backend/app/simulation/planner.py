"""Rule-based recovery plans, judged by the same Collision Engine as live actions, on a snapshot.

Every number in a plan is counted from stored records. Nothing here writes anywhere: the planner only
holds a Snapshot and the engine, and the import-boundary test keeps it that way.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from app.collision.alternatives import AlternativeSuggestionService
from app.collision.engine import CollisionEngine, RuleConfig
from app.collision.models import ActionType, Decision, ProposedAction, Severity
from app.collision.payloads import parse_payload
from app.collision.reader import StateReader
from app.core.clock import ensure_utc, local_time
from app.sla.timer import evaluate as sla_evaluate
from app.simulation.snapshot import Snapshot, SnapshotReader
from app.workorders.scoring import ceil_slot, plan_window, round_minutes

HORIZON_HOURS = 24
MIN_LEAD = timedelta(minutes=15)  # a class starting sooner than this cannot sensibly be moved
MAX_SESSIONS = 12


@dataclass
class Draft:
    id: str
    title: str
    summary: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, str]] = field(default_factory=list)
    depends: dict[str, list[Any]] = field(default_factory=lambda: {"sessions": [], "rooms": [], "technicians": [], "incidents": []})
    moved_people: int = 0

    @property
    def feasible(self) -> bool:
        return not any(finding["severity"] == "HARD" for finding in self.findings)


def rule_config(snapshot: Snapshot) -> dict[str, RuleConfig]:
    return {row["_id"]: RuleConfig(row.get("enabled", True), row.get("params") or {}) for row in snapshot.data["collision_rules"]}


async def fingerprint(reader: StateReader, depends: dict[str, list[Any]]) -> str:
    """A digest of the facts a plan rested on, read through any StateReader, live or snapshot."""
    facts: list[Any] = []
    for room_id, start, end in depends["rooms"]:
        start, end = ensure_utc(datetime.fromisoformat(start)), ensure_utc(datetime.fromisoformat(end))
        facts.append([await reader.room(room_id), await reader.room_occupancy(room_id, start, end)])
    for technician_id in depends["technicians"]:
        facts.append([await reader.technician(technician_id), await reader.technician_tasks(technician_id)])
    for incident_id in depends["incidents"]:
        facts.append(await reader.incident(incident_id))
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()[:24]


class Planner:
    def __init__(self, snapshot: Snapshot, incident: dict[str, Any], now: datetime) -> None:
        self._snapshot = snapshot
        self._incident = incident
        self._now = ensure_utc(now)
        self._engine = CollisionEngine()
        self._alternatives = AlternativeSuggestionService(self._engine)
        self._config = rule_config(snapshot)
        self._out = set(incident.get("impactRoomIds") or incident.get("roomCodes") or [])

    def _sessions(self) -> list[dict[str, Any]]:
        rows = [
            row for row in self._snapshot.data["timetable_sessions"]
            if row["roomId"] in self._out and row.get("status") == "SCHEDULED" and ensure_utc(row["endAt"]) > self._now and ensure_utc(row["startAt"]) < self._now + timedelta(hours=HORIZON_HOURS)
        ]
        rows.sort(key=lambda row: (row["kind"] != "EXAM", ensure_utc(row["startAt"]), -row["headcount"], row["_id"]))
        return rows[:MAX_SESSIONS]

    def _action(self, action_type: ActionType, payload: dict[str, Any]) -> ProposedAction:
        return ProposedAction(type=action_type, actor_id="simulator", actor_role="SYSTEM", payload=parse_payload(action_type, payload), at=self._now, expected_state_token=None)

    @staticmethod
    def _move_payload(session: dict[str, Any], room_id: str) -> dict[str, Any]:
        return {
            "roomId": room_id, "startAt": ensure_utc(session["startAt"]).isoformat(), "endAt": ensure_utc(session["endAt"]).isoformat(), "headcount": session["headcount"],
            "kind": session["kind"], "purpose": session["courseName"], "requiredFeatures": [], "excludeBookingId": None, "excludeSessionId": session["_id"],
        }

    def _depend_session(self, draft: Draft, session: dict[str, Any], room_id: str) -> None:
        window = [ensure_utc(session["startAt"]).isoformat(), ensure_utc(session["endAt"]).isoformat()]
        draft.depends["rooms"].append([session["roomId"], *window])
        draft.depends["rooms"].append([room_id, *window])

    async def _move_plan(self, plan_id: str, title: str, same_building: bool) -> Draft:
        draft = Draft(plan_id, title)
        reader = self._snapshot.reader(self._out)
        sessions = self._sessions()
        rooms_used: set[str] = set()
        building = self._incident.get("buildingId")
        for session in sessions:
            label = f"{session['studentGroup']} {session['courseName']} ({local_time(session['startAt'])})"
            if ensure_utc(session["startAt"]) < self._now + MIN_LEAD:
                draft.findings.append({"severity": "SOFT", "message": f"{label} has already started or starts too soon to move."})
                continue
            action = self._action(ActionType.MOVE_SESSION, self._move_payload(session, session["roomId"]))
            options = await self._alternatives.rooms(action, reader, self._config)
            rooms = {row["_id"]: row for row in reader.memory["rooms"].rows}
            if same_building:
                options = [option for option in options if rooms[option["roomId"]]["buildingId"] == building]
            if not options:
                where = "in the same building" if same_building else "anywhere on campus"
                draft.findings.append({"severity": "HARD", "message": f"No free room {where} fits {label}, {session['headcount']} people."})
                continue
            target = options[0]["roomId"]
            verdict = await self._engine.evaluate(replace(action, payload=parse_payload(ActionType.MOVE_SESSION, self._move_payload(session, target))), reader, self._config)
            for finding in verdict.findings:
                draft.findings.append({"severity": finding.severity.value if finding.severity is not Severity.APPROVAL else "HARD", "message": finding.message})
            if verdict.decision is Decision.BLOCK:
                continue
            reader.apply_move(session["_id"], target)  # the next class sees this one in its new room
            draft.actions.append({"type": "MOVE_SESSION", "sessionId": session["_id"], "roomId": target, "label": f"Move {label} from {session['roomId']} to {target}", "softCodes": sorted(verdict.soft_codes)})
            self._depend_session(draft, session, target)
            rooms_used.add(target)
            draft.moved_people += session["headcount"]
        draft.depends["incidents"].append(self._incident["_id"])
        moved = len(draft.actions)
        draft.summary = (
            f"Moves {moved} of {len(sessions)} affected {'class' if len(sessions) == 1 else 'classes'} into {len(rooms_used)} free {'room' if len(rooms_used) == 1 else 'rooms'}."
            if sessions else "No classes are affected in the next 24 hours, so nothing needs to move."
        )
        draft.metrics = [
            {"label": "Classes affected", "value": str(len(sessions))},
            {"label": "Classes moved", "value": str(moved)},
            {"label": "Rooms used", "value": str(len(rooms_used))},
            {"label": "Students moved", "value": str(draft.moved_people)},
            {"label": "Exams kept on time", "value": f"{sum(1 for a in draft.actions if self._kind(a['sessionId']) == 'EXAM')} of {sum(1 for s in sessions if s['kind'] == 'EXAM')}"},
            self._sla_margin(),
        ]
        return draft

    def _kind(self, session_id: str) -> str:
        return next((row["kind"] for row in self._snapshot.data["timetable_sessions"] if row["_id"] == session_id), "")

    def _sla_margin(self) -> dict[str, str]:
        """How much runway is left on this incident's own SLA clock, independent of which plan is chosen."""
        instance = next((row for row in self._snapshot.data["sla_instances"] if row["subjectId"] == self._incident["_id"]), None)
        if instance is None:
            return {"label": "SLA margin", "value": "Not tracked"}
        return {"label": "SLA margin", "value": sla_evaluate(instance, self._now)["remaining"]}

    async def _repair_plan(self) -> Draft:
        draft = Draft("C", "Repair first and keep classes where they are")
        draft.depends["incidents"].append(self._incident["_id"])
        orders = [row for row in self._snapshot.data["work_orders"] if row.get("incidentId") == self._incident["_id"] and row["status"] not in ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED")]
        sessions = self._sessions()
        if not orders:
            draft.summary = "There is no work order for this incident yet."
            draft.findings.append({"severity": "HARD", "message": f"Create a work order for {self._incident['_id']} before planning the repair."})
            draft.metrics = [{"label": "Classes affected", "value": str(len(sessions))}, self._sla_margin()]
            return draft
        order = orders[0]
        reader: SnapshotReader = self._snapshot.reader(self._out)
        minutes = round_minutes(order.get("estimatedMinutes", 60))
        if order.get("assignedTechnicianId") and order.get("scheduledEndAt"):
            technician_id, start, end = order["assignedTechnicianId"], ensure_utc(order["scheduledStartAt"]), ensure_utc(order["scheduledEndAt"])
            draft.summary = f"Keeps {order['assignedTechnicianName']} on {order['_id']}, finishing at {local_time(end)}."
        else:
            start = ceil_slot(self._now)
            end = start + timedelta(minutes=minutes)
            technician_id = None
            for tech in await reader.all_technicians():
                payload = {"technicianId": tech["_id"], "workOrderId": order["_id"], "startAt": start.isoformat(), "endAt": end.isoformat(), "requiredSkills": order.get("requiredSkills", [])}
                verdict = await self._engine.evaluate(self._action(ActionType.ASSIGN_TECHNICIAN, payload), reader, self._config)
                if verdict.decision is Decision.ALLOW:
                    technician_id = tech["_id"]
                    draft.actions.append({"type": "ASSIGN", "workOrderId": order["_id"], "technicianId": tech["_id"], "label": f"Assign {order['_id']} to {tech['name']} now", "softCodes": []})
                    break
            if technician_id is None:
                draft.findings.append({"severity": "HARD", "message": f"No qualified technician is free to start {order['_id']} now."})
            draft.summary = f"Starts the repair at {local_time(start)} and expects it done by {local_time(end)}."
        if technician_id:
            draft.depends["technicians"].append(technician_id)
        if order["status"] == "BLOCKED" or any(part.get("state") == "SHORT" for part in order.get("partRequirements", [])):
            draft.findings.append({"severity": "HARD", "message": f"{order['_id']} is waiting for a part, so no finishing time can be promised."})
        before = [row for row in sessions if ensure_utc(row["startAt"]) < end]
        for row in before:
            severity = "HARD" if row["kind"] == "EXAM" else "SOFT"
            draft.findings.append({"severity": severity, "message": f"{row['studentGroup']} {row['courseName']} at {local_time(row['startAt'])} in {row['roomId']} starts before the repair is done."})
        draft.metrics = [
            {"label": "Classes affected", "value": str(len(sessions))},
            {"label": "Classes disrupted before the repair", "value": str(len(before))},
            {"label": "Students moved", "value": "0"},
            {"label": "Technician minutes", "value": str(minutes)},
            {"label": "Parts used", "value": ", ".join(f"{p['qty']} x {p['name']}" for p in order.get("partRequirements", [])) or "None"},
            self._sla_margin(),
        ]
        return draft

    async def _repair_next_window_plan(self) -> Draft:
        """Instead of forcing an assignment right now, waits for a technician's next real in-shift window."""
        draft = Draft("D", "Repair in the next free window")
        draft.depends["incidents"].append(self._incident["_id"])
        orders = [row for row in self._snapshot.data["work_orders"] if row.get("incidentId") == self._incident["_id"] and row["status"] not in ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED")]
        sessions = self._sessions()
        if not orders:
            draft.summary = "There is no work order for this incident yet."
            draft.findings.append({"severity": "HARD", "message": f"Create a work order for {self._incident['_id']} before planning the repair."})
            draft.metrics = [{"label": "Classes affected", "value": str(len(sessions))}, self._sla_margin()]
            return draft
        order = orders[0]
        reader: SnapshotReader = self._snapshot.reader(self._out)
        minutes = round_minutes(order.get("estimatedMinutes", 60))
        best: tuple[str, str, datetime, datetime] | None = None
        for tech in await reader.all_technicians():
            tasks = await reader.technician_tasks(tech["_id"], scheduled_only=True, exclude_work_order_id=order["_id"])
            shifts = await reader.technician_shifts(tech["_id"], self._now, self._now + timedelta(hours=72))
            start, end, inside_shift = plan_window(self._now, minutes, tasks, shifts, urgent=False)
            if not inside_shift or (best is not None and start >= best[2]):
                continue  # only a real in-shift window counts for this plan, and only the earliest one
            payload = {"technicianId": tech["_id"], "workOrderId": order["_id"], "startAt": start.isoformat(), "endAt": end.isoformat(), "requiredSkills": order.get("requiredSkills", [])}
            verdict = await self._engine.evaluate(self._action(ActionType.ASSIGN_TECHNICIAN, payload), reader, self._config)
            if verdict.decision is Decision.ALLOW:
                best = (tech["_id"], tech["name"], start, end)
        if best is None:
            draft.findings.append({"severity": "HARD", "message": "No qualified technician has a free in-shift window in the next three days."})
            draft.summary = "No in-shift window was found for any qualified technician."
            end = self._now
        else:
            technician_id, tech_name, start, end = best
            wait_minutes = round((start - self._now).total_seconds() / 60)
            draft.actions.append({"type": "ASSIGN", "workOrderId": order["_id"], "technicianId": technician_id, "label": f"Assign {order['_id']} to {tech_name}, starting {local_time(start)}", "softCodes": []})
            draft.depends["technicians"].append(technician_id)
            draft.summary = (
                f"Waits for {tech_name}'s shift and starts the repair at {local_time(start)} (in {wait_minutes} min), expecting it done by {local_time(end)}."
                if wait_minutes > 0 else f"Starts the repair now with {tech_name}, in their shift, expecting it done by {local_time(end)}."
            )
        if order["status"] == "BLOCKED" or any(part.get("state") == "SHORT" for part in order.get("partRequirements", [])):
            draft.findings.append({"severity": "HARD", "message": f"{order['_id']} is waiting for a part, so no finishing time can be promised."})
        before = [row for row in sessions if ensure_utc(row["startAt"]) < end]
        for row in before:
            severity = "HARD" if row["kind"] == "EXAM" else "SOFT"
            draft.findings.append({"severity": severity, "message": f"{row['studentGroup']} {row['courseName']} at {local_time(row['startAt'])} in {row['roomId']} starts before the repair is done."})
        draft.metrics = [
            {"label": "Classes affected", "value": str(len(sessions))},
            {"label": "Classes disrupted before the repair", "value": str(len(before))},
            {"label": "Students moved", "value": "0"},
            {"label": "Technician minutes", "value": str(minutes)},
            {"label": "Wait before start (minutes)", "value": str(round((best[2] - self._now).total_seconds() / 60)) if best else "N/A"},
            self._sla_margin(),
        ]
        return draft

    async def _stock_vs_buy_plan(self) -> Draft:
        """Compares what the work order's short parts can be reserved from stock right now against what
        still needs a purchase, through the same RESERVE_PARTS check live requests go through."""
        draft = Draft("E", "Use stock, or raise a purchase")
        draft.depends["incidents"].append(self._incident["_id"])
        orders = [row for row in self._snapshot.data["work_orders"] if row.get("incidentId") == self._incident["_id"] and row["status"] not in ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED")]
        if not orders:
            draft.summary = "There is no work order for this incident yet."
            draft.findings.append({"severity": "HARD", "message": f"Create a work order for {self._incident['_id']} before comparing stock and purchase."})
            draft.metrics = [{"label": "Parts short", "value": "0"}, self._sla_margin()]
            return draft
        order = orders[0]
        short_parts = [part for part in order.get("partRequirements", []) if part["state"] == "SHORT"]
        if not short_parts:
            draft.summary = f"{order['_id']} has nothing short: every part it asked for is already reserved or issued."
            draft.metrics = [{"label": "Parts short", "value": "0"}, self._sla_margin()]
            return draft
        reader = self._snapshot.reader(self._out)
        items_by_id = {row["_id"]: row for row in self._snapshot.data["inventory_items"]}
        from_stock, need_purchase, cost_paise = [], [], 0
        for part in short_parts:
            payload = {"work_order_id": order["_id"], "lines": [{"item_id": part["itemId"], "qty": part["qty"]}]}
            verdict = await self._engine.evaluate(self._action(ActionType.RESERVE_PARTS, payload), reader, self._config)
            if any(finding.code == "STOCK_SHORT" for finding in verdict.findings):
                need_purchase.append(part)
                cost_paise += part["qty"] * items_by_id.get(part["itemId"], {}).get("unitCostPaise", 0)
            else:
                from_stock.append(part)
        if need_purchase:
            names = ", ".join(f"{p['qty']} x {p['name']}" for p in need_purchase)
            draft.summary = f"{len(from_stock)} of {len(short_parts)} short parts can come from stock now; {names} must be bought."
            draft.findings.append({"severity": "SOFT", "message": f"{names} must be bought: no store has enough free stock."})
        else:
            draft.summary = f"Every short part for {order['_id']} can be reserved from stock right now, no purchase needed."
        draft.metrics = [
            {"label": "Parts short", "value": str(len(short_parts))},
            {"label": "Available from stock", "value": str(len(from_stock))},
            {"label": "Needs a purchase", "value": str(len(need_purchase))},
            {"label": "Estimated purchase cost", "value": f"₹{cost_paise // 100:,}" if need_purchase else "₹0"},
            self._sla_margin(),
        ]
        return draft

    async def plans(self) -> list[Draft]:
        building = next((row["name"] for row in self._snapshot.data["buildings"] if row["_id"] == self._incident.get("buildingId")), "the same building")
        return [
            await self._move_plan("A", f"Move classes to free rooms in {building}", same_building=True),
            await self._move_plan("B", "Move classes to the best free rooms anywhere", same_building=False),
            await self._repair_plan(),
            await self._repair_next_window_plan(),
            await self._stock_vs_buy_plan(),
        ]


def recommend(drafts: list[Draft]) -> str | None:
    """The feasible plan that disturbs the fewest people and needs the fewest warnings to be accepted."""
    feasible = [draft for draft in drafts if draft.feasible]
    if not feasible:
        return None
    return min(feasible, key=lambda draft: (draft.moved_people, sum(1 for f in draft.findings if f["severity"] == "SOFT"), draft.id)).id
