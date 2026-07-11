import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.workflow import WorkflowAnalysisResult, WorkflowInspectResponse
from app.services.data_quality import load_dataframe
from app.services.workflow import analyze_workflow_data, build_workflow_inspection


router = APIRouter(prefix="/api/workflow", tags=["analysis-workflow"])


@router.post("/inspect", response_model=WorkflowInspectResponse)
async def inspect_analysis_workflow(file: UploadFile = File(...)) -> WorkflowInspectResponse:
    try:
        content = await file.read()
        frame, file_type = load_dataframe(file.filename or "uploaded.csv", content)
        return build_workflow_inspection(file.filename or "uploaded.csv", file_type, frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@router.post("/analyze", response_model=WorkflowAnalysisResult)
async def analyze_uploaded_data(
    file: UploadFile = File(...),
    task_key: str = Form(...),
    target: str | None = Form(None),
    x_field: str | None = Form(None),
    y_field: str | None = Form(None),
    group_field: str | None = Form(None),
    outcome_field: str | None = Form(None),
    feature_fields: str | None = Form(None),
) -> WorkflowAnalysisResult:
    try:
        content = await file.read()
        frame, _ = load_dataframe(file.filename or "uploaded.csv", content)
        parsed_features: list[str] | None = None
        if feature_fields:
            parsed = json.loads(feature_fields)
            if not isinstance(parsed, list):
                raise ValueError("feature_fields 必须是字段名数组")
            parsed_features = [str(item) for item in parsed]
        return analyze_workflow_data(
            frame=frame,
            task_key=task_key,
            target=target,
            x_field=x_field,
            y_field=y_field,
            group_field=group_field,
            outcome_field=outcome_field,
            feature_fields=parsed_features,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
