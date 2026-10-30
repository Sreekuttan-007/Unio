"""What each kind of action must say about itself. Validated before any rule runs."""

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.collision.models import ActionType
from app.core.clock import ensure_utc
from app.core.errors import rule
from app.core.schema import ApiModel


class _Window(ApiModel):
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _ordered(self) -> "_Window":
        if self.end_at <= self.start_at:
            raise ValueError("The end must be after the start.")
        return self


class BookRoom(_Window):
    room_id: str = Field(min_length=2, max_length=20)
    headcount: int = Field(ge=0, le=2000)
    kind: str = Field(default="LECTURE", pattern="^(LECTURE|PRACTICAL|EXAM|EVENT)$")
    required_features: list[str] = Field(default_factory=list, max_length=10)
    exclude_session_id: str | None = Field(default=None, max_length=60)
    exclude_booking_id: str | None = Field(default=None, max_length=40)
    purpose: str = Field(default="", max_length=200)


class SkillNeed(ApiModel):
    code: str = Field(min_length=2, max_length=30)
    min_level: int = Field(default=1, ge=1, le=5)


class AssignTechnician(_Window):
    technician_id: str = Field(min_length=2, max_length=20)
    work_order_id: str | None = Field(default=None, max_length=40)
    required_skills: list[SkillNeed] = Field(default_factory=list, max_length=6)


class PartLine(ApiModel):
    item_id: str = Field(min_length=2, max_length=60)
    qty: int = Field(ge=1, le=10000)
    location_id: str | None = Field(default=None, max_length=30)


class ReserveParts(ApiModel):
    work_order_id: str = Field(min_length=2, max_length=40)
    lines: list[PartLine] = Field(min_length=1, max_length=30)


class DecideApproval(ApiModel):
    approval_id: str = Field(min_length=2, max_length=40)
    requester_id: str = Field(min_length=2, max_length=40)
    amount_paise: int = Field(ge=0, le=10**12)
    decision: str = Field(default="APPROVE", pattern="^(APPROVE|REJECT)$")


class ValidateReceipt(ApiModel):
    receipt_id: str = Field(min_length=2, max_length=40)
    requester_id: str | None = Field(default=None, max_length=40)
    received_by: str | None = Field(default=None, max_length=40)


class ResolveIncident(ApiModel):
    incident_id: str = Field(min_length=2, max_length=40)


PAYLOADS: dict[ActionType, type[ApiModel]] = {
    ActionType.BOOK_ROOM: BookRoom,
    ActionType.MOVE_SESSION: BookRoom,
    ActionType.ASSIGN_TECHNICIAN: AssignTechnician,
    ActionType.RESERVE_PARTS: ReserveParts,
    ActionType.DECIDE_APPROVAL: DecideApproval,
    ActionType.VALIDATE_RECEIPT: ValidateReceipt,
    ActionType.RESOLVE_INCIDENT: ResolveIncident,
}


def parse_payload(action_type: ActionType, raw: dict[str, Any]) -> dict[str, Any]:
    """Returns a snake_case dict with real datetimes, or a 422 that says what is wrong."""
    try:
        model = PAYLOADS[action_type].model_validate(raw)
    except ValueError as error:
        first = error.errors()[0] if hasattr(error, "errors") else {}  # type: ignore[attr-defined]
        where = ".".join(str(part) for part in first.get("loc", ())) or "payload"
        raise rule("INVALID_ACTION", f"The {action_type.value.lower().replace('_', ' ')} request is not valid ({where}: {first.get('msg', 'invalid')}).") from error
    return model.model_dump()


def jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    """The same payload with datetimes as ISO text, for storing and for fingerprints."""

    def convert(value: Any) -> Any:
        if isinstance(value, datetime):
            return ensure_utc(value).isoformat()
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [convert(item) for item in value]
        return value

    return convert(payload)  # type: ignore[no-any-return]
