"""The simulated mailbox (PS constraint C5).

A message arrives, is read, and either becomes a report or gets a question back. The same message
arriving twice is recognised and ignored, and a reply continues the original thread.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.audit.service import AuditDomain, AuditService
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import not_found, rule
from app.core.ids import next_id
from app.incidents.service import IncidentService
from app.ml.service import MlService
from app.sla.service import SlaService

DEDUPE_WINDOW_MINUTES = 15
INSTRUCTION_PATTERNS = (
    re.compile(r"ignore (all |any |your |the )?(previous|prior|above|earlier)? ?(instructions|rules|prompt)", re.IGNORECASE),
    re.compile(r"(mark|set|make) .{0,40}\b(p1|priority|critical|urgent)\b", re.IGNORECASE),
    re.compile(r"(close|delete|approve|cancel) (all|every)\b", re.IGNORECASE),
    re.compile(r"you are now|system prompt|act as", re.IGNORECASE),
)


def looks_like_instructions(text: str) -> bool:
    return any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS)


class InboxService:
    def __init__(self, db: Any, ml: MlService, incidents: IncidentService, audit: AuditService, sla: SlaService) -> None:
        self._db = db
        self._sla = sla
        self._ml = ml
        self._incidents = incidents
        self._audit = audit

    @staticmethod
    def _message_id(sender: str, subject: str, body: str, message_id: str | None) -> str:
        if message_id:
            return message_id
        bucket = int(utcnow().timestamp() // (DEDUPE_WINDOW_MINUTES * 60))
        return "auto-" + hashlib.sha256(f"{sender}|{subject}|{body}|{bucket}".encode()).hexdigest()[:24]

    def view(self, email: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": email["_id"],
            "from": email["from"],
            "subject": email["subject"],
            "body": email["body"],
            "receivedAt": ensure_utc(email["receivedAt"]).isoformat(),
            "status": email["status"],
            "extraction": email.get("extraction"),
            "incidentId": email.get("incidentId"),
            "note": email.get("note"),
        }

    async def list(self) -> list[dict[str, Any]]:
        rows = await self._db["inbound_emails"].find({}).sort("receivedAt", -1).to_list(length=200)
        return [self.view(row) for row in rows]

    async def receive(self, sender: str, subject: str, body: str, *, message_id: str | None = None, in_reply_to: str | None = None) -> tuple[dict[str, Any], bool]:
        """Stores a message. Returns it, and whether it was a repeat delivery that was ignored."""
        message_id = self._message_id(sender, subject, body, message_id)
        extraction = await self._ml.extract(f"{subject}. {body}")
        suspicious = looks_like_instructions(f"{subject} {body}")
        email = {
            "_id": await next_id(self._db, "EML", 7100),
            "messageId": message_id,
            "from": sender,
            "subject": subject,
            "body": body,
            "receivedAt": utcnow(),
            "status": "PENDING",
            "inReplyTo": in_reply_to,
            "extraction": {
                "category": extraction["category"],
                "location": extraction["location"]["text"] or "Unclear",
                "urgency": extraction["urgency"],
                "asset": extraction["asset"],
                "confidence": extraction["categoryConfidence"],
            },
            "incidentId": None,
            "note": "The message contained instructions. They were ignored. Only the problem itself was read, and priority is set by policy, not by the message." if suspicious else None,
            "suspicious": suspicious,
            "deliveries": 1,
        }
        try:
            await self._db["inbound_emails"].insert_one(email)
        except DuplicateKeyError:
            existing = await self._db["inbound_emails"].find_one_and_update(
                {"messageId": message_id},
                {"$inc": {"deliveries": 1}, "$set": {"note": "The same message arrived more than once. The extra copies were recognised and ignored."}},
                return_document=True,
            )
            return existing, True  # type: ignore[return-value]
        return email, False

    async def process(self, user: AuthUser, email_id: str) -> dict[str, Any]:
        email = await self._db["inbound_emails"].find_one({"_id": email_id})
        if email is None:
            raise not_found("Email")
        if email["status"] != "PENDING":
            return self.view(email)
        # claim it, so two clicks or two workers cannot turn one email into two reports
        claimed = await self._db["inbound_emails"].find_one_and_update({"_id": email_id, "status": "PENDING"}, {"$set": {"status": "PROCESSING"}})
        if claimed is None:
            return self.view(await self._db["inbound_emails"].find_one({"_id": email_id}))  # type: ignore[arg-type]
        try:
            await self._convert(user, email)
        except Exception:
            await self._db["inbound_emails"].update_one({"_id": email_id}, {"$set": {"status": "PENDING"}})
            raise
        return self.view(await self._db["inbound_emails"].find_one({"_id": email_id}))  # type: ignore[arg-type]

    async def _convert(self, user: AuthUser, email: dict[str, Any]) -> None:
        sender = await self._db["users"].find_one({"email": email["from"].lower()})
        reporter_id = sender["_id"] if sender else f"email:{email['from'].lower()}"
        reporter_name = sender["name"] if sender else email["from"]
        parent = await self._db["inbound_emails"].find_one({"_id": email["inReplyTo"]}) if email.get("inReplyTo") else None
        text = f"{email['subject']}. {email['body']}"

        if parent and parent["status"] == "CLARIFICATION_SENT" and parent.get("incidentId"):
            await self._continue_thread(email, parent)
            return

        extraction = await self._incidents.extract(user, text)
        unplaced = extraction["clarification"] is not None and not extraction.get("buildingId")
        report = await self._incidents.submit(
            reporter_id, reporter_name, text, extraction, "EMAIL", allow_unplaced=True, actor_role="EMAIL",
        )
        note = email.get("note")
        if unplaced:
            await self._ask_again(email, email, extraction["clarification"])
            status, note = "CLARIFICATION_SENT", "The place was too vague, so a question was sent instead of guessing."
        else:
            status = "CONVERTED"
            if report["joinedExisting"]:
                note = note or f"Matched {report['incidentId']}, so it was linked instead of creating a duplicate."
        await self._db["inbound_emails"].update_one(
            {"_id": email["_id"]}, {"$set": {"status": status, "incidentId": report["incidentId"], "note": note, "reportId": report["id"]}}
        )
        await self._audit.record_as(user, action="inbox.process", domain=AuditDomain.OPERATIONS, entity_type="EMAIL", entity_id=email["_id"], after={"status": status, "incidentId": report["incidentId"]})

    async def _ask_again(self, email: dict[str, Any], parent: dict[str, Any], question: str) -> None:
        await self._db["outbound_emails"].insert_one(
            {"_id": await next_id(self._db, "OUT", 1), "to": email["from"], "subject": f"Re: {email['subject']}", "body": question, "inReplyTo": email["_id"], "sentAt": utcnow()}
        )

    async def _continue_thread(self, email: dict[str, Any], parent: dict[str, Any]) -> None:
        """A reply to a question: add its words to the original report and finish placing the incident."""
        report = await self._db["reports"].find_one({"_id": parent.get("reportId")})
        if report is None:
            raise rule("THREAD_BROKEN", "The original report for this reply could not be found.")
        combined = f"{report['originalText']} {email['subject']}. {email['body']}"
        incident = await self._incidents.complete_placement(parent["incidentId"], combined, report["reporterId"])
        if incident is None:
            await self._ask_again(email, parent, (await self._ml.extract(combined))["clarification"] or "Which building or room is this in?")
            await self._db["inbound_emails"].update_one(
                {"_id": email["_id"]},
                {"$set": {"status": "CLARIFICATION_SENT", "incidentId": parent["incidentId"], "reportId": parent["reportId"], "note": "Still no place. The question was sent again."}},
            )
            return
        await self._db["reports"].update_one({"_id": report["_id"]}, {"$set": {"originalText": combined}})
        await self._db["inbound_emails"].update_one(
            {"_id": email["_id"]}, {"$set": {"status": "CONVERTED", "incidentId": incident["_id"], "reportId": parent["reportId"], "note": "A reply with the missing place. The original report was completed."}}
        )
        await self._db["inbound_emails"].update_one({"_id": parent["_id"]}, {"$set": {"status": "CONVERTED", "incidentId": incident["_id"], "note": "The reporter answered the question, and the report was completed."}})
