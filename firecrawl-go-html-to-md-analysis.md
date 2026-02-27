# Firecrawl go-html-to-md-service -- Complete Source Analysis

**Repository:** [github.com/mendableai/firecrawl](https://github.com/mendableai/firecrawl)
**Path:** `apps/go-html-to-md-service/`
**Container image:** `ghcr.io/firecrawl/go-html-to-md-service:latest`
**Go version:** 1.23.0

---

## 1. Repository Structure

```
apps/go-html-to-md-service/
├── .dockerignore
├── .gitignore
├── Dockerfile            # Multi-stage alpine build
├── Makefile              # build/test/run/docker targets
├── converter.go          # Core HTML->Markdown conversion logic
├── docker-compose.yml    # Single-service compose file
├── go.mod                # Dependencies + fork replace directive
├── go.sum
├── handler.go            # HTTP API handler (3 endpoints)
├── handler_test.go       # Unit tests for all endpoints
├── main.go               # Server entrypoint
└── requests.http         # 21 REST Client test requests
```

Flat structure -- no subdirectories. The entire service is a single Go package (`package main`).

---

## 2. main.go -- Server Entrypoint

```go
package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

const (
	defaultPort            = "8080"
	defaultShutdownTimeout = 30 * time.Second
	defaultReadTimeout     = 1 * time.Minute
	defaultWriteTimeout    = 1 * time.Minute
	maxUploadSize          = 150 * 1024 * 1024  // 150 MB
)

func main() {
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix

	env := os.Getenv("ENV")
	if env == "production" {
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	} else {
		log.Logger = log.Output(zerolog.ConsoleWriter{
			Out:        os.Stdout,
			TimeFormat: time.RFC3339,
		})
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = defaultPort
	}

	converter := NewConverter()
	handler := NewHandler(converter)

	router := mux.NewRouter()
	router.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)
			next.ServeHTTP(w, r)
		})
	})
	handler.RegisterRoutes(router)

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  defaultReadTimeout,
		WriteTimeout: defaultWriteTimeout,
	}

	go func() {
		log.Info().Str("port", port).Str("env", env).
			Msg("Starting HTML to Markdown service")
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("Failed to start server")
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info().Msg("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), defaultShutdownTimeout)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal().Err(err).Msg("Server forced to shutdown")
	}
	log.Info().Msg("Server exited")
}
```

### Key design decisions:
- **150 MB max upload** enforced at middleware level via `http.MaxBytesReader`
- **Graceful shutdown** with 30-second drain window on SIGINT/SIGTERM
- **Gorilla Mux** router (not stdlib `http.ServeMux`)
- **zerolog** structured logging; pretty console in dev, JSON in production
- **Environment variables:** `PORT` (default 8080) and `ENV` (production vs dev)

---

## 3. handler.go -- HTTP API Layer

```go
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/rs/zerolog/log"
)

const maxRequestSize = 150 * 1024 * 1024 // 150MB

type Handler struct {
	converter *Converter
}

func NewHandler(converter *Converter) *Handler {
	return &Handler{converter: converter}
}

func (h *Handler) RegisterRoutes(router *mux.Router) {
	router.HandleFunc("/health", h.HealthCheck).Methods("GET")
	router.HandleFunc("/convert", h.ConvertHTML).Methods("POST")
	router.HandleFunc("/", h.Index).Methods("GET")
}
```

### Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check -- returns `{"status":"healthy","timestamp":"...","service":"html-to-markdown"}` |
| `GET` | `/` | Index -- returns service name, version, description, endpoint list |
| `POST` | `/convert` | Core conversion -- accepts `{"html":"<...>"}`, returns `{"markdown":"...","success":true}` |

### Request/Response types:

```go
type ConvertRequest struct {
	HTML string `json:"html"`
}

type ConvertResponse struct {
	Markdown string `json:"markdown"`
	Success  bool   `json:"success"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Details string `json:"details,omitempty"`
	Success bool   `json:"success"`
}

type HealthCheckResponse struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
	Service   string    `json:"service"`
}

type IndexResponse struct {
	Service     string   `json:"service"`
	Version     string   `json:"version"`
	Description string   `json:"description"`
	Endpoints   []string `json:"endpoints"`
}
```

### ConvertHTML handler flow:
1. Apply `MaxBytesReader` (150 MB limit -- applied AGAIN, double protection)
2. `io.ReadAll` the body
3. `json.Unmarshal` into `ConvertRequest`
4. Validate `html` field is non-empty
5. Call `converter.ConvertHTMLToMarkdown(req.HTML)`
6. Log metrics: duration, input size, output size
7. Return `ConvertResponse` with the markdown
8. On any error: return `ErrorResponse` with appropriate HTTP status (400/500)

### Observability:
- Reads `X-Request-ID` header for request correlation in logs
- Logs conversion duration, input/output byte sizes

---

## 4. converter.go -- Core Conversion Logic (THE IMPORTANT FILE)

```go
package main

import (
	"strings"
	"unicode/utf8"

	"github.com/PuerkitoBio/goquery"
	md "github.com/firecrawl/html-to-markdown"
	"github.com/firecrawl/html-to-markdown/plugin"
	"golang.org/x/net/html"
)

type Converter struct {
	converter *md.Converter
}

func NewConverter() *Converter {
	converter := md.NewConverter("", true, nil)
	converter.Use(plugin.GitHubFlavored())
	addGenericPreRule(converter)

	return &Converter{converter: converter}
}

func (c *Converter) ConvertHTMLToMarkdown(html string) (string, error) {
	return c.converter.ConvertString(html)
}
```

### Conversion pipeline:

1. **Base converter:** `md.NewConverter("", true, nil)` -- the forked `html-to-markdown` library
   - First arg `""` = domain (empty = no domain-relative URL resolution)
   - Second arg `true` = commonmark mode
   - Third arg `nil` = default options
2. **GitHub Flavored Markdown plugin:** Adds strikethrough, tables, task lists
3. **Custom `<pre>` block rule:** Overrides the default `<pre>` handling
4. **Custom `<code>` inline rule:** Overrides the default inline code handling

### Custom PRE rule (fenced code blocks):

```go
func addGenericPreRule(conv *md.Converter) {
	// Gutter detection -- skips line-number elements
	isGutter := func(class string) bool {
		c := strings.ToLower(class)
		return strings.Contains(c, "gutter") || strings.Contains(c, "line-numbers")
	}

	// Language detection from class attributes
	detectLang := func(sel *goquery.Selection) string {
		classes := sel.AttrOr("class", "")
		lower := strings.ToLower(classes)
		for _, part := range strings.Fields(lower) {
			if strings.HasPrefix(part, "language-") {
				return strings.TrimPrefix(part, "language-")
			}
			if strings.HasPrefix(part, "lang-") {
				return strings.TrimPrefix(part, "lang-")
			}
		}
		return ""
	}

	// Recursive text collector -- walks the HTML node tree
	var collect func(n *html.Node, b *strings.Builder)
	collect = func(n *html.Node, b *strings.Builder) {
		if n == nil { return }
		switch n.Type {
		case html.TextNode:
			b.WriteString(n.Data)
		case html.ElementNode:
			name := strings.ToLower(n.Data)
			// Skip gutter elements (line numbers in code highlighting)
			if name != "" {
				for _, a := range n.Attr {
					if a.Key == "class" && isGutter(a.Val) {
						return
					}
				}
			}
			if name == "br" {
				b.WriteString("\n")
			}
			for c := n.FirstChild; c != nil; c = c.NextSibling {
				collect(c, b)
			}
			// Newline after block-level wrappers
			switch name {
			case "p", "div", "li", "tr", "table", "thead", "tbody",
			     "tfoot", "section", "article", "blockquote", "pre",
			     "h1", "h2", "h3", "h4", "h5", "h6":
				b.WriteString("\n")
			}
		}
	}

	// PRE -> fenced code block rule
	conv.AddRules(md.Rule{
		Filter: []string{"pre"},
		Replacement: func(_ string, selec *goquery.Selection, opt *md.Options) *string {
			codeSel := selec.Find("code").First()
			lang := detectLang(codeSel)
			if lang == "" {
				lang = detectLang(selec)
			}

			var b strings.Builder
			for _, n := range selec.Nodes {
				collect(n, &b)
			}
			content := strings.TrimRight(b.String(), "\n")

			fenceChar, _ := utf8.DecodeRuneInString(opt.Fence)
			fence := md.CalculateCodeFence(fenceChar, content)
			text := "\n\n" + fence + lang + "\n" + content + "\n" + fence + "\n\n"
			return md.String(text)
		},
	})

	// CODE -> inline backtick rule (only when NOT inside <pre>)
	conv.AddRules(md.Rule{
		Filter: []string{"code"},
		Replacement: func(_ string, selec *goquery.Selection, opt *md.Options) *string {
			if selec.ParentsFiltered("pre").Length() > 0 {
				return nil  // Let PRE rule handle it
			}
			var b strings.Builder
			for _, n := range selec.Nodes {
				collect(n, &b)
			}
			code := b.String()
			code = md.TrimTrailingSpaces(strings.ReplaceAll(code, "\r\n", "\n"))

			// Adaptive backtick fencing
			fence := "`"
			if strings.Contains(code, "`") {
				fence = "``"
				if strings.Contains(code, "``") {
					fence = "```"
				}
			}
			out := fence + code + fence
			return md.String(out)
		},
	})
}
```

### Key conversion behaviors:

1. **Gutter stripping:** Elements with class containing "gutter" or "line-numbers" are completely skipped. This handles syntax highlighters (like Prism.js, highlight.js) that wrap line numbers in separate elements.

2. **Language detection:** Looks for `language-*` or `lang-*` CSS classes on the `<code>` element first, then falls back to the `<pre>` element.

3. **Recursive text extraction:** Walks the entire DOM subtree under `<pre>`, collecting only text nodes. This handles complex structures like `<pre><table><tr><td class="gutter">...</td><td class="code"><code>actual code</code></td></tr></table></pre>` which some code highlighters produce.

4. **Block element newlines:** Inserts `\n` after block-level elements (p, div, li, tr, etc.) to preserve visual line breaks.

5. **`<br>` handling:** Converted to `\n`.

6. **Dynamic fence calculation:** Uses `md.CalculateCodeFence` to find a fence string that does not conflict with the code content. For inline code, escalates from `` ` `` to ` `` ` `` to ` ``` ` as needed.

7. **PRE/CODE coordination:** The inline `<code>` rule returns `nil` when inside a `<pre>`, deferring to the PRE rule to handle the entire block.

---

## 5. go.mod -- Dependencies

```
module github.com/firecrawl/go-html-to-md-service

go 1.23.0

require (
    github.com/PuerkitoBio/goquery v1.10.3        // HTML parsing / CSS selectors
    github.com/firecrawl/html-to-markdown v0.0.0-20260203173849-25e9840a0878  // Firecrawl's fork
    github.com/gorilla/mux v1.8.1                  // HTTP router
    github.com/rs/zerolog v1.33.0                  // Structured logging
    golang.org/x/net v0.41.0                       // net/html parser
)

require (
    github.com/andybalholm/cascadia v1.3.3         // indirect -- CSS selector engine
    github.com/kr/pretty v0.3.0                    // indirect
    github.com/mattn/go-colorable v0.1.13          // indirect -- terminal colors
    github.com/mattn/go-isatty v0.0.20             // indirect
    golang.org/x/sys v0.33.0                       // indirect
    gopkg.in/check.v1 v1.0.0-20201130134442-10cb98267c6c // indirect
    gopkg.in/yaml.v2 v2.4.0                        // indirect
)

replace github.com/JohannesKaufmann/html-to-markdown => github.com/firecrawl/html-to-markdown v0.0.0-20260203173849-25e9840a0878
```

### Critical detail: The `replace` directive

The service uses a **fork** of `JohannesKaufmann/html-to-markdown` maintained at `github.com/firecrawl/html-to-markdown`. The `replace` directive ensures that any transitive dependency on the original library also redirects to Firecrawl's fork. The fork commit date is `20260203` (February 3, 2026).

### Dependency graph:

```
go-html-to-md-service
├── firecrawl/html-to-markdown (fork of JohannesKaufmann/html-to-markdown)
│   ├── PuerkitoBio/goquery (HTML DOM manipulation)
│   │   └── andybalholm/cascadia (CSS selectors)
│   └── golang.org/x/net/html (HTML parser)
├── gorilla/mux (HTTP routing)
└── rs/zerolog (Structured logging)
    ├── mattn/go-colorable
    └── mattn/go-isatty
```

---

## 6. Dockerfile -- Container Build

```dockerfile
# Build stage
FROM golang:1.23-alpine AS builder
RUN apk add --no-cache git
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o html-to-markdown-service .

# Runtime stage
FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/html-to-markdown-service .
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1
CMD ["./html-to-markdown-service"]
```

- **Static binary:** `CGO_ENABLED=0` means no C dependencies, pure Go
- **Minimal runtime:** Alpine-based final image with only ca-certificates added
- **Built-in healthcheck:** Uses wget to probe `/health` every 30 seconds

---

## 7. docker-compose.yml

```yaml
version: '3.8'
services:
  html-to-markdown:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: html-to-markdown-service
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
```

---

## 8. CI/CD -- GitHub Actions Deploy

```yaml
name: Deploy Go Service to GHCR
on:
  push:
    branches: [main]
    paths:
      - apps/go-html-to-md-service/**
      - .github/workflows/deploy-go-service.yaml
  workflow_dispatch:

jobs:
  push-app-image:
    runs-on: blacksmith-4vcpu-ubuntu-2404
    defaults:
      run:
        working-directory: "./apps/go-html-to-md-service"
    steps:
      - uses: actions/checkout@main
      - uses: useblacksmith/setup-docker-builder@v1
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{github.actor}}
          password: ${{secrets.GITHUB_TOKEN}}
      - uses: useblacksmith/build-push-action@v2
        with:
          context: ./apps/go-html-to-md-service
          push: true
          tags: ghcr.io/firecrawl/go-html-to-md-service:latest
```

- Triggers on pushes to `main` that touch files under `apps/go-html-to-md-service/`
- Uses Blacksmith CI runners (4 vCPU Ubuntu 24.04)
- Publishes to GitHub Container Registry (GHCR) as `ghcr.io/firecrawl/go-html-to-md-service:latest`

---

## 9. Test Coverage (handler_test.go)

Tests cover:

| Test | What it validates |
|------|-------------------|
| `TestHealthCheck` | `/health` returns 200 with `"healthy"` status |
| `TestIndex` | `/` returns service info and endpoint list |
| `TestConvertHTML_Success` | 5 sub-tests: paragraph, bold, link, code block, inline code |
| `TestConvertHTML_EmptyHTML` | Empty HTML returns 400 |
| `TestConvertHTML_InvalidJSON` | Malformed JSON returns 400 |
| `TestConverter_ComplexHTML` | Direct converter test with headings, lists, code, bold, italic |

The `requests.http` file provides 21 additional manual test cases including tables, blockquotes, strikethrough, task lists, nested structures, and error cases.

---

## 10. API Usage

### Convert HTML to Markdown:

```bash
curl -X POST http://localhost:8080/convert \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-request-123" \
  -d '{"html": "<h1>Hello</h1><p>World with <strong>bold</strong></p>"}'
```

Response:
```json
{
  "markdown": "# Hello\n\nWorld with **bold**\n",
  "success": true
}
```

### Health check:

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-21T12:00:00Z",
  "service": "html-to-markdown"
}
```

---

## 11. Architecture Summary

```
HTTP Request (JSON: {"html": "..."})
        │
        ▼
   handler.go: ConvertHTML()
   ├── MaxBytesReader (150 MB limit)
   ├── JSON decode → ConvertRequest
   ├── Validate non-empty HTML
   │
   ▼
   converter.go: ConvertHTMLToMarkdown()
   ├── firecrawl/html-to-markdown base converter (commonmark mode)
   ├── GitHubFlavored plugin (tables, strikethrough, task lists)
   ├── Custom PRE rule:
   │   ├── Detect language from class="language-*" or "lang-*"
   │   ├── Skip gutter/line-number elements
   │   ├── Recursive text extraction from DOM subtree
   │   └── Dynamic fence calculation (```, ````, etc.)
   └── Custom CODE rule:
       ├── Skip if inside <pre> (defer to PRE rule)
       ├── Recursive text extraction
       └── Adaptive backtick fencing (`, ``, ```)
        │
        ▼
   JSON Response: {"markdown": "...", "success": true}
```

---

## 12. Key Takeaways for Our Web Crawler

1. **The service is stateless and simple.** It is a pure HTTP JSON API -- send HTML in, get markdown out. No authentication, no rate limiting, no persistence.

2. **The custom PRE/CODE rules are the most valuable part.** They handle the messy reality of scraped HTML: syntax highlighters with gutter elements, multiple nesting patterns, various language class conventions.

3. **The forked html-to-markdown library** (`firecrawl/html-to-markdown`) is based on `JohannesKaufmann/html-to-markdown` v2 -- a mature Go library that uses goquery (not regex) for HTML parsing. The fork likely contains Firecrawl-specific fixes.

4. **Performance characteristics:**
   - 150 MB max payload
   - 1-minute read/write timeouts
   - Single-threaded conversion per request (Go's HTTP server handles concurrency)
   - No caching

5. **To replicate this locally**, we would need:
   - `github.com/firecrawl/html-to-markdown` (the fork)
   - `github.com/PuerkitoBio/goquery`
   - The custom PRE/CODE rules from `converter.go`
   - Or simply call the service via HTTP if running as a sidecar

6. **The service can be pulled directly:**
   ```bash
   docker pull ghcr.io/firecrawl/go-html-to-md-service:latest
   docker run -p 8080:8080 ghcr.io/firecrawl/go-html-to-md-service:latest
   ```
