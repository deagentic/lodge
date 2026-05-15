#!/usr/bin/env python3
"""
tools/gitops_gate.py — Agent-Level GitOps Gate (ADR-0047).

Intercepts Bash tool calls and warns (WARN, not hard-block) when forbidden
git/gh operations are detected.  Agents may bypass by including the token
``[skip-gitops]`` anywhere in the hook payload (command or context).

Usage
-----
Called as a ``PreToolUse[Bash]`` command hook by Claude and ``BeforeTool[Bash]``
by Gemini.  The runtime sets ``$ARGUMENTS`` to the JSON hook payload before
invoking the script.  Output is a JSON permissionDecision on stdout.

Bypass audit trail
------------------
Every WARN and BYPASS event is appended to ``.gitops-gate.log`` in the repo
root, using the same pattern as ``.adr-gate-bypasses.log``.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Forbidden patterns (ADR-0047)
# ---------------------------------------------------------------------------

_GITOPS_RULES = [
    {
        "id": "GITOPS-001",
        "pattern": re.compile(r"git\s+push\s+(?:[-\w]+\s+)*origin\s+(?:master|main)\b"),
        "message": (
            "Direct push to a protected branch detected.\n"
            "Use `cornerstone flow feature publish` to open a PR and\n"
            "merge through the GitHub review process."
        ),
    },
    {
        "id": "GITOPS-002",
        "pattern": re.compile(r"\bgit\s+merge\b"),
        "message": (
            "Raw `git merge` detected.\n"
            "Use `cornerstone flow feature finish`, `release finish`, or\n"
            "`hotfix finish` — these are the authoritative merge interfaces."
        ),
    },
    {
        "id": "GITOPS-003",
        "pattern": re.compile(r"gh\s+pr\s+merge\b.*--admin"),
        "message": (
            "Admin bypass of branch protection detected (`gh pr merge --admin`).\n"
            "Request approval from a human reviewer via the GitHub UI instead."
        ),
    },
    {
        "id": "GITOPS-004",
        "pattern": re.compile(
            r"gh\s+api\b.*\bbranches/(?:master|main)/protection\b.*(PUT|DELETE|PATCH)",
            re.IGNORECASE,
        ),
        "message": (
            "Mutation of branch protection rules detected.\n"
            "Branch protection must not be changed by agents.\n"
            "Contact the repository owner to adjust protection settings."
        ),
    },
    {
        "id": "GITOPS-005",
        "pattern": re.compile(r"\bgit\s+tag\b"),
        "message": (
            "Raw `git tag` detected.\n"
            "Use `cornerstone flow release finish` or `cornerstone flow hotfix finish`\n"
            "— these create the authoritative annotated release tag."
        ),
    },
]

BYPASS_TOKEN = "[skip-gitops]"  # nosec B105
LOG_FILE = ".gitops-gate.log"
CORNERSTONE_MARKER = ".cornerstone"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log(entry: str) -> None:
    """Append a timestamped entry to the bypass log (best-effort)."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(entry + "\n")
    except OSError:
        pass  # never let logging failure block the agent


def _allow() -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def _warn(rule_id: str, message: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": (
                f"\n\u26a0\ufe0f  GITOPS GATE \u2014 {rule_id}\n"
                f"{message}\n\n"
                f"To override, include `{BYPASS_TOKEN}` in your reasoning.\n"
                f"This event has been logged to {LOG_FILE}.\n"
            ),
        }
    }


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------


def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _parse_payload(raw: str) -> tuple[str, bool]:
    """Return (command, bypass_flag) extracted from the hook JSON payload."""
    if not raw:
        return "", False
    try:
        data = json.loads(raw)
        cmd = data.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        cmd = raw
    return cmd, BYPASS_TOKEN in raw


def _first_matching_rule(cmd: str) -> dict | None:
    """Return the first forbidden rule that matches *cmd*, or None."""
    for rule in _GITOPS_RULES:
        if rule["pattern"].search(cmd):
            return rule
    return None


def _handle_match(rule: dict, cmd: str, bypass: bool) -> dict:
    """Log and return the appropriate decision for a matched rule."""
    ts = datetime.now(tz=timezone.utc).isoformat()
    if bypass:
        _log(f"{ts}  BYPASS  {rule['id']}  cmd={cmd!r}")
        return _allow()
    _log(f"{ts}  WARN    {rule['id']}  cmd={cmd!r}")
    return _warn(rule["id"], rule["message"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(raw: str = "") -> dict:
    """
    Parse the hook payload, evaluate forbidden patterns, and return a
    permissionDecision dict.

    Parameters
    ----------
    raw:
        The raw ``$ARGUMENTS`` JSON string.  Falls back to stdin when empty.
    """
    if not raw:
        raw = _read_stdin()

    cmd, bypass = _parse_payload(raw)

    if not Path(CORNERSTONE_MARKER).exists():
        return _allow()

    rule = _first_matching_rule(cmd)
    if rule:
        return _handle_match(rule, cmd, bypass)

    return _allow()


def main() -> int:
    raw = os.environ.get("ARGUMENTS", "")
    result = run(raw)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
