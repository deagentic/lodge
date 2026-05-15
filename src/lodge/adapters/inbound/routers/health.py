from fastapi import APIRouter
from sqlalchemy import text

from ...outbound.db import AsyncSessionLocal
from ....domain.schemas import HealthResponse

router = APIRouter()


@router.get("/health", tags=["health"])
@router.get("/healthz", tags=["health"])
async def health() -> HealthResponse:
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # pylint: disable=broad-exception-caught
        db_status = "error"
    return HealthResponse(status="ok", db=db_status)
