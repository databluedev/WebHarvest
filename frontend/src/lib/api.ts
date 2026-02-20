const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("wh_token", token);
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("wh_token");
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("wh_token");
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/auth/login";
      }
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  private async downloadFile(path: string, filename: string) {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_URL}${path}`, { headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Auth ──────────────────────────────────────────────────
  async register(email: string, password: string, name?: string) {
    return this.request<{ access_token: string }>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    });
  }

  async login(email: string, password: string) {
    return this.request<{ access_token: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async getMe() {
    return this.request<{ id: string; email: string; name: string }>("/v1/auth/me");
  }

  // ── API Keys ──────────────────────────────────────────────
  async createApiKey(name?: string) {
    return this.request<{ id: string; full_key: string; key_prefix: string }>("/v1/auth/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }

  async listApiKeys() {
    return this.request<Array<{ id: string; key_prefix: string; name: string; is_active: boolean; created_at: string }>>("/v1/auth/api-keys");
  }

  async revokeApiKey(keyId: string) {
    return this.request(`/v1/auth/api-keys/${keyId}`, { method: "DELETE" });
  }

  // ── Scrape ────────────────────────────────────────────────
  async scrape(params: {
    url: string;
    formats?: string[];
    only_main_content?: boolean;
    wait_for?: number;
    extract?: { prompt?: string; schema_?: object };
    use_proxy?: boolean;
    headers?: Record<string, string>;
    cookies?: Record<string, string>;
    mobile?: boolean;
    mobile_device?: string;
  }) {
    return this.request<{ success: boolean; data: any; error?: string; error_code?: string; job_id?: string }>("/v1/scrape", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getScrapeStatus(jobId: string) {
    return this.request<{
      success: boolean; job_id: string; status: string;
      total_pages: number; completed_pages: number;
      data?: Array<{
        url: string; markdown?: string; html?: string; links?: string[];
        links_detail?: any; screenshot?: string; structured_data?: any;
        headings?: any[]; images?: any[]; extract?: any; metadata?: any;
      }>;
      error?: string;
    }>(`/v1/scrape/${jobId}`);
  }

  async downloadScrapeExport(jobId: string, format: "zip" | "json" | "csv") {
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    await this.downloadFile(`/v1/scrape/${jobId}/export?format=${format}`, `scrape-${jobId.slice(0, 8)}.${ext}`);
  }

  // ── Crawl ─────────────────────────────────────────────────
  async startCrawl(params: {
    url: string;
    max_pages?: number;
    max_depth?: number;
    concurrency?: number;
    include_paths?: string[];
    exclude_paths?: string[];
    scrape_options?: object;
    extract?: { prompt?: string; schema_?: object };
    use_proxy?: boolean;
    webhook_url?: string;
    webhook_secret?: string;
  }) {
    return this.request<{ success: boolean; job_id: string }>("/v1/crawl", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getCrawlStatus(jobId: string, page: number = 1, perPage: number = 20) {
    return this.request<{
      success: boolean; job_id: string; status: string;
      total_pages: number; completed_pages: number;
      total_results: number; page: number; per_page: number;
      data?: Array<{
        url: string; markdown?: string; html?: string; links?: string[];
        links_detail?: any; screenshot?: string; structured_data?: any;
        headings?: any[]; images?: any[]; extract?: any; metadata?: any;
      }>;
    }>(`/v1/crawl/${jobId}?page=${page}&per_page=${perPage}`);
  }

  async cancelCrawl(jobId: string) {
    return this.request(`/v1/crawl/${jobId}`, { method: "DELETE" });
  }

  async downloadCrawlExport(jobId: string, format: "zip" | "json" | "csv") {
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    await this.downloadFile(`/v1/crawl/${jobId}/export?format=${format}`, `crawl-${jobId.slice(0, 8)}.${ext}`);
  }

  // ── Map ───────────────────────────────────────────────────
  async mapSite(params: {
    url: string;
    search?: string;
    limit?: number;
    include_subdomains?: boolean;
    use_sitemap?: boolean;
  }) {
    return this.request<{
      success: boolean; total: number;
      links: Array<{ url: string; title?: string; description?: string; lastmod?: string; priority?: number }>;
      job_id?: string;
    }>("/v1/map", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getMapStatus(jobId: string) {
    return this.request<{
      success: boolean; job_id: string; status: string; url: string; total: number;
      links: Array<{ url: string; title?: string; description?: string; lastmod?: string; priority?: number }>;
      error?: string;
    }>(`/v1/map/${jobId}`);
  }

  async downloadMapExport(jobId: string, format: "json" | "csv") {
    const ext = format === "csv" ? "csv" : "json";
    await this.downloadFile(`/v1/map/${jobId}/export?format=${format}`, `map-${jobId.slice(0, 8)}.${ext}`);
  }

  // ── Batch ─────────────────────────────────────────────────
  async startBatch(params: {
    urls?: string[];
    formats?: string[];
    only_main_content?: boolean;
    concurrency?: number;
    extract?: { prompt?: string; schema_?: object };
    use_proxy?: boolean;
    headers?: Record<string, string>;
    cookies?: Record<string, string>;
    mobile?: boolean;
    mobile_device?: string;
    webhook_url?: string;
    webhook_secret?: string;
  }) {
    return this.request<{ success: boolean; job_id: string; status: string; total_urls: number }>("/v1/batch/scrape", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getBatchStatus(jobId: string) {
    return this.request<{
      success: boolean; job_id: string; status: string;
      total_urls: number; completed_urls: number;
      data?: Array<{ url: string; success: boolean; markdown?: string; html?: string; links?: string[]; screenshot?: string; extract?: any; metadata?: any; error?: string }>;
      error?: string;
    }>(`/v1/batch/${jobId}`);
  }

  async downloadBatchExport(jobId: string, format: "zip" | "json" | "csv") {
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    await this.downloadFile(`/v1/batch/${jobId}/export?format=${format}`, `batch-${jobId.slice(0, 8)}.${ext}`);
  }

  // ── Search ────────────────────────────────────────────────
  async startSearch(params: {
    query: string;
    num_results?: number;
    engine?: string;
    google_api_key?: string;
    google_cx?: string;
    brave_api_key?: string;
    formats?: string[];
    only_main_content?: boolean;
    extract?: { prompt?: string; schema_?: object };
    use_proxy?: boolean;
    mobile?: boolean;
    mobile_device?: string;
    webhook_url?: string;
    webhook_secret?: string;
  }) {
    return this.request<{ success: boolean; job_id: string; status: string }>("/v1/search", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getSearchStatus(jobId: string) {
    return this.request<{
      success: boolean; job_id: string; status: string; query?: string;
      total_results: number; completed_results: number;
      data?: Array<{
        url: string; title?: string; snippet?: string; success: boolean;
        markdown?: string; html?: string; links?: string[];
        links_detail?: any; screenshot?: string; structured_data?: any;
        headings?: any[]; images?: any[]; extract?: any;
        metadata?: any; error?: string;
      }>;
      error?: string;
    }>(`/v1/search/${jobId}`);
  }

  async downloadSearchExport(jobId: string, format: "zip" | "json" | "csv") {
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    await this.downloadFile(`/v1/search/${jobId}/export?format=${format}`, `search-${jobId.slice(0, 8)}.${ext}`);
  }

  // ── Extract ───────────────────────────────────────────────
  async extract(params: {
    content?: string;
    html?: string;
    url?: string;
    urls?: string[];
    prompt?: string;
    schema_?: object;
    provider?: string;
    only_main_content?: boolean;
    use_proxy?: boolean;
  }) {
    return this.request<{
      success: boolean;
      data?: { url?: string; extract?: any; content_length?: number; error?: string } | Array<{ url?: string; extract?: any; content_length?: number; error?: string }>;
      error?: string;
      job_id?: string;
    }>("/v1/extract", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // ── Job Result Detail (on-demand screenshot loading) ─────
  async getJobResultDetail(jobId: string, resultId: string) {
    return this.request<{
      id: string; url: string; markdown?: string; html?: string;
      links?: string[]; links_detail?: any; screenshot?: string;
      structured_data?: any; headings?: any[]; images?: any[];
      extract?: any; metadata?: any;
    }>(`/v1/jobs/${jobId}/results/${resultId}`);
  }

  async getExtractStatus(jobId: string) {
    return this.request<{
      success: boolean; job_id: string; status: string;
      total_urls: number; completed_urls: number;
      data?: Array<{ url?: string; extract?: any; content_length?: number; error?: string }>;
      error?: string;
    }>(`/v1/extract/${jobId}`);
  }

  // ── Monitors ──────────────────────────────────────────────
  async createMonitor(params: {
    name: string;
    url: string;
    check_interval_minutes?: number;
    css_selector?: string;
    notify_on?: string;
    keywords?: string[];
    webhook_url?: string;
    webhook_secret?: string;
    threshold?: number;
  }) {
    return this.request<{ success: boolean; monitor: any }>("/v1/monitors", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async listMonitors(activeOnly?: boolean) {
    const qs = activeOnly ? "?active_only=true" : "";
    return this.request<{ success: boolean; monitors: any[]; total: number }>(`/v1/monitors${qs}`);
  }

  async getMonitor(monitorId: string) {
    return this.request<{ success: boolean; monitor: any }>(`/v1/monitors/${monitorId}`);
  }

  async updateMonitor(monitorId: string, params: {
    name?: string;
    check_interval_minutes?: number;
    css_selector?: string;
    notify_on?: string;
    keywords?: string[];
    webhook_url?: string;
    is_active?: boolean;
    threshold?: number;
  }) {
    return this.request<{ success: boolean; monitor: any }>(`/v1/monitors/${monitorId}`, {
      method: "PATCH",
      body: JSON.stringify(params),
    });
  }

  async deleteMonitor(monitorId: string) {
    return this.request(`/v1/monitors/${monitorId}`, { method: "DELETE" });
  }

  async triggerMonitorCheck(monitorId: string) {
    return this.request<{ success: boolean }>(`/v1/monitors/${monitorId}/check`, { method: "POST" });
  }

  async getMonitorHistory(monitorId: string, limit = 50, offset = 0) {
    return this.request<{
      success: boolean; monitor_id: string;
      checks: Array<{
        id: string; checked_at: string; status_code: number;
        content_hash: string; has_changed: boolean;
        change_detail?: any; word_count: number; response_time_ms: number;
      }>;
      total: number;
    }>(`/v1/monitors/${monitorId}/history?limit=${limit}&offset=${offset}`);
  }

  // ── Webhooks ──────────────────────────────────────────────
  async listWebhookDeliveries(params: {
    limit?: number;
    offset?: number;
    event?: string;
    success?: boolean;
    job_id?: string;
  } = {}) {
    const query = new URLSearchParams();
    if (params.limit) query.set("limit", String(params.limit));
    if (params.offset) query.set("offset", String(params.offset));
    if (params.event) query.set("event", params.event);
    if (params.success !== undefined) query.set("success", String(params.success));
    if (params.job_id) query.set("job_id", params.job_id);
    const qs = query.toString();
    return this.request<{
      success: boolean;
      deliveries: Array<{
        id: string; job_id?: string; url: string; event: string;
        payload: any; status_code?: number; response_body?: string;
        response_time_ms?: number; success: boolean; attempt: number;
        max_attempts: number; error?: string; created_at: string;
      }>;
      total: number;
    }>(`/v1/webhooks/deliveries${qs ? `?${qs}` : ""}`);
  }

  async getWebhookDelivery(deliveryId: string) {
    return this.request<{ success: boolean; delivery: any }>(`/v1/webhooks/deliveries/${deliveryId}`);
  }

  async testWebhook(url: string, secret?: string) {
    const query = new URLSearchParams({ url });
    if (secret) query.set("secret", secret);
    return this.request<{
      success: boolean;
      test_result: {
        success: boolean; status_code?: number; response_body?: string;
        response_time_ms: number; error?: string;
      };
    }>(`/v1/webhooks/test?${query.toString()}`, { method: "POST" });
  }

  async getWebhookStats() {
    return this.request<{
      success: boolean;
      stats: {
        total_deliveries: number; successful: number; failed: number;
        success_rate: number; avg_response_time_ms: number;
        events_breakdown: Record<string, number>;
      };
    }>("/v1/webhooks/stats");
  }

  // ── Settings / BYOK ───────────────────────────────────────
  async saveLlmKey(params: { provider: string; api_key: string; model?: string; is_default?: boolean }) {
    return this.request("/v1/settings/llm-keys", { method: "PUT", body: JSON.stringify(params) });
  }

  async listLlmKeys() {
    return this.request<{ keys: Array<{ id: string; provider: string; model?: string; is_default: boolean; key_preview: string; created_at: string }> }>("/v1/settings/llm-keys");
  }

  async deleteLlmKey(keyId: string) {
    return this.request(`/v1/settings/llm-keys/${keyId}`, { method: "DELETE" });
  }

  // ── Proxy ─────────────────────────────────────────────────
  async addProxies(proxies: string[], proxyType: string = "http") {
    return this.request<{ proxies: Array<{ id: string; proxy_url_masked: string; proxy_type: string; label: string | null; is_active: boolean; created_at: string }>; total: number }>("/v1/settings/proxies", {
      method: "POST",
      body: JSON.stringify({ proxies, proxy_type: proxyType }),
    });
  }

  async listProxies() {
    return this.request<{ proxies: Array<{ id: string; proxy_url_masked: string; proxy_type: string; label: string | null; is_active: boolean; created_at: string }>; total: number }>("/v1/settings/proxies");
  }

  async deleteProxy(proxyId: string) {
    return this.request(`/v1/settings/proxies/${proxyId}`, { method: "DELETE" });
  }

  // ── Usage / Analytics ─────────────────────────────────────
  async getUsageStats() {
    return this.request<{
      total_jobs: number; total_pages_scraped: number;
      avg_pages_per_job: number; avg_duration_seconds: number;
      success_rate: number; jobs_by_type: Record<string, number>;
      jobs_by_status: Record<string, number>;
      jobs_per_day: Array<{ date: string; count: number }>;
    }>("/v1/usage/stats");
  }

  async getUsageHistory(params: {
    page?: number; per_page?: number; type?: string;
    status?: string; search?: string; sort_by?: string; sort_dir?: string;
  } = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.per_page) query.set("per_page", String(params.per_page));
    if (params.type && params.type !== "all") query.set("type", params.type);
    if (params.status && params.status !== "all") query.set("status", params.status);
    if (params.search) query.set("search", params.search);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    const qs = query.toString();
    return this.request<{
      total: number; page: number; per_page: number; total_pages: number;
      jobs: Array<{
        id: string; type: string; status: string; config: any;
        total_pages: number; completed_pages: number; error: string | null;
        started_at: string | null; completed_at: string | null; created_at: string | null;
        duration_seconds: number | null;
      }>;
    }>(`/v1/usage/history${qs ? `?${qs}` : ""}`);
  }

  async getTopDomains() {
    return this.request<{
      domains: Array<{ domain: string; count: number }>;
      total_unique_domains: number;
    }>("/v1/usage/top-domains");
  }

  async getQuota() {
    return this.request<{
      success: boolean; period: string;
      total_pages_scraped: number; total_bytes_processed: number;
      operations: Record<string, { limit: number; used: number; remaining: number; unlimited: boolean }>;
    }>("/v1/usage/quota");
  }

  async getDevicePresets() {
    return this.request<{
      success: boolean;
      devices: Array<{ id: string; name: string; width: number; height: number; type: string }>;
    }>("/v1/usage/devices");
  }

  async deleteJob(jobId: string) {
    return this.request(`/v1/usage/jobs/${jobId}`, { method: "DELETE" });
  }

  // ── Schedules ─────────────────────────────────────────────
  async createSchedule(params: {
    name: string; schedule_type: string; config: any;
    cron_expression: string; timezone?: string; webhook_url?: string;
  }) {
    return this.request<any>("/v1/schedules", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async listSchedules() {
    return this.request<{
      schedules: Array<{
        id: string; name: string; schedule_type: string; config: any;
        cron_expression: string; timezone: string; is_active: boolean;
        last_run_at: string | null; next_run_at: string | null;
        next_run_human: string | null; run_count: number;
        webhook_url: string | null; created_at: string; updated_at: string;
      }>;
      total: number;
    }>("/v1/schedules");
  }

  async getSchedule(scheduleId: string) {
    return this.request<any>(`/v1/schedules/${scheduleId}`);
  }

  async getScheduleRuns(scheduleId: string) {
    return this.request<{ runs: any[] }>(`/v1/schedules/${scheduleId}/runs`);
  }

  async updateSchedule(scheduleId: string, params: {
    name?: string; cron_expression?: string; timezone?: string;
    is_active?: boolean; config?: any; webhook_url?: string;
  }) {
    return this.request<any>(`/v1/schedules/${scheduleId}`, {
      method: "PUT",
      body: JSON.stringify(params),
    });
  }

  async deleteSchedule(scheduleId: string) {
    return this.request(`/v1/schedules/${scheduleId}`, { method: "DELETE" });
  }

  async triggerSchedule(scheduleId: string) {
    return this.request<{ success: boolean; job_id: string }>(`/v1/schedules/${scheduleId}/trigger`, {
      method: "POST",
    });
  }

  // ── SSE ───────────────────────────────────────────────────
  getSSEUrl(jobId: string): string {
    return `${API_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(this.getToken() || "")}`;
  }
}

export const API_BASE_URL = API_URL;
export const api = new ApiClient();
