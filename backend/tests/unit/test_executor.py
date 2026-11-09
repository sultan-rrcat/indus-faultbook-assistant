import pytest

from app.core.exceptions import SQLValidationError
from app.services.nl2sql.executor import validate_sql


@pytest.mark.parametrize("sql", ["", "   ", "\n\t"])
def test_validate_sql_rejects_empty_query(sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


def test_validate_sql_rejects_prose() -> None:
    prose = "We need to write a SELECT statement. Thus output: SELECT 1"

    with pytest.raises(SQLValidationError):
        validate_sql(prose)


def test_validate_sql_rejects_non_select() -> None:
    with pytest.raises(SQLValidationError):
        validate_sql("DELETE FROM [dbo].[fault_bookv3]")


def test_validate_sql_rejects_multiple_statements() -> None:
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT 1; SELECT 2;")


def test_validate_sql_rejects_invalid_top_placement() -> None:
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT a FROM [dbo].[t] ORDER BY b DESC TOP 3;")


def test_validate_sql_accepts_select() -> None:
    sql = "SELECT TOP (3) [fault_id] FROM [dbo].[fault_bookv3] ORDER BY [fault_time] DESC;"

    assert validate_sql(sql) == sql
