"""Phase 10: stock, approvals and the invoice-to-inventory path for a missing part."""

import asyncio
import base64
import hashlib
import json
from datetime import timedelta

import pytest_asyncio

from app.core.clock import utcnow
from tests.conftest import DEMO_PASSWORD, open_env
from tests.test_incidents import report

MCB = "ITM-MCB-32A-3P"  # seeded with zero stock everywhere
FUSE = "ITM-MCB-16A-1P"


@pytest_asyncio.fixture
async def world():
    async with open_env(seed_campus=True) as opened:
        now = utcnow()
        await opened.db["shifts"].insert_many(
            [{"_id": f"SH-INV-{t}", "technicianId": t, "startAt": now - timedelta(hours=2), "endAt": now + timedelta(hours=14), "kind": "REGULAR", "campusId": "CAMPUS-1"} for t in ("T-01", "T-02")]
        )
        yield opened


async def login(env, email):
    response = await env.client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


async def stock_hash(db):
    dump = [await db[name].find({}).sort("_id", 1).to_list(length=10_000) for name in ("inventory_balances", "stock_ledger", "reservations")]
    return hashlib.sha256(json.dumps(dump, sort_keys=True, default=str).encode()).hexdigest()


async def blocked_on_parts(env, item=MCB, qty=2):
    """A P1 electrical job, started by the demo technician, then blocked waiting for a part."""
    incident = (await report(env, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()["incidentId"]
    await env.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident}/actions/incident.createWorkOrder")
    order_id = (await env.db["work_orders"].find_one({"incidentId": incident}))["_id"]
    assert (await env.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/assign", json={"technicianId": "T-01"})).status_code == 200
    for step in ("accept", "start"):
        assert (await env.call("TECHNICIAN", "POST", f"/api/v1/work-orders/{order_id}/{step}")).status_code == 200
    blocked = await env.call("TECHNICIAN", "POST", f"/api/v1/work-orders/{order_id}/block", json={"reason": "WAITING_FOR_PARTS", "notes": "Breaker burnt", "parts": [{"itemId": item, "qty": qty}]})
    assert blocked.status_code == 200, blocked.text
    return order_id, blocked.json()


def invoice_text(po_id, qty=2, price="1450.00"):
    text = f"Supplier: Brightline Electricals\nInvoice No: BE/2026/1201\nDate: 2026-10-30\nPurchase Order: {po_id}\nMCB-32A-3P MCB 32A three pole {qty} x {price}\nTotal {qty * float(price):.2f}\n"
    return base64.b64encode(text.encode()).decode()


async def upload(env, po_id, **kwargs):
    return await env.call("PROCUREMENT_APPROVER", "POST", "/api/v1/invoices", json={"fileName": "be-1201.txt", "mime": "text/plain", "contentBase64": invoice_text(po_id, **kwargs)})


# ---- the gate: a zero-stock part, all the way to resumed work -------------------------------------------------


async def test_a_missing_part_travels_from_technician_to_resumed_work_with_one_ledger_entry(world):
    order_id, body = await blocked_on_parts(world)
    assert body["status"] == "BLOCKED" and body["parts"][0]["state"] == "SHORT" and body["approvalId"]
    approval_id = body["approvalId"]
    approval = await world.db["approvals"].find_one({"_id": approval_id})
    assert approval["type"] == "PURCHASE" and approval["requesterId"] == "U-TECH" and approval["amountPaise"] == 2 * 145_000 and approval["approverRole"] == "PROCUREMENT_APPROVER"

    decided = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/approvals/{approval_id}/decide", json={"decision": "APPROVE"})
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "EXECUTED" and decided.json()["purchaseOrderId"]
    po_id = decided.json()["purchaseOrderId"]
    po = (await world.call("PROCUREMENT_APPROVER", "GET", "/api/v1/purchase-orders")).json()[0]
    assert po["id"] == po_id and po["supplier"] == "Brightline Electricals" and po["status"] == "ORDERED"

    before = await stock_hash(world.db)
    invoice = (await upload(world, po_id)).json()
    assert invoice["status"] == "MATCHED" and invoice["lines"][0]["match"] == "OK" and invoice["invoiceNumber"] == "BE/2026/1201"
    assert await stock_hash(world.db) == before  # uploading an invoice never moves stock

    assert (await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/invoices/{invoice['id']}/validate")).json()["status"] == "VALIDATED"
    receipt = (await world.call("PROCUREMENT_APPROVER", "GET", "/api/v1/goods-receipts")).json()[0]
    assert receipt["status"] == "PENDING" and receipt["lines"] == [{"name": "MCB 32A three pole", "ordered": 2, "received": 2}]
    assert await stock_hash(world.db) == before  # still nothing until the receipt is validated

    own = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/goods-receipts/{receipt['id']}/validate")
    assert own.status_code == 422 and own.json()["details"]["findings"][0]["code"] == "SEPARATION_OF_DUTIES"  # they received it

    other = await login(world, "procure2@unio.demo")
    posted = (await world.client.post(f"/api/v1/goods-receipts/{receipt['id']}/validate", headers=other)).json()
    assert posted["posted"] and not posted["replayed"] and order_id in posted["message"]
    replay = (await world.client.post(f"/api/v1/goods-receipts/{receipt['id']}/validate", headers=other)).json()
    assert replay["replayed"] is True
    assert await world.db["stock_ledger"].count_documents({"kind": "RECEIPT"}) == 1

    order = await world.db["work_orders"].find_one({"_id": order_id})
    assert order["status"] == "IN_PROGRESS" and order["partRequirements"][0]["state"] == "RESERVED"
    balance = await world.db["inventory_balances"].find_one({"_id": "BAL-MCB-32A-3P-LOC-MAIN"})
    assert balance["onHand"] == 2 and balance["reserved"] == 2
    pauses = (await world.db["sla_instances"].find_one({"subjectId": order["incidentId"]}))["pauses"]
    assert [p["reason"] for p in pauses] == ["Waiting for parts"] and pauses[0]["to"] is not None  # the clock paused, then resumed
    assert (await world.call("PROCUREMENT_APPROVER", "GET", "/api/v1/invoices")).json()[0]["status"] == "POSTED"

    done = await world.call("TECHNICIAN", "POST", f"/api/v1/work-orders/{order_id}/complete", json={"notes": "Replaced the breaker"})
    assert done.status_code == 200
    balance = await world.db["inventory_balances"].find_one({"_id": "BAL-MCB-32A-3P-LOC-MAIN"})
    assert balance["onHand"] == 0 and balance["reserved"] == 0  # issued through the ledger, never below zero
    assert await world.db["stock_ledger"].count_documents({"kind": "ISSUE"}) == 1


# ---- stock ----------------------------------------------------------------------------------------------------


async def test_twenty_concurrent_reservations_never_oversell(world):
    await world.db["inventory_balances"].update_many({"itemId": FUSE}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": FUSE, "locationId": "LOC-MAIN"}, {"$set": {"onHand": 5}})
    results = await asyncio.gather(*[world.services.inventory.reserve(f"WO-X{n}", FUSE, 1) for n in range(20)])
    assert sum(1 for item in results if item) == 5
    balance = await world.db["inventory_balances"].find_one({"itemId": FUSE, "locationId": "LOC-MAIN"})
    assert balance["reserved"] == 5 and balance["onHand"] - balance["reserved"] == 0
    assert await world.db["reservations"].count_documents({"itemId": FUSE, "status": "ACTIVE"}) == 5


async def test_a_reservation_larger_than_free_stock_reserves_nothing(world):
    await world.db["inventory_balances"].update_many({"itemId": FUSE}, {"$set": {"onHand": 1, "reserved": 0}})
    before = await stock_hash(world.db)
    assert await world.services.inventory.reserve("WO-Y", FUSE, 1000) is None
    assert await stock_hash(world.db) == before


async def test_free_parts_are_reserved_straight_away_and_released_on_cancel(world):
    await world.db["inventory_balances"].update_many({"itemId": FUSE}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": FUSE, "locationId": "LOC-MAIN"}, {"$set": {"onHand": 4}})
    order_id, body = await blocked_on_parts(world, item=FUSE, qty=3)
    assert body["parts"][0]["state"] == "RESERVED" and body["approvalId"] is None
    assert (await world.db["inventory_balances"].find_one({"itemId": FUSE, "locationId": "LOC-MAIN"}))["reserved"] == 3
    cancelled = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/cancel", json={"reason": "Done by contractor"})
    assert cancelled.status_code == 200
    assert (await world.db["inventory_balances"].find_one({"itemId": FUSE, "locationId": "LOC-MAIN"}))["reserved"] == 0


async def test_reserving_below_the_threshold_notifies_once(world):
    await world.db["inventory_balances"].update_many({"itemId": FUSE}, {"$set": {"onHand": 0, "reserved": 0}})
    await world.db["inventory_balances"].update_one({"itemId": FUSE, "locationId": "LOC-MAIN"}, {"$set": {"onHand": 10}})
    # FUSE's reorder threshold is 6, so starting stock of 10 is comfortably above it.
    assert await world.services.inventory.reserve("WO-LOW-1", FUSE, 3) is not None  # free 7: still above the line
    assert await world.db["outbox_events"].count_documents({"eventType": "inventory.low"}) == 0

    assert await world.services.inventory.reserve("WO-LOW-1", FUSE, 1) is not None  # free 6: at the line
    assert await world.db["outbox_events"].count_documents({"eventType": "inventory.low"}) == 1

    assert await world.services.inventory.reserve("WO-LOW-1", FUSE, 1) is not None  # free 5: still low, no repeat
    assert await world.db["outbox_events"].count_documents({"eventType": "inventory.low"}) == 1

    await world.services.outbox.dispatch_due()
    told = {row["userId"] async for row in world.db["notifications"].find({"eventType": "inventory.low"})}
    approvers = {row["_id"] async for row in world.db["users"].find({"roleKey": "PROCUREMENT_APPROVER"})}
    assert told == approvers and told

    # Releasing stock back above the line clears the flag, so a later drop notifies again.
    assert await world.services.inventory.release_for_work_order("WO-LOW-1", "U-TEST", "SYSTEM") == 3
    assert (await world.db["inventory_items"].find_one({"_id": FUSE}))["lowStockAlertSent"] is False
    assert await world.services.inventory.reserve("WO-LOW-2", FUSE, 4) is not None  # free back down to 6
    assert await world.db["outbox_events"].count_documents({"eventType": "inventory.low"}) == 2


async def test_asking_for_the_same_part_twice_is_refused(world):
    incident = (await report(world, "FACULTY", "Power socket sparking in ARB-204, smells of burning")).json()["incidentId"]
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/incidents/{incident}/actions/incident.createWorkOrder")
    order_id = (await world.db["work_orders"].find_one({"incidentId": incident}))["_id"]
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/assign", json={"technicianId": "T-01"})
    response = await world.call("TECHNICIAN", "POST", f"/api/v1/work-orders/{order_id}/block", json={"reason": "WAITING_FOR_PARTS", "parts": [{"itemId": FUSE, "qty": 1}, {"itemId": FUSE, "qty": 1}]})
    assert response.status_code == 422 and response.json()["code"] == "DUPLICATE_RESERVATION"
    assert await world.db["reservations"].count_documents({}) == 0


async def test_the_reconciler_finishes_an_interrupted_posting_exactly_once(world):
    ledger = world.services.inventory.ledger
    await world.db["stock_ledger"].insert_one(
        {"_id": "GR-CRASH-1", "postingKey": "GR-CRASH-1", "itemId": MCB, "locationId": "LOC-MAIN", "onHandDelta": 3, "reservedDelta": 0, "kind": "RECEIPT", "applied": False, "at": utcnow()}
    )
    assert await ledger.reconcile() == 1
    assert await ledger.reconcile() == 0
    assert (await world.db["inventory_balances"].find_one({"_id": "BAL-MCB-32A-3P-LOC-MAIN"}))["onHand"] == 3
    assert await ledger.post(key="GR-CRASH-1", item_id=MCB, location_id="LOC-MAIN", on_hand=3, kind="RECEIPT", source=("X", "Y"), actor_id="U") is False


async def test_a_technician_sees_their_parts_and_the_catalog_but_not_stock_levels(world):
    await blocked_on_parts(world)
    mine = (await world.call("TECHNICIAN", "GET", "/api/v1/inventory/mine")).json()
    assert mine[0]["sku"] == "MCB-32A-3P" and mine[0]["state"] == "SHORT"
    catalog = (await world.call("TECHNICIAN", "GET", "/api/v1/inventory/catalog")).json()
    assert any(row["sku"] == "MCB-32A-3P" and row["available"] == 0 for row in catalog) and "onHand" not in catalog[0]
    assert (await world.call("TECHNICIAN", "GET", "/api/v1/inventory/items")).status_code == 403
    rows = (await world.call("FACILITIES_ADMIN", "GET", "/api/v1/inventory/items")).json()
    mcb = next(row for row in rows if row["sku"] == "MCB-32A-3P")
    assert mcb["status"] == "OUT" and mcb["blockedWorkOrders"] == 1 and rows[0]["status"] == "OUT"


# ---- approvals ---------------------------------------------------------------------------------------------------


async def test_nobody_approves_their_own_request(world):
    created = await world.call("FACILITIES_ADMIN", "POST", "/api/v1/approvals", json={"type": "COSTLY_REPAIR", "title": "Rewire the lab", "justification": "Old wiring", "amountPaise": 500_000})
    assert created.status_code == 201
    body = created.json()
    assert body["unavailableActions"][0]["reason"].startswith("You raised this request")
    response = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/approvals/{body['id']}/decide", json={"decision": "APPROVE"})
    assert response.status_code == 422 and response.json()["details"]["findings"][0]["code"] == "SELF_APPROVAL"
    assert (await world.db["approvals"].find_one({"_id": body["id"]}))["status"] == "SUBMITTED"


async def test_a_system_administrator_cannot_approve(world):
    _, body = await blocked_on_parts(world)
    assert (await world.call("SYSTEM_ADMIN", "POST", f"/api/v1/approvals/{body['approvalId']}/decide", json={"decision": "APPROVE"})).status_code == 403


async def test_routing_and_the_limit_follow_the_amount(world):
    small = (await world.call("DEPARTMENT_MANAGER", "POST", "/api/v1/approvals", json={"type": "COSTLY_REPAIR", "title": "Fix benches", "justification": "Broken", "amountPaise": 2_000_000})).json()
    assert small["routing"] == "Routed to a Department Manager."
    big = (await world.call("DEPARTMENT_MANAGER", "POST", "/api/v1/approvals", json={"type": "COSTLY_REPAIR", "title": "Replace AC", "justification": "Dead", "amountPaise": 20_000_000})).json()
    assert big["routing"].startswith("Above the ₹25,000") and "Procurement" in big["routing"]
    over = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/approvals/{big['id']}/decide", json={"decision": "APPROVE"})  # ₹2 lakh, Facilities limit ₹1 lakh
    assert over.status_code == 409 and over.json()["code"] == "APPROVAL_REQUIRED"
    ok = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/approvals/{big['id']}/decide", json={"decision": "APPROVE"})
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"
    again = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/approvals/{big['id']}/decide", json={"decision": "REJECT"})
    assert again.status_code == 422 and again.json()["code"] == "ALREADY_DECIDED"


async def test_a_stale_purchase_is_refused_at_execution(world):
    order_id, body = await blocked_on_parts(world)
    await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/work-orders/{order_id}/cancel", json={"reason": "Panel replaced instead"})
    response = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/approvals/{body['approvalId']}/decide", json={"decision": "APPROVE"})
    assert response.status_code == 409 and response.json()["code"] == "STALE"
    assert (await world.db["approvals"].find_one({"_id": body["approvalId"]}))["status"] == "STALE"
    assert await world.db["purchase_orders"].count_documents({}) == 0


async def test_clarification_goes_back_to_the_requester_and_returns(world):
    created = (await world.call("DEPARTMENT_MANAGER", "POST", "/api/v1/approvals", json={"type": "COSTLY_REPAIR", "title": "Fix benches", "justification": "Broken", "amountPaise": 2_000_000})).json()
    asked = await world.call("FACILITIES_ADMIN", "POST", f"/api/v1/approvals/{created['id']}/decide", json={"decision": "CLARIFY", "reason": "How many benches?"})
    assert asked.json()["status"] == "NEEDS_CLARIFICATION"
    answered = await world.call("DEPARTMENT_MANAGER", "POST", f"/api/v1/approvals/{created['id']}/answer", json={"text": "Twelve benches in ARB-204"})
    assert answered.json()["status"] == "SUBMITTED" and answered.json()["decisions"][-1]["decision"] == "CLARIFIED"


# ---- invoices ------------------------------------------------------------------------------------------------------


async def test_a_price_difference_is_a_discrepancy_until_a_person_accepts_it(world):
    _, body = await blocked_on_parts(world)
    po_id = (await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/approvals/{body['approvalId']}/decide", json={"decision": "APPROVE"})).json()["purchaseOrderId"]
    invoice = (await upload(world, po_id, price="1600.00")).json()
    assert invoice["status"] == "DISCREPANCY" and invoice["discrepancies"][0]["code"] == "PRICE_MISMATCH" and invoice["lines"][0]["match"] == "PRICE"
    blocked = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/invoices/{invoice['id']}/validate")
    assert blocked.status_code == 422 and blocked.json()["code"] == "DISCREPANCIES_OPEN"
    resolved = (await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/invoices/{invoice['id']}/resolve", json={"code": "PRICE_MISMATCH", "note": "Supplier price rise agreed"})).json()
    assert resolved["status"] == "MATCHED" and resolved["lines"][0]["match"] == "OK"


async def test_an_invoice_without_an_order_cannot_be_waved_through(world):
    text = base64.b64encode(b"Supplier: Someone\nInvoice No: X1\nWidget 3 x 10.00\n").decode()
    invoice = (await world.call("PROCUREMENT_APPROVER", "POST", "/api/v1/invoices", json={"fileName": "x.txt", "mime": "text/plain", "contentBase64": text})).json()
    assert invoice["status"] == "DISCREPANCY" and any(row["code"] == "NO_PURCHASE_ORDER" for row in invoice["discrepancies"])
    refused = await world.call("PROCUREMENT_APPROVER", "POST", f"/api/v1/invoices/{invoice['id']}/resolve", json={"code": "NO_PURCHASE_ORDER"})
    assert refused.status_code == 422 and refused.json()["code"] == "CANNOT_ACCEPT"


async def test_a_file_that_is_not_what_it_claims_is_refused(world):
    fake = base64.b64encode(b"not a pdf").decode()
    response = await world.call("PROCUREMENT_APPROVER", "POST", "/api/v1/invoices", json={"fileName": "x.pdf", "mime": "application/pdf", "contentBase64": fake})
    assert response.status_code == 422 and response.json()["code"] == "FILE_TYPE_MISMATCH"
    assert await world.db["invoices"].count_documents({}) == 0
