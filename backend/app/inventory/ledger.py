"""The stock ledger: the only way on-hand stock changes.

Every movement is one entry with a unique postingKey, so a replayed receipt or completion is ignored.
The entry is written first, then applied to its balance with a guard that lists the keys already
applied, so applying twice is impossible. A crash between the two leaves an unapplied entry, and
reconcile() finishes it at startup.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.clock import utcnow


class StockLedger:
    def __init__(self, db: Any, campus_id: str) -> None:
        self._db = db
        self._campus_id = campus_id

    async def post(
        self, *, key: str, item_id: str, location_id: str, on_hand: int, reserved: int = 0, kind: str, source: tuple[str, str], actor_id: str
    ) -> bool:
        """Records and applies one movement. Returns False when this key was already posted."""
        entry = {
            "_id": key, "postingKey": key, "itemId": item_id, "locationId": location_id, "onHandDelta": on_hand, "reservedDelta": reserved, "kind": kind,
            "sourceType": source[0], "sourceId": source[1], "actorId": actor_id, "at": utcnow(), "applied": False, "campusId": self._campus_id,
        }
        try:
            await self._db["stock_ledger"].insert_one(entry)
        except DuplicateKeyError:
            return False
        await self._apply(entry)
        return True

    async def _apply(self, entry: dict[str, Any]) -> None:
        balance_id = f"BAL-{entry['itemId'].removeprefix('ITM-')}-{entry['locationId']}"
        await self._db["inventory_balances"].update_one(
            {"_id": balance_id},
            {"$setOnInsert": {"itemId": entry["itemId"], "locationId": entry["locationId"], "onHand": 0, "reserved": 0, "version": 0, "campusId": self._campus_id}},
            upsert=True,
        )
        # shortcut: appliedKeys grows with every movement; trim keys of entries marked applied if a balance ever gets large.
        await self._db["inventory_balances"].update_one(
            {"_id": balance_id, "appliedKeys": {"$ne": entry["postingKey"]}},
            {"$inc": {"onHand": entry["onHandDelta"], "reserved": entry["reservedDelta"], "version": 1}, "$push": {"appliedKeys": entry["postingKey"]}},
        )
        await self._db["stock_ledger"].update_one({"_id": entry["_id"]}, {"$set": {"applied": True}})

    async def reconcile(self) -> int:
        """Applies entries a crash left unapplied. Safe to run any number of times."""
        fixed = 0
        for entry in await self._db["stock_ledger"].find({"applied": False}).to_list(length=10_000):
            await self._apply(entry)
            fixed += 1
        return fixed
