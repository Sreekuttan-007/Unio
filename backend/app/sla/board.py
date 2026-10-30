"""SLA lists, the summary, and the escalation sweep.

State is always computed from time on read. The sweep only fires escalations: each (instance, level)
is recorded under a unique id before anyone is told, so an escalation fires once however many
sweeps run.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.outbox import OutboxService
from app.core.scope import EntityType, scope_filter
from app.sla.service import evaluate

NOTIFY_ROLES = {"Department Manager": "DEPARTMENT_MANAGER", "Facilities Administrator": "FACILITIES_ADMIN"}
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
STATE_RANK = {"BREACHED": 0, "AT_RISK": 1, "ON_TRACK": 2, "PAUSED": 3, "MET": 4}


class SlaBoard:
    def __init__(self, db: Any, outbox: OutboxService) -> None:
        self._db = db
        self._outbox = outbox

    async def rows(self, user: AuthUser) -> list[dict[str, Any]]:
        instances = await self._db["sla_instances"].find({"$and": [scope_filter(user, EntityType.SLA), {"resolvedAt": None}]}).to_list(length=1000)
        names = {row["_id"]: row["name"] async for row in self._db["users"].find({"_id": {"$in": [i["assignedUserId"] for i in instances if i.get("assignedUserId")]}}, {"name": 1})}
        out = []
        for instance in instances:
            state = evaluate(instance)
            out.append(
                {
                    "id": instance["_id"], "subject": instance["label"], "subjectId": instance["subjectId"], "priority": instance["priority"], "category": instance["category"],
                    "state": state["state"], "percentElapsed": state["percentElapsed"], "remaining": state["remaining"], "dueAt": state["dueAt"],
                    "owner": names.get(instance.get("assignedUserId") or ""), "escalationLevel": instance.get("escalatedLevel", 0), "risk": None,
                }
            )
        out.sort(key=lambda row: (STATE_RANK.get(row["state"], 9), -row["percentElapsed"], PRIORITY_RANK.get(row["priority"], 9)))
        return out

    async def summary(self, user: AuthUser) -> dict[str, Any]:
        rows = await self.rows(user)
        count = lambda state: sum(1 for row in rows if row["state"] == state)  # noqa: E731
        closed = await self._db["sla_instances"].find({"$and": [scope_filter(user, EntityType.SLA), {"resolvedAt": {"$ne": None}}]}).to_list(length=5000)
        met = sum(1 for instance in closed if evaluate(instance)["state"] == "MET")
        return {"onTrack": count("ON_TRACK"), "atRisk": count("AT_RISK"), "breached": count("BREACHED"), "paused": count("PAUSED"), "compliance": round(met / len(closed) * 100) if closed else 100}

    async def sweep(self, now: datetime | None = None) -> list[str]:
        """Fires every escalation that is due and has not fired. Safe to run as often as you like."""
        now = ensure_utc(now or utcnow())
        fired: list[str] = []
        async for instance in self._db["sla_instances"].find({"resolvedAt": None}):
            state = evaluate(instance, now)
            if state["state"] == "PAUSED":
                continue  # a paused clock does not escalate
            policy = await self._db["sla_policies"].find_one({"_id": instance.get("policyId")}) or {}
            for step in policy.get("escalations", []):
                if state["percentElapsed"] < step["atPercent"] or step["level"] <= instance.get("escalatedLevel", 0):
                    continue
                key = f"{instance['_id']}:{step['level']}"
                try:
                    await self._db["sla_escalations"].insert_one({"_id": key, "instanceId": instance["_id"], "level": step["level"], "at": now, "percent": state["percentElapsed"]})
                except DuplicateKeyError:
                    continue
                await self._db["sla_instances"].update_one({"_id": instance["_id"], "escalatedLevel": {"$lt": step["level"]}}, {"$set": {"escalatedLevel": step["level"]}})
                role = NOTIFY_ROLES.get(step["notify"], "FACILITIES_ADMIN")
                recipients = []
                if role == "DEPARTMENT_MANAGER":
                    # Only the managers of the department the work belongs to, not every manager on campus.
                    recipients = [row["_id"] async for row in self._db["users"].find({"roleKey": role, "managedDepartmentIds": instance.get("departmentId")}, {"_id": 1})]
                payload = {"instanceId": instance["_id"], "subjectId": instance["subjectId"], "label": instance["label"], "level": step["level"], "recipientIds": recipients}
                if role != "DEPARTMENT_MANAGER" or not recipients:
                    payload["roles"] = ["FACILITIES_ADMIN"]
                await self._outbox.enqueue("sla.escalated", payload)
                fired.append(key)
        await self._db["job_runs"].replace_one({"_id": "sla-sweep"}, {"_id": "sla-sweep", "lastRun": now, "fired": len(fired)}, upsert=True)
        return fired
