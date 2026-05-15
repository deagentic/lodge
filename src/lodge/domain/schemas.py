from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class IngestEventRequest(BaseModel):
    event_type: str
    project_slug: str
    github_username: str = ""
    timestamp: datetime
    schema_version: str = "1.0"
    payload: dict[str, Any]


class IngestEventResponse(BaseModel):
    id: uuid.UUID


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class EventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    project_slug: str
    github_username: str
    schema_version: str
    received_at: datetime
    event_ts: datetime
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class SkillCount(BaseModel):
    skill_name: str
    count: int


class ModelCount(BaseModel):
    model: str
    count: int
    total_cost_usd: float


class CiStats(BaseModel):
    total: int
    passed: int
    failed: int


class SummaryResponse(BaseModel):
    projects_generated: int
    skills_invoked: int
    ci_runs: CiStats
    tools_executed: int
    knowledge_created: int
    knowledge_used: int
    top_skills: list[SkillCount]
    top_models: list[ModelCount]
    total_cost_usd: float


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    db: str
