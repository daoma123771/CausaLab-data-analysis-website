from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "name": "CausaLab",
        "version": "1.0.0",
    }


def test_module_catalog() -> None:
    response = client.get("/api/modules")
    assert response.status_code == 200
    modules = response.json()
    assert len(modules) == 6
    assert {item["key"] for item in modules} == {
        "planning",
        "quality",
        "analysis",
        "workflow",
        "robustness",
        "report",
    }
