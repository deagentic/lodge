# AGENTS.md — Lodge
**READ THIS FIRST. Every agent, every session, no exceptions.**

## 1. Project Mandate

Lodge is the **"intendente de obra"** of the deAgentic ecosystem:
the active coordinator that registers every project, enforces RBAC, tracks FinOps,
catalogs MCP servers, emits events, and exposes all of this to both humans (frontend)
and AI agents (its own MCP server).

**Acronym:** **L·O·D·G·E** — _Lifecycle · Orchestration · Distribution · Governance · Events_

Lodge is **not** a passive component. It is the operational intelligence layer that sits
between the Cornerstone scaffolder (CS) and the crisol-gateway router, ensuring that
every actor — human, agent, or system — has access to exactly what it needs, when it
needs it, and nothing more.

## 2. Universal Rules

- **ADR-First:** Any change to `src/` requires a prior ADR in `docs/adr/`. Write the ADR
  before writing the code.
- **BDD-First within features:** New features require Gherkin scenarios in `tests/features/`
  before any implementation. The `.feature` files are the source of truth.
- **No tests, no merge:** Every PR must pass `pytest tests/` with ≥ 95% coverage and all
  BDD scenarios green.
- **IDP is configurable:** Do not hardcode GitHub. Always route IdP calls through
  `src/lodge/ports/idp_port.py` — the adapter is selected via `IDP_PROVIDER` env var.
- **Security-audit gate on MCP registration:** Never bypass the `security_audit_status`
  check in the MCP catalog flow. Deferred registrations are valid; failed ones are
  permanently rejected.

## 3. Context Routing

| Working in... | Load before acting |
|---|---|
| `src/lodge/domain/` | `docs/adr/ADR-0001-lodge-architecture.md` + relevant domain ADR |
| `src/lodge/adapters/inbound/` | `.agents/AGENTS.server.md` |
| `src/lodge/adapters/outbound/` | `.agents/AGENTS.server.md` |
| `src/lodge/mcp/` | `.agents/AGENTS.server.md` + `mcp_catalog.feature` |
| `src/lodge/frontend/` | `.agents/AGENTS.server.md` — UI is served by FastAPI static mount |
| `src/lodge/webhooks/` | `.agents/AGENTS.server.md` + `events.feature` |
| `tests/features/` | `.agents/skills/software/quality/bdd-writer/SKILL.md` |
| `tests/` (unit/integration) | `.agents/skills/software/quality/tdd-developer/SKILL.md` |
| `docs/adr/` | `.agents/skills/software/quality/adr-writer/SKILL.md` |
| Starting a new feature | `.agents/skills/software/quality/tech-lead/SKILL.md` |
| Reviewing code before merge | `.agents/skills/software/quality/code-reviewer/SKILL.md` |
| Final gate before merge | `.agents/skills/software/quality/qa-validator/SKILL.md` |

## 3a. Domain Routing

| Domain | Source paths | BDD feature file |
|--------|-------------|-----------------|
| Auth (GitHub OAuth Device Flow) | `src/lodge/domain/auth/` | `tests/features/auth.feature` |
| Projects | `src/lodge/domain/projects/` | `tests/features/projects.feature` |
| RBAC | `src/lodge/domain/rbac/` | `tests/features/rbac.feature` |
| FinOps | `src/lodge/domain/finops/` | `tests/features/finops.feature` |
| MCP Catalog | `src/lodge/domain/mcp_catalog/` | `tests/features/mcp_catalog.feature` |
| Events / Telemetry | `src/lodge/domain/events/` | `tests/features/events.feature` |
| MCP Server (Lodge's own) | `src/lodge/mcp/` | `tests/features/mcp_server.feature` |
| Frontend | `src/lodge/frontend/` | manual + e2e |
| Webhooks | `src/lodge/webhooks/` | `tests/features/webhooks.feature` |
| Health | `src/lodge/adapters/inbound/health.py` | `tests/features/health.feature` |

## 3b. TDD+BDD Development Workflow (mandatory for all new features)

```
Story
 ├── 1. tech-lead      → define ACs and DoD (BLOCK if ACs are vague)
 ├── 2. bdd-writer     → write Gherkin scenarios in tests/features/ (BEFORE code)
 ├── 3. tdd-developer  → write failing unit tests (RED phase)
 ├── 4. tdd-developer  → implement until green (GREEN + REFACTOR)
 ├── 5. code-reviewer  → review diff + TDD discipline check
 └── 6. qa-validator   → scenario coverage audit + exploratory testing
```

**Invariant:** No implementation without prior failing tests.

## 4. Hexagonal Architecture Rules

Lodge uses strict hexagonal (ports & adapters) architecture:

```
domain/          ← Pure business logic. No framework imports. No I/O.
ports/           ← Abstract interfaces (ABCs). domain depends only on these.
adapters/
  inbound/       ← FastAPI routers. Translate HTTP/MCP/webhook → domain calls.
  outbound/      ← SQLAlchemy, IdP clients, GitHub API, webhook dispatcher.
```

**Rule:** `domain/` must never import from `adapters/`. All cross-boundary calls go through `ports/`.

## 5. Lodge MCP Server

Lodge's own MCP server (`src/lodge/mcp/`) exposes tools to AI agents.
New tools must:
1. Have a corresponding Gherkin scenario in `tests/features/mcp_server.feature`
2. Be declared in `src/lodge/mcp/tools.py` with full docstring (used as MCP tool description)
3. Route through the domain layer — never call the database directly from MCP tools

## 6. Webhooks

- **Inbound** webhooks from GitHub, SonarQube, and Cornerstone CI land at `/webhooks/{source}`
- All inbound webhooks must be HMAC-verified against `WEBHOOK_SECRET` before processing
- **Outbound** events are dispatched by `src/lodge/webhooks/dispatcher.py` after domain events

## 7. Commands

```bash
# Start all services
docker compose up -d

# Run migrations
alembic upgrade head

# Dev server (hot reload)
uvicorn lodge.server:app --reload

# Run all tests
pytest tests/

# Run BDD scenarios only
pytest tests/features/ --bdd

# Check coverage
pytest --cov=src/lodge --cov-report=term-missing

# Lodge MCP dev (test MCP tools interactively)
mcp dev src/lodge/mcp/server.py
```

## 8. IdP Configuration

```bash
# GitHub (default)
IDP_PROVIDER=github
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Other providers (future)
IDP_PROVIDER=google | azure | keycloak
```

Never hardcode provider-specific logic in `domain/`. Always use `ports/idp_port.py`.

## 9. Governance

- **Gates:** GitOps (pre-tool), ADR, SemVer, GitFlow, Atomic Commits (CI)
- **Tools:** `tools/gitops_gate.py` for safety checks
- **Versions:** Semantic Versioning; cut releases from `master` via `cornerstone version bump`
- **Sonar:** `sonar-project.properties` is pre-configured — do not change `sonar.projectKey`
