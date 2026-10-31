import time
from typing import Any

from fastapi import Depends
from pydantic import Field

from app.audit.service import AuditDomain
from app.core.access import GuardedRouter, authenticated, require
from app.core.authuser import AuthUser
from app.core.errors import not_found
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["notifications", "sla", "analytics", "admin"])

SLA_READERS = (P.SLA_READ_OWN, P.SLA_READ_DEPARTMENT, P.SLA_READ_CAMPUS, P.SLA_READ_PROCUREMENT, P.SLA_READ_SYSTEM)
ANALYTICS_READERS = (P.ANALYTICS_READ_DEPARTMENT, P.ANALYTICS_READ_CAMPUS, P.ANALYTICS_READ_PROCUREMENT, P.ANALYTICS_READ_SYSTEM)


class FeatureBody(ApiModel):
    enabled: bool


class WebhookCreateBody(ApiModel):
    url: str = Field(min_length=8, max_length=500)
    events: list[str] = Field(min_length=1)


class WebhookUpdateBody(ApiModel):
    url: str | None = Field(default=None, min_length=8, max_length=500)
    events: list[str] | None = Field(default=None, min_length=1)
    enabled: bool | None = None


class ReadBody(ApiModel):
    id: str | None = Field(default=None, max_length=40)


# ---- notifications ------------------------------------------------------------------------------------------


@router.get("/notifications")
async def my_notifications(user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Any:
    return await services.notifications.list(user)


@router.post("/notifications/read")
async def mark_read(body: ReadBody | None = None, user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Any:
    """Marks one notification read, or all of them when no id is given."""
    return {"marked": await services.notifications.mark_read(user, body.id if body else None)}


# ---- SLA and analytics ------------------------------------------------------------------------------------------


@router.get("/sla/instances")
async def sla_instances(user: AuthUser = Depends(require(*SLA_READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.sla_board.rows(user)


@router.get("/sla/summary")
async def sla_summary(user: AuthUser = Depends(require(*SLA_READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.sla_board.summary(user)


@router.post("/sla/sweep")
async def sla_sweep(user: AuthUser = Depends(require(P.SLA_READ_CAMPUS, P.SLA_READ_SYSTEM)), services: Services = Depends(get_services)) -> Any:
    """Runs the escalation check now. It also runs on a timer; running it again never repeats an escalation."""
    fired = await services.sla_board.sweep()
    return {"fired": len(fired)}


@router.get("/analytics/overview")
async def analytics_overview(user: AuthUser = Depends(require(*ANALYTICS_READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.analytics.overview(user)


# ---- administration -------------------------------------------------------------------------------------------------


@router.get("/admin/sla-policies")
async def sla_policies(user: AuthUser = Depends(require(P.ADMIN_SLA_POLICY)), services: Services = Depends(get_services)) -> Any:
    rows = await services.db["sla_policies"].find({}).sort([("category", 1), ("priority", 1)]).to_list(length=200)
    return [
        {"id": row["_id"], "category": row["category"], "priority": row["priority"], "responseMinutes": row["responseMinutes"], "resolutionMinutes": row["resolutionMinutes"], "escalations": row.get("escalations", [])}
        for row in rows
    ]


@router.get("/admin/integrations")
async def integrations(user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    return await _integrations(services)


async def _integrations(services: Services) -> dict[str, Any]:
    last_email = await services.db["inbound_emails"].find_one({}, sort=[("receivedAt", -1)])
    return {
        "ai": {"provider": services.settings.llm_provider, "model": services.settings.gemini_model, "features": await services.ml.features()},
        "email": {
            "address": "helpdesk@unio.demo", "polling": "Simulated mailbox (Inbox screen)",
            "lastPoll": last_email["receivedAt"].isoformat() if last_email and last_email.get("receivedAt") else "", "processed": await services.db["inbound_emails"].count_documents({}),
        },
        "webhooks": await services.webhooks.views(),
        "channels": [{"key": "FORM", "label": "Report form", "enabled": True}, {"key": "CHAT", "label": "Chat", "enabled": True}, {"key": "EMAIL", "label": "Email", "enabled": True}],
    }


@router.patch("/admin/integrations/features/{key}")
async def set_feature(key: str, body: FeatureBody, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    try:
        await services.ml.set_feature(key, body.enabled)
    except KeyError:
        raise not_found("Feature") from None
    await services.audit.record_as(user, action="integration.feature", domain=AuditDomain.SYSTEM, entity_type="FEATURE", entity_id=key, after={"enabled": body.enabled})
    return await _integrations(services)


@router.get("/admin/webhooks")
async def list_webhooks(user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    return await services.webhooks.views()


@router.post("/admin/webhooks", status_code=201)
async def create_webhook(body: WebhookCreateBody, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    hook = await services.webhooks.create(body.url, body.events)
    await services.audit.record_as(user, action="webhook.create", domain=AuditDomain.SYSTEM, entity_type="WEBHOOK", entity_id=hook["id"], after={"url": body.url, "events": body.events})
    return hook


@router.patch("/admin/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, body: WebhookUpdateBody, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    hook = await services.webhooks.update(webhook_id, url=body.url, events=body.events, enabled=body.enabled)
    await services.audit.record_as(user, action="webhook.update", domain=AuditDomain.SYSTEM, entity_type="WEBHOOK", entity_id=webhook_id, after=body.model_dump(exclude_none=True))
    return hook


@router.get("/admin/webhooks/{webhook_id}/deliveries")
async def webhook_deliveries(webhook_id: str, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    return await services.webhooks.deliveries(webhook_id)


@router.post("/admin/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    return await services.webhooks.test(webhook_id)


@router.post("/admin/webhooks/{webhook_id}/deliveries/{event_id}/replay")
async def replay_webhook_delivery(webhook_id: str, event_id: str, user: AuthUser = Depends(require(P.ADMIN_INTEGRATIONS)), services: Services = Depends(get_services)) -> Any:
    result = await services.webhooks.replay(webhook_id, event_id)
    await services.audit.record_as(user, action="webhook.replay", domain=AuditDomain.SYSTEM, entity_type="WEBHOOK", entity_id=webhook_id, after={"eventId": event_id, "status": result["status"]})
    return result


@router.get("/admin/system/health")
async def system_health(user: AuthUser = Depends(require(P.ANALYTICS_READ_SYSTEM)), services: Services = Depends(get_services)) -> Any:
    db = services.db
    started = time.perf_counter()
    try:
        await db.command("ping")
        database = "UP"
    except Exception:  # any failure means the database is not reachable
        database = "DOWN"
    latency = round((time.perf_counter() - started) * 1000)
    names = await db.list_collection_names()
    documents = sum([await db[name].estimated_document_count() for name in names])
    features = await services.ml.features()
    on = [item for item in features if item["enabled"]]
    ai = "OFF" if not on else "UP" if services.ml.llm_ready else "DEGRADED"
    note = {"OFF": "AI is switched off. Every workflow runs on rules.", "UP": "AI is configured and switched on.", "DEGRADED": "No AI key is set, so rules are used. Everything still works."}[ai]
    sweep = await db["job_runs"].find_one({"_id": "sla-sweep"})
    last_dispatch = await db["outbox_events"].find_one({"dispatchedAt": {"$ne": None}}, sort=[("dispatchedAt", -1)])
    failed = await db["outbox_events"].count_documents({"failedAt": {"$ne": None}})
    unapplied = await db["stock_ledger"].count_documents({"applied": False})
    waiting = await db["outbox_events"].count_documents({"dispatchedAt": None, "failedAt": None})
    return {
        "api": {"status": "UP", "latencyMs": latency},
        "database": {"status": database, "collections": len(names), "documents": documents},
        "ai": {"status": ai, "note": note},
        "jobs": [
            {"name": "Notification and webhook delivery", "lastRun": last_dispatch["dispatchedAt"].isoformat() if last_dispatch else "", "status": "OK" if waiting < 100 else "LATE"},
            {"name": "SLA escalation sweep", "lastRun": sweep["lastRun"].isoformat() if sweep else "", "status": "OK" if sweep else "LATE"},
        ],
        "dataQuality": [
            {"label": "Stock ledger fully applied", "ok": unapplied == 0, "detail": f"{unapplied} entries waiting" if unapplied else "Every movement is on its balance"},
            {"label": "No undeliverable events", "ok": failed == 0, "detail": f"{failed} events gave up after retries" if failed else "Nothing stuck"},
        ],
    }
