# WebHarvest

**Open-source, self-hosted web scraping platform** with a modern dashboard, REST API, Python SDK, and background job processing.

Built with FastAPI + Next.js + PostgreSQL + Redis + Celery + Playwright.

---

## What It Does

WebHarvest lets you extract content from any website through 5 core actions:

| Action | Description |
|--------|-------------|
| **Scrape** | Extract content from a single URL - markdown, HTML, screenshots, links, structured data, headings, images |
| **Crawl** | Recursively crawl an entire website following links (BFS), scraping each page |
| **Map** | Fast URL discovery via sitemaps and homepage link extraction (no content scraping) |
| **Batch** | Scrape a list of URLs in parallel |
| **Search** | Search the web (DuckDuckGo/Google/Brave) and scrape each result page |

Every action creates a **Job** record in the database. Results are persisted and can be viewed, exported (JSON/CSV/ZIP), and accessed later from the dashboard or API.

---

## Features

- **Full Browser Rendering** - Playwright (Chromium + Firefox) handles JavaScript-heavy sites
- **Anti-Bot Bypass** - 20-level stealth injection, TLS fingerprint impersonation (curl_cffi), request interception, Google referrer chains, and cookie-enhanced HTTP
- **5-Tier Scraping Pipeline** - Strategy cache → Cookie HTTP → HTTP race → Browser race → Heavy strategies → Fallback archives, with per-domain strategy learning
- **Fast Crawling** - Persistent browser sessions, cookie reuse across pages, and producer-consumer pipeline overlap fetch and extraction for ~5x crawl speed
- **Smart Content Extraction** - Trafilatura strips boilerplate before processing
- **AI Extraction (BYOK)** - Bring your own OpenAI/Anthropic/Groq key for LLM-powered structured extraction
- **Scheduled Jobs** - Cron-based recurring scrapes with Celery Beat
- **Proxy Support** - Add your own proxies for rotation
- **Webhooks** - Get notified when jobs complete
- **Export** - Download results as JSON, CSV, or ZIP
- **Job History** - Full dashboard with filtering, search, and pagination
- **Python SDK** - Sync and async clients with polling helpers
- **REST API** - Complete API with JWT auth and API key support

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

That's it. Everything runs in containers.

### 1. Clone the repo

```bash
git clone https://github.com/Takezo49/WebHarvest.git
cd WebHarvest
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and change `SECRET_KEY` to a random string:

```
SECRET_KEY=change-this-to-a-random-string-at-least-32-chars
```

The defaults work for local development. No other changes needed.

### 3. Start everything

```bash
docker compose up --build
```

This starts 6 services:
- **Backend API** at `http://localhost:8000`
- **Frontend Dashboard** at `http://localhost:3000`
- **Celery Workers** (2 replicas for background jobs)
- **Celery Beat** (scheduler)
- **PostgreSQL** database
- **Redis** (caching + task queue)

### 4. Open the dashboard

Go to `http://localhost:3000` in your browser.

1. Click **Register** to create an account
2. Start scraping!

---

## Dashboard Pages

| Page | URL | What It Does |
|------|-----|-------------|
| **Home** | `/` | Quick action cards + recent activity feed |
| **Scrape** | `/scrape` | Single-page scraper with format toggles |
| **Crawl** | `/crawl` | Full-site crawler with depth/concurrency controls |
| **Map** | `/map` | URL discovery tool |
| **Batch** | `/batch` | Multi-URL scraper |
| **Search** | `/search` | Search + scrape engine |
| **Jobs** | `/jobs` | Full job history with filters |
| **Schedules** | `/schedules` | Cron-based recurring jobs |
| **API Keys** | `/api-keys` | Generate keys for programmatic access |
| **Settings** | `/settings` | LLM keys (BYOK) and proxy management |
| **Dashboard** | `/dashboard` | Usage stats, charts, and analytics |

After running a **Scrape** or **Map**, you're redirected to a detail page (`/scrape/{id}` or `/map/{id}`) where you can browse results with tabs and export data.

---

## API Reference

Base URL: `http://localhost:8000`

All endpoints require authentication via either:
- **Bearer token**: `Authorization: Bearer <jwt_token>`
- **API key**: `Authorization: Bearer <api_key>`

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'

# Login
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
# Returns: {"access_token": "eyJ..."}
```

### Scrape

```bash
# Scrape a URL
curl -X POST http://localhost:8000/v1/scrape \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "html", "links", "screenshot"]
  }'
# Returns: {"success": true, "data": {...}, "job_id": "uuid"}

# Get scrape result by job ID
curl http://localhost:8000/v1/scrape/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export scrape result
curl http://localhost:8000/v1/scrape/JOB_ID/export?format=json \
  -H "Authorization: Bearer YOUR_TOKEN" -o result.json
```

### Crawl

```bash
# Start a crawl (runs in background)
curl -X POST http://localhost:8000/v1/crawl \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "max_pages": 50,
    "max_depth": 3
  }'
# Returns: {"success": true, "job_id": "uuid", "status": "started"}

# Check crawl status (poll this until status is "completed")
curl http://localhost:8000/v1/crawl/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export crawl results
curl http://localhost:8000/v1/crawl/JOB_ID/export?format=zip \
  -H "Authorization: Bearer YOUR_TOKEN" -o crawl.zip

# Cancel a running crawl
curl -X DELETE http://localhost:8000/v1/crawl/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Map

```bash
# Map a website (discover URLs)
curl -X POST http://localhost:8000/v1/map \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "limit": 200,
    "use_sitemap": true
  }'
# Returns: {"success": true, "total": 150, "links": [...], "job_id": "uuid"}

# Get map result by job ID
curl http://localhost:8000/v1/map/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export map results
curl http://localhost:8000/v1/map/JOB_ID/export?format=csv \
  -H "Authorization: Bearer YOUR_TOKEN" -o urls.csv
```

### Batch Scrape

```bash
# Scrape multiple URLs in parallel
curl -X POST http://localhost:8000/v1/batch/scrape \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/page1", "https://example.com/page2"],
    "formats": ["markdown"],
    "concurrency": 5
  }'

# Check batch status
curl http://localhost:8000/v1/batch/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search + Scrape

```bash
# Search the web and scrape results
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "best python web frameworks 2025",
    "num_results": 5,
    "engine": "duckduckgo"
  }'

# Check search status
curl http://localhost:8000/v1/search/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Scrape Options (All Formats)

When scraping, you can request these formats:

| Format | What You Get |
|--------|-------------|
| `markdown` | Clean markdown content (default) |
| `html` | Cleaned HTML |
| `links` | All links on the page with internal/external breakdown |
| `screenshot` | Full-page screenshot (base64 PNG) |
| `structured_data` | JSON-LD, OpenGraph, Twitter Cards, meta tags |
| `headings` | Heading hierarchy (H1-H6) |
| `images` | All images with src, alt text, dimensions |

### AI Extraction (BYOK)

First add your LLM key in Settings (or via API):

```bash
# Add an OpenAI key
curl -X PUT http://localhost:8000/v1/settings/llm-keys \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "is_default": true}'
```

Then use the `extract` parameter:

```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/product",
    "formats": ["markdown"],
    "extract": {
      "prompt": "Extract the product name, price, and description"
    }
  }'
```

---

## Python SDK

### Installation

```bash
cd sdk
pip install -e .
```

### Synchronous Usage

```python
from webharvest import WebHarvest

# Connect with email/password
wh = WebHarvest(api_url="http://localhost:8000")
wh.login("user@example.com", "password")

# Or connect with API key
wh = WebHarvest(api_url="http://localhost:8000", api_key="wh_abc123...")

# Scrape a page
result = wh.scrape("https://example.com", formats=["markdown", "links"])
print(result.data.markdown)
print(result.data.links)

# Crawl a site (blocks until complete)
status = wh.crawl("https://example.com", max_pages=20)
for page in status.data:
    print(f"{page.url}: {page.metadata.word_count} words")

# Map a site
links = wh.map("https://example.com", limit=500)
for link in links.links:
    print(link.url, link.title)

# Batch scrape
status = wh.batch(["https://example.com/a", "https://example.com/b"])
for page in status.data:
    print(page.url, page.markdown[:100])

# Search + scrape
status = wh.search("python web scraping", num_results=5)
for page in status.data:
    print(page.url, page.title)
```

### Async Usage

```python
import asyncio
from webharvest import AsyncWebHarvest

async def main():
    async with AsyncWebHarvest(api_key="wh_abc123...") as wh:
        result = await wh.scrape("https://example.com")
        print(result.data.markdown)

        # Non-blocking crawl with polling
        job = await wh.start_crawl("https://example.com", max_pages=10)
        status = await wh.get_crawl_status(job.job_id)
        print(f"Status: {status.status}, Pages: {status.completed_pages}")

asyncio.run(main())
```

---

## Project Structure

```
WebHarvest/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/            # API endpoints
│   │   │   ├── scrape.py      # POST /v1/scrape + GET detail + export
│   │   │   ├── crawl.py       # POST /v1/crawl + GET status + export
│   │   │   ├── map.py         # POST /v1/map + GET detail + export
│   │   │   ├── batch.py       # POST /v1/batch/scrape + GET status
│   │   │   ├── search.py      # POST /v1/search + GET status
│   │   │   ├── usage.py       # Usage stats, history, top domains
│   │   │   └── schedule.py    # CRUD for scheduled jobs
│   │   ├── models/            # SQLAlchemy models
│   │   │   ├── user.py        # User accounts
│   │   │   ├── job.py         # Job tracking (all types)
│   │   │   └── job_result.py  # Per-page results
│   │   ├── services/          # Business logic
│   │   │   ├── scraper.py     # 5-tier scraping pipeline with strategy cache
│   │   │   ├── browser.py     # Browser pool + CrawlSession (persistent contexts)
│   │   │   ├── crawler.py     # BFS crawler with session management
│   │   │   ├── mapper.py      # Sitemap + link discovery
│   │   │   ├── search.py      # Search engine integration
│   │   │   └── llm_extract.py # LLM extraction via LiteLLM
│   │   ├── workers/           # Celery background tasks
│   │   │   ├── crawl_worker.py # Producer-consumer pipeline
│   │   │   ├── batch_worker.py
│   │   │   └── search_worker.py
│   │   └── config.py          # Settings from environment
│   ├── alembic/               # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/               # Pages (App Router)
│   │   │   ├── page.tsx       # Home + recent activity
│   │   │   ├── scrape/        # Scrape page + detail page
│   │   │   ├── crawl/         # Crawl page + detail page
│   │   │   ├── map/           # Map page + detail page
│   │   │   ├── batch/         # Batch page + detail page
│   │   │   ├── search/        # Search page + detail page
│   │   │   ├── jobs/          # Job history
│   │   │   ├── schedules/     # Schedule management
│   │   │   └── settings/      # LLM keys + proxies
│   │   ├── components/        # Reusable UI components
│   │   └── lib/api.ts         # API client
│   └── Dockerfile
├── sdk/                        # Python SDK
│   ├── webharvest/
│   │   ├── client.py          # WebHarvest + AsyncWebHarvest classes
│   │   ├── models.py          # Pydantic response models
│   │   └── exceptions.py      # Typed exceptions
│   └── pyproject.toml
├── docker-compose.yml          # Development setup
├── docker-compose.prod.yml     # Production setup
└── .env.example                # Environment template
```

---

## Configuration

All configuration is done through environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | JWT signing secret - change this! |
| `ENCRYPTION_KEY` | (required) | Key for encrypting stored API keys |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `BROWSER_POOL_SIZE` | `5` | Max concurrent browser instances |
| `BROWSER_HEADLESS` | `true` | Run browsers headless |
| `RATE_LIMIT_SCRAPE` | `100` | Scrape requests per minute |
| `RATE_LIMIT_CRAWL` | `20` | Crawl requests per minute |
| `RATE_LIMIT_MAP` | `50` | Map requests per minute |

---

## Production Deployment

Use the production compose file:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Key differences from development:
- No hot-reloading / volume mounts
- Optimized Next.js build
- Multiple Celery worker replicas
- Health checks on all services

### Recommended changes for production:

1. **Change `SECRET_KEY`** to a long random string
2. **Change `ENCRYPTION_KEY`** to a 32-byte random string
3. **Change database password** in `.env` and `docker-compose.prod.yml`
4. **Set `BACKEND_CORS_ORIGINS`** to your actual frontend domain
5. **Add a reverse proxy** (nginx/Caddy) with HTTPS in front

---

## Development

### Run without Docker (advanced)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium --with-deps

# Start PostgreSQL and Redis separately, then:
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Celery Worker:**
```bash
cd backend
celery -A app.workers.celery_app worker -l info -c 4
```

### Database Migrations

```bash
cd backend
alembic upgrade head          # Apply all migrations
alembic revision --autogenerate -m "description"  # Create new migration
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend API** | FastAPI, Python 3.12, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | Next.js 14 (App Router), React, Tailwind CSS, shadcn/ui |
| **Database** | PostgreSQL 16 |
| **Cache / Queue** | Redis 7 |
| **Task Queue** | Celery 5 |
| **Browser** | Playwright (Chromium + Firefox), persistent sessions for crawl mode |
| **HTTP Engine** | curl_cffi (TLS fingerprint impersonation), httpx (HTTP/2) |
| **Content Extraction** | Trafilatura, BeautifulSoup, Markdownify |
| **LLM** | LiteLLM (supports OpenAI, Anthropic, Groq, etc.) |
| **Search** | DuckDuckGo (default), Google Custom Search, Brave Search |

---

## License

MIT
