from typing import Any

from fastapi import Depends
from pydantic import Field

from app.collision.models import ActionType
from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.errors import forbidden
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["collisions"])

# Holding collision.check is not enough to ask about everything: each kind of action also needs the
# permission to do that thing, so a preview cannot be used to look at data the person may not see.
ACTION_PERMISSIONS: dict[ActionType, tuple[P, ...]] = {
    ActionType.BOOK_ROOM: (P.COLLISION_CHECK,),
    ActionType.MOVE_SESSION: (P.BOOKING_COORDINATE,),
    ActionType.ASSIGN_TECHNICIAN: (P.WORKORDER_ASSIGN_DEPARTMENT, P.WORKORDER_ASSIGN_CAMPUS),
    ActionType.RESERVE_PARTS: (P.INVENTORY_RESERVE, P.INVENTORY_READ_CAMPUS, P.INVENTORY_READ_DEPARTMENT),
    ActionType.DECIDE_APPROVAL: (P.APPROVAL_DECIDE_PURCHASE, P.APPROVAL_DECIDE_REPAIR, P.APPROVAL_DECIDE_OVERRIDE),
    ActionType.VALIDATE_RECEIPT: (P.RECEIPT_VALIDATE,),
    ActionType.RESOLVE_INCIDENT: (P.INCIDENT_TRANSITION,),
}


class CheckRequest(ApiModel):
    action_type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_state_token: str | None = Field(default=None, max_length=64)


class RuleUpdate(ApiModel):
    enabled: bool | None = None
    params: dict[str, int | None] | None = None


@router.post("/collisions/check")
async def check(body: CheckRequest, user: AuthUser = Depends(require(P.COLLISION_CHECK)), services: Services = Depends(get_services)) -> Any:
    if not user.has_any(ACTION_PERMISSIONS[body.action_type]):
        raise forbidden()
    return await services.collisions.check(user, body.action_type, body.payload, body.expected_state_token)


@router.get("/collisions")
async def records(user: AuthUser = Depends(require(P.COLLISION_REVIEW)), services: Services = Depends(get_services)) -> Any:
    return await services.collisions.records()


@router.get("/admin/rules")
async def list_rules(user: AuthUser = Depends(require(P.ADMIN_RULES)), services: Services = Depends(get_services)) -> Any:
    return await services.collisions.rules()


@router.patch("/admin/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate, user: AuthUser = Depends(require(P.ADMIN_RULES)), services: Services = Depends(get_services)) -> Any:
    return await services.collisions.update_rule(user, rule_id, body.enabled, body.params)
