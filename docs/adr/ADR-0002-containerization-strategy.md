# ADR-0002 — Containerization Strategy

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-15 |
| **Deciders** | Lodge platform team |

## Context

Lodge exposes four surfaces: REST API, MCP Server (SSE), Frontend (static + Jinja2), and
Webhooks. A containerization strategy must answer:

1. How many containers serve these surfaces?
2. How is the Docker image built (single-stage vs. multi-stage)?
3. When do database migrations run?
4. How is the container monitored for health?
5. What does local development look like?

## Decision

### 1. Single application container

All four surfaces (REST, MCP, frontend, webhooks) are served by a single FastAPI process
(`lodge.server:app`). The `server.py` app factory mounts all routers, the MCP SSE
endpoint, the static frontend assets, and the webhook router.

**Rationale:** Lodge is a coordination service, not a high-throughput data plane. A
monolith is operationally simpler, avoids inter-service latency, and simplifies
deployment for teams self-hosting Lodge. The architecture's hexagonal boundaries are
enforced at the code level, not the process level — splitting into multiple containers
would add deployment complexity without a corresponding scalability need at this stage.

Surfaces can be extracted into separate containers in the future if Lodge sees traffic
patterns that justify it (tracked in FUTURE.md).

### 2. Multi-stage Docker build

```
Stage 1 — builder: python:3.11-slim + build-essential + libpq-dev
  → pip install --prefix=/install -r requirements.txt
Stage 2 — runtime: python:3.11-slim + libpq5 only
  → COPY --from=builder /install
  → pip install -e . (no-deps, editable for source)
```

**Rationale:** Build toolchains (gcc, build-essential) are not needed at runtime.
Excluding them reduces the final image by ~60% and eliminates known CVE vectors in
build tools. The `libpq5` runtime library is the only native dependency Lodge needs.

### 3. Migration-on-startup in docker-compose

The `lodge` service runs `alembic upgrade head` before starting uvicorn:

```yaml
command: >
  sh -c "alembic upgrade head &&
         uvicorn lodge.server:app --host 0.0.0.0 --port 8000"
```

**Rationale:** For self-hosted deployments and local development, migration-on-startup
is the simplest strategy — no separate migration job, no manual steps. The postgres
service has a `healthcheck` and `depends_on: condition: service_healthy` so Lodge never
attempts migration before the database is ready.

**Trade-off:** In high-availability production deployments (multiple replicas), running
migrations on every pod startup can cause lock contention. For production at scale, the
recommendation is to run migrations as a one-off Kubernetes `Job` before the Deployment
rolls out. That transition is tracked in FUTURE.md.

### 4. Healthcheck via `/v1/healthz`

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:8000/v1/healthz || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 15s
```

**Rationale:** `/v1/healthz` is the liveness probe that requires no authentication and
no database call — it reflects process health only. Using it as the Docker healthcheck
means compose's `depends_on` chains work correctly for services that depend on Lodge.
The `start_period: 15s` accommodates migration time on first startup.

### 5. Environment variables

All Lodge-specific configuration is passed via environment variables. The docker-compose
file declares all variables explicitly with safe defaults or empty strings (not omitted),
so `docker compose config` reveals the complete configuration surface without reading
source code.

Variables containing secrets (`POSTGRES_PASSWORD`, `GITHUB_CLIENT_SECRET`,
`WEBHOOK_SECRET`) use `${VAR:?error}` or are left as empty strings — they are never
assigned defaults in the compose file.

## Consequences

- All Lodge surfaces (REST, MCP, frontend, webhooks) start and stop together.
- The Docker image is smaller and has a reduced attack surface (no build tools at runtime).
- Local development requires only `docker compose up -d` — no separate migration step.
- Production deployments at scale must override the migration strategy (separate Job).
- `lodge.server:app` is the canonical entrypoint; `lodge.adapters.inbound.api:app`
  (the scaffold template default) is incorrect and must not be used.
