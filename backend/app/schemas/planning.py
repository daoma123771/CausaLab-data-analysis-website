from pydantic import BaseModel, Field, model_validator


class ProportionPlanRequest(BaseModel):
    baseline_rate: float = Field(gt=0, lt=1, description="对照组基准转化率")
    target_rate: float = Field(gt=0, lt=1, description="希望检测到的实验组转化率")
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    power: float = Field(default=0.8, gt=0.5, lt=0.999)
    allocation_ratio: float = Field(default=1.0, ge=0.1, le=10)
    daily_traffic: int | None = Field(default=None, ge=2)

    @model_validator(mode="after")
    def rates_must_differ(self) -> "ProportionPlanRequest":
        if abs(self.target_rate - self.baseline_rate) < 1e-9:
            raise ValueError("目标转化率必须与基准转化率不同")
        return self


class ContinuousPlanRequest(BaseModel):
    mean_difference: float = Field(gt=0, description="希望检测到的最小均值差")
    standard_deviation: float = Field(gt=0, description="指标标准差")
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    power: float = Field(default=0.8, gt=0.5, lt=0.999)
    allocation_ratio: float = Field(default=1.0, ge=0.1, le=10)
    daily_traffic: int | None = Field(default=None, ge=2)


class PowerCurvePoint(BaseModel):
    total_sample_size: int
    power: float


class PlanResponse(BaseModel):
    metric_type: str
    control_sample_size: int
    treatment_sample_size: int
    total_sample_size: int
    effect_size: float
    minimum_detectable_effect: float
    alpha: float
    target_power: float
    estimated_days: int | None
    curve: list[PowerCurvePoint]
    explanation: str
    warnings: list[str]

