Feature: Project Registry — cornerstone new registration
  As a developer running cornerstone new
  I want my project to be registered in Lodge
  So that the platform can track adoption, enforce RBAC, and link it to FinOps data

  Background:
    Given I have a valid API key with scope "projects:write"

  # ── Registration ──────────────────────────────────────────────────────────

  Scenario: Register a new project returns 201 with project details
    Given a project registration payload with slug "my-api" and starter "api"
    When I POST to /api/v1/projects/init with the payload
    Then the response status code should be 201
    And the response body should contain a "slug" field with value "my-api"
    And the response body should contain a "starter" field with value "api"
    And the response body should contain a "registered_at" field

  Scenario: Registering an existing slug is idempotent and returns 200
    Given a project with slug "existing-project" is already registered
    When I POST to /api/v1/projects/init with slug "existing-project"
    Then the response status code should be 200
    And the response body slug should be "existing-project"

  Scenario: Registration without authentication returns 401
    Given I have no API key
    When I POST to /api/v1/projects/init with a valid payload
    Then the response status code should be 401

  Scenario: Registration with missing required fields returns 422
    When I POST to /api/v1/projects/init with a payload missing the "slug" field
    Then the response status code should be 422

  Scenario: Project slug with invalid characters returns 422
    When I POST to /api/v1/projects/init with slug "My Project!!"
    Then the response status code should be 422
    And the response body should contain "invalid_slug"

  # ── Listing ───────────────────────────────────────────────────────────────

  Scenario: List projects returns only projects for the authenticated org
    Given projects "proj-a" and "proj-b" registered under org "deacero"
    And a project "proj-c" registered under org "other-org"
    When I GET /api/v1/projects
    Then the response status code should be 200
    And the response body should contain "proj-a"
    And the response body should contain "proj-b"
    And the response body should NOT contain "proj-c"

  Scenario: List projects supports pagination
    Given 25 projects registered for the authenticated org
    When I GET /api/v1/projects?page=1&page_size=10
    Then the response status code should be 200
    And the response body should contain exactly 10 projects
    And the response body should contain a "total" field with value 25

  # ── Detail ────────────────────────────────────────────────────────────────

  Scenario: Get project detail returns full project metadata
    Given a project with slug "lodge" is registered
    When I GET /api/v1/projects/lodge
    Then the response status code should be 200
    And the response body should contain a "slug" field
    And the response body should contain a "starter" field
    And the response body should contain a "github_repo" field
    And the response body should contain a "registered_at" field

  Scenario: Get non-existent project returns 404
    When I GET /api/v1/projects/does-not-exist
    Then the response status code should be 404
