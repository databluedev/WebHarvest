"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { ModeSwitcher } from "@/components/layout/mode-switcher";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Globe, Loader2, Play, Eye, ChevronDown, ChevronUp, Settings2, Info, Sparkles, FileText, Code, Link2, Camera, Braces, List, Image as ImageIcon } from "lucide-react";
import Link from "next/link";

export default function CrawlPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);
  const [error, setError] = useState("");

  // Advanced options (collapsed by default)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxPages, setMaxPages] = useState(100);
  const [maxDepth, setMaxDepth] = useState(3);
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [concurrency, setConcurrency] = useState(3);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [extractEnabled, setExtractEnabled] = useState(false);
  const [extractPrompt, setExtractPrompt] = useState("");
  const [useProxy, setUseProxy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobileDevice, setMobileDevice] = useState("");
  const [devicePresets, setDevicePresets] = useState<any[]>([]);
  const [webhookSecret, setWebhookSecret] = useState("");
  const [formats, setFormats] = useState<string[]>(["markdown"]);
  const [onlyMainContent, setOnlyMainContent] = useState(true);
  const [waitFor, setWaitFor] = useState(0);

  const allFormats = [
    { id: "markdown", label: "Markdown", icon: FileText },
    { id: "html", label: "HTML", icon: Code },
    { id: "links", label: "Links", icon: Link2 },
    { id: "screenshot", label: "Screenshot", icon: Camera },
    { id: "structured_data", label: "Structured", icon: Braces },
    { id: "headings", label: "Headings", icon: List },
    { id: "images", label: "Images", icon: ImageIcon },
  ];

  const toggleFormat = (format: string) => {
    setFormats((prev) =>
      prev.includes(format) ? prev.filter((f) => f !== format) : [...prev, format]
    );
  };

  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then(res => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    // Load recent crawl jobs from API
    api.getUsageHistory({ type: "crawl", per_page: 10, sort_by: "created_at", sort_dir: "desc" })
      .then((res) => {
        setJobs(res.jobs.map((j: any) => ({
          id: j.id,
          url: j.config?.url || "Unknown",
          status: j.status,
          total_pages: j.total_pages,
          completed_pages: j.completed_pages,
          created_at: j.created_at,
        })));
      })
      .catch(() => {});
  }, [router]);

  const handleStartCrawl = async () => {
    if (!url) return;
    setLoading(true);
    setError("");

    try {
      const params: any = { url };

      // Only send advanced options if user explicitly configured them
      if (showAdvanced) {
        params.max_pages = maxPages;
        params.max_depth = maxDepth;
        params.concurrency = concurrency;
        if (includePaths.trim()) params.include_paths = includePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
        if (excludePaths.trim()) params.exclude_paths = excludePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
        if (webhookUrl.trim()) params.webhook_url = webhookUrl.trim();
        if (webhookSecret.trim()) params.webhook_secret = webhookSecret.trim();
        if (useProxy) params.use_proxy = true;
        params.scrape_options = {
          formats,
          only_main_content: onlyMainContent,
          wait_for: waitFor || undefined,
        };
        if (mobile) {
          params.scrape_options.mobile = true;
          if (mobileDevice) params.scrape_options.mobile_device = mobileDevice;
        }
      }
      if (extractEnabled && extractPrompt.trim()) {
        params.scrape_options = { ...params.scrape_options, extract: { prompt: extractPrompt.trim() } };
      }

      const res = await api.startCrawl(params);
      if (res.success) {
        // Redirect immediately to the crawl status page
        router.push(`/crawl/${res.job_id}`);
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && url && !loading) {
      handleStartCrawl();
    }
  };

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="min-h-screen flex flex-col">
        <div className="flex-1 p-6 lg:p-8 max-w-4xl mx-auto w-full">
          {/* Mode Switcher */}
          <div className="pt-4 pb-6 animate-float-in">
            <ModeSwitcher />
          </div>

          <div className="mb-8 animate-float-in" style={{ animationDelay: "0.05s" }}>
            <h1 className="text-3xl font-bold">Crawl</h1>
            <p className="text-muted-foreground mt-1">
              Enter a website URL and we'll recursively discover and scrape every page.
            </p>
          </div>

          {/* Main crawl input */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="https://example.com"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="h-12 text-base"
                  />
                </div>
                <Button
                  onClick={handleStartCrawl}
                  disabled={loading || !url}
                  className="h-12 px-6 gap-2"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Start Crawl
                </Button>
              </div>

              {error && (
                <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {/* Advanced Options Toggle */}
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="mt-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <Settings2 className="h-4 w-4" />
                Advanced Options
                {showAdvanced ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </button>

              {/* Advanced Options Panel */}
              {showAdvanced && (
                <div className="mt-4 pt-4 border-t border-border space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-1.5">
                        Page Limit
                        <span className="text-xs text-muted-foreground font-normal">
                          (max pages to crawl)
                        </span>
                      </label>
                      <Input
                        type="number"
                        value={maxPages}
                        onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)}
                        min={1}
                        max={10000}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-1.5">
                        Link Depth
                        <span className="text-xs text-muted-foreground font-normal">
                          (how many clicks deep)
                        </span>
                      </label>
                      <Input
                        type="number"
                        value={maxDepth}
                        onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)}
                        min={1}
                        max={20}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Concurrency: {concurrency}
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={concurrency}
                      onChange={(e) => setConcurrency(parseInt(e.target.value))}
                      className="w-full accent-primary"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>1 (sequential)</span>
                      <span>10 (max parallel)</span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Only Crawl These Paths
                      <span className="text-xs text-muted-foreground font-normal">
                        (comma-separated, e.g. /blog/*, /docs/*)
                      </span>
                    </label>
                    <Input
                      placeholder="Leave empty to crawl everything"
                      value={includePaths}
                      onChange={(e) => setIncludePaths(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Skip These Paths
                      <span className="text-xs text-muted-foreground font-normal">
                        (comma-separated, e.g. /admin/*, /login)
                      </span>
                    </label>
                    <Input
                      placeholder="Leave empty to skip nothing"
                      value={excludePaths}
                      onChange={(e) => setExcludePaths(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Webhook URL
                      <span className="text-xs text-muted-foreground font-normal">
                        (optional, notified on completion)
                      </span>
                    </label>
                    <Input
                      placeholder="https://your-server.com/webhook"
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                    />
                  </div>

                  {/* Webhook Secret */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Webhook Secret
                      <span className="text-xs text-muted-foreground font-normal">
                        (optional, signs webhook payloads)
                      </span>
                    </label>
                    <Input
                      placeholder="your-secret-key"
                      value={webhookSecret}
                      onChange={(e) => setWebhookSecret(e.target.value)}
                    />
                  </div>

                  {/* Output Formats */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Output Formats</label>
                    <div className="flex flex-wrap gap-1.5">
                      {allFormats.map((fmt) => (
                        <button
                          key={fmt.id}
                          onClick={() => toggleFormat(fmt.id)}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                            formats.includes(fmt.id)
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          <fmt.icon className="h-3 w-3" />
                          {fmt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Main Content Only */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Main content only</label>
                    <button
                      onClick={() => setOnlyMainContent(!onlyMainContent)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        onlyMainContent
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {onlyMainContent ? "On" : "Off"}
                    </button>
                  </div>

                  {/* Wait for */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Wait after load (ms)</label>
                    <Input
                      type="number"
                      value={waitFor}
                      onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)}
                      placeholder="0"
                    />
                  </div>

                  {/* Proxy */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Use Proxy</label>
                    <button
                      onClick={() => setUseProxy(!useProxy)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        useProxy
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {useProxy ? "On" : "Off"}
                    </button>
                  </div>

                  {/* Mobile Emulation */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Mobile Emulation</label>
                    <button
                      onClick={() => setMobile(!mobile)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        mobile
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {mobile ? "On" : "Off"}
                    </button>
                  </div>
                  {mobile && devicePresets.length > 0 && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Device</label>
                      <select
                        value={mobileDevice}
                        onChange={(e) => setMobileDevice(e.target.value)}
                        className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                      >
                        <option value="">Default mobile</option>
                        {devicePresets.map((d: any) => (
                          <option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* AI Extraction */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium flex items-center gap-1.5">
                        <Sparkles className="h-4 w-4" />
                        AI Extraction (BYOK)
                        <span className="text-xs text-muted-foreground font-normal">
                          (requires LLM key in Settings)
                        </span>
                      </label>
                      <button
                        onClick={() => setExtractEnabled(!extractEnabled)}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          extractEnabled
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {extractEnabled ? "On" : "Off"}
                      </button>
                    </div>
                    {extractEnabled && (
                      <Textarea
                        placeholder="e.g., Extract the product name, price, and description from each page"
                        value={extractPrompt}
                        onChange={(e) => setExtractPrompt(e.target.value)}
                        rows={3}
                        className="text-sm"
                      />
                    )}
                  </div>

                  <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3">
                    <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <p className="text-xs text-muted-foreground">
                      Default: crawl up to 100 pages, 3 links deep, staying on the same domain.
                      The crawler respects robots.txt and skips files like images, PDFs, and stylesheets.
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Crawls */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Crawls</CardTitle>
              <CardDescription>Your crawl history from this session</CardDescription>
            </CardHeader>
            <CardContent>
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Globe className="h-12 w-12 text-muted-foreground/40 mb-4" />
                  <p className="text-sm text-muted-foreground">
                    No crawls started yet. Enter a URL above to begin.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {jobs.map((job) => (
                    <Link
                      key={job.id}
                      href={`/crawl/${job.id}`}
                      className="flex items-center justify-between rounded-lg border border-border/50 p-3 hover:border-border transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{job.url}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-muted-foreground">{job.id.slice(0, 8)}</span>
                          {job.completed_pages > 0 && (
                            <span className="text-xs text-muted-foreground">{job.completed_pages}/{job.total_pages} pages</span>
                          )}
                          {job.created_at && (
                            <span className="text-xs text-muted-foreground">
                              {new Date(job.created_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <Badge
                          variant={
                            job.status === "completed"
                              ? "success"
                              : job.status === "failed"
                              ? "destructive"
                              : job.status === "running"
                              ? "warning"
                              : "default"
                          }
                        >
                          {job.status}
                        </Badge>
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <Footer />
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
