from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.data_quality import DataQualityResponse


class VariableCandidate(BaseModel):
    name: str
    role: Literal["target", "feature", "group", "identifier", "time", "text"]
    data_type: str
    semantic_type: Literal["numeric", "categorical", "binary", "datetime", "text", "identifier"]
    non_null_count: int
    missing_percent: float
    unique_count: int
    reason: str


class AnalysisTaskRecommendation(BaseModel):
    key: Literal[
        "descriptive",
        "correlation",
        "two_group_mean",
        "multi_group_mean",
        "linear_regression",
        "proportion_test",
    ]
    title: str
    method: str
    question: str
    suitability: Literal["ready", "needs_input", "limited", "not_available"]
    confidence: int
    required_fields: list[str]
    candidate_fields: dict[str, list[str]]
    sample_assessment: str
    sample_gap: int | None = None
    explanation: str


class WorkflowInspectResponse(BaseModel):
    file_name: str
    file_type: str
    row_count: int
    column_count: int
    quality_score: int
    quality_level: str
    dataset_summary: str
    variables: list[VariableCandidate]
    recommended_tasks: list[AnalysisTaskRecommendation]
    next_steps: list[str]
    quality: DataQualityResponse
    preview: list[dict[str, Any]]


class WorkflowAnalysisMetric(BaseModel):
    label: str
    value: str
    note: str | None = None


class WorkflowAnalysisResult(BaseModel):
    task_key: str
    title: str
    method: str
    sample_size: int
    summary: str
    metrics: list[WorkflowAnalysisMetric]
    table: list[dict[str, Any]]
    interpretation: list[str]
    warnings: list[str]
    chart_data: list[dict[str, Any]] = []
