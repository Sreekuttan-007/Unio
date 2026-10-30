"""Uploaded files: completion photos and invoice documents.

The bytes live in their own collection so a list of file records stays small. Every file is checked
on the way in: size, type, and that the contents really are what the sender says they are.
"""

import base64
import binascii
import re
from typing import Any

from bson import Binary

from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import not_found, rule
from app.core.ids import next_id
from app.core.permission import Permission as P

MAX_BYTES = 6 * 1024 * 1024
SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
}
TEXT_TYPES = ("text/plain",)
PURPOSES = ("EVIDENCE", "INVOICE")


def decode_base64(content: str) -> bytes:
    try:
        return base64.b64decode(content.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError):
        raise rule("FILE_UNREADABLE", "That file could not be read. Try attaching it again.") from None


def check_content(mime: str, data: bytes) -> None:
    if not data:
        raise rule("FILE_EMPTY", "That file is empty.")
    if len(data) > MAX_BYTES:
        raise rule("FILE_TOO_LARGE", f"Files can be at most {MAX_BYTES // (1024 * 1024)} MB.")
    if mime in TEXT_TYPES:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise rule("FILE_TYPE_MISMATCH", "That file is not the type it says it is.") from None
        return
    signatures = SIGNATURES.get(mime)
    if signatures is None:
        raise rule("FILE_TYPE_NOT_ALLOWED", "Attach a photo (JPEG, PNG, WebP), a PDF, or a plain text file.")
    if not any(data.startswith(signature) for signature in signatures):
        raise rule("FILE_TYPE_MISMATCH", "That file is not the type it says it is.")


class FileStore:
    def __init__(self, db: Any) -> None:
        self._meta = db["file_objects"]
        self._blobs = db["file_blobs"]
        self._db = db

    async def save(self, *, owner: AuthUser, purpose: str, name: str, mime: str, data: bytes, entity: tuple[str, str] | None = None) -> dict[str, Any]:
        if purpose not in PURPOSES:
            raise ValueError(purpose)
        check_content(mime, data)
        file_id = await next_id(self._db, "FILE", 100)
        document = {
            "_id": file_id, "name": re.sub(r"[^A-Za-z0-9._ -]", "_", name.strip())[:120] or "file", "mime": mime, "sizeBytes": len(data), "purpose": purpose,
            "ownerId": owner.id, "ownerName": owner.name, "entityRef": {"type": entity[0], "id": entity[1]} if entity else None, "createdAt": utcnow(),
        }
        await self._meta.insert_one(document)
        await self._blobs.insert_one({"_id": file_id, "data": Binary(data)})
        return document

    async def attach(self, file_id: str, entity: tuple[str, str]) -> None:
        await self._meta.update_one({"_id": file_id}, {"$set": {"entityRef": {"type": entity[0], "id": entity[1]}}})

    @staticmethod
    def view(meta: dict[str, Any]) -> dict[str, Any]:
        return {"id": meta["_id"], "name": meta["name"], "mime": meta["mime"], "sizeBytes": meta["sizeBytes"], "createdAt": ensure_utc(meta["createdAt"]).isoformat()}

    async def meta(self, file_id: str) -> dict[str, Any] | None:
        return await self._meta.find_one({"_id": file_id})  # type: ignore[no-any-return]

    async def read(self, user: AuthUser, file_id: str) -> tuple[dict[str, Any], bytes]:
        meta = await self.meta(file_id)
        if meta is None or not self._may_read(user, meta):
            raise not_found("File")  # not 403: whether a file exists is not for everyone to know
        blob = await self._blobs.find_one({"_id": file_id})
        if blob is None:
            raise not_found("File")
        return meta, bytes(blob["data"])

    @staticmethod
    def _may_read(user: AuthUser, meta: dict[str, Any]) -> bool:
        if meta["ownerId"] == user.id:
            return True
        if meta["purpose"] == "INVOICE":
            return user.has(P.INVOICE_READ)
        return user.has_any((P.WORKORDER_READ_CAMPUS, P.WORKORDER_READ_DEPARTMENT, P.WORKORDER_VERIFY))
