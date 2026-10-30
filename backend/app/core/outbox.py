import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Protocol

from pymongo import ReturnDocument

from app.core.clock import utcnow

log = logging.getLogger("unio.outbox")

COLLECTION = "outbox_events"
CLAIM_TIMEOUT = timedelta(minutes=2)


class OutboxHandler(Protocol):
    """Consumes outbox events. Delivery is at-least-once, so handlers must tolerate repeats."""

    def supports(self, event_type: str) -> bool: ...

    async def handle(self, event: dict[str, Any]) -> None: ...


def exponential_backoff(attempts: int) -> float:
    return float(2**attempts)


class OutboxService:
    """Business code writes an event; this turns it into notifications and webhooks, with retries."""

    def __init__(
        self,
        db: Any,
        max_attempts: int,
        retry_delay: Callable[[int], float] = exponential_backoff,
    ) -> None:
        self._events = db[COLLECTION]
        self._handlers: list[OutboxHandler] = []
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay

    def register(self, handler: OutboxHandler) -> None:
        self._handlers.append(handler)

    async def enqueue(self, event_type: str, payload: dict[str, Any]) -> None:
        now = utcnow()
        await self._events.insert_one(
            {
                "eventType": event_type,
                "payload": payload,
                "createdAt": now,
                "nextAttemptAt": now,
                "attempts": 0,
                "dispatchedAt": None,
                "failedAt": None,
                "lastError": None,
            }
        )

    async def dispatch_due(self) -> int:
        """Delivers every event that is due. Returns how many were delivered."""
        delivered = 0
        while (event := await self._claim_next()) is not None:
            if await self._deliver(event):
                delivered += 1
        return delivered

    async def _claim_next(self) -> dict[str, Any] | None:
        """Atomic claim, so concurrent dispatchers cannot pick up the same event."""
        now = utcnow()
        return await self._events.find_one_and_update(
            {"dispatchedAt": None, "failedAt": None, "nextAttemptAt": {"$lte": now}},
            {"$inc": {"attempts": 1}, "$set": {"nextAttemptAt": now + CLAIM_TIMEOUT}},
            return_document=ReturnDocument.AFTER,
        )

    async def _deliver(self, event: dict[str, Any]) -> bool:
        try:
            for handler in self._handlers:
                if handler.supports(event["eventType"]):
                    await handler.handle(event)
        except Exception as exc:  # any handler failure is retried, then parked
            log.warning("Outbox delivery failed for %s on attempt %s", event["_id"], event["attempts"], exc_info=exc)
            update: dict[str, Any] = {"lastError": str(exc)}
            if event["attempts"] >= self._max_attempts:
                update["failedAt"] = utcnow()
            else:
                update["nextAttemptAt"] = utcnow() + timedelta(seconds=self._retry_delay(event["attempts"]))
            await self._events.update_one({"_id": event["_id"]}, {"$set": update})
            return False
        await self._events.update_one({"_id": event["_id"]}, {"$set": {"dispatchedAt": utcnow()}})
        return True


async def run_outbox_loop(outbox: OutboxService, interval_seconds: float, sweep: Callable[[], Any] | None = None) -> None:
    """Delivers events, and runs the SLA escalation sweep first so its events go out in the same tick."""
    while True:
        try:
            if sweep is not None:
                await sweep()
            await outbox.dispatch_due()
        except Exception as exc:  # the loop must survive a bad tick
            log.error("Outbox tick failed", exc_info=exc)
        await asyncio.sleep(interval_seconds)
