from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalysisResponse, ContinuousAnalysisRequest, ProportionAnalysisRequest
from app.services.analysis import analyze_continuous, analyze_proportion


router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/proportion", response_model=AnalysisResponse)
def run_proportion_analysis(payload: ProportionAnalysisRequest) -> AnalysisResponse:
    try:
        return analyze_proportion(payload)
    except (ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/continuous", response_model=AnalysisResponse)
def run_continuous_analysis(payload: ContinuousAnalysisRequest) -> AnalysisResponse:
    try:
        return analyze_continuous(payload)
    except (ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
