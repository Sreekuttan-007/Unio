"""Approvals for purchases, costly repairs and overrides.

Routing comes from the approval_rules table, never from code. Self-approval, approval limits and
separation of duties are the collision rules, checked again at the moment of decision. An approved
purchase is re-validated before it is executed, and a request that no longer makes sense is STALE.
"""

from __future__ import annotations

from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.collision.models import ActionType
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import conflict, not_found, rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.core.permission import Permission as P
from app.core.scope import EntityType, scope_filter

OPEN = ("SUBMITTED", "UNDER_REVIEW", "NEEDS_CLARIFICATION")
DECIDE = {"PURCHASE": P.APPROVAL_DECIDE_PURCHASE, "COSTLY_REPAIR": P.APPROVAL_DECIDE_REPAIR, "OVERRIDE": P.APPROVAL_DECIDE_OVERRIDE}
ROLE_WORD = {"PROCUREMENT_APPROVER": "a Procurement Approver", "DEPARTMENT_MANAGER": "a Department Manager", "FACILITIES_ADMIN": "the Facilities Administrator"}


def rupees(paise: int) -> str:
    return f"₹{paise // 100:,}"


class ApprovalService:
    def __init__(self, db: Any, collisions: CollisionService, audit: AuditService, outbox: OutboxService, campus_id: str) -> None:
        self._db = db
        self._collisions = collisions
        self._audit = audit
        self._outbox = outbox
        self._campus_id = campus_id
        self.procurement: Any = None  # set by build_services: turns an approved purchase into an order

    # ---- routing --------------------------------------------------------------------------------------------

    async def route(self, kind: str, amount: int) -> tuple[str, str]:
        rules = await self._db["approval_rules"].find({"type": kind}).to_list(length=20)
        rules.sort(key=lambda row: (row.get("maxPaise") is None, row.get("maxPaise") or 0))
        if not rules:
            raise rule("NO_APPROVAL_RULE", f"No approval rule covers {kind.lower().replace('_', ' ')} requests. Ask an administrator to add one.")
        chosen = next((row for row in rules if row.get("maxPaise") is None or amount <= row["maxPaise"]), rules[-1])
        skipped = [row for row in rules if row.get("maxPaise") is not None and amount > row["maxPaise"]]
        words = f"Routed to {ROLE_WORD.get(chosen['approverRole'], chosen['approverRole'])}."
        if skipped:
            words = f"Above the {rupees(skipped[-1]['maxPaise'])} {ROLE_WORD.get(skipped[-1]['approverRole'], '').removeprefix('a ').removeprefix('the ')} limit, so {words[0].lower()}{words[1:]}"
        return chosen["approverRole"], words

    # ---- reading ----------------------------------------------------------------------------------------------

    def _actions(self, approval: dict[str, Any], user: AuthUser, limit: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        if approval["status"] not in OPEN:
            return [], []
        if approval["requesterId"] == user.id:
            return [], [{"key": "approval.approve", "label": "Approve", "reason": "You raised this request, so someone else must decide it. Nobody approves their own request."}]
        if not user.has(DECIDE[approval["type"]]):
            return [], []
        if approval["amountPaise"] > limit:
            return [{"key": "approval.reject", "label": "Reject"}, {"key": "approval.clarify", "label": "Ask for clarification"}], [
                {"key": "approval.approve", "label": "Approve", "reason": f"{rupees(approval['amountPaise'])} is above your {rupees(limit)} limit, so it goes to a higher approver."}
            ]
        return [{"key": "approval.approve", "label": "Approve"}, {"key": "approval.reject", "label": "Reject"}, {"key": "approval.clarify", "label": "Ask for clarification"}], []

    async def _limit(self, user: AuthUser) -> int:
        return user.approval_limit_paise

    def view(self, approval: dict[str, Any], user: AuthUser, limit: int) -> dict[str, Any]:
        available, unavailable = self._actions(approval, user, limit)
        return {
            "id": approval["_id"], "type": approval["type"], "status": approval["status"], "title": approval["title"], "requesterName": approval["requesterName"],
            "requesterRole": approval["requesterRole"], "amountPaise": approval["amountPaise"], "justification": approval["justification"],
            "linkedWorkOrderId": approval.get("linkedWorkOrderId"), "linkedIncidentId": approval.get("linkedIncidentId"),
            "lines": [{"name": line["name"], "qty": line["qty"], "estimatePaise": line["qty"] * line.get("unitPaise", 0)} for line in approval.get("lines", [])],
            "evidence": approval.get("evidence", []), "routing": approval["routing"],
            "decisions": [{**row, "at": ensure_utc(row["at"]).isoformat()} for row in approval.get("decisions", [])],
            "purchaseOrderId": approval.get("purchaseOrderId"), "createdAt": ensure_utc(approval["createdAt"]).isoformat(),
            "availableActions": available, "unavailableActions": unavailable,
        }

    def _scope(self, user: AuthUser) -> dict[str, Any]:
        if user.has(P.APPROVAL_READ_ALL):
            return {"campusId": self._campus_id}
        options = [{"requesterId": user.id}]
        if user.has(P.APPROVAL_READ_DEPARTMENT) and user.managed_department_ids:
            options.append({"departmentId": {"$in": list(user.managed_department_ids)}})
        return {"$or": options} if user.has_any((P.APPROVAL_READ_OWN, P.APPROVAL_READ_DEPARTMENT)) else scope_filter(user, EntityType.APPROVAL)

    async def list(self, user: AuthUser) -> list[dict[str, Any]]:
        rows = await self._db["approvals"].find(self._scope(user)).sort("createdAt", -1).to_list(length=300)
        limit = await self._limit(user)
        rows.sort(key=lambda row: (row["status"] not in OPEN, -ensure_utc(row["createdAt"]).timestamp()))
        return [self.view(row, user, limit) for row in rows]

    async def get(self, user: AuthUser, approval_id: str) -> dict[str, Any]:
        row = await self._db["approvals"].find_one({"$and": [{"_id": approval_id}, self._scope(user)]})
        if row is None:
            raise not_found("Approval")
        return row  # type: ignore[no-any-return]

    # ---- raising ------------------------------------------------------------------------------------------------

    async def _insert(self, *, kind: str, title: str, justification: str, amount: int, requester: dict[str, Any], department_id: str | None, lines: list[dict[str, Any]],
                      work_order_id: str | None = None, incident_id: str | None = None, evidence: list[dict[str, str]] | None = None) -> dict[str, Any]:
        role, routing = await self.route(kind, amount)
        now = utcnow()
        approval = {
            "_id": await next_id(self._db, "APR", 620), "type": kind, "status": "SUBMITTED", "title": title, "justification": justification, "amountPaise": amount,
            "requesterId": requester["id"], "requesterName": requester["name"], "requesterRole": requester["role"], "departmentId": department_id, "campusId": self._campus_id,
            "linkedWorkOrderId": work_order_id, "linkedIncidentId": incident_id, "lines": lines, "evidence": evidence or [], "approverRole": role, "routing": routing,
            "decisions": [], "version": 0, "createdAt": now, "updatedAt": now,
        }
        await self._db["approvals"].insert_one(approval)
        await self._audit.record(
            actor_id=requester["id"], actor_role=requester["role"], action="approval.create", domain=AuditDomain.PROCUREMENT, entity_type="APPROVAL", entity_id=approval["_id"],
            after={"type": kind, "amountPaise": amount, "approverRole": role},
        )
        await self._outbox.enqueue("approval.submitted", {"approvalId": approval["_id"], "roles": [role]})
        return approval

    async def create(self, user: AuthUser, kind: str, title: str, justification: str, amount: int, work_order_id: str | None) -> dict[str, Any]:
        approval = await self._insert(
            kind=kind, title=title.strip(), justification=justification.strip(), amount=amount, requester={"id": user.id, "name": user.name, "role": user.role_key},
            department_id=user.managed_department_ids[0] if user.managed_department_ids else user.department_id,
            lines=[], work_order_id=work_order_id,
        )
        return self.view(approval, user, await self._limit(user))

    async def raise_for_shortage(self, user: AuthUser, order: dict[str, Any], short: list[dict[str, Any]]) -> str:
        """A part is out of stock: a purchase request is raised in the technician's name, with the evidence attached."""
        lines = [{"itemId": part["itemId"], "sku": part["sku"], "name": part["name"], "qty": part["qty"], "unitPaise": part["unitPaise"]} for part in short]
        amount = sum(line["qty"] * line["unitPaise"] for line in lines)
        names = ", ".join(f"{line['qty']} x {line['name']}" for line in lines)
        approval = await self._insert(
            kind="PURCHASE", title=f"Buy {names} for {order['_id']}", justification=f"{order['_id']} ({order['title']}) is blocked: {names} out of stock.", amount=amount,
            requester={"id": user.id, "name": user.name, "role": user.role_key}, department_id=order.get("departmentId"), lines=lines, work_order_id=order["_id"],
            incident_id=order.get("incidentId"), evidence=[{"label": "Work order", "value": f"{order['_id']} blocked", "tone": "danger"}, {"label": "Free stock", "value": "0", "tone": "danger"}],
        )
        return approval["_id"]  # type: ignore[no-any-return]

    # ---- deciding -----------------------------------------------------------------------------------------------

    async def _set(self, approval: dict[str, Any], status: str, entry: dict[str, Any] | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        update: dict[str, Any] = {"$set": {"status": status, "updatedAt": utcnow(), **(extra or {})}, "$inc": {"version": 1}}
        if entry:
            update["$push"] = {"decisions": entry}
        # The status and version guard is why the same decision cannot be applied twice.
        done = await self._db["approvals"].update_one({"_id": approval["_id"], "version": approval["version"], "status": approval["status"]}, update)
        if done.modified_count != 1:
            raise conflict("ALREADY_DECIDED", f"{approval['_id']} was decided or changed by someone else. Reload it.")
        return await self._db["approvals"].find_one({"_id": approval["_id"]})  # type: ignore[no-any-return]

    async def decide(self, user: AuthUser, approval_id: str, decision: str, reason: str | None) -> dict[str, Any]:
        approval = await self.get(user, approval_id)
        if approval["status"] not in OPEN:
            raise rule("ALREADY_DECIDED", f"{approval_id} is already {approval['status'].lower().replace('_', ' ')}.")
        if not user.has(DECIDE[approval["type"]]):
            raise rule("NOT_YOUR_DECISION", f"{approval['type'].replace('_', ' ').lower()} requests are decided by {ROLE_WORD.get(approval['approverRole'], 'another role')}.")
        reason = (reason or "").strip() or None
        entry = {"by": user.name, "byId": user.id, "decision": {"APPROVE": "APPROVED", "REJECT": "REJECTED", "CLARIFY": "CLARIFICATION REQUESTED"}[decision], "reason": reason, "at": utcnow()}
        if decision == "CLARIFY":
            if approval["requesterId"] == user.id:
                raise rule("SELF_APPROVAL", "You raised this request, so someone else must decide it.")
            if not reason:
                raise rule("REASON_REQUIRED", "Say what you need to know.")
            moved = await self._set(approval, "NEEDS_CLARIFICATION", entry)
            await self._outbox.enqueue("approval.clarification", {"approvalId": approval_id, "recipientIds": [approval["requesterId"]], "question": reason})
        else:
            check = await self._collisions.enforce(
                user, ActionType.DECIDE_APPROVAL, {"approvalId": approval_id, "requesterId": approval["requesterId"], "amountPaise": approval["amountPaise"], "decision": decision}
            )
            entry["collisionCheckId"] = check["checkId"]
            moved = await self._set(approval, "APPROVED" if decision == "APPROVE" else "REJECTED", entry)
            if decision == "APPROVE" and moved["type"] == "PURCHASE":
                moved = await self._execute(user, moved)
            await self._outbox.enqueue(f"approval.{moved['status'].lower()}", {"approvalId": approval_id, "recipientIds": [approval["requesterId"]]})
        await self._audit.record_as(
            user, action=f"approval.{decision.lower()}", domain=AuditDomain.PROCUREMENT, entity_type="APPROVAL", entity_id=approval_id,
            before={"status": approval["status"]}, after={"status": moved["status"], "purchaseOrderId": moved.get("purchaseOrderId")}, reason=reason,
        )
        if moved["status"] == "STALE":
            raise conflict("STALE", moved.get("staleReason") or "This request no longer applies.")
        return self.view(moved, user, await self._limit(user))

    async def _still_needed(self, approval: dict[str, Any]) -> str | None:
        """Why an approved purchase should not go ahead after all, or None if it still should."""
        if approval.get("linkedWorkOrderId"):
            order = await self._db["work_orders"].find_one({"_id": approval["linkedWorkOrderId"]})
            if order is None or order["status"] in ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"):
                return f"{approval['linkedWorkOrderId']} no longer needs parts, so nothing was ordered."
            short = {part["itemId"] for part in order.get("partRequirements", []) if part["state"] == "SHORT"}
            if not short & {line["itemId"] for line in approval["lines"]}:
                return f"The parts for {approval['linkedWorkOrderId']} are no longer short, so nothing was ordered."
        return None

    async def _execute(self, user: AuthUser, approval: dict[str, Any]) -> dict[str, Any]:
        stale = await self._still_needed(approval)
        if stale:
            return await self._set(approval, "STALE", None, {"staleReason": stale})
        order = await self.procurement.create_order(user, approval) if self.procurement else None
        return await self._set(approval, "EXECUTED", None, {"purchaseOrderId": order["_id"] if order else None})

    async def answer(self, user: AuthUser, approval_id: str, text: str) -> dict[str, Any]:
        """The requester answers a clarification question, which sends the request back for a decision."""
        approval = await self.get(user, approval_id)
        if approval["requesterId"] != user.id:
            raise not_found("Approval")
        if approval["status"] != "NEEDS_CLARIFICATION":
            raise rule("NOTHING_ASKED", "Nobody has asked a question about this request.")
        moved = await self._set(approval, "SUBMITTED", {"by": user.name, "byId": user.id, "decision": "CLARIFIED", "reason": text.strip(), "at": utcnow()})
        await self._outbox.enqueue("approval.submitted", {"approvalId": approval_id, "roles": [approval["approverRole"]]})
        return self.view(moved, user, await self._limit(user))
