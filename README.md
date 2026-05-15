# Lodge

A FastAPI + PostgreSQL service scaffolded by Cornerstone

**Archetype:** `api` (FastAPI + PostgreSQL)
**Scaffolded by:** [Cornerstone](https://github.com/deagentic/cornerstone)

## Quick Start

```bash
cp .env.example .env
# Edit .env with your database credentials
docker compose up -d
```

## API Endpoints

- `POST /v1/events` — ingest events
- `GET /v1/events` — query events
- `GET /v1/summary` — aggregated stats
- `GET /health` — liveness probe
- `GET /` — dashboard

## CLI

```bash
pip install -e .
cornerstone-obs report summary --url http://localhost:8000
```
