"""Stock levels, reservations for work orders, and putting arrived parts to work.

Reservation is a compare-and-set on the balance's version, so concurrent requests can never reserve
more than is free. Stock on hand only moves through the ledger.
"""

from __future__ import annotations

from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.collision.models import ActionType, Severity
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.inventory.ledger import StockLedger

RESERVE_ATTEMPTS = 25
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


class InventoryService:
    def __init__(self, db: Any, collisions: CollisionService, audit: AuditService, outbox: OutboxService, ledger: StockLedger) -> None:
        self._db = db
        self._collisions = collisions
        self._audit = audit
        self._outbox = outbox
        self.ledger = ledger
        self.approvals: Any = None  # set by build_services: raises a purchase request for a shortage
        self.workorders: Any = None  # set by build_services: resumes work once its parts are reserved

    # ---- reading ------------------------------------------------------------------------------------------

    async def items(self) -> list[dict[str, Any]]:
        items = await self._db["inventory_items"].find({}).sort("_id", 1).to_list(length=2000)
        balances = await self._db["inventory_balances"].find({}).to_list(length=10_000)
        names = {row["_id"]: row["name"] async for row in self._db["stock_locations"].find({})}
        blocked: dict[str, int] = {}
        async for order in self._db["work_orders"].find({"status": "BLOCKED"}):
            for part in order.get("partRequirements", []):
                if part["state"] == "SHORT":
                    blocked[part["itemId"]] = blocked.get(part["itemId"], 0) + 1
        rows = []
        for item in items:
            mine = [row for row in balances if row["itemId"] == item["_id"]]
            on_hand, reserved = sum(row["onHand"] for row in mine), sum(row["reserved"] for row in mine)
            stores = sorted({names.get(row["locationId"], row["locationId"]) for row in mine if row["onHand"] > 0}) or sorted({names.get(row["locationId"], row["locationId"]) for row in mine})
            status = "OUT" if on_hand - reserved <= 0 else "LOW" if on_hand <= item["reorderThreshold"] else "OK"
            rows.append(
                {
                    "id": item["_id"], "sku": item["sku"], "name": item["name"], "category": item["category"], "unit": item["unit"], "onHand": on_hand, "reserved": reserved,
                    "available": on_hand - reserved, "threshold": item["reorderThreshold"], "critical": item.get("critical", False), "location": ", ".join(stores[:2]) or "No store",
                    "status": status, "blockedWorkOrders": blocked.get(item["_id"], 0),
                }
            )
        rows.sort(key=lambda row: ({"OUT": 0, "LOW": 1, "OK": 2}[row["status"]], not row["critical"], row["name"]))
        return rows

    async def catalog(self) -> list[dict[str, Any]]:
        """What a technician can ask for, with what is free now. No costs and no store detail."""
        return [{"id": row["id"], "sku": row["sku"], "name": row["name"], "unit": row["unit"], "category": row["category"], "available": max(0, row["available"])} for row in await self.items()]

    async def mine(self, user: AuthUser) -> list[dict[str, Any]]:
        rows = []
        free = {row["id"]: row["available"] for row in await self.items()}
        async for order in self._db["work_orders"].find({"assignedUserId": user.id, "partRequirements.0": {"$exists": True}}).sort("_id", 1):
            for part in order["partRequirements"]:
                rows.append(
                    {"sku": part["sku"], "name": part["name"], "qty": part["qty"], "state": part["state"], "available": max(0, free.get(part["itemId"], 0)), "workOrderId": order["_id"], "workOrderTitle": order["title"]}
                )
        return rows

    # ---- reserving ------------------------------------------------------------------------------------------

    async def reserve(self, work_order_id: str, item_id: str, qty: int) -> str | None:
        """Holds qty from one store that has it free. Returns the reservation id, or None if no store has enough."""
        reservation_id: str | None = None
        for _ in range(RESERVE_ATTEMPTS):
            balances = await self._db["inventory_balances"].find({"itemId": item_id}).to_list(length=20)
            balances.sort(key=lambda row: (-(row["onHand"] - row["reserved"]), row["_id"]))
            pick = next((row for row in balances if row["onHand"] - row["reserved"] >= qty), None)
            if pick is None:
                break
            # The version guard is what makes this safe: a concurrent reservation bumps it and this one retries.
            done = await self._db["inventory_balances"].update_one({"_id": pick["_id"], "version": pick.get("version", 0)}, {"$inc": {"reserved": qty, "version": 1}})
            if done.modified_count == 1:
                reservation_id = await next_id(self._db, "RES", 100)
                await self._db["reservations"].insert_one(
                    {"_id": reservation_id, "workOrderId": work_order_id, "itemId": item_id, "balanceId": pick["_id"], "locationId": pick["locationId"], "qty": qty, "status": "ACTIVE", "createdAt": utcnow()}
                )
                break
        await self._check_reorder(item_id)
        return reservation_id

    async def _check_reorder(self, item_id: str) -> None:
        """Enqueues `inventory.low` once when free stock falls to or below the item's reorder point, and
        clears the flag once it recovers, so the next drop below the line notifies again."""
        item = await self._db["inventory_items"].find_one({"_id": item_id})
        if item is None:
            return
        balances = await self._db["inventory_balances"].find({"itemId": item_id}).to_list(length=20)
        available = sum(row["onHand"] - row["reserved"] for row in balances)
        if available <= item["reorderThreshold"]:
            # The filter on the flag itself is the CAS: only the request that actually flips it enqueues.
            claimed = await self._db["inventory_items"].update_one({"_id": item_id, "lowStockAlertSent": {"$ne": True}}, {"$set": {"lowStockAlertSent": True}})
            if claimed.modified_count == 1:
                await self._outbox.enqueue(
                    "inventory.low", {"itemId": item_id, "itemName": item["name"], "available": available, "threshold": item["reorderThreshold"], "roles": ["PROCUREMENT_APPROVER"]}
                )
        else:
            await self._db["inventory_items"].update_one({"_id": item_id, "lowStockAlertSent": True}, {"$set": {"lowStockAlertSent": False}})

    async def request_parts(self, user: AuthUser, order: dict[str, Any], parts: list[dict[str, Any]]) -> dict[str, Any]:
        """A technician says what is missing. Free stock is reserved now; anything short raises a purchase request."""
        lines = [{"itemId": part["item_id"], "qty": part["qty"]} for part in parts]
        action = self._collisions.build_action(user, ActionType.RESERVE_PARTS, {"workOrderId": order["_id"], "lines": lines}, None)
        verdict = await self._collisions.evaluate(action, with_alternatives=False)
        for finding in verdict.findings:
            if finding.severity is Severity.HARD and finding.code != "STOCK_SHORT":
                raise rule(finding.code, finding.message)
        items = {row["_id"]: row async for row in self._db["inventory_items"].find({"_id": {"$in": [line["itemId"] for line in lines]}})}
        added, short = [], []
        for line in lines:
            item = items[line["itemId"]]
            reservation = await self.reserve(order["_id"], item["_id"], line["qty"])
            entry = {"itemId": item["_id"], "sku": item["sku"], "name": item["name"], "qty": line["qty"], "state": "RESERVED" if reservation else "SHORT", "reservationId": reservation}
            added.append(entry)
            if reservation is None:
                short.append({**entry, "unitPaise": item.get("unitCostPaise", 0)})
        await self._db["work_orders"].update_one({"_id": order["_id"]}, {"$push": {"partRequirements": {"$each": added}}, "$inc": {"version": 1}})
        approval_id = None
        if short and self.approvals is not None:
            approval_id = await self.approvals.raise_for_shortage(user, order, short)
            await self._db["work_orders"].update_one({"_id": order["_id"]}, {"$push": {"approvalIds": approval_id}, "$inc": {"version": 1}})
        await self._audit.record_as(
            user, action="inventory.request_parts", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=order["_id"],
            after={"parts": [{"itemId": entry["itemId"], "qty": entry["qty"], "state": entry["state"]} for entry in added], "purchaseRequest": approval_id},
        )
        return {"parts": added, "approvalId": approval_id}

    async def issue_for_completion(self, user: AuthUser, order: dict[str, Any], parts_used: list[dict[str, Any]]) -> None:
        """Reserved parts leave the store when the work is done: one ledger entry per reservation."""
        async for reservation in self._db["reservations"].find({"workOrderId": order["_id"], "status": "ACTIVE"}):
            await self.ledger.post(
                key=f"ISSUE-{reservation['_id']}", item_id=reservation["itemId"], location_id=reservation["locationId"], on_hand=-reservation["qty"], reserved=-reservation["qty"],
                kind="ISSUE", source=("WORK_ORDER", order["_id"]), actor_id=user.id,
            )
            await self._db["reservations"].update_one({"_id": reservation["_id"], "status": "ACTIVE"}, {"$set": {"status": "ISSUED", "issuedAt": utcnow()}})
        parts = [{**part, "state": "ISSUED"} if part["state"] == "RESERVED" else part for part in order.get("partRequirements", [])]
        await self._db["work_orders"].update_one({"_id": order["_id"]}, {"$set": {"partRequirements": parts}, "$inc": {"version": 1}})

    async def release_for_work_order(self, work_order_id: str, actor_id: str, actor_role: str) -> int:
        released = 0
        freed_items: set[str] = set()
        async for reservation in self._db["reservations"].find({"workOrderId": work_order_id, "status": "ACTIVE"}):
            claimed = await self._db["reservations"].update_one({"_id": reservation["_id"], "status": "ACTIVE"}, {"$set": {"status": "RELEASED", "releasedAt": utcnow()}})
            if claimed.modified_count == 1:
                await self._db["inventory_balances"].update_one({"_id": reservation["balanceId"]}, {"$inc": {"reserved": -reservation["qty"], "version": 1}})
                freed_items.add(reservation["itemId"])
                released += 1
        for item_id in freed_items:
            await self._check_reorder(item_id)
        if released:
            await self._audit.record(actor_id=actor_id, actor_role=actor_role, action="inventory.release", domain=AuditDomain.OPERATIONS, entity_type="WORK_ORDER", entity_id=work_order_id, after={"released": released})
        return released

    # ---- arrivals -------------------------------------------------------------------------------------------

    async def allocate(self, item_ids: list[str], actor_id: str, actor_role: str) -> list[str]:
        """Arrived stock goes to blocked work, most urgent first. Work whose parts are all reserved resumes."""
        for item_id in set(item_ids):
            await self._check_reorder(item_id)  # catches a receipt that lifts stock back above the line
        resumed: list[str] = []
        orders = await self._db["work_orders"].find({"status": "BLOCKED", "partRequirements": {"$elemMatch": {"state": "SHORT", "itemId": {"$in": item_ids}}}}).to_list(length=200)
        orders.sort(key=lambda row: (PRIORITY_RANK.get(row["priority"], 9), row["createdAt"], row["_id"]))
        for order in orders:
            parts = order["partRequirements"]
            changed = False
            for part in parts:
                if part["state"] == "SHORT" and part["itemId"] in item_ids:
                    reservation = await self.reserve(order["_id"], part["itemId"], part["qty"])
                    if reservation:
                        part.update({"state": "RESERVED", "reservationId": reservation})
                        changed = True
            if not changed:
                continue
            await self._db["work_orders"].update_one({"_id": order["_id"]}, {"$set": {"partRequirements": parts}, "$inc": {"version": 1}})
            fresh = await self._db["work_orders"].find_one({"_id": order["_id"]})
            if fresh["blockReason"] == "WAITING_FOR_PARTS" and not any(part["state"] == "SHORT" for part in fresh["partRequirements"]) and self.workorders is not None:
                await self.workorders.resume_work(fresh, actor_id, actor_role)
                resumed.append(order["_id"])
        return resumed
