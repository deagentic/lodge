Feature: MCP Catalog — Registration and Governance
  As a developer who has built an MCP server with cornerstone
  I want to register it in Lodge's catalog
  So that it is published to crisol-gateway and made available to authorized teams

  Background:
    Given I have a valid API key with role "contributor"

  # ── Registration ──────────────────────────────────────────────────────────

  Scenario: Registering an MCP server with a passed security audit opens a PR
    Given an mcp-catalog.yaml payload for server "crisol-bigquery-mcp" with security_audit_status "passed"
    When I POST to /api/v1/mcp/register with the payload
    Then the response status code should be 202
    And the response body should contain a "pr_url" field pointing to deagentic/crisol-gateway
    And the response body should contain "status" with value "pr_opened"

  Scenario: Registering an MCP server with a pending security audit defers registration
    Given an mcp-catalog.yaml payload for server "new-mcp" with security_audit_status "pending"
    When I POST to /api/v1/mcp/register with the payload
    Then the response status code should be 202
    And the response body should contain "status" with value "deferred"
    And the response body should contain "reason" with value "security_audit_pending"
    And no PR should have been opened on crisol-gateway

  Scenario: Registering an MCP server with a failed security audit is rejected
    Given an mcp-catalog.yaml payload for server "unsafe-mcp" with security_audit_status "failed"
    When I POST to /api/v1/mcp/register with the payload
    Then the response status code should be 422
    And the response body should contain "security_audit_failed"

  Scenario: Re-registering an already-registered MCP updates the existing PR
    Given server "crisol-bigquery-mcp" is already registered with an open PR
    When I POST to /api/v1/mcp/register with updated metadata for "crisol-bigquery-mcp"
    Then the response status code should be 200
    And the response body should contain "status" with value "pr_updated"
    And only one PR should be open on crisol-gateway for "crisol-bigquery-mcp"

  Scenario: Registration without authentication returns 401
    Given I have no API key
    When I POST to /api/v1/mcp/register with a valid payload
    Then the response status code should be 401

  # ── Catalog listing ───────────────────────────────────────────────────────

  Scenario: List catalog returns all registered MCPs for the org
    Given servers "crisol-mcp-github", "crisol-context-mcp" are registered
    When I GET /api/v1/mcp/catalog
    Then the response status code should be 200
    And the response body should contain "crisol-mcp-github"
    And the response body should contain "crisol-context-mcp"

  Scenario: Catalog entry includes security audit status
    Given server "crisol-mcp-github" is registered with security_audit_status "passed"
    When I GET /api/v1/mcp/catalog
    Then the response body entry for "crisol-mcp-github" should have "security_audit_status" equal to "passed"

  Scenario: Catalog supports filtering by security audit status
    When I GET /api/v1/mcp/catalog?security_audit_status=pending
    Then the response status code should be 200
    And every entry in the catalog should have security_audit_status "pending"

  # ── Catalog update ────────────────────────────────────────────────────────

  Scenario: Platform admin can update catalog entry metadata
    Given I have a valid API key with role "platform-admin"
    And server "crisol-context-mcp" is registered
    When I PATCH /api/v1/mcp/catalog/crisol-context-mcp with updated owner "platform-team"
    Then the response status code should be 200
    And the response body "owner" field should be "platform-team"

  Scenario: Non-admin cannot update another team's catalog entry
    Given server "other-team-mcp" is owned by "other-team"
    And I have a valid API key with role "contributor" for team "my-team"
    When I PATCH /api/v1/mcp/catalog/other-team-mcp with updated owner "my-team"
    Then the response status code should be 403
