from typing import Any

from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.users.models import BootstrapResponse, DepartmentSummary, RoleSummary, Theme, UserSummary
from app.users.navigation import navigation_for
from app.users.roles import RoleService

# All off until the AI features are integrated in Phase 4.
FEATURE_FLAGS: dict[str, bool] = {
    "mlTriage": False,
    "mlDuplicate": False,
    "mlSummary": False,
    "ocr": False,
    "slaRisk": False,
}


def initials(name: str) -> str:
    return "".join(part[0].upper() for part in name.split() if part and part[0].isalpha())[:2]


async def build_bootstrap(user: AuthUser, roles: RoleService, db: Any) -> BootstrapResponse:
    role = roles.get(user.role_key)
    navigation = navigation_for(role["workspace"], user.permissions)
    department = None
    if user.department_id:
        found = await db["departments"].find_one({"_id": user.department_id})
        if found:
            department = DepartmentSummary(id=found["_id"], name=found["name"])
    return BootstrapResponse(
        user=UserSummary(id=user.id, name=user.name, email=user.email, avatar_initials=initials(user.name)),
        role=RoleSummary(key=role["_id"], label=role["label"], workspace=role["workspace"]),
        department=department,
        permissions=sorted(permission.value for permission in user.permissions),
        scopes={entity.value: scope.value for entity, scope in user.scopes.items()},
        navigation=navigation,
        landing_path=navigation[0].path if navigation else "/not-permitted",
        feature_flags=FEATURE_FLAGS,
        theme=Theme(accent=role["accent"]),
        server_time=utcnow(),
    )
