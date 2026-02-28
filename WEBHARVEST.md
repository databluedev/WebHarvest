# DataBlue

**Open-source web scraping platform with industry-leading content extraction, data richness, and zero cost.**

DataBlue is a self-hosted, full-stack web scraping platform with 5 core features: Scrape, Map, Crawl, Batch, and Search. It uses a multi-strategy anti-detection pipeline to bypass bot protection on sites like Amazon, Ticketmaster, and Cloudflare-protected pages — and it's completely free to run.

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend    │────▶│  Backend (API)   │────▶│  Celery Workers │
│  Next.js 14  │     │  FastAPI         │     │  2 replicas x4  │
│  Port 3000   │     │  Port 8000       │     │  5 task queues   │
└─────────────┘     └──────────────────┘     └─────────────────┘
                           │    │                     │
                    ┌──────┘    └──────┐              │
                    ▼                  ▼              ▼
              ┌──────────┐     ┌──────────┐    ┌──────────┐
              │PostgreSQL│     │  Redis    │    │Playwright │
              │  16      │     │  7       │    │Chromium + │
              │  Port 5432│     │  Port 6379│    │Firefox    │
              └──────────┘     └──────────┘    └──────────┘
```

**6 Docker containers**, one command to run:
```bash
cp .env.example .env
docker compose up -d
```

---

## Tech Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| FastAPI | 0.115+ | Async REST API framework |
| SQLAlchemy | 2.0+ | Async ORM (with asyncpg driver) |
| PostgreSQL | 16 | Primary database |
| Redis | 7 | Caching, rate limiting, Celery broker, crawl frontier |
| Celery | 5.4+ | Distributed task queue (8 concurrent workers across 2 replicas) |
| Playwright | 1.49+ | Browser automation (Chromium + Firefox) |
| curl_cffi | 0.7+ | Chrome TLS fingerprint impersonation (JA3/JA4/HTTP2) |
| httpx | 0.28+ | Async HTTP client with HTTP/2 and SOCKS5 proxy support |
| trafilatura | 2.0+ | Main content extraction |
| BeautifulSoup4 | 4.12+ | HTML parsing |
| markdownify | 0.14+ | HTML to Markdown conversion |
| litellm | 1.55+ | Multi-LLM extraction (OpenAI, Anthropic, etc.) |
| Alembic | 1.14+ | Database migrations |
| Prometheus | 0.21+ | Metrics and monitoring |
| Pydantic | 2.10+ | Request/response validation |
| bcrypt + PyJWT | Latest | Authentication (JWT tokens + API keys) |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 14.2 | React framework with App Router |
| React | 18.3 | UI library |
| TypeScript | 5.7 | Type safety |
| Tailwind CSS | 3.4 | Styling |
| Radix UI | Latest | Accessible component primitives (dialogs, tabs, dropdowns, etc.) |
| Recharts | 2.15 | Charts and data visualization |
| Lucide React | 0.468 | Icon library |
| Sonner | 1.7 | Toast notifications |

---

## Core Features

### 1. Scrape — Single URL Extraction

**Endpoint:** `POST /v1/scrape`

Scrape any URL and extract content in multiple formats simultaneously. Returns results synchronously (no polling needed).

**Request:**
```json
{
  "url": "https://www.amazon.com",
  "formats": ["markdown", "html", "links", "structured_data", "headings", "images", "screenshot"],
  "only_main_content": true,
  "wait_for": 0,
  "timeout": 30000,
  "include_tags": ["article", "main"],
  "exclude_tags": ["nav", "footer"],
  "use_proxy": false
}
```

**7 output formats:**
| Format | Description |
|--------|-------------|
| `markdown` | Clean markdown extracted from main content |
| `html` | Cleaned HTML with boilerplate removed |
| `links` | All URLs found on the page + detailed breakdown (internal/external, anchor text) |
| `structured_data` | JSON-LD, OpenGraph, Twitter Cards, meta tags |
| `headings` | Full heading hierarchy (h1-h6 with nesting) |
| `images` | All images with src, alt text, dimensions |
| `screenshot` | Full-page screenshot as base64 PNG |

**Rich metadata on every response:**
- Page title, description, language
- HTTP status code, response headers
- Word count, reading time, content length
- Canonical URL, favicon, og:image
- Robots directives

**Browser automation actions** (execute before scraping):
- `click` — Click any CSS selector
- `wait` — Wait N milliseconds
- `scroll` — Scroll up/down by amount
- `type` — Type text into inputs
- `screenshot` — Capture screenshot at any step

**LLM extraction** (optional):
- Send a prompt + JSON schema
- Get structured data back using any LLM (OpenAI, Anthropic, etc. via litellm)
- Example: "Extract all product prices" → `{"prices": [29.99, 49.99]}`

---

### 2. Map — Website Link Discovery

**Endpoint:** `POST /v1/map`

Discover all URLs on a website with titles and descriptions. Returns results synchronously.

**Request:**
```json
{
  "url": "https://news.ycombinator.com"
}
```

**Response includes:**
- All discovered links (internal + external)
- Page title for each link
- Description/anchor text
- Total link count

**How it works:**
1. Fetches the page with curl_cffi (Chrome TLS impersonation)
2. Falls back to httpx if needed
3. Falls back to browser if < 5 links found
4. Extracts all `<a>` tags with href, title, and surrounding text
5. Deduplicates and returns sorted list

---

### 3. Crawl — Full Website Crawling

**Endpoint:** `POST /v1/crawl` (async — returns job ID, poll for results)

BFS web crawler that discovers and scrapes entire websites. Uses Redis as the crawl frontier for distributed processing.

**Request:**
```json
{
  "url": "https://example.com",
  "max_pages": 100,
  "max_depth": 3,
  "include_paths": ["/blog/*", "/docs/*"],
  "exclude_paths": ["/admin/*"],
  "allow_external_links": false,
  "respect_robots_txt": true,
  "use_proxy": false,
  "scrape_options": {
    "formats": ["markdown", "links", "headings"],
    "only_main_content": true
  }
}
```

**Features:**
- BFS traversal with configurable depth and page limits
- Glob pattern filtering for include/exclude paths
- robots.txt compliance (uses curl_cffi for fetching)
- Automatic link discovery and frontier expansion
- Skips non-page extensions (.pdf, .jpg, .css, .js, etc.)
- Domain restriction (optional external link following)
- Real-time progress tracking via polling
- Cancel running crawls via `DELETE /v1/crawl/{job_id}`

**Export formats:**
- **JSON** — Full data dump
- **CSV** — URL, title, word count, status
- **ZIP** — Per-page folders with content.md, content.html, metadata.json, screenshot.png

---

### 4. Batch — Multi-URL Concurrent Scraping

**Endpoint:** `POST /v1/batch/scrape` (async — returns job ID, poll for results)

Scrape multiple URLs in parallel with shared defaults and per-URL overrides.

**Request (simple):**
```json
{
  "urls": [
    "https://example.com",
    "https://httpbin.org/html",
    "https://news.ycombinator.com"
  ],
  "formats": ["markdown", "links"],
  "concurrency": 5
}
```

**Request (with per-URL overrides):**
```json
{
  "items": [
    {"url": "https://example.com", "formats": ["markdown"]},
    {"url": "https://spa-app.com", "formats": ["html"], "wait_for": 3000}
  ],
  "concurrency": 3
}
```

**Features:**
- Configurable concurrency (default: 5 simultaneous)
- Per-URL format and timeout overrides
- Up to 100 URLs per batch
- Same rich data as single scrape (all 7 formats)
- Export to JSON, CSV, or ZIP

---

### 5. Search — Web Search + Auto-Scrape

**Endpoint:** `POST /v1/search` (async — returns job ID, poll for results)

Search the web using DuckDuckGo (free, no API key) or Google Custom Search (BYOK), then automatically scrape the top results.

**Request:**
```json
{
  "query": "python web scraping tutorial",
  "num_results": 5,
  "engine": "duckduckgo",
  "formats": ["markdown", "links"]
}
```

**Google Custom Search (optional):**
```json
{
  "query": "machine learning papers",
  "num_results": 10,
  "engine": "google",
  "google_api_key": "your-api-key",
  "google_cx": "your-search-engine-id",
  "formats": ["markdown"]
}
```

**Features:**
- DuckDuckGo search (free, no API key needed)
- Google Custom Search (bring your own key)
- Each result is auto-scraped with full content extraction
- Search snippet + title preserved alongside scraped content
- Export to JSON, CSV, or ZIP

---

## Anti-Detection Pipeline

DataBlue uses a **multi-strategy pipeline** that automatically escalates through increasingly sophisticated methods. Most sites are scraped in 1-3 seconds. Hard sites (Amazon, Ticketmaster, etc.) may take 10-20 seconds.

```
Request
  │
  ▼
┌─────────────────────────────────────────────┐
│ Strategy 1: curl_cffi                       │ ~1-2s
│ Chrome 124 TLS fingerprint impersonation    │
│ Matches real Chrome's JA3/JA4/HTTP2 config  │
│ Works for 80%+ of sites including Amazon    │
└─────────────┬───────────────────────────────┘
              │ blocked?
              ▼
┌─────────────────────────────────────────────┐
│ Strategy 2: httpx HTTP/2                    │ ~1-2s
│ Rotating headers, Sec-Ch-Ua, Sec-Fetch-*   │
│ Skipped for known hard sites                │
└─────────────┬───────────────────────────────┘
              │ blocked?
              ▼
┌─────────────────────────────────────────────┐
│ Strategy 3: Chromium Stealth Browser        │ ~6-8s
│ domcontentloaded + 5s networkidle           │
│ 20-level stealth: canvas noise, WebGL       │
│ randomization, CDP detection bypass,        │
│ AudioContext spoofing, WebRTC prevention,    │
│ Battery API, Performance.now() noise        │
└─────────────┬───────────────────────────────┘
              │ blocked?
              ▼
┌─────────────────────────────────────────────┐
│ Strategy 4: Firefox Browser                 │ ~6-8s
│ Completely different engine & TLS stack     │
│ Bypasses Chrome-targeted bot detection      │
│ Skipped if we already have >5KB content     │
└─────────────┬───────────────────────────────┘
              │ blocked?
              ▼
┌─────────────────────────────────────────────┐
│ Strategy 5: Aggressive Browser              │ ~10-15s
│ Human simulation: mouse moves, scrolling    │
│ Challenge page wait loop (3s check)         │
│ Only used if <2KB content from all above    │
└─────────────────────────────────────────────┘
```

**Smart short-circuiting:**
- If any strategy returns >5KB of HTML, skip remaining browser strategies
- If any strategy returns >2KB, skip aggressive mode entirely
- Sites in the "hard sites" list skip httpx (always blocked anyway)

**Chromium stealth patches (20 levels):**
1. Canvas fingerprint noise injection (unique per session)
2. AudioContext frequency spoofing
3. WebRTC IP leak prevention
4. Chrome DevTools Protocol (CDP) detection bypass
5. Battery API spoofing
6. Performance.now() timing noise
7. WebGL vendor/renderer randomization (9 GPU profiles)
8. Screen/display consistency
9. Navigator property scrubbing (webdriver, plugins, languages)
10. Speech synthesis voice list
11. Media codec support
12. Keyboard event consistency
13. Document visibility API
14. Permission query spoofing
15. Chrome runtime simulation
16. Notification permission
17. Connection type spoofing
18. Hardware concurrency randomization
19. Device memory randomization
20. Plugin/MimeType array population

---

## Authentication

**Two authentication methods:**

### JWT Tokens
```bash
# Register
POST /v1/auth/register
{"email": "user@example.com", "password": "securepass"}

# Login
POST /v1/auth/login
{"email": "user@example.com", "password": "securepass"}
# Returns: {"access_token": "eyJ...", "token_type": "bearer"}

# Use token
GET /v1/auth/me
Authorization: Bearer eyJ...
```

Tokens expire after 7 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

### API Keys
```bash
# Create API key
POST /v1/auth/api-keys
{"name": "My Integration"}
# Returns: {"key": "wh_abc123..."}  (shown once, stored hashed)

# Use API key
POST /v1/scrape
Authorization: Bearer wh_abc123...
```

API keys use the `wh_` prefix and are encrypted at rest with AES-256.

---

## Proxy Support

Configure rotating HTTP/HTTPS/SOCKS5 proxies via the Settings page or API.

```bash
# Add a proxy
POST /v1/settings/proxies
{"proxy_url": "socks5://user:pass@proxy.example.com:1080", "label": "US Proxy 1"}

# List proxies
GET /v1/settings/proxies

# Delete a proxy
DELETE /v1/settings/proxies/{proxy_id}
```

When `use_proxy: true` is set on any request, DataBlue randomly selects from your proxy pool and routes both HTTP (curl_cffi/httpx) and browser (Playwright) traffic through it.

---

## Caching

Redis-based response cache with SHA256 key generation:

- **Key format:** `cache:scrape:<sha256(url + sorted_formats)>`
- **Default TTL:** 1 hour (configurable via `CACHE_TTL_SECONDS`)
- **Bypass conditions:** Actions requested, screenshot format, LLM extraction
- **Toggle:** `CACHE_ENABLED=true/false` in `.env`

Identical scrape requests within the TTL window return instantly from cache.

---

## Rate Limiting

Per-user, per-minute limits enforced via Redis:

| Endpoint | Default Limit |
|----------|--------------|
| Scrape | 100/min |
| Crawl | 20/min |
| Map | 50/min |
| Batch | 20/min |
| Search | 30/min |

Configurable via environment variables (`RATE_LIMIT_SCRAPE`, etc.).

---

## Monitoring

### Health Checks
- `GET /health` — Liveness probe (always 200)
- `GET /health/ready` — Readiness probe (checks DB + Redis + browser pool, returns 503 if any down)

### Prometheus Metrics (`GET /metrics`)

**Counters:**
- `scrape_requests_total{status="success|error"}` — Total scrape requests
- `crawl_jobs_total{status="started"}` — Crawl jobs launched
- `batch_jobs_total{status="started"}` — Batch jobs launched
- `search_jobs_total{status="started"}` — Search jobs launched

**Histograms:**
- `scrape_duration_seconds` — Scrape timing (buckets: 0.5s to 60s)
- `crawl_page_duration_seconds` — Per-page crawl timing

**Gauges:**
- `active_browser_contexts` — Current browser instances
- `db_pool_size` — Database connection pool usage

---

## Data Export

All async features (Crawl, Batch, Search) support export in 3 formats:

| Format | Endpoint | Contents |
|--------|----------|----------|
| **JSON** | `GET /v1/{feature}/{job_id}/export?format=json` | Full data dump |
| **CSV** | `GET /v1/{feature}/{job_id}/export?format=csv` | URL, title, word count, status, error |
| **ZIP** | `GET /v1/{feature}/{job_id}/export?format=zip` | Per-page folders: content.md, content.html, metadata.json, screenshot.png + index.json + full_data.json |

---

## Task Queue Architecture

Celery workers process async jobs (crawl, batch, search) across 5 dedicated queues:

| Queue | Task | Worker Config |
|-------|------|--------------|
| `scrape` | Single URL scrape (via batch/search) | 4 concurrent per replica |
| `crawl` | BFS website crawling | 4 concurrent per replica |
| `map` | URL discovery | 4 concurrent per replica |
| `batch` | Multi-URL batch scraping | 4 concurrent per replica |
| `search` | Search + auto-scrape | 4 concurrent per replica |

**Worker settings:**
- 2 replicas (8 total concurrent workers)
- Late acknowledgment (`acks_late=True`) — tasks survive worker crashes
- Priority support (0-9 levels)
- Prefetch multiplier: 1 (fair scheduling)
- JSON serialization

---

## Database Schema

**Tables:**
- `users` — Email, hashed password, created_at
- `api_keys` — Hashed key, user_id, name, encrypted prefix
- `jobs` — id, user_id, type (scrape/crawl/batch/search), status, config JSON, progress counters, timestamps
- `job_results` — id, job_id, url, markdown, html, links (JSON), screenshot_url (base64), metadata_ (JSON), created_at
- `proxy_configs` — id, user_id, proxy_url (encrypted), proxy_type, label, is_active
- `llm_keys` — id, user_id, provider, encrypted_key, label

Managed with Alembic migrations. All sensitive fields (proxy URLs, LLM keys) encrypted with AES-256.

---

## Quick Start

```bash
git clone https://github.com/your-username/web-crawler.git
cd web-crawler
cp .env.example .env
docker compose up -d
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Metrics:** http://localhost:8000/metrics

Register an account at http://localhost:3000/auth/register and start scraping.

---

## API Quick Reference

```bash
# Register & login
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"password123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"password123"}' | jq -r .access_token)

# Scrape a URL
curl -X POST http://localhost:8000/v1/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown","links"]}'

# Map a website
curl -X POST http://localhost:8000/v1/map \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'

# Crawl a website
curl -X POST http://localhost:8000/v1/crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","max_pages":50,"max_depth":2}'

# Batch scrape
curl -X POST http://localhost:8000/v1/batch/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com","https://httpbin.org/html"],"formats":["markdown"]}'

# Search + scrape
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"python tutorials","num_results":5}'
```

---

## Configuration Reference

All settings via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | JWT signing key |
| `ENCRYPTION_KEY` | — | AES-256 key for sensitive data |
| `DATABASE_URL` | postgresql+asyncpg://... | PostgreSQL connection |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection |
| `CELERY_BROKER_URL` | redis://redis:6379/1 | Celery broker |
| `BROWSER_POOL_SIZE` | 5 | Max concurrent browser instances |
| `BROWSER_HEADLESS` | true | Run browsers headless |
| `RATE_LIMIT_SCRAPE` | 100 | Scrape requests/minute |
| `RATE_LIMIT_CRAWL` | 20 | Crawl jobs/minute |
| `RATE_LIMIT_MAP` | 50 | Map requests/minute |
| `RATE_LIMIT_BATCH` | 20 | Batch jobs/minute |
| `RATE_LIMIT_SEARCH` | 30 | Search requests/minute |
| `MAX_CRAWL_PAGES` | 1000 | Max pages per crawl |
| `MAX_CRAWL_DEPTH` | 10 | Max crawl depth |
| `MAX_BATCH_SIZE` | 100 | Max URLs per batch |
| `MAX_SEARCH_RESULTS` | 10 | Max search results |
| `CACHE_ENABLED` | true | Enable response caching |
| `CACHE_TTL_SECONDS` | 3600 | Cache expiration (seconds) |
| `DB_POOL_SIZE` | 20 | Database connection pool |
| `DB_MAX_OVERFLOW` | 10 | Pool overflow connections |
| `REDIS_MAX_CONNECTIONS` | 50 | Redis connection pool |
