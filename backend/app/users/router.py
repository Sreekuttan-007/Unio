from dataclasses import replace

from fastapi import Depends, Request, Response

from app.approvals.service import DECIDE
from app.audit.service import AuditDomain
from app.core.access import GuardedRouter, authenticated, public, require
from app.core.authuser import AuthUser
from app.core.pagination import PageParams, PageResponse, page_params
from app.core.permission import Permission
from app.services import Services, get_services
from app.users.bootstrap import build_bootstrap
from app.users.models import (
    BootstrapResponse,
    CreateUser,
    DemoAccount,
    DemoLoginRequest,
    LoginRequest,
    ProfileUpdate,
    RoleChange,
    RoleDto,
    RoleUpdate,
    StatusUpdate,
    TokenResponse,
    UserDto,
)

auth_router = GuardedRouter(prefix="/api/v1/auth", tags=["auth"])
demo_router = GuardedRouter(prefix="/api/v1/auth", tags=["demo"])
me_router = GuardedRouter(prefix="/api/v1/me", tags=["me"])
admin_router = GuardedRouter(prefix="/api/v1/admin", tags=["admin"])


def _token_response(issued) -> TokenResponse:
    return TokenResponse(access_token=issued.token, expires_at=issued.expires_at)


@auth_router.post("/login", response_model=TokenResponse, dependencies=[public])
async def login(body: LoginRequest, request: Request, services: Services = Depends(get_services)) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    return _token_response(await services.auth.login(body.email, body.password, client_ip))


@auth_router.post("/logout", status_code=204)
async def logout(user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Response:
    await services.auth.logout(user)
    return Response(status_code=204)


# One-tap sign-in for the demo. Only mounted when DEMO_MODE_ENABLED is true, and limited to
# seeded demo accounts, so the frontend never holds a password.
@demo_router.get("/demo-accounts", response_model=list[DemoAccount], dependencies=[public])
async def demo_accounts(services: Services = Depends(get_services)) -> list[DemoAccount]:
    rows = await services.db["users"].find({"demoAccount": True, "status": "ACTIVE"}).to_list(length=50)
    return [
        DemoAccount(
            email=row["email"],
            name=row["name"],
            role_key=row["roleKey"],
            role_label=services.roles.get(row["roleKey"])["label"],
            accent=services.roles.get(row["roleKey"])["accent"],
        )
        for row in rows
    ]


@demo_router.post("/demo-login", response_model=TokenResponse, dependencies=[public])
async def demo_login(body: DemoLoginRequest, services: Services = Depends(get_services)) -> TokenResponse:
    return _token_response(await services.auth.demo_login(body.email))


@me_router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)
) -> BootstrapResponse:
    return await build_bootstrap(user, services.roles, services.db)


@me_router.get("/badges", response_model=dict[str, int])
async def badges(user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> dict[str, int]:
    """Live counts for navigation badges, each limited to what this person can see and act on."""
    db = services.db
    counts = {"notifications.unread": await db["notifications"].count_documents({"userId": user.id, "readAt": None})}
    if user.has(Permission.INCIDENT_TRIAGE):
        counts["incident.triage"] = await db["incidents"].count_documents({"status": {"$in": ["SUBMITTED", "UNDER_REVIEW"]}})
    if user.has(Permission.WORKORDER_EXECUTE):
        counts["workorder.open"] = await db["work_orders"].count_documents({"assignedUserId": user.id, "status": {"$in": ["ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"]}})
    deciding = [kind for kind, permission in DECIDE.items() if user.has(permission)]
    if deciding:
        counts["approval.pending"] = await db["approvals"].count_documents({"type": {"$in": deciding}, "status": {"$in": ["SUBMITTED", "UNDER_REVIEW"]}, "requesterId": {"$ne": user.id}})
    return counts


@me_router.patch("/profile", response_model=BootstrapResponse)
async def update_profile(
    body: ProfileUpdate, user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)
) -> BootstrapResponse:
    name = body.name.strip()
    await services.db["users"].update_one({"_id": user.id}, {"$set": {"name": name}, "$inc": {"version": 1}})
    await services.audit.record_as(
        user,
        action="user.profile.update",
        domain=AuditDomain.SYSTEM,
        entity_type="USER",
        entity_id=user.id,
        before={"name": user.name},
        after={"name": name},
    )
    return await build_bootstrap(replace(user, name=name), services.roles, services.db)


@admin_router.get("/users", response_model=PageResponse[UserDto])
async def list_users(
    actor: AuthUser = Depends(require(Permission.ADMIN_USERS)),
    paging: PageParams = Depends(page_params),
    services: Services = Depends(get_services),
) -> PageResponse[UserDto]:
    items, total = await services.directory.list(actor, paging.skip, paging.size)
    return PageResponse(items=items, page=paging.page, size=paging.size, total=total)


@admin_router.post("/users", response_model=UserDto, status_code=201)
async def create_user(
    body: CreateUser,
    actor: AuthUser = Depends(require(Permission.ADMIN_USERS)),
    services: Services = Depends(get_services),
) -> UserDto:
    return await services.directory.create(actor, body)


@admin_router.patch("/users/{user_id}/status", response_model=UserDto)
async def set_user_status(
    user_id: str,
    body: StatusUpdate,
    actor: AuthUser = Depends(require(Permission.ADMIN_USERS)),
    services: Services = Depends(get_services),
) -> UserDto:
    return await services.directory.set_status(actor, user_id, body.status)


@admin_router.patch("/users/{user_id}/role", response_model=UserDto)
async def set_user_role(
    user_id: str,
    body: RoleChange,
    actor: AuthUser = Depends(require(Permission.ADMIN_USERS)),
    services: Services = Depends(get_services),
) -> UserDto:
    return await services.directory.set_role(actor, user_id, body.role_key)


def _role_dto(role: dict) -> RoleDto:
    return RoleDto(
        key=role["_id"],
        label=role["label"],
        workspace=role["workspace"],
        accent=role["accent"],
        permissions=role["permissions"],
        scopes=role.get("scopes", {}),
        version=role.get("version", 0),
    )


@admin_router.get("/permissions", response_model=list[str])
async def list_permissions(actor: AuthUser = Depends(require(Permission.ADMIN_ROLES))) -> list[str]:
    """Every permission key that exists, so the role editor can offer the full set."""
    return sorted(permission.value for permission in Permission)


@admin_router.get("/roles", response_model=list[RoleDto])
async def list_roles(
    actor: AuthUser = Depends(require(Permission.ADMIN_ROLES)), services: Services = Depends(get_services)
) -> list[RoleDto]:
    return [_role_dto(role) for role in services.roles.all()]


@admin_router.put("/roles/{key}", response_model=RoleDto)
async def update_role(
    key: str,
    body: RoleUpdate,
    actor: AuthUser = Depends(require(Permission.ADMIN_ROLES)),
    services: Services = Depends(get_services),
) -> RoleDto:
    return _role_dto(await services.roles.update_permissions(key, body.permissions, actor))
