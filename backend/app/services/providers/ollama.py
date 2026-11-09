from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import LLMResponseError
from app.services.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url = settings.ollama_base_url,
            timeout = settings.ollama_timeout / 1000.0,
            trust_env = False
        )
    
    def generate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        r = self._client.post("/api/chat", json={
            "model": model,
            "messages": messages,
            "stream": False,
            "think": settings.ollama_think,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        })
        r.raise_for_status()
        message = r.json().get("message", {})
        content = str(message.get("content") or "").strip()
        if not content:
            content = str(message.get("thinking") or "").strip()
        if not content:
            raise LLMResponseError("Ollama returned an empty response")
        return content
