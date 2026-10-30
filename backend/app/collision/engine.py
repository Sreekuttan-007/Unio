"""Runs the rules and combines what they say. It reads through a StateReader and writes nothing."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.collision.models import Acknowledgement, CollisionResult, Decision, Finding, ProposedAction, Severity, decide
from app.collision.reader import StateReader
from app.collision.rules import ALL_RULES, Rule, StaleState

SEVERITY_ORDER = {Severity.HARD: 0, Severity.APPROVAL: 1, Severity.SOFT: 2}
MIN_REASON_LENGTH = 5


@dataclass(frozen=True)
class RuleConfig:
    enabled: bool = True
    params: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Gate:
    """Whether an action may go ahead, given what was found and what the person supplied."""

    allowed: bool
    status: int = 200
    code: str | None = None
    message: str | None = None
    requires_reason: bool = False


class CollisionEngine:
    def __init__(self, rules: tuple[Rule, ...] = ALL_RULES) -> None:
        self._rules = tuple(rule for rule in rules if not isinstance(rule, StaleState))
        self._stale = next((rule for rule in rules if isinstance(rule, StaleState)), None)

    def _active(self, action: ProposedAction, config: Mapping[str, RuleConfig]) -> list[Rule]:
        chosen = []
        for rule in self._rules:
            if action.type not in rule.actions:
                continue
            setting = config.get(rule.id)
            # A locked rule protects a guarantee, so a configuration row cannot switch it off.
            if rule.locked or setting is None or setting.enabled:
                chosen.append(rule)
        return chosen

    async def evaluate(self, action: ProposedAction, reader: StateReader, config: Mapping[str, RuleConfig] | None = None) -> CollisionResult:
        settings = config or {}
        findings: list[Finding] = []
        for rule in self._active(action, settings):
            setting = settings.get(rule.id)
            params = {**rule.default_params, **(dict(setting.params) if setting and setting.params else {})}
            findings.extend(await rule.check(action, reader, params))
        token = reader.token()
        if self._stale is not None:
            findings.extend(await self._stale.check(action, reader, {}))
        findings.sort(key=lambda item: SEVERITY_ORDER[item.severity])
        return CollisionResult(decide(findings), findings, token)


def gate(result: CollisionResult, acknowledgement: Acknowledgement | None, approval_valid: bool) -> Gate:
    """Hard findings are final. An approval finding needs a valid approval. A soft finding needs a reason."""
    if result.decision is Decision.BLOCK:
        first = next(finding for finding in result.findings if finding.severity is Severity.HARD)
        return Gate(False, 422, "COLLISION_BLOCKED", first.message)
    if result.needs_approval and not approval_valid:
        first = next(finding for finding in result.findings if finding.severity is Severity.APPROVAL)
        return Gate(False, 409, "APPROVAL_REQUIRED", first.message)
    soft = result.soft_codes
    if soft:
        reason = (acknowledgement.reason if acknowledgement else "").strip()
        covered = set(acknowledgement.codes) if acknowledgement else set()
        if len(reason) < MIN_REASON_LENGTH or not set(soft) <= covered:
            first = next(finding for finding in result.findings if finding.severity is Severity.SOFT)
            return Gate(False, 409, "COLLISION_WARNING", first.message, requires_reason=True)
    return Gate(True)
