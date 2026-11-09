from typing import Any

import google.genai as genai
from google.genai import types

from app.core.config import settings
from app.services.providers.base import LLMProvider

_client: "genai.Client | None" = None

def _build_http_options() -> "types.HttpOptions | None":
    proxy = settings.https_proxy or settings.http_proxy
    if not proxy:
        return None
    return types.HttpOptions(client_args={"proxy": proxy})

def _get_client() -> "genai.Client":
    global _client
    if _client is None:
        if not settings.gemini_api_key.get_secret_value():
            raise ValueError("GEMINI_API_KEY is not set")
        _client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=_build_http_options(),
        )
    return _client

class GeminiProvider(LLMProvider):
    def generate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        prompt = "\n\n".join(m["content"] for m in messages)
        resp = _get_client().models.generate_content(
            model = model,
            contents = prompt,
            config = types.GenerateContentConfig(
                max_output_tokens = max_tokens,
                temperature = temperature
            )
        )
        return resp.text or ""
    

