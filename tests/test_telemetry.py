"""
Unit tests for .telemetry SDK.

Run with: pytest tests/test_telemetry.py -v
No network calls are made — urllib.request.urlopen is mocked.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import importlib.util
from pathlib import Path
import types

# --- Hack to load .telemetry modules since Python doesn't support dot-prefixed directories natively ---
telemetry_dir = Path(__file__).parent.parent / ".telemetry"
telemetry_pkg = types.ModuleType("telemetry")
telemetry_pkg.__path__ = [str(telemetry_dir)]
telemetry_pkg.__package__ = "telemetry"
sys.modules["telemetry"] = telemetry_pkg

for mod in ["client", "cost_rates", "schema", "decorators", "otel"]:
    spec = importlib.util.spec_from_file_location(
        f"telemetry.{mod}", telemetry_dir / f"{mod}.py"
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "telemetry"
    sys.modules[f"telemetry.{mod}"] = module
    setattr(telemetry_pkg, mod, module)

for mod in ["client", "cost_rates", "schema", "decorators", "otel"]:
    sys.modules[f"telemetry.{mod}"].__spec__.loader.exec_module(
        sys.modules[f"telemetry.{mod}"]
    )

import telemetry.client as client  # noqa: E402
import telemetry.cost_rates as cost_rates  # noqa: E402
import telemetry.decorators as decorators  # noqa: E402
import telemetry.schema as schema  # noqa: E402


def _reload_client(env: dict) -> object:
    with patch.dict("os.environ", env, clear=True):
        spec = importlib.util.spec_from_file_location(
            "telemetry.client", telemetry_dir / "client.py"
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "telemetry"
        spec.loader.exec_module(mod)
        return mod


def test_no_op_when_env_var_absent():
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("AGENTIC_TELEMETRY_URL", None)
        assert not client.is_telemetry_enabled()
        with patch("urllib.request.urlopen") as mock_open:
            client.send_event({"event_type": "skill.invoked", "project_slug": "test"})
            import time

            time.sleep(0.05)
            mock_open.assert_not_called()


def test_sends_when_env_var_set():
    import os
    import time

    os.environ["AGENTIC_TELEMETRY_URL"] = "http://localhost:9999"
    try:
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            client.send_event(
                {
                    "event_type": "skill.invoked",
                    "project_slug": "my-project",
                    "github_username": "myuser",
                    "timestamp": "2026-03-17T00:00:00Z",
                    "schema_version": "1.0",
                    "payload": {},
                }
            )
            time.sleep(0.1)
            assert mock_open.called
            req_arg = mock_open.call_args[0][0]
            assert req_arg.full_url == "http://localhost:9999/v1/events"
            assert req_arg.get_header("Content-type") == "application/json"
    finally:
        os.environ.pop("AGENTIC_TELEMETRY_URL", None)


def test_swallows_network_errors():
    import os
    import time

    os.environ["AGENTIC_TELEMETRY_URL"] = "http://unreachable.invalid"
    try:
        with patch(
            "urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")
        ):
            client.send_event({"event_type": "test", "project_slug": "p"})
            time.sleep(0.1)
    finally:
        os.environ.pop("AGENTIC_TELEMETRY_URL", None)


def test_cost_estimation_claude_sonnet():
    cost = cost_rates.estimate_cost(
        "claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == 18.0


def test_cost_estimation_precise():
    cost = cost_rates.estimate_cost(
        "claude-sonnet-4-6", input_tokens=1_000, output_tokens=500
    )
    assert cost == round((1_000 * 3.00 + 500 * 15.00) / 1_000_000, 8)


def test_cost_estimation_unknown_model():
    assert cost_rates.estimate_cost("gpt-99-ultra", 100, 50) is None


def test_skill_span_decorator():
    import os

    os.environ["AGENTIC_TELEMETRY_URL"] = "http://localhost:9999"
    try:
        events_sent: list[dict] = []
        with patch.object(decorators, "send_event", side_effect=events_sent.append):

            @decorators.skill_span("test-skill", ".agents/skills/test/SKILL.md")
            def my_skill(
                model: str = "claude-sonnet-4-6",
                input_tokens: int = 100,
                output_tokens: int = 50,
            ):
                return "done"

            result = my_skill(
                model="claude-sonnet-4-6", input_tokens=100, output_tokens=50
            )
        assert result == "done"
        assert len(events_sent) == 1
        evt = events_sent[0]
        assert evt["event_type"] == "skill.invoked"
        assert evt["payload"]["skill_name"] == "test-skill"
        assert evt["payload"]["model"] == "claude-sonnet-4-6"
    finally:
        os.environ.pop("AGENTIC_TELEMETRY_URL", None)


def test_tool_span_decorator():
    import os

    os.environ["AGENTIC_TELEMETRY_URL"] = "http://localhost:9999"
    try:
        events_sent: list[dict] = []
        with patch.object(decorators, "send_event", side_effect=events_sent.append):

            @decorators.tool_span(
                "sql_topology", "tools/software/discovery/sql_topology.py"
            )
            def run_tool():
                return 42

            result = run_tool()
        assert result == 42
        assert len(events_sent) == 1
        evt = events_sent[0]
        assert evt["event_type"] == "tool.executed"
        assert evt["payload"]["tool_name"] == "sql_topology"
    finally:
        os.environ.pop("AGENTIC_TELEMETRY_URL", None)


def test_project_generated_event_schema():
    payload = schema.ProjectGeneratedPayload(
        python_version="3.11",
        template_version="1.0.0",
        cookiecutter_vars={"project_name": "My Project", "project_slug": "my-project"},
    )
    event = schema.make_event("project.generated", "my-project", "myuser", payload)
    assert event["event_type"] == "project.generated"
    assert event["project_slug"] == "my-project"
    assert event["payload"]["python_version"] == "3.11"
