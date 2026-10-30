from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.audit.service import AuditService
from app.bookings.service import BookingService
from app.collision.service import CollisionService
from app.config import Settings
from app.core.outbox import OutboxService
from app.core.security import JwtService, LoginRateLimiter, PasswordService
from app.files.service import FileStore
from app.incidents.inbox import InboxService
from app.incidents.service import IncidentService
from app.ml.service import MlService
from app.sla.service import SlaService
from app.users.directory import UserDirectory
from app.users.roles import RoleService
from app.users.service import AuthService, IdentityService
from app.workorders.service import WorkOrderService


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
    ml: MlService
    sla: SlaService
    incidents: IncidentService
    inbox: InboxService
    collisions: CollisionService
    bookings: BookingService
    files: FileStore
    workorders: WorkOrderService


def build_services(settings: Settings, db: Any) -> Services:
    audit = AuditService(db)
    roles = RoleService(db, audit)
    passwords = PasswordService()
    jwt_service = JwtService(settings.jwt_secret, settings.jwt_ttl_minutes)
    limiter = LoginRateLimiter(settings.login_max_failures, settings.login_failure_window_seconds)
    outbox = OutboxService(db, settings.outbox_max_attempts)
    ml = MlService(db, settings)
    sla = SlaService(db)
    collisions = CollisionService(db, audit, settings.campus_id)
    incidents = IncidentService(db, ml, sla, audit, outbox, settings.campus_id, collisions)
    files = FileStore(db)
    workorders = WorkOrderService(db, collisions, incidents, sla, audit, outbox, files, settings.campus_id)
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
        outbox=outbox,
        ml=ml,
        sla=sla,
        incidents=incidents,
        inbox=InboxService(db, ml, incidents, audit, sla),
        collisions=collisions,
        bookings=BookingService(db, collisions, audit, outbox, settings.campus_id),
        files=files,
        workorders=workorders,
    )


def get_services(request: Request) -> Services:
    return request.app.state.services
