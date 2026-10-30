from typing import Any

from fastapi import Depends, Query
from pydantic import Field

from app.audit.service import AuditDomain
from app.campus import service
from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.clock import utcnow
from app.core.errors import not_found, rule
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services
from app.staff.service import faculty_list, technician_cards

router = GuardedRouter(prefix="/api/v1", tags=["campus"])

MAP_VIEWERS = (P.MAP_READ_PUBLIC, P.MAP_READ_OPERATIONAL, P.ADMIN_CAMPUS)


@router.get("/campus/map")
async def campus_map(user: AuthUser = Depends(require(*MAP_VIEWERS)), services: Services = Depends(get_services)) -> Any:
    return await service.map_payload(services.db, user)


@router.get("/campus/buildings/{ident}")
async def campus_building(ident: str, user: AuthUser = Depends(require(*MAP_VIEWERS)), services: Services = Depends(get_services)) -> Any:
    return await service.building_detail(services.db, user, ident)


@router.get("/campus/rooms")
async def campus_rooms(
    bookable: bool = Query(False),
    user: AuthUser = Depends(require(P.CAMPUS_READ, P.BOOKING_REQUEST)),
    services: Services = Depends(get_services),
) -> Any:
    return await service.room_directory(services.db, bookable)


@router.get("/campus/resources")
async def campus_resources(user: AuthUser = Depends(require(P.CAMPUS_READ)), services: Services = Depends(get_services)) -> Any:
    return await service.resources(services.db, user)


@router.get("/technicians")
async def list_technicians(user: AuthUser = Depends(require(P.STAFF_READ, P.WORKORDER_ASSIGN_CAMPUS, P.WORKORDER_ASSIGN_DEPARTMENT)), services: Services = Depends(get_services)) -> Any:
    return await technician_cards(services.db)


@router.get("/admin/campus/summary")
async def admin_campus_summary(user: AuthUser = Depends(require(P.ADMIN_CAMPUS)), services: Services = Depends(get_services)) -> Any:
    return await service.admin_summary(services.db)


@router.get("/admin/staff")
async def admin_staff(user: AuthUser = Depends(require(P.ADMIN_STAFF)), services: Services = Depends(get_services)) -> Any:
    return {"technicians": await technician_cards(services.db), "faculty": await faculty_list(services.db)}


class StatusChange(ApiModel):
    status: str = Field(pattern="^(OPEN|CLOSED|MAINTENANCE)$")
    reason: str | None = Field(default=None, max_length=200)


@router.patch("/admin/campus/rooms/{code}/status")
async def set_room_status(code: str, body: StatusChange, user: AuthUser = Depends(require(P.ADMIN_CAMPUS)), services: Services = Depends(get_services)) -> Any:
    room = await services.db["rooms"].find_one({"_id": code})
    if room is None:
        raise not_found("Room")
    if body.status != "OPEN" and not body.reason:
        raise rule("REASON_REQUIRED", "Say why the room is being closed, so people can be told.")
    await services.db["rooms"].update_one(
        {"_id": code}, {"$set": {"status": body.status, "closedReason": body.reason if body.status != "OPEN" else None, "updatedAt": utcnow()}}
    )
    await services.audit.record_as(
        user, action="room.status.update", domain=AuditDomain.OPERATIONS, entity_type="ROOM", entity_id=code,
        before={"status": room["status"]}, after={"status": body.status}, reason=body.reason,
    )
    return {"code": code, "status": body.status, "closedReason": body.reason if body.status != "OPEN" else None}


@router.patch("/admin/campus/buildings/{ident}/status")
async def set_building_status(ident: str, body: StatusChange, user: AuthUser = Depends(require(P.ADMIN_CAMPUS)), services: Services = Depends(get_services)) -> Any:
    building = await services.db["buildings"].find_one({"$or": [{"_id": ident}, {"mapRegionId": ident}]})
    if building is None:
        raise not_found("Building")
    if body.status != "OPEN" and not body.reason:
        raise rule("REASON_REQUIRED", "Say why the building is being closed, so people can be told.")
    await services.db["buildings"].update_one(
        {"_id": building["_id"]}, {"$set": {"status": body.status, "publicNote": body.reason if body.status != "OPEN" else None, "operationalNote": body.reason if body.status != "OPEN" else None, "updatedAt": utcnow()}}
    )
    await services.audit.record_as(
        user, action="building.status.update", domain=AuditDomain.OPERATIONS, entity_type="BUILDING", entity_id=building["_id"],
        before={"status": building.get("status", "OPEN")}, after={"status": body.status}, reason=body.reason,
    )
    return {"id": building["_id"], "status": body.status}
