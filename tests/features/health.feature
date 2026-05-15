Feature: Health and readiness endpoints
  As an operator, load balancer, or cornerstone doctor command
  I want Lodge to expose liveness and readiness probes
  So that I can route traffic only to healthy instances and detect misconfiguration early

  # ── Liveness (/v1/healthz) ────────────────────────────────────────────────

  Scenario: Liveness probe returns 200 when the process is running
    When I GET /v1/healthz
    Then the response status code should be 200
    And the response body should contain a "status" field with value "ok"

  Scenario: Liveness probe does not require authentication
    When I GET /v1/healthz without an Authorization header
    Then the response status code should be 200

  # ── Readiness (/v1/ready) ─────────────────────────────────────────────────

  Scenario: Readiness probe returns 200 when database and IdP are reachable
    Given the database is connected
    And the IdP (GitHub OAuth) is reachable
    When I GET /v1/ready
    Then the response status code should be 200
    And the response body should contain "database" with value "ok"
    And the response body should contain "idp" with value "ok"

  Scenario: Readiness probe returns 503 when database is unreachable
    Given the database is NOT connected
    When I GET /v1/ready
    Then the response status code should be 503
    And the response body should contain "database" with value "error"

  Scenario: Readiness probe returns 503 when IdP is unreachable
    Given the IdP is NOT reachable
    When I GET /v1/ready
    Then the response status code should be 503
    And the response body should contain "idp" with value "error"

  # ── cornerstone doctor integration ───────────────────────────────────────

  Scenario: /v1/healthz response time is under 200ms
    When I GET /v1/healthz
    Then the response time should be under 200 milliseconds
