from typing import Any


async def next_number(db: Any, name: str, start: int = 1) -> int:
    """An atomic counter, so two requests can never be handed the same id."""
    from pymongo import ReturnDocument

    row = await db["counters"].find_one_and_update(
        {"_id": name}, {"$inc": {"value": 1}, "$setOnInsert": {"base": start}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return start - 1 + int(row["value"])


async def next_id(db: Any, prefix: str, start: int = 1) -> str:
    return f"{prefix}-{await next_number(db, prefix, start)}"
