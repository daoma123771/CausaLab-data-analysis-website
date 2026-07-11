from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.reporting import AnalysisReportRequest
from app.services.reporting import build_analysis_report


payload = AnalysisReportRequest(
    project_name="首页改版 A/B 实验",
    analyst="CausaLab 演示用户",
    metric_name="注册转化率",
    metric_type="proportion",
    method="两比例 Z 检验 + 参数 Bootstrap",
    control_size=5000,
    treatment_size=5000,
    control_value=0.10,
    treatment_value=0.13,
    absolute_effect=0.03,
    relative_effect_percent=30.0,
    p_value=0.00001,
    ci_lower=0.017,
    ci_upper=0.043,
    decision="拒绝原假设",
    conclusion="实验组注册转化率显著高于对照组，可在业务价值与风险评估后考虑推广。",
    quality_score=88,
    notes=[
        "统计显著不等同于业务收益，需要结合实施成本。",
        "建议持续监控上线后的长期指标与护栏指标。",
    ],
)

output = ROOT / "examples" / "CausaLab_示例分析报告.docx"
output.write_bytes(build_analysis_report(payload))
print(output)
