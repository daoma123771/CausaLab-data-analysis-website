import io
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.schemas.data_quality import (
    ColumnProfile,
    DataQualityResponse,
    GroupCount,
    NumericSummary,
)


ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def load_dataframe(file_name: str, content: bytes) -> tuple[pd.DataFrame, str]:
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持 CSV 和 XLSX 文件")
    if not content:
        raise ValueError("上传文件为空")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("文件不能超过 10 MB")

    try:
        if extension == ".xlsx":
            frame = pd.read_excel(io.BytesIO(content))
        else:
            try:
                frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            except UnicodeDecodeError:
                frame = pd.read_csv(io.BytesIO(content), encoding="gb18030")
    except Exception as exc:
        raise ValueError(f"无法解析文件：{exc}") from exc

    if frame.empty:
        raise ValueError("文件中没有可分析的数据行")
    if frame.shape[1] > 200:
        raise ValueError("字段数量不能超过 200 列")
    frame.columns = [str(column).strip() or f"column_{index + 1}" for index, column in enumerate(frame.columns)]
    if frame.columns.duplicated().any():
        raise ValueError("文件包含重复的字段名")
    return frame, extension.removeprefix(".")


def _infer_role(series: pd.Series, name: str, row_count: int) -> str:
    lowered = name.lower()
    unique_count = int(series.nunique(dropna=True))
    unique_ratio = unique_count / max(int(series.notna().sum()), 1)
    if any(token in lowered for token in ("time", "date", "日期", "时间")) or pd.api.types.is_datetime64_any_dtype(series):
        return "time"
    if any(token in lowered for token in ("group", "variant", "treatment", "实验组", "分组")):
        return "group"
    if any(token in lowered for token in ("id", "编号", "用户")) or (row_count >= 10 and unique_ratio >= 0.98):
        return "identifier"
    if pd.api.types.is_numeric_dtype(series):
        return "metric"
    if 2 <= unique_count <= 10:
        return "category"
    return "text"


def _profile_column(series: pd.Series, name: str, row_count: int) -> ColumnProfile:
    missing_count = int(series.isna().sum())
    role = _infer_role(series, name, row_count)
    numeric_summary = None
    outlier_count = None
    if pd.api.types.is_numeric_dtype(series) and series.notna().any():
        clean = series.dropna().astype(float)
        q1, q3 = clean.quantile([0.25, 0.75])
        iqr = q3 - q1
        outlier_count = int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
        numeric_summary = NumericSummary(
            minimum=float(clean.min()),
            maximum=float(clean.max()),
            mean=float(clean.mean()),
            median=float(clean.median()),
            standard_deviation=float(clean.std(ddof=1)) if len(clean) > 1 else 0.0,
        )
    return ColumnProfile(
        name=name,
        data_type=str(series.dtype),
        inferred_role=role,
        non_null_count=int(series.notna().sum()),
        missing_count=missing_count,
        missing_percent=round(missing_count / row_count * 100, 2),
        unique_count=int(series.nunique(dropna=True)),
        outlier_count=outlier_count,
        numeric_summary=numeric_summary,
    )


def _json_value(value: Any) -> Any:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def inspect_dataframe(file_name: str, file_type: str, frame: pd.DataFrame) -> DataQualityResponse:
    row_count, column_count = frame.shape
    profiles = [_profile_column(frame[column], column, row_count) for column in frame.columns]
    duplicate_rows = int(frame.duplicated().sum())
    duplicate_percent = duplicate_rows / row_count * 100
    total_missing = int(frame.isna().sum().sum())
    total_cells = row_count * column_count
    total_missing_percent = total_missing / total_cells * 100

    group_candidates = [profile.name for profile in profiles if profile.inferred_role == "group"]
    if not group_candidates:
        group_candidates = [
            profile.name for profile in profiles
            if profile.inferred_role == "category" and profile.unique_count == 2
        ]
    detected_group = group_candidates[0] if group_candidates else None
    group_distribution: list[GroupCount] = []
    imbalance = 0.0
    if detected_group:
        counts = frame[detected_group].fillna("(缺失)").astype(str).value_counts()
        group_distribution = [
            GroupCount(value=value, count=int(count), percent=round(count / row_count * 100, 2))
            for value, count in counts.items()
        ]
        if len(counts) == 2:
            imbalance = abs(float(counts.iloc[0] - counts.iloc[1])) / row_count * 100

    outlier_total = sum(profile.outlier_count or 0 for profile in profiles)
    numeric_non_null = sum(profile.non_null_count for profile in profiles if profile.numeric_summary)
    outlier_percent = outlier_total / max(numeric_non_null, 1) * 100
    score = round(100 - min(35, total_missing_percent * 1.5) - min(25, duplicate_percent) - min(20, outlier_percent * 2) - min(10, imbalance / 3))
    score = max(0, min(100, score))
    level = "excellent" if score >= 90 else "good" if score >= 75 else "warning" if score >= 55 else "poor"

    warnings: list[str] = []
    recommendations: list[str] = []
    if total_missing:
        warnings.append(f"发现 {total_missing} 个缺失单元格，占全部数据的 {total_missing_percent:.2f}%。")
        recommendations.append("分析前确认缺失机制，并根据业务含义选择删除、插补或保留缺失标记。")
    if duplicate_rows:
        warnings.append(f"发现 {duplicate_rows} 行完全重复记录。")
        recommendations.append("核对重复记录是否来自重复采集；若是同一实验单位，应先去重。")
    if outlier_total:
        warnings.append(f"数值字段中检测到 {outlier_total} 个 IQR 规则异常值。")
        recommendations.append("结合箱线图和业务边界复核异常值，不建议仅凭统计规则直接删除。")
    if imbalance > 20:
        warnings.append(f"两组样本占比相差 {imbalance:.2f} 个百分点，存在明显分组失衡。")
        recommendations.append("检查流量分配、随机化逻辑和样本比例失配（SRM）风险。")
    if not detected_group:
        warnings.append("未自动识别出二元实验分组字段。")
        recommendations.append("建议使用 group、variant 或 分组 等清晰字段名，并采用 A/B 两个取值。")
    if not warnings:
        recommendations.append("数据结构完整，可继续选择指标并进行效应评估。")

    preview = [
        {str(key): _json_value(value) for key, value in record.items()}
        for record in frame.head(8).to_dict(orient="records")
    ]
    return DataQualityResponse(
        file_name=Path(file_name).name,
        file_type=file_type,
        row_count=row_count,
        column_count=column_count,
        quality_score=score,
        quality_level=level,
        duplicate_rows=duplicate_rows,
        duplicate_percent=round(duplicate_percent, 2),
        total_missing_cells=total_missing,
        total_missing_percent=round(total_missing_percent, 2),
        detected_group_column=detected_group,
        group_distribution=group_distribution,
        columns=profiles,
        preview=preview,
        warnings=warnings,
        recommendations=recommendations,
    )
