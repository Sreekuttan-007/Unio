"""The vocabulary of the Collision Engine. Plain data, no database, so a simulator can use it too."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    BOOK_ROOM = "BOOK_ROOM"
    MOVE_SESSION = "MOVE_SESSION"
    ASSIGN_TECHNICIAN = "ASSIGN_TECHNICIAN"
    RESERVE_PARTS = "RESERVE_PARTS"
    DECIDE_APPROVAL = "DECIDE_APPROVAL"
    VALIDATE_RECEIPT = "VALIDATE_RECEIPT"
    RESOLVE_INCIDENT = "RESOLVE_INCIDENT"


ROOM_ACTIONS = frozenset({ActionType.BOOK_ROOM, ActionType.MOVE_SESSION})


class Severity(StrEnum):
    HARD = "HARD"  # cannot proceed, and nothing overrides it
    APPROVAL = "APPROVAL"  # can proceed once a named approver has approved this exact action
    SOFT = "SOFT"  # can proceed if the person acknowledges it with a reason


class Decision(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class Stage(StrEnum):
    PREVIEW = "PREVIEW"
    COMMIT = "COMMIT"
    SIMULATION = "SIMULATION"


@dataclass(frozen=True)
class Finding:
    code: str
    rule_id: str
    severity: Severity
    message: str
    affected: tuple[tuple[str, str], ...] = ()  # (entity type, id)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "ruleId": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "affected": ", ".join(entity_id for _, entity_id in self.affected),
            "affectedEntities": [{"type": kind, "id": entity_id} for kind, entity_id in self.affected],
            "data": self.data,
        }


@dataclass
class ProposedAction:
    type: ActionType
    actor_id: str
    actor_role: str
    payload: dict[str, Any]
    at: datetime  # the moment of evaluation, passed in so a simulation is repeatable
    expected_state_token: str | None = None


@dataclass
class Acknowledgement:
    """What a person supplies to go ahead despite a soft or approval finding."""

    reason: str = ""
    codes: tuple[str, ...] = ()
    override_approval_id: str | None = None


@dataclass
class CollisionResult:
    decision: Decision
    findings: list[Finding]
    state_token: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    @property
    def soft_codes(self) -> list[str]:
        return [finding.code for finding in self.findings if finding.severity is Severity.SOFT]

    @property
    def needs_approval(self) -> bool:
        return any(finding.severity is Severity.APPROVAL for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "alternatives": self.alternatives,
            "stateToken": self.state_token,
        }


def decide(findings: list[Finding]) -> Decision:
    severities = {finding.severity for finding in findings}
    if Severity.HARD in severities:
        return Decision.BLOCK
    if Severity.APPROVAL in severities:
        return Decision.REQUIRE_APPROVAL
    if Severity.SOFT in severities:
        return Decision.WARN
    return Decision.ALLOW


def fingerprint(action_type: ActionType | str, payload: dict[str, Any]) -> str:
    """Identifies exactly what was proposed, so an approval can be bound to it and to nothing else."""
    body = json.dumps({"type": str(action_type), "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:32]


def rupees(paise: int) -> str:
    """12345600 -> ₹1,23,456, the way people here write money."""
    whole = abs(paise) // 100
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return f"₹{digits}" + (f".{abs(paise) % 100:02d}" if abs(paise) % 100 else "")
