import asyncio
from typing import Any

from mongomock_motor import AsyncMongoMockClient

from app.core.outbox import OutboxService


class Recorder:
    def __init__(self, fail_times: int = 0, event_type: str = "demo.event") -> None:
        self.event_type = event_type
        self.calls: list[Any] = []
        self.fail_times = fail_times

    def supports(self, event_type: str) -> bool:
        return event_type == self.event_type

    async def handle(self, event: dict[str, Any]) -> None:
        self.calls.append(event["_id"])
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("downstream is down")


def make_outbox(handler: Recorder, max_attempts: int = 3) -> tuple[OutboxService, Any]:
    db = AsyncMongoMockClient()["t"]
    outbox = OutboxService(db, max_attempts=max_attempts, retry_delay=lambda attempts: 0)
    outbox.register(handler)
    return outbox, db["outbox_events"]


async def test_an_event_is_delivered_once_and_marked_dispatched():
    handler = Recorder()
    outbox, events = make_outbox(handler)
    await outbox.enqueue("demo.event", {"n": 1})
    assert await outbox.dispatch_due() == 1
    assert await outbox.dispatch_due() == 0
    assert len(handler.calls) == 1
    stored = await events.find_one({})
    assert stored["dispatchedAt"] is not None and stored["attempts"] == 1


async def test_a_failing_handler_is_retried_then_succeeds():
    handler = Recorder(fail_times=2)
    outbox, events = make_outbox(handler, max_attempts=5)
    await outbox.enqueue("demo.event", {})
    await outbox.dispatch_due()
    stored = await events.find_one({})
    assert len(handler.calls) == 3
    assert stored["dispatchedAt"] is not None
    assert stored["failedAt"] is None


async def test_an_event_that_keeps_failing_is_parked_not_retried_forever():
    handler = Recorder(fail_times=99)
    outbox, events = make_outbox(handler, max_attempts=3)
    await outbox.enqueue("demo.event", {})
    assert await outbox.dispatch_due() == 0
    stored = await events.find_one({})
    assert stored["failedAt"] is not None and stored["dispatchedAt"] is None
    assert stored["lastError"] == "downstream is down"
    assert len(handler.calls) == 3
    await outbox.dispatch_due()
    assert len(handler.calls) == 3


async def test_two_dispatchers_never_deliver_the_same_event_twice():
    handler = Recorder()
    outbox, _ = make_outbox(handler)
    for number in range(5):
        await outbox.enqueue("demo.event", {"n": number})
    await asyncio.gather(outbox.dispatch_due(), outbox.dispatch_due(), outbox.dispatch_due())
    assert len(handler.calls) == 5
    assert len(set(handler.calls)) == 5


async def test_events_nobody_handles_are_still_closed_out():
    handler = Recorder(event_type="something.else")
    outbox, events = make_outbox(handler)
    await outbox.enqueue("demo.event", {})
    assert await outbox.dispatch_due() == 1
    assert handler.calls == []
    assert (await events.find_one({}))["dispatchedAt"] is not None
