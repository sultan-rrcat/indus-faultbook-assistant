from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        min_length = 1,
        max_length = 2000,
        description = "Natural-language question about the fault book"
    )

class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    row_count: int = 0