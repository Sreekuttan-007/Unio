"""The rules. Each is a small class that reads facts and returns findings, and decides nothing else.

A rule never writes and never calls another rule. The engine combines what they return.
"""

from datetime import timedelta
from typing import Any, ClassVar

from app.collision.models import ROOM_ACTIONS, ActionType, Finding, ProposedAction, Severity, rupees
from app.collision.reader import StateReader
from app.core.clock import IST, local_time

CLOSED_ROOM_STATES = ("CLOSED", "MAINTENANCE")
DOWN_FEATURES = {"PROJECTOR": ("EQUIPMENT", "projector"), "AIR_CONDITIONING": ("HVAC", "air conditioner")}


class Rule:
    id = ""
    code = ""
    name = ""
    description = ""
    severity = Severity.HARD
    actions: frozenset[ActionType] = frozenset()
    locked = False
    default_params: ClassVar[dict[str, Any]] = {}
    parameter_label: str | None = None

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        raise NotImplementedError

    def finding(self, message: str, *affected: tuple[str, str], code: str | None = None, **data: Any) -> Finding:
        return Finding(code or self.code, self.id, self.severity, message, tuple(affected), data)

    def describe(self, params: dict[str, Any]) -> str | None:
        return None


def _span(start: Any, end: Any) -> str:
    return f"{local_time(start)} to {local_time(end)}"


# ---- rooms ------------------------------------------------------------------------------------------------


class RoomOverlap(Rule):
    id, code = "ROOM-001", "ROOM_OVERLAP"
    name = "Room double-booking"
    description = "A room cannot hold two things at once. Sessions that only touch at an end and a start are fine."
    severity = Severity.HARD
    actions = ROOM_ACTIONS
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        found = await reader.room_occupancy(p["room_id"], p["start_at"], p["end_at"], exclude_session_id=p.get("exclude_session_id"), exclude_booking_id=p.get("exclude_booking_id"))
        return [
            self.finding(
                f"{p['room_id']} is already used by {item['label']} ({item['detail']}) from {_span(item['startAt'], item['endAt'])}.",
                ("ROOM", p["room_id"]), (item["kind"], item["id"]), occupant=item["id"], occupantKind=item["sessionKind"],
            )
            for item in found
        ]


class RoomClosed(Rule):
    id, code = "ROOM-002", "ROOM_CLOSED"
    name = "Room closed or under maintenance"
    description = "A closed room, or a room in a closed building, cannot be used."
    severity = Severity.HARD
    actions = ROOM_ACTIONS
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        room_id = action.payload["room_id"]
        room = await reader.room(room_id)
        if room is None:
            return [self.finding(f"Room {room_id} does not exist.", ("ROOM", room_id), code="ROOM_UNKNOWN")]
        if room["status"] in CLOSED_ROOM_STATES:
            return [self.finding(f"{room_id} is {room['status'].lower()} and cannot be used.", ("ROOM", room_id))]
        building = await reader.building(room["buildingId"])
        if building and building["status"] in CLOSED_ROOM_STATES:
            return [self.finding(f"{building['name']} is {building['status'].lower()}, so {room_id} cannot be used.", ("ROOM", room_id), ("BUILDING", building["_id"]))]
        return []


class RoomBookable(Rule):
    id, code = "ROOM-005", "ROOM_NOT_BOOKABLE"
    name = "Room is not bookable"
    description = "Offices, hostel rooms and common areas are not for booking."
    severity = Severity.HARD
    actions = ROOM_ACTIONS
    locked = False

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        room = await reader.room(action.payload["room_id"])
        if room is not None and not room.get("bookable", False):
            return [self.finding(f"{room['code']} is a {room['type'].lower()} and cannot be booked.", ("ROOM", room["_id"]))]
        return []


class RoomCapacity(Rule):
    id, code = "ROOM-003", "ROOM_CAPACITY"
    name = "Room too small"
    description = "The number of people cannot exceed the seats in the room."
    severity = Severity.HARD
    actions = ROOM_ACTIONS
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        room = await reader.room(action.payload["room_id"])
        headcount = action.payload["headcount"]
        if room is not None and headcount > room["capacity"]:
            return [self.finding(f"{room['code']} seats {room['capacity']}, and this has {headcount} people.", ("ROOM", room["_id"]), seats=room["capacity"], needed=headcount)]
        return []


class RoomType(Rule):
    id, code = "ROOM-004", "ROOM_TYPE"
    name = "Room type does not suit the session"
    description = "Practicals belong in labs, and labs are not for ordinary lectures. Allowed with a reason."
    severity = Severity.SOFT
    actions = ROOM_ACTIONS

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        room = await reader.room(action.payload["room_id"])
        kind = action.payload["kind"]
        if room is None:
            return []
        if kind == "PRACTICAL" and room["type"] != "LAB":
            return [self.finding(f"A practical needs a lab, and {room['code']} is a {room['type'].lower()}.", ("ROOM", room["_id"]))]
        if kind == "LECTURE" and room["type"] == "LAB":
            return [self.finding(f"{room['code']} is a lab. Using it for a lecture takes it from practical classes.", ("ROOM", room["_id"]))]
        return []


class OutsideHours(Rule):
    id, code = "ROOM-006", "OUTSIDE_HOURS"
    name = "Outside opening hours"
    description = "A booking should fall inside the building's opening hours. Allowed with a reason, for example an evening event."
    severity = Severity.SOFT
    actions = ROOM_ACTIONS

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        room = await reader.room(action.payload["room_id"])
        building = await reader.building(room["buildingId"]) if room else None
        hours = (building or {}).get("openingHours", "")
        if not building or "-" not in hours:
            return []  # "24 hours", or unknown: nothing to compare against
        opens, closes = hours.split("-")
        start, end = action.payload["start_at"] + IST, action.payload["end_at"] + IST
        first, last = start.strftime("%H:%M"), end.strftime("%H:%M")
        crosses_midnight = end.date() != start.date() and last != "00:00"
        if first < opens or last > closes or crosses_midnight:
            return [self.finding(f"{building['name']} is open {opens} to {closes}, and this runs {_span(action.payload['start_at'], action.payload['end_at'])}.", ("BUILDING", building["_id"]))]
        return []


class AssetDown(Rule):
    id, code = "ASSET-001", "ASSET_DOWN"
    name = "Required equipment is down"
    description = "A room whose required equipment is faulty or in maintenance cannot be booked for that need."
    severity = Severity.HARD
    actions = ROOM_ACTIONS
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        wanted = [feature for feature in action.payload.get("required_features", []) if feature in DOWN_FEATURES]
        if not wanted:
            return []
        assets = await reader.room_assets(action.payload["room_id"])
        findings = []
        for feature in wanted:
            category, noun = DOWN_FEATURES[feature]
            for asset in assets:
                if asset["category"] == category and noun in (asset["name"] or "").lower() and asset["status"] != "OK":
                    findings.append(self.finding(f"The {noun} in {action.payload['room_id']} is {str(asset['status']).lower()}.", ("ASSET", asset["_id"]), ("ROOM", action.payload["room_id"])))
        return findings


# ---- technicians ---------------------------------------------------------------------------------------------


class TechSkill(Rule):
    id, code = "TECH-001", "TECH_SKILL"
    name = "Technician lacks the skill"
    description = "The technician must hold every required skill at the level the job needs."
    severity = Severity.HARD
    actions = frozenset({ActionType.ASSIGN_TECHNICIAN})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        tech = await reader.technician(action.payload["technician_id"])
        if tech is None:
            return [self.finding(f"Technician {action.payload['technician_id']} does not exist.", ("TECHNICIAN", action.payload["technician_id"]), code="TECH_UNKNOWN")]
        held = {skill["code"]: skill["level"] for skill in tech["skills"]}
        findings = []
        for need in action.payload["required_skills"]:
            level = held.get(need["code"])
            if level is None:
                findings.append(self.finding(f"{tech['name']} does not hold the {need['code']} skill this job needs.", ("TECHNICIAN", tech["_id"]), skill=need["code"]))
            elif level < need["min_level"]:
                findings.append(self.finding(f"{tech['name']} holds {need['code']} at level {level}, and this job needs level {need['min_level']}.", ("TECHNICIAN", tech["_id"]), skill=need["code"]))
        return findings


class TechAvailable(Rule):
    id, code = "TECH-005", "TECH_UNAVAILABLE"
    name = "Technician is away"
    description = "A technician on leave or sick cannot be given work."
    severity = Severity.HARD
    actions = frozenset({ActionType.ASSIGN_TECHNICIAN})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        tech = await reader.technician(action.payload["technician_id"])
        if tech is not None and tech.get("availability") in ("ON_LEAVE", "SICK"):
            reason = "on leave" if tech["availability"] == "ON_LEAVE" else "off sick"
            return [self.finding(f"{tech['name']} is {reason}.", ("TECHNICIAN", tech["_id"]))]
        return []


class TechOverlap(Rule):
    id, code = "TECH-002", "TECH_OVERLAP"
    name = "Technician double-booked"
    description = "A technician cannot do two scheduled jobs at the same time."
    severity = Severity.HARD
    actions = frozenset({ActionType.ASSIGN_TECHNICIAN})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        tech = await reader.technician(p["technician_id"])
        if tech is None:
            return []
        tasks = await reader.technician_tasks(p["technician_id"], scheduled_only=True, exclude_work_order_id=p.get("work_order_id"))
        return [
            self.finding(f"{tech['name']} is already on {task['id']} from {_span(task['startAt'], task['endAt'])}.", ("TECHNICIAN", tech["_id"]), ("WORK_ORDER", task["id"]))
            for task in tasks
            if task["startAt"] and task["endAt"] and task["startAt"] < p["end_at"] and task["endAt"] > p["start_at"]
        ]


class TechShift(Rule):
    id, code = "TECH-004", "TECH_SHIFT"
    name = "Outside the technician's shift"
    description = "The job should fall inside a shift. Allowed with a reason, for urgent work."
    severity = Severity.SOFT
    actions = frozenset({ActionType.ASSIGN_TECHNICIAN})
    default_params: ClassVar[dict[str, Any]] = {"graceMinutes": 0}
    parameter_label = "Grace period in minutes"

    def describe(self, params: dict[str, Any]) -> str | None:
        return f"Grace {params.get('graceMinutes', 0)} min"

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        tech = await reader.technician(p["technician_id"])
        if tech is None:
            return []
        grace = timedelta(minutes=int(params.get("graceMinutes", 0)))
        shifts = await reader.technician_shifts(p["technician_id"], p["start_at"] - grace, p["end_at"] + grace)
        if any(shift["startAt"] - grace <= p["start_at"] and shift["endAt"] + grace >= p["end_at"] for shift in shifts):
            return []
        message = f"{p['work_order_id'] or 'This job'} runs {_span(p['start_at'], p['end_at'])}, outside {tech['name']}'s shift."
        return [self.finding(message, ("TECHNICIAN", tech["_id"]))]


class TechWorkload(Rule):
    id, code = "TECH-003", "TECH_WORKLOAD"
    name = "Technician workload"
    description = "Warns when another job would take a technician past the number of tasks they can hold."
    severity = Severity.SOFT
    actions = frozenset({ActionType.ASSIGN_TECHNICIAN})
    default_params: ClassVar[dict[str, Any]] = {"maxConcurrent": None}
    parameter_label = "Maximum open tasks (blank uses each technician's own limit)"

    def describe(self, params: dict[str, Any]) -> str | None:
        limit = params.get("maxConcurrent")
        return f"Max {limit} tasks" if limit else "Each technician's own limit"

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        tech = await reader.technician(p["technician_id"])
        if tech is None:
            return []
        limit = int(params.get("maxConcurrent") or tech.get("maxConcurrentTasks", 3))
        open_tasks = await reader.technician_tasks(p["technician_id"], exclude_work_order_id=p.get("work_order_id"))
        if len(open_tasks) + 1 > limit:
            return [self.finding(f"{tech['name']} already has {len(open_tasks)} of {limit} tasks, and this would be one more.", ("TECHNICIAN", tech["_id"]), open=len(open_tasks), limit=limit)]
        return []


# ---- stock ------------------------------------------------------------------------------------------------------


class StockShort(Rule):
    id, code = "STOCK-001", "STOCK_SHORT"
    name = "Not enough stock"
    description = "A part cannot be reserved if there is not enough free stock. The work order is then blocked."
    severity = Severity.HARD
    actions = frozenset({ActionType.RESERVE_PARTS})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        needed: dict[str, int] = {}
        for line in action.payload["lines"]:
            needed[line["item_id"]] = needed.get(line["item_id"], 0) + line["qty"]
        findings = []
        for item_id, qty in needed.items():
            item = await reader.item(item_id)
            if item is None:
                findings.append(self.finding(f"Item {item_id} is not in the inventory.", ("ITEM", item_id), code="ITEM_UNKNOWN"))
                continue
            balances = await reader.stock(item_id)
            free = sum(balance["available"] for balance in balances)
            held = sum(balance["reserved"] for balance in balances)
            if free < qty:
                reserved_note = f" ({held} are reserved for other work)" if held else ""
                findings.append(
                    self.finding(f"Need {qty} x {item['name']}, but only {max(free, 0)} {'is' if free == 1 else 'are'} free{reserved_note}.", ("ITEM", item_id), needed=qty, free=max(free, 0), shortBy=qty - max(free, 0), itemName=item["name"])
                )
        return findings


class DuplicateReservation(Rule):
    id, code = "STOCK-002", "DUPLICATE_RESERVATION"
    name = "Part reserved twice"
    description = "The same part cannot be reserved twice for one work order."
    severity = Severity.HARD
    actions = frozenset({ActionType.RESERVE_PARTS})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        findings = []
        seen: set[str] = set()
        work_order = action.payload["work_order_id"]
        for line in action.payload["lines"]:
            item_id = line["item_id"]
            item = await reader.item(item_id)
            name = item["name"] if item else item_id
            if item_id in seen:
                findings.append(self.finding(f"{name} appears twice in this request. Combine the quantities into one line.", ("ITEM", item_id)))
            elif await reader.active_reservations(work_order, item_id):
                findings.append(self.finding(f"{work_order} already has {name} reserved.", ("ITEM", item_id), ("WORK_ORDER", work_order)))
            seen.add(item_id)
        return findings


# ---- approvals and integrity ----------------------------------------------------------------------------------------


class SelfApproval(Rule):
    id, code = "APPR-001", "SELF_APPROVAL"
    name = "No self-approval"
    description = "Nobody can decide a request they raised themselves."
    severity = Severity.HARD
    actions = frozenset({ActionType.DECIDE_APPROVAL})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        if action.actor_id == p["requester_id"]:
            return [self.finding(f"You raised {p['approval_id']}, so someone else must decide it.", ("APPROVAL", p["approval_id"]))]
        return []


class ApprovalLimit(Rule):
    id, code = "APPR-002", "APPROVAL_LIMIT"
    name = "Amount above the approver's limit"
    description = "An approver can decide only up to their own limit. Larger amounts go to a higher approver."
    severity = Severity.APPROVAL
    actions = frozenset({ActionType.DECIDE_APPROVAL})

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        if action.payload["decision"] != "APPROVE":
            return []
        user = await reader.user(action.actor_id)
        limit = user["approvalLimitPaise"] if user else 0
        amount = action.payload["amount_paise"]
        if amount > limit:
            return [self.finding(f"{rupees(amount)} is above your approval limit of {rupees(limit)}, so it needs a higher approver.", ("APPROVAL", action.payload["approval_id"]), amount=amount, limit=limit)]
        return []


class SeparationOfDuties(Rule):
    id, code = "APPR-003", "SEPARATION_OF_DUTIES"
    name = "Separation of duties"
    description = "People who configure the system do not approve spending, and whoever raised or received an order does not verify its receipt."
    severity = Severity.HARD
    actions = frozenset({ActionType.DECIDE_APPROVAL, ActionType.VALIDATE_RECEIPT})
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        p = action.payload
        if action.type is ActionType.DECIDE_APPROVAL:
            if action.actor_role == "SYSTEM_ADMIN":
                return [self.finding("System administrators configure the system and do not approve spending.", ("APPROVAL", p["approval_id"]))]
            return []
        clash = {person for person in (p.get("requester_id"), p.get("received_by")) if person}
        if action.actor_id in clash:
            return [self.finding(f"You raised or received the goods for {p['receipt_id']}, so someone else must verify it.", ("RECEIPT", p["receipt_id"]))]
        return []


class DependencyOrder(Rule):
    id, code = "DEP-001", "DEPENDENCY_ORDER"
    name = "Cause before consequence"
    description = "An incident cannot be resolved while the incident that caused it is still open."
    severity = Severity.HARD
    actions = frozenset({ActionType.RESOLVE_INCIDENT})

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        incident = await reader.incident(action.payload["incident_id"])
        if incident is None or not incident["causedById"]:
            return []
        cause = await reader.incident(incident["causedById"])
        if cause and cause["status"] not in ("RESOLVED", "CLOSED"):
            return [self.finding(f"{cause['_id']} caused this and is not resolved yet.", ("INCIDENT", cause["_id"]), ("INCIDENT", incident["_id"]))]
        return []


class StaleState(Rule):
    """Run last by the engine, because it compares the facts everything else read."""

    id, code = "STATE-001", "STALE_STATE"
    name = "State changed since the preview"
    description = "If anything the decision rested on has changed since it was previewed, the action is refused and must be previewed again."
    severity = Severity.HARD
    actions = frozenset(ActionType)
    locked = True

    async def check(self, action: ProposedAction, reader: StateReader, params: dict[str, Any]) -> list[Finding]:
        if action.expected_state_token and action.expected_state_token != reader.token():
            return [self.finding("Something changed since this was checked. Nothing was done. Check it again.", ("STATE", "token"))]
        return []


ALL_RULES: tuple[Rule, ...] = (
    RoomOverlap(), RoomClosed(), RoomCapacity(), RoomBookable(), RoomType(), OutsideHours(), AssetDown(),
    TechSkill(), TechAvailable(), TechOverlap(), TechShift(), TechWorkload(),
    StockShort(), DuplicateReservation(),
    SelfApproval(), ApprovalLimit(), SeparationOfDuties(), DependencyOrder(), StaleState(),
)
RULES_BY_ID = {item.id: item for item in ALL_RULES}


def catalog() -> list[dict[str, Any]]:
    """The documents seeded into collision_rules."""
    return [
        {
            "_id": item.id, "code": item.code, "name": item.name, "description": item.description,
            "actionTypes": sorted(action.value for action in item.actions), "severity": item.severity.value,
            "enabled": True, "locked": item.locked, "params": dict(item.default_params), "version": 0,
        }
        for item in ALL_RULES
    ]
