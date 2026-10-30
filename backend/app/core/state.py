from collections.abc import Mapping
from enum import Enum
from typing import Any, Generic, TypeVar

from app.core.clock import utcnow
from app.core.errors import conflict, rule

S = TypeVar("S", bound=Enum)
E = TypeVar("E", bound=Enum)


class StateMachine(Generic[S, E]):
    """Immutable transition table for one aggregate. Each aggregate declares exactly one (C4)."""

    def __init__(self, transitions: Mapping[tuple[S, E], S]) -> None:
        self._transitions = dict(transitions)

    @classmethod
    def build(cls, rows: list[tuple[S, E, S]]) -> "StateMachine[S, E]":
        table: dict[tuple[S, E], S] = {}
        for source, event, target in rows:
            if (source, event) in table:
                raise ValueError(f"Duplicate transition: {source} + {event}")
            table[(source, event)] = target
        return cls(table)

    def target(self, source: S, event: E) -> S | None:
        return self._transitions.get((source, event))

    def can(self, source: S, event: E) -> bool:
        return (source, event) in self._transitions

    def events_from(self, source: S) -> set[E]:
        return {event for (state, event) in self._transitions if state == source}

    def next(self, source: S, event: E) -> S:
        """The next state, or a 422 naming the rejected move."""
        target = self.target(source, event)
        if target is None:
            raise rule("ILLEGAL_TRANSITION", f"Cannot apply {event.name} while the status is {source.name}.")
        return target


async def try_guarded_update(
    collection: Any, doc_id: Any, expected_version: int, expected_status: Enum | str, update: dict[str, Any]
) -> bool:
    """Compare-and-set on version and status.

    Relies on single-document atomicity, so a repeated or concurrent event applies once,
    with or without multi-document transactions.
    """
    status = expected_status.value if isinstance(expected_status, Enum) else expected_status
    body = {key: dict(value) if isinstance(value, dict) else value for key, value in update.items()}
    body.setdefault("$set", {})["updatedAt"] = utcnow()
    body.setdefault("$inc", {})["version"] = 1
    result = await collection.update_one({"_id": doc_id, "version": expected_version, "status": status}, body)
    return result.modified_count == 1


async def guarded_update(
    collection: Any, doc_id: Any, expected_version: int, expected_status: Enum | str, update: dict[str, Any]
) -> None:
    """As try_guarded_update, but a lost race becomes a 409."""
    if not await try_guarded_update(collection, doc_id, expected_version, expected_status, update):
        raise conflict("VERSION_CONFLICT", "This record changed. Reload it and try again.")
