"""The part of a request body that says "I know about the warnings" or "an approved override covers this"."""

from typing import Any

from pydantic import Field

from app.collision.service import merge_acknowledgement
from app.core.schema import ApiModel


class Acknowledging(ApiModel):
    """What a person sends to go ahead despite a warning, or with an approved override."""

    expected_state_token: str | None = Field(default=None, max_length=64)
    acknowledged_codes: list[str] = Field(default_factory=list, max_length=20)
    override_reason: str | None = Field(default=None, max_length=500)
    override_approval_id: str | None = Field(default=None, max_length=40)

    def acknowledgement(self) -> Any:
        return merge_acknowledgement(self.override_reason, self.acknowledged_codes, self.override_approval_id)
