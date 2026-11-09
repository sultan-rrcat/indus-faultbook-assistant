from typing import Any

import pytest

from app.core.exceptions import LLMResponseError
from app.services.nl2sql.orchestrator import ChatService


class _FakeProvider:
    def __init__(self, sql: str = "```sql\nSELECT TOP 3 * FROM fault_bookv3\n```") -> None:
        self._sql = sql
        self.calls = 0

    def generate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.calls += 1
        if self.calls == 1:
            return self._sql
        return "Three faults found."


def test_answer_strips_fences_and_counts_rows() -> None:
    provider = _FakeProvider()
    service = ChatService(
        provider=provider,
        model="fake",
        executor=lambda sql: [{"fault_id": 1}, {"fault_id": 2}, {"fault_id": 3}],
    )

    result = service.answer("recent faults")

    assert result.sql == "SELECT TOP 3 * FROM fault_bookv3"
    assert result.row_count == 3
    assert result.answer == "Three faults found."
    assert provider.calls == 2


def test_answer_rejects_empty_sql_before_execution() -> None:
    provider = _FakeProvider(sql="   ")
    executed: list[str] = []
    service = ChatService(
        provider=provider,
        model="fake",
        executor=lambda sql: executed.append(sql) or [],
    )

    with pytest.raises(LLMResponseError):
        service.answer("recent faults")

    assert executed == []
    assert provider.calls == 1
