from enum import StrEnum
from typing import Any

from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.correlation import correlation_id
from app.core.scope import EntityType, scope_filter


class AuditDomain(StrEnum):
    """Which audience an audit entry belongs to. Drives audit data scope."""

    OPERATIONS = "OPERATIONS"
    PROCUREMENT = "PROCUREMENT"
    SYSTEM = "SYSTEM"


class AuditService:
    """Append-only. There is deliberately no update or delete path."""

    def __init__(self, db: Any) -> None:
        self._logs = db["audit_logs"]

    async def record(
        self,
        *,
        actor_id: str,
        actor_role: str,
        action: str,
        domain: AuditDomain,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        await self._logs.insert_one(
            {
                "actorId": actor_id,
                "actorRole": actor_role,
                "action": action,
                "domain": domain.value,
                "entityType": entity_type,
                "entityId": entity_id,
                "before": before or {},
                "after": after or {},
                "reason": reason,
                "correlationId": correlation_id.get(),
                "at": utcnow(),
            }
        )

    async def record_as(self, actor: AuthUser, **fields: Any) -> None:
        await self.record(actor_id=actor.id, actor_role=actor.role_key, **fields)

    async def list(self, user: AuthUser, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        query = scope_filter(user, EntityType.AUDIT)
        total = await self._logs.count_documents(query)
        # Timestamps have millisecond resolution, so entries written together tie. The ObjectId
        # increases with insertion, which makes the order deterministic.
        rows = await self._logs.find(query).sort([("at", -1), ("_id", -1)]).skip(skip).limit(limit).to_list(length=limit)
        return rows, total
