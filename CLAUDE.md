# WebHarvest — Project Context

## Overview

Open-source, self-hosted web scraping platform. Firecrawl-compatible API.

**Stack**: FastAPI (Python 3.12) · Next.js 14 App Router (TypeScript) · PostgreSQL 16 · Redis 7 · Celery · Docker Compose

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Frontend    │───▶│  Backend     │───▶│  Celery      │
│  Next.js 14  │    │  FastAPI     │    │  Workers x2  │
│  :3000       │    │  :8000       │    │  (4 conc ea) │
└─────────────┘    └──────┬───────┘    └──────┬───────┘
                          │                    │
                   ┌──────┴───────┐    ┌──────┴───────┐
                   │  PostgreSQL  │    │    Redis      │
                   │  :5433→5432  │    │  :6380→6379   │
                   └──────────────┘    └──────────────┘
                                       │
                   ┌───────────────┐   │  DB 0: cache
                   │ Stealth Engine│   │  DB 1: broker
                   │ :8888 (opt)   │   │  DB 2: results
                   └───────────────┘
                   ┌───────────────┐
                   │ go-html-to-md │
                   │ :8080 (opt)   │
                   └───────────────┘
```

## Key Directories

| Path | Purpose |
|------|---------|
| `backend/app/api/v1/` | FastAPI route handlers (scrape, crawl, map, search, extract, auth, jobs, monitors, schedules, webhooks) |
| `backend/app/models/` | SQLAlchemy async ORM models |
| `backend/app/services/` | Business logic — scraper (5-tier pipeline), crawler (BFS producer-consumer), browser pool, LLM extraction |
| `backend/app/workers/` | Celery tasks (scrape, crawl, map, search, extract, monitor, schedule, cleanup) |
| `backend/app/core/` | Infrastructure: database, cache, redis, security, rate limiter, metrics, exceptions |
| `backend/app/schemas/` | Pydantic request/response models |
| `backend/tests/` | Pytest async test suite |
| `backend/alembic/` | Database migrations |
| `frontend/src/app/` | Next.js 14 App Router pages |
| `frontend/src/components/` | React components (Shadcn/ui + Radix primitives) |
| `frontend/src/lib/` | ApiClient, utilities |
| `stealth-engine/` | Isolated browser sidecar with advanced fingerprinting |
| `sdk/` | Python SDK for WebHarvest API |

## Development Commands

```bash
# Start all services
docker compose up -d

# Backend tests
cd backend && python -m pytest tests/ -v

# Frontend dev (if running outside Docker)
cd frontend && npm run dev

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"

# Celery worker (manual, outside Docker)
celery -A app.workers.celery_app worker -l info -c 4 -Q scrape,crawl,map,search

# Logs
docker compose logs -f backend
docker compose logs -f celery-worker
```

## Conventions

### Python (Backend)
- **Async everywhere**: FastAPI endpoints, SQLAlchemy, Redis, Playwright — all async/await
- **Linter**: Ruff
- **Type hints**: Full typing on all functions, Pydantic models for validation
- **Imports**: Absolute from `app.` namespace (e.g., `from app.services.scraper import ...`)
- **Error handling**: Custom exceptions in `core/exceptions.py` (AuthenticationError, RateLimitError, NotFoundError, BadRequestError)
- **Logging**: Structured JSON via `core/logging_config.py`, always include request_id context

### TypeScript (Frontend)
- **Framework**: Next.js 14 App Router, `"use client"` for interactive components
- **UI**: Shadcn/ui + Radix UI + Tailwind CSS
- **Strict mode**: TypeScript strict enabled
- **Path aliases**: `@/*` → `./src/*`
- **API calls**: Use `ApiClient` class from `lib/api.ts` (handles JWT auth)
- **Lint**: ESLint with `next/core-web-vitals`

### Database
- **ORM**: SQLAlchemy 2.0 async (asyncpg driver)
- **Migrations**: Alembic with autogenerate
- **Session**: One async session per request via `get_db` dependency
- **Naming**: snake_case tables and columns

### Celery
- **Queues**: `scrape`, `crawl`, `map`, `search` (routed by task type)
- **Beat tasks**: `check_schedules` (60s), `check_monitors` (60s), `cleanup_old_data` (24h)
- **DLQ**: Failed tasks go to `dlq:tasks` Redis list
- **Worker config**: max 100 tasks/child, 512MB soft memory limit

## Auth

Two methods:
1. **JWT** (`Bearer eyJ...`) — HS256, 7-day TTL, from `/v1/auth/login`
2. **API Key** (`Bearer wh_...`) — persistent, hashed in DB, from `/v1/auth/api-keys`

Sensitive data (LLM keys, proxy configs) encrypted with Fernet (AES-256).

## Ports (Docker Compose → Host)

| Service | Container | Host |
|---------|-----------|------|
| Backend | 8000 | 8000 |
| Frontend | 3000 | 3000 |
| PostgreSQL | 5432 | **5433** |
| Redis | 6379 | **6380** |

## Environment Variables

See `.env.example` for all config. Key ones:
- `SECRET_KEY` — JWT signing
- `ENCRYPTION_KEY` — Fernet key (exactly 32 chars)
- `DATABASE_URL` — `postgresql+asyncpg://webharvest:webharvest@db:5432/webharvest`
- `REDIS_URL` — `redis://redis:6379/0`
- `CELERY_BROKER_URL` — `redis://redis:6379/1`
- `GO_HTML_TO_MD_URL`, `STEALTH_ENGINE_URL` — optional sidecars

## Testing

- **Framework**: Pytest with `asyncio_mode = auto`
- **DB**: SQLite in-memory (isolated per test)
- **Fixtures**: `conftest.py` provides `db_session`, `client`, `authed_client`, `test_user`, `mock_browser_pool`, `mock_redis`
- **Pattern**: Rate limiter mocked to always allow, browser pool fully mocked

## External Services

- **GitHub**: `github.com/Takezo49` — repo hosting, CI/CD
- **Sentry**: Error tracking (production)
- **Linear**: Issue tracking and project management
