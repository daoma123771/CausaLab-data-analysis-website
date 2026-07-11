from typing import Literal

from pydantic import BaseModel, Field


class AnalysisReportRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)
    analyst: str = Field(default="CausaLab 用户", max_length=50)
    metric_name: str = Field(min_length=1, max_length=80)
    metric_type: Literal["proportion", "continuous"]
    method: str = Field(min_length=1, max_length=100)
    control_label: str = Field(default="对照组 A", max_length=40)
    treatment_label: str = Field(default="实验组 B", max_length=40)
    control_size: int = Field(gt=1)
    treatment_size: int = Field(gt=1)
    control_value: float
    treatment_value: float
    absolute_effect: float
    relative_effect_percent: float | None = None
    p_value: float = Field(ge=0, le=1)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1)
    ci_lower: float
    ci_upper: float
    decision: str = Field(min_length=1, max_length=80)
    conclusion: str = Field(min_length=1, max_length=500)
    quality_score: int | None = Field(default=None, ge=0, le=100)
    notes: list[str] = Field(default_factory=list, max_length=10)
