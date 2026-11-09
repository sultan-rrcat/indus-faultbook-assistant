from functools import lru_cache

from app.services.nl2sql.orchestrator import ChatService
from app.services.providers.base import LLMProvider
from app.services.providers.factory import get_model_name, get_provider


@lru_cache
def _provider() -> LLMProvider:
    return get_provider()

def get_chat_service() -> ChatService:
    return ChatService(provider=_provider(), model=get_model_name())

def get_current_user() -> str:
    return "service-account"
