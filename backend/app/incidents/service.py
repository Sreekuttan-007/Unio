from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any

from app.audit.service import AuditDomain, AuditService
from app.collision.models import ActionType
from app.collision.service import CollisionService
from app.core.authuser import AuthUser
from app.core.clock import ensure_utc, utcnow
from app.core.errors import conflict, not_found, rule
from app.core.ids import next_id
from app.core.outbox import OutboxService
from app.core.permission import Permission as P
from app.core.scope import EntityType, scope_filter
from app.core.state import try_guarded_update
from app.incidents.policy import priority_for
from app.incidents.state import CLOSED_STATUSES, INCIDENT_MACHINE, OPEN_STATUSES, IncidentEvent, IncidentStatus
from app.ml import similarity
from app.ml.service import MlService
from app.sla.service import SlaService

CATEGORIES = ("ELECTRICAL", "NETWORK", "PLUMBING", "HVAC", "CARPENTRY", "EQUIPMENT", "HOUSEKEEPING", "SAFETY", "OTHER")
URGENCIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
JOIN_WINDOW = timedelta(hours=48)

# Faults that can spread across a building, so a new report is probably the same outage.
AREA_WIDE = frozenset({"NETWORK", "ELECTRICAL"})
SIMILAR_ENOUGH = 0.6  # two reports that read this alike are the same fault
RELATED_ENOUGH = 0.12  # for an area-wide fault, even a loose match joins an incident that already has company
OUTAGE_ENOUGH = 0.2  # an area-wide fault joins a lone report when they plainly describe the same outage
OPEN = [status.value for status in OPEN_STATUSES]
log = logging.getLogger("unio.incidents")
DONE_WORK = ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED")


def public_event(event_id: str, title: str, tone: str, detail: str | None = None, *, public: bool = True) -> dict[str, Any]:
    return {"id": event_id, "title": title, "detail": detail, "at": utcnow(), "tone": tone, "public": public}


class IncidentService:
    def __init__(self, db: Any, ml: MlService, sla: SlaService, audit: AuditService, outbox: OutboxService, campus_id: str, collisions: CollisionService | None = None) -> None:
        self._db = db
        self._ml = ml
        self._sla = sla
        self._audit = audit
        self._outbox = outbox
        self._campus_id = campus_id
        self._collisions = collisions
        self.cascade: Any = None  # set by build_services: recomputes the impact of an incident when it changes

    # ---- reading ----------------------------------------------------------------------------

    async def _open_orders(self, incident_id: str) -> list[dict[str, Any]]:
        return await self._db["work_orders"].find({"incidentId": incident_id, "status": {"$nin": list(DONE_WORK)}}).sort("_id", 1).to_list(length=50)

    async def view(self, incident: dict[str, Any], user: AuthUser) -> dict[str, Any]:
        sla = await self._sla.view(incident["_id"])
        orders = await self._open_orders(incident["_id"])
        available, unavailable = await self._actions(incident, user, orders)
        return {
            "id": incident["_id"],
            "title": incident["title"],
            "category": incident["category"],
            "priority": incident["priority"],
            "status": incident["status"],
            "buildingId": incident.get("buildingId") or "",
            "buildingName": incident.get("buildingName") or "Unknown location",
            "regionId": incident.get("regionId") or "",
            "roomCodes": incident.get("roomCodes", []),
            "reportCount": incident["reportCount"],
            "channels": incident["channels"],
            "summary": incident["summary"],
            "impact": incident.get("impact") or {"rooms": 0, "sessions": 0, "exams": 0, "people": 0},
            "sla": sla,
            "assignedTo": incident.get("assignedTo"),
            "relatedIds": incident.get("relatedIds", []),
            "createdAt": ensure_utc(incident["createdAt"]).isoformat(),
            "updatedAt": ensure_utc(incident["updatedAt"]).isoformat(),
            "timeline": [{**{k: v for k, v in event.items() if k != "public" and v is not None}, "at": ensure_utc(event["at"]).isoformat()} for event in incident.get("timeline", [])],
            "availableActions": available,
            "unavailableActions": unavailable,
        }

    async def list(self, user: AuthUser, status: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"$and": [scope_filter(user, EntityType.INCIDENT)]}
        if status:
            query["$and"].append({"status": status})
        rows = await self._db["incidents"].find(query).sort("updatedAt", -1).to_list(length=300)
        return [await self.view(row, user) for row in rows]

    async def get(self, user: AuthUser, incident_id: str) -> dict[str, Any]:
        row = await self._db["incidents"].find_one({"$and": [{"_id": incident_id}, scope_filter(user, EntityType.INCIDENT)]})
        if row is None:
            raise not_found("Incident")
        return row

    async def _actions(self, incident: dict[str, Any], user: AuthUser, orders: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        available: list[dict[str, str]] = []
        unavailable: list[dict[str, str]] = []
        status = incident["status"]
        closed = status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
        if user.has(P.INCIDENT_TRIAGE):
            if closed:
                pass
            elif orders:
                unavailable.append({"key": "incident.createWorkOrder", "label": "Create work order", "reason": f"Work order {orders[0]['_id']} already covers this incident."})
            else:
                available.append({"key": "incident.createWorkOrder", "label": "Create work order"})
        if user.has(P.INCIDENT_LINK_DUPLICATE) and not closed:
            others = await self._db["incidents"].count_documents({"_id": {"$ne": incident["_id"]}, "category": incident["category"], "status": {"$in": OPEN}})
            if others:
                available.append({"key": "incident.link", "label": "Link as duplicate"})
            else:
                unavailable.append({"key": "incident.link", "label": "Link as duplicate", "reason": "There is no other open incident of this type to link to."})
        if user.has(P.INCIDENT_TRANSITION):
            if status == IncidentStatus.RESOLVED:
                available.append({"key": "incident.close", "label": "Close"})
            elif not closed:
                reason = await self._resolve_blocker(incident, orders)
                if reason:
                    unavailable.append({"key": "incident.resolve", "label": "Mark resolved", "reason": reason})
                else:
                    available.append({"key": "incident.resolve", "label": "Mark resolved"})
        return available, unavailable

    async def _resolve_blocker(self, incident: dict[str, Any], orders: list[dict[str, Any]]) -> str | None:
        if orders:
            blocked = next((order for order in orders if order["status"] == "BLOCKED"), orders[0])
            state = "blocked and not yet completed" if blocked["status"] == "BLOCKED" else "not yet completed"
            return f"Work order {blocked['_id']} is {state}."
        if self._collisions is not None:
            action = self._collisions.build_action(None, ActionType.RESOLVE_INCIDENT, {"incidentId": incident["_id"]}, None)
            verdict = await self._collisions.evaluate(action, with_alternatives=False)
            if verdict.findings:
                return verdict.findings[0].message
        return None

    # ---- intake -----------------------------------------------------------------------------

    async def extract(self, user: AuthUser, text: str) -> dict[str, Any]:
        extraction = await self._ml.extract(text)
        extraction["duplicate"] = await self._duplicate_hint(extraction, text)
        suggestion_id = await next_id(self._db, "AIS", 9000)
        await self._db["ai_suggestions"].insert_one(
            {
                "_id": suggestion_id,
                "kind": "TRIAGE",
                "subjectType": "DRAFT",
                "subjectId": user.id,
                "output": {key: extraction[key] for key in ("category", "urgency", "location", "asset", "clarification")},
                "confidence": extraction["categoryConfidence"],
                "modelVersion": extraction["modelVersion"],
                "source": extraction["source"],
                "decision": "PENDING",
                "createdAt": utcnow(),
            }
        )
        extraction["suggestionId"] = suggestion_id
        return extraction

    async def _link_target(self, extraction: dict[str, Any], text: str, exclude: str | None = None) -> tuple[dict[str, Any] | None, float]:
        """The open incident a new report should join, if any, with how alike it reads.

        With similarity scoring off, only the deterministic rules apply, so correlation still works.
        """
        building_id = extraction.get("buildingId")
        if not building_id:
            return None, 0.0
        scored = await self._ml.enabled("mlDuplicate")
        cutoff = utcnow() - JOIN_WINDOW
        rows = await self._db["incidents"].find({"category": extraction["category"], "buildingId": building_id, "status": {"$in": OPEN}, "_id": {"$ne": exclude}}).to_list(length=50)
        rows = [row for row in rows if ensure_utc(row["createdAt"]) >= cutoff]
        if not rows:
            return None, 0.0
        texts: list[tuple[str, str]] = []
        for row in rows:
            reports = await self._db["reports"].find({"incidentId": row["_id"]}).sort("createdAt", 1).to_list(length=6)
            texts.append((row["_id"], " ".join(report["originalText"] for report in reports) or row["title"]))
        scores = dict(similarity.rank(text, texts)) if scored else {}
        room = (extraction.get("location") or {}).get("roomCode")
        best: tuple[dict[str, Any], float] | None = None
        for row in rows:
            score = scores.get(row["_id"], 0.0)
            same_room = bool(room) and room in row.get("roomCodes", [])
            accompanied = row["reportCount"] >= 2 or len(row.get("roomCodes", [])) >= 2
            area_wide = extraction["category"] in AREA_WIDE
            if scored:
                joins = same_room or score >= SIMILAR_ENOUGH or (area_wide and score >= (RELATED_ENOUGH if accompanied else OUTAGE_ENOUGH))
            else:
                # Rules only: the same room, or an area-wide fault in the same building, inside the window.
                joins = same_room or area_wide
            if joins and (best is None or score + same_room > best[1]):
                best = (row, score + (1.0 if same_room else 0.0))
        return (best[0], best[1]) if best else (None, 0.0)

    async def _duplicate_hint(self, extraction: dict[str, Any], text: str) -> dict[str, Any] | None:
        target, _ = await self._link_target(extraction, text)
        return {"incidentId": target["_id"], "title": target["title"], "reportCount": target["reportCount"]} if target else None

    async def _reconcile(self, extraction: dict[str, Any], text: str) -> dict[str, Any]:
        """Takes the person's edits, but re-derives place and building on the server."""
        if extraction.get("category") not in CATEGORIES or extraction.get("urgency") not in URGENCIES:
            raise rule("INVALID_EXTRACTION", "Choose a valid issue type and urgency.")
        place_text = (extraction.get("location") or {}).get("text") or ""
        fresh = await self._ml.extract(f"{text} {place_text}")
        cleaned = {**extraction, "buildingId": fresh.get("buildingId"), "location": fresh["location"] if fresh.get("buildingId") else extraction.get("location", {})}
        cleaned["clarification"] = None if fresh.get("buildingId") else fresh["clarification"]
        return cleaned

    async def submit(
        self, reporter_id: str, reporter_name: str, text: str, extraction: dict[str, Any], channel: str, *, academic_impact: str | None = None,
        allow_unplaced: bool = False, actor_role: str = "STUDENT",
    ) -> dict[str, Any]:
        text = text.strip()
        if len(text) < 6:
            raise rule("TEXT_TOO_SHORT", "Describe the problem in a few words.")
        extraction = await self._reconcile(extraction, text)
        if not extraction.get("buildingId") and not allow_unplaced:
            raise rule("CLARIFICATION_NEEDED", extraction.get("clarification") or "Say which room or building this is in.")

        await self._record_decision(extraction, reporter_id)
        room_code = (extraction.get("location") or {}).get("roomCode")
        now = utcnow()
        report_id = await next_id(self._db, "R", 5600)
        target, score = await self._link_target(extraction, text)
        report = {
            "_id": report_id,
            "reporterId": reporter_id,
            "reporterName": reporter_name,
            "channel": channel,
            "originalText": text,
            "category": extraction["category"],
            "urgency": extraction["urgency"],
            "location": extraction.get("location"),
            "asset": extraction.get("asset"),
            "roomCodes": [room_code] if room_code else [],
            "academicImpact": academic_impact,
            "suggestionId": extraction.get("suggestionId"),
            "incidentId": None,
            "joinedExisting": target is not None,
            "linkScore": round(score, 3),
            "createdAt": now,
            "attachments": [],
        }
        if target is not None:
            incident = await self._join(target, report, extraction)
        else:
            incident = await self._create(report, extraction, allow_unplaced)
        report["incidentId"] = incident["_id"]
        await self._db["reports"].insert_one(report)
        await self._refresh_summary(incident["_id"])
        await self._audit.record(
            actor_id=reporter_id, actor_role=actor_role, action="report.submit", domain=AuditDomain.OPERATIONS, entity_type="REPORT", entity_id=report_id,
            after={"incidentId": incident["_id"], "joined": target is not None, "channel": channel},
        )
        return await self.report_view(report)

    async def _record_decision(self, extraction: dict[str, Any], reporter_id: str) -> None:
        suggestion_id = extraction.get("suggestionId")
        if not suggestion_id:
            return
        stored = await self._db["ai_suggestions"].find_one({"_id": suggestion_id})
        if stored is None:
            return
        suggested = stored["output"]
        changed = {key: extraction[key] for key in ("category", "urgency") if suggested.get(key) != extraction.get(key)}
        await self._db["ai_suggestions"].update_one(
            {"_id": suggestion_id},
            {"$set": {"decision": "CORRECTED" if changed else "ACCEPTED", "correction": changed or None, "decidedBy": reporter_id, "decidedAt": utcnow()}},
        )

    async def _create(self, report: dict[str, Any], extraction: dict[str, Any], unplaced: bool) -> dict[str, Any]:
        gaz = await self._ml.gazetteer()
        building = gaz.buildings.get(extraction.get("buildingId") or "")
        clarification = bool(extraction.get("clarification")) and unplaced
        priority = priority_for(extraction["category"], extraction["urgency"], 1)
        incident_id = await next_id(self._db, "INC", 1043)
        now = report["createdAt"]
        title = self._title(report, extraction, building)
        incident = {
            "_id": incident_id,
            "title": title,
            "category": extraction["category"],
            "priority": priority,
            "urgency": extraction["urgency"],
            "status": IncidentStatus.NEEDS_CLARIFICATION.value if clarification else IncidentStatus.ACKNOWLEDGED.value,
            "buildingId": building["_id"] if building else None,
            "buildingName": building["name"] if building else None,
            "regionId": building["mapRegionId"] if building else None,
            "departmentId": building.get("departmentId") if building else None,
            "campusId": self._campus_id,
            "roomCodes": list(report["roomCodes"]),
            "reportCount": 1,
            "channels": {"FORM": int(report["channel"] == "FORM"), "CHAT": int(report["channel"] == "CHAT"), "EMAIL": int(report["channel"] == "EMAIL")},
            "reporterIds": [report["reporterId"]],
            "assignedUserIds": [],
            "assignedTo": None,
            "relatedIds": [],
            "summary": {"text": "", "source": "TEMPLATE", "basedOnReportCount": 0},
            "impact": {"rooms": 0, "sessions": 0, "exams": 0, "people": 0},
            "timeline": [
                public_event("e1", "Report received", "neutral", report["originalText"][:140]),
                public_event("e2", "Needs a detail from you" if clarification else f"Acknowledged and prioritised {priority}", "info" if clarification else "accent", extraction.get("clarification") if clarification else None),
            ],
            "version": 0,
            "createdAt": now,
            "updatedAt": now,
        }
        await self._db["incidents"].insert_one(incident)
        await self._sla.start(
            subject_type="INCIDENT", subject_id=incident_id, label=f"{incident_id} {title}", category=incident["category"], priority=priority,
            owner_ids=[report["reporterId"]], assigned_user_id=None, department_id=incident["departmentId"], campus_id=self._campus_id,
            started_at=now, paused_reason="Waiting for the reporter to answer" if clarification else None,
        )
        await self._outbox.enqueue("incident.created", {"incidentId": incident_id, "priority": priority, "reporterIds": [report["reporterId"]], "buildingId": incident["buildingId"]})
        return incident

    @staticmethod
    def _title(report: dict[str, Any], extraction: dict[str, Any], building: dict[str, Any] | None) -> str:
        words = {"ELECTRICAL": "Electrical fault", "NETWORK": "Network problem", "PLUMBING": "Plumbing problem", "HVAC": "Air conditioning problem", "CARPENTRY": "Repair needed",
                 "EQUIPMENT": "Equipment problem", "HOUSEKEEPING": "Cleaning needed", "SAFETY": "Safety concern", "OTHER": "Request"}
        asset = extraction.get("asset")
        head = f"{asset} problem" if asset and extraction["category"] in ("EQUIPMENT", "HVAC", "CARPENTRY") else words.get(extraction["category"], "Problem")
        place = (extraction.get("location") or {}).get("roomCode") or (building["name"] if building else "an unknown location")
        return f"{head} in {place}"

    async def _join(self, target: dict[str, Any], report: dict[str, Any], extraction: dict[str, Any]) -> dict[str, Any]:
        count = target["reportCount"] + 1
        priority = priority_for(extraction["category"], extraction["urgency"], count, exams_affected=(target.get("impact") or {}).get("exams", 0), current=target["priority"])
        update: dict[str, Any] = {
            "$inc": {f"channels.{report['channel']}": 1, "reportCount": 1, "version": 1},
            "$addToSet": {"reporterIds": report["reporterId"], "roomCodes": {"$each": report["roomCodes"]}},
            "$set": {"updatedAt": report["createdAt"], "priority": priority},
        }
        milestone = count in (2, 3, 5, 10, 15, 20, 30, 50)
        if milestone:
            update["$push"] = {"timeline": public_event(f"j{count}", f"{count} reports now describe this incident", "info", "Reports are kept together, and every reporter stays on it.")}
        await self._db["incidents"].update_one({"_id": target["_id"]}, update)
        if priority != target["priority"]:
            await self._sla.reprioritise(target["_id"], target["category"], priority)
            await self._db["incidents"].update_one({"_id": target["_id"]}, {"$push": {"timeline": public_event(f"p{count}", f"Priority raised to {priority}", "warning", "Many people reported it.")}})
        await self._outbox.enqueue("incident.joined", {"incidentId": target["_id"], "reporterId": report["reporterId"], "reportCount": count})
        return await self._db["incidents"].find_one({"_id": target["_id"]})  # type: ignore[return-value]

    async def _refresh_summary(self, incident_id: str) -> None:
        incident = await self._db["incidents"].find_one({"_id": incident_id})
        if incident is None:
            return
        reports = await self._db["reports"].find({"incidentId": incident_id}).sort("createdAt", 1).to_list(length=500)
        summary = await self._ml.summarise(incident, reports)
        await self._db["incidents"].update_one({"_id": incident_id}, {"$set": {"summary": summary}})

    # ---- reports as the reporter sees them -------------------------------------------------

    async def report_view(self, report: dict[str, Any]) -> dict[str, Any]:
        incident = await self._db["incidents"].find_one({"_id": report["incidentId"]}) or {}
        created = ensure_utc(report["createdAt"])
        timeline = [{"id": "submitted", "title": "You reported this", "at": created.isoformat(), "tone": "neutral"}]
        if report.get("joinedExisting"):
            timeline.append({"id": "joined", "title": "This matched an incident that already existed", "detail": "Kept as one incident, and you stay on it", "at": created.isoformat(), "tone": "info"})
        for event in incident.get("timeline", []):
            if event.get("public") and ensure_utc(event["at"]) > created:
                timeline.append({"id": event["id"], "title": event["title"], **({"detail": event["detail"]} if event.get("detail") else {}), "at": ensure_utc(event["at"]).isoformat(), "tone": event.get("tone", "neutral")})
        count = incident.get("reportCount", 1)
        status = incident.get("status", "ACKNOWLEDGED")
        if report.get("joinedExisting") or count > 1:
            summary = f"{count} people have reported this, and you are one of them. They are handled as one incident, with one shared status."
        else:
            summary = "Your report was received and sent to triage."
        if status in ("RESOLVED", "CLOSED"):
            summary = "This is fixed. Tell us whether it really is."
        return {
            "id": report["_id"],
            "incidentId": report["incidentId"],
            "title": report["originalText"] if len(report["originalText"]) <= 70 else f"{report['originalText'][:67]}...",
            "status": status,
            "priority": incident.get("priority", "P3"),
            "channel": report["channel"],
            "submittedAt": created.isoformat(),
            "joinedExisting": bool(report.get("joinedExisting")),
            "incidentReportCount": count,
            "summary": summary,
            "timeline": timeline,
            "canGiveFeedback": status in ("RESOLVED", "CLOSED") and not report.get("feedback"),
        }

    async def my_reports(self, user: AuthUser) -> list[dict[str, Any]]:
        rows = await self._db["reports"].find({"reporterId": user.id}).sort("createdAt", -1).to_list(length=100)
        return [await self.report_view(row) for row in rows]

    async def feedback(self, user: AuthUser, report_id: str, fixed: bool) -> None:
        report = await self._db["reports"].find_one({"_id": report_id, "reporterId": user.id})
        if report is None:
            raise not_found("Report")
        await self._db["reports"].update_one({"_id": report_id}, {"$set": {"feedback": {"fixed": fixed, "at": utcnow()}}})
        if not fixed:
            await self._db["incidents"].update_one({"_id": report["incidentId"], "status": IncidentStatus.RESOLVED.value}, {"$push": {"timeline": public_event(f"f{report_id}", "A reporter says it is not fixed", "warning")}})

    # ---- moving an incident along -----------------------------------------------------------

    async def transition(self, user: AuthUser, incident_id: str, event_name: str) -> dict[str, Any]:
        incident = await self.get(user, incident_id)
        try:
            event = IncidentEvent(event_name)
        except ValueError:
            raise rule("UNKNOWN_EVENT", f"Unknown event {event_name}.") from None
        if event is IncidentEvent.RESOLVE:
            await self._check_resolvable(user, incident)
        return await self._apply(incident, event, user.id, user.role_key)

    async def _check_resolvable(self, user: AuthUser, incident: dict[str, Any]) -> None:
        """Open work stops a resolve, and so does an unresolved cause. The cause check is the collision engine's DEP-001."""
        orders = await self._open_orders(incident["_id"])
        if orders:
            raise rule("ILLEGAL_TRANSITION", await self._resolve_blocker(incident, orders) or "Work is still open.")
        if self._collisions is not None:
            await self._collisions.enforce(user, ActionType.RESOLVE_INCIDENT, {"incidentId": incident["_id"]})

    async def _apply(self, incident: dict[str, Any], event: IncidentEvent, actor_id: str, actor_role: str) -> dict[str, Any]:
        """One legal move of the state machine, as one compare-and-set, with its side effects."""
        incident_id = incident["_id"]
        current = IncidentStatus(incident["status"])
        target = INCIDENT_MACHINE.next(current, event)
        update: dict[str, Any] = {"$set": {"status": target.value}, "$push": {"timeline": public_event(f"t{incident['version'] + 1}", self._event_title(event), "success" if target in CLOSED_STATUSES else "accent", public=True)}}
        if event is IncidentEvent.RESOLVE:
            update["$set"]["resolvedAt"] = utcnow()
        if not await try_guarded_update(self._db["incidents"], incident_id, incident["version"], current, update):
            raise conflict("VERSION_CONFLICT", "This incident changed. Reload it and try again.")
        if event is IncidentEvent.RESOLVE:
            await self._sla.finish(incident_id)
        elif event is IncidentEvent.REOPEN:
            await self._sla.reopen(incident_id)
        elif event is IncidentEvent.CLARIFY:
            await self._sla.resume(incident_id)
        await self._audit.record(
            actor_id=actor_id, actor_role=actor_role, action=f"incident.{event.value.lower()}", domain=AuditDomain.OPERATIONS, entity_type="INCIDENT", entity_id=incident_id,
            before={"status": current.value}, after={"status": target.value},
        )
        await self._outbox.enqueue("incident.status", {"incidentId": incident_id, "status": target.value, "reporterIds": incident["reporterIds"]})
        await self.refresh_impact(incident_id)
        return await self._db["incidents"].find_one({"_id": incident_id})  # type: ignore[return-value]

    async def advance(self, incident_id: str, event: IncidentEvent, actor_id: str, actor_role: str) -> dict[str, Any] | None:
        """A move made by the system on behalf of someone else, such as work starting. A move that does not fit is skipped."""
        incident = await self._db["incidents"].find_one({"_id": incident_id})
        if incident is None or not INCIDENT_MACHINE.can(IncidentStatus(incident["status"]), event):
            return None
        return await self._apply(incident, event, actor_id, actor_role)

    async def note_assignment(self, incident_id: str, user_id: str | None, name: str | None, actor_id: str, actor_role: str) -> None:
        """Records who is on the job, so that person can see the incident, and moves it to ASSIGNED when it is ready."""
        await self._db["incidents"].update_one(
            {"_id": incident_id}, {"$set": {"assignedTo": name, "assignedUserIds": [user_id] if user_id else [], "updatedAt": utcnow()}, "$inc": {"version": 1}}
        )
        await self._sla.assign(incident_id, user_id)
        if user_id:
            await self.advance(incident_id, IncidentEvent.ASSIGN, actor_id, actor_role)

    async def note(self, incident_id: str, title: str, tone: str = "neutral", detail: str | None = None, *, public: bool = True) -> None:
        """Adds a line to the incident timeline. Public lines are what the people who reported it read."""
        await self._db["incidents"].update_one(
            {"_id": incident_id}, {"$push": {"timeline": public_event(f"n{secrets.token_hex(4)}", title, tone, detail, public=public)}, "$set": {"updatedAt": utcnow()}}
        )

    async def refresh_impact(self, incident_id: str) -> None:
        """Impact follows the incident's state. A failure here must never undo the change that triggered it."""
        if self.cascade is None:
            return
        try:
            await self.cascade.refresh(incident_id)
        except Exception:  # noqa: BLE001 - the impact view is derived data and can be recomputed on demand
            log.exception("Impact refresh failed for %s", incident_id)

    @staticmethod
    def _event_title(event: IncidentEvent) -> str:
        return {
            IncidentEvent.RESOLVE: "Marked resolved",
            IncidentEvent.CLOSE: "Closed",
            IncidentEvent.REOPEN: "Reopened",
            IncidentEvent.ASSIGN: "Assigned for repair",
            IncidentEvent.START: "Work started",
            IncidentEvent.ACKNOWLEDGE: "Acknowledged",
            IncidentEvent.REVIEW: "Under review",
            IncidentEvent.REQUEST_CLARIFICATION: "Waiting for more detail",
            IncidentEvent.CLARIFY: "Detail received",
        }[event]

    async def complete_placement(self, incident_id: str, text: str, reporter_id: str) -> dict[str, Any] | None:
        """A reporter answered "where?". Returns None while the place is still unknown.

        Once placed, the incident leaves NEEDS_CLARIFICATION through the state machine, its clock
        resumes, and it may turn out to be a duplicate of an incident that already exists.
        """
        incident = await self._db["incidents"].find_one({"_id": incident_id})
        if incident is None:
            raise not_found("Incident")
        if incident["status"] != IncidentStatus.NEEDS_CLARIFICATION.value:
            return incident
        extraction = await self._ml.extract(text)
        if not extraction.get("buildingId"):
            return None
        building = (await self._ml.gazetteer()).buildings[extraction["buildingId"]]
        room = extraction["location"]["roomCode"]
        update: dict[str, Any] = {
            "$set": {"buildingId": building["_id"], "buildingName": building["name"], "regionId": building["mapRegionId"], "departmentId": building.get("departmentId"), "status": IncidentStatus.ACKNOWLEDGED.value},
            "$push": {"timeline": public_event(f"c{incident['version'] + 1}", "Detail received", "accent", f"Location confirmed: {building['name']}")},
        }
        if room:
            update["$addToSet"] = {"roomCodes": room}
        if not await try_guarded_update(self._db["incidents"], incident_id, incident["version"], IncidentStatus.NEEDS_CLARIFICATION, update):
            raise conflict("VERSION_CONFLICT", "This incident changed. Reload it and try again.")
        await self._db["reports"].update_many({"incidentId": incident_id}, {"$set": {"location": extraction["location"]}})
        if room:
            await self._db["reports"].update_many({"incidentId": incident_id}, {"$addToSet": {"roomCodes": room}})
        await self._db["sla_instances"].update_one({"subjectId": incident_id}, {"$set": {"departmentId": building.get("departmentId")}})
        await self._sla.resume(incident_id)
        placed = await self._db["incidents"].find_one({"_id": incident_id})
        merged_into: str | None = None
        target, _ = await self._link_target({**extraction, "category": placed["category"]}, text, exclude=incident_id)
        if target is not None and target["_id"] != incident_id:
            await self._merge(placed, target["_id"])  # type: ignore[arg-type]
            merged_into = target["_id"]
        await self._audit.record(
            actor_id=reporter_id, actor_role="EMAIL", action="incident.clarified", domain=AuditDomain.OPERATIONS, entity_type="INCIDENT", entity_id=incident_id,
            after={"buildingId": building["_id"], "mergedInto": merged_into},
        )
        await self._refresh_summary(merged_into or incident_id)
        return await self._db["incidents"].find_one({"_id": merged_into or incident_id})

    async def link_duplicate(self, user: AuthUser, incident_id: str, target_id: str | None) -> str:
        """Merges one incident into another. Every report and reporter moves across and none is lost."""
        source = await self.get(user, incident_id)
        if target_id is None:
            candidates = await self._db["incidents"].find({"_id": {"$ne": incident_id}, "category": source["category"], "status": {"$in": OPEN}}).to_list(length=50)
            if not candidates:
                raise rule("NOTHING_TO_LINK", "There is no other open incident of this type to link to.")
            same_building = [item for item in candidates if item.get("buildingId") == source.get("buildingId")] or candidates
            target_id = max(same_building, key=lambda item: item["reportCount"])["_id"]
        if target_id == incident_id:
            raise rule("SELF_LINK", "An incident cannot be linked to itself.")
        message = await self._merge(source, target_id)
        await self._refresh_summary(target_id)
        await self._audit.record_as(user, action="incident.link", domain=AuditDomain.OPERATIONS, entity_type="INCIDENT", entity_id=incident_id, after={"linkedTo": target_id})
        return message

    async def _merge(self, source: dict[str, Any], target_id: str) -> str:
        incident_id = source["_id"]
        target = await self._db["incidents"].find_one({"_id": target_id})
        if target is None:
            raise not_found("Target incident")
        if target["status"] not in OPEN:
            raise rule("TARGET_CLOSED", f"{target_id} is already resolved, so nothing can be linked to it.")
        await self._db["reports"].update_many({"incidentId": incident_id}, {"$set": {"incidentId": target_id, "joinedExisting": True}})
        await self._db["incidents"].update_one(
            {"_id": target_id},
            {
                "$inc": {"reportCount": source["reportCount"], "channels.FORM": source["channels"]["FORM"], "channels.CHAT": source["channels"]["CHAT"], "channels.EMAIL": source["channels"]["EMAIL"], "version": 1},
                "$addToSet": {"reporterIds": {"$each": source["reporterIds"]}, "roomCodes": {"$each": source["roomCodes"]}},
                "$set": {"updatedAt": utcnow()},
                "$push": {"timeline": public_event(f"l{incident_id}", f"{incident_id} was linked to this incident", "info", f"{source['reportCount']} reports and their reporters moved here.")},
            },
        )
        await self._db["incidents"].update_one(
            {"_id": incident_id},
            {"$set": {"status": IncidentStatus.CLOSED.value, "duplicateOf": target_id, "updatedAt": utcnow()}, "$inc": {"version": 1}, "$push": {"timeline": public_event(f"d{target_id}", f"Linked to {target_id}", "neutral")}},
        )
        await self._sla.finish(incident_id)
        return f"{incident_id} was linked to {target_id}. Nobody who reported was lost: {source['reportCount']} reports moved across."

    async def notices(self) -> list[dict[str, Any]]:
        rows = await self._db["notices"].find({}).sort("at", -1).to_list(length=50)
        return [{"id": row["_id"], "title": row["title"], "body": row["body"], "severity": row["severity"], "audience": row["audience"], "at": ensure_utc(row["at"]).isoformat()} for row in rows]
