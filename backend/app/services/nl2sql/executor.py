import logging
from typing import Any

import pyodbc
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.core.config import settings
from app.core.exceptions import SQLValidationError

logger = logging.getLogger(__name__)

MAX_ROWS = 1000

def _safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<binary>"
    return value

def validate_sql(sql_query: str) -> str:
    if not sql_query or not sql_query.strip():
        raise SQLValidationError("Refusing to execute an empty SQL query.")

    try:
        statements = [s for s in sqlglot.parse(sql_query, read="tsql") if s is not None]
    except ParseError as err:
        raise SQLValidationError(f"Generated SQL is not valid T-SQL: {err}") from err

    if len(statements) != 1:
        raise SQLValidationError("Expected exactly one SQL statement.")

    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLValidationError("Only read-only SELECT statements are allowed.")

    return sql_query.strip()

def execute_sql(sql_query: str, max_rows: int = MAX_ROWS) -> list[dict[str, Any]]:
    sql_query = validate_sql(sql_query)

    connection = pyodbc.connect(
        settings.db_connection_string,
        timeout = settings.db_timeout_seconds
    )
    try:
        connection.timeout = settings.db_timeout_seconds
        cursor = connection.cursor()
        cursor.execute(sql_query)

        if cursor.description is None:
            return []
        
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchmany(max_rows)

        return [
            {column: _safe(value) for column, value in zip(columns, row, strict=False)}
            for row in rows
        ]
    finally:
        connection.close()