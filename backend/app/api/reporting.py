from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.reporting import AnalysisReportRequest
from app.services.reporting import build_analysis_report


router = APIRouter(prefix="/api/reports", tags=["reporting"])


@router.post("/analysis.docx")
def export_analysis_report(payload: AnalysisReportRequest) -> Response:
    try:
        content = build_analysis_report(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    safe_name = "".join(character for character in payload.project_name if character not in '\\/:*?\"<>|').strip() or "CausaLab"
    file_name = quote(f"{safe_name}_分析报告.docx")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{file_name}"},
    )
