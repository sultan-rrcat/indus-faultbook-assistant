import pyodbc
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_degraded_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(*args: object, **kwargs: object) -> None:
        raise pyodbc.Error("database unavailable")

    monkeypatch.setattr(pyodbc, "connect", _fail)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "down"
    assert body["status"] == "degraded"
    assert body["llm_provider"] in {"ollama", "gemini"}
    assert body["model"]


def test_chat_rejects_empty_question() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"question": ""})

    assert response.status_code == 422
