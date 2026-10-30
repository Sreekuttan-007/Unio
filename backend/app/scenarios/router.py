from typing import Any

from fastapi import Depends

from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.permission import Permission as P
from app.services import Services, get_services
from app.scenarios.service import ScenarioService

router = GuardedRouter(prefix="/api/v1", tags=["admin"])


@router.get("/admin/scenarios")
async def scenarios(user: AuthUser = Depends(require(P.ADMIN_SEED)), services: Services = Depends(get_services)) -> Any:
    return ScenarioService(services).list()


@router.post("/admin/scenarios/{scenario_id}/reset")
async def reset_scenario(scenario_id: str, user: AuthUser = Depends(require(P.ADMIN_SEED)), services: Services = Depends(get_services)) -> Any:
    """Wipes operational data and stages a demo scenario. Refused unless this is a demo deployment."""
    return await ScenarioService(services).reset(user, scenario_id)
