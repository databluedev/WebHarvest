# DataBlue

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Next.js](https://img.shields.io/badge/frontend-Next.js%2014-black)

> **Still in active development** — features may change, APIs may break, and some functionality is incomplete.

**Open-source, self-hosted web scraping platform** with a 5-tier scraping pipeline, cross-user caching, format-aware extraction, built-in monitoring, scheduling, and LLM extraction.

Built with FastAPI + Next.js + PostgreSQL + Redis + Celery + Playwright.

---

## Why DataBlue?

| Feature | Included |
|---------|:--------:|
| 5-tier scraping pipeline with strategy cache | Yes |
| Cross-user URL cache (Redis) — instant results for repeated URLs | Yes |
| Format-aware extraction — only extract what you request | Yes |
| Circuit breaker per domain | Yes |
| Dead Letter Queue for failed tasks | Yes |
| Built-in URL change monitoring | Yes |
| Cron-based scheduled jobs | Yes |
| Producer-consumer crawl pipeline | Yes |
| Anti-bot bypass (20-level stealth) | Yes |
| Multi-format document extraction (PDF/DOCX/XLSX/PPTX/CSV/RTF/EPUB) | Yes |
| BYOK LLM extraction (100+ models via LiteLLM) | Yes |
| Full browser rendering (Chromium + Firefox) | Yes |
| Stealth Engine sidecar (isolated browser with advanced fingerprinting) | Yes |
| Proxy rotation with bulk import + Scrape.do integration | Yes |
| Self-hosted / no cloud dependency | Yes |
| Python SDK (sync + async) | Yes |
| Prometheus metrics | Yes |
| Structured JSON logging + Request ID tracing | Yes |

---

## Architecture

```
                        +------------------+
                        |   Dashboard      |
                        |  (Next.js 14)    |
                        +--------+---------+
                                 |
                        +--------v---------+
    Client / SDK  ----->|   FastAPI API     |------> Prometheus /metrics
                        |  (Auth, Rate      |
                        |   Limit, CORS)    |
                        +--------+---------+
                                 |
                    +------------+-------------+
                    |                          |
             +------v------+          +-------v-------+
             |  PostgreSQL  |          |    Redis       |
             |  (Jobs, Users)|         |  (Queue, Cache,|
             |              |          |   Rate Limits) |
             +--------------+          +-------+-------+
                                               |
                                    +----------v----------+
                                    |   Celery Workers     |
                                    |  (scrape, crawl,     |
                                    |   map, search,       |
                                    |   extract, monitor)  |
                                    +----------+----------+
                                               |
                              +----------------+----------------+
                              |                                 |
                   +----------v----------+          +-----------v-----------+
                   |   Browser Pool       |          |   Stealth Engine      |
                   |  (Chromium + Firefox) |          |  (Isolated sidecar)   |
                   +----------+----------+          +-----------+-----------+
                              |                                 |
                              +-----------+---------------------+
                                          |
                                   Target Sites
```

---

## What It Does

DataBlue lets you extract content from any website through 4 core actions:

| Action | Description |
|--------|-------------|
| **Scrape** | Extract content from a single URL — markdown, HTML, screenshots, links, structured data, headings, images |
| **Crawl** | Recursively crawl an entire website following links (BFS), scraping each page |
| **Map** | Fast URL discovery via sitemaps and homepage link extraction (no content scraping) |
| **Search** | Search the web (DuckDuckGo/Google/Brave) and scrape each result page |

Every action creates a **Job** record in the database. Results are persisted and can be viewed, exported (JSON/CSV/ZIP), and accessed later from the dashboard or API.

### Cross-User Caching

Results are cached in Redis keyed by URL + parameters. When any user requests the same URL with the same settings, the cached result is returned instantly — no job, no worker, no waiting.

| Mode | Cache Key | Where Checked |
|------|-----------|---------------|
| Scrape | URL + formats | API endpoint (instant return, no job created) |
| Map | URL + limit + subdomains + sitemap + search | API endpoint (instant) + worker |
| Search | Query + num_results + engine + formats | Worker (instant job completion) |
| Crawl | URL + max_pages + max_depth | Worker (instant job completion) |

Cache TTL defaults to 1 hour (`CACHE_TTL_SECONDS`). Results larger than 10MB are not cached.

### Format-Aware Extraction

Selecting only the formats you need directly improves performance and reduces server load. The pipeline **skips expensive operations** entirely when they're not requested:

| Format | What Gets Skipped When Not Selected |
|--------|-------------------------------------|
| `screenshot` | No browser launch, no page rendering, no screenshot capture |
| `links` | No link parsing or detailed link extraction |
| `html` | No HTML copy in result |
| `structured_data` | No JSON-LD / OpenGraph / meta tag parsing |
| `headings` | No heading hierarchy extraction |
| `images` | No image tag extraction |

When only `markdown` is selected, the scraper uses fast HTTP-only tiers (curl_cffi, httpx) instead of launching a browser — this is significantly faster and uses far less CPU/memory.

---

## Features

- **Full Browser Rendering** — Playwright (Chromium + Firefox) handles JavaScript-heavy sites
- **Anti-Bot Bypass** — 20-level stealth injection, TLS fingerprint impersonation (curl_cffi), request interception, Google referrer chains, and cookie-enhanced HTTP
- **5-Tier Scraping Pipeline** — Strategy cache → Cookie HTTP → HTTP race → Browser race → Heavy strategies → Fallback archives, with per-domain strategy learning
- **Stealth Engine** — Optional sidecar microservice with isolated browser instances and advanced fingerprinting for hard-to-scrape sites
- **Fast Crawling** — Persistent browser sessions, cookie reuse across pages, and producer-consumer pipeline overlap fetch and extraction for ~5x crawl speed
- **Smart Content Extraction** — Trafilatura strips boilerplate before processing
- **Advanced Document Extraction** — Multi-format support for PDF (tables, images, OCR), DOCX (formatting, hyperlinks, footnotes), XLSX, PPTX, CSV, RTF, and EPUB with multi-strategy fallbacks
- **AI Extraction (BYOK)** — Bring your own OpenAI/Anthropic/Groq/OpenRouter/Fireworks/Cohere/Ollama key for LLM-powered structured extraction via LiteLLM (100+ models)
- **URL Change Monitoring** — Track changes to any URL with configurable intervals, CSS selector targeting, keyword detection, content hash comparison, and similarity thresholds
- **Scheduled Jobs** — Cron-based recurring scrapes with Celery Beat and timezone support
- **Webhooks** — HMAC-SHA256 signed notifications when jobs complete or monitors detect changes, with delivery history and debugging
- **Proxy Support** — Add your own proxies for rotation with bulk import, plus Scrape.do integration for hard sites
- **Cross-User Caching** — Redis-based URL cache shared across all users for instant repeated lookups
- **Usage Quotas** — Per-user quota tracking and enforcement with usage analytics
- **Export** — Download results as JSON, CSV, or ZIP
- **Job History** — Full dashboard with filtering, search, and pagination
- **Python SDK** — Sync and async clients with polling helpers
- **REST API** — Complete API with JWT auth and API key support

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
| **Playground** | `/playground` | Multi-mode workspace — scrape, crawl, map, search in one page |
| **Scrape** | `/scrape` | Single-page scraper with format toggles |
| **Crawl** | `/crawl` | Full-site crawler with depth/concurrency controls |
| **Map** | `/map` | URL discovery tool |
| **Search** | `/search` | Search + scrape engine |
| **Extract** | `/extract` | Standalone LLM extraction UI |
| **Jobs** | `/jobs` | Full job history with filters |
| **Schedules** | `/schedules` | Cron-based recurring jobs |
| **Monitors** | `/monitors` | URL change monitoring dashboard |
| **Webhooks** | `/webhooks` | Webhook delivery history + debugging |
| **API Keys** | `/api-keys` | Generate keys for programmatic access |
| **Settings** | `/settings` | LLM keys (BYOK) and proxy management |
| **Dashboard** | `/dashboard` | Usage stats, charts, and analytics |

---

## Document Extraction

DataBlue automatically detects and extracts content from document URLs with format-specific strategies:

| Format | Extraction Capabilities |
|--------|------------------------|
| **PDF** | Text, tables (PyMuPDF + pdfplumber fallback), embedded images, hyperlinks, heading detection via font-size analysis, OCR fallback for scanned PDFs |
| **DOCX** | Paragraphs, headings, bold/italic formatting, hyperlinks, tables, embedded images, footnotes/endnotes |
| **XLSX** | All sheets as markdown tables, merged cells, formula detection, metadata |
| **PPTX** | Slide text, titles, tables, speaker notes, embedded images |
| **CSV/TSV** | Auto-detect delimiter and encoding, markdown table output, large file truncation |
| **RTF** | Text extraction with paragraph-based markdown |
| **EPUB** | Spine-order chapter extraction, HTML-to-markdown conversion, cover image, OPF metadata |

PDF extraction uses a 3-strategy fallback chain:
1. **PyMuPDF** (primary) — structured text, tables via `find_tables()`, images, links
2. **pdfplumber** (fallback) — for complex table layouts when PyMuPDF finds no tables
3. **OCR** (scanned PDF) — PyMuPDF built-in Tesseract OCR for image-only PDFs

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
    "max_depth": 3,
    "scrape_options": {
      "formats": ["markdown"]
    }
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

### Search + Scrape

```bash
# Search the web and scrape results
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "best python web frameworks 2025",
    "num_results": 5,
    "engine": "duckduckgo",
    "formats": ["markdown"]
  }'

# Check search status
curl http://localhost:8000/v1/search/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### AI Extraction

First add your LLM key in Settings (or via API):

```bash
# Add an OpenAI key
curl -X PUT http://localhost:8000/v1/settings/llm-keys \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "is_default": true}'
```

Then use the `extract` parameter on scrape, or the standalone extract endpoint:

```bash
# Extract structured data from a URL
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

# Standalone extraction from content or URL
curl -X POST http://localhost:8000/v1/extract \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/page1"],
    "prompt": "Extract all email addresses and phone numbers"
  }'
```

### Monitors

```bash
# Create a URL change monitor
curl -X POST http://localhost:8000/v1/monitors \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/pricing",
    "check_interval_minutes": 60,
    "css_selector": ".pricing-table",
    "webhook_url": "https://your-server.com/webhook"
  }'

# List all monitors
curl http://localhost:8000/v1/monitors \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Webhooks

```bash
# View webhook delivery history
curl http://localhost:8000/v1/webhooks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Scrape Options (All Formats)

When scraping, you can request these formats:

| Format | What You Get |
|--------|-------------|
| `markdown` | Clean markdown content (default) |
| `html` | Cleaned HTML |
| `links` | All links on the page with internal/external breakdown |
| `screenshot` | Full-page screenshot (base64 JPEG) |
| `structured_data` | JSON-LD, OpenGraph, Twitter Cards, meta tags |
| `headings` | Heading hierarchy (H1-H6) |
| `images` | All images with src, alt text, dimensions |

Only request the formats you need — the pipeline skips extraction for formats not in the list, saving CPU and time.

---

## Python SDK

### Installation

```bash
cd sdk
pip install -e .
```

### Synchronous Usage

```python
from webharvest import DataBlue

# Connect with email/password
wh = DataBlue(api_url="http://localhost:8000")
wh.login("user@example.com", "password")

# Or connect with API key
wh = DataBlue(api_url="http://localhost:8000", api_key="wh_abc123...")

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

# Search + scrape
status = wh.search("python web scraping", num_results=5)
for page in status.data:
    print(page.url, page.title)
```

### Async Usage

```python
import asyncio
from webharvest import AsyncDataBlue

async def main():
    async with AsyncDataBlue(api_key="wh_abc123...") as wh:
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
│   │   │   ├── search.py      # POST /v1/search + GET status
│   │   │   ├── extract.py     # Standalone LLM extraction
│   │   │   ├── monitor.py     # URL change monitoring
│   │   │   ├── webhook.py     # Webhook delivery logs
│   │   │   ├── usage.py       # Usage stats, history, top domains
│   │   │   └── schedule.py    # CRUD for scheduled jobs
│   │   ├── models/            # SQLAlchemy models
│   │   │   ├── user.py        # User accounts + API keys
│   │   │   ├── job.py         # Job tracking (all types)
│   │   │   ├── job_result.py  # Per-page results
│   │   │   ├── monitor.py     # Monitor + MonitorCheck
│   │   │   └── webhook.py     # WebhookDelivery
│   │   ├── services/          # Business logic
│   │   │   ├── scraper.py     # 5-tier scraping pipeline with strategy cache
│   │   │   ├── browser.py     # Browser pool + CrawlSession (persistent contexts)
│   │   │   ├── crawler.py     # BFS crawler with session management
│   │   │   ├── document.py    # Multi-format document extraction
│   │   │   ├── mapper.py      # Sitemap + link discovery
│   │   │   ├── search.py      # Search engine integration
│   │   │   ├── llm_extract.py # LLM extraction via LiteLLM
│   │   │   ├── webhook.py     # Webhook delivery with HMAC-SHA256
│   │   │   └── quota.py       # Usage quota tracking
│   │   ├── core/              # Framework utilities
│   │   │   ├── cache.py       # Cross-user URL cache (scrape, map, search, crawl)
│   │   │   ├── redis.py       # ResilientRedis client
│   │   │   ├── rate_limiter.py
│   │   │   └── metrics.py     # Prometheus metrics
│   │   ├── workers/           # Celery background tasks
│   │   │   ├── crawl_worker.py    # Producer-consumer pipeline
│   │   │   ├── scrape_worker.py
│   │   │   ├── map_worker.py
│   │   │   ├── search_worker.py
│   │   │   ├── extract_worker.py
│   │   │   ├── monitor_worker.py
│   │   │   └── schedule_worker.py
│   │   └── config.py          # Settings from environment
│   ├── alembic/               # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/               # Pages (App Router)
│   │   │   ├── page.tsx       # Home + recent activity
│   │   │   ├── playground/    # Multi-mode workspace
│   │   │   ├── scrape/        # Scrape page + detail page
│   │   │   ├── crawl/         # Crawl page + detail page
│   │   │   ├── map/           # Map page + detail page
│   │   │   ├── search/        # Search page + detail page
│   │   │   ├── extract/       # LLM extraction UI
│   │   │   ├── jobs/          # Job history
│   │   │   ├── schedules/     # Schedule management
│   │   │   ├── monitors/      # URL change monitoring
│   │   │   ├── webhooks/      # Webhook delivery history
│   │   │   └── settings/      # LLM keys + proxies
│   │   ├── components/        # Reusable UI components
│   │   └── lib/api.ts         # API client
│   └── Dockerfile
├── stealth-engine/             # Stealth browser sidecar
│   ├── main.py                # FastAPI service with isolated browser
│   ├── browser_pool.py        # Chromium + Firefox pool
│   ├── config.py
│   └── Dockerfile
├── sdk/                        # Python SDK
│   ├── webharvest/
│   │   ├── client.py          # DataBlue + AsyncDataBlue classes
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
| `SECRET_KEY` | (required) | JWT signing secret — change this! |
| `ENCRYPTION_KEY` | (required) | Key for encrypting stored API keys (32 chars) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `BROWSER_POOL_SIZE` | `8` | Max concurrent browser instances |
| `CHROMIUM_POOL_SIZE` | `6` | Chromium instances in the pool |
| `FIREFOX_POOL_SIZE` | `2` | Firefox instances in the pool |
| `BROWSER_HEADLESS` | `true` | Run browsers headless |
| `RATE_LIMIT_SCRAPE` | `100` | Scrape requests per minute |
| `RATE_LIMIT_CRAWL` | `20` | Crawl requests per minute |
| `RATE_LIMIT_MAP` | `50` | Map requests per minute |
| `RATE_LIMIT_SEARCH` | `30` | Search requests per minute |
| `MAX_CRAWL_PAGES` | `1000` | Max pages per crawl |
| `MAX_CRAWL_DEPTH` | `10` | Max link depth per crawl |
| `DEFAULT_TIMEOUT` | `30000` | Default scrape timeout (ms) |
| `CACHE_ENABLED` | `true` | Enable cross-user URL cache |
| `CACHE_TTL_SECONDS` | `3600` | Cache TTL (1 hour default) |
| `STEALTH_ENGINE_URL` | (empty) | Stealth engine sidecar URL (optional) |
| `GO_HTML_TO_MD_URL` | (empty) | Go HTML-to-Markdown sidecar URL (optional) |
| `SCRAPE_DO_API_KEY` | (empty) | Scrape.do proxy API key for hard sites (optional) |

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
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, shadcn/ui, Radix UI |
| **Database** | PostgreSQL 16 + asyncpg |
| **Cache / Queue** | Redis 7 |
| **Task Queue** | Celery 5 + Celery Beat |
| **Browser** | Playwright (Chromium + Firefox), persistent sessions for crawl mode |
| **Stealth Engine** | Isolated browser sidecar with advanced fingerprinting |
| **HTTP Engine** | curl_cffi (TLS fingerprint impersonation), httpx (HTTP/2) |
| **Content Extraction** | Trafilatura, BeautifulSoup, Markdownify |
| **Document Parsing** | PyMuPDF, pdfplumber, python-docx, openpyxl, python-pptx, striprtf |
| **LLM** | LiteLLM (supports OpenAI, Anthropic, Groq, OpenRouter, Fireworks, Cohere, Ollama, etc.) |
| **Search** | DuckDuckGo (default), Google Custom Search, Brave Search |
| **Auth** | JWT (PyJWT), bcrypt, AES-256 encryption for stored keys |
| **Metrics** | Prometheus client |

---

## Status

This project is **under active development**. Current known limitations:

- Some edge cases in anti-bot bypass for heavily protected sites
- OCR for scanned PDFs requires Tesseract to be installed in the container
- Monitor scheduling depends on Celery Beat running continuously
- No built-in HTTPS — use a reverse proxy for production

---

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the test suite: `cd backend && python -m pytest tests/ -v`
5. Submit a pull request

Please open an issue first for large changes to discuss the approach.

---

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.
