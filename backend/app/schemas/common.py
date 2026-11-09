from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["up", "down", "unknown"]
    llm_provider: str
    model: str

class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None