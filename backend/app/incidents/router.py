from typing import Any

from fastapi import Depends, Query, Response
from pydantic import Field

from app.core.access import GuardedRouter, authenticated, require
from app.core.authuser import AuthUser
from app.core.errors import rule
from app.core.pagination import PageParams, page_params
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["incidents"])


class ExtractRequest(ApiModel):
    text: str = Field(min_length=3, max_length=2000)


class SubmitRequest(ApiModel):
    text: str = Field(min_length=3, max_length=2000)
    extraction: dict[str, Any]
    channel: str = Field(default="FORM", pattern="^(FORM|CHAT)$")
    academic_impact: str | None = Field(default=None, pattern="^(LECTURE|PRACTICAL|EXAM|EVENT)$")


class FeedbackRequest(ApiModel):
    fixed: bool


class TransitionRequest(ApiModel):
    event: str = Field(min_length=3, max_length=40)


class ActionRequest(ApiModel):
    target_id: str | None = Field(default=None, max_length=40)


class SimulateEmail(ApiModel):
    from_: str = Field(alias="from", min_length=3, max_length=254)
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    message_id: str | None = Field(default=None, max_length=200)
    in_reply_to: str | None = Field(default=None, max_length=40)


@router.post("/issues/extract")
async def extract_issue(body: ExtractRequest, user: AuthUser = Depends(require(P.ISSUE_CREATE)), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.extract(user, body.text)


@router.post("/issues", status_code=201)
async def submit_issue(body: SubmitRequest, user: AuthUser = Depends(require(P.ISSUE_CREATE)), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.submit(user.id, user.name, body.text, body.extraction, body.channel, academic_impact=body.academic_impact, actor_role=user.role_key)


@router.get("/issues/mine")
async def my_reports(user: AuthUser = Depends(require(P.ISSUE_CREATE)), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.my_reports(user)


@router.post("/issues/{report_id}/feedback", status_code=204)
async def report_feedback(report_id: str, body: FeedbackRequest, user: AuthUser = Depends(require(P.ISSUE_CREATE)), services: Services = Depends(get_services)) -> Response:
    await services.incidents.feedback(user, report_id, body.fixed)
    return Response(status_code=204)


@router.get("/notices")
async def list_notices(user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.notices()


READERS = (P.ISSUE_READ_DEPARTMENT, P.ISSUE_READ_CAMPUS, P.ISSUE_READ_ASSIGNED, P.INCIDENT_TRIAGE)


@router.get("/incidents")
async def list_incidents(
    status: str | None = Query(None, max_length=30),
    paging: PageParams = Depends(page_params),
    user: AuthUser = Depends(require(*READERS)),
    services: Services = Depends(get_services),
) -> Any:
    items = await services.incidents.list(user, status)
    window = items[paging.skip : paging.skip + paging.size]
    return {"items": window, "page": paging.page, "size": paging.size, "total": len(items)}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, user: AuthUser = Depends(require(*READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.view(await services.incidents.get(user, incident_id), user)


@router.post("/incidents/{incident_id}/transition")
async def transition_incident(incident_id: str, body: TransitionRequest, user: AuthUser = Depends(require(P.INCIDENT_TRANSITION)), services: Services = Depends(get_services)) -> Any:
    return await services.incidents.view(await services.incidents.transition(user, incident_id, body.event), user)


@router.post("/incidents/{incident_id}/actions/{key}")
async def incident_action(
    incident_id: str,
    key: str,
    body: ActionRequest | None = None,
    user: AuthUser = Depends(require(P.INCIDENT_TRIAGE, P.INCIDENT_LINK_DUPLICATE, P.INCIDENT_TRANSITION)),
    services: Services = Depends(get_services),
) -> Any:
    if key == "incident.link" and user.has(P.INCIDENT_LINK_DUPLICATE):
        return {"message": await services.incidents.link_duplicate(user, incident_id, body.target_id if body else None)}
    if key == "incident.close" and user.has(P.INCIDENT_TRANSITION):
        await services.incidents.transition(user, incident_id, "CLOSE")
        await services.workorders.close_for_incident(incident_id, user.id, user.role_key)
        return {"message": "The incident was closed and the reporters were told."}
    if key == "incident.resolve" and user.has(P.INCIDENT_TRANSITION):
        await services.incidents.transition(user, incident_id, "RESOLVE")
        return {"message": "Marked resolved. Reporters are asked to confirm."}
    if key == "incident.createWorkOrder" and user.has(P.INCIDENT_TRIAGE):
        workorders = getattr(services, "workorders", None)
        if workorders is None:
            raise rule("NOT_BUILT_YET", "Work orders arrive in Phase 7.")
        return {"message": await workorders.create_from_incident(user, incident_id)}
    raise rule("UNKNOWN_ACTION", "That action is not available here.")


@router.get("/inbox")
async def list_inbox(user: AuthUser = Depends(require(P.INBOX_READ)), services: Services = Depends(get_services)) -> Any:
    return await services.inbox.list()


@router.post("/inbox/simulate", status_code=201)
async def simulate_email(body: SimulateEmail, user: AuthUser = Depends(require(P.INBOX_TRIAGE)), services: Services = Depends(get_services)) -> Any:
    email, _repeat = await services.inbox.receive(body.from_, body.subject, body.text, message_id=body.message_id, in_reply_to=body.in_reply_to)
    return services.inbox.view(email)


@router.post("/inbox/{email_id}/process")
async def process_email(email_id: str, user: AuthUser = Depends(require(P.INBOX_TRIAGE)), services: Services = Depends(get_services)) -> Any:
    return await services.inbox.process(user, email_id)
