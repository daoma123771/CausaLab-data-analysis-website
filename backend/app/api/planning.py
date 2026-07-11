from fastapi import APIRouter, HTTPException

from app.schemas.planning import (
    ContinuousPlanRequest,
    PlanResponse,
    ProportionPlanRequest,
)
from app.services.planning import plan_continuous_experiment, plan_proportion_experiment


router = APIRouter(prefix="/api/planning", tags=["planning"])


@router.post("/proportion", response_model=PlanResponse)
def calculate_proportion_plan(payload: ProportionPlanRequest) -> PlanResponse:
    try:
        return plan_proportion_experiment(payload)
    except (ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/continuous", response_model=PlanResponse)
def calculate_continuous_plan(payload: ContinuousPlanRequest) -> PlanResponse:
    try:
        return plan_continuous_experiment(payload)
    except (ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

