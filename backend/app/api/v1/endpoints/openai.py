import json
import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.core.exceptions import LLMResponseError, SQLValidationError
from app.schemas.openai import ChatCompletionChoice, ChatCompletionRequest, ChatCompletionResponse, OpenAIMessage, Usage
from app.services.nl2sql.orchestrator import ChatService

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL_ID = "faultbook-assistant"
TASK_MARKER = "### Task:"

def _is_auxiliary_task(messages: list[OpenAIMessage]) -> bool:
    """Open WebUI sends title/tags/follow-up generation as a single user message
    whose content starts with a '### Task:' prompt."""
    return any(
        msg.role == "user" and msg.content.lstrip().startswith(TASK_MARKER)
        for msg in messages
    )

def _last_user_question(messages: list[OpenAIMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()
    raise HTTPException(status_code=400, detail="No user message found.")


@router.get("/models")
def list_models() -> dict[str, object]:
    return {"object": "list","data": [{"id": MODEL_ID, "object": "model", "owned_by": "indus"}]}

def _call_service(question: str, service: ChatService) -> str:
    try:
        return service.answer(question).answer
    except LLMResponseError as err:
        raise HTTPException(status_code=502, detail="The language model did not return a usable answer.") from err
    except SQLValidationError as err:
        raise HTTPException(status_code=422, detail="The generated query could not be executed safely.") from err
    except Exception as err:
        logger.exception("OpenAI-compat chat failed: %s", err)
        raise HTTPException(status_code=500, detail="Failed to process the question.") from err

def _call_completion(messages: list[OpenAIMessage], service: ChatService) -> str:
    try:
        return service.complete([{"role": msg.role, "content": msg.content} for msg in messages])
    except LLMResponseError as err:
        raise HTTPException(status_code=502, detail="The language model did not return a usable answer.") from err
    except Exception as err:
        logger.exception("OpenAI-compat helper task failed: %s", err)
        raise HTTPException(status_code=500, detail="Failed to process the request.") from err

@router.post("/chat/completions", response_model=None)
def chat_completions(
    request: ChatCompletionRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatCompletionResponse | StreamingResponse:
    if _is_auxiliary_task(request.messages):
        answer = _call_completion(request.messages, service)
    else:
        question = _last_user_question(request.messages)
        answer = _call_service(question, service)
    now = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    if not request.stream:
        return ChatCompletionResponse(
            id = completion_id,
            created = now,
            model = MODEL_ID,
            choices = [ChatCompletionChoice(message=OpenAIMessage(role="assistant", content=answer))],
            usage=Usage(completion_tokens=len(answer.split()))
        )
    
    # OpenWebUI always requests stream=true -> SSE
    def _sse(payload: str) -> str:
        return f"data: {payload}\n\n"

    chunk = {
        "id": completion_id, "object": "chat.completion.chunk", "created":now, "model": MODEL_ID,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": answer}, "finish_reason": None}],
    }
    
    done = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    body = _sse(json.dumps(chunk)) + _sse(json.dumps(done)) + _sse("[DONE]")
    
    return StreamingResponse(iter([body]), media_type="text/event-stream")