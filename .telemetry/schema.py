"""
Event schema definitions for Cornerstone telemetry.

All events share a common envelope. Payload varies by event_type.
Uses stdlib dataclasses — no external dependencies required.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


def _now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

@dataclass
class EventEnvelope:
    event_type: str
    project_slug: str
    github_username: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=_now_utc)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

@dataclass
class ProjectGeneratedPayload:
    python_version: str
    template_version: str
    cookiecutter_vars: dict[str, Any]


@dataclass
class SkillInvokedPayload:
    skill_name: str
    skill_path: str
    model: str
    provider: str  # "anthropic" | "google" | "openai" | "unknown"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None


@dataclass
class CiRunPayload:
    workflow: str
    run_id: str
    ref: str
    commit_sha: str
    adr_gate_passed: bool
    tests_passed: bool
    lint_passed: bool
    duration_ms: int


@dataclass
class ToolExecutedPayload:
    tool_name: str
    tool_path: str
    duration_ms: int
    exit_code: int
    invocation_count: int = 1


@dataclass
class KnowledgeCreatedPayload:
    kind: str  # "skill" | "adr" | "domain_doc" | "tool"
    path: str
    commit_sha: Optional[str] = None


@dataclass
class KnowledgeUsedPayload:
    kind: str  # "skill" | "domain_doc" | "tool"
    path: str
    context: Optional[str] = None


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def make_event(
    event_type: str,
    project_slug: str,
    github_username: str,
    payload_obj: Any,
) -> dict[str, Any]:
    """Build a ready-to-send event dict from a typed payload dataclass."""
    return EventEnvelope(
        event_type=event_type,
        project_slug=project_slug,
        github_username=github_username,
        payload=asdict(payload_obj),
    ).to_dict()
