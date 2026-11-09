from typing import Any

import pytest

from app.core.exceptions import LLMResponseError
from app.services.providers.ollama import OllamaProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, message: dict[str, Any] | None = None) -> None:
        self._message = message if message is not None else {"content": "ok"}
        self.last_call: tuple[str, dict[str, Any]] | None = None

    def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
        self.last_call = (url, json)
        return _FakeResponse({"message": self._message})


def test_generate_posts_to_chat_endpoint() -> None:
    provider = OllamaProvider()
    fake_client = _FakeClient()
    provider._client = fake_client  # type: ignore[assignment]

    result = provider.generate(
        "qwen2.5-coder:7b",
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=16,
    )

    assert result == "ok"
    assert fake_client.last_call is not None
    url, payload = fake_client.last_call
    assert url == "/api/chat"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.0, "num_predict": 16}


def test_generate_falls_back_to_thinking_when_content_empty() -> None:
    provider = OllamaProvider()
    fake_client = _FakeClient({"content": "", "thinking": "SELECT 1"})
    provider._client = fake_client  # type: ignore[assignment]

    result = provider.generate(
        "qwen2.5-coder:7b",
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=16,
    )

    assert result == "SELECT 1"


def test_generate_raises_when_response_is_empty() -> None:
    provider = OllamaProvider()
    fake_client = _FakeClient({"content": "   ", "thinking": ""})
    provider._client = fake_client  # type: ignore[assignment]

    with pytest.raises(LLMResponseError):
        provider.generate(
            "qwen2.5-coder:7b",
            [{"role": "user", "content": "hi"}],
            temperature=0.0,
            max_tokens=16,
        )
