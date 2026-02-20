"use client";

import { useState, useEffect, useCallback, useRef, memo, Suspense } from "react";
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
  ChevronUp,
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
  X,
  CheckCircle2,
  XCircle,
  Crosshair,
  Satellite,
  Network,
  Bug,
  Boxes,
  RefreshCw,
  Square,
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

// ── Inline Result Card ───────────────────────────────────────

type ResultTab = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract" | "json";

const InlineResultCard = memo(function InlineResultCard({
  page,
  index,
  jobId,
}: {
  page: any;
  index: number;
  jobId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<ResultTab>("markdown");
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const hasMarkdown = !!page.markdown;
  const hasHtml = !!page.html;
  const hasScreenshot = !!page.id;
  const hasLinks = page.links?.length > 0 || page.links_detail;
  const hasStructured = page.structured_data && Object.keys(page.structured_data).length > 0;
  const hasHeadings = page.headings?.length > 0;
  const hasImages = page.images?.length > 0;
  const hasExtract = !!page.extract;

  const tabs: { id: ResultTab; label: string; icon: any; available: boolean }[] = [
    { id: "markdown", label: "Markdown", icon: FileText, available: hasMarkdown },
    { id: "html", label: "HTML", icon: Code, available: hasHtml },
    { id: "screenshot", label: "Screenshot", icon: Camera, available: hasScreenshot },
    { id: "links", label: "Links", icon: Link2, available: hasLinks },
    { id: "structured", label: "Structured", icon: Braces, available: hasStructured },
    { id: "headings", label: "Headings", icon: List, available: hasHeadings },
    { id: "images", label: "Images", icon: ImageIcon, available: hasImages },
    { id: "extract", label: "AI Extract", icon: Sparkles, available: hasExtract },
    { id: "json", label: "JSON", icon: FileCode, available: true },
  ];

  const availableTabs = tabs.filter((t) => t.available);

  useEffect(() => {
    if (!availableTabs.find((t) => t.id === activeTab)) {
      setActiveTab(availableTabs[0]?.id || "json");
    }
  }, []);

  const loadScreenshot = useCallback(async () => {
    if (screenshotData || screenshotLoading || !page.id) return;
    setScreenshotLoading(true);
    try {
      const detail = await api.getJobResultDetail(jobId, page.id);
      setScreenshotData(detail.screenshot || null);
    } catch {
      setScreenshotData(null);
    } finally {
      setScreenshotLoading(false);
    }
  }, [jobId, page.id, screenshotData, screenshotLoading]);

  const copyContent = () => {
    let text = "";
    switch (activeTab) {
      case "markdown": text = page.markdown || ""; break;
      case "html": text = page.html || ""; break;
      case "links": text = (page.links || []).join("\n"); break;
      case "json": text = JSON.stringify(page, null, 2); break;
      default: text = JSON.stringify(page[activeTab], null, 2); break;
    }
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const wordCount = page.metadata?.word_count || 0;
  const statusCode = page.metadata?.status_code;

  return (
    <div className="rounded-xl border border-border/50 bg-card/60 overflow-hidden transition-all duration-200">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-3 w-full px-4 py-3 hover:bg-muted/30 transition-colors text-left"
      >
        <span className="text-[12px] text-muted-foreground font-mono w-6 shrink-0 text-right tabular-nums">
          {index + 1}
        </span>
        {page.url && (
          <img
            src={`https://www.google.com/s2/favicons?domain=${getDomain(page.url)}&sz=32`}
            alt=""
            className="h-4 w-4 rounded-sm shrink-0"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-medium truncate">{page.url || "Unknown URL"}</p>
          {page.metadata?.title && (
            <p className="text-[12px] text-muted-foreground truncate mt-0.5">{page.metadata.title}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {wordCount > 0 && (
            <span className="text-[11px] font-medium text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md">
              {wordCount.toLocaleString()} words
            </span>
          )}
          {statusCode && (
            <span className={cn(
              "text-[11px] font-bold px-2 py-0.5 rounded-md",
              statusCode >= 200 && statusCode < 400
                ? "bg-emerald-500/10 text-emerald-400"
                : "bg-red-500/10 text-red-400"
            )}>
              {statusCode}
            </span>
          )}
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border/40">
          {/* Tab bar */}
          <div className="flex items-center gap-1 px-3 py-2 border-b border-border/30 bg-muted/20 overflow-x-auto">
            {availableTabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    if (tab.id === "screenshot" && !screenshotData && !screenshotLoading) loadScreenshot();
                  }}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all whitespace-nowrap",
                    activeTab === tab.id
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
            <div className="flex-1" />
            {activeTab !== "screenshot" && (
              <button onClick={copyContent} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-all">
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>

          {/* Tab content */}
          <div className="p-4">
            {activeTab === "markdown" && hasMarkdown && (
              <pre className="max-h-80 overflow-auto text-[13px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-4 leading-relaxed">
                {page.markdown}
              </pre>
            )}

            {activeTab === "html" && hasHtml && (
              <pre className="max-h-80 overflow-auto text-[12px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-4">
                {page.html}
              </pre>
            )}

            {activeTab === "screenshot" && hasScreenshot && (
              <div className="flex justify-center">
                {screenshotData ? (
                  <img
                    src={`data:image/jpeg;base64,${screenshotData}`}
                    alt={`Screenshot of ${page.url}`}
                    className="max-w-full rounded-lg border border-border/50 shadow-lg"
                    style={{ maxHeight: "500px" }}
                  />
                ) : screenshotLoading ? (
                  <div className="flex items-center gap-2 py-8 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm font-medium">Loading screenshot...</span>
                  </div>
                ) : (
                  <button
                    onClick={loadScreenshot}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
                  >
                    <Camera className="h-4 w-4" />
                    Load Screenshot
                  </button>
                )}
              </div>
            )}

            {activeTab === "links" && hasLinks && (
              <div className="space-y-2 max-h-80 overflow-auto">
                {page.links_detail ? (
                  <>
                    <div className="flex gap-4 text-[13px] pb-2 border-b border-border/30">
                      <span className="font-medium">{page.links_detail.total} total</span>
                      {page.links_detail.internal && <span className="text-blue-400">{page.links_detail.internal.count} internal</span>}
                      {page.links_detail.external && <span className="text-amber-400">{page.links_detail.external.count} external</span>}
                    </div>
                    {page.links_detail.internal?.links?.map((link: any, i: number) => (
                      <a key={`i-${i}`} href={link.url} target="_blank" rel="noopener noreferrer" className="block text-[12px] text-primary hover:underline truncate">{link.url}</a>
                    ))}
                    {page.links_detail.external?.links?.map((link: any, i: number) => (
                      <a key={`e-${i}`} href={link.url} target="_blank" rel="noopener noreferrer" className="block text-[12px] text-amber-400/80 hover:underline truncate">{link.url}</a>
                    ))}
                  </>
                ) : page.links?.map((link: string, i: number) => (
                  <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-[12px] text-primary hover:underline truncate">{link}</a>
                ))}
              </div>
            )}

            {activeTab === "structured" && hasStructured && (
              <pre className="max-h-80 overflow-auto text-[12px] font-mono bg-muted/30 rounded-lg p-4">
                {JSON.stringify(page.structured_data, null, 2)}
              </pre>
            )}

            {activeTab === "headings" && hasHeadings && (
              <div className="space-y-1 max-h-80 overflow-auto">
                {page.headings.map((h: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-[13px]" style={{ paddingLeft: `${(h.level - 1) * 16}px` }}>
                    <span className="text-[10px] font-bold text-primary/60 bg-primary/10 px-1.5 py-0.5 rounded shrink-0">H{h.level}</span>
                    <span className={h.level === 1 ? "font-semibold" : "text-muted-foreground"}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-80 overflow-auto">
                {page.images.map((img: any, i: number) => (
                  <div key={i} className="border border-border/40 rounded-lg overflow-hidden bg-muted/20">
                    <div className="aspect-video bg-muted/30 flex items-center justify-center">
                      <img src={img.src} alt={img.alt || ""} className="max-w-full max-h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                    </div>
                    <div className="p-2">
                      <p className="text-[11px] text-muted-foreground truncate">{img.src.split("/").pop()}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "extract" && hasExtract && (
              <pre className="max-h-80 overflow-auto text-[13px] whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-4">
                {JSON.stringify(page.extract, null, 2)}
              </pre>
            )}

            {activeTab === "json" && (
              <pre className="max-h-80 overflow-auto text-[12px] font-mono bg-muted/30 rounded-lg p-4">
                {JSON.stringify(page, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

// ── Main Component ───────────────────────────────────────────

function PlaygroundContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // State-based endpoint switching — NO router navigation for instant feel
  const [activeEndpoint, setActiveEndpoint] = useState<Endpoint>(() => {
    const ep = searchParams.get("endpoint") as Endpoint;
    return ENDPOINTS.find((e) => e.id === ep) ? ep : "scrape";
  });

  // Sync if navigated via sidebar Link
  useEffect(() => {
    const ep = searchParams.get("endpoint") as Endpoint;
    if (ep && ENDPOINTS.find((e) => e.id === ep) && ep !== activeEndpoint) {
      setActiveEndpoint(ep);
    }
  }, [searchParams]);

  const switchEndpoint = useCallback((ep: Endpoint) => {
    setActiveEndpoint(ep);
    setError("");
    // Update URL silently without triggering Next.js navigation
    window.history.replaceState(null, "", `/playground?endpoint=${ep}`);
  }, []);

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
  const [maxPages, setMaxPages] = useState(10);
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

  // ── Active job tracking (inline progress) ──
  const [activeJob, setActiveJob] = useState<{
    id: string;
    type: Endpoint;
    status: string;
    target: string;
    total: number;
    completed: number;
    data?: any[];
    error?: string;
  } | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!api.getToken()) { router.push("/auth/login"); return; }
    api.getUsageHistory({ per_page: 9 })
      .then((res) => { setRecentJobs(res.jobs || []); setJobsLoaded(true); })
      .catch(() => setJobsLoaded(true));
  }, [router]);

  // ── Fetch job status (unified for all types) ──
  const fetchJobStatus = useCallback(async (jobId: string, jobType: Endpoint) => {
    try {
      let res: any;
      switch (jobType) {
        case "scrape": res = await api.getScrapeStatus(jobId); break;
        case "crawl": res = await api.getCrawlStatus(jobId, 1, 20); break;
        case "search": res = await api.getSearchStatus(jobId); break;
        case "map": res = await api.getMapStatus(jobId); break;
        case "batch": res = await api.getBatchStatus(jobId); break;
      }
      setActiveJob((prev) => prev && prev.id === jobId ? {
        ...prev,
        status: res.status || prev.status,
        completed: res.completed_pages || res.completed_results || res.completed_urls || prev.completed,
        data: res.data || res.links || prev.data,
        error: res.error,
      } : prev);
      return res.status;
    } catch { return null; }
  }, []);

  // ── SSE / polling for active job ──
  useEffect(() => {
    if (!activeJob || ["completed", "failed", "cancelled"].includes(activeJob.status)) return;

    const jobId = activeJob.id;
    const jobType = activeJob.type;

    // Try SSE first
    try {
      const sseUrl = api.getSSEUrl(jobId);
      const es = new EventSource(sseUrl);
      sseRef.current = es;

      es.onmessage = async () => {
        const status = await fetchJobStatus(jobId, jobType);
        if (status && ["completed", "failed", "cancelled"].includes(status)) {
          es.close();
          sseRef.current = null;
          // Refresh recent runs
          api.getUsageHistory({ per_page: 9 }).then((r) => setRecentJobs(r.jobs || [])).catch(() => {});
        }
      };

      es.onerror = () => {
        es.close();
        sseRef.current = null;
        // Fallback to polling
        const interval = setInterval(async () => {
          const status = await fetchJobStatus(jobId, jobType);
          if (status && ["completed", "failed", "cancelled"].includes(status)) {
            clearInterval(interval);
            pollRef.current = null;
            api.getUsageHistory({ per_page: 9 }).then((r) => setRecentJobs(r.jobs || [])).catch(() => {});
          }
        }, 2000);
        pollRef.current = interval;
      };
    } catch {
      // SSE not available, use polling
      const interval = setInterval(async () => {
        const status = await fetchJobStatus(jobId, jobType);
        if (status && ["completed", "failed", "cancelled"].includes(status)) {
          clearInterval(interval);
          pollRef.current = null;
          api.getUsageHistory({ per_page: 9 }).then((r) => setRecentJobs(r.jobs || [])).catch(() => {});
        }
      }, 2000);
      pollRef.current = interval;
    }

    // Also do an immediate fetch
    fetchJobStatus(jobId, jobType);

    return () => {
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [activeJob?.id, activeJob?.status, fetchJobStatus]);

  const dismissJob = useCallback(() => {
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setActiveJob(null);
  }, []);

  const handleDownloadActiveJob = useCallback(() => {
    if (!activeJob) return;
    handleDownload({ id: activeJob.id, type: activeJob.type });
  }, [activeJob]);

  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then((res) => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

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
          if (res.job_id) setActiveJob({ id: res.job_id, type: "scrape", status: "running", target: fullUrl, total: 1, completed: 0 });
          break;
        }
        case "crawl": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const params: any = { url: fullUrl, max_pages: maxPages, max_depth: maxDepth, concurrency };
          if (showAdvanced) {
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
          if (res.success && res.job_id) setActiveJob({ id: res.job_id, type: "crawl", status: "running", target: fullUrl, total: maxPages, completed: 0 });
          break;
        }
        case "search": {
          if (!searchQuery.trim()) return;
          const params: any = { query: searchQuery.trim(), num_results: numResults, engine, formats, only_main_content: onlyMainContent, use_proxy: useProxy || undefined, mobile: mobile || undefined, mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined, webhook_url: webhookUrl.trim() || undefined, webhook_secret: webhookSecret.trim() || undefined };
          if (extractEnabled && extractPrompt.trim()) params.extract = { prompt: extractPrompt.trim() };
          const res = await api.startSearch(params);
          if (res.success && res.job_id) setActiveJob({ id: res.job_id, type: "search", status: "running", target: searchQuery.trim(), total: numResults, completed: 0 });
          break;
        }
        case "map": {
          if (!url.trim()) return;
          const fullUrl = url.startsWith("http") ? url : `https://${url}`;
          const res = await api.mapSite({ url: fullUrl, search: mapSearch || undefined, limit: mapLimit, include_subdomains: includeSubdomains || undefined, use_sitemap: useSitemap });
          if (res.success && res.job_id) setActiveJob({ id: res.job_id, type: "map", status: "running", target: fullUrl, total: mapLimit, completed: 0 });
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
          if (res.success && res.job_id) setActiveJob({ id: res.job_id, type: "batch", status: "running", target: `${urls.length} URLs`, total: urls.length, completed: 0 });
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
              "flex-1 flex flex-col w-full max-w-5xl mx-auto px-6 lg:px-8",
              !hasRuns && jobsLoaded ? "justify-center" : "pt-8"
            )}>

              {/* ── Mode Switcher ── */}
              <div className={cn(hasRuns ? "pb-8" : "pb-10")}>
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-1 rounded-2xl border border-border/60 bg-card/70 backdrop-blur-md p-1.5 shadow-lg shadow-black/10">
                    {ENDPOINTS.map((ep) => {
                      const isActive = activeEndpoint === ep.id;
                      return (
                        <button
                          key={ep.id}
                          onClick={() => switchEndpoint(ep.id)}
                          className={cn(
                            "flex items-center gap-2 rounded-xl px-5 py-2.5 text-[15px] font-semibold transition-all duration-200",
                            isActive
                              ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                          )}
                        >
                          <ep.icon className="h-[18px] w-[18px]" />
                          <span>{ep.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* ── URL Input Section ── */}
              <section className={cn(
                "max-w-2xl w-full mx-auto relative z-20",
                hasRuns ? "mb-10" : "mb-6"
              )}>
                <div className="rounded-2xl border border-primary/15 bg-card/80 backdrop-blur-sm p-5 shadow-xl shadow-primary/5">

                  {/* Input */}
                  {activeEndpoint === "batch" ? (
                    <div className="mb-4">
                      <textarea
                        className="flex min-h-[140px] w-full rounded-xl border border-border/50 bg-background px-5 py-4 text-base font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:border-primary/30 resize-none transition-all"
                        placeholder={"https://example.com\nhttps://another-site.com\nhttps://docs.example.com"}
                        value={batchUrlText}
                        onChange={(e) => setBatchUrlText(e.target.value)}
                      />
                      <p className="text-[13px] text-muted-foreground mt-2 font-medium">
                        {batchUrlCount} URL{batchUrlCount !== 1 ? "s" : ""} (one per line, max 100)
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-0 rounded-xl bg-background border border-border/50 px-5 h-14 mb-4 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/25 transition-all">
                      {activeEndpoint !== "search" ? (
                        <span className="text-base text-muted-foreground shrink-0 select-none font-mono">https://</span>
                      ) : (
                        <Search className="h-5 w-5 text-muted-foreground shrink-0 mr-2" />
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
                          "flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground/50",
                          activeEndpoint !== "search" && "ml-1"
                        )}
                      />
                      <ActiveIcon className="h-5 w-5 shrink-0 ml-2 text-primary/40" />
                    </div>
                  )}

                  {/* No format warning */}
                  {formats.length === 0 && activeEndpoint !== "map" && (
                    <div className="flex items-center gap-2 mb-3 px-1">
                      <div className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                      <p className="text-[13px] text-amber-400 font-medium">
                        No format selected — only metadata will be returned
                      </p>
                    </div>
                  )}

                  {/* Controls Row */}
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className={cn(
                          "h-10 w-10 rounded-lg grid place-items-center transition-all duration-200",
                          showAdvanced ? "bg-primary/15 text-primary" : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
                        )}
                        title="Settings"
                      >
                        <SlidersHorizontal className="h-[18px] w-[18px]" />
                      </button>

                      {activeEndpoint !== "batch" && (
                        <button onClick={() => switchEndpoint("batch")} className="h-10 w-10 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="Batch mode">
                          <Boxes className="h-[18px] w-[18px]" />
                        </button>
                      )}

                      <button onClick={() => router.push("/docs")} className="h-10 w-10 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="API Docs">
                        <FileCode className="h-[18px] w-[18px]" />
                      </button>

                      {activeEndpoint !== "map" && (
                        <div className="relative">
                          <button
                            onClick={() => setShowFormatSelector(!showFormatSelector)}
                            className="flex items-center gap-2 h-10 rounded-lg bg-muted/60 px-3.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
                          >
                            <FileText className="h-[18px] w-[18px]" />
                            <span>{formatSummary}</span>
                            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
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

                    <div className="flex items-center gap-3">
                      <button onClick={handleGetCode} className="flex items-center gap-2 h-10 rounded-lg px-4 text-sm font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted/50 transition-all">
                        <Code className="h-[18px] w-[18px]" />
                        <span className="hidden sm:inline">Get code</span>
                      </button>

                      <button
                        onClick={handleAction}
                        disabled={isDisabled}
                        className="flex items-center gap-2 h-11 rounded-lg px-6 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/15"
                      >
                        {loading ? <Loader2 className="h-[18px] w-[18px] animate-spin" /> : <>{ACTION_LABELS[activeEndpoint]}</>}
                      </button>
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="mt-4 rounded-xl bg-red-500/10 border border-red-500/20 px-5 py-3 text-base text-red-400 font-medium animate-scale-in">
                    {error}
                  </div>
                )}
              </section>

              {/* ── Advanced Settings (ALL endpoint settings consolidated here) ── */}
              {showAdvanced && (
                <section className="max-w-2xl mx-auto w-full mb-8 animate-scale-in">
                  <div className="rounded-2xl border border-border/40 bg-card/60 p-5 space-y-5">
                    <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                      <SlidersHorizontal className="h-[18px] w-[18px]" /> Settings
                    </h3>

                    {/* Search-specific */}
                    {activeEndpoint === "search" && (
                      <div className="space-y-4 pb-4 border-b border-border/30">
                        <div className="space-y-2">
                          <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Search Engine</label>
                          <div className="flex gap-2">
                            {["duckduckgo", "brave", "google"].map((eng) => (
                              <button key={eng} onClick={() => setEngine(eng)} className={cn("px-4 py-2 rounded-lg text-sm font-semibold transition-all", engine === eng ? "bg-primary text-primary-foreground shadow-md shadow-primary/20" : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground")}>
                                {eng === "duckduckgo" ? "DuckDuckGo" : eng === "brave" ? "Brave" : "Google (BYOK)"}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Results: {numResults}</label>
                          <input type="range" min={1} max={10} value={numResults} onChange={(e) => setNumResults(parseInt(e.target.value))} className="w-full" />
                        </div>
                      </div>
                    )}

                    {/* Crawl-specific */}
                    {activeEndpoint === "crawl" && (
                      <div className="space-y-4 pb-4 border-b border-border/30">
                        <div className="grid grid-cols-3 gap-4">
                          <div className="space-y-2">
                            <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Page Limit</label>
                            <Input type="number" value={maxPages} onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)} min={1} max={10000} className="h-11" />
                          </div>
                          <div className="space-y-2">
                            <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Link Depth</label>
                            <Input type="number" value={maxDepth} onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)} min={1} max={20} className="h-11" />
                          </div>
                          <div className="space-y-2">
                            <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Concurrency</label>
                            <Input type="number" value={concurrency} onChange={(e) => setConcurrency(parseInt(e.target.value) || 3)} min={1} max={10} className="h-11" />
                          </div>
                        </div>
                        <div className="space-y-3">
                          <div className="space-y-2">
                            <label className="text-[15px] text-foreground">Include Paths <span className="text-muted-foreground text-sm">(comma-separated)</span></label>
                            <Input placeholder="/blog/*, /docs/*" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} className="h-11" />
                          </div>
                          <div className="space-y-2">
                            <label className="text-[15px] text-foreground">Exclude Paths <span className="text-muted-foreground text-sm">(comma-separated)</span></label>
                            <Input placeholder="/admin/*, /login" value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} className="h-11" />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Batch-specific */}
                    {activeEndpoint === "batch" && (
                      <div className="space-y-2 pb-4 border-b border-border/30">
                        <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Concurrency: {batchConcurrency}</label>
                        <input type="range" min={1} max={20} value={batchConcurrency} onChange={(e) => setBatchConcurrency(parseInt(e.target.value))} className="w-full mt-2" />
                        <div className="flex justify-between text-[13px] text-muted-foreground mt-1 font-medium">
                          <span>1 (gentle)</span><span>20 (aggressive)</span>
                        </div>
                      </div>
                    )}

                    {/* Map-specific */}
                    {activeEndpoint === "map" && (
                      <div className="space-y-4 pb-4 border-b border-border/30">
                        <div className="space-y-2">
                          <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Filter by keyword</label>
                          <Input placeholder="e.g. blog, pricing, docs" value={mapSearch} onChange={(e) => setMapSearch(e.target.value)} className="h-11" />
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="space-y-2">
                            <label className="text-[13px] font-semibold text-primary/70 uppercase tracking-widest">Max URLs</label>
                            <Input type="number" value={mapLimit} onChange={(e) => setMapLimit(parseInt(e.target.value) || 100)} className="h-11" />
                          </div>
                          <div className="flex items-end justify-center pb-1">
                            <button onClick={() => setIncludeSubdomains(!includeSubdomains)} className={cn("px-4 py-2 rounded-lg text-sm font-semibold transition-all", includeSubdomains ? "bg-primary text-primary-foreground" : "bg-muted/60 text-muted-foreground")}>
                              Subdomains {includeSubdomains ? "On" : "Off"}
                            </button>
                          </div>
                          <div className="flex items-end justify-center pb-1">
                            <button onClick={() => setUseSitemap(!useSitemap)} className={cn("px-4 py-2 rounded-lg text-sm font-semibold transition-all", useSitemap ? "bg-primary text-primary-foreground" : "bg-muted/60 text-muted-foreground")}>
                              Sitemap {useSitemap ? "On" : "Off"}
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Common settings (not for map) */}
                    {activeEndpoint !== "map" && (
                      <>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex items-center justify-between">
                            <label className="text-[15px] text-foreground">Main content only</label>
                            <button onClick={() => setOnlyMainContent(!onlyMainContent)} className={cn("px-4 py-1.5 rounded-md text-sm font-semibold transition-all", onlyMainContent ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{onlyMainContent ? "On" : "Off"}</button>
                          </div>
                          <div className="flex items-center justify-between">
                            <label className="text-[15px] text-foreground">Use Proxy</label>
                            <button onClick={() => setUseProxy(!useProxy)} className={cn("px-4 py-1.5 rounded-md text-sm font-semibold transition-all", useProxy ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{useProxy ? "On" : "Off"}</button>
                          </div>
                          <div className="flex items-center justify-between">
                            <label className="text-[15px] text-foreground">Mobile Emulation</label>
                            <button onClick={() => setMobile(!mobile)} className={cn("px-4 py-1.5 rounded-md text-sm font-semibold transition-all", mobile ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{mobile ? "On" : "Off"}</button>
                          </div>
                          <div className="space-y-2">
                            <label className="text-[15px] text-foreground">Wait after load (ms)</label>
                            <Input type="number" value={waitFor} onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)} placeholder="0" className="h-10" />
                          </div>
                        </div>

                        {mobile && devicePresets.length > 0 && (
                          <select value={mobileDevice} onChange={(e) => setMobileDevice(e.target.value)} className="w-full h-11 text-sm">
                            <option value="">Default mobile</option>
                            {devicePresets.map((d: any) => (<option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>))}
                          </select>
                        )}
                      </>
                    )}

                    {/* Webhooks */}
                    <div className="space-y-3 pt-3 border-t border-border/30">
                      <div className="space-y-2">
                        <label className="text-[15px] text-foreground">Webhook URL</label>
                        <Input placeholder="https://your-server.com/webhook" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} className="h-11" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[15px] text-foreground">Webhook Secret</label>
                        <Input placeholder="your-secret-key" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} className="h-11" />
                      </div>
                    </div>

                    {/* Headers / Cookies */}
                    {(activeEndpoint === "scrape" || activeEndpoint === "batch") && (
                      <div className="space-y-3 pt-3 border-t border-border/30">
                        <div className="space-y-2">
                          <label className="text-[15px] text-foreground">Custom Headers (JSON)</label>
                          <textarea className="flex w-full rounded-lg border border-input bg-background px-4 py-3 text-sm font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[60px] resize-none" placeholder='{"Authorization": "Bearer ..."}' value={headersText} onChange={(e) => setHeadersText(e.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <label className="text-[15px] text-foreground">Cookies (JSON)</label>
                          <textarea className="flex w-full rounded-lg border border-input bg-background px-4 py-3 text-sm font-mono placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[60px] resize-none" placeholder='{"session_id": "abc123"}' value={cookiesText} onChange={(e) => setCookiesText(e.target.value)} />
                        </div>
                      </div>
                    )}

                    {/* AI Extraction */}
                    <div className="space-y-3 pt-3 border-t border-border/30">
                      <div className="flex items-center justify-between">
                        <label className="text-[15px] font-medium text-foreground flex items-center gap-2">
                          <Sparkles className="h-[18px] w-[18px] text-primary" /> AI Extraction (BYOK)
                        </label>
                        <button onClick={() => setExtractEnabled(!extractEnabled)} className={cn("px-4 py-1.5 rounded-md text-sm font-semibold transition-all", extractEnabled ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{extractEnabled ? "On" : "Off"}</button>
                      </div>
                      {extractEnabled && (
                        <textarea
                          className="flex w-full rounded-lg border border-input bg-background px-4 py-3 text-base placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[80px] resize-none"
                          placeholder="e.g., Extract the product name, price, and description"
                          value={extractPrompt}
                          onChange={(e) => setExtractPrompt(e.target.value)}
                        />
                      )}
                    </div>
                  </div>
                </section>
              )}

              {/* ── Active Job Progress ── */}
              {activeJob && (
                <section className={cn(
                  "mx-auto w-full mb-8 animate-scale-in",
                  activeJob.data && activeJob.data.length > 0 ? "max-w-5xl" : "max-w-2xl"
                )}>
                  <div className="rounded-2xl border border-primary/20 bg-card/80 backdrop-blur-sm overflow-hidden shadow-lg shadow-primary/5">
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
                      <div className="flex items-center gap-3 min-w-0">
                        {activeJob.status === "running" ? (
                          <div className="h-9 w-9 rounded-lg bg-primary/15 grid place-items-center shrink-0">
                            <Loader2 className="h-5 w-5 text-primary animate-spin" />
                          </div>
                        ) : activeJob.status === "completed" ? (
                          <div className="h-9 w-9 rounded-lg bg-emerald-500/15 grid place-items-center shrink-0">
                            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                          </div>
                        ) : (
                          <div className="h-9 w-9 rounded-lg bg-red-500/15 grid place-items-center shrink-0">
                            <XCircle className="h-5 w-5 text-red-400" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-base font-bold capitalize">{activeJob.type}</span>
                            <span className={cn(
                              "text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full",
                              activeJob.status === "running" ? "bg-primary/15 text-primary" :
                              activeJob.status === "completed" ? "bg-emerald-500/15 text-emerald-400" :
                              "bg-red-500/15 text-red-400"
                            )}>
                              {activeJob.status === "running" ? "In progress" : activeJob.status}
                            </span>
                          </div>
                          <p className="text-[13px] text-muted-foreground truncate mt-0.5">{activeJob.target}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {activeJob.status === "running" && (
                          <button
                            onClick={async () => {
                              try {
                                await api.cancelJob(activeJob.id);
                                setActiveJob((prev: any) => prev ? { ...prev, status: "cancelled" } : null);
                              } catch {}
                            }}
                            className="h-8 px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
                            title="Stop job"
                          >
                            <Square className="h-3.5 w-3.5" />
                            Stop
                          </button>
                        )}
                        <button
                          onClick={dismissJob}
                          className="h-8 w-8 rounded-lg grid place-items-center text-muted-foreground/60 hover:text-foreground hover:bg-muted/60 transition-all"
                          title="Dismiss"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Progress */}
                    <div className="px-5 py-4 space-y-3">
                      {/* Progress bar */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-semibold text-foreground">
                            {activeJob.completed} <span className="text-muted-foreground font-medium">of</span> {activeJob.total > 0 ? activeJob.total : "—"} <span className="text-muted-foreground font-medium">completed</span>
                          </span>
                          <span className="font-bold text-primary tabular-nums">
                            {activeJob.total > 0 ? Math.round((activeJob.completed / activeJob.total) * 100) : 0}%
                          </span>
                        </div>
                        <div className="h-2.5 rounded-full bg-muted/80 overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-500 ease-out",
                              activeJob.status === "completed" ? "bg-emerald-500" :
                              activeJob.status === "failed" ? "bg-red-500" :
                              "bg-primary"
                            )}
                            style={{ width: `${activeJob.total > 0 ? Math.min(100, (activeJob.completed / activeJob.total) * 100) : 0}%` }}
                          />
                        </div>
                      </div>

                      {/* Counter pills */}
                      {activeJob.status === "running" && activeJob.completed > 0 && (
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-[13px] font-bold">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {activeJob.completed} done
                          </div>
                          {activeJob.total > 0 && activeJob.total - activeJob.completed > 0 && (
                            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/60 text-muted-foreground text-[13px] font-medium">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              {activeJob.total - activeJob.completed} remaining
                            </div>
                          )}
                        </div>
                      )}

                      {/* Error message */}
                      {activeJob.error && (
                        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-sm text-red-400 font-medium">
                          {activeJob.error}
                        </div>
                      )}

                      {/* Completed actions */}
                      {activeJob.status === "completed" && (
                        <div className="flex items-center gap-3 pt-1">
                          <button
                            onClick={handleDownloadActiveJob}
                            className="flex items-center gap-2 h-10 rounded-lg px-5 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-md shadow-primary/15"
                          >
                            <Download className="h-[18px] w-[18px]" />
                            Download JSON
                          </button>
                          <Link
                            href={getJobDetailPath({ id: activeJob.id, type: activeJob.type })}
                            className="flex items-center gap-2 h-10 rounded-lg px-5 text-sm font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
                          >
                            <ExternalLink className="h-[18px] w-[18px]" />
                            View full results
                          </Link>
                        </div>
                      )}

                      {(activeJob.status === "failed" || activeJob.status === "cancelled") && (
                        <div className="flex items-center gap-3 pt-1">
                          <button
                            onClick={async () => {
                              try {
                                const res = await api.retryJob(activeJob.id);
                                setActiveJob({
                                  id: res.new_job_id,
                                  type: activeJob.type,
                                  status: "running",
                                  target: activeJob.target,
                                  completed: 0,
                                  total: activeJob.total || 0,
                                  data: [],
                                  error: undefined,
                                });
                              } catch {}
                            }}
                            className="flex items-center gap-2 h-10 rounded-lg px-5 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-md shadow-primary/15"
                          >
                            <RefreshCw className="h-[18px] w-[18px]" />
                            Retry
                          </button>
                          <Link
                            href={getJobDetailPath({ id: activeJob.id, type: activeJob.type })}
                            className="flex items-center gap-2 h-10 rounded-lg px-5 text-sm font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
                          >
                            <ExternalLink className="h-[18px] w-[18px]" />
                            View details
                          </Link>
                        </div>
                      )}
                    </div>

                    {/* ── Inline Results ── */}
                    {activeJob.data && activeJob.data.length > 0 && activeJob.type !== "map" && (
                      <div className="border-t border-border/30">
                        <div className="px-5 py-3 flex items-center justify-between bg-muted/10">
                          <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-primary" />
                            <span className="text-[13px] font-bold text-foreground">
                              {activeJob.data.length} {activeJob.data.length === 1 ? "result" : "results"}
                            </span>
                          </div>
                          {activeJob.status === "running" && (
                            <div className="flex items-center gap-1.5 text-[12px] text-primary font-medium">
                              <Loader2 className="h-3 w-3 animate-spin" />
                              Live
                            </div>
                          )}
                        </div>
                        <div className="px-4 pb-4 space-y-2 max-h-[600px] overflow-auto">
                          {activeJob.data.map((page: any, i: number) => (
                            <InlineResultCard
                              key={page.id || page.url || i}
                              page={page}
                              index={i}
                              jobId={activeJob.id}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Map inline results (URL list only) */}
                    {activeJob.data && activeJob.data.length > 0 && activeJob.type === "map" && (
                      <div className="border-t border-border/30">
                        <div className="px-5 py-3 flex items-center gap-2 bg-muted/10">
                          <Network className="h-4 w-4 text-primary" />
                          <span className="text-[13px] font-bold text-foreground">
                            {activeJob.data.length} URLs discovered
                          </span>
                        </div>
                        <div className="max-h-[400px] overflow-auto">
                          {activeJob.data.map((link: any, i: number) => (
                            <div key={i} className="flex items-center justify-between px-5 py-2.5 hover:bg-muted/30 group transition-colors">
                              <a
                                href={link.url || link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[13px] text-primary hover:underline truncate"
                              >
                                {link.url || link}
                              </a>
                              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground/40 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* ── Map Results ── */}
              {activeEndpoint === "map" && mapResult && (
                <section className="max-w-2xl mx-auto mb-8 animate-float-in">
                  <div className="rounded-2xl border border-primary/15 bg-card/60 overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
                      <div className="flex items-center gap-2.5">
                        <Network className="h-5 w-5 text-primary" />
                        <span className="text-base font-semibold">Discovered URLs</span>
                        <Badge variant="outline" className="border-primary/20 text-primary text-sm">{mapResult.total}</Badge>
                      </div>
                      <button onClick={copyMapUrls} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all">
                        {copied ? <Check className="h-[18px] w-[18px] text-emerald-400" /> : <Copy className="h-[18px] w-[18px]" />}
                        Copy All
                      </button>
                    </div>
                    <div className="max-h-[400px] overflow-auto">
                      {mapResult.links?.map((link: any, i: number) => (
                        <div key={i} className="flex items-center justify-between px-5 py-3 hover:bg-muted/30 group transition-colors">
                          <div className="min-w-0 flex-1">
                            <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-[15px] text-primary hover:underline truncate block">{link.url}</a>
                            {link.title && <p className="text-[13px] text-muted-foreground truncate">{link.title}</p>}
                          </div>
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="opacity-0 group-hover:opacity-100 ml-2 transition-opacity">
                            <ExternalLink className="h-4 w-4 text-muted-foreground" />
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {/* ── Recent Runs ── */}
              {hasRuns && (
                <section className="max-w-5xl mx-auto pb-10" style={{ animationDelay: "0.1s" }}>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <h2 className="text-xl font-bold tracking-tight">Recent Runs</h2>
                      <div className="h-px flex-1 bg-gradient-to-r from-border to-transparent min-w-[40px]" />
                    </div>
                    <Link href="/jobs" className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 font-medium">
                      View all <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                    {recentJobs.map((job) => {
                      const jobUrl = getJobUrl(job);
                      const domain = getDomain(jobUrl);
                      const TypeIcon = getTypeIcon(job.type);
                      const { date, time } = job.created_at ? formatDate(job.created_at) : { date: "", time: "" };
                      const jobFormats: string[] = job.config?.formats || [];
                      const isCompleted = job.status === "completed";

                      return (
                        <div key={job.id} className="rounded-xl border border-border/50 bg-card/70 hover:bg-card transition-all duration-200 group overflow-hidden">
                          <div className="h-[2px] bg-primary" />

                          <Link href={getJobDetailPath(job)}>
                            <div className="flex items-center justify-between px-5 pt-4 pb-3">
                              <div className="flex items-center gap-2.5 min-w-0">
                                {jobUrl && !jobUrl.includes("URLs") && (
                                  <img src={getFavicon(jobUrl)} alt="" className="h-5 w-5 rounded-sm shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                                )}
                                <span className="text-base font-semibold truncate">{domain || "No URL"}</span>
                              </div>
                              <ExternalLink className="h-4 w-4 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors shrink-0" />
                            </div>

                            <div className="px-5 pb-4 space-y-2.5">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <TypeIcon className="h-[18px] w-[18px] text-primary" />
                                  <span className="text-[13px] font-bold uppercase tracking-wider text-primary">{job.type}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className={cn("h-2 w-2 rounded-full", job.status === "completed" ? "bg-emerald-400" : job.status === "failed" ? "bg-red-400" : job.status === "running" ? "bg-amber-400 animate-pulse" : "bg-muted-foreground")} />
                                  <span className="text-[13px] font-medium text-muted-foreground capitalize">{job.status === "completed" ? "Done" : job.status}</span>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 text-muted-foreground">
                                <Clock className="h-4 w-4" />
                                <span className="text-[13px] font-medium">{date} {time}</span>
                              </div>

                              {jobFormats.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pt-0.5">
                                  {jobFormats.slice(0, 4).map((fmt: string) => {
                                    const fmtInfo = formatIcons[fmt];
                                    const FmtIcon = fmtInfo?.icon || FileText;
                                    return (
                                      <span key={fmt} className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                                        <FmtIcon className="h-3 w-3" /> {fmtInfo?.label || fmt}
                                      </span>
                                    );
                                  })}
                                  {jobFormats.length > 4 && <span className="text-[11px] text-muted-foreground font-medium self-center">+{jobFormats.length - 4}</span>}
                                </div>
                              )}
                            </div>
                          </Link>

                          {isCompleted && (
                            <div className="px-5 pb-4 pt-0">
                              <button onClick={(e) => { e.preventDefault(); handleDownload(job); }} className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-bold transition-all border border-primary/20 text-primary hover:bg-primary/10">
                                <Download className="h-[18px] w-[18px]" /> Download JSON
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
                  <p className="text-base text-muted-foreground font-medium">Your runs will appear here</p>
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
