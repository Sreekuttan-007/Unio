from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.authuser import AuthUser
from app.core.errors import unauthenticated

# auto_error is off so a missing token returns our own error shape rather than the framework default.
bearer_scheme = HTTPBearer(auto_error=False, description="Sign in at /api/v1/auth/login")


@dataclass(frozen=True)
class ParsedToken:
    user_id: str
    token_id: str
    expires_at: datetime


class Identity(Protocol):
    """Implemented in app.users.service. The core never imports the users package."""

    async def verify_token(self, token: str) -> ParsedToken | None: ...

    async def authenticate(self, token: str) -> AuthUser | None: ...


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUser:
    if credentials is None or not credentials.credentials:
        raise unauthenticated()
    identity: Identity = request.app.state.identity
    user = await identity.authenticate(credentials.credentials)
    if user is None:
        raise unauthenticated()
    return user
