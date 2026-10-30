from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import ApiException, not_found
from app.core.identity import ParsedToken
from app.core.security import IssuedToken, JwtService, LoginRateLimiter, PasswordService
from app.users.roles import RoleService

STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"


class IdentityService:
    """Turns a bearer token into the current user, reading the database on every request.

    Deactivating a user or changing a role therefore takes effect immediately, not when the
    token expires.
    """

    def __init__(self, db: Any, roles: RoleService, jwt: JwtService) -> None:
        self._users = db["users"]
        self._revoked = db["revoked_tokens"]
        self._roles = roles
        self._jwt = jwt

    async def verify_token(self, token: str) -> ParsedToken | None:
        parsed = self._jwt.parse(token)
        if parsed is None:
            return None
        if await self._revoked.find_one({"_id": parsed.token_id}) is not None:
            return None
        return parsed

    async def authenticate(self, token: str) -> AuthUser | None:
        parsed = await self.verify_token(token)
        if parsed is None:
            return None
        user = await self._users.find_one({"_id": parsed.user_id})
        if user is None or user.get("status") != STATUS_ACTIVE:
            return None
        try:
            return self._roles.to_auth_user(user, parsed)
        except ApiException:
            return None


class AuthService:
    def __init__(
        self, db: Any, passwords: PasswordService, jwt: JwtService, limiter: LoginRateLimiter, audit: AuditService
    ) -> None:
        self._users = db["users"]
        self._revoked = db["revoked_tokens"]
        self._passwords = passwords
        self._jwt = jwt
        self._limiter = limiter
        self._audit = audit
        # Compared when the email is unknown, so response time does not reveal which accounts exist.
        self._decoy_hash = passwords.hash_sync("decoy-password")

    async def login(self, email: str, password: str, client_ip: str) -> IssuedToken:
        normalised = email.strip().lower()
        limiter_key = f"{normalised}|{client_ip}"
        self._limiter.assert_allowed(limiter_key)
        user = await self._users.find_one({"email": normalised})
        stored_hash = user.get("passwordHash") if user else None
        matches = await self._passwords.verify(stored_hash or self._decoy_hash, password)
        if user is None or not stored_hash or not matches or user.get("status") != STATUS_ACTIVE:
            self._limiter.record_failure(limiter_key)
            raise ApiException(401, "INVALID_CREDENTIALS", "Incorrect email or password.")
        self._limiter.reset(limiter_key)
        return await self._issue(user, "auth.login")

    async def demo_login(self, email: str) -> IssuedToken:
        user = await self._users.find_one(
            {"email": email.strip().lower(), "demoAccount": True, "status": STATUS_ACTIVE}
        )
        if user is None:
            raise not_found("Demo account")
        return await self._issue(user, "auth.demo-login")

    async def logout(self, user: AuthUser) -> None:
        await self._revoked.replace_one(
            {"_id": user.token_id}, {"_id": user.token_id, "expiresAt": user.token_expires_at}, upsert=True
        )
        await self._audit.record_as(
            user, action="auth.logout", domain=AuditDomain.SYSTEM, entity_type="USER", entity_id=user.id
        )

    async def _issue(self, user: dict[str, Any], action: str) -> IssuedToken:
        await self._users.update_one({"_id": user["_id"]}, {"$set": {"lastLoginAt": utcnow()}})
        await self._audit.record(
            actor_id=user["_id"],
            actor_role=user["roleKey"],
            action=action,
            domain=AuditDomain.SYSTEM,
            entity_type="USER",
            entity_id=user["_id"],
        )
        return self._jwt.issue(user["_id"])
