from pydantic import BaseModel, Field


class OpenAIMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = Field(default="faultbook-assistant")
    messages: list[OpenAIMessage]
    stream: bool = False

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage = Usage()
