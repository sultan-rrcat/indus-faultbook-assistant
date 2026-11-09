class AssistantError(Exception):
    """Base class for expected application errors."""


class LLMResponseError(AssistantError):
    """Raised when the LLM returns an unusable or empty response."""


class SQLValidationError(AssistantError):
    """Raised when generated SQL is unsafe or cannot be executed."""
