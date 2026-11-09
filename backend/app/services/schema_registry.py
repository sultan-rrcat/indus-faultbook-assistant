from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "resources" / "schema.sql"

_schema: str | None = None

def get_schema() -> str:
    global _schema
    if _schema is None:
        _schema = SCHEMA_FILE.read_text(encoding="utf-8").strip()
    return _schema
