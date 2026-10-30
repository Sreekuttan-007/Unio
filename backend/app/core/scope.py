from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.authuser import AuthUser


class DataScope(StrEnum):
    OWN = "OWN"
    ASSIGNED = "ASSIGNED"
    DEPARTMENT = "DEPARTMENT"
    CAMPUS = "CAMPUS"
    PROCUREMENT = "PROCUREMENT"
    RESERVED = "RESERVED"
    SYSTEM = "SYSTEM"


class EntityType(StrEnum):
    INCIDENT = "INCIDENT"
    WORK_ORDER = "WORK_ORDER"
    BOOKING = "BOOKING"
    INVENTORY = "INVENTORY"
    APPROVAL = "APPROVAL"
    SLA = "SLA"
    AUDIT = "AUDIT"
    RESOURCE = "RESOURCE"


# (field read by OWN, field read by ASSIGNED and RESERVED). None means that scope matches nothing.
_USER_FIELDS: dict[EntityType, tuple[str | None, str | None]] = {
    EntityType.INCIDENT: ("reporterIds", "assignedUserIds"),
    EntityType.WORK_ORDER: (None, "assignedUserId"),
    EntityType.BOOKING: ("requesterId", None),
    EntityType.INVENTORY: (None, "reservedForTechnicianIds"),
    EntityType.APPROVAL: ("requesterId", None),
    EntityType.SLA: ("subjectOwnerIds", "assignedUserId"),
    EntityType.AUDIT: (None, None),
    EntityType.RESOURCE: (None, None),
}

# Audit rows carry a domain instead of an owner. Values are AuditDomain names.
_AUDIT_DOMAINS: dict[DataScope, str] = {DataScope.CAMPUS: "OPERATIONS", DataScope.PROCUREMENT: "PROCUREMENT"}


def match_nothing() -> dict[str, Any]:
    return {"_id": {"$in": []}}


def scope_filter(user: "AuthUser", entity: EntityType) -> dict[str, Any]:
    """Layer 2 of RBAC: the Mongo filter every list and detail query must include.

    Fails closed: no scope configured for this role and entity means no rows.
    """
    scope = user.scopes.get(entity)
    if scope is None:
        return match_nothing()
    if entity is EntityType.AUDIT:
        return _audit_filter(scope)
    own_field, assigned_field = _USER_FIELDS[entity]
    match scope:
        case DataScope.OWN:
            return _by_user(own_field, user)
        case DataScope.ASSIGNED | DataScope.RESERVED:
            return _by_user(assigned_field, user)
        case DataScope.DEPARTMENT:
            if not user.managed_department_ids:
                return match_nothing()
            return {"departmentId": {"$in": list(user.managed_department_ids)}}
        case DataScope.CAMPUS:
            return {"campusId": user.campus_id}
        case DataScope.PROCUREMENT:
            return {"domain": "PROCUREMENT"}
        case DataScope.SYSTEM:
            return {}
    return match_nothing()


def _audit_filter(scope: DataScope) -> dict[str, Any]:
    if scope is DataScope.SYSTEM:
        return {}
    domain = _AUDIT_DOMAINS.get(scope)
    return {"domain": domain} if domain else match_nothing()


def _by_user(field: str | None, user: "AuthUser") -> dict[str, Any]:
    return match_nothing() if field is None else {field: user.id}
