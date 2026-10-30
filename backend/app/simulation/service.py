"""Runs and executes recovery simulations.

run() reads live data once into a Snapshot and writes only its own simulation_runs record.
execute() is the only path from a plan to live data: it recomputes the fingerprint of the facts the
plan depended on, refuses with STALE if any changed, and otherwise applies each step through the
normal services as the person executing, so every live rule and audit applies again.
"""

from __future__ import annotations

from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.bookings.service import OPEN_INCIDENT, BookingService
from app.collision.models import Acknowledgement
from app.collision.reader import LiveStateReader
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import conflict, not_found, rule
from app.core.ids import next_id
from app.incidents.service import IncidentService
from app.simulation.planner import Planner, fingerprint, recommend
from app.simulation.snapshot import Snapshot
from app.workorders.service import WorkOrderService


class SimulationService:
    def __init__(self, db: Any, incidents: IncidentService, bookings: BookingService, workorders: WorkOrderService, audit: AuditService) -> None:
        self._db = db
        self._incidents = incidents
        self._bookings = bookings
        self._workorders = workorders
        self._audit = audit

    @staticmethod
    def view(run: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": run["_id"], "incidentId": run["incidentId"], "snapshotAt": ensure_utc(run["snapshotAt"]).isoformat(), "snapshotHash": run["snapshotHash"],
            "recommendedPlanId": run["recommendedPlanId"], "status": run["status"],
            "plans": [
                {
                    "id": plan["id"], "title": plan["title"], "summary": plan["summary"], "feasible": plan["feasible"], "metrics": plan["metrics"],
                    "findings": plan["findings"], "actions": [step["label"] for step in plan["steps"]],
                }
                for plan in run["plans"]
            ],
        }

    async def run(self, user: AuthUser, incident_id: str) -> dict[str, Any]:
        incident = await self._incidents.get(user, incident_id)
        if incident["status"] not in OPEN_INCIDENT:
            raise rule("INCIDENT_CLOSED", "This incident is already resolved, so there is nothing to recover from.")
        now = utcnow()
        snapshot = await Snapshot.load(self._db, now)
        frozen = next((row for row in snapshot.data["incidents"] if row["_id"] == incident_id), incident)
        drafts = await Planner(snapshot, frozen, now).plans()
        plans = []
        for draft in drafts:
            plans.append(
                {
                    "id": draft.id, "title": draft.title, "summary": draft.summary, "feasible": draft.feasible, "metrics": draft.metrics, "findings": draft.findings,
                    "steps": draft.actions, "depends": draft.depends, "fingerprint": await fingerprint(snapshot.reader(), draft.depends),
                }
            )
        run = {
            "_id": await next_id(self._db, "SIM", 1000), "incidentId": incident_id, "snapshotAt": now, "snapshotHash": snapshot.hash, "plans": plans,
            "recommendedPlanId": recommend(drafts), "status": "READY", "createdBy": user.id, "createdAt": now,
        }
        await self._db["simulation_runs"].insert_one(run)  # the only write a simulation makes
        return self.view(run)

    async def get(self, user: AuthUser, run_id: str) -> dict[str, Any]:
        run = await self._db["simulation_runs"].find_one({"_id": run_id})
        if run is None:
            raise not_found("Simulation")
        await self._incidents.get(user, run["incidentId"])
        return run  # type: ignore[no-any-return]

    async def execute(self, user: AuthUser, run_id: str, plan_id: str) -> dict[str, Any]:
        run = await self.get(user, run_id)
        plan = next((item for item in run["plans"] if item["id"] == plan_id), None)
        if plan is None:
            raise not_found("Plan")
        if not plan["feasible"]:
            raise rule("PLAN_BLOCKED", "A blocked plan cannot be executed. Its findings say why.")
        if run["status"] != "READY":
            raise conflict("ALREADY_EXECUTED", f"Plan {run.get('executedPlanId')} from this simulation was already executed. Run a new simulation.")
        if await fingerprint(LiveStateReader(self._db), plan["depends"]) != plan["fingerprint"]:
            await self._db["simulation_runs"].update_one({"_id": run_id, "status": "READY"}, {"$set": {"status": "STALE"}})
            return {"status": "STALE", "message": "Something this plan relied on has changed since the simulation. Nothing was applied. Run the simulation again."}
        # Claim the run so a double tap cannot apply the plan twice.
        claimed = await self._db["simulation_runs"].update_one({"_id": run_id, "status": "READY"}, {"$set": {"status": "EXECUTING", "executedPlanId": plan_id, "executedBy": user.id}})
        if claimed.modified_count != 1:
            raise conflict("ALREADY_EXECUTED", "This simulation is already being executed.")
        done: list[str] = []
        reason = f"Recovery plan {plan_id} from simulation {run_id}"
        try:
            for step in plan["steps"]:
                acknowledgement = Acknowledgement(codes=tuple(step["softCodes"]), reason=reason) if step["softCodes"] else None
                if step["type"] == "MOVE_SESSION":
                    await self._bookings.move_session(user, step["sessionId"], step["roomId"], None, None, acknowledgement, None)
                elif step["type"] == "ASSIGN":
                    await self._workorders.assign(user, step["workOrderId"], step["technicianId"], acknowledgement=acknowledgement)
                done.append(step["label"])
        except Exception:
            await self._db["simulation_runs"].update_one({"_id": run_id}, {"$set": {"status": "PARTIAL", "applied": done}})
            raise
        await self._db["simulation_runs"].update_one({"_id": run_id}, {"$set": {"status": "EXECUTED", "applied": done, "executedAt": utcnow()}})
        await self._audit.record_as(
            user, action="simulation.execute", domain=AuditDomain.OPERATIONS, entity_type="SIMULATION", entity_id=run_id, after={"planId": plan_id, "steps": done, "incidentId": run["incidentId"]},
        )
        await self._incidents.refresh_impact(run["incidentId"])
        message = f"Plan {plan_id} applied: {'; '.join(done)}." if done else f"Plan {plan_id} needed no changes."
        return {"status": "EXECUTED", "message": message}
