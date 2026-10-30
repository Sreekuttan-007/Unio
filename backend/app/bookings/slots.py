"""Room time slots, claimed one by one so that two people can never hold the same room.

Every slot is a document whose _id is the room and the slot's start. The database refuses a second
insert with the same _id, so the claim cannot be won twice however many requests arrive together.
Slots are claimed in time order, so two requests that overlap always fight over the same first
slot and exactly one of them wins, instead of each holding half of what the other needs.
"""

from datetime import datetime, timedelta
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.clock import ensure_utc

SLOT = timedelta(minutes=15)
SLOT_SECONDS = int(SLOT.total_seconds())


class SlotTaken(Exception):
    def __init__(self, room_id: str, slot_start: datetime, owner_id: str | None) -> None:
        super().__init__(f"{room_id} is already held from {slot_start.isoformat()}")
        self.room_id = room_id
        self.slot_start = slot_start
        self.owner_id = owner_id


def aligned(value: datetime) -> bool:
    value = ensure_utc(value)
    return int(value.timestamp()) % SLOT_SECONDS == 0 and value.second == 0 and value.microsecond == 0


def slot_starts(start: datetime, end: datetime) -> list[datetime]:
    start, end = ensure_utc(start), ensure_utc(end)
    count = int((end - start).total_seconds() // SLOT_SECONDS)
    return [start + SLOT * index for index in range(count)]


def slot_id(room_id: str, slot_start: datetime) -> str:
    return f"{room_id}|{int(ensure_utc(slot_start).timestamp())}"


class SlotClaims:
    """Claims 15-minute slots on one kind of resource. Rooms by default, and technicians with their own collection."""

    def __init__(self, db: Any, collection: str = "room_slots", key_field: str = "roomId") -> None:
        self._slots = db[collection]
        self._key = key_field

    async def claim(self, owner_kind: str, owner_id: str, room_id: str, start: datetime, end: datetime) -> int:
        """Claims every slot or none. Slots this owner already holds are kept as they are."""
        taken: list[str] = []
        try:
            for slot in slot_starts(start, end):
                document = {"_id": slot_id(room_id, slot), self._key: room_id, "slotStart": slot, "ownerKind": owner_kind, "ownerId": owner_id}
                try:
                    await self._slots.insert_one(document)
                    taken.append(document["_id"])
                except DuplicateKeyError:
                    holder = await self._slots.find_one({"_id": document["_id"]})
                    if holder and holder["ownerId"] == owner_id:
                        continue
                    raise SlotTaken(room_id, slot, holder["ownerId"] if holder else None) from None
        except BaseException:
            if taken:
                await self._slots.delete_many({"_id": {"$in": taken}, "ownerId": owner_id})
            raise
        return len(taken)

    async def release(self, owner_id: str, keep: set[str] | None = None) -> int:
        query: dict[str, Any] = {"ownerId": owner_id}
        if keep:
            query["_id"] = {"$nin": sorted(keep)}
        result = await self._slots.delete_many(query)
        return result.deleted_count

    async def holder(self, room_id: str, start: datetime, end: datetime) -> list[str]:
        ids = [slot_id(room_id, slot) for slot in slot_starts(start, end)]
        rows = await self._slots.find({"_id": {"$in": ids}}).to_list(length=len(ids))
        return sorted({row["ownerId"] for row in rows})

    async def move(self, owner_kind: str, owner_id: str, room_id: str, start: datetime, end: datetime) -> None:
        """Claims the new slots first, then lets go of the old ones, so the owner is never left without a room."""
        wanted = {slot_id(room_id, slot) for slot in slot_starts(start, end)}
        await self.claim(owner_kind, owner_id, room_id, start, end)
        await self.release(owner_id, keep=wanted)
