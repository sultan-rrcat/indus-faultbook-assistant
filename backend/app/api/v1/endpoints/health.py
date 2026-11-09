import logging
from typing import Literal

import pyodbc
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse
from app.services.providers.factory import get_model_name

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db: Literal["up", "down", "unknown"] = "unknown"
    try:
        connection = pyodbc.connect(settings.db_connection_string, timeout=3)
        try:
            connection.cursor().execute("SELECT 1")
            db = "up"
        finally:
            connection.close()
    except pyodbc.Error:
        logger.warning("Health check: database unreachable", exc_info=True)
        db = "down"

    status: Literal["ok", "degraded"] = "ok" if db == "up" else "degraded"

    return HealthResponse(
        status=status,
        db=db,
        llm_provider=settings.llm_provider,
        model=get_model_name(),
    )