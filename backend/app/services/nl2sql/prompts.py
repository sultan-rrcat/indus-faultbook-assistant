from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

def _load(name: str) -> Template:
    return Template((PROMPTS_DIR / name).read_text(encoding="utf-8"))

_SQL_GENERATE = _load("sql_generate.txt")
_SUMMARIZE = _load("summarize.txt")

def build_sql_prompt(schema: str, question: str) -> str:
    return _SQL_GENERATE.substitute(schema=schema, question=question)

def build_summary_prompt(question: str, results: str) -> str:
    return _SUMMARIZE.substitute(question=question, results=results)