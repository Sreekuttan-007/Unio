"""SLA timers. Targets are data (the sla_policies collection), and state is always computed from time,
so a sleeping server never shows a stale answer."""

from datetime import datetime
from typing import Any

from app.core.clock import ensure_utc, utcnow
from app.core.ids import next_id
from app.sla.timer import AT_RISK_PERCENT, evaluate

__all__ = ["AT_RISK_PERCENT", "SlaService", "default_policies", "evaluate"]

CATEGORIES = ("ELECTRICAL", "NETWORK", "PLUMBING", "HVAC", "CARPENTRY", "EQUIPMENT", "HOUSEKEEPING", "SAFETY", "OTHER")
PRIORITIES = ("P1", "P2", "P3", "P4")

# priority: (respond within, resolve within) in minutes
DEFAULT_TARGETS = {"P1": (15, 240), "P2": (60, 480), "P3": (120, 1440), "P4": (480, 4320)}
CATEGORY_OVERRIDES = {("ELECTRICAL", "P1"): (10, 180), ("SAFETY", "P1"): (5, 120), ("SAFETY", "P2"): (15, 240)}
LADDER = [{"level": 1, "atPercent": 75, "notify": "Department Manager"}, {"level": 2, "atPercent": 100, "notify": "Facilities Administrator"}]


def default_policies() -> list[dict[str, Any]]:
    policies = []
    for category in CATEGORIES:
        for priority in PRIORITIES:
            response, resolution = CATEGORY_OVERRIDES.get((category, priority), DEFAULT_TARGETS[priority])
            policies.append(
                {
                    "_id": f"SLA-{category[:3]}-{priority}",
                    "category": category,
                    "priority": priority,
                    "responseMinutes": response,
                    "resolutionMinutes": resolution,
                    "atRiskPercent": AT_RISK_PERCENT,
                    "pausable": True,
                    "escalations": LADDER if priority in ("P1", "P2") else LADDER[1:],
                }
            )
    return policies


class SlaService:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_policies(self) -> None:
        from app.core.bulk import insert_missing

        await insert_missing(self._db["sla_policies"], default_policies())

    async def policy_for(self, category: str, priority: str) -> dict[str, Any]:
        found = await self._db["sla_policies"].find_one({"category": category, "priority": priority})
        if found:
            return found
        response, resolution = DEFAULT_TARGETS.get(priority, DEFAULT_TARGETS["P3"])
        return {"_id": "SLA-DEFAULT", "responseMinutes": response, "resolutionMinutes": resolution, "atRiskPercent": AT_RISK_PERCENT, "escalations": LADDER[1:]}

    async def start(
        self, *, subject_type: str, subject_id: str, label: str, category: str, priority: str, owner_ids: list[str], assigned_user_id: str | None,
        department_id: str | None, campus_id: str, started_at: datetime | None = None, paused_reason: str | None = None,
    ) -> dict[str, Any]:
        policy = await self.policy_for(category, priority)
        started = ensure_utc(started_at or utcnow())
        instance = {
            "_id": await next_id(self._db, "SLI", 1000),
            "subjectType": subject_type,
            "subjectId": subject_id,
            "label": label,
            "category": category,
            "priority": priority,
            "policyId": policy["_id"],
            "responseMinutes": policy["responseMinutes"],
            "resolutionMinutes": policy["resolutionMinutes"],
            "atRiskPercent": policy.get("atRiskPercent", AT_RISK_PERCENT),
            "startedAt": started,
            "respondedAt": None,
            "resolvedAt": None,
            "pausedMinutes": 0,
            "pauses": [{"from": started, "to": None, "reason": paused_reason}] if paused_reason else [],
            "subjectOwnerIds": owner_ids,
            "assignedUserId": assigned_user_id,
            "departmentId": department_id,
            "campusId": campus_id,
            "escalatedLevel": 0,
            "version": 0,
        }
        await self._db["sla_instances"].insert_one(instance)
        return instance

    async def for_subject(self, subject_id: str) -> dict[str, Any] | None:
        return await self._db["sla_instances"].find_one({"subjectId": subject_id})

    async def view(self, subject_id: str) -> dict[str, Any]:
        instance = await self.for_subject(subject_id)
        if instance is None:
            return {"state": "ON_TRACK", "percentElapsed": 0, "remaining": "No timer", "dueAt": utcnow().isoformat()}
        return evaluate(instance)

    async def pause(self, subject_id: str, reason: str) -> None:
        instance = await self.for_subject(subject_id)
        if instance is None or instance.get("resolvedAt") or any(pause.get("to") is None for pause in instance["pauses"]):
            return
        await self._db["sla_instances"].update_one({"_id": instance["_id"]}, {"$push": {"pauses": {"from": utcnow(), "to": None, "reason": reason}}})

    async def resume(self, subject_id: str) -> None:
        instance = await self.for_subject(subject_id)
        if instance is None:
            return
        open_pause = next((pause for pause in instance["pauses"] if pause.get("to") is None), None)
        if open_pause is None:
            return
        now = utcnow()
        minutes = (now - ensure_utc(open_pause["from"])).total_seconds() / 60
        pauses = [{**pause, "to": now} if pause is open_pause or pause.get("to") is None else pause for pause in instance["pauses"]]
        await self._db["sla_instances"].update_one({"_id": instance["_id"]}, {"$set": {"pauses": pauses}, "$inc": {"pausedMinutes": minutes}})

    async def finish(self, subject_id: str) -> None:
        await self.resume(subject_id)
        await self._db["sla_instances"].update_one({"subjectId": subject_id, "resolvedAt": None}, {"$set": {"resolvedAt": utcnow()}})

    async def reopen(self, subject_id: str) -> None:
        await self._db["sla_instances"].update_one({"subjectId": subject_id}, {"$set": {"resolvedAt": None}})

    async def reprioritise(self, subject_id: str, category: str, priority: str) -> None:
        policy = await self.policy_for(category, priority)
        await self._db["sla_instances"].update_one(
            {"subjectId": subject_id},
            {"$set": {"priority": priority, "policyId": policy["_id"], "responseMinutes": policy["responseMinutes"], "resolutionMinutes": policy["resolutionMinutes"]}},
        )

    async def assign(self, subject_id: str, user_id: str | None) -> None:
        await self._db["sla_instances"].update_one({"subjectId": subject_id}, {"$set": {"assignedUserId": user_id}})

    async def mark_responded(self, subject_id: str) -> None:
        await self._db["sla_instances"].update_one({"subjectId": subject_id, "respondedAt": None}, {"$set": {"respondedAt": utcnow()}})
