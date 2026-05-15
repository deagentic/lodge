"""BDD step definitions for tests/features/ingest.feature."""

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("../features/ingest.feature")

_BASE_PAYLOAD = {
    "event_type": "ci.run",
    "project_slug": "my-project",
    "github_username": "dev",
    "timestamp": "2026-01-01T00:00:00Z",
    "schema_version": "1.0",
    "payload": {"tests_passed": True},
}


@pytest.fixture
def ctx():
    return {"payload": None, "response": None}


@given('a valid event payload with event_type "ci.run"')
def payload_ci_run(ctx):
    ctx["payload"] = {**_BASE_PAYLOAD, "event_type": "ci.run"}


@given('a valid event payload with event_type "skill.invoked"')
def payload_skill_invoked(ctx):
    ctx["payload"] = {**_BASE_PAYLOAD, "event_type": "skill.invoked"}


@given('an event payload with an unknown event_type "unknown.type"')
def payload_unknown_type(ctx):
    ctx["payload"] = {**_BASE_PAYLOAD, "event_type": "unknown.type"}


@given("an incomplete event payload missing the timestamp field")
def payload_missing_timestamp(ctx):
    p = {**_BASE_PAYLOAD}
    del p["timestamp"]
    ctx["payload"] = p


@when("I POST the payload to /v1/events")
def post_event(client, ctx):
    ctx["response"] = client.post("/v1/events", json=ctx["payload"])


@then("the response status code should be 202")
def status_202(ctx):
    assert ctx["response"].status_code == 202, (
        f"Expected 202, got {ctx['response'].status_code}. Body: {ctx['response'].text}"
    )


@then('the response body should contain an "id" field')
def body_has_id(ctx):
    data = ctx["response"].json()
    assert "id" in data, f"No 'id' key in response: {data}"


@then("the response status code should be 400")
def status_400(ctx):
    assert ctx["response"].status_code == 400, (
        f"Expected 400, got {ctx['response'].status_code}. Body: {ctx['response'].text}"
    )


@then("the response status code should be 422")
def status_422(ctx):
    assert ctx["response"].status_code == 422, (
        f"Expected 422, got {ctx['response'].status_code}. Body: {ctx['response'].text}"
    )
