import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .db import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    project_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    github_username: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
    )
    schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1.0"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("idx_events_event_type", "event_type"),
        Index("idx_events_project_slug", "project_slug"),
        Index("idx_events_received_at", "received_at"),
        Index("idx_events_type_project", "event_type", "project_slug"),
    )
