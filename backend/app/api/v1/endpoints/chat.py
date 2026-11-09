import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service
from app.core.exceptions import LLMResponseError, SQLValidationError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.nl2sql.orchestrator import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat", response_model = ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    try:
        return service.answer(request.question)
    except LLMResponseError as err:
        logger.warning("LLM returned an unusable response: %s", err)
        raise HTTPException(
            status_code=502,
            detail="The language model did not return a usable answer.",
        ) from err
    except SQLValidationError as err:
        logger.warning("Generated SQL failed validation: %s", err)
        raise HTTPException(
            status_code=422,
            detail="The generated query could not be executed safely.",
        ) from err
    except Exception as err:
        logger.exception(f"Chat request failed. Error: {err}")

        raise HTTPException(
            status_code=500,
            detail="Failed to process the question.",
        ) from err