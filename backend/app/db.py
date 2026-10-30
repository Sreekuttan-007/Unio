from typing import Any


async def ensure_indexes(db: Any) -> None:
    """Idempotent. The unique indexes here are what make concurrent writes safe (docs/DATA_MODEL.md)."""
    await db["users"].create_index("email", unique=True)
    await db["audit_logs"].create_index([("entityType", 1), ("entityId", 1), ("at", -1)])
    await db["audit_logs"].create_index([("actorId", 1), ("at", -1)])
    await db["audit_logs"].create_index([("domain", 1), ("at", -1)])
    await db["idempotency_keys"].create_index("createdAt", expireAfterSeconds=24 * 3600)
    await db["revoked_tokens"].create_index("expiresAt", expireAfterSeconds=0)
    await db["outbox_events"].create_index([("dispatchedAt", 1), ("failedAt", 1), ("nextAttemptAt", 1)])
