import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Correlation-Id"
_SAFE_ID = re.compile(r"[A-Za-z0-9-]{8,64}")

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdMiddleware:
    """Gives every request an id, echoes it back, and exposes it to logs and audit entries."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"x-correlation-id"), None)
        cid = incoming if incoming and _SAFE_ID.fullmatch(incoming) else str(uuid.uuid4())
        token = correlation_id.set(cid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = cid
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            correlation_id.reset(token)
