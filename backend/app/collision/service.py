"""The Collision Engine wired to the database: configuration, persistence of every check, and the gate.

Business services call enforce() at the moment they commit. The same rules run again there, on the
facts as they are then, so a decision made at preview time is never trusted blindly.
"""

from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.collision.alternatives import AlternativeSuggestionService
from app.collision.engine import CollisionEngine, RuleConfig, gate
from app.collision.models import (
    Acknowledgement,
    ActionType,
    CollisionResult,
    Decision,
    ProposedAction,
    Severity,
    Stage,
    fingerprint,
)
from app.collision.payloads import jsonable, parse_payload
from app.collision.reader import LiveStateReader, StateReader
from app.collision.rules import RULES_BY_ID, catalog
from app.core.authuser import AuthUser
from app.core.bulk import insert_missing
from app.core.clock import ensure_utc, local_time, utcnow
from app.core.errors import ApiException, not_found, rule
from app.core.ids import next_id


class CollisionService:
    def __init__(self, db: Any, audit: AuditService, campus_id: str) -> None:
        self._db = db
        self._audit = audit
        self._campus_id = campus_id
        self.engine = CollisionEngine()
        self.alternatives = AlternativeSuggestionService(self.engine)

    # ---- configuration ---------------------------------------------------------------------------

    async def ensure_rules(self) -> None:
        """Adds rules the catalogue gained. Rows an administrator has edited are never overwritten."""
        await insert_missing(self._db["collision_rules"], catalog())

    async def config(self) -> dict[str, RuleConfig]:
        rows = await self._db["collision_rules"].find({}).to_list(length=100)
        return {row["_id"]: RuleConfig(row.get("enabled", True), row.get("params") or {}) for row in rows}

    @staticmethod
    def rule_view(row: dict[str, Any]) -> dict[str, Any]:
        rule_object = RULES_BY_ID.get(row["_id"])
        return {
            "id": row["_id"], "code": row["code"], "name": row["name"], "description": row["description"], "actionTypes": row["actionTypes"],
            "severity": row["severity"], "enabled": True if row["locked"] else row["enabled"], "locked": row["locked"],
            "parameter": rule_object.describe(row.get("params") or {}) if rule_object else None,
            "params": row.get("params") or {},
            "parameterLabel": rule_object.parameter_label if rule_object else None,
        }

    async def rules(self) -> list[dict[str, Any]]:
        rows = await self._db["collision_rules"].find({}).sort("_id", 1).to_list(length=100)
        return [self.rule_view(row) for row in rows]

    async def update_rule(self, user: AuthUser, rule_id: str, enabled: bool | None, params: dict[str, Any] | None) -> dict[str, Any]:
        row = await self._db["collision_rules"].find_one({"_id": rule_id})
        if row is None:
            raise not_found("Rule")
        if enabled is False and row["locked"]:
            raise rule("RULE_LOCKED", f"{row['name']} protects a safety guarantee and cannot be switched off.")
        changes: dict[str, Any] = {}
        if enabled is not None:
            changes["enabled"] = enabled
        if params is not None:
            allowed = set(RULES_BY_ID[rule_id].default_params)
            unknown = set(params) - allowed
            if unknown or not allowed:
                raise rule("UNKNOWN_PARAMETER", f"{row['name']} has no setting called {', '.join(sorted(unknown)) or 'that'}.")
            for key, value in params.items():
                if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1000):
                    raise rule("INVALID_PARAMETER", f"{key} must be a whole number from 0 to 1000, or empty.")
            changes["params"] = {**(row.get("params") or {}), **params}
        if not changes:
            return self.rule_view(row)
        updated = await self._db["collision_rules"].find_one_and_update({"_id": rule_id}, {"$set": changes, "$inc": {"version": 1}}, return_document=True)
        await self._audit.record_as(
            user, action="rule.update", domain=AuditDomain.SYSTEM, entity_type="COLLISION_RULE", entity_id=rule_id,
            before={key: row.get(key) for key in changes}, after=changes,
        )
        return self.rule_view(updated)

    # ---- evaluating ---------------------------------------------------------------------------------

    def reader(self) -> LiveStateReader:
        return LiveStateReader(self._db)

    def build_action(self, user: AuthUser | None, action_type: ActionType, raw_payload: dict[str, Any], expected_state_token: str | None) -> ProposedAction:
        return ProposedAction(
            type=action_type,
            actor_id=user.id if user else "system",
            actor_role=user.role_key if user else "SYSTEM",
            payload=parse_payload(action_type, raw_payload),
            at=utcnow(),
            expected_state_token=expected_state_token,
        )

    async def evaluate(self, action: ProposedAction, reader: StateReader | None = None, *, with_alternatives: bool = True) -> CollisionResult:
        reader = reader or self.reader()
        config = await self.config()
        result = await self.engine.evaluate(action, reader, config)
        if with_alternatives:
            result.alternatives = await self.alternatives.suggest(action, result, self.reader(), config)
        return result

    async def summarise(self, action: ProposedAction) -> str:
        p, reader = action.payload, self.reader()
        match action.type:
            case ActionType.BOOK_ROOM | ActionType.MOVE_SESSION:
                verb = "Book" if action.type is ActionType.BOOK_ROOM else "Move a session to"
                return f"{verb} {p['room_id']}, {local_time(p['start_at'])} to {local_time(p['end_at'])}" + (f" for {p['purpose']}" if p["purpose"] else "")
            case ActionType.ASSIGN_TECHNICIAN:
                tech = await reader.technician(p["technician_id"])
                return f"Assign {p['work_order_id'] or 'a job'} to {tech['name'] if tech else p['technician_id']}"
            case ActionType.RESERVE_PARTS:
                lines = []
                for line in p["lines"]:
                    item = await reader.item(line["item_id"])
                    lines.append(f"{line['qty']} x {item['name'] if item else line['item_id']}")
                return f"Reserve {', '.join(lines)} for {p['work_order_id']}"
            case ActionType.DECIDE_APPROVAL:
                return f"{'Approve' if p['decision'] == 'APPROVE' else 'Reject'} {p['approval_id']}"
            case ActionType.VALIDATE_RECEIPT:
                return f"Verify goods receipt {p['receipt_id']}"
            case ActionType.RESOLVE_INCIDENT:
                return f"Resolve {p['incident_id']}"
        return action.type.value

    async def _record(self, user: AuthUser | None, action: ProposedAction, result: CollisionResult, stage: Stage, override: dict[str, Any] | None = None) -> dict[str, Any]:
        document = {
            "_id": await next_id(self._db, "CC", 5100),
            "actionType": action.type.value,
            "summary": await self.summarise(action),
            "proposedAction": jsonable(action.payload),
            "fingerprint": fingerprint(action.type, jsonable(action.payload)),
            "actorId": action.actor_id,
            "actorName": user.name if user else "System",
            "actorRole": action.actor_role,
            "stage": stage.value,
            "stateToken": result.state_token,
            "decision": result.decision.value,
            "findings": [finding.to_dict() for finding in result.findings],
            "alternatives": result.alternatives,
            "override": override,
            "campusId": self._campus_id,
            "createdAt": action.at,
        }
        await self._db["collision_checks"].insert_one(document)
        return document

    def _view(self, action: ProposedAction, result: CollisionResult, check_id: str | None) -> dict[str, Any]:
        return {
            "checkId": check_id,
            "actionType": action.type.value,
            "fingerprint": fingerprint(action.type, jsonable(action.payload)),
            **result.to_dict(),
            "requiresReason": bool(result.soft_codes),
            "requiresApproval": result.needs_approval,
            "canProceed": result.decision is Decision.ALLOW,
        }

    async def check(self, user: AuthUser, action_type: ActionType, raw_payload: dict[str, Any], expected_state_token: str | None = None) -> dict[str, Any]:
        """A preview. It explains and records, and changes nothing else."""
        action = self.build_action(user, action_type, raw_payload, expected_state_token)
        result = await self.evaluate(action)
        stored = await self._record(user, action, result, Stage.PREVIEW) if result.decision is not Decision.ALLOW else None
        return self._view(action, result, stored["_id"] if stored else None)

    async def _approval_covers(self, reader: StateReader, action: ProposedAction, acknowledgement: Acknowledgement | None) -> bool:
        if acknowledgement is None or not acknowledgement.override_approval_id:
            return False
        approval = await reader.approval(acknowledgement.override_approval_id)
        if approval is None or approval.get("status") != "APPROVED" or approval.get("type") != "OVERRIDE":
            return False
        if approval.get("requesterId") != action.actor_id:
            return False
        return (approval.get("subject") or {}).get("actionFingerprint") == fingerprint(action.type, jsonable(action.payload))

    async def enforce(
        self,
        user: AuthUser | None,
        action_type: ActionType,
        raw_payload: dict[str, Any],
        *,
        acknowledgement: Acknowledgement | None = None,
        expected_state_token: str | None = None,
    ) -> dict[str, Any]:
        """The commit-time check. Returns the stored check when the action may proceed, otherwise raises.

        Hard findings stop it whatever the caller supplies. Soft findings need a reason that names them.
        Approval findings need an approved override bound to exactly this action.
        """
        action = self.build_action(user, action_type, raw_payload, expected_state_token)
        reader = self.reader()
        result = await self.evaluate(action, reader)
        covered = await self._approval_covers(reader, action, acknowledgement)
        decision = gate(result, acknowledgement, covered)
        if not decision.allowed:
            stored = await self._record(user, action, result, Stage.COMMIT)
            stale = any(finding.code == "STALE_STATE" for finding in result.findings)
            status, code = (409, "STALE_STATE") if stale and decision.code == "COLLISION_BLOCKED" else (decision.status, decision.code or "COLLISION_BLOCKED")
            raise ApiException(status, code, decision.message or "This action is not allowed.", {**self._view(action, result, stored["_id"]), "requiresReason": decision.requires_reason})
        override = None
        if result.decision is not Decision.ALLOW and acknowledgement is not None:
            override = {
                "by": user.name if user else "System", "reason": acknowledgement.reason.strip(), "codes": sorted(result.soft_codes),
                "approvalId": acknowledgement.override_approval_id if result.needs_approval else None,
            }
        stored = await self._record(user, action, result, Stage.COMMIT, override)
        if override is not None:
            await self._audit.record(
                actor_id=action.actor_id, actor_role=action.actor_role, action="collision.override", domain=AuditDomain.OPERATIONS, entity_type="COLLISION_CHECK",
                entity_id=stored["_id"], after={"actionType": action.type.value, "codes": [finding.code for finding in result.findings if finding.severity is not Severity.HARD], **override},
                reason=override["reason"],
            )
        return {**self._view(action, result, stored["_id"]), "canProceed": True, "override": override}

    # ---- the review list ---------------------------------------------------------------------------------

    async def records(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self._db["collision_checks"].find({}).sort([("createdAt", -1), ("_id", -1)]).to_list(length=limit)
        return [
            {
                "id": row["_id"], "at": ensure_utc(row["createdAt"]).isoformat(), "actionType": row["actionType"], "summary": row["summary"], "actor": row["actorName"],
                "stage": row["stage"], "decision": row["decision"], "findings": [{key: finding[key] for key in ("code", "severity", "message", "affected")} for finding in row["findings"]],
                "override": {"by": row["override"]["by"], "reason": row["override"]["reason"]} if row.get("override") else None,
            }
            for row in rows
        ]


def merge_acknowledgement(reason: str | None, codes: list[str] | None, approval_id: str | None) -> Acknowledgement | None:
    if not (reason or codes or approval_id):
        return None
    return Acknowledgement(reason=reason or "", codes=tuple(codes or ()), override_approval_id=approval_id)
