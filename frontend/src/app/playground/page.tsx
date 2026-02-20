"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Footer } from "@/components/layout/footer";
import { FormatSelector } from "@/components/layout/format-selector";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";
import {
  Globe,
  Search,
  Map,
  Layers,
  Radar,
  Loader2,
  SlidersHorizontal,
  FileCode,
  Code,
  ChevronDown,
  FileText,
  Link2,
  Camera,
  Braces,
  List,
  Image as ImageIcon,
  Sparkles,
  ExternalLink,
  Copy,
  Check,
  Download,
  ArrowRight,
  Clock,
  Crosshair,
  Satellite,
  Network,
  Bug,
  Boxes,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────

type Endpoint = "scrape" | "crawl" | "search" | "map" | "batch";

const ENDPOINTS: { id: Endpoint; label: string; icon: any }[] = [
  { id: "scrape", label: "Scrape", icon: Crosshair },
  { id: "search", label: "Search", icon: Satellite },
  { id: "map", label: "Map", icon: Network },
  { id: "crawl", label: "Crawl", icon: Bug },
  { id: "batch", label: "Batch", icon: Boxes },
];

const ACTION_LABELS: Record<Endpoint, string> = {
  scrape: "Start scraping",
  crawl: "Start crawling",
  search: "Start searching",
  map: "Start mapping",
  batch: "Start batch",
};

const PLACEHOLDERS: Record<Endpoint, string> = {
  scrape: "example.com",
  crawl: "example.com",
  map: "example.com",
  search: "python web scraping tutorial",
  batch: "",
};

// ── Helpers ──────────────────────────────────────────────────

function getJobDetailPath(job: any): string {
  switch (job.type) {
    case "scrape": return `/scrape/${job.id}`;
    case "crawl": return `/crawl/${job.id}`;
    case "batch": return `/batch/${job.id}`;
    case "search": return `/search/${job.id}`;
    case "map": return `/map/${job.id}`;
    default: return `/crawl/${job.id}`;
  }
}

function getJobUrl(job: any): string {
  if (!job.config) return "";
  if (job.config.url) return job.config.url;
  if (job.config.query) return job.config.query;
  if (job.config.urls?.length === 1) return job.config.urls[0];
  if (job.config.urls?.length > 1) return `${job.config.urls.length} URLs`;
  return "";
}

function getDomain(url: string): string {
  try {
    const parsed = new URL(url.startsWith("http") ? url : `https://${url}`);
    return parsed.hostname;
  } catch {
    return url;
  }
}

function getFavicon(url: string): string {
  return `https://www.google.com/s2/favicons?domain=${getDomain(url)}&sz=32`;
}

function getTypeIcon(type: string) {
  switch (type) {
    case "scrape": return Crosshair;
    case "crawl": return Bug;
    case "map": return Network;
    case "search": return Satellite;
    case "batch": return Boxes;
    default: return FileText;
  }
}

function formatDate(dateStr: string): { date: string; time: string } {
  const d = new Date(dateStr);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
  };
}

const formatIcons: Record<string, { icon: any; label: string }> = {
  markdown: { icon: FileText, label: "Markdown" },
  html: { icon: Code, label: "HTML" },
  links: { icon: Link2, label: "Links" },
  screenshot: { icon: Camera, label: "Screenshot" },
  structured_data: { icon: Braces, label: "JSON" },
  headings: { icon: List, label: "Summary" },
  images: { icon: ImageIcon, label: "Images" },
};

async function handleDownload(job: any) {
  try {
    switch (job.type) {
      case "scrape": await api.downloadScrapeExport(job.id, "json"); break;
      case "crawl": await api.downloadCrawlExport(job.id, "json"); break;
      case "search": await api.downloadSearchExport(job.id, "json"); break;
      case "map": await api.downloadMapExport(job.id, "json"); break;
      case "batch": await api.downloadBatchExport(job.id, "json"); break;
    }
  } catch {}
}

// ── Main Component ───────────────────────────────────────────

function PlaygroundContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const endpointParam = (searchParams.get("endpoint") || "scrape") as Endpoint;
  const activeEndpoint = ENDPOINTS.find((e) => e.id === endpointParam) ? endpointParam : "scrape";

  // ── Shared state ──
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [formats, setFormats] = useState<string[]>(["markdown"]);
  const [showFormatSelector, setShowFormatSelector] = useState(false);
  const [htmlMode, setHtmlMode] = useState<"cleaned" | "raw">("cleaned");
  const [screenshotMode, setScreenshotMode] = useState<"viewport" | "fullpage">("fullpage");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [onlyMainContent, setOnlyMainContent] = useState(true);
  const [waitFor, setWaitFor] = useState(0);
  const [useProxy, setUseProxy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobileDevice, setMobileDevice] = useState("");
  const [devicePresets, setDevicePresets] = useState<any[]>([]);
  const [extractEnabled, setExtractEnabled] = useState(false);
  const [extractPrompt, setExtractPrompt] = useState("");
  const [headersText, setHeadersText] = useState("");
  const [cookiesText, setCookiesText] = useState("");

  // ── Recent runs ──
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);

  // ── Crawl state ──
  const [maxPages, setMaxPages] = useState(100);
  const [maxDepth, setMaxDepth] = useState(3);
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [concurrency, setConcurrency] = useState(3);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  // ── Search state ──
  const [searchQuery, setSearchQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [engine, setEngine] = useState("duckduckgo");

  // ── Batch state ──
  const [batchUrlText, setBatchUrlText] = useState("");
  const [batchConcurrency, setBatchConcurrency] = useState(5);

  // ── Map state ──
  const [mapSearch, setMapSearch] = useState("");
  const [mapLimit, setMapLimit] = useState(100);
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [useSitemap, setUseSitemap] = useState(true);
  const [mapResult, setMapResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!api.getToken()) { router.push("/auth/login"); return; }
    api.getUsageHistory({ per_page: 9 })
      .then((res) => { setRecentJobs(res.jobs || []); setJobsLoaded(true); })
      .catch(() => setJobsLoaded(true));
  }, [router]);

  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then((res) => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

  useEffect(() => { setError(""); }, [activeEndpoint]);

  const switchEndpoint = (ep: Endpoint) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("endpoint", ep);
    router.replace(`/playground?${params.toString()}`, { scroll: false });
  };

  const toggleFormat = (format: string) => {
    setFormats((prev) =>
      prev.includes(format) ? prev.filter((f) => f !== format) : [...prev, format]
    );
  };

  const formatSummary = formats.length === 0
    ? "No format"
    : formats.length === 1
    ? formats[0].charAt(0).toUpperCase() + formats[0].slice(1).replace("_", " ")
    : `${formats.length} formats`;

  const handleGetCode = () => {
    let code = "";
    const fullUrl = url.startsWith("http") ? url : `https://${url}`;
    switch (activeEndpoint) {
      case "scrape":
        code = `curl -X POST /v1/scrape \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "formats": ${JSON.stringify(formats)}}'`;
        break;
      case "crawl":
        code = `curl -X POST /v1/crawl \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "max_pages": ${maxPages}, "max_depth": ${maxDepth}}'`;
        break;
      case "search":
        code = `curl -X POST /v1/search \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"query": "${searchQuery}", "num_results": ${numResults}, "engine": "${engine}"}'`;
        break;
      case "map":
        code = `curl -X POST /v1/map \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "limit": ${mapLimit}}'`;
        break;
      case "batch": {
        const urls = batchUrlText.split("\n").filter((l) => l.trim()).slice(0, 3);
        code = `curl -X POST /v1/batch/scrape \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"urls": ${JSON.stringify(urls)}, "formats": ${JSON.stringify(formats)}}'`;
        break;
      }
    }
    navigator.clipboard.writeText(code);
  };

  const handleAction = async () => {
    setLoading(true);
    setError("");
    try {
      switch (activeEndpoint) {
        case "scrape": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const params: any = { url: fullUrl, formats, only_main_content: onlyMainContent, wait_for: waitFor || undefined, use_proxy: useProxy || undefined, mobile: mobile || undefined, mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined };
          if (extractEnabled && extractPrompt) params.extract = { prompt: extractPrompt };
          if (headersText.trim()) { try { params.headers = JSON.parse(headersText); } catch {} }
          if (cookiesText.trim()) { try { params.cookies = JSON.parse(cookiesText); } catch {} }
          const res = await api.scrape(params);
          if (res.job_id) router.push(`/scrape/${res.job_id}`);
          break;
        }
        case "crawl": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const params: any = { url: fullUrl };
          if (showAdvanced) {
            params.max_pages = maxPages; params.max_depth = maxDepth; params.concurrency = concurrency;
            if (includePaths.trim()) params.include_paths = includePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
            if (excludePaths.trim()) params.exclude_paths = excludePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
            if (webhookUrl.trim()) params.webhook_url = webhookUrl.trim();
            if (webhookSecret.trim()) params.webhook_secret = webhookSecret.trim();
            if (useProxy) params.use_proxy = true;
            params.scrape_options = { formats, only_main_content: onlyMainContent, wait_for: waitFor || undefined };
            if (mobile) { params.scrape_options.mobile = true; if (mobileDevice) params.scrape_options.mobile_device = mobileDevice; }
          }
          if (extractEnabled && extractPrompt.trim()) {
            params.scrape_options = { ...params.scrape_options, extract: { prompt: extractPrompt.trim() } };
          }
          const res = await api.startCrawl(params);
          if (res.success) router.push(`/crawl/${res.job_id}`);
          break;
        }
        case "search": {
          if (!searchQuery.trim()) return;
          const params: any = { query: searchQuery.trim(), num_results: numResults, engine, formats, only_main_content: onlyMainContent, use_proxy: useProxy || undefined, mobile: mobile || undefined, mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined, webhook_url: webhookUrl.trim() || undefined, webhook_secret: webhookSecret.trim() || undefined };
          if (extractEnabled && extractPrompt.trim()) params.extract = { prompt: extractPrompt.trim() };
          const res = await api.startSearch(params);
          if (res.success) router.push(`/search/${res.job_id}`);
          break;
        }
        case "map": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const res = await api.mapSite({ url: fullUrl, search: mapSearch || undefined, limit: mapLimit, include_subdomains: includeSubdomains || undefined, use_sitemap: useSitemap });
          if (res.success && res.job_id) router.push(`/map/${res.job_id}`);
          else if (res.success) setMapResult(res);
          else setError("Map failed");
          break;
        }
        case "batch": {
          const urls = batchUrlText.split("\n").map((l) => l.trim()).filter(Boolean);
          if (urls.length === 0) return;
          const params: any = { urls, formats, concurrency: batchConcurrency, only_main_content: onlyMainContent, wait_for: waitFor || undefined, use_proxy: useProxy || undefined, mobile: mobile || undefined, mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined, webhook_url: webhookUrl.trim() || undefined, webhook_secret: webhookSecret.trim() || undefined };
          if (extractEnabled && extractPrompt.trim()) params.extract = { prompt: extractPrompt.trim() };
          if (headersText.trim()) { try { params.headers = JSON.parse(headersText); } catch {} }
          if (cookiesText.trim()) { try { params.cookies = JSON.parse(cookiesText); } catch {} }
          const res = await api.startBatch(params);
          if (res.success) router.push(`/batch/${res.job_id}`);
          break;
        }
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isDisabled = loading || (
    activeEndpoint === "search" ? !searchQuery.trim() :
    activeEndpoint === "batch" ? batchUrlText.split("\n").filter((l) => l.trim()).length === 0 :
    !url.trim()
  );

  const batchUrlCount = batchUrlText.split("\n").filter((l) => l.trim()).length;
  const hasRuns = recentJobs.length > 0;

  const copyMapUrls = () => {
    if (!mapResult?.links) return;
    navigator.clipboard.writeText(mapResult.links.map((l: any) => l.url).join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ActiveIcon = ENDPOINTS.find((e) => e.id === activeEndpoint)?.icon || Crosshair;

  return (
    <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background">
          <MobileMenuButton />
          <div className="min-h-screen flex flex-col">
            <div className={cn(
              "flex-1 flex flex-col w-full max-w-5xl mx-auto px-6 lg:px-8 transition-all duration-500",
              !hasRuns && jobsLoaded ? "justify-center" : "pt-6"
            )}>

              {/* ── Mode Switcher ── */}
              <div className={cn("animate-float-in", hasRuns ? "pb-6" : "pb-8")}>
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-0.5 rounded-2xl border border-border/60 bg-card/70 backdrop-blur-md p-1 shadow-lg shadow-black/10">
                    {ENDPOINTS.map((ep) => {
                      const isActive = activeEndpoint === ep.id;
                      return (
                        <button
                          key={ep.id}
                          onClick={() => switchEndpoint(ep.id)}
                          className={cn(
                            "flex items-center gap-1.5 rounded-xl px-4 py-2 text-[13px] font-semibold transition-all duration-250",
                            isActive
                              ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                          )}
                        >
                          <ep.icon className="h-3.5 w-3.5" />
                          <span>{ep.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* ── Active mode tag (empty state only) ── */}
              {!hasRuns && jobsLoaded && (
                <div className="flex justify-center mb-5 animate-fade-in">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-primary">
                      {activeEndpoint} mode
                    </span>
                  </div>
                </div>
              )}

              {/* ── URL Input Section ── */}
              <section className={cn(
                "max-w-2xl w-full mx-auto animate-float-in",
                hasRuns ? "mb-8" : "mb-4"
              )} style={{ animationDelay: "0.05s" }}>
                <div className="rounded-2xl border border-primary/15 bg-card/80 backdrop-blur-sm p-4 shadow-xl shadow-primary/5">

                  {/* Input */}
                  {activeEndpoint === "batch" ? (
                    <div className="mb-3">
                      <textarea
                        className="flex min-h-[120px] w-full rounded-xl border border-border/50 bg-background px-4 py-3 text-sm font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:border-primary/30 resize-none transition-all"
                        placeholder={"https://example.com\nhttps://another-site.com\nhttps://docs.example.com"}
                        value={batchUrlText}
                        onChange={(e) => setBatchUrlText(e.target.value)}
                      />
                      <p className="text-[11px] text-muted-foreground mt-1.5 font-medium">
                        {batchUrlCount} URL{batchUrlCount !== 1 ? "s" : ""} (one per line, max 100)
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-0 rounded-xl bg-background border border-border/50 px-4 h-12 mb-3 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/25 transition-all">
                      {activeEndpoint !== "search" ? (
                        <span className="text-sm text-muted-foreground shrink-0 select-none font-mono">https://</span>
                      ) : (
                        <Search className="h-4 w-4 text-muted-foreground shrink-0 mr-1" />
                      )}
                      <input
                        type="text"
                        value={activeEndpoint === "search" ? searchQuery : url}
                        onChange={(e) => {
                          if (activeEndpoint === "search") setSearchQuery(e.target.value);
                          else setUrl(e.target.value);
                        }}
                        onKeyDown={(e) => e.key === "Enter" && !isDisabled && handleAction()}
                        placeholder={PLACEHOLDERS[activeEndpoint]}
                        className={cn(
                          "flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50",
                          activeEndpoint !== "search" && "ml-1"
                        )}
                      />
                      <ActiveIcon className="h-4 w-4 shrink-0 ml-2 text-primary/40" />
                    </div>
                  )}

                  {/* No format warning */}
                  {formats.length === 0 && activeEndpoint !== "map" && (
                    <div className="flex items-center gap-2 mb-2 px-1">
                      <div className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                      <p className="text-[11px] text-amber-400 font-medium">
                        No format selected — only metadata will be returned
                      </p>
                    </div>
                  )}

                  {/* Controls Row */}
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className={cn(
                          "h-8 w-8 rounded-lg grid place-items-center transition-all duration-200",
                          showAdvanced ? "bg-primary/15 text-primary" : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
                        )}
                        title="Advanced settings"
                      >
                        <SlidersHorizontal className="h-3.5 w-3.5" />
                      </button>

                      {activeEndpoint !== "batch" && (
                        <button onClick={() => switchEndpoint("batch")} className="h-8 w-8 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="Batch mode">
                          <Boxes className="h-3.5 w-3.5" />
                        </button>
                      )}

                      <button onClick={() => router.push("/docs")} className="h-8 w-8 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="API Docs">
                        <FileCode className="h-3.5 w-3.5" />
                      </button>

                      {activeEndpoint !== "map" && (
                        <div className="relative">
                          <button
                            onClick={() => setShowFormatSelector(!showFormatSelector)}
                            className="flex items-center gap-1.5 h-8 rounded-lg bg-muted/60 px-2.5 text-[12px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            <span>{formatSummary}</span>
                            <ChevronDown className="h-3 w-3 opacity-60" />
                          </button>
                          <FormatSelector
                            open={showFormatSelector}
                            onClose={() => setShowFormatSelector(false)}
                            selectedFormats={formats}
                            onToggleFormat={toggleFormat}
                            htmlMode={htmlMode}
                            onHtmlModeChange={setHtmlMode}
                            screenshotMode={screenshotMode}
                            onScreenshotModeChange={setScreenshotMode}
                          />
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <button onClick={handleGetCode} className="flex items-center gap-1.5 h-8 rounded-lg px-3 text-[12px] font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted/50 transition-all">
                        <Code className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Get code</span>
                      </button>

                      <button
                        onClick={handleAction}
                        disabled={isDisabled}
                        className="flex items-center gap-1.5 h-8 rounded-lg px-4 text-[12px] font-bold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/15"
                      >
                        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <>{ACTION_LABELS[activeEndpoint]}</>}
                      </button>
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="mt-3 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-sm text-red-400 font-medium animate-scale-in">
                    {error}
                  </div>
                )}
              </section>

              {/* ── Endpoint Options ── */}

              {activeEndpoint === "search" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-2xl border border-border/50 bg-card/60 p-4 space-y-4">
                    <div className="space-y-2">
                      <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Search Engine</label>
                      <div className="flex gap-2">
                        {["duckduckgo", "brave", "google"].map((eng) => (
                          <button key={eng} onClick={() => setEngine(eng)} className={cn("px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all", engine === eng ? "bg-primary text-primary-foreground shadow-md shadow-primary/20" : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground")}>
                            {eng === "duckduckgo" ? "DuckDuckGo" : eng === "brave" ? "Brave" : "Google (BYOK)"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Results: {numResults}</label>
                      <input type="range" min={1} max={10} value={numResults} onChange={(e) => setNumResults(parseInt(e.target.value))} className="w-full" />
                    </div>
                  </div>
                </section>
              )}

              {activeEndpoint === "crawl" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-2xl border border-border/50 bg-card/60 p-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Page Limit</label>
                        <Input type="number" value={maxPages} onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)} min={1} max={10000} className="h-9" />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Link Depth</label>
                        <Input type="number" value={maxDepth} onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)} min={1} max={20} className="h-9" />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Concurrency</label>
                        <Input type="number" value={concurrency} onChange={(e) => setConcurrency(parseInt(e.target.value) || 3)} min={1} max={10} className="h-9" />
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {activeEndpoint === "batch" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-2xl border border-border/50 bg-card/60 p-4">
                    <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Concurrency: {batchConcurrency}</label>
                    <input type="range" min={1} max={20} value={batchConcurrency} onChange={(e) => setBatchConcurrency(parseInt(e.target.value))} className="w-full mt-2" />
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-1 font-medium">
                      <span>1 (gentle)</span><span>20 (aggressive)</span>
                    </div>
                  </div>
                </section>
              )}

              {activeEndpoint === "map" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-2xl border border-border/50 bg-card/60 p-4 space-y-3">
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Filter by keyword</label>
                      <Input placeholder="e.g. blog, pricing, docs" value={mapSearch} onChange={(e) => setMapSearch(e.target.value)} className="h-9" />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold text-primary/70 uppercase tracking-widest">Max URLs</label>
                        <Input type="number" value={mapLimit} onChange={(e) => setMapLimit(parseInt(e.target.value) || 100)} className="h-9" />
                      </div>
                      <div className="flex items-end justify-center pb-1">
                        <button onClick={() => setIncludeSubdomains(!includeSubdomains)} className={cn("px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all", includeSubdomains ? "bg-primary text-primary-foreground" : "bg-muted/60 text-muted-foreground")}>
                          Subdomains {includeSubdomains ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-end justify-center pb-1">
                        <button onClick={() => setUseSitemap(!useSitemap)} className={cn("px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all", useSitemap ? "bg-primary text-primary-foreground" : "bg-muted/60 text-muted-foreground")}>
                          Sitemap {useSitemap ? "On" : "Off"}
                        </button>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* ── Advanced Options ── */}
              {showAdvanced && activeEndpoint !== "map" && (
                <section className="max-w-2xl mx-auto mb-6 animate-scale-in">
                  <div className="rounded-2xl border border-border/40 bg-card/60 p-4 space-y-4">
                    <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                      <SlidersHorizontal className="h-3.5 w-3.5" /> Advanced Options
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center justify-between">
                        <label className="text-[13px] text-foreground">Main content only</label>
                        <button onClick={() => setOnlyMainContent(!onlyMainContent)} className={cn("px-3 py-1 rounded-md text-xs font-semibold transition-all", onlyMainContent ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{onlyMainContent ? "On" : "Off"}</button>
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-[13px] text-foreground">Use Proxy</label>
                        <button onClick={() => setUseProxy(!useProxy)} className={cn("px-3 py-1 rounded-md text-xs font-semibold transition-all", useProxy ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{useProxy ? "On" : "Off"}</button>
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-[13px] text-foreground">Mobile Emulation</label>
                        <button onClick={() => setMobile(!mobile)} className={cn("px-3 py-1 rounded-md text-xs font-semibold transition-all", mobile ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{mobile ? "On" : "Off"}</button>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[13px] text-foreground">Wait after load (ms)</label>
                        <Input type="number" value={waitFor} onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)} placeholder="0" className="h-8" />
                      </div>
                    </div>

                    {mobile && devicePresets.length > 0 && (
                      <select value={mobileDevice} onChange={(e) => setMobileDevice(e.target.value)} className="w-full h-9">
                        <option value="">Default mobile</option>
                        {devicePresets.map((d: any) => (<option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>))}
                      </select>
                    )}

                    {activeEndpoint === "crawl" && (
                      <div className="space-y-3 pt-3 border-t border-border/30">
                        <div className="space-y-1.5"><label className="text-[13px] text-foreground">Include Paths <span className="text-muted-foreground text-xs">(comma-separated)</span></label><Input placeholder="/blog/*, /docs/*" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} className="h-8" /></div>
                        <div className="space-y-1.5"><label className="text-[13px] text-foreground">Exclude Paths <span className="text-muted-foreground text-xs">(comma-separated)</span></label><Input placeholder="/admin/*, /login" value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} className="h-8" /></div>
                      </div>
                    )}

                    <div className="space-y-3 pt-3 border-t border-border/30">
                      <div className="space-y-1.5"><label className="text-[13px] text-foreground">Webhook URL</label><Input placeholder="https://your-server.com/webhook" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} className="h-8" /></div>
                      <div className="space-y-1.5"><label className="text-[13px] text-foreground">Webhook Secret</label><Input placeholder="your-secret-key" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} className="h-8" /></div>
                    </div>

                    {(activeEndpoint === "scrape" || activeEndpoint === "batch") && (
                      <div className="space-y-3 pt-3 border-t border-border/30">
                        <div className="space-y-1.5"><label className="text-[13px] text-foreground">Custom Headers (JSON)</label><textarea className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-xs font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[50px] resize-none" placeholder='{"Authorization": "Bearer ..."}' value={headersText} onChange={(e) => setHeadersText(e.target.value)} /></div>
                        <div className="space-y-1.5"><label className="text-[13px] text-foreground">Cookies (JSON)</label><textarea className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-xs font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[50px] resize-none" placeholder='{"session_id": "abc123"}' value={cookiesText} onChange={(e) => setCookiesText(e.target.value)} /></div>
                      </div>
                    )}

                    <div className="space-y-2 pt-3 border-t border-border/30">
                      <div className="flex items-center justify-between">
                        <label className="text-[13px] font-medium text-foreground flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 text-primary" /> AI Extraction (BYOK)</label>
                        <button onClick={() => setExtractEnabled(!extractEnabled)} className={cn("px-3 py-1 rounded-md text-xs font-semibold transition-all", extractEnabled ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{extractEnabled ? "On" : "Off"}</button>
                      </div>
                      {extractEnabled && <textarea className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[70px] resize-none" placeholder="e.g., Extract the product name, price, and description" value={extractPrompt} onChange={(e) => setExtractPrompt(e.target.value)} />}
                    </div>
                  </div>
                </section>
              )}

              {/* ── Map Results ── */}
              {activeEndpoint === "map" && mapResult && (
                <section className="max-w-2xl mx-auto mb-8 animate-float-in">
                  <div className="rounded-2xl border border-primary/15 bg-card/60 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border/30">
                      <div className="flex items-center gap-2">
                        <Network className="h-4 w-4 text-primary" />
                        <span className="text-sm font-semibold">Discovered URLs</span>
                        <Badge variant="outline" className="border-primary/20 text-primary">{mapResult.total}</Badge>
                      </div>
                      <button onClick={copyMapUrls} className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-[12px] font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all">
                        {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                        Copy All
                      </button>
                    </div>
                    <div className="max-h-[400px] overflow-auto">
                      {mapResult.links?.map((link: any, i: number) => (
                        <div key={i} className="flex items-center justify-between px-4 py-2 hover:bg-muted/30 group transition-colors">
                          <div className="min-w-0 flex-1">
                            <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-primary hover:underline truncate block">{link.url}</a>
                            {link.title && <p className="text-[11px] text-muted-foreground truncate">{link.title}</p>}
                          </div>
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="opacity-0 group-hover:opacity-100 ml-2 transition-opacity"><ExternalLink className="h-3 w-3 text-muted-foreground" /></a>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {/* ── Recent Runs ── */}
              {hasRuns && (
                <section className="max-w-5xl mx-auto pb-8 animate-float-in" style={{ animationDelay: "0.1s" }}>
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold tracking-tight">Recent Runs</h2>
                      <div className="h-px flex-1 bg-gradient-to-r from-border to-transparent min-w-[40px]" />
                    </div>
                    <Link href="/jobs" className="text-[12px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 font-medium">
                      View all <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                    {recentJobs.map((job) => {
                      const jobUrl = getJobUrl(job);
                      const domain = getDomain(jobUrl);
                      const TypeIcon = getTypeIcon(job.type);
                      const { date, time } = job.created_at ? formatDate(job.created_at) : { date: "", time: "" };
                      const jobFormats: string[] = job.config?.formats || [];
                      const isCompleted = job.status === "completed";

                      return (
                        <div key={job.id} className="rounded-xl border border-border/50 bg-card/70 hover:bg-card transition-all duration-200 group overflow-hidden">
                          {/* Accent top bar */}
                          <div className="h-[2px] bg-primary" />

                          <Link href={getJobDetailPath(job)}>
                            <div className="flex items-center justify-between px-4 pt-3 pb-2.5">
                              <div className="flex items-center gap-2 min-w-0">
                                {jobUrl && !jobUrl.includes("URLs") && (
                                  <img src={getFavicon(jobUrl)} alt="" className="h-4 w-4 rounded-sm shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                                )}
                                <span className="text-sm font-semibold truncate">{domain || "No URL"}</span>
                              </div>
                              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors shrink-0" />
                            </div>

                            <div className="px-4 pb-3 space-y-2">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-1.5">
                                  <TypeIcon className="h-3.5 w-3.5 text-primary" />
                                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary">{job.type}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <div className={cn("h-1.5 w-1.5 rounded-full", job.status === "completed" ? "bg-emerald-400" : job.status === "failed" ? "bg-red-400" : job.status === "running" ? "bg-amber-400 animate-pulse" : "bg-muted-foreground")} />
                                  <span className="text-[11px] font-medium text-muted-foreground capitalize">{job.status === "completed" ? "Done" : job.status}</span>
                                </div>
                              </div>

                              <div className="flex items-center gap-1.5 text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                <span className="text-[11px] font-medium">{date} {time}</span>
                              </div>

                              {jobFormats.length > 0 && (
                                <div className="flex flex-wrap gap-1 pt-0.5">
                                  {jobFormats.slice(0, 4).map((fmt: string) => {
                                    const fmtInfo = formatIcons[fmt];
                                    const FmtIcon = fmtInfo?.icon || FileText;
                                    return (
                                      <span key={fmt} className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground uppercase tracking-wider">
                                        <FmtIcon className="h-2.5 w-2.5" /> {fmtInfo?.label || fmt}
                                      </span>
                                    );
                                  })}
                                  {jobFormats.length > 4 && <span className="text-[9px] text-muted-foreground font-medium self-center">+{jobFormats.length - 4}</span>}
                                </div>
                              )}
                            </div>
                          </Link>

                          {isCompleted && (
                            <div className="px-4 pb-3 pt-0">
                              <button onClick={(e) => { e.preventDefault(); handleDownload(job); }} className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg text-[11px] font-bold transition-all border border-primary/20 text-primary hover:bg-primary/10">
                                <Download className="h-3 w-3" /> Download JSON
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {/* Empty state */}
              {!hasRuns && jobsLoaded && (
                <div className="text-center py-4 animate-fade-in">
                  <p className="text-[13px] text-muted-foreground font-medium">Your runs will appear here</p>
                </div>
              )}

            </div>
            <Footer />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}

export default function PlaygroundPage() {
  return (
    <Suspense fallback={null}>
      <PlaygroundContent />
    </Suspense>
  );
}
