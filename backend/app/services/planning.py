import math
from collections.abc import Callable

import numpy as np
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize

from app.schemas.planning import (
    ContinuousPlanRequest,
    PlanResponse,
    PowerCurvePoint,
    ProportionPlanRequest,
)


def _sample_sizes(n_control_raw: float, ratio: float) -> tuple[int, int]:
    control = math.ceil(float(n_control_raw))
    treatment = math.ceil(float(n_control_raw) * ratio)
    return control, treatment


def _estimated_days(total: int, daily_traffic: int | None) -> int | None:
    return math.ceil(total / daily_traffic) if daily_traffic else None


def _build_power_curve(
    required_control: int,
    ratio: float,
    power_at: Callable[[int], float],
) -> list[PowerCurvePoint]:
    lower = max(10, math.ceil(required_control * 0.2))
    upper = max(lower + 1, math.ceil(required_control * 1.6))
    control_sizes = np.unique(np.linspace(lower, upper, 18, dtype=int))
    points: list[PowerCurvePoint] = []
    for control_size in control_sizes:
        treatment_size = math.ceil(int(control_size) * ratio)
        points.append(
            PowerCurvePoint(
                total_sample_size=int(control_size) + treatment_size,
                power=round(float(power_at(int(control_size))), 4),
            )
        )
    return points


def plan_proportion_experiment(payload: ProportionPlanRequest) -> PlanResponse:
    effect_size = abs(proportion_effectsize(payload.target_rate, payload.baseline_rate))
    solver = NormalIndPower()
    n_control_raw = solver.solve_power(
        effect_size=effect_size,
        alpha=payload.alpha,
        power=payload.power,
        ratio=payload.allocation_ratio,
        alternative="two-sided",
    )
    control, treatment = _sample_sizes(n_control_raw, payload.allocation_ratio)
    total = control + treatment
    absolute_effect = abs(payload.target_rate - payload.baseline_rate)

    warnings: list[str] = []
    if min(payload.baseline_rate, payload.target_rate) < 0.01:
        warnings.append("转化率低于 1%，建议结合更长实验周期并检查稀有事件波动。")
    if payload.allocation_ratio < 0.5 or payload.allocation_ratio > 2:
        warnings.append("分组比例较不均衡，总样本量会高于 1:1 分组。")

    curve = _build_power_curve(
        control,
        payload.allocation_ratio,
        lambda n: solver.power(
            effect_size=effect_size,
            nobs1=n,
            alpha=payload.alpha,
            ratio=payload.allocation_ratio,
            alternative="two-sided",
        ),
    )

    explanation = (
        f"当对照组转化率为 {payload.baseline_rate:.1%}，希望检测到实验组达到 "
        f"{payload.target_rate:.1%} 时，在显著性水平 {payload.alpha:.3f}、"
        f"统计功效 {payload.power:.0%} 下，建议对照组至少 {control} 个样本，"
        f"实验组至少 {treatment} 个样本。"
    )
    return PlanResponse(
        metric_type="proportion",
        control_sample_size=control,
        treatment_sample_size=treatment,
        total_sample_size=total,
        effect_size=round(effect_size, 6),
        minimum_detectable_effect=round(absolute_effect, 6),
        alpha=payload.alpha,
        target_power=payload.power,
        estimated_days=_estimated_days(total, payload.daily_traffic),
        curve=curve,
        explanation=explanation,
        warnings=warnings,
    )


def plan_continuous_experiment(payload: ContinuousPlanRequest) -> PlanResponse:
    effect_size = payload.mean_difference / payload.standard_deviation
    solver = TTestIndPower()
    n_control_raw = solver.solve_power(
        effect_size=effect_size,
        alpha=payload.alpha,
        power=payload.power,
        ratio=payload.allocation_ratio,
        alternative="two-sided",
    )
    control, treatment = _sample_sizes(n_control_raw, payload.allocation_ratio)
    total = control + treatment

    warnings: list[str] = []
    if effect_size < 0.2:
        warnings.append("标准化效应小于 0.2，需要较大样本才能稳定检出。")
    if effect_size > 1.5:
        warnings.append("预期效应较大，请确认最小均值差和标准差的单位一致。")
    if payload.allocation_ratio < 0.5 or payload.allocation_ratio > 2:
        warnings.append("分组比例较不均衡，总样本量会高于 1:1 分组。")

    curve = _build_power_curve(
        control,
        payload.allocation_ratio,
        lambda n: solver.power(
            effect_size=effect_size,
            nobs1=n,
            alpha=payload.alpha,
            ratio=payload.allocation_ratio,
            alternative="two-sided",
        ),
    )
    explanation = (
        f"希望检测到至少 {payload.mean_difference:g} 的均值差，假设总体标准差为 "
        f"{payload.standard_deviation:g}，对应 Cohen's d={effect_size:.3f}。"
        f"在显著性水平 {payload.alpha:.3f}、统计功效 {payload.power:.0%} 下，"
        f"建议对照组至少 {control} 个样本，实验组至少 {treatment} 个样本。"
    )
    return PlanResponse(
        metric_type="continuous",
        control_sample_size=control,
        treatment_sample_size=treatment,
        total_sample_size=total,
        effect_size=round(effect_size, 6),
        minimum_detectable_effect=payload.mean_difference,
        alpha=payload.alpha,
        target_power=payload.power,
        estimated_days=_estimated_days(total, payload.daily_traffic),
        curve=curve,
        explanation=explanation,
        warnings=warnings,
    )

