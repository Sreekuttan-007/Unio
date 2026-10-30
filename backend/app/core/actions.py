from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.authuser import AuthUser
from app.core.permission import Permission
from app.core.schema import ApiModel

T = TypeVar("T")


class AvailableAction(ApiModel):
    key: str
    label: str


class UnavailableAction(ApiModel):
    key: str
    label: str
    reason: str


class ActionSet(ApiModel):
    available_actions: list[AvailableAction]
    unavailable_actions: list[UnavailableAction]


@dataclass(frozen=True)
class ActionRule(Generic[T]):
    """blocked_reason returns None when the action is allowed in the current state of the entity."""

    key: str
    label: str
    any_of: tuple[Permission, ...]
    blocked_reason: Callable[[T, AuthUser], str | None]


class ActionResolver(Generic[T]):
    """Server-driven actions: permissions first, then state rules.

    An action the caller has no permission for is left out entirely, so a role never learns
    about controls it cannot use. A permitted action blocked by state comes back with a reason.
    """

    rules: tuple[ActionRule[T], ...] = ()

    def resolve(self, entity: T, user: AuthUser) -> ActionSet:
        available: list[AvailableAction] = []
        unavailable: list[UnavailableAction] = []
        for action_rule in self.rules:
            if not user.has_any(action_rule.any_of):
                continue
            reason = action_rule.blocked_reason(entity, user)
            if reason is None:
                available.append(AvailableAction(key=action_rule.key, label=action_rule.label))
            else:
                unavailable.append(UnavailableAction(key=action_rule.key, label=action_rule.label, reason=reason))
        return ActionSet(available_actions=available, unavailable_actions=unavailable)
