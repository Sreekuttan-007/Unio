from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.audit.service import AuditService
from app.config import Settings
from app.core.outbox import OutboxService
from app.core.security import JwtService, LoginRateLimiter, PasswordService
from app.users.directory import UserDirectory
from app.users.roles import RoleService
from app.users.service import AuthService, IdentityService


@dataclass
class Services:
    """The wired-up application. Built once at startup and read through get_services."""

    settings: Settings
    db: Any
    audit: AuditService
    roles: RoleService
    passwords: PasswordService
    jwt: JwtService
    identity: IdentityService
    auth: AuthService
    directory: UserDirectory
    outbox: OutboxService


def build_services(settings: Settings, db: Any) -> Services:
    audit = AuditService(db)
    roles = RoleService(db, audit)
    passwords = PasswordService()
    jwt_service = JwtService(settings.jwt_secret, settings.jwt_ttl_minutes)
    limiter = LoginRateLimiter(settings.login_max_failures, settings.login_failure_window_seconds)
    return Services(
        settings=settings,
        db=db,
        audit=audit,
        roles=roles,
        passwords=passwords,
        jwt=jwt_service,
        identity=IdentityService(db, roles, jwt_service),
        auth=AuthService(db, passwords, jwt_service, limiter, audit),
        directory=UserDirectory(db, roles, passwords, audit, settings.campus_id),
        outbox=OutboxService(db, settings.outbox_max_attempts),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services
