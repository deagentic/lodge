Feature: FinOps — Cost and Usage Tracking
  As a platform engineer or team lead
  I want to see aggregated cost and usage data for my org's agentic activity
  So that I can track spend, identify top consumers, and manage budgets

  Background:
    Given I have a valid API key with role "platform-admin"
    And telemetry events with token cost data have been ingested for the last 30 days

  # ── Cost summary ──────────────────────────────────────────────────────────

  Scenario: Cost summary returns breakdown by team
    When I GET /api/v1/finops/summary
    Then the response status code should be 200
    And the response body should contain a "by_team" array
    And each item in "by_team" should have "team", "total_cost_usd", and "event_count" fields

  Scenario: Cost summary supports date range filtering
    When I GET /api/v1/finops/summary?from=2026-05-01&to=2026-05-15
    Then the response status code should be 200
    And the response body should contain a "period" field with "from" and "to" values

  Scenario: Cost summary filtered by project returns single-project view
    When I GET /api/v1/finops/summary?project=lodge
    Then the response status code should be 200
    And the response body "by_team" array should only include data for project "lodge"

  Scenario: Cost summary by model shows per-model spend
    When I GET /api/v1/finops/summary?group_by=model
    Then the response status code should be 200
    And the response body should contain a "by_model" array
    And each item should have "model", "provider", and "total_cost_usd" fields

  # ── Burn rate ─────────────────────────────────────────────────────────────

  Scenario: Burn rate returns current daily spend vs budget
    When I GET /api/v1/finops/burn-rate
    Then the response status code should be 200
    And the response body should contain a "daily_spend_usd" field
    And the response body should contain a "monthly_budget_usd" field
    And the response body should contain a "days_remaining" field
    And the response body should contain a "projected_monthly_usd" field

  Scenario: Burn rate with no budget configured omits budget fields
    Given no monthly budget has been set for the org
    When I GET /api/v1/finops/burn-rate
    Then the response status code should be 200
    And the response body "monthly_budget_usd" field should be null

  # ── Top consumers ─────────────────────────────────────────────────────────

  Scenario: Top consumers returns the 10 highest cost drivers
    When I GET /api/v1/finops/top-consumers
    Then the response status code should be 200
    And the response body should contain a "consumers" array with at most 10 items
    And each item should have "type", "name", "total_cost_usd", and "event_count" fields
    And the "consumers" array should be sorted by "total_cost_usd" descending

  Scenario: Top consumers can be filtered by type
    When I GET /api/v1/finops/top-consumers?type=skill
    Then the response status code should be 200
    And every item in "consumers" should have type "skill"

  # ── Access control ────────────────────────────────────────────────────────

  Scenario: Viewer without finops scope cannot access cost summary
    Given I have a valid API key with role "viewer"
    When I GET /api/v1/finops/summary
    Then the response status code should be 403
