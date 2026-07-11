from typing import Literal

from pydantic import BaseModel, Field, model_validator


Alternative = Literal["two-sided", "greater", "less"]


class ProportionAnalysisRequest(BaseModel):
    control_total: int = Field(gt=1)
    control_success: int = Field(ge=0)
    treatment_total: int = Field(gt=1)
    treatment_success: int = Field(ge=0)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    alternative: Alternative = "two-sided"
    bootstrap_iterations: int = Field(default=3000, ge=500, le=20000)
    random_seed: int = Field(default=2026, ge=0)

    @model_validator(mode="after")
    def successes_cannot_exceed_total(self) -> "ProportionAnalysisRequest":
        if self.control_success > self.control_total:
            raise ValueError("对照组成功数不能超过样本量")
        if self.treatment_success > self.treatment_total:
            raise ValueError("实验组成功数不能超过样本量")
        return self


class ContinuousAnalysisRequest(BaseModel):
    control_values: list[float] = Field(min_length=2, max_length=50000)
    treatment_values: list[float] = Field(min_length=2, max_length=50000)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    alternative: Alternative = "two-sided"
    bootstrap_iterations: int = Field(default=3000, ge=500, le=20000)
    random_seed: int = Field(default=2026, ge=0)


class HistogramBin(BaseModel):
    lower: float
    upper: float
    count: int


class AnalysisResponse(BaseModel):
    metric_type: Literal["proportion", "continuous"]
    method: str
    control_size: int
    treatment_size: int
    control_value: float
    treatment_value: float
    absolute_effect: float
    relative_effect_percent: float | None
    statistic: float
    p_value: float
    alpha: float
    confidence_level: float
    ci_lower: float
    ci_upper: float
    significant: bool
    direction_matches: bool
    decision: str
    conclusion: str
    bootstrap_iterations: int
    bootstrap_histogram: list[HistogramBin]
    warnings: list[str]
