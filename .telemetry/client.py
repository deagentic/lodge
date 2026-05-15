"""
Telemetry client for Cornerstone.

Fires events to AGENTIC_TELEMETRY_URL/v1/events in a background thread.
If AGENTIC_TELEMETRY_URL is unset or empty, all calls are silent no-ops.
Never raises. Never blocks the caller.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from typing import Any

_TELEMETRY_URL_VAR = "AGENTIC_TELEMETRY_URL"
_DEBUG_VAR = "AGENTIC_TELEMETRY_DEBUG"
_TIMEOUT_SECONDS = 3


def is_telemetry_enabled() -> bool:
    """Return True if AGENTIC_TELEMETRY_URL is set and non-empty."""
    return bool(os.environ.get(_TELEMETRY_URL_VAR, "").strip())


def _base_url() -> str:
    return os.environ.get(_TELEMETRY_URL_VAR, "").rstrip("/")


def _debug(msg: str) -> None:
    if os.environ.get(_DEBUG_VAR):
        import sys
        print(f"[agentic-telemetry] {msg}", file=sys.stderr)


def send_event(event: dict[str, Any]) -> None:
    """
    Fire-and-forget POST of *event* to the telemetry service.

    Returns immediately. Swallows all exceptions. No-op when telemetry
    is disabled (AGENTIC_TELEMETRY_URL not set).
    """
    if not is_telemetry_enabled():
        return

    url = _base_url() + "/v1/events"

    def _fire() -> None:
        try:
            data = json.dumps(event, default=str).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS):  # nosec B310  # URL sourced from config/env, not user input
                pass
            _debug(f"sent {event.get('event_type')} for {event.get('project_slug')}")
        except Exception as exc:  # noqa: BLE001
            _debug(f"error sending event: {exc}")

    t = threading.Thread(target=_fire, daemon=True)
    t.start()
