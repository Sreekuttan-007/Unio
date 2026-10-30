import logging
from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import not_found, rule
from app.core.identity import ParsedToken
from app.core.permission import Permission
from app.core.scope import DataScope, EntityType

log = logging.getLogger("unio.roles")

SYSTEM_ADMIN_ROLE = "SYSTEM_ADMIN"

# Configuring the platform never grants business authority. Without this rule a System
# Administrator could use the role editor to give themselves approval rights.
BUSINESS_AUTHORITY: frozenset[Permission] = frozenset(
    {
        Permission.APPROVAL_DECIDE_PURCHASE,
        Permission.APPROVAL_DECIDE_REPAIR,
        Permission.APPROVAL_DECIDE_OVERRIDE,
        Permission.WORKORDER_ASSIGN_CAMPUS,
        Permission.WORKORDER_ASSIGN_DEPARTMENT,
        Permission.WORKORDER_EXECUTE,
        Permission.WORKORDER_VERIFY,
        Permission.INVENTORY_TRANSACT,
        Permission.INVENTORY_RESERVE,
        Permission.INVOICE_VALIDATE,
        Permission.RECEIPT_VALIDATE,
        Permission.PURCHASE_ORDER_MANAGE,
        Permission.SIMULATION_EXECUTE,
        Permission.BOOKING_COORDINATE,
    }
)


class RoleService:
    """Roles are read on every request, so they are cached and refreshed when edited."""

    def __init__(self, db: Any, audit: AuditService) -> None:
        self._roles = db["roles_permissions"]
        self._audit = audit
        self._cache: dict[str, dict[str, Any]] = {}

    async def refresh(self) -> None:
        self._cache = {role["_id"]: role async for role in self._roles.find({})}

    def get(self, key: str) -> dict[str, Any]:
        role = self._cache.get(key)
        if role is None:
            raise not_found("Role")
        return role

    def all(self) -> list[dict[str, Any]]:
        return sorted(self._cache.values(), key=lambda role: role["_id"])

    def permissions_of(self, user: dict[str, Any]) -> frozenset[Permission]:
        permissions: set[Permission] = set()
        for key in self.get(user["roleKey"])["permissions"]:
            try:
                permissions.add(Permission(key))
            except ValueError:
                log.warning("Role %s lists unknown permission %s", user["roleKey"], key)
        if user.get("procurementRequester"):
            permissions |= {Permission.APPROVAL_REQUEST_CREATE, Permission.APPROVAL_READ_OWN}
        return frozenset(permissions)

    def scopes_of(self, role_key: str) -> dict[EntityType, DataScope]:
        return {EntityType(entity): DataScope(scope) for entity, scope in self.get(role_key).get("scopes", {}).items()}

    def to_auth_user(self, user: dict[str, Any], token: ParsedToken) -> AuthUser:
        return AuthUser(
            id=user["_id"],
            name=user["name"],
            email=user["email"],
            role_key=user["roleKey"],
            campus_id=user["campusId"],
            department_id=user.get("departmentId"),
            managed_department_ids=tuple(user.get("managedDepartmentIds", [])),
            approval_limit_paise=int(user.get("approvalLimitPaise", 0)),
            permissions=self.permissions_of(user),
            scopes=self.scopes_of(user["roleKey"]),
            token_id=token.token_id,
            token_expires_at=token.expires_at,
        )

    async def update_permissions(self, key: str, requested: list[str], actor: AuthUser) -> dict[str, Any]:
        current = self.get(key)
        permissions: set[Permission] = set()
        for requested_key in requested:
            try:
                permissions.add(Permission(requested_key))
            except ValueError:
                raise rule("UNKNOWN_PERMISSION", f"Unknown permission: {requested_key}") from None
        if key == SYSTEM_ADMIN_ROLE:
            self._assert_system_admin_rules(permissions)
        ordered = sorted(permission.value for permission in permissions)
        await self._roles.update_one(
            {"_id": key}, {"$set": {"permissions": ordered, "updatedAt": utcnow()}, "$inc": {"version": 1}}
        )
        self._cache[key] = await self._roles.find_one({"_id": key})
        await self._audit.record_as(
            actor,
            action="role.permissions.update",
            domain=AuditDomain.SYSTEM,
            entity_type="ROLE",
            entity_id=key,
            before={"permissions": current["permissions"]},
            after={"permissions": ordered},
        )
        return self._cache[key]

    @staticmethod
    def _assert_system_admin_rules(permissions: set[Permission]) -> None:
        blocked = sorted(permission.value for permission in permissions & BUSINESS_AUTHORITY)
        if blocked:
            raise rule(
                "SEPARATION_OF_DUTIES",
                "System Administrators cannot hold business authority: " + ", ".join(blocked),
            )
        if Permission.ADMIN_ROLES not in permissions:
            raise rule("ROLE_LOCKOUT", "System Administrators must keep admin.roles.")
