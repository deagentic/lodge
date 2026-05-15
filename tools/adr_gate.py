#!/usr/bin/env python3
"""tools/adr_gate.py — ADR Gate for Claude Code PreToolUse[Edit|Write] hooks.

Replaces the agent-based ADR gate with a deterministic command hook.
Unlike the agent hook, this never fails due to conversation length or
token limits — it is purely shell-level: parse JSON, check git status,
emit allow/deny JSON.

Usage
-----
Called as a ``PreToolUse[Edit|Write]`` command hook by Claude and Gemini.
The runtime sets ``$ARGUMENTS`` to the JSON hook payload before invoking.
Output is a JSON permissionDecision on stdout.

Bypass
------
Include ``[skip-adr]`` anywhere in the hook payload to bypass.
Every bypass is logged to ``.adr-gate-bypasses.log``.

Configuration
-------------
``CORNERSTONE_ADR_PATH``  — directory scanned for new ADR files (default: docs/adr)
"""

import json
import os
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ADR_PATH = os.environ.get("CORNERSTONE_ADR_PATH", "docs/adr")
_BYPASS_TOKEN = "[skip-adr]"  # nosec B105
_BYPASS_ALT = "--skip-adr"
_LOG_FILE = Path(".adr-gate-bypasses.log")

#: File extensions that trigger the ADR mandate.
_ADR_REQUIRED_EXTENSIONS = {".py", ".sh", ".yml", ".yaml"}

#: Path fragments that are always exempt (no ADR needed).
_EXEMPT_FRAGMENTS = [
    "/tests/",
    "tests/",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _parse_payload(raw: str) -> tuple[str, bool]:
    """Return (file_path, bypass_flag) from the hook JSON payload."""
    if not raw:
        return "", False
    bypass = _BYPASS_TOKEN in raw or _BYPASS_ALT in raw
    try:
        data = json.loads(raw)
        file_path = data.get("tool_input", {}).get("file_path", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        file_path = ""
    return file_path, bypass


def _needs_adr(file_path: str) -> bool:
    """True if this file path is subject to the ADR mandate."""
    if not file_path:
        return False

    # Writing the ADR itself — always exempt
    if file_path.startswith(_ADR_PATH + "/") or ("/" + _ADR_PATH + "/") in file_path:
        return False

    # Exempt path fragments
    for fragment in _EXEMPT_FRAGMENTS:
        if fragment in file_path:
            return False

    p = Path(file_path)

    # .md files are always exempt (docs, README, AGENTS.md, etc.)
    if p.suffix == ".md":
        return False

    return p.suffix in _ADR_REQUIRED_EXTENSIONS


def _has_pending_adr() -> bool:
    """True if a new ADR file is staged or untracked in the ADR directory."""
    try:
        result = subprocess.run(  # nosec B603, B607
            ["git", "status", "--porcelain", _ADR_PATH + "/"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            status = line[:2].strip()
            if status in ("??", "A", "AM", "M"):
                return True
        return False
    except Exception:
        # Fail-open: if git is unavailable, don't block work
        return True


def _log_bypass(reason: str, file_path: str, context: str) -> None:
    try:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = f"{ts} | reason={reason} | files=[{file_path}] | msg='{context[:80]}'\n"
        existing = _LOG_FILE.read_text(encoding="utf-8") if _LOG_FILE.exists() else ""
        _LOG_FILE.write_text(existing + entry, encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Decision builders
# ---------------------------------------------------------------------------


def _allow() -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def _deny(file_path: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"ADR MANDATE BLOCKED\n\n"
                f"Modifying '{file_path}' requires an Architecture Decision Record.\n\n"
                f"Steps:\n"
                f"  1. Read .agents/skills/software/architecture/architect/SKILL.md\n"
                f"  2. Design the change and its trade-offs\n"
                f"  3. Read .agents/skills/software/architecture/adr-writer/SKILL.md\n"
                f"  4. Write {_ADR_PATH}/ADR-NNNN-<title>.md\n"
                f"     (see {_ADR_PATH}/index.md for the next ADR number)\n"
                f"  5. Retry this edit\n\n"
                f"Trivial fix? Include [skip-adr] in your message to bypass."
            ),
        }
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(raw: str = "") -> dict:
    """Evaluate the hook payload and return a permissionDecision."""
    if not raw:
        raw = _read_stdin()

    file_path, bypass = _parse_payload(raw)

    if bypass:
        _log_bypass(_BYPASS_TOKEN, file_path, raw[:80])
        return _allow()

    if not _needs_adr(file_path):
        return _allow()

    if _has_pending_adr():
        return _allow()

    return _deny(file_path)


def main() -> int:
    raw = os.environ.get("ARGUMENTS", "")
    result = run(raw)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
