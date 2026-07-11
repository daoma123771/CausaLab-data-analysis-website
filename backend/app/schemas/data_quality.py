from typing import Any, Literal

from pydantic import BaseModel


class NumericSummary(BaseModel):
    minimum: float
    maximum: float
    mean: float
    median: float
    standard_deviation: float


class ColumnProfile(BaseModel):
    name: str
    data_type: str
    inferred_role: Literal["identifier", "group", "metric", "time", "category", "text"]
    non_null_count: int
    missing_count: int
    missing_percent: float
    unique_count: int
    outlier_count: int | None = None
    numeric_summary: NumericSummary | None = None


class GroupCount(BaseModel):
    value: str
    count: int
    percent: float


class DataQualityResponse(BaseModel):
    file_name: str
    file_type: str
    row_count: int
    column_count: int
    quality_score: int
    quality_level: Literal["excellent", "good", "warning", "poor"]
    duplicate_rows: int
    duplicate_percent: float
    total_missing_cells: int
    total_missing_percent: float
    detected_group_column: str | None
    group_distribution: list[GroupCount]
    columns: list[ColumnProfile]
    preview: list[dict[str, Any]]
    warnings: list[str]
    recommendations: list[str]
