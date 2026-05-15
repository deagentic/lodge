"""
Decorators for automatic telemetry instrumentation.

Usage:
    from .telemetry import skill_span, tool_span

    @skill_span("software-archeologist", ".agents/skills/software/discovery/software-archeologist/SKILL.md")
    def run_archeologist(model: str, input_tokens: int, output_tokens: int, **kwargs):
        ...

    @tool_span("sql_topology", "tools/software/discovery/sql_topology.py")
    def run_sql_topology(**kwargs):
        ...
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

from .client import send_event
from .cost_rates import estimate_cost, get_provider
from .schema import SkillInvokedPayload, ToolExecutedPayload, make_event

F = TypeVar("F", bound=Callable[..., Any])

# These variables are templated by cookiecutter at generation time.
_PROJECT_SLUG = "lodge"
_GITHUB_USERNAME = "myuser"


def skill_span(skill_name: str, skill_path: str = "") -> Callable[[F], F]:
    """
    Decorator that wraps a function and emits a skill.invoked event.

    The wrapped function may optionally accept and return keyword arguments
    `model`, `input_tokens`, `output_tokens` which are used to calculate cost.
    If the function raises, the event is still sent with duration_ms set.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                raise
            finally:
                duration_ms = int((time.monotonic() - start) * 1000)
                model: str = kwargs.get("model", "unknown")
                input_tokens: int | None = kwargs.get("input_tokens")
                output_tokens: int | None = kwargs.get("output_tokens")
                cost: float | None = None
                if input_tokens is not None and output_tokens is not None:
                    cost = estimate_cost(model, input_tokens, output_tokens)

                payload = SkillInvokedPayload(
                    skill_name=skill_name,
                    skill_path=skill_path,
                    model=model,
                    provider=get_provider(model),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=cost,
                    duration_ms=duration_ms,
                )
                send_event(make_event("skill.invoked", _PROJECT_SLUG, _GITHUB_USERNAME, payload))
        return wrapper  # type: ignore[return-value]
    return decorator


def tool_span(tool_name: str, tool_path: str = "") -> Callable[[F], F]:
    """
    Decorator that wraps a tool execution function and emits a tool.executed event.

    Captures duration and exit_code (0 for success, 1 for exception).
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            exit_code = 0
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                exit_code = 1
                raise
            finally:
                duration_ms = int((time.monotonic() - start) * 1000)
                payload = ToolExecutedPayload(
                    tool_name=tool_name,
                    tool_path=tool_path,
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                )
                send_event(make_event("tool.executed", _PROJECT_SLUG, _GITHUB_USERNAME, payload))
        return wrapper  # type: ignore[return-value]
    return decorator


def track_knowledge_used(kind: str, path: str, context: str | None = None) -> None:
    """
    Emit a knowledge.used event. Call this explicitly when an agent reads
    an existing skill doc, ADR, or domain knowledge file.
    """
    from .schema import KnowledgeUsedPayload, make_event
    payload = KnowledgeUsedPayload(kind=kind, path=path, context=context)
    send_event(make_event("knowledge.used", _PROJECT_SLUG, _GITHUB_USERNAME, payload))


def track_knowledge_created(kind: str, path: str, commit_sha: str | None = None) -> None:
    """
    Emit a knowledge.created event. Call this when a new ADR, skill,
    domain doc, or tool is created.
    """
    from .schema import KnowledgeCreatedPayload, make_event
    payload = KnowledgeCreatedPayload(kind=kind, path=path, commit_sha=commit_sha)
    send_event(make_event("knowledge.created", _PROJECT_SLUG, _GITHUB_USERNAME, payload))
