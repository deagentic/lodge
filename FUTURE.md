# FUTURE.md — Lodge

Ideas, planned features, and long-horizon capabilities.
Items here are **not committed**. They exist to capture intent so future contributors
understand what the architecture was designed to accommodate.

Ordered roughly by implementation horizon.

---

## Near-term (next 2–3 sprints)

### Service Dependency Graph — Live View
Lodge currently stores project metadata and MCP catalog entries. The next step is to
infer and persist **service-to-service edges** from registration payloads and telemetry:

```
lodge_get_dependency_graph() → {
  "nodes": [{"id": "lodge", "type": "api"}, {"id": "crisol-bigquery-mcp", "type": "mcp"}, ...],
  "edges": [{"from": "crisol-gateway", "to": "crisol-bigquery-mcp", "protocol": "mcp"}, ...]
}
```

The frontend `/ui/graph` page will render this as an interactive D3.js force-directed
graph. Nodes are colored by health status (green/amber/red) from the last readiness check.

Implementation path:
- Add `service_edges` table to the data model (source, target, protocol, discovered_at)
- Populate via MCP registration payloads (declared dependencies) + webhook events (observed calls)
- Expose as JSON and as Mermaid `graph LR` in `lodge_get_dependency_graph(format=)`
- Frontend: D3.js in `/ui/graph`, auto-refreshes every 30s

### Ecosystem Health Dashboard
Extend `/ui` to poll `/v1/ready` and each registered service's `healthz` endpoint:
- Aggregate into a single `lodge_get_health()` snapshot
- Show uptime percentage, last incident time, P95 latency for each service
- Feed into the dependency graph node colors in real time

---

## Medium-term (1–2 months)

### MCP Internals Observability
As Lodge ingests telemetry events from crisol-gateway and individual MCP servers, it can
surface **per-tool metrics** across the ecosystem:

```
GET /api/v1/mcp/catalog/{name}/metrics
{
  "tool": "lodge_get_finops_summary",
  "p50_ms": 42,
  "p95_ms": 180,
  "error_rate": 0.003,
  "calls_last_24h": 1240,
  "top_callers": ["cornerstone-cli", "gemini-agent"]
}
```

This becomes the foundation for:
- **Alerting** when a tool's error rate exceeds a threshold (outbound webhook: `lodge.mcp.tool_degraded`)
- **Cost attribution** per tool call (already possible from token cost events)
- **Deprecation notices** — Lodge can warn when a tool is called that has a newer version

Implementation path:
- Add `mcp_tool_calls` materialized view from `telemetry` where `event_type='tool_call'`
- Aggregate by `(server_name, tool_name, day)` in a nightly batch
- Expose via REST + `lodge_get_mcp_metrics()` MCP tool

### Webhook Subscription UI
Expose `/ui/webhooks` for admins to register and test outbound webhook targets without
touching environment variables. Includes a "send test event" button and delivery logs.

### React/Next.js Frontend
Replace the Jinja2 templates with a proper React + TypeScript frontend:
- Better interactivity for the dependency graph (zoom, search, click-to-drill)
- Real-time updates via WebSockets or SSE for health and cost metrics
- Mobile-responsive layout
- Storybook for component documentation

Can be served as a static build mounted at `/ui` or deployed separately (Vercel/Cloud Run).

---

## Long-horizon (3–6 months)

### MCP Protocol Tracing
Full distributed trace of an agentic request as it travels through the ecosystem:

```
cornerstone agent run "summarize billing"
  → crisol-gateway  (route selection, 12ms)
    → lodge (lodge_get_finops_summary, 45ms)
      → PostgreSQL (query, 8ms)
    → crisol-bigquery-mcp (bq_query_costs, 280ms)
      → BigQuery (query, 240ms)
  → claude-sonnet-4-6 (inference, 1.2s, $0.0034)
```

Implementation path:
- Instrument all Lodge inbound adapters with OpenTelemetry trace IDs
- Propagate `traceparent` header through MCP tool calls
- Store trace spans in the `telemetry` table (or a dedicated `traces` table)
- Expose trace viewer in Lodge frontend (Jaeger-style waterfall)

### Multi-Org / Federation
Currently Lodge assumes a single org (`LODGE_ORG`). Federation would allow multiple
orgs to share a single Lodge deployment with strict data isolation, or for Lodge
instances to peer with each other to share a global MCP catalog.

Design considerations:
- Org-scoped API keys and RBAC grants (already partially in the data model)
- Cross-org MCP catalog sharing with configurable visibility (`public` / `org-private`)
- Lodge-to-Lodge event forwarding for ecosystem-wide health views

### AI-Assisted Governance
Lodge already has the telemetry, RBAC, and FinOps data to answer governance questions.
A future `lodge_ask()` MCP tool could answer natural language queries:

```
lodge_ask("Which teams are on track to exceed budget this month?")
lodge_ask("Which MCP servers have not had a security audit in 90 days?")
lodge_ask("What is the P95 cost-per-call for the crisol-bigquery-mcp tools?")
```

This would route through Lodge's own AI budget (Claude Sonnet) with a RAG query
over the Lodge database, and return structured answers with supporting data.

### Cornerstone CLI `doctor` Integration
Extend `cornerstone doctor` to call Lodge's health endpoint and dependency graph:
- Check that the current project is registered in Lodge
- Check that its declared MCP dependencies are healthy
- Warn if budget is within 20% of the monthly limit
- Flag any registered MCPs with `security_audit_status: failed`

---

## Architectural Constraints to Preserve

Any future capability must respect:

1. **Hexagonal boundary** — new features add domain services + ports, not HTTP calls from domain code
2. **IdP adapter pattern** — `IDP_PROVIDER` env var selects the adapter; domain code never hardcodes GitHub
3. **MCP tool → domain layer** — Lodge MCP tools are thin wrappers; business logic stays in `domain/`
4. **Security-audit gate** — `mcp_catalog` registration never bypasses the `security_audit_status` check
5. **Outbound webhooks are async** — `WebhookDispatcher` runs in a background task; domain services never wait on HTTP delivery
