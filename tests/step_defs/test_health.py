"""BDD step definitions for tests/features/health.feature."""

import pytest
from pytest_bdd import scenarios, then, when

scenarios("../features/health.feature")


@pytest.fixture
def ctx():
    return {"response": None}


@when("I GET /health")
def get_health(client, ctx):
    ctx["response"] = client.get("/health")


@when("I GET /healthz")
def get_healthz(client, ctx):
    ctx["response"] = client.get("/healthz")


@then("the response status code should be 200")
def status_200(ctx):
    assert (
        ctx["response"].status_code == 200
    ), f"Expected 200, got {ctx['response'].status_code}. Body: {ctx['response'].text}"


@then('the response body should contain a "status" field')
def body_has_status(ctx):
    data = ctx["response"].json()
    assert "status" in data, f"No 'status' key in response: {data}"
