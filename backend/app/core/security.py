import asyncio
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import ApiException
from app.core.identity import ParsedToken


class PasswordService:
    """Argon2id hashing. Runs in a worker thread so it never blocks the event loop."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash_sync(self, password: str) -> str:
        return self._hasher.hash(password)

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        def check() -> bool:
            try:
                return self._hasher.verify(password_hash, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

        return await asyncio.to_thread(check)


class IssuedToken:
    def __init__(self, token: str, expires_at: datetime) -> None:
        self.token = token
        self.expires_at = expires_at


class JwtService:
    ALGORITHM = "HS256"

    def __init__(self, secret: str, ttl_minutes: int) -> None:
        self._secret = secret
        self._ttl = timedelta(minutes=ttl_minutes)

    def issue(self, user_id: str) -> IssuedToken:
        now = datetime.now(UTC)
        expires_at = now + self._ttl
        payload = {"sub": user_id, "jti": uuid.uuid4().hex, "iat": now, "exp": expires_at}
        return IssuedToken(jwt.encode(payload, self._secret, algorithm=self.ALGORITHM), expires_at)

    def parse(self, token: str) -> ParsedToken | None:
        """None for anything malformed, expired or forged. HS256 is the only accepted algorithm."""
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=[self.ALGORITHM], options={"require": ["exp", "sub", "jti"]}
            )
        except jwt.PyJWTError:
            return None
        return ParsedToken(
            user_id=str(claims["sub"]),
            token_id=str(claims["jti"]),
            expires_at=datetime.fromtimestamp(claims["exp"], UTC),
        )


class LoginRateLimiter:
    """In-memory, which is enough for the single backend instance we deploy."""

    def __init__(self, max_failures: int, window_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _prune(self, attempts: deque[float]) -> None:
        cutoff = self._clock() - self._window
        while attempts and attempts[0] < cutoff:
            attempts.popleft()

    def assert_allowed(self, key: str) -> None:
        attempts = self._failures.get(key)
        if attempts is None:
            return
        self._prune(attempts)
        if len(attempts) >= self._max:
            raise ApiException(429, "TOO_MANY_ATTEMPTS", "Too many failed sign-ins. Try again later.")

    def record_failure(self, key: str) -> None:
        attempts = self._failures.setdefault(key, deque())
        self._prune(attempts)
        attempts.append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
