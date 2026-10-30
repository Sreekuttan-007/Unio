from datetime import datetime
from typing import Any

from fastapi import Depends

from app.core.access import GuardedRouter, public, require
from app.core.clock import utcnow
from app.core.errors import ApiException
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["system"])


class Ping(ApiModel):
    service: str
    database: str
    server_time: datetime


@router.get("/system/ping", response_model=Ping, dependencies=[public])
async def ping(services: Services = Depends(get_services)) -> Ping:
    """The frontend uses this to tell a sleeping backend from a broken one."""
    try:
        await services.db.command("ping")
        database = "UP"
    except Exception:  # noqa: BLE001 - any failure means the database is not reachable
        database = "DOWN"
    return Ping(service="unio-backend", database=database, server_time=utcnow())


def _not_built(phase: int) -> ApiException:
    return ApiException(501, "NOT_BUILT_YET", f"This arrives in Phase {phase}.")


# Permission-guarded placeholders for endpoints built in later phases. They let the permission
# matrix cover the real role model now: callers who may use one get 501, everyone else 403.
# Delete each one when its phase adds the real endpoint.
reserved = GuardedRouter(prefix="/api/v1", tags=["reserved"])


@reserved.post("/issues", dependencies=[Depends(require(P.ISSUE_CREATE))])
async def submit_issue() -> Any:
    raise _not_built(4)


@reserved.get("/inbox", dependencies=[Depends(require(P.INBOX_READ))])
async def inbox() -> Any:
    raise _not_built(4)


@reserved.get(
    "/work-orders",
    dependencies=[Depends(require(P.WORKORDER_READ_ASSIGNED, P.WORKORDER_READ_DEPARTMENT, P.WORKORDER_READ_CAMPUS))],
)
async def list_work_orders() -> Any:
    raise _not_built(7)


@reserved.post(
    "/work-orders/{work_order_id}/assign",
    dependencies=[Depends(require(P.WORKORDER_ASSIGN_DEPARTMENT, P.WORKORDER_ASSIGN_CAMPUS))],
)
async def assign_work_order(work_order_id: str) -> Any:
    raise _not_built(7)


@reserved.post("/work-orders/{work_order_id}/complete", dependencies=[Depends(require(P.WORKORDER_EXECUTE))])
async def complete_work_order(work_order_id: str) -> Any:
    raise _not_built(7)


@reserved.post("/simulations", dependencies=[Depends(require(P.SIMULATION_RUN))])
async def run_simulation() -> Any:
    raise _not_built(9)


@reserved.post(
    "/approvals/{approval_id}/decide",
    dependencies=[
        Depends(require(P.APPROVAL_DECIDE_PURCHASE, P.APPROVAL_DECIDE_REPAIR, P.APPROVAL_DECIDE_OVERRIDE))
    ],
)
async def decide_approval(approval_id: str) -> Any:
    raise _not_built(10)


@reserved.post("/invoices", dependencies=[Depends(require(P.INVOICE_UPLOAD))])
async def upload_invoice() -> Any:
    raise _not_built(10)


@reserved.post("/goods-receipts/{receipt_id}/validate", dependencies=[Depends(require(P.RECEIPT_VALIDATE))])
async def validate_receipt(receipt_id: str) -> Any:
    raise _not_built(10)
