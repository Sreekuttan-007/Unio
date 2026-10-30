from datetime import datetime

from pydantic import Field

from app.core.actions import AvailableAction, UnavailableAction
from app.core.schema import ApiModel

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(ApiModel):
    access_token: str
    expires_at: datetime


class DemoLoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)


class DemoAccount(ApiModel):
    email: str
    name: str
    role_key: str
    role_label: str
    accent: str


class NavBadge(ApiModel):
    source: str


class NavItem(ApiModel):
    key: str
    label: str
    path: str
    icon: str
    badge: NavBadge | None = None


class UserSummary(ApiModel):
    id: str
    name: str
    email: str
    avatar_initials: str


class RoleSummary(ApiModel):
    key: str
    label: str
    workspace: str


class DepartmentSummary(ApiModel):
    id: str
    name: str


class Theme(ApiModel):
    accent: str


class BootstrapResponse(ApiModel):
    """Everything the frontend needs to become the right application for this role."""

    user: UserSummary
    role: RoleSummary
    department: DepartmentSummary | None
    permissions: list[str]
    scopes: dict[str, str]
    navigation: list[NavItem]
    landing_path: str
    feature_flags: dict[str, bool]
    theme: Theme
    server_time: datetime


class UserDto(ApiModel):
    id: str
    name: str
    email: str
    role_key: str
    department_id: str | None
    status: str
    last_login_at: datetime | None
    available_actions: list[AvailableAction]
    unavailable_actions: list[UnavailableAction]


class CreateUser(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=10, max_length=200)
    role_key: str = Field(min_length=1)
    department_id: str | None = None


class StatusUpdate(ApiModel):
    status: str = Field(pattern="^(ACTIVE|INACTIVE)$")


class RoleChange(ApiModel):
    role_key: str = Field(min_length=1)


class ProfileUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=80)


class RoleDto(ApiModel):
    key: str
    label: str
    workspace: str
    accent: str
    permissions: list[str]
    scopes: dict[str, str]
    version: int


class RoleUpdate(ApiModel):
    permissions: list[str]
