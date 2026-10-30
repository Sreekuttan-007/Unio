from dataclasses import dataclass

from app.core.permission import Permission as P
from app.users.models import NavBadge, NavItem


@dataclass(frozen=True)
class NavEntry:
    key: str
    label: str
    slug: str
    icon: str
    any_of: tuple[P, ...]
    badge: str | None = None


def _item(key: str, label: str, slug: str, icon: str, *any_of: P, badge: str | None = None) -> NavEntry:
    return NavEntry(key, label, slug, icon, any_of, badge)


# One manifest per workspace. An item appears only while the role holds one of its permissions,
# so editing a role changes the sidebar with no frontend change. Every key needs a screen in
# frontend/src/platform/workspaces/registry.ts (checked by a test).
CATALOG: dict[str, tuple[NavEntry, ...]] = {
    "student": (
        _item("student.home", "Home", "home", "house", P.ISSUE_READ_OWN),
        _item("student.report", "Report Issue", "report", "circle-plus", P.ISSUE_CREATE),
        _item("student.myReports", "My Reports", "reports", "clipboard-list", P.ISSUE_READ_OWN),
        _item("student.notices", "Campus Notices", "notices", "megaphone", P.ISSUE_READ_OWN),
        _item("student.map", "Campus Map", "map", "map", P.MAP_READ_PUBLIC),
    ),
    "faculty": (
        _item("faculty.home", "Home", "home", "house", P.ISSUE_READ_OWN),
        _item("faculty.report", "Report Issue", "report", "circle-plus", P.ISSUE_CREATE),
        _item("faculty.booking", "Book a Room", "book", "calendar-plus", P.BOOKING_REQUEST),
        _item("faculty.myBookings", "My Bookings", "bookings", "calendar-days", P.BOOKING_READ_OWN),
        _item("faculty.impact", "Academic Impact", "impact", "graduation-cap", P.CASCADE_READ),
        _item("faculty.map", "Campus Map", "map", "map", P.MAP_READ_PUBLIC),
    ),
    "department": (
        _item("dept.overview", "Overview", "overview", "layout-dashboard", P.ANALYTICS_READ_DEPARTMENT),
        _item("dept.incidents", "Department Incidents", "incidents", "siren", P.ISSUE_READ_DEPARTMENT),
        _item("dept.workRequests", "Work Requests", "work-requests", "wrench", P.WORKORDER_READ_DEPARTMENT),
        _item("dept.resources", "Resources", "resources", "building-2", P.WORKORDER_READ_DEPARTMENT),
        _item("dept.bookings", "Room Bookings", "bookings", "calendar-days", P.BOOKING_READ_DEPARTMENT),
        _item("dept.inventory", "Inventory", "inventory", "package", P.INVENTORY_READ_DEPARTMENT),
        _item("dept.approvals", "Approvals", "approvals", "badge-check", P.APPROVAL_READ_DEPARTMENT),
        _item("dept.sla", "SLA & Escalations", "sla", "timer", P.SLA_READ_DEPARTMENT),
        _item("dept.analytics", "Analytics", "analytics", "chart-column", P.ANALYTICS_READ_DEPARTMENT),
    ),
    "facilities": (
        _item("fac.command", "Command Centre", "command", "radar", P.ANALYTICS_READ_CAMPUS),
        _item("fac.map", "Live Campus Map", "map", "map", P.MAP_READ_OPERATIONAL),
        _item("fac.inbox", "Intake Inbox", "inbox", "inbox", P.INBOX_READ),
        _item("fac.triage", "Incident Triage", "triage", "siren", P.INCIDENT_TRIAGE, badge="incident.triage"),
        _item("fac.workOrders", "Work Orders", "work-orders", "wrench", P.WORKORDER_READ_CAMPUS),
        _item("fac.technicians", "Technicians", "technicians", "hard-hat", P.WORKORDER_ASSIGN_CAMPUS),
        _item("fac.collision", "Collision Review", "collisions", "shield-alert", P.COLLISION_REVIEW),
        _item("fac.simulator", "What-If Simulator", "simulator", "flask-conical", P.SIMULATION_RUN),
        _item("fac.inventory", "Inventory", "inventory", "package", P.INVENTORY_READ_CAMPUS),
        _item("fac.approvals", "Approvals", "approvals", "badge-check", P.APPROVAL_DECIDE_OVERRIDE),
        _item("fac.sla", "SLA Monitor", "sla", "timer", P.SLA_READ_CAMPUS),
        _item("fac.analytics", "Analytics", "analytics", "chart-column", P.ANALYTICS_READ_CAMPUS),
        _item("fac.audit", "Audit Trail", "audit", "scroll-text", P.AUDIT_READ_CAMPUS),
    ),
    "procurement": (
        _item("proc.overview", "Overview", "overview", "layout-dashboard", P.ANALYTICS_READ_PROCUREMENT),
        _item("proc.queue", "Approval Queue", "queue", "badge-check", P.APPROVAL_DECIDE_PURCHASE, badge="approval.pending"),
        _item("proc.requests", "Requests", "requests", "clipboard-list", P.APPROVAL_READ_ALL),
        _item("proc.orders", "Purchase Orders", "orders", "shopping-cart", P.PURCHASE_ORDER_MANAGE),
        _item("proc.invoices", "Invoices", "invoices", "receipt-text", P.INVOICE_READ),
        _item("proc.discrepancies", "Discrepancies", "discrepancies", "triangle-alert", P.INVOICE_VALIDATE),
        _item("proc.receipts", "Goods Receipts", "receipts", "package-check", P.RECEIPT_VALIDATE),
        _item("proc.history", "History", "history", "history", P.AUDIT_READ_PROCUREMENT),
    ),
    "technician": (
        _item("tech.tasks", "My Tasks", "tasks", "clipboard-check", P.WORKORDER_READ_ASSIGNED, badge="workorder.open"),
        _item("tech.parts", "Parts", "parts", "package", P.INVENTORY_READ_RESERVED),
        _item("tech.availability", "Availability", "availability", "calendar-clock", P.TECHNICIAN_AVAILABILITY_SELF),
        _item("tech.history", "History", "history", "history", P.WORKORDER_READ_ASSIGNED),
        _item("tech.map", "Site Map", "map", "map-pin", P.MAP_READ_PUBLIC),
    ),
    "system": (
        _item("sys.overview", "System Overview", "overview", "activity", P.ANALYTICS_READ_SYSTEM),
        _item("sys.users", "Users", "users", "users", P.ADMIN_USERS),
        _item("sys.roles", "Roles & Permissions", "roles", "key-round", P.ADMIN_ROLES),
        _item("sys.campus", "Campus Master Data", "campus", "building-2", P.ADMIN_CAMPUS),
        _item("sys.staff", "Staff & Skills", "staff", "hard-hat", P.ADMIN_STAFF),
        _item("sys.inventoryMaster", "Inventory Master", "inventory", "package", P.INVENTORY_MASTER_MANAGE),
        _item("sys.rules", "Operational Rules", "rules", "sliders-horizontal", P.ADMIN_RULES),
        _item("sys.slaPolicy", "SLA Policies", "sla-policies", "timer", P.ADMIN_SLA_POLICY),
        _item("sys.integrations", "AI & Integrations", "integrations", "plug", P.ADMIN_INTEGRATIONS),
        _item("sys.audit", "Audit Logs", "audit", "scroll-text", P.AUDIT_READ_SYSTEM),
        _item("sys.seed", "Seed & Demo Data", "seed", "database", P.ADMIN_SEED),
    ),
}


def navigation_for(workspace: str, permissions: frozenset[P]) -> list[NavItem]:
    return [
        NavItem(
            key=entry.key,
            label=entry.label,
            path=f"/w/{workspace}/{entry.slug}",
            icon=entry.icon,
            badge=NavBadge(source=entry.badge) if entry.badge else None,
        )
        for entry in CATALOG.get(workspace, ())
        if any(permission in permissions for permission in entry.any_of)
    ]
