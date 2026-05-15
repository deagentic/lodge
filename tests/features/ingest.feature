Feature: Event ingestion endpoint
  As an agent or CI pipeline reporting telemetry
  I want POST /v1/events to accept and store structured events
  So that agentic session activity is captured for analytics

  Scenario: Valid event is accepted with HTTP 202
    Given a valid event payload with event_type "ci.run"
    When I POST the payload to /v1/events
    Then the response status code should be 202

  Scenario: Response body contains the event ID
    Given a valid event payload with event_type "skill.invoked"
    When I POST the payload to /v1/events
    Then the response body should contain an "id" field

  Scenario: Unknown event_type is rejected with HTTP 400
    Given an event payload with an unknown event_type "unknown.type"
    When I POST the payload to /v1/events
    Then the response status code should be 400

  Scenario: Missing required field returns HTTP 422
    Given an incomplete event payload missing the timestamp field
    When I POST the payload to /v1/events
    Then the response status code should be 422
