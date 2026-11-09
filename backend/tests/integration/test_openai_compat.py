import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.main import app
from app.schemas.chat import ChatResponse


class FakeChatService:
    def __init__(self) -> None:
        self.questions: list[str] = []
        self.completions: list[list[dict[str, str]]] = []

    def answer(self, question: str) -> ChatResponse:
        self.questions.append(question)
        return ChatResponse(answer=f"echo: {question}", sql="SELECT 1", row_count=1)

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.completions.append(messages)
        return '{"follow_ups": ["one", "two", "three"]}'


@pytest.fixture
def fake_service() -> Generator[FakeChatService]:
    service = FakeChatService()
    app.dependency_overrides[get_chat_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_models_endpoint_lists_assistant(fake_service: FakeChatService) -> None:
    with TestClient(app) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "faultbook-assistant"


def test_chat_completions_returns_last_user_message(fake_service: FakeChatService) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "faultbook-assistant",
                "messages": [
                    {"role": "system", "content": "You are a helper."},
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "an answer"},
                    {"role": "user", "content": "How many faults today?"},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "echo: How many faults today?"
    assert fake_service.questions == ["How many faults today?"]


def test_chat_completions_streams_sse(fake_service: FakeChatService) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "faultbook-assistant",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in response.text

    chunks = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert chunks[0]["choices"][0]["delta"]["content"] == "echo: hello"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_chat_completions_rejects_missing_user_message(fake_service: FakeChatService) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "faultbook-assistant",
                "messages": [{"role": "system", "content": "System only"}],
            },
        )

    assert response.status_code == 400
    assert fake_service.questions == []


def test_auxiliary_task_bypasses_sql_pipeline(fake_service: FakeChatService) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "faultbook-assistant",
                "messages": [
                    {
                        "role": "user",
                        "content": "### Task:\nSuggest 3-5 follow-up questions.\n"
                        "### Chat History:\n<chat_history>How many faults today?</chat_history>",
                    },
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"].startswith('{"follow_ups"')
    assert fake_service.questions == []
    assert len(fake_service.completions) == 1
    assert fake_service.completions[0][0]["content"].startswith("### Task:")
