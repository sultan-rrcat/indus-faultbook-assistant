import os
from collections.abc import Iterator

import httpx
import pyodbc
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.e2e


def _db_reachable() -> bool:
    try:
        connection = pyodbc.connect(settings.db_connection_string, timeout=5)
        try:
            connection.cursor().execute("SELECT 1")
        finally:
            connection.close()
    except Exception:
        return False
    return True


def _llm_reachable() -> bool:
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        response.raise_for_status()
    except Exception:
        return False

    models = {model["name"] for model in response.json().get("models", [])}
    return settings.ollama_model in models


def _fault_count() -> int:
    connection = pyodbc.connect(settings.db_connection_string, timeout=5)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.fault_bookv3")
        return int(cursor.fetchone()[0])
    finally:
        connection.close()


@pytest.fixture(scope="module")
def live_client() -> Iterator[TestClient]:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run end-to-end tests")
    if not _db_reachable():
        pytest.skip("SQL Server is not reachable with the current settings")
    with TestClient(app) as client:
        yield client


def test_health_reports_database_up(live_client: TestClient) -> None:
    response = live_client.get("/api/v1/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["db"] == "up"
    assert body["status"] == "ok"


def test_chat_end_to_end_against_real_db_and_llm(live_client: TestClient) -> None:
    if not _llm_reachable():
        pytest.skip(f"Ollama model {settings.ollama_model!r} is not available")

    expected_count = _fault_count()

    response = live_client.post(
        "/api/v1/chat",
        json={"question": "How many fault records are in the fault_bookv3 table?"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sql"].strip().lower().startswith("select")
    assert body["row_count"] >= 1
    assert body["answer"].strip()

    normalized_answer = body["answer"].replace(",", "")
    assert str(expected_count) in normalized_answer
