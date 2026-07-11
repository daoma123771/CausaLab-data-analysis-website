from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.data_quality import router as data_quality_router
from app.api.planning import router as planning_router
from app.api.reporting import router as reporting_router
from app.api.workflow import router as workflow_router
from app.schemas.system import HealthResponse, ModuleInfo


app = FastAPI(
    title="CausaLab API",
    version="1.0.0",
    description="智能实验设计与效应评估平台后端服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planning_router)
app.include_router(analysis_router)
app.include_router(data_quality_router)
app.include_router(reporting_router)
app.include_router(workflow_router)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", name="CausaLab", version="1.0.0")


@app.get("/api/modules", response_model=list[ModuleInfo], tags=["system"])
def list_modules() -> list[ModuleInfo]:
    return [
        ModuleInfo(key="planning", name="实验规划", status="ready"),
        ModuleInfo(key="quality", name="数据质量诊断", status="ready"),
        ModuleInfo(key="analysis", name="效应评估", status="ready"),
        ModuleInfo(key="workflow", name="统计分析向导", status="ready"),
        ModuleInfo(key="robustness", name="稳健性验证", status="ready"),
        ModuleInfo(key="report", name="分析报告", status="ready"),
    ]
