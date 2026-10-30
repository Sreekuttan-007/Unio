from typing import Any

from fastapi import Depends
from pydantic import Field

from app.core.access import GuardedRouter, require
from app.core.authuser import AuthUser
from app.core.permission import Permission as P
from app.core.schema import ApiModel
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["simulations"])


class SimulateBody(ApiModel):
    incident_id: str = Field(min_length=3, max_length=20)


@router.post("/simulations", status_code=201)
async def run_simulation(body: SimulateBody, user: AuthUser = Depends(require(P.SIMULATION_RUN)), services: Services = Depends(get_services)) -> Any:
    """Compares recovery plans on a frozen copy of the campus. Writes nothing but the run itself."""
    return await services.simulations.run(user, body.incident_id)


@router.get("/simulations/{run_id}")
async def get_simulation(run_id: str, user: AuthUser = Depends(require(P.SIMULATION_RUN)), services: Services = Depends(get_services)) -> Any:
    return services.simulations.view(await services.simulations.get(user, run_id))


@router.post("/simulations/{run_id}/plans/{plan_id}/execute")
async def execute_plan(run_id: str, plan_id: str, user: AuthUser = Depends(require(P.SIMULATION_EXECUTE)), services: Services = Depends(get_services)) -> Any:
    return await services.simulations.execute(user, run_id, plan_id)
