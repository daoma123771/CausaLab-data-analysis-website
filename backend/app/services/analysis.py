import math

import numpy as np
from scipy import stats

from app.schemas.analysis import (
    AnalysisResponse,
    ContinuousAnalysisRequest,
    HistogramBin,
    ProportionAnalysisRequest,
)


def _p_value_from_statistic(statistic: float, alternative: str, distribution: object) -> float:
    if alternative == "greater":
        return float(distribution.sf(statistic))
    if alternative == "less":
        return float(distribution.cdf(statistic))
    return float(2 * distribution.sf(abs(statistic)))


def _histogram(values: np.ndarray, bins: int = 24) -> list[HistogramBin]:
    counts, edges = np.histogram(values, bins=bins)
    return [
        HistogramBin(lower=float(edges[index]), upper=float(edges[index + 1]), count=int(count))
        for index, count in enumerate(counts)
    ]


def _direction_matches(effect: float, alternative: str) -> bool:
    if alternative == "greater":
        return effect > 0
    if alternative == "less":
        return effect < 0
    return True


def _decision(significant: bool, effect: float, alternative: str) -> tuple[str, str]:
    direction_ok = _direction_matches(effect, alternative)
    if significant and direction_ok:
        direction = "提升" if effect > 0 else "下降"
        return "拒绝原假设", f"实验组相对对照组呈现统计显著的{direction}，可进入业务价值评估。"
    if significant:
        return "不支持预设方向", "差异达到统计显著，但方向与预设的单侧假设相反，不支持原实验假设。"
    return "暂不拒绝原假设", "当前数据不足以证明两组存在统计显著差异，建议检查功效或继续积累样本。"


def analyze_proportion(payload: ProportionAnalysisRequest) -> AnalysisResponse:
    control = payload.control_success / payload.control_total
    treatment = payload.treatment_success / payload.treatment_total
    effect = treatment - control
    pooled = (payload.control_success + payload.treatment_success) / (
        payload.control_total + payload.treatment_total
    )
    standard_error = math.sqrt(
        pooled * (1 - pooled) * (1 / payload.control_total + 1 / payload.treatment_total)
    )
    if standard_error == 0:
        statistic = 0.0 if effect == 0 else math.copysign(math.inf, effect)
    else:
        statistic = effect / standard_error
    p_value = _p_value_from_statistic(statistic, payload.alternative, stats.norm)

    rng = np.random.default_rng(payload.random_seed)
    control_boot = rng.binomial(payload.control_total, control, payload.bootstrap_iterations) / payload.control_total
    treatment_boot = rng.binomial(payload.treatment_total, treatment, payload.bootstrap_iterations) / payload.treatment_total
    bootstrap_effects = treatment_boot - control_boot
    lower, upper = np.quantile(bootstrap_effects, [payload.alpha / 2, 1 - payload.alpha / 2])
    significant = p_value < payload.alpha
    direction_ok = _direction_matches(effect, payload.alternative)
    decision, conclusion = _decision(significant, effect, payload.alternative)
    warnings: list[str] = []
    if min(payload.control_success, payload.treatment_success) < 5:
        warnings.append("至少一组成功事件少于 5，Z 检验近似可能不稳定，建议增加样本或采用精确检验。")
    if control == 0:
        relative_effect = None
        warnings.append("对照组比例为 0，无法计算相对提升率。")
    else:
        relative_effect = effect / control * 100

    return AnalysisResponse(
        metric_type="proportion",
        method="两比例 Z 检验 + 参数 Bootstrap",
        control_size=payload.control_total,
        treatment_size=payload.treatment_total,
        control_value=control,
        treatment_value=treatment,
        absolute_effect=effect,
        relative_effect_percent=relative_effect,
        statistic=statistic,
        p_value=p_value,
        alpha=payload.alpha,
        confidence_level=1 - payload.alpha,
        ci_lower=float(lower),
        ci_upper=float(upper),
        significant=significant,
        direction_matches=direction_ok,
        decision=decision,
        conclusion=conclusion,
        bootstrap_iterations=payload.bootstrap_iterations,
        bootstrap_histogram=_histogram(bootstrap_effects),
        warnings=warnings,
    )


def analyze_continuous(payload: ContinuousAnalysisRequest) -> AnalysisResponse:
    control_values = np.asarray(payload.control_values, dtype=float)
    treatment_values = np.asarray(payload.treatment_values, dtype=float)
    if not np.isfinite(control_values).all() or not np.isfinite(treatment_values).all():
        raise ValueError("数据中不能包含 NaN 或无穷值")

    control = float(control_values.mean())
    treatment = float(treatment_values.mean())
    effect = treatment - control
    test = stats.ttest_ind(
        treatment_values,
        control_values,
        equal_var=False,
        alternative=payload.alternative,
    )
    statistic = float(test.statistic)
    p_value = float(test.pvalue)
    if not math.isfinite(statistic) or not math.isfinite(p_value):
        if np.all(control_values == control_values[0]) and np.all(treatment_values == treatment_values[0]):
            statistic = 0.0 if effect == 0 else math.copysign(math.inf, effect)
            p_value = 1.0 if effect == 0 else 0.0
        else:
            raise ValueError("当前数据无法完成 t 检验，请检查样本方差")

    rng = np.random.default_rng(payload.random_seed)
    bootstrap_effects = np.empty(payload.bootstrap_iterations)
    for index in range(payload.bootstrap_iterations):
        control_sample = rng.choice(control_values, size=control_values.size, replace=True)
        treatment_sample = rng.choice(treatment_values, size=treatment_values.size, replace=True)
        bootstrap_effects[index] = treatment_sample.mean() - control_sample.mean()
    lower, upper = np.quantile(bootstrap_effects, [payload.alpha / 2, 1 - payload.alpha / 2])
    significant = p_value < payload.alpha
    direction_ok = _direction_matches(effect, payload.alternative)
    decision, conclusion = _decision(significant, effect, payload.alternative)
    warnings: list[str] = []
    if min(control_values.size, treatment_values.size) < 30:
        warnings.append("至少一组样本量小于 30，请结合分布形态和 Bootstrap 区间谨慎解释。")
    relative_effect = None if control == 0 else effect / abs(control) * 100

    return AnalysisResponse(
        metric_type="continuous",
        method="Welch t 检验 + 非参数 Bootstrap",
        control_size=int(control_values.size),
        treatment_size=int(treatment_values.size),
        control_value=control,
        treatment_value=treatment,
        absolute_effect=effect,
        relative_effect_percent=relative_effect,
        statistic=statistic,
        p_value=p_value,
        alpha=payload.alpha,
        confidence_level=1 - payload.alpha,
        ci_lower=float(lower),
        ci_upper=float(upper),
        significant=significant,
        direction_matches=direction_ok,
        decision=decision,
        conclusion=conclusion,
        bootstrap_iterations=payload.bootstrap_iterations,
        bootstrap_histogram=_histogram(bootstrap_effects),
        warnings=warnings,
    )
