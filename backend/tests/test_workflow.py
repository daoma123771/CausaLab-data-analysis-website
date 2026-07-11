from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_workflow_inspect_recommends_regression_for_housing_like_data() -> None:
    rows = ["price,income,rooms,age,region"]
    for index in range(80):
        region = ["east", "west", "north", "south"][index % 4]
        rows.append(f"{180 + index * 2},{40 + index * 0.5},{2 + index % 5},{5 + index % 30},{region}")
    content = "\n".join(rows).encode("utf-8")

    response = client.post(
        "/api/workflow/inspect",
        files={"file": ("housing.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 80
    assert data["column_count"] == 5
    assert "数据包含 80 行" in data["dataset_summary"]

    variable_names = {item["name"] for item in data["variables"]}
    assert {"price", "income", "rooms", "age", "region"}.issubset(variable_names)

    tasks = {item["key"]: item for item in data["recommended_tasks"]}
    assert tasks["linear_regression"]["suitability"] == "ready"
    assert "price" in tasks["linear_regression"]["candidate_fields"]["target"]
    assert tasks["correlation"]["suitability"] == "ready"
    assert tasks["descriptive"]["suitability"] == "ready"


def test_workflow_inspect_reports_sample_gap_for_small_data() -> None:
    content = "\n".join([
        "salary,experience,degree",
        "6000,1,bachelor",
        "6500,2,bachelor",
        "7200,3,master",
        "7600,4,master",
        "8000,5,master",
    ]).encode("utf-8")

    response = client.post(
        "/api/workflow/inspect",
        files={"file": ("salary.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    tasks = {item["key"]: item for item in response.json()["recommended_tasks"]}
    assert tasks["linear_regression"]["sample_gap"] is not None
    assert tasks["linear_regression"]["suitability"] == "needs_input"
    assert "还差" in tasks["linear_regression"]["sample_assessment"]


def test_workflow_analyze_linear_regression() -> None:
    rows = ["price,income,rooms,age,region"]
    for index in range(100):
        region = ["east", "west", "north", "south"][index % 4]
        price = 120 + index * 1.7 + (index % 5) * 3
        rows.append(f"{price},{40 + index * 0.4},{2 + index % 5},{5 + index % 30},{region}")
    content = "\n".join(rows).encode("utf-8")

    response = client.post(
        "/api/workflow/analyze",
        data={
            "task_key": "linear_regression",
            "target": "price",
            "feature_fields": '["income","rooms","age"]',
        },
        files={"file": ("housing.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_key"] == "linear_regression"
    assert data["sample_size"] == 100
    assert any(metric["label"] == "R²" for metric in data["metrics"])
    assert any(row["变量"] == "income" for row in data["table"])
    assert data["interpretation"]


def test_workflow_analyze_correlation() -> None:
    content = "\n".join([
        "x,y",
        "1,2",
        "2,4",
        "3,6",
        "4,8",
        "5,10",
    ]).encode("utf-8")

    response = client.post(
        "/api/workflow/analyze",
        data={"task_key": "correlation", "x_field": "x", "y_field": "y"},
        files={"file": ("corr.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_key"] == "correlation"
    assert data["metrics"][0]["label"] == "Pearson r"
    assert float(data["metrics"][0]["value"]) > 0.99
