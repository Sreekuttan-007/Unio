from datetime import datetime
from fastapi import Depends

from app.core.access import GuardedRouter, public
from app.core.clock import utcnow
from app.core.errors import ApiException
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["system"])


class Ping(ApiModel):
    service: str
    database: str
    server_time: datetime


@router.get("/system/ping", response_model=Ping, dependencies=[public])
async def ping(services: Services = Depends(get_services)) -> Ping:
    """The frontend uses this to tell a sleeping backend from a broken one."""
    try:
        await services.db.command("ping")
        database = "UP"
    except Exception:  # noqa: BLE001 - any failure means the database is not reachable
        database = "DOWN"
    return Ping(service="unio-backend", database=database, server_time=utcnow())


def _not_built(phase: int) -> ApiException:
    return ApiException(501, "NOT_BUILT_YET", f"This arrives in Phase {phase}.")


# Permission-guarded placeholders for endpoints built in later phases. They let the permission
# matrix cover the real role model now: callers who may use one get 501, everyone else 403.
# Delete each one when its phase adds the real endpoint.
reserved = GuardedRouter(prefix="/api/v1", tags=["reserved"])
