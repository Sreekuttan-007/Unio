import hashlib
from typing import Any

from pymongo.errors import DuplicateKeyError
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.clock import utcnow
from app.core.errors import respond

HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotent-Replay"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_KEY_LENGTH = 128
COLLECTION = "idempotency_keys"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


async def _read_body(receive: Receive) -> bytes | None:
    """The whole request body, or None if the client went away."""
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            return b"".join(chunks)


def _replay_receive(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


class IdempotencyMiddleware:
    """Makes a retried write return its first result (C4).

    The key is claimed with an insert, so concurrent duplicates cannot both run. Only
    successes are kept: a failed request changed nothing, so a retry should run the checks again.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        raw_key = headers.get(HEADER.lower().encode())
        if raw_key is None:
            await self.app(scope, receive, send)
            return
        key = raw_key.decode("latin-1")
        if not key.strip() or len(key) > MAX_KEY_LENGTH:
            await respond(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must be 1-128 characters.")(
                scope, receive, send
            )
            return
        body = await _read_body(receive)
        if body is None:
            return
        replay = _replay_receive(body, receive)
        user_id = await self._user_id(scope, headers)
        if user_id is None:
            await self.app(scope, replay, send)  # not signed in: the route answers 401
            return
        claim_id = _sha256(f"{user_id}|{scope['method']}|{scope['path']}|{key}".encode())
        request_hash = _sha256(body)
        collection = scope["app"].state.db[COLLECTION]
        try:
            await collection.insert_one(
                {"_id": claim_id, "requestHash": request_hash, "status": "IN_PROGRESS", "createdAt": utcnow()}
            )
        except DuplicateKeyError:
            await self._answer_repeat(collection, claim_id, request_hash, scope, receive, send)
            return
        await self._run_and_record(collection, claim_id, request_hash, scope, replay, send)

    async def _user_id(self, scope: Scope, headers: dict[bytes, bytes]) -> str | None:
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if not authorization.lower().startswith("bearer "):
            return None
        parsed = await scope["app"].state.identity.verify_token(authorization[7:].strip())
        return parsed.user_id if parsed else None

    async def _run_and_record(
        self, collection: Any, claim_id: str, request_hash: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        captured: list[Message] = []

        async def capture(message: Message) -> None:
            captured.append(message)

        completed = False
        try:
            await self.app(scope, receive, capture)
            start = next((m for m in captured if m["type"] == "http.response.start"), None)
            status = start["status"] if start else 500
            if start and 200 <= status < 300:
                content_type = next(
                    (v.decode("latin-1") for k, v in start.get("headers", []) if k.lower() == b"content-type"), None
                )
                response_body = b"".join(m.get("body", b"") for m in captured if m["type"] == "http.response.body")
                await collection.replace_one(
                    {"_id": claim_id},
                    {
                        "_id": claim_id,
                        "requestHash": request_hash,
                        "status": "COMPLETED",
                        "responseStatus": status,
                        "responseContentType": content_type,
                        "responseBody": response_body.decode("utf-8", errors="replace"),
                        "createdAt": utcnow(),
                    },
                )
                completed = True
        finally:
            if not completed:
                await collection.delete_one({"_id": claim_id})
        for message in captured:
            await send(message)

    async def _answer_repeat(
        self, collection: Any, claim_id: str, request_hash: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        existing = await collection.find_one({"_id": claim_id})
        if existing is None or existing["status"] == "IN_PROGRESS":
            response: Response = respond(409, "REQUEST_IN_PROGRESS", "This request is already being processed.")
        elif existing["requestHash"] != request_hash:
            response = respond(409, "IDEMPOTENCY_KEY_REUSED", "This key was already used for a different request.")
        else:
            response = Response(
                content=existing["responseBody"],
                status_code=existing["responseStatus"],
                media_type=existing.get("responseContentType"),
                headers={REPLAY_HEADER: "true"},
            )
        await response(scope, receive, send)
