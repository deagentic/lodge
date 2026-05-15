# ARCHITECTURE.md — Lodge

## Overview

Lodge is a **FastAPI + PostgreSQL** service following strict **hexagonal architecture**
(ports & adapters). It exposes four surfaces:

| Surface | Transport | Consumers |
|---------|-----------|-----------|
| REST API | HTTP/JSON | Cornerstone CLI, CI pipelines, humans |
| MCP Server | SSE (MCP protocol) | AI agents (Cornerstone, Gemini, crisol-gateway) |
| Frontend | HTTP/HTML | Humans (browser) |
| Webhooks | HTTP/JSON | GitHub, SonarQube, Cornerstone CI (inbound) + custom targets (outbound) |

---

## Hexagonal Layer Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        ADAPTERS — INBOUND                        │
│                                                                   │
│  FastAPI Routers     Lodge MCP Server    Frontend    Webhooks    │
│  (HTTP REST)         (SSE /mcp)          (/ui)       (/webhooks) │
└───────────────────────────┬─────────────────────────────────────┘
                            │  calls
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                          PORTS (ABCs)                            │
│                                                                   │
│  ProjectRepository   IdpPort   FinOpsRepository   EventPort     │
│  McpCatalogRepository          RbacRepository                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │  implements
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ADAPTERS — OUTBOUND                          │
│                                                                   │
│  SQLAlchemy repos    GitHubIdpAdapter     GitHubGatewayClient   │
│  (PostgreSQL)        (device flow)        (PR open/update)       │
│                      WebhookDispatcher    SonarWebhookHandler   │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │  are injected into
┌─────────────────────────────────────────────────────────────────┐
│                        DOMAIN (pure Python)                      │
│                                                                   │
│  auth/      projects/    rbac/      finops/                     │
│  events/    mcp_catalog/                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Invariant

`domain/` has **zero** imports from `adapters/`. All I/O crosses a port interface.
This makes every domain service unit-testable without a database or network.

---

## Source Tree

```
src/lodge/
├── server.py                  # FastAPI app factory + router wiring
├── domain/
│   ├── auth/                  # Device flow state machine, token lifecycle
│   ├── projects/              # Project registration, idempotency, org isolation
│   ├── rbac/                  # Role model, grant/revoke, scope enforcement
│   ├── finops/                # Cost aggregation, burn rate, top consumers
│   ├── events/                # Event ingestion, query
│   └── mcp_catalog/           # Security-audit gate, PR lifecycle, catalog queries
├── ports/
│   ├── idp_port.py            # Abstract: request_device_code(), exchange_code(), …
│   ├── project_repository.py
│   ├── rbac_repository.py
│   ├── finops_repository.py
│   ├── event_port.py
│   └── mcp_catalog_repository.py
├── adapters/
│   ├── inbound/
│   │   ├── auth_router.py
│   │   ├── projects_router.py
│   │   ├── rbac_router.py
│   │   ├── finops_router.py
│   │   ├── events_router.py
│   │   ├── mcp_catalog_router.py
│   │   └── health.py
│   └── outbound/
│       ├── sqlalchemy/        # All repo implementations
│       ├── github_idp.py      # GitHub Device Flow adapter
│       ├── google_idp.py      # (future)
│       ├── github_gateway.py  # Opens/updates PRs on crisol-gateway
│       └── webhook_dispatcher.py
├── mcp/
│   ├── server.py              # FastMCP server instance
│   └── tools.py               # Tool definitions (lodge_register_project, etc.)
├── frontend/
│   ├── static/                # JS/CSS bundles
│   └── templates/             # Jinja2 HTML templates
└── webhooks/
    ├── router.py              # POST /webhooks/{source}
    ├── verifier.py            # HMAC verification
    └── handlers/
        ├── github.py
        ├── sonarqube.py
        └── cornerstone_ci.py
```

---

## Domain Model (key entities)

```sql
-- Core tables (simplified)
projects    (id, slug, name, org, owner_team, sonar_key, created_at)
api_keys    (id, project_id, user_id, key_hash, scopes[], expires_at)
rbac_grants (id, user_id, role, granted_by, created_at, revoked_at)
telemetry   (id, project_id, event_type, model, tokens_in, tokens_out,
             cost_usd, team, skill, ts)
mcp_entries (id, server_name, owner_team, security_audit_status,
             pr_url, version, metadata jsonb, updated_at)
webhook_subs(id, org, target_url, events[], secret_hash, active)
```

---

## Identity Provider (IdP) — Adapter Pattern

```
IDP_PROVIDER=github   →  adapters/outbound/github_idp.py   (default)
IDP_PROVIDER=google   →  adapters/outbound/google_idp.py   (future)
IDP_PROVIDER=azure    →  adapters/outbound/azure_idp.py    (future)
IDP_PROVIDER=keycloak →  adapters/outbound/keycloak_idp.py (future)
```

The active adapter is selected at startup by `server.py` based on `IDP_PROVIDER` and
injected into all domain services that call `IdpPort`. Switching providers requires only
an env var change — no domain code changes.

---

## MCP Server

Lodge's MCP server (`src/lodge/mcp/`) is built with **FastMCP** and mounted at `/mcp`
using SSE transport. It gives AI agents first-class tool access to Lodge:

```python
# Conceptual tool signatures (see tools.py for full docstrings)
lodge_register_project(name, org, owner_team, sonar_key) → ProjectRecord
lodge_get_project(slug) → ProjectRecord
lodge_get_finops_summary(team?, project?, from?, to?, group_by?) → FinOpsSummary
lodge_get_burn_rate() → BurnRate
lodge_list_mcp_catalog(security_audit_status?) → list[McpEntry]
lodge_register_mcp(payload: mcp_catalog_yaml) → RegistrationResult
lodge_get_dependency_graph(format?) → DependencyGraph  # json | mermaid
lodge_get_health() → EcosystemHealth
```

All MCP tools route through the domain layer — they share the same use cases as the REST API.

---

## Frontend

The web UI is served by Lodge itself as a **FastAPI static mount + Jinja2 templates**:

```
GET /ui                 → Dashboard (health + burn rate overview)
GET /ui/graph           → Interactive service dependency graph (D3.js)
GET /ui/finops          → FinOps charts (Chart.js)
GET /ui/projects        → Project registry table
GET /ui/mcp-catalog     → MCP catalog browser
GET /ui/rbac            → RBAC management (admin only)
```

The frontend is intentionally minimal — no build step for the initial version (vanilla JS + Jinja2).
A full React/Next.js frontend is listed in FUTURE.md.

---

## Webhook Flow

### Inbound
```
POST /webhooks/github      →  verifier (HMAC-SHA256)  →  github.py handler
POST /webhooks/sonarqube   →  verifier                →  sonarqube.py handler
POST /webhooks/ci          →  verifier                →  cornerstone_ci.py handler
```

### Outbound
```
Domain event emitted  →  EventPort.publish()
                       →  WebhookDispatcher
                       →  filters active subscriptions (webhook_subs table)
                       →  POST to each target URL with HMAC signature
```

Outbound retries: 3 attempts with exponential backoff (2s, 8s, 32s).

---

## Integration Map

```
Cornerstone CLI (CS)
  ├── cornerstone login          →  POST /api/v1/auth/device/request
  ├── cornerstone project init   →  POST /api/v1/projects/init
  └── MCP tool calls             →  GET  /mcp  (SSE)

crisol-gateway
  ├── Reads MCP catalog          →  GET  /api/v1/mcp/catalog
  └── MCP registration PR webhook→  POST /webhooks/github

KeyStone (KS)
  └── Queries project context    →  GET  /api/v1/projects/{slug}

SonarQube
  └── Scan complete webhook      →  POST /webhooks/sonarqube

GitHub OAuth
  └── Device Flow exchange       →  GitHub API  (outbound from Lodge)
```

---

## Containerization (ADR-0002)

### Docker — multi-stage build

```
Stage 1 — builder
  python:3.11-slim + build-essential + libpq-dev
  pip install --prefix=/install -r requirements.txt

Stage 2 — runtime  (final image)
  python:3.11-slim + libpq5 only
  COPY --from=builder /install
  pip install -e .  (no-deps)
  CMD uvicorn lodge.server:app
```

Build tools are stripped from the runtime image, reducing size by ~60% and eliminating
gcc/build-essential CVEs from the attack surface.

### docker-compose services

| Service | Image | Ports | Notes |
|---------|-------|-------|-------|
| `postgres` | `postgres:16-alpine` | 5432 | Healthcheck with `pg_isready` |
| `lodge` | `build: .` | 8000 | Runs `alembic upgrade head` before uvicorn |
| `grafana` _(optional)_ | `dashboard/grafana` | 3000 | Uncomment to enable FinOps dashboards |

### Migration strategy

Migrations run as part of the `lodge` container startup:
```yaml
command: sh -c "alembic upgrade head && uvicorn lodge.server:app ..."
```

For HA production deployments (multiple replicas), run migrations as a one-off
Kubernetes `Job` before the Deployment rolls out (see FUTURE.md).

### Healthcheck

```yaml
test: ["CMD-SHELL", "curl -sf http://localhost:8000/v1/healthz || exit 1"]
start_period: 15s   # accommodates migration time on first startup
```

`/v1/healthz` is the liveness probe: no auth, no DB call, reflects process health only.
`/v1/ready` is the readiness probe: checks DB + IdP connectivity.

### Single container, all surfaces

All four surfaces (REST API, MCP Server, Frontend, Webhooks) are served by a single
`lodge.server:app` FastAPI process. Splitting into multiple containers is possible
without breaking the hexagonal boundaries — tracked in FUTURE.md.

---

## ADR Trail

| ADR | Decision |
|-----|----------|
| [ADR-0001](docs/adr/ADR-0001-lodge-architecture.md) | Lodge architecture, hexagonal structure, 6 domains, IdP adapter pattern |
| [ADR-0002](docs/adr/ADR-0002-containerization-strategy.md) | Containerization: multi-stage build, single container, migration-on-startup |
| [ADR-0089 (Cornerstone)](https://github.com/deagentic/cornerstone/blob/master/docs/adr/ADR-0089-lodge-platform-server.md) | Decision to create Lodge, naming rationale, FM-01 resolution |
| [ADR-0090 (Cornerstone)](https://github.com/deagentic/cornerstone/blob/master/docs/adr/ADR-0090-adr-gate-repo-boundary.md) | ADR gate repo-boundary guard (fixes cross-repo false positives) |
