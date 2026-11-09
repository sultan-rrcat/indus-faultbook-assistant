import json
import logging
import re
from collections.abc import Callable
from typing import Any

from app.core.exceptions import LLMResponseError
from app.schemas.chat import ChatResponse
from app.services.nl2sql.executor import execute_sql
from app.services.nl2sql.prompts import build_sql_prompt, build_summary_prompt
from app.services.providers.base import LLMProvider
from app.services.schema_registry import get_schema

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_OPEN_FENCE_RE = re.compile(r"```(?:sql)?\s*", re.IGNORECASE)

Executor = Callable[[str], list[dict[str, Any]]]

def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    open_match = _OPEN_FENCE_RE.search(text)
    if open_match:
        return text[open_match.end():].strip()
    return text.strip()

class ChatService:
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        executor: Executor | None = None
    ) -> None:
        self._provider = provider
        self._model = model
        self._executor = executor or execute_sql

    def _generate_sql(self, question: str) -> str:
        prompt = build_sql_prompt(get_schema(), question)
        messages = [
            {"role": "system", "content": "You are an expert SQL Server query generator."},
            {"role": "user", "content": prompt}
        ]
        raw = self._provider.generate(
            self._model,
            messages,
            temperature=0.0,
            max_tokens=512
        )
        sql = _strip_fences(raw)
        if not sql:
            raise LLMResponseError("The language model returned an empty SQL query.")
        return sql
    
    def _summarize(self, question: str, rows: list[dict[str, Any]]) -> str:
        results = json.dumps(rows, default=str, ensure_ascii=False)
        prompt = build_summary_prompt(question, results)
        messages = [
            {"role": "system", "content": "You are an advanced data analyst."},
            {"role": "user", "content": prompt},
        ]
        return self._provider.generate(
            self._model,
            messages,
            temperature=0.2,
            max_tokens=2048
        )
    def answer(self, question: str) -> ChatResponse:
        sql = self._generate_sql(question)
        logger.info("Generated SQL: %s", sql)
        
        rows = self._executor(sql)
        summary = self._summarize(question, rows)

        return ChatResponse(answer=summary, sql=sql, row_count=len(rows))

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Answer a plain chat request without the NL2SQL pipeline.

        Used for UI helper tasks (titles, tags, follow-up suggestions) that
        Open WebUI sends to the selected model.
        """
        return self._provider.generate(
            self._model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
