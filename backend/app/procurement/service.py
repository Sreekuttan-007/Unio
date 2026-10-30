"""Purchase orders, invoices and goods receipts: the path from an approved purchase to stock on the shelf.

An invoice is read and checked against its order, and that is all: uploading never moves stock. Stock
arrives only when a goods receipt is validated by someone who neither raised the request nor received
the goods, and then exactly once, through the ledger.
"""

from __future__ import annotations

import io
import re
from typing import Any

from rapidfuzz import fuzz

from app.audit.service import AuditDomain, AuditService
from app.collision.models import ActionType
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import conflict, not_found, rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.files.service import FileStore, decode_base64
from app.inventory.service import InventoryService

RECEIVING_LOCATION = "LOC-MAIN"
FUZZY_MATCH = 80
LINE = re.compile(r"^(?P<desc>.*?[A-Za-z].*?)\s+(?P<qty>\d{1,5})\s*(?:x|X|@|nos?\.?|pcs?\.?)?\s*(?:Rs\.?|INR|₹)?\s*(?P<price>\d[\d,]*(?:\.\d{1,2})?)\s*(?:\S+)?\s*$")
DISCREPANCY_WORDS = {
    "QTY_MISMATCH": "The quantity on line {n} differs from the order: {inv} invoiced, {po} ordered.",
    "PRICE_MISMATCH": "The price on line {n} differs from the order: {inv} invoiced, {po} agreed.",
    "EXTRA_LINE": "Line {n} ({desc}) is not on the order.",
}


def paise(text: str) -> int:
    return round(float(text.replace(",", "")) * 100)


def read_text(mime: str, data: bytes) -> str:
    """Text from a plain-text or PDF invoice. Photos need the AI reader, which is optional (constraint C6)."""
    if mime == "text/plain":
        return data.decode("utf-8", errors="replace")
    if mime == "application/pdf":
        try:
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        except Exception:  # noqa: BLE001 - an unreadable PDF is a discrepancy for a person, not a crash
            return ""
    return ""


def parse_invoice(text: str) -> dict[str, Any]:
    """A deterministic reader for the common invoice layout: header fields, then one line per item."""
    header = lambda pattern: (m.group(1).strip() if (m := re.search(pattern, text, re.IGNORECASE | re.MULTILINE)) else None)  # noqa: E731
    supplier = header(r"^\s*supplier\s*[:\-]\s*(.+)$") or next((line.strip() for line in text.splitlines() if line.strip()), None)
    lines = []
    for raw in text.splitlines():
        if re.search(r"\b(total|subtotal|gst|tax|invoice|supplier|date|purchase order|po\s*(no|number)?\s*[:\-])", raw, re.IGNORECASE):
            continue
        match = LINE.match(raw.strip())
        if match:
            lines.append({"description": match.group("desc").strip(" -:|"), "qty": int(match.group("qty")), "unitPaise": paise(match.group("price"))})
    return {
        "supplier": supplier, "invoiceNumber": header(r"invoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9/\-]+)"),
        "invoiceDate": header(r"(\d{4}-\d{2}-\d{2})"), "purchaseOrderId": header(r"\b(PO-\d+)\b"), "lines": lines,
    }


def match_lines(lines: list[dict[str, Any]], order: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Each invoice line against the order, by SKU first and then by name. Returns the lines and the discrepancies."""
    out, problems = [], []
    po_lines = (order or {}).get("lines", [])
    for number, line in enumerate(lines, start=1):
        text = line["description"].upper()
        po, confidence = next(((row, 1.0) for row in po_lines if row["sku"].upper() in text), (None, 0.0))
        if po is None and po_lines:
            best = max(po_lines, key=lambda row: fuzz.token_set_ratio(row["name"].upper(), text))
            score = fuzz.token_set_ratio(best["name"].upper(), text)
            po, confidence = (best, score / 100) if score >= FUZZY_MATCH else (None, score / 100)
        state = "OK"
        if po is None:
            state = "EXTRA"
            problems.append({"code": "EXTRA_LINE", "line": number, "message": DISCREPANCY_WORDS["EXTRA_LINE"].format(n=number, desc=line["description"]), "resolved": False})
        elif line["qty"] != po["qty"]:
            state = "QTY"
            problems.append({"code": "QTY_MISMATCH", "line": number, "message": DISCREPANCY_WORDS["QTY_MISMATCH"].format(n=number, inv=line["qty"], po=po["qty"]), "resolved": False})
        elif line["unitPaise"] != po["unitPaise"]:
            state = "PRICE"
            problems.append({"code": "PRICE_MISMATCH", "line": number, "message": DISCREPANCY_WORDS["PRICE_MISMATCH"].format(n=number, inv=f"₹{line['unitPaise'] / 100:,.2f}", po=f"₹{po['unitPaise'] / 100:,.2f}"), "resolved": False})
        out.append(
            {"lineNo": number, "description": line["description"], "qty": line["qty"], "unitPaise": line["unitPaise"], "itemId": po["itemId"] if po else None,
             "poQty": po["qty"] if po else None, "poUnitPaise": po["unitPaise"] if po else None, "match": state, "confidence": round(confidence, 2)}
        )
    if order is None:
        problems.append({"code": "NO_PURCHASE_ORDER", "line": 0, "message": "No purchase order could be found for this invoice.", "resolved": False})
    elif not lines:
        problems.append({"code": "NOTHING_READ", "line": 0, "message": "No item lines could be read. Check the document and enter the lines by hand.", "resolved": False})
    return out, problems


class ProcurementService:
    def __init__(self, db: Any, collisions: CollisionService, inventory: InventoryService, files: FileStore, audit: AuditService, outbox: OutboxService, campus_id: str) -> None:
        self._db = db
        self._collisions = collisions
        self._inventory = inventory
        self._files = files
        self._audit = audit
        self._outbox = outbox
        self._campus_id = campus_id

    # ---- purchase orders -------------------------------------------------------------------------------------

    async def create_order(self, user: AuthUser, approval: dict[str, Any]) -> dict[str, Any]:
        items = {row["_id"]: row async for row in self._db["inventory_items"].find({"_id": {"$in": [line["itemId"] for line in approval["lines"]]}})}
        category = items[approval["lines"][0]["itemId"]]["category"] if approval["lines"] else None
        supplier = await self._db["suppliers"].find_one({"categories": category}) or await self._db["suppliers"].find_one({}) or {"_id": "SUP-NONE", "name": "Supplier to be chosen"}
        lines = [
            {"itemId": line["itemId"], "sku": line["sku"], "name": line["name"], "qty": line["qty"], "unitPaise": line.get("unitPaise") or items[line["itemId"]].get("unitCostPaise", 0), "received": 0}
            for line in approval["lines"]
        ]
        order = {
            "_id": await next_id(self._db, "PO", 884), "approvalId": approval["_id"], "requesterId": approval["requesterId"], "supplierId": supplier["_id"], "supplier": supplier["name"],
            "lines": lines, "totalPaise": sum(line["qty"] * line["unitPaise"] for line in lines), "status": "ORDERED", "orderedAt": utcnow(), "createdBy": user.id, "campusId": self._campus_id,
            "linkedWorkOrderId": approval.get("linkedWorkOrderId"),
        }
        await self._db["purchase_orders"].insert_one(order)
        await self._audit.record_as(user, action="purchase_order.create", domain=AuditDomain.PROCUREMENT, entity_type="PURCHASE_ORDER", entity_id=order["_id"], after={"approvalId": approval["_id"], "totalPaise": order["totalPaise"]})
        return order

    @staticmethod
    def order_view(order: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": order["_id"], "approvalId": order["approvalId"], "supplier": order["supplier"], "totalPaise": order["totalPaise"], "status": order["status"],
            "orderedAt": ensure_utc(order["orderedAt"]).isoformat(), "lines": [{key: line[key] for key in ("sku", "name", "qty", "unitPaise", "received")} for line in order["lines"]],
        }

    async def orders(self) -> list[dict[str, Any]]:
        return [self.order_view(row) for row in await self._db["purchase_orders"].find({}).sort("orderedAt", -1).to_list(length=300)]

    # ---- invoices ----------------------------------------------------------------------------------------------

    @staticmethod
    def invoice_view(invoice: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": invoice["_id"], "supplier": invoice.get("supplier") or "Unknown supplier", "invoiceNumber": invoice.get("invoiceNumber") or "Not read", "invoiceDate": invoice.get("invoiceDate") or "",
            "purchaseOrderId": invoice.get("purchaseOrderId") or "", "status": invoice["status"], "totalPaise": invoice["totalPaise"], "fileName": invoice["fileName"],
            "fileId": invoice["fileId"], "extractionSource": invoice["extractionSource"],
            "lines": [{key: value for key, value in line.items() if key != "itemId"} for line in invoice["lines"]],
            "discrepancies": [{"code": row["code"], "message": row["message"], "resolved": row["resolved"]} for row in invoice["discrepancies"]],
        }

    async def invoices(self) -> list[dict[str, Any]]:
        return [self.invoice_view(row) for row in await self._db["invoices"].find({}).sort("createdAt", -1).to_list(length=300)]

    async def upload(self, user: AuthUser, name: str, mime: str, content: str, purchase_order_id: str | None) -> dict[str, Any]:
        data = decode_base64(content)
        meta = await self._files.save(owner=user, purpose="INVOICE", name=name, mime=mime, data=data)
        extracted = parse_invoice(read_text(mime, data))
        po_id = purchase_order_id or extracted["purchaseOrderId"]
        order = await self._db["purchase_orders"].find_one({"_id": po_id}) if po_id else None
        lines, problems = match_lines(extracted["lines"], order)
        invoice = {
            "_id": await next_id(self._db, "INV", 440), "supplier": extracted["supplier"] or (order or {}).get("supplier"), "invoiceNumber": extracted["invoiceNumber"],
            "invoiceDate": extracted["invoiceDate"], "purchaseOrderId": order["_id"] if order else po_id, "status": "DISCREPANCY" if problems else "MATCHED",
            "totalPaise": sum(line["qty"] * line["unitPaise"] for line in lines), "fileName": meta["name"], "fileId": meta["_id"], "extractionSource": "MANUAL",
            "lines": lines, "discrepancies": problems, "uploadedBy": user.id, "createdAt": utcnow(), "version": 0, "campusId": self._campus_id,
        }
        await self._db["invoices"].insert_one(invoice)  # an invoice is a document to check, never a stock movement
        await self._audit.record_as(user, action="invoice.upload", domain=AuditDomain.PROCUREMENT, entity_type="INVOICE", entity_id=invoice["_id"], after={"purchaseOrderId": invoice["purchaseOrderId"], "status": invoice["status"], "fileId": meta["_id"]})
        return self.invoice_view(invoice)

    async def _invoice(self, invoice_id: str) -> dict[str, Any]:
        row = await self._db["invoices"].find_one({"_id": invoice_id})
        if row is None:
            raise not_found("Invoice")
        return row  # type: ignore[no-any-return]

    async def _save_invoice(self, invoice: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        done = await self._db["invoices"].update_one({"_id": invoice["_id"], "version": invoice["version"]}, {"$set": update, "$inc": {"version": 1}})
        if done.modified_count != 1:
            raise conflict("VERSION_CONFLICT", "This invoice changed. Reload it and try again.")
        return await self._invoice(invoice["_id"])

    async def resolve(self, user: AuthUser, invoice_id: str, code: str, note: str | None) -> dict[str, Any]:
        """A person accepts a discrepancy with a note. Missing orders and unread documents cannot be waved through."""
        invoice = await self._invoice(invoice_id)
        if invoice["status"] not in ("DISCREPANCY", "MATCHED"):
            raise rule("ILLEGAL_TRANSITION", f"{invoice_id} is already {invoice['status'].lower()}.")
        if code in ("NO_PURCHASE_ORDER", "NOTHING_READ"):
            raise rule("CANNOT_ACCEPT", "This cannot be accepted. Upload the invoice again with its purchase order number, or a clearer document.")
        problems = invoice["discrepancies"]
        target = next((row for row in problems if row["code"] == code and not row["resolved"]), None)
        if target is None:
            raise rule("NOTHING_TO_RESOLVE", "That discrepancy is not open.")
        for row in problems:
            if row["code"] == code:
                row.update({"resolved": True, "resolvedBy": user.id, "note": (note or "").strip() or None})
        lines = [{**line, "match": "OK"} if any(row["line"] == line["lineNo"] and row["resolved"] for row in problems) else line for line in invoice["lines"]]
        saved = await self._save_invoice(invoice, {"discrepancies": problems, "lines": lines, "status": "MATCHED" if all(row["resolved"] for row in problems) else "DISCREPANCY"})
        await self._audit.record_as(user, action="invoice.resolve", domain=AuditDomain.PROCUREMENT, entity_type="INVOICE", entity_id=invoice_id, after={"code": code}, reason=note)
        return self.invoice_view(saved)

    async def validate(self, user: AuthUser, invoice_id: str) -> dict[str, Any]:
        """Confirms the delivery matches. This creates the goods receipt, which a different person must validate."""
        invoice = await self._invoice(invoice_id)
        if invoice["status"] == "DISCREPANCY":
            raise rule("DISCREPANCIES_OPEN", "Resolve every discrepancy before validating this invoice.")
        if invoice["status"] != "MATCHED":
            raise rule("ILLEGAL_TRANSITION", f"{invoice_id} is already {invoice['status'].lower()}.")
        order = await self._db["purchase_orders"].find_one({"_id": invoice["purchaseOrderId"]})
        if order is None:
            raise rule("NO_PURCHASE_ORDER", "No purchase order could be found for this invoice.")
        received: dict[str, int] = {}
        for line in invoice["lines"]:
            if line.get("itemId"):
                received[line["itemId"]] = received.get(line["itemId"], 0) + line["qty"]
        lines = [
            {"itemId": po["itemId"], "sku": po["sku"], "name": po["name"], "ordered": po["qty"], "received": min(received.get(po["itemId"], 0), po["qty"] - po["received"])}
            for po in order["lines"] if received.get(po["itemId"])
        ]
        saved = await self._save_invoice(invoice, {"status": "VALIDATED", "validatedBy": user.id})
        receipt = {
            "_id": await next_id(self._db, "GR", 300), "purchaseOrderId": order["_id"], "invoiceId": invoice_id, "status": "PENDING", "lines": lines,
            "receivedBy": user.id, "requesterId": order.get("requesterId"), "receivedAt": utcnow(), "version": 0, "campusId": self._campus_id,
        }
        await self._db["goods_receipts"].insert_one(receipt)
        await self._audit.record_as(user, action="invoice.validate", domain=AuditDomain.PROCUREMENT, entity_type="INVOICE", entity_id=invoice_id, after={"goodsReceiptId": receipt["_id"]})
        return self.invoice_view(saved)

    # ---- goods receipts ---------------------------------------------------------------------------------------

    @staticmethod
    def receipt_view(receipt: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": receipt["_id"], "purchaseOrderId": receipt["purchaseOrderId"], "invoiceId": receipt.get("invoiceId"), "status": receipt["status"],
            "lines": [{"name": line["name"], "ordered": line["ordered"], "received": line["received"]} for line in receipt["lines"]], "receivedAt": ensure_utc(receipt["receivedAt"]).isoformat(),
        }

    async def receipts(self) -> list[dict[str, Any]]:
        return [self.receipt_view(row) for row in await self._db["goods_receipts"].find({}).sort("receivedAt", -1).to_list(length=300)]

    @staticmethod
    def _entries(receipt: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"sku": line["sku"], "qty": line["received"]} for line in receipt["lines"] if line["received"] > 0]

    async def validate_receipt(self, user: AuthUser, receipt_id: str) -> dict[str, Any]:
        receipt = await self._db["goods_receipts"].find_one({"_id": receipt_id})
        if receipt is None:
            raise not_found("Goods receipt")
        if receipt["status"] == "VALIDATED":
            return {"posted": True, "replayed": True, "ledgerEntries": self._entries(receipt), "message": "This receipt was already posted. Nothing changed."}
        await self._collisions.enforce(user, ActionType.VALIDATE_RECEIPT, {"receiptId": receipt_id, "requesterId": receipt.get("requesterId"), "receivedBy": receipt.get("receivedBy")})
        claimed = await self._db["goods_receipts"].update_one(
            {"_id": receipt_id, "status": "PENDING", "version": receipt["version"]}, {"$set": {"status": "VALIDATED", "validatedBy": user.id, "validatedAt": utcnow()}, "$inc": {"version": 1}}
        )
        if claimed.modified_count != 1:
            return {"posted": True, "replayed": True, "ledgerEntries": self._entries(receipt), "message": "This receipt was already posted. Nothing changed."}
        for number, line in enumerate(receipt["lines"], start=1):
            if line["received"] > 0:
                await self._inventory.ledger.post(
                    key=f"GR-{receipt_id}-{number}", item_id=line["itemId"], location_id=RECEIVING_LOCATION, on_hand=line["received"], kind="RECEIPT", source=("GOODS_RECEIPT", receipt_id), actor_id=user.id,
                )
        order = await self._db["purchase_orders"].find_one({"_id": receipt["purchaseOrderId"]})
        if order:
            got = {line["itemId"]: line["received"] for line in receipt["lines"]}
            lines = [{**line, "received": line["received"] + got.get(line["itemId"], 0)} for line in order["lines"]]
            status = "RECEIVED" if all(line["received"] >= line["qty"] for line in lines) else "PARTIALLY_RECEIVED"
            await self._db["purchase_orders"].update_one({"_id": order["_id"]}, {"$set": {"lines": lines, "status": status}})
        if receipt.get("invoiceId"):
            await self._db["invoices"].update_one({"_id": receipt["invoiceId"]}, {"$set": {"status": "POSTED"}, "$inc": {"version": 1}})
        resumed = await self._inventory.allocate([line["itemId"] for line in receipt["lines"] if line["received"] > 0], user.id, user.role_key)
        await self._audit.record_as(user, action="receipt.validate", domain=AuditDomain.PROCUREMENT, entity_type="GOODS_RECEIPT", entity_id=receipt_id, after={"entries": self._entries(receipt), "resumed": resumed})
        await self._outbox.enqueue("receipt.posted", {"receiptId": receipt_id, "resumedWorkOrders": resumed, "roles": ["FACILITIES_ADMIN"]})
        tail = f" {', '.join(resumed)} resumed." if resumed else ""
        return {"posted": True, "replayed": False, "ledgerEntries": self._entries(receipt), "message": f"Stock posted once, with your name, the time and {receipt_id} as the source.{tail}"}
