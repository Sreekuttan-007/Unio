import uuid
from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import ApiException, conflict, not_found, rule
from app.core.security import PasswordService
from app.users.actions import UserActionResolver
from app.users.models import CreateUser, UserDto
from app.users.roles import RoleService
from app.users.service import STATUS_ACTIVE


class UserDirectory:
    """Administrator operations on user accounts. Every change is audited."""

    def __init__(self, db: Any, roles: RoleService, passwords: PasswordService, audit: AuditService, campus_id: str):
        self._users = db["users"]
        self._roles = roles
        self._passwords = passwords
        self._audit = audit
        self._campus_id = campus_id
        self._actions = UserActionResolver()

    def to_dto(self, user: dict[str, Any], actor: AuthUser) -> UserDto:
        actions = self._actions.resolve(user, actor)
        return UserDto(
            id=user["_id"],
            name=user["name"],
            email=user["email"],
            role_key=user["roleKey"],
            department_id=user.get("departmentId"),
            status=user["status"],
            last_login_at=user.get("lastLoginAt"),
            available_actions=actions.available_actions,
            unavailable_actions=actions.unavailable_actions,
        )

    async def list(self, actor: AuthUser, skip: int, limit: int) -> tuple[list[UserDto], int]:
        total = await self._users.count_documents({})
        rows = await self._users.find({}).sort("name", 1).skip(skip).limit(limit).to_list(length=limit)
        return [self.to_dto(row, actor) for row in rows], total

    async def create(self, actor: AuthUser, body: CreateUser) -> UserDto:
        self._require_role(body.role_key)
        email = body.email.strip().lower()
        if await self._users.find_one({"email": email}) is not None:
            raise conflict("EMAIL_TAKEN", "An account with this email already exists.")
        now = utcnow()
        user = {
            "_id": f"U-{uuid.uuid4().hex[:12]}",
            "name": body.name.strip(),
            "email": email,
            "passwordHash": await self._passwords.hash(body.password),
            "roleKey": body.role_key,
            "departmentId": body.department_id,
            "managedDepartmentIds": [],
            "campusId": self._campus_id,
            "approvalLimitPaise": 0,
            "procurementRequester": False,
            "demoAccount": False,
            "status": STATUS_ACTIVE,
            "lastLoginAt": None,
            "version": 0,
            "createdAt": now,
            "updatedAt": now,
        }
        await self._users.insert_one(user)
        await self._audit.record_as(
            actor,
            action="user.create",
            domain=AuditDomain.SYSTEM,
            entity_type="USER",
            entity_id=user["_id"],
            after={"roleKey": user["roleKey"], "email": email},
        )
        return self.to_dto(user, actor)

    async def set_status(self, actor: AuthUser, user_id: str, status: str) -> UserDto:
        user = await self._load(user_id)
        if user_id == actor.id:
            raise rule("SELF_MODIFICATION", "You cannot change your own account status.")
        updated = await self._apply(user_id, {"status": status})
        await self._audit.record_as(
            actor,
            action="user.status.update",
            domain=AuditDomain.SYSTEM,
            entity_type="USER",
            entity_id=user_id,
            before={"status": user["status"]},
            after={"status": status},
        )
        return self.to_dto(updated, actor)

    async def set_role(self, actor: AuthUser, user_id: str, role_key: str) -> UserDto:
        user = await self._load(user_id)
        if user_id == actor.id:
            raise rule("SELF_MODIFICATION", "You cannot change your own role.")
        self._require_role(role_key)
        updated = await self._apply(user_id, {"roleKey": role_key})
        await self._audit.record_as(
            actor,
            action="user.role.update",
            domain=AuditDomain.SYSTEM,
            entity_type="USER",
            entity_id=user_id,
            before={"roleKey": user["roleKey"]},
            after={"roleKey": role_key},
        )
        return self.to_dto(updated, actor)

    def _require_role(self, role_key: str) -> None:
        try:
            self._roles.get(role_key)
        except ApiException:
            raise rule("UNKNOWN_ROLE", f"Unknown role: {role_key}") from None

    async def _load(self, user_id: str) -> dict[str, Any]:
        user = await self._users.find_one({"_id": user_id})
        if user is None:
            raise not_found("User")
        return user

    async def _apply(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        await self._users.update_one(
            {"_id": user_id}, {"$set": {**changes, "updatedAt": utcnow()}, "$inc": {"version": 1}}
        )
        return await self._load(user_id)
