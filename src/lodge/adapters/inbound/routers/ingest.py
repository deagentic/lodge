from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from ...outbound.db import get_db
from ...outbound.models import Event
from ....domain.schemas import IngestEventRequest, IngestEventResponse

router = APIRouter(prefix="/v1", tags=["ingest"])

VALID_EVENT_TYPES = {
    "project.generated",
    "skill.invoked",
    "ci.run",
    "tool.executed",
    "knowledge.created",
    "knowledge.used",
}


@router.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(
    body: IngestEventRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestEventResponse:
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event_type '{body.event_type}'. Valid: {sorted(VALID_EVENT_TYPES)}",
        )

    event = Event(
        event_type=body.event_type,
        project_slug=body.project_slug,
        github_username=body.github_username,
        schema_version=body.schema_version,
        event_ts=body.timestamp,
        payload=body.payload,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Refresh materialized view asynchronously (best-effort)
    try:
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_summary"))
        await db.commit()
    except (
        Exception
    ):  # nosec B110  # best-effort refresh  # pylint: disable=broad-exception-caught
        pass

    return IngestEventResponse(id=event.id)
