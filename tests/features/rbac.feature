Feature: RBAC — Role-Based Access Control
  As a platform administrator
  I want to grant and revoke roles to users
  So that each actor has access only to what they need

  # ── Role listing ─────────────────────────────────────────────────────────

  Scenario: Authenticated user can list their own roles
    Given I have a valid API key for user "alice@deacero.com"
    When I GET /api/v1/rbac/roles
    Then the response status code should be 200
    And the response body should contain a "roles" array

  Scenario: Unauthenticated request to list roles returns 401
    When I GET /api/v1/rbac/roles without an Authorization header
    Then the response status code should be 401

  # ── Grant ─────────────────────────────────────────────────────────────────

  Scenario: Platform admin can grant a role to a user
    Given I have a valid API key with role "platform-admin"
    When I POST to /api/v1/rbac/grants with user "bob@deacero.com" and role "contributor"
    Then the response status code should be 201
    And the response body should contain a "grant_id" field

  Scenario: Non-admin cannot grant roles
    Given I have a valid API key with role "contributor"
    When I POST to /api/v1/rbac/grants with user "carol@deacero.com" and role "admin"
    Then the response status code should be 403

  Scenario: Granting a duplicate role is idempotent and returns 200
    Given user "dave@deacero.com" already has role "viewer"
    And I have a valid API key with role "platform-admin"
    When I POST to /api/v1/rbac/grants with user "dave@deacero.com" and role "viewer"
    Then the response status code should be 200

  # ── Revoke ────────────────────────────────────────────────────────────────

  Scenario: Platform admin can revoke a grant
    Given grant "grant-abc-123" exists for user "eve@deacero.com"
    And I have a valid API key with role "platform-admin"
    When I DELETE /api/v1/rbac/grants/grant-abc-123
    Then the response status code should be 204

  Scenario: Revoking a non-existent grant returns 404
    Given I have a valid API key with role "platform-admin"
    When I DELETE /api/v1/rbac/grants/does-not-exist
    Then the response status code should be 404

  # ── Enforcement ───────────────────────────────────────────────────────────

  Scenario: User without projects:write scope cannot register a project
    Given I have a valid API key with role "viewer"
    When I POST to /api/v1/projects/init with a valid payload
    Then the response status code should be 403

  Scenario: User without finops:read scope cannot view cost summaries
    Given I have a valid API key with role "viewer" and no finops scope
    When I GET /api/v1/finops/summary
    Then the response status code should be 403
