# ADR-0001: Lodge — Architecture and Domain Model

**Status:** Accepted
**Deciders:** DeAcero Platform Team
**Date:** 2026-05-15

---

## Context and Problem Statement

Lodge is the **active platform coordinator** of the Cornerstone ecosystem
(`deagentic/cornerstone` ADR-0089). It resolves pre-mortem finding FM-01
(issue #334): the entire L0 onboarding flow (`cornerstone login` →
`cornerstone new` → first CI run) was unexecutable without a central server.

Lodge's role is that of an *intendente de obra* — it registers every actor
in the ecosystem and distributes exactly the information each actor needs,
when it needs it, and no more.

**LODGE** = **L**ifecycle · **O**rchestration · **D**istribution · **G**overnance · **E**vents

---

## Architecture Decision

### Starter

Scaffolded from the Cornerstone `api` starter (FastAPI + PostgreSQL + Alembic),
which enforces hexagonal architecture (ADR-0013) and the full governance pipeline
(ADR-first, TDD+BDD, SonarQube, 100% coverage).

### Hexagonal layer map

```
src/lodge/
├── domain/          # Pure Python — zero framework imports
│   ├── auth/        # Device Flow state machine, token issuance, RBAC rules
│   ├── projects/    # Project registration, lifecycle state machine
│   ├── finops/      # Cost aggregation, burn rate models
│   └── events/      # Event envelope validation, routing rules
├── ports/           # Abstract interfaces (repositories, IdP, GitHub client)
├── adapters/
│   ├── inbound/     # FastAPI routers — one module per domain
│   └── outbound/    # SQLAlchemy repos, GitHub HTTP client, IdP OAuth client
└── server.py        # FastAPI app composition root
```

The domain layer has **no knowledge** of FastAPI, SQLAlchemy, or any IdP SDK.
All I/O crosses a port boundary.

### Identity Provider

GitHub OAuth is the **default configurable** IdP. The `IDP_PROVIDER` environment
variable selects the backend adapter at startup:

| `IDP_PROVIDER` | Adapter |
|----------------|---------|
| `github` (default) | GitHub OAuth App — Device Flow via `github.com/login/device/code` |
| `google` | Google OAuth 2.0 + PKCE |
| `azure` | Azure AD OAuth 2.0 |
| `keycloak` | Keycloak OIDC |

The domain layer sees only the `IdentityPort` interface — the provider is
an outbound adapter swapped at compose time. No domain code changes when the
IdP changes.

### The 6 domains

| Domain | Responsibility | Primary endpoints |
|--------|---------------|-------------------|
| **Auth** | Device Flow login, API key issuance, token validation, logout | `/api/v1/auth/*` |
| **Projects** | Project registration (`cornerstone new`), lifecycle | `/api/v1/projects/*` |
| **RBAC** | Role grants, permission checks per endpoint | `/api/v1/rbac/*` |
| **FinOps** | Cost aggregation by team/project/model, burn rate | `/api/v1/finops/*` |
| **Events** | Telemetry ingest + query (ADR-0001/ADR-0002 schema) | `/v1/events/*` |
| **MCP Catalog** | Register MCPs, open PRs on crisol-gateway | `/api/v1/mcp/*` |

### Data model summary

| Table | Purpose |
|-------|---------|
| `users` | Identity record created at first login |
| `api_keys` | Scoped tokens with expiry and revocation flag |
| `rbac_grants` | Role → user → resource assignments |
| `projects` | Project slug, starter, GitHub repo, team, org |
| `events` | Telemetry events (JSONB payload, ADR-0002 schema) |
| `mcp_catalog` | MCP entries with `security_audit_status` |

### Self-hosting

```bash
# Minimal self-host
IDP_PROVIDER=github \
IDP_CLIENT_ID=<gh-oauth-app-client-id> \
IDP_CLIENT_SECRET=<secret> \
docker compose up
```

Full configuration reference: `docker-compose.yml`.
`cornerstone doctor` checks `GET /v1/healthz` to verify reachability.

---

## Consequences

### Positive
- L0 onboarding is fully executable: `cornerstone login` → `cornerstone new` → CI ✓
- Domain logic is IdP-agnostic — swap GitHub for Google/Azure with one env var
- Lodge governs itself with the same ADR-first + TDD+BDD pipeline it provides to others
- Events domain gives Lodge telemetry parity with `services/observability/`

### Negative
- Lodge is a new runtime dependency for CLI authentication — teams need it deployed
  before `cornerstone login` works
- GitHub OAuth Device Flow requires a registered GitHub OAuth App per org deployment

### Neutral
- `services/observability/` (Cornerstone repo) remains the short-term telemetry
  receiver; Lodge's Events domain provides the long-term migration path
