import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app


client = TestClient(app)


def test_inspect_csv_detects_quality_issues() -> None:
    content = b"user_id,group,revenue\n1,A,10\n2,A,12\n3,B,100\n3,B,100\n4,B,\n"
    response = client.post("/api/data/inspect", files={"file": ("experiment.csv", content, "text/csv")})
    assert response.status_code == 200
    result = response.json()
    assert result["row_count"] == 5
    assert result["duplicate_rows"] == 1
    assert result["total_missing_cells"] == 1
    assert result["detected_group_column"] == "group"
    assert sum(item["count"] for item in result["group_distribution"]) == 5
    assert any(column["outlier_count"] is not None for column in result["columns"])


def test_inspect_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["user_id", "variant", "converted"])
    sheet.append([1, "A", 0])
    sheet.append([2, "B", 1])
    buffer = io.BytesIO()
    workbook.save(buffer)
    response = client.post(
        "/api/data/inspect",
        files={"file": ("experiment.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    assert response.json()["file_type"] == "xlsx"


def test_rejects_unsupported_file() -> None:
    response = client.post("/api/data/inspect", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 422
