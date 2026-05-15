"""
Cornerstone telemetry SDK.

Public API:
    send_event(event)              — send a raw event dict
    is_telemetry_enabled()         — check if telemetry is active
    skill_span(name, path)         — decorator for skill invocations
    tool_span(name, path)          — decorator for tool executions
    track_knowledge_used(...)      — explicit knowledge.used event
    track_knowledge_created(...)   — explicit knowledge.created event
    setup_otel_if_available(name)  — optional OpenTelemetry setup

All functions are safe to call unconditionally — they are no-ops when
AGENTIC_TELEMETRY_URL is not set.
"""

from .client import is_telemetry_enabled, send_event
from .decorators import skill_span, tool_span, track_knowledge_created, track_knowledge_used
from .otel import setup_otel_if_available

__all__ = [
    "send_event",
    "is_telemetry_enabled",
    "skill_span",
    "tool_span",
    "track_knowledge_used",
    "track_knowledge_created",
    "setup_otel_if_available",
]
