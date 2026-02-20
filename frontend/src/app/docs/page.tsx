"use client";

import { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ChevronDown, ChevronRight, Search, FileText, Copy, Check } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HttpMethod = "GET" | "POST" | "DELETE" | "PATCH" | "PUT";

interface Endpoint {
  method: HttpMethod;
  path: string;
  description: string;
  requestBody?: string;
  responseBody: string;
}

interface Section {
  id: string;
  title: string;
  description: string;
  endpoints: Endpoint[];
}

// ---------------------------------------------------------------------------
// Method badge color map
// ---------------------------------------------------------------------------

const METHOD_STYLES: Record<HttpMethod, string> = {
  GET: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  POST: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  DELETE: "bg-red-500/15 text-red-400 border-red-500/25",
  PATCH: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  PUT: "bg-orange-500/15 text-orange-400 border-orange-500/25",
};

// ---------------------------------------------------------------------------
// API Section Data
// ---------------------------------------------------------------------------

const API_SECTIONS: Section[] = [
  {
    id: "authentication",
    title: "Authentication",
    description:
      "Register, login, and manage authentication. All protected endpoints require a Bearer token or API key in the Authorization header.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/auth/register",
        description:
          "Create a new user account. Returns an access token upon successful registration.",
        requestBody: JSON.stringify(
          {
            email: "user@example.com",
            password: "securepassword123",
            name: "Jane Doe",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            access_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            token_type: "bearer",
            user: {
              id: "usr_a1b2c3d4e5f6",
              email: "user@example.com",
              name: "Jane Doe",
              created_at: "2025-09-15T08:30:00Z",
            },
          },
          null,
          2
        ),
      },
      {
        method: "POST",
        path: "/v1/auth/login",
        description:
          "Authenticate with email and password. Returns a JWT access token for subsequent API calls.",
        requestBody: JSON.stringify(
          {
            email: "user@example.com",
            password: "securepassword123",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            access_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            token_type: "bearer",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/auth/me",
        description:
          "Retrieve the currently authenticated user profile. Requires a valid Bearer token.",
        responseBody: JSON.stringify(
          {
            id: "usr_a1b2c3d4e5f6",
            email: "user@example.com",
            name: "Jane Doe",
            created_at: "2025-09-15T08:30:00Z",
            settings: {
              openai_api_key_set: true,
              anthropic_api_key_set: false,
              default_format: "markdown",
            },
          },
          null,
          2
        ),
      },
      {
        method: "POST",
        path: "/v1/auth/api-keys",
        description:
          "Generate a new API key for programmatic access. The full key is only shown once.",
        requestBody: JSON.stringify(
          {
            name: "Production Key",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            id: "key_x7y8z9w0",
            name: "Production Key",
            prefix: "wh_prod_",
            full_key: "wh_prod_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            created_at: "2025-09-15T10:00:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/auth/api-keys",
        description:
          "List all API keys associated with the authenticated user. Keys are masked except for the prefix.",
        responseBody: JSON.stringify(
          {
            keys: [
              {
                id: "key_x7y8z9w0",
                name: "Production Key",
                prefix: "wh_prod_",
                last_used_at: "2025-09-16T14:22:00Z",
                created_at: "2025-09-15T10:00:00Z",
              },
            ],
          },
          null,
          2
        ),
      },
      {
        method: "DELETE",
        path: "/v1/auth/api-keys/:id",
        description:
          "Revoke and permanently delete an API key. This action cannot be undone.",
        responseBody: JSON.stringify(
          {
            message: "API key revoked successfully",
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "scrape",
    title: "Scrape",
    description:
      "Single-page scraping with JavaScript rendering, stealth mode, and content extraction. The 5-tier engine tries multiple strategies in parallel for maximum reliability.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/scrape",
        description:
          "Scrape a single URL. The engine automatically selects the best extraction strategy (HTTP, browser, stealth, or archive fallback).",
        requestBody: JSON.stringify(
          {
            url: "https://example.com/pricing",
            formats: ["markdown", "html"],
            wait_for: 2000,
            timeout: 30000,
            headers: {
              "Accept-Language": "en-US",
            },
            include_tags: ["article", "main"],
            exclude_tags: ["nav", "footer"],
            only_main_content: true,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            data: {
              id: "scrape_k8m2n4p6",
              url: "https://example.com/pricing",
              status: "completed",
              markdown: "# Pricing\\n\\n## Starter Plan\\n- $9/month\\n- 1,000 pages...",
              html: "<h1>Pricing</h1><h2>Starter Plan</h2>...",
              metadata: {
                title: "Pricing - Example",
                description: "View our pricing plans",
                language: "en",
                status_code: 200,
              },
              extracted_at: "2025-09-16T12:00:00Z",
              duration_ms: 1842,
              strategy_used: "tier_2_browser",
            },
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/scrape/:id",
        description:
          "Retrieve the status and results of a scrape job by its ID.",
        responseBody: JSON.stringify(
          {
            id: "scrape_k8m2n4p6",
            url: "https://example.com/pricing",
            status: "completed",
            markdown: "# Pricing\\n\\n## Starter Plan...",
            metadata: {
              title: "Pricing - Example",
              status_code: 200,
            },
            duration_ms: 1842,
            strategy_used: "tier_2_browser",
            created_at: "2025-09-16T12:00:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/scrape/:id/export",
        description:
          "Export scrape results in the specified format. Supports JSON, CSV, and markdown file downloads.",
        responseBody: JSON.stringify(
          {
            format: "json",
            filename: "scrape_k8m2n4p6.json",
            data: {
              url: "https://example.com/pricing",
              markdown: "# Pricing\\n\\n## Starter Plan...",
              metadata: { title: "Pricing - Example" },
            },
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "crawl",
    title: "Crawl",
    description:
      "Recursive website crawling with BFS traversal, link discovery, and persistent browser sessions. Ideal for scraping entire sites or sections.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/crawl",
        description:
          "Start a crawl job that recursively follows links from the seed URL. Supports depth limits, URL filtering, and page limits.",
        requestBody: JSON.stringify(
          {
            url: "https://docs.example.com",
            max_depth: 3,
            max_pages: 100,
            formats: ["markdown"],
            include_patterns: ["/docs/*", "/guides/*"],
            exclude_patterns: ["/blog/*", "*.pdf"],
            only_main_content: true,
            wait_for: 1000,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "crawl_r3s5t7v9",
            url: "https://docs.example.com",
            status: "running",
            config: {
              max_depth: 3,
              max_pages: 100,
              formats: ["markdown"],
            },
            total_pages: 0,
            completed_pages: 0,
            created_at: "2025-09-16T12:05:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/crawl/:id",
        description:
          "Check the status and progress of a crawl job. Returns discovered pages and completion stats.",
        responseBody: JSON.stringify(
          {
            id: "crawl_r3s5t7v9",
            url: "https://docs.example.com",
            status: "completed",
            total_pages: 47,
            completed_pages: 47,
            failed_pages: 2,
            duration_ms: 84320,
            pages: [
              {
                url: "https://docs.example.com/getting-started",
                status: "completed",
                markdown: "# Getting Started\\n\\nWelcome to...",
                metadata: { title: "Getting Started" },
              },
            ],
            created_at: "2025-09-16T12:05:00Z",
            completed_at: "2025-09-16T12:06:24Z",
          },
          null,
          2
        ),
      },
      {
        method: "DELETE",
        path: "/v1/crawl/:id",
        description:
          "Cancel a running crawl job. Already scraped pages are retained; no new pages will be fetched.",
        responseBody: JSON.stringify(
          {
            message: "Crawl job cancelled successfully",
            id: "crawl_r3s5t7v9",
            pages_completed: 23,
            pages_remaining: 24,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/crawl/:id/export",
        description:
          "Export all crawled pages as a bundled archive. Supports JSON and CSV formats.",
        responseBody: JSON.stringify(
          {
            format: "json",
            filename: "crawl_r3s5t7v9_export.json",
            total_pages: 47,
            data: [
              {
                url: "https://docs.example.com/getting-started",
                markdown: "# Getting Started...",
                metadata: { title: "Getting Started" },
              },
            ],
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "batch",
    title: "Batch",
    description:
      "Scrape multiple URLs in a single batch job with shared configuration. Efficient for bulk extraction of known URL lists.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/batch/scrape",
        description:
          "Submit a batch of URLs to scrape concurrently. All URLs share the same extraction settings.",
        requestBody: JSON.stringify(
          {
            urls: [
              "https://example.com/page-1",
              "https://example.com/page-2",
              "https://example.com/page-3",
            ],
            formats: ["markdown", "html"],
            only_main_content: true,
            concurrency: 5,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "batch_w1x3y5z7",
            status: "running",
            total_urls: 3,
            completed: 0,
            failed: 0,
            created_at: "2025-09-16T12:10:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/batch/:id",
        description:
          "Retrieve the status and progress of a batch scrape job, including per-URL results.",
        responseBody: JSON.stringify(
          {
            id: "batch_w1x3y5z7",
            status: "completed",
            total_urls: 3,
            completed: 3,
            failed: 0,
            results: [
              {
                url: "https://example.com/page-1",
                status: "completed",
                markdown: "# Page 1 Content...",
                duration_ms: 1230,
              },
              {
                url: "https://example.com/page-2",
                status: "completed",
                markdown: "# Page 2 Content...",
                duration_ms: 980,
              },
              {
                url: "https://example.com/page-3",
                status: "completed",
                markdown: "# Page 3 Content...",
                duration_ms: 1540,
              },
            ],
            duration_ms: 3120,
            created_at: "2025-09-16T12:10:00Z",
            completed_at: "2025-09-16T12:10:03Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/batch/:id/export",
        description:
          "Export all batch results as a bundled download in JSON or CSV format.",
        responseBody: JSON.stringify(
          {
            format: "json",
            filename: "batch_w1x3y5z7_export.json",
            total_urls: 3,
            data: [
              {
                url: "https://example.com/page-1",
                markdown: "# Page 1 Content...",
                metadata: { title: "Page 1" },
              },
            ],
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "search",
    title: "Search",
    description:
      "Search the web and scrape the results. Combines search engine queries with the scraping pipeline for research workflows.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/search",
        description:
          "Execute a web search query and scrape the top results. Returns structured content from each result page.",
        requestBody: JSON.stringify(
          {
            query: "best practices for web scraping in 2025",
            num_results: 5,
            formats: ["markdown"],
            only_main_content: true,
            country: "us",
            language: "en",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "search_a2b4c6d8",
            status: "running",
            query: "best practices for web scraping in 2025",
            num_results: 5,
            completed: 0,
            created_at: "2025-09-16T12:15:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/search/:id",
        description:
          "Retrieve the status and results of a search job.",
        responseBody: JSON.stringify(
          {
            id: "search_a2b4c6d8",
            status: "completed",
            query: "best practices for web scraping in 2025",
            results: [
              {
                url: "https://blog.example.com/web-scraping-guide",
                title: "Web Scraping Best Practices 2025",
                snippet: "A comprehensive guide to ethical web scraping...",
                markdown: "# Web Scraping Best Practices 2025\\n\\n...",
                rank: 1,
              },
            ],
            total_results: 5,
            duration_ms: 12480,
            created_at: "2025-09-16T12:15:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/search/:id/export",
        description:
          "Export search results with scraped content as a bundled download.",
        responseBody: JSON.stringify(
          {
            format: "json",
            filename: "search_a2b4c6d8_export.json",
            query: "best practices for web scraping in 2025",
            total_results: 5,
            data: [
              {
                url: "https://blog.example.com/web-scraping-guide",
                title: "Web Scraping Best Practices 2025",
                markdown: "# Web Scraping Best Practices...",
              },
            ],
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "map",
    title: "Map",
    description:
      "Fast URL discovery and sitemap generation without extracting page content. Quickly enumerate all reachable pages on a domain.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/map",
        description:
          "Start a map job to discover all URLs on a domain using sitemap parsing, robots.txt, and link extraction.",
        requestBody: JSON.stringify(
          {
            url: "https://docs.example.com",
            max_pages: 500,
            include_patterns: ["/docs/*"],
            exclude_patterns: ["/internal/*"],
            include_subdomains: false,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "map_e4f6g8h0",
            url: "https://docs.example.com",
            status: "running",
            urls_found: 0,
            created_at: "2025-09-16T12:20:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/map/:id",
        description:
          "Retrieve the status and discovered URLs from a map job.",
        responseBody: JSON.stringify(
          {
            id: "map_e4f6g8h0",
            url: "https://docs.example.com",
            status: "completed",
            urls_found: 142,
            urls: [
              "https://docs.example.com/",
              "https://docs.example.com/getting-started",
              "https://docs.example.com/api-reference",
              "https://docs.example.com/guides/authentication",
            ],
            duration_ms: 4320,
            created_at: "2025-09-16T12:20:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/map/:id/export",
        description:
          "Export the discovered URL list as JSON, CSV, or plain text.",
        responseBody: JSON.stringify(
          {
            format: "json",
            filename: "map_e4f6g8h0_urls.json",
            total_urls: 142,
            urls: [
              "https://docs.example.com/",
              "https://docs.example.com/getting-started",
              "https://docs.example.com/api-reference",
            ],
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "extract",
    title: "Extract",
    description:
      "AI-powered structured data extraction. Define a schema or prompt and the engine will extract matching data from any page.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/extract",
        description:
          "Extract structured data from a URL using an AI model. Provide either a JSON schema or a natural language prompt describing the data you need.",
        requestBody: JSON.stringify(
          {
            url: "https://example.com/product/12345",
            prompt: "Extract the product name, price, rating, and availability",
            schema: {
              type: "object",
              properties: {
                product_name: { type: "string" },
                price: { type: "number" },
                currency: { type: "string" },
                rating: { type: "number" },
                in_stock: { type: "boolean" },
              },
            },
            model: "gpt-4o-mini",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "extract_i1j3k5l7",
            status: "completed",
            url: "https://example.com/product/12345",
            extracted_data: {
              product_name: "Wireless Noise-Cancelling Headphones",
              price: 299.99,
              currency: "USD",
              rating: 4.7,
              in_stock: true,
            },
            model_used: "gpt-4o-mini",
            tokens_used: 1240,
            duration_ms: 3420,
            created_at: "2025-09-16T12:25:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/extract/:id",
        description:
          "Retrieve the result of an extraction job by its ID.",
        responseBody: JSON.stringify(
          {
            id: "extract_i1j3k5l7",
            status: "completed",
            url: "https://example.com/product/12345",
            extracted_data: {
              product_name: "Wireless Noise-Cancelling Headphones",
              price: 299.99,
              currency: "USD",
              rating: 4.7,
              in_stock: true,
            },
            model_used: "gpt-4o-mini",
            tokens_used: 1240,
            duration_ms: 3420,
            created_at: "2025-09-16T12:25:00Z",
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "monitors",
    title: "Monitors",
    description:
      "Set up automated monitors to track changes on web pages. Get notified when content changes via webhooks or periodic checks.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/monitors",
        description:
          "Create a new page monitor that periodically checks a URL for content changes.",
        requestBody: JSON.stringify(
          {
            name: "Pricing Page Monitor",
            url: "https://example.com/pricing",
            check_interval_minutes: 60,
            notify_on_change: true,
            webhook_url: "https://hooks.example.com/pricing-changed",
            css_selector: ".pricing-table",
            formats: ["markdown"],
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "mon_m2n4o6p8",
            name: "Pricing Page Monitor",
            url: "https://example.com/pricing",
            status: "active",
            check_interval_minutes: 60,
            next_check_at: "2025-09-16T13:25:00Z",
            created_at: "2025-09-16T12:25:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/monitors",
        description:
          "List all monitors for the authenticated user with their current status.",
        responseBody: JSON.stringify(
          {
            monitors: [
              {
                id: "mon_m2n4o6p8",
                name: "Pricing Page Monitor",
                url: "https://example.com/pricing",
                status: "active",
                last_check_at: "2025-09-16T13:25:00Z",
                last_change_at: "2025-09-15T08:00:00Z",
                check_interval_minutes: 60,
                checks_count: 24,
              },
            ],
            total: 1,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/monitors/:id",
        description:
          "Retrieve details of a specific monitor including its configuration and latest status.",
        responseBody: JSON.stringify(
          {
            id: "mon_m2n4o6p8",
            name: "Pricing Page Monitor",
            url: "https://example.com/pricing",
            status: "active",
            check_interval_minutes: 60,
            css_selector: ".pricing-table",
            notify_on_change: true,
            webhook_url: "https://hooks.example.com/pricing-changed",
            last_check_at: "2025-09-16T13:25:00Z",
            last_change_at: "2025-09-15T08:00:00Z",
            checks_count: 24,
            changes_count: 3,
            created_at: "2025-09-16T12:25:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "PATCH",
        path: "/v1/monitors/:id",
        description:
          "Update monitor configuration such as the check interval, selectors, or webhook URL.",
        requestBody: JSON.stringify(
          {
            check_interval_minutes: 30,
            css_selector: ".pricing-table, .plan-card",
            notify_on_change: true,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            id: "mon_m2n4o6p8",
            name: "Pricing Page Monitor",
            status: "active",
            check_interval_minutes: 30,
            css_selector: ".pricing-table, .plan-card",
            updated_at: "2025-09-16T14:00:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "DELETE",
        path: "/v1/monitors/:id",
        description:
          "Delete a monitor and all its check history. This action cannot be undone.",
        responseBody: JSON.stringify(
          {
            message: "Monitor deleted successfully",
            id: "mon_m2n4o6p8",
          },
          null,
          2
        ),
      },
      {
        method: "POST",
        path: "/v1/monitors/:id/check",
        description:
          "Manually trigger an immediate check on a monitor, bypassing the scheduled interval.",
        responseBody: JSON.stringify(
          {
            id: "check_q1r3s5t7",
            monitor_id: "mon_m2n4o6p8",
            status: "completed",
            changed: true,
            diff_summary: "Price changed from $9/mo to $12/mo on Starter plan",
            checked_at: "2025-09-16T14:05:00Z",
            duration_ms: 2180,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/monitors/:id/history",
        description:
          "Retrieve the check history for a monitor, showing each check result and whether changes were detected.",
        responseBody: JSON.stringify(
          {
            monitor_id: "mon_m2n4o6p8",
            checks: [
              {
                id: "check_q1r3s5t7",
                status: "completed",
                changed: true,
                diff_summary: "Price changed from $9/mo to $12/mo",
                checked_at: "2025-09-16T14:05:00Z",
              },
              {
                id: "check_u8v0w2x4",
                status: "completed",
                changed: false,
                checked_at: "2025-09-16T13:05:00Z",
              },
            ],
            total: 24,
            page: 1,
            per_page: 20,
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "webhooks",
    title: "Webhooks",
    description:
      "Manage webhook delivery logs, test webhook endpoints, and view delivery statistics.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/webhooks/deliveries",
        description:
          "List recent webhook delivery attempts with their status and response details.",
        responseBody: JSON.stringify(
          {
            deliveries: [
              {
                id: "dlv_a1b2c3d4",
                webhook_url: "https://hooks.example.com/pricing-changed",
                event_type: "monitor.change_detected",
                status: "delivered",
                response_code: 200,
                response_time_ms: 142,
                payload_size_bytes: 1024,
                delivered_at: "2025-09-16T14:05:01Z",
              },
              {
                id: "dlv_e5f6g7h8",
                webhook_url: "https://hooks.example.com/pricing-changed",
                event_type: "monitor.check_failed",
                status: "failed",
                response_code: 500,
                response_time_ms: 3021,
                retry_count: 2,
                next_retry_at: "2025-09-16T14:35:00Z",
                delivered_at: "2025-09-16T14:05:02Z",
              },
            ],
            total: 2,
            page: 1,
            per_page: 20,
          },
          null,
          2
        ),
      },
      {
        method: "POST",
        path: "/v1/webhooks/test",
        description:
          "Send a test webhook payload to a URL to verify your endpoint is correctly configured.",
        requestBody: JSON.stringify(
          {
            url: "https://hooks.example.com/test",
            event_type: "test.ping",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            delivery_id: "dlv_test_i9j0k1l2",
            response_code: 200,
            response_time_ms: 89,
            response_body: "{\"received\": true}",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/webhooks/stats",
        description:
          "View aggregate webhook delivery statistics including success rates and average response times.",
        responseBody: JSON.stringify(
          {
            total_deliveries: 1248,
            successful: 1201,
            failed: 47,
            success_rate: 96.23,
            avg_response_time_ms: 156,
            deliveries_last_24h: 42,
            events_by_type: {
              "monitor.change_detected": 820,
              "monitor.check_failed": 38,
              "crawl.completed": 312,
              "batch.completed": 78,
            },
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "schedules",
    title: "Schedules",
    description:
      "Create and manage scheduled scraping jobs using cron expressions. Automate recurring data extraction workflows.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/schedules",
        description:
          "Create a new scheduled job that runs at the specified cron interval.",
        requestBody: JSON.stringify(
          {
            name: "Daily News Scrape",
            cron: "0 8 * * *",
            timezone: "America/New_York",
            job_type: "scrape",
            job_config: {
              url: "https://news.example.com",
              formats: ["markdown"],
              only_main_content: true,
            },
            enabled: true,
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            success: true,
            id: "sched_m3n5o7p9",
            name: "Daily News Scrape",
            cron: "0 8 * * *",
            timezone: "America/New_York",
            job_type: "scrape",
            status: "active",
            next_run_at: "2025-09-17T08:00:00Z",
            created_at: "2025-09-16T12:30:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/schedules",
        description:
          "List all scheduled jobs with their current status and next run times.",
        responseBody: JSON.stringify(
          {
            schedules: [
              {
                id: "sched_m3n5o7p9",
                name: "Daily News Scrape",
                cron: "0 8 * * *",
                timezone: "America/New_York",
                job_type: "scrape",
                status: "active",
                last_run_at: "2025-09-16T08:00:00Z",
                next_run_at: "2025-09-17T08:00:00Z",
                total_runs: 14,
                success_rate: 100,
              },
            ],
            total: 1,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/schedules/:id",
        description:
          "Retrieve the full configuration and run history summary for a scheduled job.",
        responseBody: JSON.stringify(
          {
            id: "sched_m3n5o7p9",
            name: "Daily News Scrape",
            cron: "0 8 * * *",
            timezone: "America/New_York",
            job_type: "scrape",
            job_config: {
              url: "https://news.example.com",
              formats: ["markdown"],
              only_main_content: true,
            },
            status: "active",
            last_run_at: "2025-09-16T08:00:00Z",
            last_run_status: "completed",
            next_run_at: "2025-09-17T08:00:00Z",
            total_runs: 14,
            successful_runs: 14,
            failed_runs: 0,
            created_at: "2025-09-02T10:00:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "PATCH",
        path: "/v1/schedules/:id",
        description:
          "Update a schedule's configuration, cron expression, or enabled state.",
        requestBody: JSON.stringify(
          {
            cron: "0 6 * * *",
            enabled: true,
            name: "Early Morning News Scrape",
          },
          null,
          2
        ),
        responseBody: JSON.stringify(
          {
            id: "sched_m3n5o7p9",
            name: "Early Morning News Scrape",
            cron: "0 6 * * *",
            status: "active",
            next_run_at: "2025-09-17T06:00:00Z",
            updated_at: "2025-09-16T14:30:00Z",
          },
          null,
          2
        ),
      },
      {
        method: "DELETE",
        path: "/v1/schedules/:id",
        description:
          "Delete a scheduled job. Running instances are not affected, but no new runs will be triggered.",
        responseBody: JSON.stringify(
          {
            message: "Schedule deleted successfully",
            id: "sched_m3n5o7p9",
          },
          null,
          2
        ),
      },
      {
        method: "POST",
        path: "/v1/schedules/:id/trigger",
        description:
          "Manually trigger an immediate run of the scheduled job, independent of the cron schedule.",
        responseBody: JSON.stringify(
          {
            success: true,
            schedule_id: "sched_m3n5o7p9",
            triggered_job_id: "scrape_t9u1v3w5",
            status: "running",
            triggered_at: "2025-09-16T14:35:00Z",
          },
          null,
          2
        ),
      },
    ],
  },
  {
    id: "usage",
    title: "Usage",
    description:
      "Access usage analytics, quota information, and historical data about your account's API consumption.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/usage/stats",
        description:
          "Get aggregate usage statistics including total jobs, pages scraped, success rates, and breakdowns by type.",
        responseBody: JSON.stringify(
          {
            total_jobs: 1847,
            total_pages_scraped: 24530,
            avg_pages_per_job: 13.3,
            avg_duration_seconds: 8.4,
            success_rate: 97.2,
            jobs_by_type: {
              scrape: 892,
              crawl: 412,
              batch: 283,
              search: 156,
              map: 104,
            },
            jobs_by_status: {
              completed: 1795,
              failed: 32,
              running: 12,
              queued: 8,
            },
            jobs_per_day: [
              { date: "2025-09-15", count: 42 },
              { date: "2025-09-16", count: 38 },
            ],
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/usage/history",
        description:
          "Retrieve paginated job history with filtering by type, status, and date range.",
        responseBody: JSON.stringify(
          {
            jobs: [
              {
                id: "scrape_k8m2n4p6",
                type: "scrape",
                status: "completed",
                url: "https://example.com/pricing",
                total_pages: 1,
                completed_pages: 1,
                duration_ms: 1842,
                created_at: "2025-09-16T12:00:00Z",
              },
              {
                id: "crawl_r3s5t7v9",
                type: "crawl",
                status: "completed",
                url: "https://docs.example.com",
                total_pages: 47,
                completed_pages: 47,
                duration_ms: 84320,
                created_at: "2025-09-16T12:05:00Z",
              },
            ],
            total: 1847,
            page: 1,
            per_page: 20,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/usage/quota",
        description:
          "Check current quota limits and usage for the billing period. Self-hosted instances may not enforce quotas.",
        responseBody: JSON.stringify(
          {
            plan: "self-hosted",
            period_start: "2025-09-01T00:00:00Z",
            period_end: "2025-09-30T23:59:59Z",
            limits: {
              jobs_per_month: null,
              pages_per_month: null,
              concurrent_jobs: 10,
              max_pages_per_crawl: 10000,
            },
            usage: {
              jobs_this_month: 1847,
              pages_this_month: 24530,
              active_jobs: 12,
            },
            unlimited: true,
          },
          null,
          2
        ),
      },
      {
        method: "GET",
        path: "/v1/usage/devices",
        description:
          "List active sessions and devices that have accessed the API, with geolocation and last-active timestamps.",
        responseBody: JSON.stringify(
          {
            devices: [
              {
                id: "dev_a1b2c3",
                name: "Chrome on macOS",
                ip_address: "192.168.1.100",
                user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
                last_active_at: "2025-09-16T14:30:00Z",
                created_at: "2025-09-10T08:00:00Z",
              },
              {
                id: "dev_d4e5f6",
                name: "API Key: Production Key",
                ip_address: "10.0.0.50",
                last_active_at: "2025-09-16T14:28:00Z",
                created_at: "2025-09-15T10:00:00Z",
              },
            ],
            total: 2,
          },
          null,
          2
        ),
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// CodeBlock component with copy button
// ---------------------------------------------------------------------------

function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for insecure contexts
      const textarea = document.createElement("textarea");
      textarea.value = code;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-widest">
          {label}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-muted-foreground/50 hover:text-foreground/70 hover:bg-foreground/[0.05] transition-all duration-150"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="rounded-lg border border-border bg-muted p-4 overflow-x-auto text-[12px] leading-relaxed font-mono text-foreground/70">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EndpointCard component
// ---------------------------------------------------------------------------

function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden transition-all duration-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-foreground/[0.02] transition-all duration-150"
      >
        <div className="shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground/50" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
          )}
        </div>
        <Badge
          className={`shrink-0 rounded-md border px-2 py-0.5 text-[11px] font-bold tracking-wide ${METHOD_STYLES[endpoint.method]}`}
        >
          {endpoint.method}
        </Badge>
        <code className="text-sm font-mono text-foreground/80 truncate">
          {endpoint.path}
        </code>
        <span className="ml-auto text-xs text-muted-foreground/50 hidden sm:block max-w-[40%] truncate">
          {endpoint.description}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-border animate-scale-in">
          <p className="text-sm text-muted-foreground mt-4 leading-relaxed">
            {endpoint.description}
          </p>

          {endpoint.requestBody && (
            <CodeBlock code={endpoint.requestBody} label="Request Body" />
          )}

          <CodeBlock code={endpoint.responseBody} label="Response" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Docs Page
// ---------------------------------------------------------------------------

export default function DocsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSection, setActiveSection] = useState("");

  // Filter sections & endpoints based on search query
  const filteredSections = useMemo(() => {
    if (!searchQuery.trim()) return API_SECTIONS;

    const q = searchQuery.toLowerCase();
    return API_SECTIONS.map((section) => {
      const matchesSection =
        section.title.toLowerCase().includes(q) ||
        section.description.toLowerCase().includes(q);

      const matchedEndpoints = section.endpoints.filter(
        (ep) =>
          ep.method.toLowerCase().includes(q) ||
          ep.path.toLowerCase().includes(q) ||
          ep.description.toLowerCase().includes(q)
      );

      if (matchesSection) return section;
      if (matchedEndpoints.length > 0) {
        return { ...section, endpoints: matchedEndpoints };
      }
      return null;
    }).filter(Boolean) as Section[];
  }, [searchQuery]);

  const handleSectionClick = (sectionId: string) => {
    setActiveSection(sectionId);
    const element = document.getElementById(`section-${sectionId}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Update active section on scroll
  const handleScroll = (e: React.UIEvent<HTMLElement>) => {
    const container = e.currentTarget;
    const scrollTop = container.scrollTop;

    for (const section of API_SECTIONS) {
      const el = document.getElementById(`section-${section.id}`);
      if (el) {
        const offsetTop = el.offsetTop - container.offsetTop;
        if (scrollTop >= offsetTop - 120) {
          setActiveSection(section.id);
        }
      }
    }
  };

  const totalEndpoints = API_SECTIONS.reduce(
    (sum, s) => sum + s.endpoints.length,
    0
  );

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar Navigation */}
      <aside className="hidden lg:flex flex-col w-72 border-r border-border bg-sidebar">
        {/* Sidebar Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="h-9 w-9 rounded-lg bg-primary/10 grid place-items-center">
              <FileText className="h-4.5 w-4.5 text-primary" />
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight">API Docs</h1>
              <p className="text-[11px] text-muted-foreground/50">v1 Reference</p>
            </div>
          </div>

          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/40" />
            <Input
              placeholder="Search endpoints..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 rounded-md text-sm h-9"
            />
          </div>
        </div>

        {/* Section Links */}
        <nav className="flex-1 overflow-y-auto py-3 px-3">
          {API_SECTIONS.map((section) => {
            const isActive = activeSection === section.id;
            return (
              <button
                key={section.id}
                onClick={() => handleSectionClick(section.id)}
                className={`relative w-full flex items-center justify-between rounded-md px-3 py-2.5 text-left text-sm transition-all duration-150 mb-0.5 ${
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground/80 hover:bg-foreground/[0.03]"
                }`}
              >
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-r-full bg-primary" />
                )}
                <span>{section.title}</span>
                <span
                  className={`text-[10px] tabular-nums ${
                    isActive ? "text-primary/60" : "text-muted-foreground/40"
                  }`}
                >
                  {section.endpoints.length}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-border">
          <div className="rounded-lg border border-border bg-muted/50 p-3">
            <p className="text-[11px] text-muted-foreground/50 leading-relaxed">
              <span className="text-foreground/60 font-medium">{API_SECTIONS.length} sections</span>
              {" / "}
              <span className="text-foreground/60 font-medium">{totalEndpoints} endpoints</span>
            </p>
            <p className="text-[10px] text-muted-foreground/40 mt-1">
              Base URL: <code className="text-primary/70 font-mono">/api/v1</code>
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main
        className="flex-1 overflow-y-auto"
        onScroll={handleScroll}
      >
        <div className="max-w-4xl mx-auto px-6 md:px-10 py-10">
          {/* Page Header */}
          <header className="mb-10 animate-float-in">
            <div className="inline-flex items-center gap-2 rounded-md border border-border bg-muted/50 px-3.5 py-1.5 mb-5">
              <FileText className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs text-foreground/60">API Reference</span>
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.1]">
              API{" "}
              <span className="text-foreground">Documentation</span>
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mt-4 leading-relaxed font-light">
              Complete reference for the WebHarvest REST API. All endpoints accept and
              return JSON. Authenticate using a Bearer token or API key in the{" "}
              <code className="text-xs bg-foreground/[0.06] px-1.5 py-0.5 rounded font-mono text-foreground/70">
                Authorization
              </code>{" "}
              header.
            </p>

            {/* Auth example */}
            <div className="mt-5 rounded-lg border border-border bg-card p-4">
              <p className="text-[10px] text-muted-foreground/50 uppercase tracking-widest font-medium mb-2">
                Authorization Header
              </p>
              <code className="text-sm font-mono text-foreground/60 block">
                <span className="text-muted-foreground/40">Authorization:</span>{" "}
                <span className="text-primary/80">Bearer</span>{" "}
                <span className="text-amber-400/70">wh_prod_sk_a1b2c3d4...</span>
              </code>
            </div>

            {/* Mobile search */}
            <div className="relative mt-5 lg:hidden">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/40" />
              <Input
                placeholder="Search endpoints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 rounded-md text-sm h-10"
              />
            </div>

            {/* Mobile section pills */}
            <div className="flex flex-wrap gap-2 mt-5 lg:hidden">
              {API_SECTIONS.map((section) => (
                <button
                  key={section.id}
                  onClick={() => handleSectionClick(section.id)}
                  className={`rounded-md px-3 py-1.5 text-xs transition-all duration-150 border ${
                    activeSection === section.id
                      ? "bg-primary/10 text-primary border-primary/20"
                      : "text-muted-foreground border-border hover:bg-muted"
                  }`}
                >
                  {section.title}
                </button>
              ))}
            </div>
          </header>

          {/* Sections */}
          <div className="space-y-12">
            {filteredSections.length === 0 && (
              <div className="rounded-lg border border-border bg-card p-12 text-center">
                <Search className="h-10 w-10 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground text-sm">
                  No endpoints matching{" "}
                  <span className="text-foreground/70 font-medium">
                    &ldquo;{searchQuery}&rdquo;
                  </span>
                </p>
                <button
                  onClick={() => setSearchQuery("")}
                  className="mt-3 text-xs text-primary hover:underline"
                >
                  Clear search
                </button>
              </div>
            )}

            {filteredSections.map((section) => (
              <section
                key={section.id}
                id={`section-${section.id}`}
                className="scroll-mt-6"
              >
                {/* Section Header */}
                <div className="mb-4">
                  <h2 className="text-xl font-bold tracking-tight flex items-center gap-3">
                    {section.title}
                    <Badge
                      variant="outline"
                      className="text-[10px] font-normal text-muted-foreground border-border"
                    >
                      {section.endpoints.length}{" "}
                      {section.endpoints.length === 1 ? "endpoint" : "endpoints"}
                    </Badge>
                  </h2>
                  <p className="text-sm text-muted-foreground/70 mt-1.5 leading-relaxed max-w-2xl">
                    {section.description}
                  </p>
                </div>

                {/* Endpoints */}
                <div className="space-y-2">
                  {section.endpoints.map((endpoint, idx) => (
                    <EndpointCard
                      key={`${endpoint.method}-${endpoint.path}-${idx}`}
                      endpoint={endpoint}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>

          {/* Footer */}
          <footer className="mt-16 mb-8 pt-8 border-t border-border">
            <div className="rounded-lg border border-border bg-card p-6 text-center">
              <p className="text-sm text-muted-foreground">
                Need help?{" "}
                <a href="/api-keys" className="text-primary hover:underline">
                  Generate an API key
                </a>{" "}
                to get started or check the{" "}
                <a href="/" className="text-primary hover:underline">
                  dashboard
                </a>{" "}
                for usage analytics.
              </p>
              <p className="text-[11px] text-muted-foreground/40 mt-2">
                WebHarvest API v1 -- Self-hosted open source web crawling platform
              </p>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
