"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Footer } from "@/components/layout/footer";
import { FormatSelector } from "@/components/layout/format-selector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Globe,
  Search,
  Map,
  Layers,
  Radar,
  Loader2,
  Settings2,
  LayoutGrid,
  FileCode,
  Code,
  ChevronDown,
  ChevronUp,
  FileText,
  Link2,
  Camera,
  Braces,
  List,
  Image as ImageIcon,
  Sparkles,
  Info,
  ExternalLink,
  Copy,
  Check,
  AlignLeft,
} from "lucide-react";

type Endpoint = "scrape" | "crawl" | "search" | "map" | "batch";

const ENDPOINTS: { id: Endpoint; label: string; icon: any }[] = [
  { id: "scrape", label: "Scrape", icon: Search },
  { id: "search", label: "Search", icon: Radar },
  { id: "map", label: "Map", icon: Map },
  { id: "crawl", label: "Crawl", icon: Globe },
  { id: "batch", label: "Batch", icon: Layers },
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

  // ── Crawl-specific state ──
  const [maxPages, setMaxPages] = useState(100);
  const [maxDepth, setMaxDepth] = useState(3);
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [concurrency, setConcurrency] = useState(3);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  // ── Search-specific state ──
  const [searchQuery, setSearchQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [engine, setEngine] = useState("duckduckgo");

  // ── Batch-specific state ──
  const [batchUrlText, setBatchUrlText] = useState("");
  const [batchConcurrency, setBatchConcurrency] = useState(5);

  // ── Map-specific state ──
  const [mapSearch, setMapSearch] = useState("");
  const [mapLimit, setMapLimit] = useState(100);
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [useSitemap, setUseSitemap] = useState(true);
  const [mapResult, setMapResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  // Auth check
  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  // Load device presets when mobile is enabled
  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then((res) => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

  // Clear error when switching endpoints
  useEffect(() => {
    setError("");
  }, [activeEndpoint]);

  // ── Mode switcher (inline, no navigation) ──
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

  // ── Format summary label ──
  const formatSummary = formats.length === 0
    ? "No format"
    : formats.length === 1
    ? formats[0].charAt(0).toUpperCase() + formats[0].slice(1).replace("_", " ")
    : `${formats.length} formats`;

  // ── Get code ──
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

  // ── Action handlers ──
  const handleAction = async () => {
    setLoading(true);
    setError("");

    try {
      switch (activeEndpoint) {
        case "scrape": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const params: any = {
            url: fullUrl,
            formats,
            only_main_content: onlyMainContent,
            wait_for: waitFor || undefined,
            use_proxy: useProxy || undefined,
            mobile: mobile || undefined,
            mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined,
          };
          if (extractEnabled && extractPrompt) params.extract = { prompt: extractPrompt };
          if (headersText.trim()) { try { params.headers = JSON.parse(headersText); } catch {} }
          if (cookiesText.trim()) { try { params.cookies = JSON.parse(cookiesText); } catch {} }
          const res = await api.scrape(params);
          if (res.job_id) {
            router.push(`/scrape/${res.job_id}`);
          } else if (res.data) {
            router.push("/scrape");
          }
          break;
        }
        case "crawl": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const params: any = { url: fullUrl };
          if (showAdvanced) {
            params.max_pages = maxPages;
            params.max_depth = maxDepth;
            params.concurrency = concurrency;
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
          const params: any = {
            query: searchQuery.trim(),
            num_results: numResults,
            engine,
            formats,
            only_main_content: onlyMainContent,
            use_proxy: useProxy || undefined,
            mobile: mobile || undefined,
            mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined,
            webhook_url: webhookUrl.trim() || undefined,
            webhook_secret: webhookSecret.trim() || undefined,
          };
          if (extractEnabled && extractPrompt.trim()) params.extract = { prompt: extractPrompt.trim() };
          const res = await api.startSearch(params);
          if (res.success) router.push(`/search/${res.job_id}`);
          break;
        }
        case "map": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const res = await api.mapSite({
            url: fullUrl,
            search: mapSearch || undefined,
            limit: mapLimit,
            include_subdomains: includeSubdomains || undefined,
            use_sitemap: useSitemap,
          });
          if (res.success && res.job_id) {
            router.push(`/map/${res.job_id}`);
          } else if (res.success) {
            setMapResult(res);
          } else {
            setError("Map failed");
          }
          break;
        }
        case "batch": {
          const urls = batchUrlText.split("\n").map((l) => l.trim()).filter(Boolean);
          if (urls.length === 0) return;
          const params: any = {
            urls,
            formats,
            concurrency: batchConcurrency,
            only_main_content: onlyMainContent,
            wait_for: waitFor || undefined,
            use_proxy: useProxy || undefined,
            mobile: mobile || undefined,
            mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined,
            webhook_url: webhookUrl.trim() || undefined,
            webhook_secret: webhookSecret.trim() || undefined,
          };
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

  const copyMapUrls = () => {
    if (!mapResult?.links) return;
    navigator.clipboard.writeText(mapResult.links.map((l: any) => l.url).join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background">
          <MobileMenuButton />
          <div className="min-h-screen flex flex-col">
            <div className="flex-1 p-6 lg:p-8 max-w-5xl mx-auto w-full">

              {/* ── Mode Switcher (inline, no navigation) ── */}
              <div className="pt-4 pb-8 animate-float-in">
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-card/80 backdrop-blur-sm p-1">
                    {ENDPOINTS.map((ep) => {
                      const isActive = activeEndpoint === ep.id;
                      return (
                        <button
                          key={ep.id}
                          onClick={() => switchEndpoint(ep.id)}
                          className={cn(
                            "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-medium transition-all duration-200",
                            isActive
                              ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20"
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

              {/* ── URL Input Section ── */}
              <section className="max-w-2xl mx-auto mb-8 animate-float-in" style={{ animationDelay: "0.05s" }}>
                <div className="rounded-xl border border-border/50 bg-card/80 backdrop-blur-sm p-4 shadow-lg shadow-black/5">

                  {/* Input: URL or Search Query or Batch */}
                  {activeEndpoint === "batch" ? (
                    <div className="mb-3">
                      <textarea
                        className="flex min-h-[120px] w-full rounded-lg border border-border/50 bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                        placeholder={"https://example.com\nhttps://another-site.com\nhttps://docs.example.com"}
                        value={batchUrlText}
                        onChange={(e) => setBatchUrlText(e.target.value)}
                      />
                      <p className="text-[11px] text-muted-foreground/50 mt-1.5">
                        {batchUrlCount} URL{batchUrlCount !== 1 ? "s" : ""} (one per line, max 100)
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-0 rounded-lg bg-background border border-border/50 px-3 h-11 mb-3">
                      {activeEndpoint !== "search" && (
                        <span className="text-sm text-muted-foreground/50 shrink-0 select-none">https://</span>
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
                          "flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/30",
                          activeEndpoint !== "search" && "ml-1"
                        )}
                      />
                    </div>
                  )}

                  {/* No format warning */}
                  {formats.length === 0 && activeEndpoint !== "map" && (
                    <p className="text-[11px] text-amber-400/70 mb-2 flex items-center gap-1">
                      <span className="text-amber-400">&#9888;</span>
                      No format selected - only metadata will be returned
                    </p>
                  )}

                  {/* Controls Row */}
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {/* Settings icon → advanced */}
                      <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className={cn(
                          "h-8 w-8 rounded-md grid place-items-center transition-colors",
                          showAdvanced
                            ? "bg-primary/10 text-primary"
                            : "bg-muted/50 text-muted-foreground/50 hover:text-foreground hover:bg-muted"
                        )}
                        title="Advanced settings"
                      >
                        <Settings2 className="h-3.5 w-3.5" />
                      </button>

                      {/* Grid icon → batch shortcut */}
                      {activeEndpoint !== "batch" && (
                        <button
                          onClick={() => switchEndpoint("batch")}
                          className="h-8 w-8 rounded-md bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                          title="Batch scrape"
                        >
                          <LayoutGrid className="h-3.5 w-3.5" />
                        </button>
                      )}

                      {/* File icon → docs */}
                      <button
                        onClick={() => router.push("/docs")}
                        className="h-8 w-8 rounded-md bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                        title="API Docs"
                      >
                        <FileCode className="h-3.5 w-3.5" />
                      </button>

                      {/* Format Dropdown (not shown for map) */}
                      {activeEndpoint !== "map" && (
                        <div className="relative">
                          <button
                            onClick={() => setShowFormatSelector(!showFormatSelector)}
                            className="flex items-center gap-1.5 h-8 rounded-md bg-muted/50 px-2.5 text-[12px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            <span>Format: {formatSummary}</span>
                            <ChevronDown className="h-3 w-3" />
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
                      {/* Get Code */}
                      <button
                        onClick={handleGetCode}
                        className="flex items-center gap-1.5 h-8 rounded-md px-3 text-[12px] font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted transition-colors"
                      >
                        <Code className="h-3.5 w-3.5" />
                        Get code
                      </button>

                      {/* Action Button */}
                      <button
                        onClick={handleAction}
                        disabled={isDisabled}
                        className="flex items-center gap-1.5 h-8 rounded-md px-4 text-[12px] font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm shadow-primary/20"
                      >
                        {loading ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <>{ACTION_LABELS[activeEndpoint]}</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <div className="mt-3 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-2.5 text-sm text-red-400">
                    {error}
                  </div>
                )}
              </section>

              {/* ── Endpoint-specific options (below URL bar) ── */}

              {/* Search engine + results count */}
              {activeEndpoint === "search" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-xl border border-border/40 bg-card/50 p-4 space-y-4">
                    <div className="space-y-2">
                      <label className="text-[12px] font-medium text-muted-foreground/70 uppercase tracking-wider">Search Engine</label>
                      <div className="flex gap-2">
                        {["duckduckgo", "brave", "google"].map((eng) => (
                          <button
                            key={eng}
                            onClick={() => setEngine(eng)}
                            className={cn(
                              "px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors",
                              engine === eng
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                            )}
                          >
                            {eng === "duckduckgo" ? "DuckDuckGo" : eng === "brave" ? "Brave" : "Google (BYOK)"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[12px] font-medium text-muted-foreground/70 uppercase tracking-wider">
                        Results to scrape: {numResults}
                      </label>
                      <input
                        type="range"
                        min={1}
                        max={10}
                        value={numResults}
                        onChange={(e) => setNumResults(parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  </div>
                </section>
              )}

              {/* Crawl quick options */}
              {activeEndpoint === "crawl" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-xl border border-border/40 bg-card/50 p-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">Page Limit</label>
                        <Input
                          type="number"
                          value={maxPages}
                          onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)}
                          min={1}
                          max={10000}
                          className="h-9"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">Link Depth</label>
                        <Input
                          type="number"
                          value={maxDepth}
                          onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)}
                          min={1}
                          max={20}
                          className="h-9"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">Concurrency</label>
                        <Input
                          type="number"
                          value={concurrency}
                          onChange={(e) => setConcurrency(parseInt(e.target.value) || 3)}
                          min={1}
                          max={10}
                          className="h-9"
                        />
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* Batch concurrency */}
              {activeEndpoint === "batch" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-xl border border-border/40 bg-card/50 p-4">
                    <label className="text-[12px] font-medium text-muted-foreground/70 uppercase tracking-wider">
                      Concurrency: {batchConcurrency}
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={20}
                      value={batchConcurrency}
                      onChange={(e) => setBatchConcurrency(parseInt(e.target.value))}
                      className="w-full mt-2"
                    />
                    <div className="flex justify-between text-[10px] text-muted-foreground/40 mt-1">
                      <span>1 (gentle)</span>
                      <span>20 (aggressive)</span>
                    </div>
                  </div>
                </section>
              )}

              {/* Map options */}
              {activeEndpoint === "map" && (
                <section className="max-w-2xl mx-auto mb-6 animate-float-in" style={{ animationDelay: "0.08s" }}>
                  <div className="rounded-xl border border-border/40 bg-card/50 p-4 space-y-3">
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">Filter by keyword</label>
                      <Input
                        placeholder="e.g. blog, pricing, docs"
                        value={mapSearch}
                        onChange={(e) => setMapSearch(e.target.value)}
                        className="h-9"
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">Max URLs</label>
                        <Input
                          type="number"
                          value={mapLimit}
                          onChange={(e) => setMapLimit(parseInt(e.target.value) || 100)}
                          className="h-9"
                        />
                      </div>
                      <div className="flex items-end justify-center pb-1">
                        <button
                          onClick={() => setIncludeSubdomains(!includeSubdomains)}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors",
                            includeSubdomains ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground"
                          )}
                        >
                          Subdomains {includeSubdomains ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-end justify-center pb-1">
                        <button
                          onClick={() => setUseSitemap(!useSitemap)}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors",
                            useSitemap ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground"
                          )}
                        >
                          Sitemap {useSitemap ? "On" : "Off"}
                        </button>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* ── Advanced Options (shared, collapsible) ── */}
              {showAdvanced && activeEndpoint !== "map" && (
                <section className="max-w-2xl mx-auto mb-6 animate-scale-in">
                  <div className="rounded-xl border border-border/40 bg-card/50 p-4 space-y-4">
                    <h3 className="text-[12px] font-semibold text-muted-foreground/70 uppercase tracking-wider flex items-center gap-2">
                      <Settings2 className="h-3.5 w-3.5" />
                      Advanced Options
                    </h3>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center justify-between">
                        <label className="text-[13px]">Main content only</label>
                        <button
                          onClick={() => setOnlyMainContent(!onlyMainContent)}
                          className={cn("px-3 py-1 rounded-md text-xs font-medium transition-colors", onlyMainContent ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}
                        >
                          {onlyMainContent ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-[13px]">Use Proxy</label>
                        <button
                          onClick={() => setUseProxy(!useProxy)}
                          className={cn("px-3 py-1 rounded-md text-xs font-medium transition-colors", useProxy ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}
                        >
                          {useProxy ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-[13px]">Mobile Emulation</label>
                        <button
                          onClick={() => setMobile(!mobile)}
                          className={cn("px-3 py-1 rounded-md text-xs font-medium transition-colors", mobile ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}
                        >
                          {mobile ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[13px]">Wait after load (ms)</label>
                        <Input type="number" value={waitFor} onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)} placeholder="0" className="h-8" />
                      </div>
                    </div>

                    {mobile && devicePresets.length > 0 && (
                      <select value={mobileDevice} onChange={(e) => setMobileDevice(e.target.value)} className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm">
                        <option value="">Default mobile</option>
                        {devicePresets.map((d: any) => (
                          <option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>
                        ))}
                      </select>
                    )}

                    {/* Crawl-specific advanced */}
                    {activeEndpoint === "crawl" && (
                      <div className="space-y-3 pt-3 border-t border-border/30">
                        <div className="space-y-1.5">
                          <label className="text-[13px]">Include Paths <span className="text-muted-foreground/50 text-xs">(comma-separated)</span></label>
                          <Input placeholder="/blog/*, /docs/*" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} className="h-8" />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[13px]">Exclude Paths <span className="text-muted-foreground/50 text-xs">(comma-separated)</span></label>
                          <Input placeholder="/admin/*, /login" value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} className="h-8" />
                        </div>
                      </div>
                    )}

                    {/* Webhook */}
                    <div className="space-y-3 pt-3 border-t border-border/30">
                      <div className="space-y-1.5">
                        <label className="text-[13px]">Webhook URL</label>
                        <Input placeholder="https://your-server.com/webhook" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} className="h-8" />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[13px]">Webhook Secret</label>
                        <Input placeholder="your-secret-key" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} className="h-8" />
                      </div>
                    </div>

                    {/* Custom Headers/Cookies (scrape/batch) */}
                    {(activeEndpoint === "scrape" || activeEndpoint === "batch") && (
                      <div className="space-y-3 pt-3 border-t border-border/30">
                        <div className="space-y-1.5">
                          <label className="text-[13px]">Custom Headers (JSON)</label>
                          <textarea
                            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono placeholder:text-muted-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[50px] resize-none"
                            placeholder='{"Authorization": "Bearer ..."}'
                            value={headersText}
                            onChange={(e) => setHeadersText(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[13px]">Cookies (JSON)</label>
                          <textarea
                            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono placeholder:text-muted-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[50px] resize-none"
                            placeholder='{"session_id": "abc123"}'
                            value={cookiesText}
                            onChange={(e) => setCookiesText(e.target.value)}
                          />
                        </div>
                      </div>
                    )}

                    {/* AI Extraction */}
                    <div className="space-y-2 pt-3 border-t border-border/30">
                      <div className="flex items-center justify-between">
                        <label className="text-[13px] font-medium flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5" />
                          AI Extraction (BYOK)
                        </label>
                        <button
                          onClick={() => setExtractEnabled(!extractEnabled)}
                          className={cn("px-3 py-1 rounded-md text-xs font-medium transition-colors", extractEnabled ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}
                        >
                          {extractEnabled ? "On" : "Off"}
                        </button>
                      </div>
                      {extractEnabled && (
                        <textarea
                          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[70px] resize-none"
                          placeholder="e.g., Extract the product name, price, and description"
                          value={extractPrompt}
                          onChange={(e) => setExtractPrompt(e.target.value)}
                        />
                      )}
                    </div>
                  </div>
                </section>
              )}

              {/* ── Map Results (inline) ── */}
              {activeEndpoint === "map" && mapResult && (
                <section className="max-w-2xl mx-auto mb-8 animate-float-in">
                  <div className="rounded-xl border border-border/40 bg-card/50 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border/30">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold">Discovered URLs</span>
                        <Badge variant="outline">{mapResult.total}</Badge>
                      </div>
                      <button
                        onClick={copyMapUrls}
                        className="flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      >
                        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                        Copy All
                      </button>
                    </div>
                    <div className="max-h-[400px] overflow-auto">
                      {mapResult.links?.map((link: any, i: number) => (
                        <div key={i} className="flex items-center justify-between px-4 py-2 hover:bg-muted/30 group">
                          <div className="min-w-0 flex-1">
                            <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-primary hover:underline truncate block">
                              {link.url}
                            </a>
                            {link.title && <p className="text-[11px] text-muted-foreground/50 truncate">{link.title}</p>}
                          </div>
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="opacity-0 group-hover:opacity-100 ml-2">
                            <ExternalLink className="h-3 w-3 text-muted-foreground/40" />
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
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
