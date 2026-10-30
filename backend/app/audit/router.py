from datetime import datetime
from typing import Any

from fastapi import Depends

from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.pagination import PageParams, PageResponse, page_params
from app.core.permission import Permission
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEntry(ApiModel):
    id: str
    actor_id: str
    actor_role: str
    action: str
    domain: str
    entity_type: str
    entity_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str | None
    correlation_id: str | None
    at: datetime


def _to_entry(row: dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        id=str(row["_id"]),
        actor_id=row["actorId"],
        actor_role=row["actorRole"],
        action=row["action"],
        domain=row["domain"],
        entity_type=row["entityType"],
        entity_id=row["entityId"],
        before=row.get("before", {}),
        after=row.get("after", {}),
        reason=row.get("reason"),
        correlation_id=row.get("correlationId"),
        at=row["at"],
    )


@router.get("", response_model=PageResponse[AuditEntry])
async def list_audit(
    user: AuthUser = Depends(
        require(Permission.AUDIT_READ_CAMPUS, Permission.AUDIT_READ_PROCUREMENT, Permission.AUDIT_READ_SYSTEM)
    ),
    paging: PageParams = Depends(page_params),
    services: Services = Depends(get_services),
) -> PageResponse[AuditEntry]:
    rows, total = await services.audit.list(user, paging.skip, paging.size)
    return PageResponse(items=[_to_entry(row) for row in rows], page=paging.page, size=paging.size, total=total)
