from enum import StrEnum


class Permission(StrEnum):
    """FROZEN, append-only. See docs/RBAC_AND_NAVIGATION.md. The value is the wire key."""

    # intake and incidents (M1, M2)
    ISSUE_CREATE = "issue.create"
    ISSUE_READ_OWN = "issue.read.own"
    ISSUE_READ_ASSIGNED = "issue.read.assigned"
    ISSUE_READ_DEPARTMENT = "issue.read.department"
    ISSUE_READ_CAMPUS = "issue.read.campus"
    INCIDENT_TRIAGE = "incident.triage"
    INCIDENT_TRANSITION = "incident.transition"
    INCIDENT_LINK_DUPLICATE = "incident.link.duplicate"
    INCIDENT_SUMMARY_READ = "incident.summary.read"
    INBOX_READ = "inbox.read"
    INBOX_TRIAGE = "inbox.triage"

    # bookings (M5)
    BOOKING_REQUEST = "booking.request"
    BOOKING_READ_OWN = "booking.read.own"
    BOOKING_READ_DEPARTMENT = "booking.read.department"
    BOOKING_READ_CAMPUS = "booking.read.campus"
    BOOKING_COORDINATE = "booking.coordinate"
    BOOKING_CANCEL_ANY = "booking.cancel.any"

    # work orders (M4)
    WORKORDER_READ_ASSIGNED = "workorder.read.assigned"
    WORKORDER_READ_DEPARTMENT = "workorder.read.department"
    WORKORDER_READ_CAMPUS = "workorder.read.campus"
    WORKORDER_ASSIGN_DEPARTMENT = "workorder.assign.department"
    WORKORDER_ASSIGN_CAMPUS = "workorder.assign.campus"
    WORKORDER_EXECUTE = "workorder.execute"
    WORKORDER_VERIFY = "workorder.verify"
    TECHNICIAN_AVAILABILITY_SELF = "technician.availability.self"
    TECHNICIAN_AVAILABILITY_MANAGE = "technician.availability.manage"

    # constraint engines
    COLLISION_CHECK = "collision.check"
    COLLISION_REVIEW = "collision.review"
    CASCADE_READ = "cascade.read"
    SIMULATION_RUN = "simulation.run"
    SIMULATION_EXECUTE = "simulation.execute"

    # inventory (M6)
    INVENTORY_READ_RESERVED = "inventory.read.reserved"
    INVENTORY_READ_DEPARTMENT = "inventory.read.department"
    INVENTORY_READ_CAMPUS = "inventory.read.campus"
    INVENTORY_RESERVE = "inventory.reserve"
    INVENTORY_TRANSACT = "inventory.transact"
    INVENTORY_MASTER_MANAGE = "inventory.master.manage"

    # approvals: purchases, costly repairs, overrides (M7)
    APPROVAL_REQUEST_CREATE = "approval.request.create"
    APPROVAL_READ_OWN = "approval.read.own"
    APPROVAL_READ_DEPARTMENT = "approval.read.department"
    APPROVAL_READ_ALL = "approval.read.all"
    APPROVAL_DECIDE_PURCHASE = "approval.decide.purchase"
    APPROVAL_DECIDE_REPAIR = "approval.decide.repair"
    APPROVAL_DECIDE_OVERRIDE = "approval.decide.override"
    PURCHASE_ORDER_MANAGE = "purchase.order.manage"
    INVOICE_UPLOAD = "invoice.upload"
    INVOICE_READ = "invoice.read"
    INVOICE_VALIDATE = "invoice.validate"
    RECEIPT_VALIDATE = "receipt.validate"

    # cross-cutting (M8, M9)
    SLA_READ_OWN = "sla.read.own"
    SLA_READ_DEPARTMENT = "sla.read.department"
    SLA_READ_CAMPUS = "sla.read.campus"
    SLA_READ_PROCUREMENT = "sla.read.procurement"
    SLA_READ_SYSTEM = "sla.read.system"
    MAP_READ_PUBLIC = "map.read.public"
    MAP_READ_OPERATIONAL = "map.read.operational"
    ANALYTICS_READ_DEPARTMENT = "analytics.read.department"
    ANALYTICS_READ_CAMPUS = "analytics.read.campus"
    ANALYTICS_READ_PROCUREMENT = "analytics.read.procurement"
    ANALYTICS_READ_SYSTEM = "analytics.read.system"
    AUDIT_READ_CAMPUS = "audit.read.campus"
    AUDIT_READ_PROCUREMENT = "audit.read.procurement"
    AUDIT_READ_SYSTEM = "audit.read.system"

    # administration: configuration only, never business authority
    ADMIN_USERS = "admin.users"
    ADMIN_ROLES = "admin.roles"
    ADMIN_CAMPUS = "admin.campus"
    ADMIN_STAFF = "admin.staff"
    ADMIN_RULES = "admin.rules"
    ADMIN_SLA_POLICY = "admin.sla.policy"
    ADMIN_INTEGRATIONS = "admin.integrations"
    ADMIN_SEED = "admin.seed"

    # campus and staff directories (Phase 3)
    CAMPUS_READ = "campus.read"
    STAFF_READ = "staff.read"
