from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_proportion_sample_size_plan() -> None:
    response = client.post(
        "/api/planning/proportion",
        json={
            "baseline_rate": 0.10,
            "target_rate": 0.12,
            "alpha": 0.05,
            "power": 0.80,
            "allocation_ratio": 1.0,
            "daily_traffic": 500,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["metric_type"] == "proportion"
    assert 3700 <= result["control_sample_size"] <= 4000
    assert result["control_sample_size"] == result["treatment_sample_size"]
    assert result["estimated_days"] >= 15
    assert len(result["curve"]) >= 10


def test_continuous_sample_size_plan() -> None:
    response = client.post(
        "/api/planning/continuous",
        json={
            "mean_difference": 5,
            "standard_deviation": 10,
            "alpha": 0.05,
            "power": 0.80,
            "allocation_ratio": 1.0,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["metric_type"] == "continuous"
    assert 60 <= result["control_sample_size"] <= 70
    assert result["effect_size"] == 0.5


def test_equal_proportion_rates_are_rejected() -> None:
    response = client.post(
        "/api/planning/proportion",
        json={"baseline_rate": 0.1, "target_rate": 0.1},
    )
    assert response.status_code == 422

