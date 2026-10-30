from datetime import datetime
from typing import Any

from fastapi import Depends, Query
from pydantic import Field

from app.collision.acknowledge import Acknowledging
from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.pagination import PageParams, page_params
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["work-orders"])

READERS = (P.WORKORDER_READ_ASSIGNED, P.WORKORDER_READ_DEPARTMENT, P.WORKORDER_READ_CAMPUS)
ASSIGNERS = (P.WORKORDER_ASSIGN_DEPARTMENT, P.WORKORDER_ASSIGN_CAMPUS)


class AssignBody(Acknowledging):
    technician_id: str = Field(min_length=2, max_length=20)
    start_at: datetime | None = None


class EvidenceFile(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    mime: str = Field(min_length=3, max_length=60)
    content_base64: str = Field(min_length=4, max_length=9_000_000)


class CompleteBody(ApiModel):
    notes: str = Field(default="", max_length=2000)
    evidence: list[EvidenceFile] = Field(default_factory=list, max_length=4)


class PartAsk(ApiModel):
    item_id: str = Field(min_length=2, max_length=60)
    qty: int = Field(ge=1, le=1000)


class BlockBody(ApiModel):
    reason: str = Field(min_length=3, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    parts: list[PartAsk] = Field(default_factory=list, max_length=10)


class ReasonBody(ApiModel):
    reason: str | None = Field(default=None, max_length=500)


class VerifyBody(ApiModel):
    notes: str | None = Field(default=None, max_length=1000)


class AvailabilityBody(ApiModel):
    availability: str = Field(pattern="^(AVAILABLE|SICK|ON_LEAVE)$")
    reason: str | None = Field(default=None, max_length=300)


class ManagedAvailabilityBody(ApiModel):
    availability: str = Field(pattern="^(AVAILABLE|SICK|ON_LEAVE|OFF_SHIFT)$")
    reason: str | None = Field(default=None, max_length=300)


@router.get("/work-orders")
async def list_work_orders(
    status: str | None = Query(None, max_length=30),
    paging: PageParams = Depends(page_params),
    user: AuthUser = Depends(require(*READERS)),
    services: Services = Depends(get_services),
) -> Any:
    items = await services.workorders.list(user, status)
    return {"items": items[paging.skip : paging.skip + paging.size], "page": paging.page, "size": paging.size, "total": len(items)}


@router.post("/work-orders/review-late")
async def review_late_work(user: AuthUser = Depends(require(*ASSIGNERS)), services: Services = Depends(get_services)) -> Any:
    """Flags work that was not picked up or is running late, each with a proposed replacement."""
    flagged = await services.workorders.review_late()
    return {"flagged": flagged, "message": f"{len(flagged)} work {'order was' if len(flagged) == 1 else 'orders were'} flagged." if flagged else "Nothing is late."}


@router.get("/work-orders/{work_order_id}")
async def get_work_order(work_order_id: str, user: AuthUser = Depends(require(*READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.get(user, work_order_id), user)


@router.get("/work-orders/{work_order_id}/history")
async def work_order_history(work_order_id: str, user: AuthUser = Depends(require(*READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.history(user, work_order_id)


@router.get("/work-orders/{work_order_id}/candidates")
async def work_order_candidates(work_order_id: str, user: AuthUser = Depends(require(*ASSIGNERS)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.candidates(user, work_order_id)


@router.post("/work-orders/{work_order_id}/assign")
async def assign_work_order(work_order_id: str, body: AssignBody, user: AuthUser = Depends(require(*ASSIGNERS)), services: Services = Depends(get_services)) -> Any:
    order = await services.workorders.assign(user, work_order_id, body.technician_id, acknowledgement=body.acknowledgement(), expected_state_token=body.expected_state_token, start_at=body.start_at)
    return await services.workorders.view(order, user)


@router.post("/work-orders/{work_order_id}/cancel")
async def cancel_work_order(work_order_id: str, body: ReasonBody | None = None, user: AuthUser = Depends(require(*ASSIGNERS)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.cancel(user, work_order_id, body.reason if body else None), user)


@router.post("/work-orders/{work_order_id}/accept")
async def accept_work_order(work_order_id: str, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.accept(user, work_order_id), user)


@router.post("/work-orders/{work_order_id}/decline")
async def decline_work_order(work_order_id: str, body: ReasonBody | None = None, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.decline(user, work_order_id, body.reason if body else None), user)


@router.post("/work-orders/{work_order_id}/start")
async def start_work_order(work_order_id: str, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.start(user, work_order_id), user)


@router.post("/work-orders/{work_order_id}/block")
async def block_work_order(work_order_id: str, body: BlockBody, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    order = await services.workorders.block(user, work_order_id, body.reason, body.notes, [part.model_dump() for part in body.parts])
    return await services.workorders.view(order, user)


@router.post("/work-orders/{work_order_id}/resume")
async def resume_work_order(work_order_id: str, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.resume(user, work_order_id), user)


@router.post("/work-orders/{work_order_id}/complete")
async def complete_work_order(work_order_id: str, body: CompleteBody, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    order = await services.workorders.complete(user, work_order_id, body.notes, [item.model_dump() for item in body.evidence])
    return await services.workorders.view(order, user)


@router.post("/work-orders/{work_order_id}/request-reassign")
async def request_reassign(work_order_id: str, body: ReasonBody | None = None, user: AuthUser = Depends(require(P.WORKORDER_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.request_reassign(user, work_order_id, body.reason if body else None), user)


@router.post("/work-orders/{work_order_id}/verify")
async def verify_work_order(work_order_id: str, body: VerifyBody | None = None, user: AuthUser = Depends(require(P.WORKORDER_VERIFY)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.verify(user, work_order_id, True, body.notes if body else None), user)


@router.post("/work-orders/{work_order_id}/reject")
async def reject_work_order(work_order_id: str, body: VerifyBody | None = None, user: AuthUser = Depends(require(P.WORKORDER_VERIFY)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.view(await services.workorders.verify(user, work_order_id, False, body.notes if body else None), user)


@router.get("/technicians/me")
async def my_technician_profile(user: AuthUser = Depends(require(P.TECHNICIAN_AVAILABILITY_SELF)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.me(user)


@router.patch("/technicians/me/availability")
async def set_my_availability(body: AvailabilityBody, user: AuthUser = Depends(require(P.TECHNICIAN_AVAILABILITY_SELF)), services: Services = Depends(get_services)) -> Any:
    tech = await services.workorders.technician_for(user)
    return await services.workorders.set_availability(user, tech["_id"], body.availability, body.reason)


@router.patch("/technicians/{technician_id}/availability")
async def set_availability(
    technician_id: str, body: ManagedAvailabilityBody, user: AuthUser = Depends(require(P.TECHNICIAN_AVAILABILITY_MANAGE)), services: Services = Depends(get_services)
) -> Any:
    return await services.workorders.set_availability(user, technician_id, body.availability, body.reason)


@router.get("/maintenance-history")
async def maintenance_history(user: AuthUser = Depends(require(P.WORKORDER_READ_ASSIGNED, P.WORKORDER_READ_CAMPUS)), services: Services = Depends(get_services)) -> Any:
    return await services.workorders.maintenance_history(user)
