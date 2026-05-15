# Lodge

**L·O·D·G·E** — _Lifecycle · Orchestration · Distribution · Governance · Events_

Lodge is the platform server for the **Stoneworks ecosystem**. It is the "intendente de obra":
the active coordinator that registers every project, enforces governance, tracks spend,
manages RBAC, catalogs MCP servers, and broadcasts events to every actor that needs them.

> Lodge is not a stone — it is the institution that coordinates the stoneworks. is intended for
> the administrators use to track, accept, give permissions, and, generally, allow the creation
> and access of new components into the Stoneworks ecosystem.

---

## Architecture at a glance

```
Cornerstone CLI  ──────►  Lodge REST API   ◄──── crisol-gateway
                          Lodge MCP Server  ◄──── AI Agents (Cornerstone, Gemini, etc.)
                          Lodge Frontend    ◄──── Humans (browser)
                          Lodge Webhooks   ──────► GitHub / SonarQube / Slack / custom
```

Lodge is built on **FastAPI + PostgreSQL** using a hexagonal (ports & adapters) architecture.
It authenticates via **GitHub OAuth Device Flow** by default (`IDP_PROVIDER=github`).

---

## Quick Start

```bash
cp .env.example .env
# Set at minimum:
#   DATABASE_URL=postgresql+asyncpg://lodge:lodge@localhost:5432/lodge
#   IDP_PROVIDER=github
#   GITHUB_CLIENT_ID=<your-oauth-app>
#   GITHUB_CLIENT_SECRET=<your-oauth-app-secret>
#   GITHUB_GATEWAY_REPO=deagentic/crisol-gateway

docker compose up -d
```

The API is available at `http://localhost:8000`.
The dashboard is available at `http://localhost:8000/ui`.

### Cornerstone CLI integration

```bash
cornerstone login --lodge-url http://localhost:8000
cornerstone project init --name "my-service"
```

---

## API Domains

### Auth  `/api/v1/auth`
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/device/request` | Begin GitHub OAuth Device Flow |
| `POST` | `/api/v1/auth/device/exchange` | Exchange device code for access token |
| `POST` | `/api/v1/auth/logout` | Revoke session |
| `GET`  | `/api/v1/auth/me` | Current user info |

### Projects  `/api/v1/projects`
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/projects/init` | Register a new project |
| `GET`  | `/api/v1/projects` | List all projects (paginated) |
| `GET`  | `/api/v1/projects/{slug}` | Get project detail |
| `PATCH`| `/api/v1/projects/{slug}` | Update project metadata |

### RBAC  `/api/v1/rbac`
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/rbac/roles` | List current user's roles |
| `POST` | `/api/v1/rbac/grants` | Grant a role (admin only) |
| `DELETE`| `/api/v1/rbac/grants/{id}` | Revoke a grant (admin only) |

### FinOps  `/api/v1/finops`
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/finops/summary` | Cost breakdown by team/model/project |
| `GET`  | `/api/v1/finops/burn-rate` | Daily spend vs. monthly budget |
| `GET`  | `/api/v1/finops/top-consumers` | Top 10 cost drivers |

### MCP Catalog  `/api/v1/mcp`
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/mcp/register` | Register/update an MCP server (opens PR on crisol-gateway) |
| `GET`  | `/api/v1/mcp/catalog` | List all registered MCPs |
| `PATCH`| `/api/v1/mcp/catalog/{name}` | Update MCP catalog entry |

### Events  `/api/v1/events`
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/events` | Ingest a telemetry event |
| `GET`  | `/api/v1/events` | Query events (with filters) |

### Health
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/v1/healthz` | Liveness probe (no auth) |
| `GET`  | `/v1/ready` | Readiness probe (DB + IdP) |

---

## Lodge MCP Server

Lodge exposes an **MCP server** at `/mcp` (SSE transport) so AI agents can call Lodge tools
directly without raw HTTP:

```
lodge_register_project     — register a new project in the catalog
lodge_get_project          — retrieve project metadata
lodge_get_finops_summary   — cost breakdown for a team or project
lodge_get_burn_rate        — current spend vs. budget
lodge_list_mcp_catalog     — browse registered MCP servers
lodge_register_mcp         — register an MCP server (security-audit-gated)
lodge_get_dependency_graph — service dependency graph (JSON + Mermaid)
lodge_get_health           — ecosystem health snapshot
```

```bash
# Add Lodge to your Cornerstone project's MCP config:
cornerstone mcp add lodge --url http://localhost:8000/mcp
```

---

## Frontend

The web dashboard lives at `/ui` and is served directly by Lodge.
It provides:
- **Ecosystem health** — live status of all registered services
- **Service dependency graph** — interactive D3.js graph of service-to-service dependencies
- **FinOps dashboards** — spend trends, burn rate, top consumers
- **Project registry** — searchable table of all registered projects
- **MCP catalog** — security audit status, owner, version for each MCP server
- **RBAC management** — grant/revoke roles (admin only)

---

## Webhooks

### Inbound (Lodge receives)
| Source | Event | Lodge action |
|--------|-------|--------------|
| GitHub | `pull_request` merged on crisol-gateway | Sync MCP catalog status |
| SonarQube | `analysis_complete` | Update project quality score |
| Cornerstone CI | `ci_passed` | Update project build status |

### Outbound (Lodge dispatches)
| Trigger | Payload |
|---------|---------|
| Project registered | `lodge.project.registered` |
| Budget threshold crossed | `lodge.finops.budget_alert` |
| MCP audit failed | `lodge.mcp.audit_failed` |
| New role granted | `lodge.rbac.grant_created` |

Outbound webhook targets are configured per-org in `.env` or the admin UI.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL async DSN |
| `IDP_PROVIDER` | `github` | Identity provider (`github`, `google`, `azure`, `keycloak`) |
| `GITHUB_CLIENT_ID` | — | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth App secret |
| `GITHUB_GATEWAY_REPO` | `deagentic/crisol-gateway` | Repo where MCP PRs are opened |
| `MCP_SERVER_ENABLED` | `true` | Enable/disable the Lodge MCP server |
| `WEBHOOK_SECRET` | — | HMAC secret for inbound webhook verification |
| `MONTHLY_BUDGET_USD` | — | Org-level monthly AI spend budget |

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn lodge.server:app --reload
```

```bash
pytest tests/                      # unit + integration
pytest tests/features/ --bdd       # BDD scenarios
```

---

## Ecosystem position

```
Cornerstone (CS — Central Scaffolder)  ←→  Lodge (LODGE — platform server)
KeyStone    (KS — Knowledge System)    ←→  Lodge (queries Lodge for project context)
crisol-gateway                         ←→  Lodge (MCP catalog sync via PR)
```

See [ADR-0089](https://github.com/deagentic/cornerstone/blob/master/docs/adr/ADR-0089-lodge-platform-server.md)
for the full architectural rationale.
