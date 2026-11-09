
from app.core.config import settings
from app.services.providers.base import LLMProvider


def get_provider() -> LLMProvider:
    if settings.llm_provider == "ollama":
        from app.services.providers.ollama import OllamaProvider
        return OllamaProvider()

    from app.services.providers.gemini import GeminiProvider
    return GeminiProvider()

def get_model_name() -> str:
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    return settings.gemini_model