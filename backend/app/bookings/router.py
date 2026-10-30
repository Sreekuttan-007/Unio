from datetime import datetime
from typing import Any

from fastapi import Depends, Query
from pydantic import Field

from app.collision.acknowledge import Acknowledging
from app.core.access import GuardedRouter, authenticated, require
from app.core.authuser import AuthUser
from app.core.errors import rule
from app.core.pagination import PageParams, page_params
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["bookings"])

READERS = (P.BOOKING_READ_OWN, P.BOOKING_READ_DEPARTMENT, P.BOOKING_READ_CAMPUS)
KINDS = "^(LECTURE|PRACTICAL|EXAM|EVENT)$"


class BookingCheck(ApiModel):
    room_code: str = Field(min_length=3, max_length=20)
    start: datetime
    end: datetime
    headcount: int = Field(ge=1, le=2000)
    kind: str = Field(default="LECTURE", pattern=KINDS)
    purpose: str = Field(default="", max_length=200)
    required_features: list[str] = Field(default_factory=list, max_length=10)
    expected_state_token: str | None = Field(default=None, max_length=64)


class BookingCreate(BookingCheck, Acknowledging):
    purpose: str = Field(min_length=3, max_length=200)


class Reschedule(Acknowledging):
    room_code: str | None = Field(default=None, min_length=3, max_length=20)
    start: datetime
    end: datetime
    headcount: int | None = Field(default=None, ge=1, le=2000)


class MoveSession(Acknowledging):
    room_code: str | None = Field(default=None, min_length=3, max_length=20)
    start: datetime | None = None
    end: datetime | None = None


@router.get("/bookings")
async def list_bookings(
    status: str | None = Query(None, pattern="^(CONFIRMED|RESCHEDULED|CANCELLED)$"),
    paging: PageParams = Depends(page_params),
    user: AuthUser = Depends(require(*READERS)),
    services: Services = Depends(get_services),
) -> Any:
    items = await services.bookings.list(user, status)
    return {"items": items[paging.skip : paging.skip + paging.size], "page": paging.page, "size": paging.size, "total": len(items)}


@router.post("/bookings/check")
async def check_booking(body: BookingCheck, user: AuthUser = Depends(require(P.BOOKING_REQUEST)), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.check(user, body.room_code, body.start, body.end, body.headcount, body.kind, body.purpose, body.required_features, body.expected_state_token)


@router.post("/bookings", status_code=201)
async def create_booking(body: BookingCreate, user: AuthUser = Depends(require(P.BOOKING_REQUEST)), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.create(
        user, body.room_code, body.start, body.end, body.headcount, body.kind, body.purpose, body.required_features, body.acknowledgement(), body.expected_state_token
    )


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, user: AuthUser = Depends(require(*READERS)), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.view(await services.bookings.get(user, booking_id), user)


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, user: AuthUser = Depends(require(P.BOOKING_REQUEST, P.BOOKING_CANCEL_ANY)), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.cancel(user, booking_id)


@router.post("/bookings/{booking_id}/reschedule")
async def reschedule_booking(booking_id: str, body: Reschedule, user: AuthUser = Depends(require(P.BOOKING_REQUEST, P.BOOKING_COORDINATE)), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.reschedule(user, booking_id, body.room_code, body.start, body.end, body.headcount, body.acknowledgement(), body.expected_state_token)


@router.post("/timetable/sessions/{session_id}/move")
async def move_session(session_id: str, body: MoveSession, user: AuthUser = Depends(require(P.BOOKING_COORDINATE)), services: Services = Depends(get_services)) -> Any:
    if body.room_code is None and body.start is None and body.end is None:
        raise rule("NOTHING_TO_MOVE", "Say which room or time to move the class to.")
    return await services.bookings.move_session(user, session_id, body.room_code, body.start, body.end, body.acknowledgement(), body.expected_state_token)


@router.get("/timetable/today")
async def timetable_today(date: str | None = Query(None, max_length=10), user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Any:
    return await services.bookings.today(user, date)


@router.get("/timetable/affected")
async def timetable_affected(
    rooms: str = Query(min_length=3, max_length=400),
    start: datetime = Query(),
    end: datetime = Query(),
    user: AuthUser = Depends(require(P.BOOKING_COORDINATE, P.BOOKING_READ_DEPARTMENT, P.BOOKING_REQUEST)),
    services: Services = Depends(get_services),
) -> Any:
    if end <= start:
        raise rule("INVALID_WINDOW", "The end must be after the start.")
    codes = [code.strip().upper() for code in rooms.split(",") if code.strip()][:30]
    return await services.bookings.affected(codes, start, end)
