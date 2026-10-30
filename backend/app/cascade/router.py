from typing import Any

from fastapi import Depends
from pydantic import Field

from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["cascading"])


class RecomputeBody(ApiModel):
    root_asset_ids: list[str] | None = Field(default=None, max_length=10)


@router.get("/cascading/academic")
async def academic_impact(user: AuthUser = Depends(require(P.CASCADE_READ)), services: Services = Depends(get_services)) -> Any:
    """Classes hit by open incidents, limited to the ones this person teaches, manages or attends."""
    return await services.cascade.academic(user)


@router.get("/cascading/impact/{incident_id}")
async def incident_impact(incident_id: str, user: AuthUser = Depends(require(P.CASCADE_READ)), services: Services = Depends(get_services)) -> Any:
    return await services.cascade.impact(user, incident_id)


@router.post("/cascading/impact/{incident_id}/recompute")
async def recompute_impact(
    incident_id: str, body: RecomputeBody | None = None, user: AuthUser = Depends(require(P.INCIDENT_TRIAGE)), services: Services = Depends(get_services)
) -> Any:
    return await services.cascade.recompute(user, incident_id, body.root_asset_ids if body else None)
