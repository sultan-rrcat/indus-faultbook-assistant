from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        model: str,
        messages: list[dict[str,Any]],
        *,
        temperature: float,
        max_tokens: int
    ) -> str :
        """Return the model's text response to 'messages'(OpenAI style message list)"""
        raise NotImplementedError
