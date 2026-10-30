"""Who decides what, and from whom parts are bought. Policy data (assumptions A26 and A27), seeded once and editable later.

Rows are inserted only when missing, so an administrator's changes survive restarts.
"""

from typing import Any

from app.core.bulk import insert_missing

# type, highest amount in paise (None means no ceiling), approver role. The cheapest matching row wins.
APPROVAL_RULES = (
    ("AR-PURCHASE", "PURCHASE", None, "PROCUREMENT_APPROVER"),
    ("AR-REPAIR-DEPT", "COSTLY_REPAIR", 2_500_000, "DEPARTMENT_MANAGER"),
    ("AR-REPAIR", "COSTLY_REPAIR", None, "PROCUREMENT_APPROVER"),
    ("AR-OVERRIDE", "OVERRIDE", None, "FACILITIES_ADMIN"),
)

# Fictional suppliers (constraint C2), each serving some item categories.
SUPPLIERS = (
    ("SUP-01", "Brightline Electricals", ("ELECTRICAL", "HVAC")),
    ("SUP-02", "NetCore Systems", ("NETWORK", "EQUIPMENT")),
    ("SUP-03", "Campus Hardware Co", ("PLUMBING", "CARPENTRY", "HOUSEKEEPING")),
)


async def ensure_procurement_policy(db: Any, campus_id: str) -> None:
    await insert_missing(db["approval_rules"], [{"_id": rule_id, "type": kind, "maxPaise": ceiling, "approverRole": role, "campusId": campus_id} for rule_id, kind, ceiling, role in APPROVAL_RULES])
    await insert_missing(db["suppliers"], [{"_id": supplier_id, "name": name, "categories": list(categories), "campusId": campus_id} for supplier_id, name, categories in SUPPLIERS])
