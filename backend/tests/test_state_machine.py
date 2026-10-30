from enum import Enum

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.core.errors import ApiException
from app.core.state import StateMachine, guarded_update, try_guarded_update


class Status(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    DONE = "DONE"


class Event(Enum):
    ASSIGN = 1
    FINISH = 2
    REOPEN = 3


MACHINE = StateMachine.build(
    [
        (Status.OPEN, Event.ASSIGN, Status.ASSIGNED),
        (Status.ASSIGNED, Event.FINISH, Status.DONE),
        (Status.DONE, Event.REOPEN, Status.OPEN),
    ]
)


def test_legal_moves_go_to_the_declared_state():
    assert MACHINE.next(Status.OPEN, Event.ASSIGN) is Status.ASSIGNED
    assert MACHINE.next(Status.ASSIGNED, Event.FINISH) is Status.DONE
    assert MACHINE.can(Status.DONE, Event.REOPEN)


def test_illegal_moves_are_a_422_naming_the_move():
    with pytest.raises(ApiException) as caught:
        MACHINE.next(Status.OPEN, Event.FINISH)
    assert caught.value.status == 422
    assert caught.value.code == "ILLEGAL_TRANSITION"
    assert "FINISH" in caught.value.message and "OPEN" in caught.value.message


def test_a_repeated_event_in_the_new_state_is_illegal_not_applied_twice():
    state = MACHINE.next(Status.OPEN, Event.ASSIGN)
    with pytest.raises(ApiException):
        MACHINE.next(state, Event.ASSIGN)


def test_events_from_lists_only_what_the_state_allows():
    assert MACHINE.events_from(Status.OPEN) == {Event.ASSIGN}
    assert MACHINE.events_from(Status.DONE) == {Event.REOPEN}


def test_a_duplicate_transition_is_a_programming_error():
    with pytest.raises(ValueError, match="Duplicate transition"):
        StateMachine.build([(Status.OPEN, Event.ASSIGN, Status.ASSIGNED), (Status.OPEN, Event.ASSIGN, Status.DONE)])


async def _collection():
    collection = AsyncMongoMockClient()["t"]["things"]
    await collection.insert_one({"_id": "T1", "status": "OPEN", "version": 0})
    return collection


async def test_guarded_update_applies_once_and_bumps_the_version():
    collection = await _collection()
    assert await try_guarded_update(collection, "T1", 0, Status.OPEN, {"$set": {"status": "ASSIGNED"}})
    stored = await collection.find_one({"_id": "T1"})
    assert stored["status"] == "ASSIGNED"
    assert stored["version"] == 1
    assert "updatedAt" in stored


async def test_the_same_event_delivered_twice_applies_once():
    collection = await _collection()
    first = await try_guarded_update(collection, "T1", 0, Status.OPEN, {"$set": {"status": "ASSIGNED"}})
    second = await try_guarded_update(collection, "T1", 0, Status.OPEN, {"$set": {"status": "ASSIGNED"}})
    assert (first, second) == (True, False)
    assert (await collection.find_one({"_id": "T1"}))["version"] == 1


async def test_a_stale_status_or_version_is_refused():
    collection = await _collection()
    assert not await try_guarded_update(collection, "T1", 5, Status.OPEN, {"$set": {"status": "DONE"}})
    assert not await try_guarded_update(collection, "T1", 0, Status.DONE, {"$set": {"status": "OPEN"}})
    assert (await collection.find_one({"_id": "T1"}))["status"] == "OPEN"


async def test_a_lost_race_becomes_a_409():
    collection = await _collection()
    await guarded_update(collection, "T1", 0, Status.OPEN, {"$set": {"status": "ASSIGNED"}})
    with pytest.raises(ApiException) as caught:
        await guarded_update(collection, "T1", 0, Status.OPEN, {"$set": {"status": "ASSIGNED"}})
    assert caught.value.status == 409
    assert caught.value.code == "VERSION_CONFLICT"


async def test_the_callers_update_document_is_not_mutated():
    collection = await _collection()
    update = {"$set": {"status": "ASSIGNED"}}
    await try_guarded_update(collection, "T1", 0, Status.OPEN, update)
    assert update == {"$set": {"status": "ASSIGNED"}}
