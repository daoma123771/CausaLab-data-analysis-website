from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from app.schemas.data_quality import DataQualityResponse
from app.schemas.workflow import AnalysisTaskRecommendation, VariableCandidate, WorkflowAnalysisMetric, WorkflowAnalysisResult, WorkflowInspectResponse
from app.services.data_quality import inspect_dataframe


MIN_DESCRIPTIVE_N = 20
MIN_CORRELATION_N = 30
MIN_GROUP_N = 20
MIN_REGRESSION_BASE = 50


def _semantic_type(series: pd.Series, unique_count: int) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        non_null = max(int(series.notna().sum()), 1)
        if 1 < unique_count <= 2:
            return "binary"
        if unique_count <= min(12, max(3, non_null // 10)):
            return "categorical"
        return "numeric"
    if 1 < unique_count <= 2:
        return "binary"
    if unique_count <= 20:
        return "categorical"
    return "text"


def _profile_variables(frame: pd.DataFrame, quality: DataQualityResponse) -> list[VariableCandidate]:
    quality_by_name = {column.name: column for column in quality.columns}
    variables: list[VariableCandidate] = []
    row_count = len(frame)
    for name in frame.columns:
        series = frame[name]
        profile = quality_by_name[name]
        semantic = _semantic_type(series, profile.unique_count)
        role = "feature"
        reason = "字段可作为解释变量或描述统计对象。"
        lowered = name.lower()
        id_like_name = any(token in lowered for token in ("id", "编号", "用户", "user", "uuid", "code"))
        if (profile.inferred_role == "identifier" and id_like_name) or semantic == "identifier":
            role = "identifier"
            reason = "字段近似唯一，更适合作为样本标识，不建议作为建模变量。"
        elif profile.inferred_role == "time":
            role = "time"
            reason = "字段可能表示时间，可用于后续趋势或分层分析。"
        elif profile.inferred_role == "group" or semantic in {"binary", "categorical"}:
            role = "group"
            reason = "字段类别数量有限，适合作为分组变量。"
        elif semantic == "numeric":
            role = "target" if any(token in lowered for token in ("price", "salary", "wage", "income", "value", "房价", "工资", "收入", "得分", "score", "mpg", "y")) else "feature"
            reason = "数值字段可作为连续目标变量或解释变量。" if role == "target" else "数值字段适合描述统计、相关分析或回归建模。"
        elif semantic == "text":
            role = "text"
            reason = "高基数文本字段暂不进入第一阶段统计建模。"

        variables.append(
            VariableCandidate(
                name=name,
                role=role,
                data_type=profile.data_type,
                semantic_type=semantic,  # type: ignore[arg-type]
                non_null_count=profile.non_null_count,
                missing_percent=profile.missing_percent,
                unique_count=profile.unique_count,
                reason=reason,
            )
        )
    return variables


def _gap(current: int, required: int) -> int | None:
    return max(0, required - current) if current < required else None


def _assessment(current: int, required: int, unit: str = "有效样本") -> str:
    if current >= required:
        return f"当前约 {current} 个{unit}，达到第一阶段建议最低值 {required}。"
    return f"当前约 {current} 个{unit}，建议至少 {required}，还差约 {required - current}。"


def _build_recommendations(frame: pd.DataFrame, variables: list[VariableCandidate], quality: DataQualityResponse) -> list[AnalysisTaskRecommendation]:
    row_count = len(frame)
    numeric = [item.name for item in variables if item.semantic_type == "numeric" and item.role not in {"identifier"}]
    groups = [item.name for item in variables if item.semantic_type in {"binary", "categorical"} and item.role == "group"]
    binary_groups = [item.name for item in variables if item.semantic_type == "binary" and item.role == "group"]
    numeric_targets = [item.name for item in variables if item.semantic_type == "numeric" and item.role == "target"] or numeric[:3]

    recommendations: list[AnalysisTaskRecommendation] = []

    recommendations.append(
        AnalysisTaskRecommendation(
            key="descriptive",
            title="先了解数据整体分布",
            method="描述统计 + 缺失/异常值诊断",
            question="每个关键变量的均值、中位数、波动范围和异常情况如何？",
            suitability="ready" if numeric else "limited",
            confidence=95 if numeric else 55,
            required_fields=["至少 1 个数值变量"],
            candidate_fields={"numeric": numeric[:8]},
            sample_assessment=_assessment(row_count, MIN_DESCRIPTIVE_N),
            sample_gap=_gap(row_count, MIN_DESCRIPTIVE_N),
            explanation="适合作为所有分析的第一步，用来判断变量分布、缺失和异常值是否会影响后续结论。",
        )
    )

    correlation_ready = len(numeric) >= 2 and row_count >= MIN_CORRELATION_N
    recommendations.append(
        AnalysisTaskRecommendation(
            key="correlation",
            title="分析两个数值变量是否相关",
            method="Pearson/Spearman 相关分析",
            question="两个连续变量是否存在同向或反向关系？",
            suitability="ready" if correlation_ready else "needs_input" if len(numeric) >= 2 else "not_available",
            confidence=88 if correlation_ready else 60 if len(numeric) >= 2 else 20,
            required_fields=["至少 2 个数值变量"],
            candidate_fields={"numeric": numeric[:8]},
            sample_assessment=_assessment(row_count, MIN_CORRELATION_N),
            sample_gap=_gap(row_count, MIN_CORRELATION_N),
            explanation="适合房价-面积、工资-工龄、油耗-车重等两个连续变量关系的初步判断。",
        )
    )

    group_sizes: dict[str, int] = {}
    for group in binary_groups:
        counts = frame[group].dropna().value_counts()
        if len(counts) == 2:
            group_sizes[group] = int(counts.min())
    best_binary_group = max(group_sizes, key=group_sizes.get) if group_sizes else None
    per_group_n = group_sizes.get(best_binary_group, 0) if best_binary_group else 0
    two_group_ready = bool(best_binary_group and numeric and per_group_n >= MIN_GROUP_N)
    recommendations.append(
        AnalysisTaskRecommendation(
            key="two_group_mean",
            title="比较两组均值是否存在差异",
            method="Welch t 检验 + 效应量",
            question="两个分组在某个数值指标上的平均水平是否不同？",
            suitability="ready" if two_group_ready else "needs_input" if best_binary_group and numeric else "not_available",
            confidence=86 if two_group_ready else 58 if best_binary_group and numeric else 20,
            required_fields=["1 个二分类分组变量", "1 个数值指标变量"],
            candidate_fields={"group": [best_binary_group] if best_binary_group else binary_groups[:5], "metric": numeric[:6]},
            sample_assessment=_assessment(per_group_n or row_count, MIN_GROUP_N, "每组样本"),
            sample_gap=_gap(per_group_n or 0, MIN_GROUP_N) if best_binary_group else None,
            explanation="适合比较两类人群、两种方案或两个地区在工资、房价、评分等数值指标上的差异。",
        )
    )

    multi_groups = [group for group in groups if frame[group].dropna().nunique() >= 3]
    best_multi_group = multi_groups[0] if multi_groups else None
    multi_ready = bool(best_multi_group and numeric and row_count >= MIN_GROUP_N * 3)
    recommendations.append(
        AnalysisTaskRecommendation(
            key="multi_group_mean",
            title="比较多组均值是否存在差异",
            method="单因素 ANOVA",
            question="三个及以上分组在某个数值指标上的均值是否存在总体差异？",
            suitability="ready" if multi_ready else "needs_input" if best_multi_group and numeric else "not_available",
            confidence=82 if multi_ready else 55 if best_multi_group and numeric else 18,
            required_fields=["1 个多分类分组变量", "1 个数值指标变量"],
            candidate_fields={"group": [best_multi_group] if best_multi_group else multi_groups[:5], "metric": numeric[:6]},
            sample_assessment=_assessment(row_count, MIN_GROUP_N * 3),
            sample_gap=_gap(row_count, MIN_GROUP_N * 3),
            explanation="适合比较不同行业、地区、学历或类别之间的数值指标差异。",
        )
    )

    feature_count = max(0, len(numeric) - 1)
    required_regression_n = MIN_REGRESSION_BASE + max(0, feature_count) * 10
    regression_ready = bool(numeric_targets and feature_count >= 1 and row_count >= required_regression_n)
    recommendations.append(
        AnalysisTaskRecommendation(
            key="linear_regression",
            title="建立连续目标变量的解释模型",
            method="多元线性回归",
            question="哪些变量可能影响目标变量，影响方向和强度如何？",
            suitability="ready" if regression_ready else "needs_input" if numeric_targets and feature_count >= 1 else "not_available",
            confidence=90 if regression_ready else 62 if numeric_targets and feature_count >= 1 else 25,
            required_fields=["1 个连续目标变量", "至少 1 个解释变量"],
            candidate_fields={"target": numeric_targets[:5], "features": [name for name in numeric if name not in numeric_targets[:1]][:8]},
            sample_assessment=_assessment(row_count, required_regression_n),
            sample_gap=_gap(row_count, required_regression_n),
            explanation="适合房价、工资、油耗等连续目标变量分析，可作为数学建模的第一阶段基线模型。",
        )
    )

    binary_metrics = [item.name for item in variables if item.semantic_type == "binary" and item.name not in binary_groups]
    prop_ready = bool(best_binary_group and binary_metrics and per_group_n >= MIN_GROUP_N)
    recommendations.append(
        AnalysisTaskRecommendation(
            key="proportion_test",
            title="比较两组比例是否存在差异",
            method="两比例 z 检验",
            question="两个分组在二元结果上的成功率/发生率是否不同？",
            suitability="ready" if prop_ready else "needs_input" if best_binary_group else "not_available",
            confidence=82 if prop_ready else 48 if best_binary_group else 15,
            required_fields=["1 个二分类分组变量", "1 个二元结果变量"],
            candidate_fields={"group": [best_binary_group] if best_binary_group else binary_groups[:5], "outcome": binary_metrics[:5]},
            sample_assessment=_assessment(per_group_n or row_count, MIN_GROUP_N, "每组样本"),
            sample_gap=_gap(per_group_n or 0, MIN_GROUP_N) if best_binary_group else None,
            explanation="适合转化率、通过率、是否购买、是否违约等二元结果的组间比较。",
        )
    )

    return sorted(recommendations, key=lambda item: item.confidence, reverse=True)


def build_workflow_inspection(file_name: str, file_type: str, frame: pd.DataFrame) -> WorkflowInspectResponse:
    quality = inspect_dataframe(file_name, file_type, frame)
    variables = _profile_variables(frame, quality)
    recommendations = _build_recommendations(frame, variables, quality)
    numeric_count = sum(1 for item in variables if item.semantic_type == "numeric")
    category_count = sum(1 for item in variables if item.semantic_type in {"categorical", "binary"})
    dataset_summary = (
        f"数据包含 {quality.row_count} 行、{quality.column_count} 列；"
        f"识别出 {numeric_count} 个数值字段、{category_count} 个类别/二元字段。"
        f"综合质量评分为 {quality.quality_score}/100。"
    )
    ready_tasks = [task.title for task in recommendations if task.suitability == "ready"][:3]
    next_steps = [
        "先确认系统推荐的目标变量、分组变量和解释变量是否符合业务含义。",
        "选择一个最想回答的分析问题，再进入对应统计检验或建模流程。",
        "若样本量提示不足，可调整最小效应假设，或继续补充数据后再检验。",
    ]
    if ready_tasks:
        next_steps.insert(0, f"当前优先可开展：{'、'.join(ready_tasks)}。")
    if quality.quality_score < 75:
        next_steps.append("数据质量评分偏低，建议先处理缺失、重复或异常值，再生成最终结论。")

    return WorkflowInspectResponse(
        file_name=quality.file_name,
        file_type=quality.file_type,
        row_count=quality.row_count,
        column_count=quality.column_count,
        quality_score=quality.quality_score,
        quality_level=quality.quality_level,
        dataset_summary=dataset_summary,
        variables=variables,
        recommended_tasks=recommendations,
        next_steps=next_steps,
        quality=quality,
        preview=quality.preview,
    )


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(column) for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]


def _categorical_columns(frame: pd.DataFrame) -> list[str]:
    return [
        str(column)
        for column in frame.columns
        if not pd.api.types.is_numeric_dtype(frame[column]) or frame[column].dropna().nunique() <= 20
    ]


def _first_present(candidates: list[str] | None, fallback: list[str]) -> str | None:
    for value in candidates or []:
        if value in fallback:
            return value
    return fallback[0] if fallback else None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _format_p(value: float) -> str:
    if value < 0.0001:
        return "< 0.0001"
    return f"{value:.4f}"


def analyze_workflow_data(
    frame: pd.DataFrame,
    task_key: str,
    target: str | None = None,
    x_field: str | None = None,
    y_field: str | None = None,
    group_field: str | None = None,
    outcome_field: str | None = None,
    feature_fields: list[str] | None = None,
) -> WorkflowAnalysisResult:
    if task_key == "descriptive":
        return _analyze_descriptive(frame, feature_fields)
    if task_key == "correlation":
        return _analyze_correlation(frame, x_field, y_field)
    if task_key == "two_group_mean":
        return _analyze_two_group_mean(frame, group_field, target)
    if task_key == "multi_group_mean":
        return _analyze_multi_group_mean(frame, group_field, target)
    if task_key == "linear_regression":
        return _analyze_linear_regression(frame, target, feature_fields)
    if task_key == "proportion_test":
        return _analyze_proportion_test(frame, group_field, outcome_field)
    raise ValueError("暂不支持该分析任务")


def _analyze_descriptive(frame: pd.DataFrame, fields: list[str] | None) -> WorkflowAnalysisResult:
    numeric = [field for field in (fields or _numeric_columns(frame)) if field in frame.columns and pd.api.types.is_numeric_dtype(frame[field])]
    _require(bool(numeric), "描述统计至少需要 1 个数值字段")
    table: list[dict[str, Any]] = []
    for field in numeric[:12]:
        series = frame[field].dropna().astype(float)
        _require(len(series) > 0, f"字段 {field} 没有有效数值")
        q1, q3 = series.quantile([0.25, 0.75])
        iqr = q3 - q1
        outliers = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
        table.append(
            {
                "字段": field,
                "有效样本": int(series.size),
                "均值": _json_value(series.mean()),
                "中位数": _json_value(series.median()),
                "标准差": _json_value(series.std(ddof=1)) if series.size > 1 else 0,
                "最小值": _json_value(series.min()),
                "最大值": _json_value(series.max()),
                "异常值": outliers,
            }
        )
    return WorkflowAnalysisResult(
        task_key="descriptive",
        title="描述统计与分布诊断",
        method="均值/中位数/标准差/IQR 异常值检测",
        sample_size=int(len(frame)),
        summary=f"已对 {len(table)} 个数值字段完成描述统计，可作为后续建模和检验的基础。",
        metrics=[
            WorkflowAnalysisMetric(label="分析字段", value=str(len(table))),
            WorkflowAnalysisMetric(label="样本行数", value=str(len(frame))),
            WorkflowAnalysisMetric(label="异常值合计", value=str(sum(int(row["异常值"]) for row in table))),
        ],
        table=table,
        interpretation=[
            "均值和中位数差距较大时，说明变量可能存在偏态或极端值影响。",
            "标准差越大，说明该变量在样本中的波动越明显。",
            "IQR 异常值只是一种统计提示，是否删除需要结合实际业务含义判断。",
        ],
        warnings=[],
    )


def _analyze_correlation(frame: pd.DataFrame, x_field: str | None, y_field: str | None) -> WorkflowAnalysisResult:
    numeric = _numeric_columns(frame)
    x = x_field if x_field in numeric else None
    y = y_field if y_field in numeric and y_field != x else None
    if not x or not y:
        selected = numeric[:2]
        _require(len(selected) >= 2, "相关分析至少需要 2 个数值字段")
        x, y = selected[0], selected[1]
    data = frame[[x, y]].dropna().astype(float)
    _require(len(data) >= 3, "相关分析至少需要 3 条有效样本")
    pearson_r, pearson_p = stats.pearsonr(data[x], data[y])
    spearman_r, spearman_p = stats.spearmanr(data[x], data[y])
    direction = "正相关" if pearson_r > 0 else "负相关" if pearson_r < 0 else "无线性相关"
    strength = "较强" if abs(pearson_r) >= 0.7 else "中等" if abs(pearson_r) >= 0.4 else "较弱"
    return WorkflowAnalysisResult(
        task_key="correlation",
        title=f"{x} 与 {y} 的相关分析",
        method="Pearson 相关 + Spearman 秩相关",
        sample_size=int(len(data)),
        summary=f"{x} 与 {y} 的 Pearson 相关系数为 {pearson_r:.3f}，呈{strength}{direction}。",
        metrics=[
            WorkflowAnalysisMetric(label="Pearson r", value=f"{pearson_r:.3f}", note=f"p = {_format_p(float(pearson_p))}"),
            WorkflowAnalysisMetric(label="Spearman ρ", value=f"{spearman_r:.3f}", note=f"p = {_format_p(float(spearman_p))}"),
            WorkflowAnalysisMetric(label="有效样本", value=str(len(data))),
        ],
        table=[
            {"方法": "Pearson", "相关系数": _json_value(pearson_r), "p 值": _format_p(float(pearson_p))},
            {"方法": "Spearman", "相关系数": _json_value(spearman_r), "p 值": _format_p(float(spearman_p))},
        ],
        interpretation=[
            "相关系数为正表示两个变量同向变化，为负表示反向变化。",
            "相关不等于因果；若要解释影响机制，需要进一步结合回归模型和业务背景。",
        ],
        warnings=[],
        chart_data=[{x: _json_value(row[x]), y: _json_value(row[y])} for _, row in data.head(300).iterrows()],
    )


def _analyze_two_group_mean(frame: pd.DataFrame, group_field: str | None, metric_field: str | None) -> WorkflowAnalysisResult:
    groups = [field for field in _categorical_columns(frame) if frame[field].dropna().nunique() == 2]
    numeric = _numeric_columns(frame)
    group = _first_present([group_field] if group_field else None, groups)
    metric = _first_present([metric_field] if metric_field else None, numeric)
    _require(bool(group and metric), "两组均值比较需要 1 个二分类分组字段和 1 个数值字段")
    data = frame[[group, metric]].dropna()
    levels = list(data[group].astype(str).unique())
    _require(len(levels) == 2, "分组字段必须刚好包含两个有效取值")
    a = data.loc[data[group].astype(str) == levels[0], metric].astype(float)
    b = data.loc[data[group].astype(str) == levels[1], metric].astype(float)
    _require(len(a) >= 2 and len(b) >= 2, "每组至少需要 2 条有效样本")
    statistic, p_value = stats.ttest_ind(a, b, equal_var=False)
    diff = float(b.mean() - a.mean())
    se = math.sqrt(float(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
    ci_low, ci_high = diff - 1.96 * se, diff + 1.96 * se
    pooled_sd = math.sqrt(((len(a) - 1) * float(a.var(ddof=1)) + (len(b) - 1) * float(b.var(ddof=1))) / max(len(a) + len(b) - 2, 1))
    cohen_d = diff / pooled_sd if pooled_sd > 0 else 0.0
    return WorkflowAnalysisResult(
        task_key="two_group_mean",
        title=f"{metric} 的两组均值比较",
        method="Welch t 检验",
        sample_size=int(len(data)),
        summary=f"{levels[1]} 组均值比 {levels[0]} 组高 {diff:.3f}，p 值为 {_format_p(float(p_value))}。",
        metrics=[
            WorkflowAnalysisMetric(label="均值差", value=f"{diff:.3f}"),
            WorkflowAnalysisMetric(label="p 值", value=_format_p(float(p_value))),
            WorkflowAnalysisMetric(label="Cohen's d", value=f"{cohen_d:.3f}"),
            WorkflowAnalysisMetric(label="95% CI", value=f"[{ci_low:.3f}, {ci_high:.3f}]"),
        ],
        table=[
            {"分组": levels[0], "样本量": int(len(a)), "均值": _json_value(a.mean()), "标准差": _json_value(a.std(ddof=1))},
            {"分组": levels[1], "样本量": int(len(b)), "均值": _json_value(b.mean()), "标准差": _json_value(b.std(ddof=1))},
        ],
        interpretation=[
            "Welch t 检验不要求两组方差完全相等，更适合真实表格数据的组间均值比较。",
            "p 值小于 0.05 通常说明两组均值差异具有统计显著性，但仍需结合效应量判断实际意义。",
        ],
        warnings=[],
    )


def _analyze_multi_group_mean(frame: pd.DataFrame, group_field: str | None, metric_field: str | None) -> WorkflowAnalysisResult:
    groups = [field for field in _categorical_columns(frame) if frame[field].dropna().nunique() >= 3]
    numeric = _numeric_columns(frame)
    group = _first_present([group_field] if group_field else None, groups)
    metric = _first_present([metric_field] if metric_field else None, numeric)
    _require(bool(group and metric), "ANOVA 需要 1 个多分类分组字段和 1 个数值字段")
    data = frame[[group, metric]].dropna()
    grouped = [(str(level), values.astype(float)) for level, values in data.groupby(group)[metric] if len(values) >= 2]
    _require(len(grouped) >= 3, "ANOVA 至少需要 3 个有效分组，且每组至少 2 条样本")
    statistic, p_value = stats.f_oneway(*[values for _, values in grouped])
    table = [
        {"分组": level, "样本量": int(len(values)), "均值": _json_value(values.mean()), "标准差": _json_value(values.std(ddof=1))}
        for level, values in grouped
    ]
    return WorkflowAnalysisResult(
        task_key="multi_group_mean",
        title=f"{metric} 的多组均值比较",
        method="单因素 ANOVA",
        sample_size=int(sum(len(values) for _, values in grouped)),
        summary=f"{len(grouped)} 个分组的均值差异检验 F = {statistic:.3f}，p 值为 {_format_p(float(p_value))}。",
        metrics=[
            WorkflowAnalysisMetric(label="F 值", value=f"{statistic:.3f}"),
            WorkflowAnalysisMetric(label="p 值", value=_format_p(float(p_value))),
            WorkflowAnalysisMetric(label="分组数量", value=str(len(grouped))),
        ],
        table=table,
        interpretation=[
            "ANOVA 用于判断多个分组的总体均值是否存在差异。",
            "若 ANOVA 显著，后续可进一步做事后比较，判断具体哪些组之间不同。",
        ],
        warnings=[],
    )


def _analyze_linear_regression(frame: pd.DataFrame, target: str | None, features: list[str] | None) -> WorkflowAnalysisResult:
    numeric = _numeric_columns(frame)
    target_field = target if target in numeric else None
    if not target_field:
        target_candidates = [field for field in numeric if any(token in field.lower() for token in ("price", "salary", "wage", "income", "value", "score", "mpg"))]
        target_field = target_candidates[0] if target_candidates else (numeric[0] if numeric else None)
    _require(bool(target_field), "线性回归需要 1 个连续目标变量")
    selected_features = [field for field in (features or []) if field in frame.columns and field != target_field]
    if not selected_features:
        selected_features = [field for field in numeric if field != target_field][:6]
    _require(bool(selected_features), "线性回归至少需要 1 个解释变量")

    data = frame[[target_field, *selected_features]].dropna()
    _require(len(data) >= len(selected_features) + 5, "有效样本量不足，无法稳定估计回归模型")
    y = data[target_field].astype(float)
    encoded_parts: list[pd.DataFrame] = []
    for field in selected_features:
        if pd.api.types.is_numeric_dtype(data[field]):
            encoded_parts.append(data[[field]].astype(float))
        else:
            dummies = pd.get_dummies(data[field].astype(str), prefix=field, drop_first=True, dtype=float)
            encoded_parts.append(dummies)
    x = pd.concat(encoded_parts, axis=1)
    _require(x.shape[1] > 0, "解释变量编码后为空")
    model = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
    rows: list[dict[str, Any]] = []
    for name in model.params.index:
        if name == "const":
            continue
        rows.append(
            {
                "变量": str(name),
                "系数": _json_value(model.params[name]),
                "p 值": _format_p(float(model.pvalues[name])),
                "置信区间下限": _json_value(model.conf_int().loc[name, 0]),
                "置信区间上限": _json_value(model.conf_int().loc[name, 1]),
                "方向": "正向" if model.params[name] > 0 else "负向" if model.params[name] < 0 else "无变化",
            }
        )
    rows = sorted(rows, key=lambda row: abs(float(row["系数"] or 0)), reverse=True)
    strongest = rows[0]["变量"] if rows else "暂无"
    warnings: list[str] = []
    if len(data) < 50 + x.shape[1] * 10:
        warnings.append("样本量相对解释变量数量偏少，模型结果建议作为探索性结论。")
    return WorkflowAnalysisResult(
        task_key="linear_regression",
        title=f"{target_field} 的线性回归建模",
        method="多元线性回归 OLS",
        sample_size=int(len(data)),
        summary=f"模型 R² = {model.rsquared:.3f}，调整 R² = {model.rsquared_adj:.3f}；当前影响幅度最大的变量为 {strongest}。",
        metrics=[
            WorkflowAnalysisMetric(label="R²", value=f"{model.rsquared:.3f}", note="模型解释力"),
            WorkflowAnalysisMetric(label="调整 R²", value=f"{model.rsquared_adj:.3f}"),
            WorkflowAnalysisMetric(label="整体 p 值", value=_format_p(float(model.f_pvalue)) if np.isfinite(model.f_pvalue) else "—"),
            WorkflowAnalysisMetric(label="有效样本", value=str(len(data))),
        ],
        table=rows,
        interpretation=[
            "回归系数为正表示该变量增加时目标变量倾向于增加，为负则倾向于降低。",
            "p 值用于判断单个变量在控制其他变量后是否仍具有统计显著性。",
            "R² 表示模型对目标变量波动的解释比例，但高 R² 不等同于因果关系。",
        ],
        warnings=warnings,
        chart_data=[
            {"actual": _json_value(actual), "predicted": _json_value(predicted)}
            for actual, predicted in zip(y.head(300), model.predict(sm.add_constant(x, has_constant="add")).head(300), strict=False)
        ],
    )


def _success_mask(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float) > 0
    truthy = {"1", "true", "yes", "y", "success", "成功", "是", "购买", "通过"}
    return series.astype(str).str.strip().str.lower().isin(truthy)


def _analyze_proportion_test(frame: pd.DataFrame, group_field: str | None, outcome_field: str | None) -> WorkflowAnalysisResult:
    groups = [field for field in _categorical_columns(frame) if frame[field].dropna().nunique() == 2]
    group = _first_present([group_field] if group_field else None, groups)
    outcomes = [field for field in frame.columns if field != group and frame[field].dropna().nunique() == 2]
    outcome = _first_present([outcome_field] if outcome_field else None, [str(item) for item in outcomes])
    _require(bool(group and outcome), "比例检验需要 1 个二分类分组字段和 1 个二元结果字段")
    data = frame[[group, outcome]].dropna()
    levels = list(data[group].astype(str).unique())
    _require(len(levels) == 2, "分组字段必须刚好包含两个有效取值")
    successes: list[int] = []
    counts: list[int] = []
    table: list[dict[str, Any]] = []
    for level in levels:
        subset = data[data[group].astype(str) == level]
        mask = _success_mask(subset[outcome])
        success = int(mask.sum())
        count = int(len(subset))
        successes.append(success)
        counts.append(count)
        table.append({"分组": level, "样本量": count, "成功数": success, "比例": _json_value(success / count if count else 0)})
    _require(all(count > 0 for count in counts), "每组都需要至少 1 条有效样本")
    statistic, p_value = proportions_ztest(successes, counts)
    diff = successes[1] / counts[1] - successes[0] / counts[0]
    return WorkflowAnalysisResult(
        task_key="proportion_test",
        title=f"{outcome} 的两组比例检验",
        method="两比例 z 检验",
        sample_size=int(sum(counts)),
        summary=f"{levels[1]} 组比例比 {levels[0]} 组高 {diff * 100:.2f} 个百分点，p 值为 {_format_p(float(p_value))}。",
        metrics=[
            WorkflowAnalysisMetric(label="比例差", value=f"{diff * 100:.2f}%"),
            WorkflowAnalysisMetric(label="z 值", value=f"{statistic:.3f}"),
            WorkflowAnalysisMetric(label="p 值", value=_format_p(float(p_value))),
        ],
        table=table,
        interpretation=[
            "两比例 z 检验用于比较两个分组在二元结果上的发生率或成功率差异。",
            "若 p 值较小，说明观察到的比例差异不太可能仅由随机波动造成。",
        ],
        warnings=[],
    )
