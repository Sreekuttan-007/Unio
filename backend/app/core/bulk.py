from typing import Any

from pymongo.errors import BulkWriteError

DUPLICATE_KEY = 11000


async def insert_missing(collection: Any, documents: list[dict[str, Any]], chunk: int = 500) -> int:
    """Inserts documents whose _id is not there yet, and never touches existing ones.

    A restart therefore cannot undo a change made at runtime. Works in a few round trips even for
    a thousand documents, which matters on a hosted database.
    """
    inserted = 0
    for start in range(0, len(documents), chunk):
        part = documents[start : start + chunk]
        ids = [document["_id"] for document in part]
        existing = {row["_id"] async for row in collection.find({"_id": {"$in": ids}}, {"_id": 1})}
        fresh = [document for document in part if document["_id"] not in existing]
        if not fresh:
            continue
        try:
            await collection.insert_many(fresh, ordered=False)
            inserted += len(fresh)
        except BulkWriteError as error:
            real = [item for item in error.details.get("writeErrors", []) if item.get("code") != DUPLICATE_KEY]
            if real:
                raise
            inserted += error.details.get("nInserted", 0)
    return inserted
