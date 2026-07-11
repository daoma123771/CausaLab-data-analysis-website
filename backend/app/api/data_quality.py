from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.data_quality import DataQualityResponse
from app.services.data_quality import inspect_dataframe, load_dataframe


router = APIRouter(prefix="/api/data", tags=["data-quality"])


@router.post("/inspect", response_model=DataQualityResponse)
async def inspect_uploaded_data(file: UploadFile = File(...)) -> DataQualityResponse:
    try:
        content = await file.read()
        frame, file_type = load_dataframe(file.filename or "uploaded.csv", content)
        return inspect_dataframe(file.filename or "uploaded.csv", file_type, frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
