"""Turning outbox events into in-app notifications and signed webhooks.

Both are outbox handlers, so business code never calls them and delivery is retried. Delivery is
at-least-once; each notification has a unique dedupeKey and each webhook delivery a unique
(webhook, event) key, so a repeat changes nothing.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import urllib.request
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import not_found, rule

INTERNAL_RECEIVER = "internal://receiver"
SIGNATURE_HEADER = "X-Unio-Signature"

# event type -> (title, body template). Anything else gets a plain line built from its type.
WORDS = {
    "workorder.assigned": ("New task assigned", "{workOrderId} is yours."),
    "workorder.reassigned": ("Task reassigned", "{workOrderId} has a new technician."),
    "workorder.reassignment_proposed": ("Work needs a new technician", "{workOrderId}: {reason}."),
    "workorder.blocked": ("Work is blocked", "{workOrderId} is waiting: {reason}."),
    "workorder.resumed": ("Work can continue", "{workOrderId} has what it needs."),
    "workorder.completed": ("Repair completed", "{workOrderId} is ready to be checked."),
    "workorder.sent_back": ("Repair sent back", "{workOrderId} needs more work."),
    "approval.submitted": ("Request waiting for you", "{approvalId} needs a decision."),
    "approval.clarification": ("A question about your request", "{approvalId}: {question}"),
    "approval.executed": ("Purchase approved", "{approvalId} was approved and ordered."),
    "approval.approved": ("Request approved", "{approvalId} was approved."),
    "approval.rejected": ("Request rejected", "{approvalId} was rejected."),
    "receipt.posted": ("Stock arrived", "{receiptId} was posted to stock."),
    "session.moved": ("Your class has moved", "{course} is now in {toRoom}."),
    "sla.escalated": ("Deadline at risk", "{label} reached escalation level {level}."),
    "incident.status": ("Your report was updated", "{incidentId} is now {status}."),
    "impact.changed": ("Your class is affected", "An incident ({incidentId}) now affects something on your timetable."),
    "inventory.low": ("Low stock", "{itemName} is down to {available}, at or below its reorder point of {threshold}."),
}


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def words(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    title, template = WORDS.get(event_type, (event_type.replace(".", " ").replace("_", " ").capitalize(), ""))
    try:
        body = template.format(**{key: str(value).lower() if key == "status" else value for key, value in payload.items()})
    except (KeyError, IndexError):
        body = ""
    return title, body


class NotificationService:
    """The in-app notification centre. Only the people named by an event, or holding its roles, are told."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def supports(self, event_type: str) -> bool:
        return True

    async def recipients(self, payload: dict[str, Any]) -> list[str]:
        people = set(payload.get("recipientIds") or []) | set(payload.get("reporterIds") or [])
        if payload.get("roles"):
            people.update([row["_id"] async for row in self._db["users"].find({"roleKey": {"$in": payload["roles"]}, "active": {"$ne": False}}, {"_id": 1})])
        return sorted(people)

    async def handle(self, event: dict[str, Any]) -> None:
        title, body = words(event["eventType"], event["payload"])
        for user_id in await self.recipients(event["payload"]):
            try:
                await self._db["notifications"].insert_one(
                    {"userId": user_id, "eventType": event["eventType"], "title": title, "body": body, "payload": event["payload"], "readAt": None, "createdAt": utcnow(), "dedupeKey": f"{event['_id']}:{user_id}"}
                )
            except DuplicateKeyError:
                continue  # a redelivered event: this person was already told

    async def list(self, user: AuthUser, limit: int = 50) -> dict[str, Any]:
        rows = await self._db["notifications"].find({"userId": user.id}).sort("createdAt", -1).to_list(length=limit)
        unread = await self._db["notifications"].count_documents({"userId": user.id, "readAt": None})
        return {
            "unread": unread,
            "items": [{"id": str(row["_id"]), "title": row["title"], "body": row["body"], "eventType": row["eventType"], "read": row["readAt"] is not None, "at": ensure_utc(row["createdAt"]).isoformat()} for row in rows],
        }

    async def mark_read(self, user: AuthUser, notification_id: str | None) -> int:
        query: dict[str, Any] = {"userId": user.id, "readAt": None}
        if notification_id:
            from bson import ObjectId
            from bson.errors import InvalidId

            try:
                query["_id"] = ObjectId(notification_id)
            except InvalidId:
                raise not_found("Notification") from None
        result = await self._db["notifications"].update_many(query, {"$set": {"readAt": utcnow()}})
        return int(result.modified_count)


class WebhookService:
    """Signed outbound webhooks with a delivery log, and a built-in receiver for demonstrating them."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_default(self, campus_id: str) -> None:
        if await self._db["webhooks"].count_documents({}) == 0:
            await self._db["webhooks"].insert_one(
                {"_id": "WH-1", "url": INTERNAL_RECEIVER, "events": ["workorder.*", "approval.*", "receipt.*", "sla.*"], "enabled": True, "secret": secrets.token_hex(24), "campusId": campus_id}
            )

    def supports(self, event_type: str) -> bool:
        return True

    @staticmethod
    def _wants(hook: dict[str, Any], event_type: str) -> bool:
        return any(pattern == "*" or pattern == event_type or (pattern.endswith(".*") and event_type.startswith(pattern[:-1])) for pattern in hook["events"])

    async def handle(self, event: dict[str, Any]) -> None:
        async for hook in self._db["webhooks"].find({"enabled": True}):
            if self._wants(hook, event["eventType"]):
                await self.deliver(hook, str(event["_id"]), event["eventType"], event["payload"])

    async def deliver(self, hook: dict[str, Any], event_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Sends once per (webhook, event). A failure raises, so the outbox retries it later."""
        key = f"{hook['_id']}:{event_id}"
        done = await self._db["webhook_deliveries"].find_one({"_id": key, "status": {"$lt": 300}})
        if done:
            return done  # type: ignore[no-any-return]
        body = json.dumps({"id": event_id, "type": event_type, "data": payload}, sort_keys=True, default=str).encode()
        signature = sign(hook["secret"], body)
        try:
            status = await (self._receive_internally(body, signature) if hook["url"] == INTERNAL_RECEIVER else asyncio.to_thread(self._post, hook["url"], body, signature))
            error = None
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised for a retry
            status, error = 0, str(exc)[:300]
        record = {"_id": key, "webhookId": hook["_id"], "eventId": event_id, "eventType": event_type, "status": status, "error": error, "at": utcnow()}
        await self._db["webhook_deliveries"].replace_one({"_id": key}, record, upsert=True)
        await self._db["webhooks"].update_one({"_id": hook["_id"]}, {"$set": {"lastStatus": status, "lastAt": record["at"]}})
        if not 200 <= status < 300:
            raise RuntimeError(f"Webhook {hook['_id']} answered {status}: {error or 'no detail'}")
        return record

    @staticmethod
    def _post(url: str, body: bytes, signature: str) -> int:
        request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", SIGNATURE_HEADER: signature})
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - administrators configure https URLs
            return int(response.status)

    async def _receive_internally(self, body: bytes, signature: str) -> int:
        """The demo receiver: checks the signature and ignores an event it has seen before (replay protection)."""
        hook = await self._db["webhooks"].find_one({"url": INTERNAL_RECEIVER})
        if hook is None or not hmac.compare_digest(sign(hook["secret"], body), signature):
            return 401
        event = json.loads(body)
        try:
            await self._db["webhook_received"].insert_one({"_id": event["id"], "type": event["type"], "receivedAt": utcnow()})
        except DuplicateKeyError:
            return 200  # already processed: acknowledged, not processed again
        return 200

    async def test(self, webhook_id: str) -> dict[str, Any]:
        hook = await self._db["webhooks"].find_one({"_id": webhook_id})
        if hook is None:
            raise not_found("Webhook")
        try:
            record = await self.deliver(hook, f"test-{secrets.token_hex(6)}", "webhook.test", {"message": "Test delivery from UNIO"})
        except RuntimeError as exc:
            raise rule("WEBHOOK_FAILED", str(exc)) from None
        return {"status": record["status"], "signed": True, "message": "Delivered with a signature. Sending the same event again is ignored by the receiver."}

    async def views(self) -> list[dict[str, Any]]:
        return [
            {"id": row["_id"], "url": row["url"], "events": row["events"], "enabled": row["enabled"], "lastStatus": row.get("lastStatus", 0), "lastAt": ensure_utc(row["lastAt"]).isoformat() if row.get("lastAt") else ""}
            async for row in self._db["webhooks"].find({}).sort("_id", 1)
        ]
