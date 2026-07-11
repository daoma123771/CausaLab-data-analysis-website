from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_proportion_analysis_detects_lift() -> None:
    response = client.post(
        "/api/analysis/proportion",
        json={
            "control_total": 5000,
            "control_success": 500,
            "treatment_total": 5000,
            "treatment_success": 650,
            "alternative": "greater",
            "bootstrap_iterations": 1000,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["significant"] is True
    assert result["absolute_effect"] == 0.03
    assert result["ci_lower"] > 0
    assert sum(item["count"] for item in result["bootstrap_histogram"]) == 1000


def test_proportion_analysis_rejects_invalid_counts() -> None:
    response = client.post(
        "/api/analysis/proportion",
        json={
            "control_total": 100,
            "control_success": 101,
            "treatment_total": 100,
            "treatment_success": 10,
        },
    )
    assert response.status_code == 422


def test_continuous_analysis_detects_difference() -> None:
    response = client.post(
        "/api/analysis/continuous",
        json={
            "control_values": [9, 10, 11, 10, 9, 11, 10, 10],
            "treatment_values": [13, 14, 15, 14, 13, 15, 14, 14],
            "alternative": "greater",
            "bootstrap_iterations": 1000,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["method"].startswith("Welch")
    assert result["significant"] is True
    assert result["absolute_effect"] == 4.0


def test_continuous_equal_constants_are_handled() -> None:
    response = client.post(
        "/api/analysis/continuous",
        json={
            "control_values": [5, 5, 5],
            "treatment_values": [5, 5, 5],
            "bootstrap_iterations": 500,
        },
    )
    assert response.status_code == 200
    assert response.json()["p_value"] == 1.0
