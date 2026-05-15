from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...outbound.db import get_db
from ...outbound.models import Event
from ....domain.schemas import (
    CiStats,
    EventListResponse,
    EventOut,
    ModelCount,
    SkillCount,
    SummaryResponse,
)

router = APIRouter(prefix="/v1", tags=["query"])


@router.get("/events")
async def list_events(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    event_type: Optional[str] = Query(None),
    project_slug: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    q = select(Event)
    count_q = select(func.count()).select_from(Event)

    if event_type:
        q = q.where(Event.event_type == event_type)
        count_q = count_q.where(Event.event_type == event_type)
    if project_slug:
        q = q.where(Event.project_slug == project_slug)
        count_q = count_q.where(Event.project_slug == project_slug)
    if from_dt:
        q = q.where(Event.event_ts >= from_dt)
        count_q = count_q.where(Event.event_ts >= from_dt)
    if to_dt:
        q = q.where(Event.event_ts <= to_dt)
        count_q = count_q.where(Event.event_ts <= to_dt)

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    q = q.order_by(Event.event_ts.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    items = [EventOut.model_validate(row) for row in result.scalars().all()]

    return EventListResponse(items=items, total=total)


@router.get("/summary")
async def summary(  # pylint: disable=too-many-locals
    project_slug: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    # Default: last 30 days
    if not from_dt:
        from_dt = datetime.now(timezone.utc) - timedelta(days=30)
    if not to_dt:
        to_dt = datetime.now(timezone.utc)

    def base_filter(q):
        q = q.where(Event.event_ts >= from_dt).where(Event.event_ts <= to_dt)
        if project_slug:
            q = q.where(Event.project_slug == project_slug)
        return q

    async def count_type(etype: str) -> int:
        q = base_filter(
            select(func.count()).select_from(Event).where(Event.event_type == etype)
        )
        r = await db.execute(q)
        return r.scalar_one() or 0

    projects_generated = await count_type("project.generated")
    skills_invoked = await count_type("skill.invoked")
    tools_executed = await count_type("tool.executed")
    knowledge_created = await count_type("knowledge.created")
    knowledge_used = await count_type("knowledge.used")

    # CI stats
    ci_total = await count_type("ci.run")
    ci_passed_q = base_filter(
        select(func.count())
        .select_from(Event)
        .where(Event.event_type == "ci.run")
        .where(Event.payload["tests_passed"].astext == "true")
    )
    r = await db.execute(ci_passed_q)
    ci_passed = r.scalar_one() or 0
    ci_stats = CiStats(total=ci_total, passed=ci_passed, failed=ci_total - ci_passed)

    # Top skills
    top_skills_q = (
        base_filter(
            select(
                Event.payload["skill_name"].astext.label("skill_name"),
                func.count().label("count"),
            ).where(Event.event_type == "skill.invoked")
        )
        .group_by(Event.payload["skill_name"].astext)
        .order_by(func.count().desc())
        .limit(10)
    )
    r = await db.execute(top_skills_q)
    top_skills = [
        SkillCount(skill_name=row.skill_name or "unknown", count=row.count) for row in r
    ]

    # Top models + cost
    top_models_q = (
        base_filter(
            select(
                Event.payload["model"].astext.label("model"),
                func.count().label("count"),
                func.coalesce(
                    func.sum(Event.payload["estimated_cost_usd"].cast("float")), 0.0
                ).label("total_cost_usd"),
            ).where(Event.event_type == "skill.invoked")
        )
        .group_by(Event.payload["model"].astext)
        .order_by(func.count().desc())
        .limit(10)
    )
    r = await db.execute(top_models_q)
    top_models = [
        ModelCount(
            model=row.model or "unknown",
            count=row.count,
            total_cost_usd=row.total_cost_usd or 0.0,
        )
        for row in r
    ]

    total_cost_usd = sum(m.total_cost_usd for m in top_models)

    return SummaryResponse(
        projects_generated=projects_generated,
        skills_invoked=skills_invoked,
        ci_runs=ci_stats,
        tools_executed=tools_executed,
        knowledge_created=knowledge_created,
        knowledge_used=knowledge_used,
        top_skills=top_skills,
        top_models=top_models,
        total_cost_usd=total_cost_usd,
    )
