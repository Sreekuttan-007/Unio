from typing import Any

from fastapi import Depends
from pydantic import Field

from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["inventory", "approvals", "procurement"])

DECIDERS = (P.APPROVAL_DECIDE_PURCHASE, P.APPROVAL_DECIDE_REPAIR, P.APPROVAL_DECIDE_OVERRIDE)


class ApprovalBody(ApiModel):
    type: str = Field(pattern="^(PURCHASE|COSTLY_REPAIR|OVERRIDE)$")
    title: str = Field(min_length=3, max_length=200)
    justification: str = Field(min_length=3, max_length=2000)
    amount_paise: int = Field(ge=0, le=10**11)
    linked_work_order_id: str | None = Field(default=None, max_length=20)


class DecisionBody(ApiModel):
    decision: str = Field(pattern="^(APPROVE|REJECT|CLARIFY)$")
    reason: str | None = Field(default=None, max_length=1000)


class AnswerBody(ApiModel):
    text: str = Field(min_length=3, max_length=2000)


class InvoiceBody(ApiModel):
    file_name: str = Field(min_length=1, max_length=120)
    mime: str = Field(min_length=3, max_length=60)
    content_base64: str = Field(min_length=4, max_length=9_000_000)
    purchase_order_id: str | None = Field(default=None, max_length=20)


class ResolveBody(ApiModel):
    code: str = Field(min_length=3, max_length=40)
    note: str | None = Field(default=None, max_length=500)


# ---- inventory -----------------------------------------------------------------------------------------------


@router.get("/inventory/items")
async def stock_levels(user: AuthUser = Depends(require(P.INVENTORY_READ_DEPARTMENT, P.INVENTORY_READ_CAMPUS)), services: Services = Depends(get_services)) -> Any:
    return await services.inventory.items()


@router.get("/inventory/catalog")
async def part_catalog(
    user: AuthUser = Depends(require(P.INVENTORY_READ_RESERVED, P.INVENTORY_READ_DEPARTMENT, P.INVENTORY_READ_CAMPUS)), services: Services = Depends(get_services)
) -> Any:
    """What can be asked for, and how many are free. For the technician's part picker."""
    return await services.inventory.catalog()


@router.get("/inventory/mine")
async def my_parts(user: AuthUser = Depends(require(P.INVENTORY_READ_RESERVED)), services: Services = Depends(get_services)) -> Any:
    return await services.inventory.mine(user)


# ---- approvals -------------------------------------------------------------------------------------------------


@router.get("/approvals")
async def list_approvals(
    user: AuthUser = Depends(require(P.APPROVAL_READ_OWN, P.APPROVAL_READ_DEPARTMENT, P.APPROVAL_READ_ALL)), services: Services = Depends(get_services)
) -> Any:
    items = await services.approvals.list(user)
    return {"items": items, "page": 0, "size": len(items), "total": len(items)}


@router.post("/approvals", status_code=201)
async def create_approval(body: ApprovalBody, user: AuthUser = Depends(require(P.APPROVAL_REQUEST_CREATE)), services: Services = Depends(get_services)) -> Any:
    return await services.approvals.create(user, body.type, body.title, body.justification, body.amount_paise, body.linked_work_order_id)


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, body: DecisionBody, user: AuthUser = Depends(require(*DECIDERS)), services: Services = Depends(get_services)) -> Any:
    return await services.approvals.decide(user, approval_id, body.decision, body.reason)


@router.post("/approvals/{approval_id}/answer")
async def answer_clarification(approval_id: str, body: AnswerBody, user: AuthUser = Depends(require(P.APPROVAL_REQUEST_CREATE)), services: Services = Depends(get_services)) -> Any:
    return await services.approvals.answer(user, approval_id, body.text)


# ---- purchase orders, invoices, receipts -------------------------------------------------------------------------


@router.get("/purchase-orders")
async def purchase_orders(user: AuthUser = Depends(require(P.PURCHASE_ORDER_MANAGE, P.INVOICE_READ)), services: Services = Depends(get_services)) -> Any:
    return await services.procurement.orders()


@router.get("/invoices")
async def list_invoices(user: AuthUser = Depends(require(P.INVOICE_READ)), services: Services = Depends(get_services)) -> Any:
    return await services.procurement.invoices()


@router.post("/invoices", status_code=201)
async def upload_invoice(body: InvoiceBody, user: AuthUser = Depends(require(P.INVOICE_UPLOAD)), services: Services = Depends(get_services)) -> Any:
    """Reads the invoice and checks it against its order. It never changes stock."""
    return await services.procurement.upload(user, body.file_name, body.mime, body.content_base64, body.purchase_order_id)


@router.post("/invoices/{invoice_id}/resolve")
async def resolve_discrepancy(invoice_id: str, body: ResolveBody, user: AuthUser = Depends(require(P.INVOICE_VALIDATE)), services: Services = Depends(get_services)) -> Any:
    return await services.procurement.resolve(user, invoice_id, body.code, body.note)


@router.post("/invoices/{invoice_id}/validate")
async def validate_invoice(invoice_id: str, user: AuthUser = Depends(require(P.INVOICE_VALIDATE)), services: Services = Depends(get_services)) -> Any:
    return await services.procurement.validate(user, invoice_id)


@router.get("/goods-receipts")
async def list_receipts(user: AuthUser = Depends(require(P.RECEIPT_VALIDATE, P.INVOICE_READ)), services: Services = Depends(get_services)) -> Any:
    return await services.procurement.receipts()


@router.post("/goods-receipts/{receipt_id}/validate")
async def validate_receipt(receipt_id: str, user: AuthUser = Depends(require(P.RECEIPT_VALIDATE)), services: Services = Depends(get_services)) -> Any:
    """Posts the received stock to the ledger exactly once, then puts it to work on blocked repairs."""
    return await services.procurement.validate_receipt(user, receipt_id)
