import io

from docx import Document
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


REPORT_PAYLOAD = {
    "project_name": "首页改版实验",
    "analyst": "测试用户",
    "metric_name": "注册转化率",
    "metric_type": "proportion",
    "method": "两比例 Z 检验 + 参数 Bootstrap",
    "control_size": 5000,
    "treatment_size": 5000,
    "control_value": 0.10,
    "treatment_value": 0.13,
    "absolute_effect": 0.03,
    "relative_effect_percent": 30.0,
    "p_value": 0.00001,
    "ci_lower": 0.017,
    "ci_upper": 0.043,
    "decision": "拒绝原假设",
    "conclusion": "实验组注册转化率显著高于对照组。",
    "quality_score": 88,
}


def test_export_analysis_docx() -> None:
    response = client.post("/api/reports/analysis.docx", json=REPORT_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert response.content[:2] == b"PK"
    document = Document(io.BytesIO(response.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "首页改版实验" in text
    assert "执行摘要" in text
    assert "实验组注册转化率显著高于对照组" in text


def test_report_validation() -> None:
    payload = {**REPORT_PAYLOAD, "control_size": 1}
    response = client.post("/api/reports/analysis.docx", json=payload)
    assert response.status_code == 422
