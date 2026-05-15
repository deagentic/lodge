Feature: Authentication — GitHub OAuth Device Flow
  As a developer using the Cornerstone CLI
  I want to authenticate against Lodge using my GitHub identity
  So that I receive a scoped API key stored securely in ~/.cornerstone/credentials

  Background:
    Given Lodge is running with IDP_PROVIDER set to "github"

  # ── Device Flow initiation ────────────────────────────────────────────────

  Scenario: Request device code returns verification URI and user code
    When I POST to /api/v1/auth/device/request with client_id "cornerstone-cli"
    Then the response status code should be 200
    And the response body should contain a "user_code" field
    And the response body should contain a "verification_uri" field
    And the response body should contain a "device_code" field
    And the response body should contain an "expires_in" field

  Scenario: Device code request without client_id returns 422
    When I POST to /api/v1/auth/device/request with an empty body
    Then the response status code should be 422

  # ── Token exchange ─────────────────────────────────────────────────────────

  Scenario: Exchanging an authorized device code returns a scoped API key
    Given a device code that has been authorized by the user on GitHub
    When I POST to /api/v1/auth/device/exchange with the device_code
    Then the response status code should be 200
    And the response body should contain an "api_key" field
    And the response body should contain a "scopes" field
    And the response body should contain an "expires_at" field

  Scenario: Polling before authorization returns authorization_pending
    Given a device code that has NOT yet been authorized
    When I POST to /api/v1/auth/device/exchange with the device_code
    Then the response status code should be 202
    And the response body should contain "authorization_pending"

  Scenario: Exchanging an expired device code returns 410
    Given a device code that has expired
    When I POST to /api/v1/auth/device/exchange with the device_code
    Then the response status code should be 410

  # ── Token validation ──────────────────────────────────────────────────────

  Scenario: Valid API key returns user profile and RBAC claims
    Given I have a valid API key
    When I GET /api/v1/auth/me with the API key in the Authorization header
    Then the response status code should be 200
    And the response body should contain an "email" field
    And the response body should contain a "roles" field
    And the response body should contain an "org" field

  Scenario: Missing Authorization header returns 401
    When I GET /api/v1/auth/me without an Authorization header
    Then the response status code should be 401

  Scenario: Expired API key returns 401
    Given I have an expired API key
    When I GET /api/v1/auth/me with the expired key
    Then the response status code should be 401
    And the response body should contain "token_expired"

  Scenario: Revoked API key returns 401
    Given I have a revoked API key
    When I GET /api/v1/auth/me with the revoked key
    Then the response status code should be 401
    And the response body should contain "token_revoked"

  # ── Logout ────────────────────────────────────────────────────────────────

  Scenario: Logout revokes the current API key
    Given I have a valid API key
    When I DELETE /api/v1/auth/token with the API key in the Authorization header
    Then the response status code should be 204
    And subsequent GET /api/v1/auth/me with the same key returns 401
