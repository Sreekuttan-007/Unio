from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from app.core.permission import Permission
from app.core.scope import DataScope, EntityType


@dataclass(frozen=True)
class AuthUser:
    """The authenticated caller, rebuilt from the database on every request."""

    id: str
    name: str
    email: str
    role_key: str
    campus_id: str
    department_id: str | None
    managed_department_ids: tuple[str, ...]
    approval_limit_paise: int
    permissions: frozenset[Permission]
    scopes: Mapping[EntityType, DataScope]
    token_id: str
    token_expires_at: datetime

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_any(self, candidates: Iterable[Permission]) -> bool:
        return any(candidate in self.permissions for candidate in candidates)
