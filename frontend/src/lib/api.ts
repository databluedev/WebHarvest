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

  // Auth
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

  // API Keys
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

  // Scrape
  async scrape(params: {
    url: string;
    formats?: string[];
    only_main_content?: boolean;
    wait_for?: number;
    extract?: { prompt?: string; schema_?: object };
    use_proxy?: boolean;
  }) {
    return this.request<{ success: boolean; data: any; error?: string }>("/v1/scrape", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // Crawl
  async startCrawl(params: {
    url: string;
    max_pages?: number;
    max_depth?: number;
    include_paths?: string[];
    exclude_paths?: string[];
    scrape_options?: object;
    use_proxy?: boolean;
  }) {
    return this.request<{ success: boolean; job_id: string }>("/v1/crawl", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getCrawlStatus(jobId: string) {
    return this.request<{
      success: boolean;
      job_id: string;
      status: string;
      total_pages: number;
      completed_pages: number;
      data?: Array<{
        url: string;
        markdown?: string;
        html?: string;
        links?: string[];
        links_detail?: any;
        screenshot?: string;
        structured_data?: any;
        headings?: any[];
        images?: any[];
        metadata?: any;
      }>;
    }>(`/v1/crawl/${jobId}`);
  }

  async cancelCrawl(jobId: string) {
    return this.request(`/v1/crawl/${jobId}`, { method: "DELETE" });
  }

  async downloadCrawlExport(jobId: string, format: "zip" | "json" | "csv") {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_URL}/v1/crawl/${jobId}/export?format=${format}`, { headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    const mime = format === "zip" ? "application/zip" : format === "csv" ? "text/csv" : "application/json";
    const url = URL.createObjectURL(new Blob([blob], { type: mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `crawl-${jobId.slice(0, 8)}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Map
  async mapSite(params: {
    url: string;
    search?: string;
    limit?: number;
    include_subdomains?: boolean;
    use_sitemap?: boolean;
  }) {
    return this.request<{
      success: boolean;
      total: number;
      links: Array<{ url: string; title?: string; description?: string }>;
    }>("/v1/map", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // Settings / BYOK
  async saveLlmKey(params: {
    provider: string;
    api_key: string;
    model?: string;
    is_default?: boolean;
  }) {
    return this.request("/v1/settings/llm-keys", {
      method: "PUT",
      body: JSON.stringify(params),
    });
  }

  async listLlmKeys() {
    return this.request<{
      keys: Array<{
        id: string;
        provider: string;
        model?: string;
        is_default: boolean;
        key_preview: string;
        created_at: string;
      }>;
    }>("/v1/settings/llm-keys");
  }

  async deleteLlmKey(keyId: string) {
    return this.request(`/v1/settings/llm-keys/${keyId}`, { method: "DELETE" });
  }

  // Proxy
  async addProxies(proxies: string[], proxyType: string = "http") {
    return this.request<{
      proxies: Array<{
        id: string;
        proxy_url_masked: string;
        proxy_type: string;
        label: string | null;
        is_active: boolean;
        created_at: string;
      }>;
      total: number;
    }>("/v1/settings/proxies", {
      method: "POST",
      body: JSON.stringify({ proxies, proxy_type: proxyType }),
    });
  }

  async listProxies() {
    return this.request<{
      proxies: Array<{
        id: string;
        proxy_url_masked: string;
        proxy_type: string;
        label: string | null;
        is_active: boolean;
        created_at: string;
      }>;
      total: number;
    }>("/v1/settings/proxies");
  }

  async deleteProxy(proxyId: string) {
    return this.request(`/v1/settings/proxies/${proxyId}`, { method: "DELETE" });
  }

  // Batch
  async startBatch(params: {
    urls?: string[];
    formats?: string[];
    only_main_content?: boolean;
    concurrency?: number;
    use_proxy?: boolean;
  }) {
    return this.request<{
      success: boolean;
      job_id: string;
      status: string;
      total_urls: number;
    }>("/v1/batch/scrape", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async downloadBatchExport(jobId: string, format: "zip" | "json" | "csv") {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_URL}/v1/batch/${jobId}/export?format=${format}`, { headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch-${jobId.slice(0, 8)}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async getBatchStatus(jobId: string) {
    return this.request<{
      success: boolean;
      job_id: string;
      status: string;
      total_urls: number;
      completed_urls: number;
      data?: Array<{
        url: string;
        success: boolean;
        markdown?: string;
        html?: string;
        links?: string[];
        screenshot?: string;
        metadata?: any;
        error?: string;
      }>;
      error?: string;
    }>(`/v1/batch/${jobId}`);
  }

  // Search
  async startSearch(params: {
    query: string;
    num_results?: number;
    engine?: string;
    google_api_key?: string;
    google_cx?: string;
    formats?: string[];
    use_proxy?: boolean;
  }) {
    return this.request<{
      success: boolean;
      job_id: string;
      status: string;
    }>("/v1/search", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async downloadSearchExport(jobId: string, format: "zip" | "json" | "csv") {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_URL}/v1/search/${jobId}/export?format=${format}`, { headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const ext = format === "zip" ? "zip" : format === "csv" ? "csv" : "json";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `search-${jobId.slice(0, 8)}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async getSearchStatus(jobId: string) {
    return this.request<{
      success: boolean;
      job_id: string;
      status: string;
      query?: string;
      total_results: number;
      completed_results: number;
      data?: Array<{
        url: string;
        title?: string;
        snippet?: string;
        success: boolean;
        markdown?: string;
        html?: string;
        metadata?: any;
        error?: string;
      }>;
      error?: string;
    }>(`/v1/search/${jobId}`);
  }
}

export const api = new ApiClient();
