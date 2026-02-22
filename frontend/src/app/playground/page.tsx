"use client";

import { useState, useEffect, useCallback, useRef, memo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";
import {
  Globe,
  Search,
  Loader2,
  SlidersHorizontal,
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
  RefreshCw,
  Square,
  Menu,
} from "lucide-react";

// ── Glitch Text Hook ─────────────────────────────────────────

const GLITCH_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*!?<>{}[]";

function useGlitchText(text: string, duration = 400) {
  const [display, setDisplay] = useState(text);
  const frameRef = useRef<number | null>(null);
  const prevText = useRef(text);

  useEffect(() => {
    if (text === prevText.current) return;
    prevText.current = text;

    const target = text.toUpperCase();
    const len = Math.max(target.length, display.length);
    const startTime = performance.now();

    const scramble = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);

      let result = "";
      for (let i = 0; i < len; i++) {
        const charProgress = Math.max(0, (progress - i / len / 2) * 2);
        if (charProgress >= 1 && i < target.length) {
          result += target[i];
        } else if (i < target.length) {
          result += GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)];
        }
      }
      setDisplay(result);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(scramble);
      } else {
        setDisplay(target);
      }
    };

    frameRef.current = requestAnimationFrame(scramble);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [text, duration]);

  return display;
}

// ── Types ────────────────────────────────────────────────────

type Endpoint = "scrape" | "crawl" | "search" | "map";

const ENDPOINTS: { id: Endpoint; label: string; icon: any; desc: string }[] = [
  { id: "scrape", label: "Scrape", icon: Crosshair, desc: "Single page extraction" },
  { id: "search", label: "Search", icon: Satellite, desc: "Web search + scrape" },
  { id: "map", label: "Map", icon: Network, desc: "Discover all URLs" },
  { id: "crawl", label: "Crawl", icon: Bug, desc: "Multi-page BFS crawl" },
];

const ACTION_LABELS: Record<Endpoint, string> = {
  scrape: "Execute Scrape",
  crawl: "Execute Crawl",
  search: "Execute Search",
  map: "Execute Map",
};

const PLACEHOLDERS: Record<Endpoint, string> = {
  scrape: "example.com",
  crawl: "example.com",
  map: "example.com",
  search: "python web scraping tutorial",
};

// ── Helpers ──────────────────────────────────────────────────

function getJobDetailPath(job: any): string {
  switch (job.type) {
    case "scrape": return `/scrape/${job.id}`;
    case "crawl": return `/crawl/${job.id}`;
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
    default: return FileText;
  }
}

function getTypeColor(type: string): string {
  switch (type) {
    case "scrape": return "text-cyan-400";
    case "crawl": return "text-violet-400";
    case "search": return "text-amber-400";
    case "map": return "text-pink-400";
    default: return "text-white/50";
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
  markdown: { icon: FileText, label: "MD" },
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
    }
  } catch {}
}

// ── Inline Result Card ───────────────────────────────────────

type ResultTab = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract";

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
  const [screenshotData, setScreenshotData] = useState<string | null>(page.screenshot || null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const hasMarkdown = !!page.markdown;
  const hasHtml = !!page.html;
  const hasScreenshot = !!page.screenshot;
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
    { id: "structured", label: "JSON", icon: Braces, available: hasStructured },
    { id: "headings", label: "Headings", icon: List, available: hasHeadings },
    { id: "images", label: "Images", icon: ImageIcon, available: hasImages },
    { id: "extract", label: "AI Extract", icon: Sparkles, available: hasExtract },
  ];

  const availableTabs = tabs.filter((t) => t.available);

  useEffect(() => {
    if (!availableTabs.find((t) => t.id === activeTab)) {
      setActiveTab(availableTabs[0]?.id || "markdown");
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
      default: text = JSON.stringify(page[activeTab], null, 2); break;
    }
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const wordCount = page.metadata?.word_count || 0;
  const statusCode = page.metadata?.status_code;

  return (
    <div className="border border-white/10 hover:border-white/20 transition-all">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-5 w-full px-8 py-5 hover:bg-white/[0.02] transition-colors text-left"
      >
        <span className="text-[14px] text-white/40 font-mono w-8 shrink-0 text-right tabular-nums font-bold">
          {String(index + 1).padStart(2, "0")}
        </span>
        {page.url && (
          <img
            src={`https://www.google.com/s2/favicons?domain=${getDomain(page.url)}&sz=32`}
            alt=""
            className="h-5 w-5 shrink-0"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-mono font-medium truncate text-white">{page.url || "Unknown URL"}</p>
          {page.metadata?.title && (
            <p className="text-[13px] text-white/50 truncate mt-1">{page.metadata.title}</p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {wordCount > 0 && (
            <span className="text-[12px] font-mono text-white/40 bg-white/[0.04] px-3 py-1 border border-white/[0.06]">
              {wordCount.toLocaleString()} words
            </span>
          )}
          {statusCode && (
            <span className={cn(
              "text-[12px] font-mono font-bold px-3 py-1 border",
              statusCode >= 200 && statusCode < 400
                ? "bg-emerald-500/[0.06] text-emerald-400 border-emerald-500/15"
                : "bg-red-500/10 text-red-400 border-red-500/20"
            )}>
              {statusCode}
            </span>
          )}
          {expanded ? <ChevronUp className="h-4 w-4 text-white/40" /> : <ChevronDown className="h-4 w-4 text-white/40" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-white/[0.08]">
          <div className="flex items-center border-b border-white/[0.08] bg-white/[0.01]">
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
                    "flex items-center gap-2 px-6 py-3.5 text-[12px] font-mono uppercase tracking-[0.15em] transition-all border-b-2 -mb-[1px]",
                    activeTab === tab.id
                      ? "border-emerald-500 text-emerald-400 bg-emerald-500/[0.03]"
                      : "border-transparent text-white/40 hover:text-white/70"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
            <div className="flex-1" />
            {activeTab !== "screenshot" && (
              <button onClick={copyContent} className="flex items-center gap-2 px-5 py-3.5 text-[12px] font-mono text-white/40 hover:text-white/70 transition-all">
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            )}
          </div>

          <div className="p-6">
            {activeTab === "markdown" && hasMarkdown && (
              <pre className="max-h-72 overflow-auto text-[14px] text-white/60 whitespace-pre-wrap font-mono bg-black/40 p-6 leading-[1.8] border border-white/[0.06]">
                {page.markdown}
              </pre>
            )}
            {activeTab === "html" && hasHtml && (
              <pre className="max-h-72 overflow-auto text-[13px] text-white/60 whitespace-pre-wrap font-mono bg-black/40 p-6 border border-white/[0.06]">
                {page.html}
              </pre>
            )}
            {activeTab === "screenshot" && hasScreenshot && (
              <div className="flex justify-center">
                {screenshotData ? (
                  <img src={`data:image/jpeg;base64,${screenshotData}`} alt={`Screenshot of ${page.url}`} className="max-w-full border border-white/10" style={{ maxHeight: "500px" }} />
                ) : screenshotLoading ? (
                  <div className="flex items-center gap-3 py-8 text-white/50">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-[13px] font-mono uppercase tracking-wider">Loading...</span>
                  </div>
                ) : (
                  <button onClick={loadScreenshot} className="flex items-center gap-2 px-5 py-3 text-[13px] font-mono uppercase tracking-wider border border-white/10 text-white/50 hover:text-white/80 hover:bg-white/[0.03] transition-all">
                    <Camera className="h-4 w-4" /> Load Screenshot
                  </button>
                )}
              </div>
            )}
            {activeTab === "links" && hasLinks && (
              <div className="space-y-2 max-h-72 overflow-auto">
                {page.links_detail ? (
                  <>
                    <div className="flex gap-4 text-[13px] font-mono pb-3 border-b border-white/[0.08]">
                      <span className="text-white/60">{page.links_detail.total} total</span>
                      {page.links_detail.internal && <span className="text-blue-400">{page.links_detail.internal.count} internal</span>}
                      {page.links_detail.external && <span className="text-amber-400">{page.links_detail.external.count} external</span>}
                    </div>
                    {page.links_detail.internal?.links?.map((link: any, i: number) => (
                      <a key={`i-${i}`} href={link.url} target="_blank" rel="noopener noreferrer" className="block text-[13px] font-mono text-emerald-400 hover:text-emerald-300 truncate">{link.url}</a>
                    ))}
                    {page.links_detail.external?.links?.map((link: any, i: number) => (
                      <a key={`e-${i}`} href={link.url} target="_blank" rel="noopener noreferrer" className="block text-[13px] font-mono text-amber-400/80 hover:text-amber-400 truncate">{link.url}</a>
                    ))}
                  </>
                ) : page.links?.map((link: string, i: number) => (
                  <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-[13px] font-mono text-emerald-400 hover:text-emerald-300 truncate">{link}</a>
                ))}
              </div>
            )}
            {activeTab === "structured" && hasStructured && (
              <pre className="max-h-72 overflow-auto text-[13px] font-mono bg-black/40 p-6 text-amber-400/60 border border-white/[0.06]">
                {JSON.stringify(page.structured_data, null, 2)}
              </pre>
            )}
            {activeTab === "headings" && hasHeadings && (
              <div className="space-y-1.5 max-h-72 overflow-auto">
                {page.headings.map((h: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 text-[13px]" style={{ paddingLeft: `${(h.level - 1) * 16}px` }}>
                    <span className="text-[10px] font-mono font-bold text-emerald-500 bg-emerald-500/10 px-2 py-0.5 shrink-0">H{h.level}</span>
                    <span className={h.level === 1 ? "font-medium text-white" : "text-white/60"}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}
            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-72 overflow-auto">
                {page.images.map((img: any, i: number) => (
                  <div key={i} className="border border-white/[0.08] overflow-hidden bg-black/20">
                    <div className="aspect-video bg-black/30 flex items-center justify-center">
                      <img src={img.src} alt={img.alt || ""} className="max-w-full max-h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                    </div>
                    <div className="p-2">
                      <p className="text-[11px] font-mono text-white/40 truncate">{img.src.split("/").pop()}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {activeTab === "extract" && hasExtract && (
              <pre className="max-h-72 overflow-auto text-[13px] whitespace-pre-wrap font-mono bg-black/40 p-6 text-emerald-400/70 border border-white/[0.06]">
                {JSON.stringify(page.extract, null, 2)}
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

  const [activeEndpoint, setActiveEndpoint] = useState<Endpoint>(() => {
    const ep = searchParams.get("endpoint") as Endpoint;
    return ENDPOINTS.find((e) => e.id === ep) ? ep : "scrape";
  });

  const glitchTitle = useGlitchText(activeEndpoint);

  useEffect(() => {
    const ep = searchParams.get("endpoint") as Endpoint;
    if (ep && ENDPOINTS.find((e) => e.id === ep) && ep !== activeEndpoint) {
      setActiveEndpoint(ep);
    }
  }, [searchParams]);

  const switchEndpoint = useCallback((ep: Endpoint) => {
    setActiveEndpoint(ep);
    setError("");
    window.history.replaceState(null, "", `/playground?endpoint=${ep}`);
  }, []);

  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [formats, setFormats] = useState<string[]>(["markdown"]);
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
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [maxPages, setMaxPages] = useState(10);
  const [maxDepth, setMaxDepth] = useState(3);
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [concurrency, setConcurrency] = useState(3);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [engine, setEngine] = useState("duckduckgo");
  const [mapSearch, setMapSearch] = useState("");
  const [mapLimit, setMapLimit] = useState(100);
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [useSitemap, setUseSitemap] = useState(true);
  const [mapResult, setMapResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  const [activeJob, setActiveJob] = useState<{
    id: string; type: Endpoint; status: string; target: string;
    total: number; completed: number; data?: any[]; error?: string;
  } | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!api.getToken()) { router.push("/auth/login"); return; }
    api.getUsageHistory({ per_page: 9 })
      .then((res) => { setRecentJobs(res.jobs || []); setJobsLoaded(true); })
      .catch(() => setJobsLoaded(true));
  }, [router]);

  const fetchJobStatus = useCallback(async (jobId: string, jobType: Endpoint) => {
    try {
      let res: any;
      switch (jobType) {
        case "scrape": res = await api.getScrapeStatus(jobId); break;
        case "crawl": res = await api.getCrawlStatus(jobId, 1, 20); break;
        case "search": res = await api.getSearchStatus(jobId); break;
        case "map": res = await api.getMapStatus(jobId); break;
      }
      setActiveJob((prev) => {
        if (!prev || prev.id !== jobId) return prev;
        return { ...prev, status: res.status || prev.status, completed: res.completed_pages ?? res.completed_results ?? res.completed_urls ?? prev.completed, total: res.total_pages || res.total_results || res.total_urls || res.total || prev.total, data: res.data || res.links || prev.data, error: res.error };
      });
      return res.status;
    } catch { return null; }
  }, []);

  useEffect(() => {
    if (!activeJob || ["completed", "failed", "cancelled"].includes(activeJob.status)) return;
    const jobId = activeJob.id; const jobType = activeJob.type;
    try {
      const es = new EventSource(api.getSSEUrl(jobId)); sseRef.current = es;
      es.onmessage = async () => { const s = await fetchJobStatus(jobId, jobType); if (s && ["completed","failed","cancelled"].includes(s)) { es.close(); sseRef.current = null; api.getUsageHistory({ per_page: 9 }).then(r => setRecentJobs(r.jobs||[])).catch(()=>{}); } };
      es.onerror = () => { es.close(); sseRef.current = null; const iv = setInterval(async () => { const s = await fetchJobStatus(jobId, jobType); if (s && ["completed","failed","cancelled"].includes(s)) { clearInterval(iv); pollRef.current = null; api.getUsageHistory({ per_page: 9 }).then(r => setRecentJobs(r.jobs||[])).catch(()=>{}); } }, 2000); pollRef.current = iv; };
    } catch { const iv = setInterval(async () => { const s = await fetchJobStatus(jobId, jobType); if (s && ["completed","failed","cancelled"].includes(s)) { clearInterval(iv); pollRef.current = null; api.getUsageHistory({ per_page: 9 }).then(r => setRecentJobs(r.jobs||[])).catch(()=>{}); } }, 2000); pollRef.current = iv; }
    fetchJobStatus(jobId, jobType);
    return () => { if (sseRef.current) { sseRef.current.close(); sseRef.current = null; } if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [activeJob?.id, activeJob?.status, fetchJobStatus]);

  const dismissJob = useCallback(() => { if (sseRef.current) { sseRef.current.close(); sseRef.current = null; } if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } setActiveJob(null); }, []);
  const handleDownloadActiveJob = useCallback(() => { if (!activeJob) return; handleDownload({ id: activeJob.id, type: activeJob.type }); }, [activeJob]);

  useEffect(() => { if (mobile && devicePresets.length === 0) { api.getDevicePresets().then((res) => setDevicePresets(res.devices || [])).catch(() => {}); } }, [mobile]);

  const toggleFormat = (format: string) => setFormats((prev) => prev.includes(format) ? prev.filter((f) => f !== format) : [...prev, format]);

  const handleGetCode = () => {
    let code = "";
    const fullUrl = url.startsWith("http") ? url : `https://${url}`;
    switch (activeEndpoint) {
      case "scrape": code = `curl -X POST /v1/scrape \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "formats": ${JSON.stringify(formats)}}'`; break;
      case "crawl": code = `curl -X POST /v1/crawl \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "max_pages": ${maxPages}, "max_depth": ${maxDepth}}'`; break;
      case "search": code = `curl -X POST /v1/search \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"query": "${searchQuery}", "num_results": ${numResults}, "engine": "${engine}"}'`; break;
      case "map": code = `curl -X POST /v1/map \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl}", "limit": ${mapLimit}}'`; break;
    }
    navigator.clipboard.writeText(code);
  };

  const handleAction = async () => {
    setLoading(true); setError("");
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
          params.scrape_options = { formats, only_main_content: onlyMainContent, wait_for: waitFor || undefined };
          if (mobile) { params.scrape_options.mobile = true; if (mobileDevice) params.scrape_options.mobile_device = mobileDevice; }
          if (includePaths.trim()) params.include_paths = includePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
          if (excludePaths.trim()) params.exclude_paths = excludePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
          if (showAdvanced) { if (webhookUrl.trim()) params.webhook_url = webhookUrl.trim(); if (webhookSecret.trim()) params.webhook_secret = webhookSecret.trim(); if (useProxy) params.use_proxy = true; }
          if (extractEnabled && extractPrompt.trim()) params.scrape_options = { ...params.scrape_options, extract: { prompt: extractPrompt.trim() } };
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
      }
    } catch (err: any) { setError(err.message); } finally { setLoading(false); }
  };

  const isDisabled = loading || (activeEndpoint === "search" ? !searchQuery.trim() : !url.trim());
  const hasRuns = recentJobs.length > 0;
  const copyMapUrls = () => { if (!mapResult?.links) return; navigator.clipboard.writeText(mapResult.links.map((l: any) => l.url).join("\n")); setCopied(true); setTimeout(() => setCopied(false), 2000); };
  const pct = activeJob && activeJob.total > 0 ? Math.round((activeJob.completed / activeJob.total) * 100) : 0;

  const TICKER_ITEMS = [
    { label: "PAGES_SCRAPED", value: "14,203", color: "text-emerald-400", prefix: "▲ " },
    { label: "AVG_RESPONSE", value: "2.3s", color: "text-amber-400" },
    { label: "SUCCESS_RATE", value: "98.7%", color: "text-cyan-400", prefix: "▲ " },
    { label: "ANTI_BOT_BYPASS", value: "ACTIVE", color: "text-violet-400" },
    { label: "WORKERS", value: "4/4", color: "text-pink-400" },
    { label: "QUEUE", value: "0 pending", color: "text-white/50" },
    { label: "UPTIME", value: "99.9%", color: "text-emerald-400" },
    { label: "PROXY_POOL", value: "ROTATING", color: "text-amber-400" },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      {/* ═══ NAV ═══ */}
      <nav className="relative fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-[#050505]/95 backdrop-blur-sm">
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-emerald-500 via-cyan-500 to-violet-500" />
        <div className="flex items-center justify-between px-6 md:px-10 h-16">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-4 w-4 bg-gradient-to-br from-emerald-400 to-cyan-500" />
            <span className="text-[18px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
          </Link>
          <div className="hidden md:flex items-center gap-10">
            <Link href="/dashboard" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">Dashboard</Link>
            <span className="text-[12px] uppercase tracking-[0.2em] text-white border-b border-white/40 pb-0.5 font-mono cursor-default">Playground</span>
            <Link href="/docs" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">API Docs</Link>
            <Link href="/jobs" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">Jobs</Link>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden sm:flex text-[11px] text-white/40 items-center gap-1.5 font-mono">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              ONLINE
            </span>
            <Link href="/settings" className="hidden sm:block border border-white/20 px-5 py-2 text-[12px] uppercase tracking-[0.15em] hover:bg-white hover:text-black transition-all font-mono">Settings</Link>
            <button onClick={() => setMobileNav(!mobileNav)} className="md:hidden h-10 w-10 grid place-items-center text-white/60"><Menu className="h-5 w-5" /></button>
          </div>
        </div>
        {mobileNav && (
          <div className="md:hidden border-t border-white/10 bg-[#050505] px-6 py-4 space-y-3">
            <Link href="/dashboard" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Dashboard</Link>
            <span className="block text-[12px] uppercase tracking-[0.2em] text-white font-mono py-2">Playground</span>
            <Link href="/docs" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">API Docs</Link>
            <Link href="/jobs" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Jobs</Link>
            <Link href="/settings" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Settings</Link>
          </div>
        )}
      </nav>

      {/* ═══ TICKER ═══ */}
      <div className="mt-16 border-b border-white/[0.06] bg-[#050505] overflow-hidden h-8 flex items-center">
        <div className="flex whitespace-nowrap animate-ticker">
          {[0, 1].map((dup) => (
            <div key={dup} className="flex">
              {TICKER_ITEMS.map((item, i) => (
                <span key={`${dup}-${i}`} className="text-[11px] tracking-wider mx-8 text-white/30 font-mono">
                  {item.label} <span className={item.color}>{item.prefix || ""}{item.value}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <main>
        {/* Grid bg */}
        <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />

        {/* ── HERO ── */}
        <section className="px-6 md:px-10 pt-16 pb-12 border-b border-white/[0.06]">
          <div className="max-w-[1400px] mx-auto">
            <div className="flex flex-col lg:flex-row items-start justify-between gap-10 lg:gap-0">
              <div>
                <div className="inline-block border border-emerald-500 text-emerald-400 text-[11px] uppercase tracking-[0.25em] px-4 py-1.5 mb-8 font-mono">Interactive Console</div>
                <h1 className="font-display text-[48px] md:text-[72px] leading-[0.9] tracking-[-3px] uppercase mb-6">
                  <span className="animate-gradient-text">{glitchTitle}</span><br />
                  <span className="text-white/30">THE WEB.</span>
                </h1>
                <p className="text-[16px] text-white/50 max-w-[500px] leading-[1.8] border-l-2 border-emerald-500/40 pl-6 font-mono">
                  Enter a target URL below. Select your output formats. Execute and watch results stream in real-time.
                </p>
              </div>

              {/* Endpoint selector */}
              <div className="border border-white/10 w-full lg:w-auto lg:min-w-[280px]">
                <div className="text-[10px] uppercase tracking-[0.3em] text-white/40 px-6 py-3 border-b border-white/[0.06] font-mono">Endpoint</div>
                {ENDPOINTS.map((ep) => {
                  const isActive = activeEndpoint === ep.id;
                  return (
                    <button
                      key={ep.id}
                      onClick={() => switchEndpoint(ep.id)}
                      className={cn(
                        "flex items-center gap-4 w-full px-6 py-4 text-left transition-colors border-l-2",
                        isActive ? `bg-white/[0.03] ${ep.id === "scrape" ? "border-cyan-500" : ep.id === "crawl" ? "border-violet-500" : ep.id === "search" ? "border-amber-500" : "border-pink-500"}` : "border-transparent hover:bg-white/[0.02]"
                      )}
                    >
                      <ep.icon className={cn("h-5 w-5", isActive ? (ep.id === "scrape" ? "text-cyan-400" : ep.id === "crawl" ? "text-violet-400" : ep.id === "search" ? "text-amber-400" : "text-pink-400") : "text-white/30")} />
                      <div>
                        <div className={cn("text-[14px] font-bold uppercase tracking-[0.1em] font-mono", isActive ? "text-white" : "text-white/50")}>{ep.label}</div>
                        <div className={cn("text-[11px] mt-0.5 font-mono", isActive ? "text-white/40" : "text-white/25")}>{ep.desc}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* ── COMMAND INPUT ── */}
        <section className="px-6 md:px-10 py-12 border-b border-white/[0.06]">
          <div className="max-w-[1400px] mx-auto">
            <div className="flex items-center gap-3 mb-8">
              <span className="text-[12px] uppercase tracking-[0.25em] text-white/40 font-mono">{activeEndpoint === "search" ? "Search Query" : "Target URL"}</span>
              <div className="h-px flex-1 bg-white/[0.06]" />
              <span className="text-[11px] text-white/30 font-mono">POST /v1/{activeEndpoint}</span>
            </div>

            {/* Big input */}
            <div className="border border-white/10 mb-8">
              <div className="flex items-center h-[72px] md:h-[88px] px-6 md:px-8">
                <span className="text-amber-500/50 text-[20px] md:text-[24px] mr-4 font-bold select-none font-mono">$</span>
                {activeEndpoint !== "search" ? (
                  <span className="text-white/40 text-[16px] md:text-[20px] select-none font-mono">https://</span>
                ) : (
                  <Search className="h-5 w-5 md:h-6 md:w-6 text-white/40 shrink-0 mr-2" />
                )}
                <input
                  type="text"
                  value={activeEndpoint === "search" ? searchQuery : url}
                  onChange={(e) => { if (activeEndpoint === "search") setSearchQuery(e.target.value); else setUrl(e.target.value.replace(/^https?:\/\//, "")); }}
                  onKeyDown={(e) => e.key === "Enter" && !isDisabled && handleAction()}
                  placeholder={PLACEHOLDERS[activeEndpoint]}
                  className="flex-1 bg-transparent text-[18px] md:text-[24px] text-white outline-none ml-2 font-medium placeholder:text-white/15 font-mono"
                />
              </div>
              {formats.length === 0 && activeEndpoint !== "map" && (
                <div className="flex items-center gap-2 px-6 md:px-8 pb-3">
                  <div className="h-2 w-2 bg-amber-400" />
                  <p className="text-[12px] font-mono text-amber-400 uppercase tracking-wider">No format selected — metadata only</p>
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2 md:gap-3">
                {activeEndpoint !== "map" && ["markdown", "html", "links", "screenshot"].map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => toggleFormat(fmt)}
                    className={cn(
                      "px-4 md:px-5 py-2.5 md:py-3 text-[11px] md:text-[12px] uppercase tracking-[0.15em] flex items-center gap-2 transition-all font-mono",
                      formats.includes(fmt)
                        ? "border border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-400"
                        : "border border-white/[0.08] text-white/50 hover:border-white/20 hover:text-white/70"
                    )}
                  >
                    <span className="text-[14px] md:text-[16px]">◉</span> {fmt.charAt(0).toUpperCase() + fmt.slice(1)}
                  </button>
                ))}

                {activeEndpoint !== "map" && <div className="w-px h-8 bg-white/[0.06] mx-1 hidden md:block" />}

                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className={cn(
                    "border px-4 md:px-5 py-2.5 md:py-3 text-[11px] md:text-[12px] uppercase tracking-[0.15em] transition-all font-mono flex items-center gap-2",
                    showAdvanced ? "border-emerald-500/30 text-emerald-400" : "border-white/[0.08] text-white/50 hover:border-white/20 hover:text-white/70"
                  )}
                >
                  <SlidersHorizontal className="h-4 w-4" /> Config
                </button>
                <button
                  onClick={handleGetCode}
                  className="border border-white/[0.08] text-white/50 px-4 md:px-5 py-2.5 md:py-3 text-[11px] md:text-[12px] uppercase tracking-[0.15em] hover:border-white/20 hover:text-white/70 transition-all font-mono flex items-center gap-2"
                >
                  <Code className="h-4 w-4" /> cURL
                </button>
              </div>
              <button
                onClick={handleAction}
                disabled={isDisabled}
                className="bg-white text-black px-8 md:px-10 py-3.5 md:py-4 text-[13px] md:text-[14px] font-bold uppercase tracking-[0.15em] hover:bg-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center gap-3 font-mono w-full md:w-auto justify-center"
              >
                {loading ? <Loader2 className="h-[18px] w-[18px] animate-spin" /> : <>{ACTION_LABELS[activeEndpoint]} <span className="text-[18px]">→</span></>}
              </button>
            </div>

            {error && (
              <div className="mt-4 border border-red-500/20 bg-red-500/[0.05] px-8 py-4 text-[13px] font-mono text-red-400">
                <span className="text-red-500/60 mr-2 font-bold">ERR</span>{error}
              </div>
            )}
          </div>
        </section>

        {/* ── ADVANCED SETTINGS ── */}
        {showAdvanced && (
          <section className="px-6 md:px-10 py-12 border-b border-white/[0.06] animate-fade-in">
            <div className="max-w-[1400px] mx-auto">
              <div className="border border-white/10">
                <div className="flex items-center gap-3 px-8 py-4 border-b border-white/[0.08]">
                  <SlidersHorizontal className="h-4 w-4 text-white/40" />
                  <span className="text-[12px] font-mono text-white/40 uppercase tracking-[0.2em]">Configuration</span>
                </div>
                <div className="p-8 space-y-6">
                  {activeEndpoint === "search" && (
                    <div className="space-y-5 pb-5 border-b border-white/[0.08]">
                      <div className="space-y-2">
                        <label className="text-[11px] font-mono text-emerald-400/70 uppercase tracking-[0.2em]">Engine</label>
                        <div className="flex gap-2">
                          {["duckduckgo", "brave", "google"].map((eng) => (
                            <button key={eng} onClick={() => setEngine(eng)} className={cn("px-5 py-2.5 text-[12px] font-mono uppercase tracking-wider transition-all", engine === eng ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/50 hover:bg-white/[0.08] hover:text-white/80")}>
                              {eng === "duckduckgo" ? "DuckDuckGo" : eng === "brave" ? "Brave" : "Google (BYOK)"}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-[11px] font-mono text-emerald-400/70 uppercase tracking-[0.2em]">Results: <span className="text-amber-400">{numResults}</span></label>
                        <input type="range" min={1} max={10} value={numResults} onChange={(e) => setNumResults(parseInt(e.target.value))} className="w-full" />
                      </div>
                    </div>
                  )}
                  {activeEndpoint === "crawl" && (
                    <div className="space-y-5 pb-5 border-b border-white/[0.08]">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {[
                          { label: "Page Limit", value: maxPages, set: setMaxPages, max: 10000 },
                          { label: "Link Depth", value: maxDepth, set: setMaxDepth, max: 20 },
                          { label: "Concurrency", value: concurrency, set: setConcurrency, max: 10 },
                        ].map((f) => (
                          <div key={f.label} className="space-y-2">
                            <label className="text-[11px] font-mono text-emerald-400/70 uppercase tracking-[0.2em]">{f.label}</label>
                            <Input type="number" value={f.value} onChange={(e) => f.set(parseInt(e.target.value) || 1)} min={1} max={f.max} className="h-11 font-mono bg-transparent border-white/10 text-white text-[14px]" />
                          </div>
                        ))}
                      </div>
                      <div className="space-y-3">
                        <div className="space-y-2">
                          <label className="text-[12px] font-mono text-white/60 uppercase tracking-wider">Include Paths <span className="text-white/30">(comma-separated)</span></label>
                          <Input placeholder="/blog/*, /docs/*" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} className="h-11 font-mono bg-transparent border-white/10 text-white placeholder:text-white/20 text-[14px]" />
                        </div>
                        <div className="space-y-2">
                          <label className="text-[12px] font-mono text-white/60 uppercase tracking-wider">Exclude Paths <span className="text-white/30">(comma-separated)</span></label>
                          <Input placeholder="/admin/*, /login" value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} className="h-11 font-mono bg-transparent border-white/10 text-white placeholder:text-white/20 text-[14px]" />
                        </div>
                      </div>
                    </div>
                  )}
                  {activeEndpoint === "map" && (
                    <div className="space-y-5 pb-5 border-b border-white/[0.08]">
                      <div className="space-y-2">
                        <label className="text-[11px] font-mono text-emerald-400/70 uppercase tracking-[0.2em]">Filter Keyword</label>
                        <Input placeholder="blog, pricing, docs" value={mapSearch} onChange={(e) => setMapSearch(e.target.value)} className="h-11 font-mono bg-transparent border-white/10 text-white placeholder:text-white/20 text-[14px]" />
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="space-y-2">
                          <label className="text-[11px] font-mono text-emerald-400/70 uppercase tracking-[0.2em]">Max URLs</label>
                          <Input type="number" value={mapLimit} onChange={(e) => setMapLimit(parseInt(e.target.value) || 100)} className="h-11 font-mono bg-transparent border-white/10 text-white text-[14px]" />
                        </div>
                        <div className="flex items-end justify-center pb-1">
                          <button onClick={() => setIncludeSubdomains(!includeSubdomains)} className={cn("px-5 py-2.5 text-[12px] font-mono uppercase tracking-wider transition-all", includeSubdomains ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/50")}>Subdomains {includeSubdomains ? "ON" : "OFF"}</button>
                        </div>
                        <div className="flex items-end justify-center pb-1">
                          <button onClick={() => setUseSitemap(!useSitemap)} className={cn("px-5 py-2.5 text-[12px] font-mono uppercase tracking-wider transition-all", useSitemap ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/50")}>Sitemap {useSitemap ? "ON" : "OFF"}</button>
                        </div>
                      </div>
                    </div>
                  )}
                  {activeEndpoint !== "map" && (
                    <>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                        {[
                          { label: "Main content only", val: onlyMainContent, set: setOnlyMainContent },
                          { label: "Use Proxy", val: useProxy, set: setUseProxy },
                          { label: "Mobile Emulation", val: mobile, set: setMobile },
                        ].map((f) => (
                          <div key={f.label} className="flex items-center justify-between">
                            <label className="text-[13px] font-mono text-white/70">{f.label}</label>
                            <button onClick={() => f.set(!f.val)} className={cn("px-4 py-1.5 text-[11px] font-mono font-bold uppercase tracking-[0.2em] transition-all", f.val ? "bg-white text-black" : "bg-white/[0.04] text-white/40")}>{f.val ? "ON" : "OFF"}</button>
                          </div>
                        ))}
                        <div className="space-y-2">
                          <label className="text-[13px] font-mono text-white/70">Wait after load (ms)</label>
                          <Input type="number" value={waitFor} onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)} placeholder="0" className="h-10 font-mono bg-transparent border-white/10 text-white text-sm placeholder:text-white/20" />
                        </div>
                      </div>
                      {/* HTML mode toggle */}
                      {formats.includes("html") && (
                        <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                          <label className="text-[13px] font-mono text-white/70">HTML Mode</label>
                          <div className="flex gap-2">
                            <button onClick={() => setHtmlMode("cleaned")} className={cn("px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.15em] transition-all", htmlMode === "cleaned" ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/40")}>Cleaned</button>
                            <button onClick={() => setHtmlMode("raw")} className={cn("px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.15em] transition-all", htmlMode === "raw" ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/40")}>Raw</button>
                          </div>
                        </div>
                      )}
                      {/* Screenshot mode toggle */}
                      {formats.includes("screenshot") && (
                        <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                          <label className="text-[13px] font-mono text-white/70">Screenshot Mode</label>
                          <div className="flex gap-2">
                            <button onClick={() => setScreenshotMode("viewport")} className={cn("px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.15em] transition-all", screenshotMode === "viewport" ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/40")}>Viewport</button>
                            <button onClick={() => setScreenshotMode("fullpage")} className={cn("px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.15em] transition-all", screenshotMode === "fullpage" ? "bg-white text-black font-bold" : "bg-white/[0.04] text-white/40")}>Full Page</button>
                          </div>
                        </div>
                      )}
                      {mobile && devicePresets.length > 0 && (
                        <select value={mobileDevice} onChange={(e) => setMobileDevice(e.target.value)} className="w-full h-11 text-[13px] font-mono bg-transparent border border-white/10 text-white/80 px-4">
                          <option value="">Default mobile</option>
                          {devicePresets.map((d: any) => (<option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>))}
                        </select>
                      )}
                    </>
                  )}
                  <div className="space-y-3 pt-4 border-t border-white/[0.08]">
                    <label className="text-[11px] font-mono text-white/40 uppercase tracking-[0.2em]">Webhooks</label>
                    <Input placeholder="https://your-server.com/webhook" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} className="h-11 font-mono bg-transparent border-white/10 text-white placeholder:text-white/20 text-[14px]" />
                    <Input placeholder="webhook-secret" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} className="h-11 font-mono bg-transparent border-white/10 text-white placeholder:text-white/20 text-[14px]" />
                  </div>
                  {activeEndpoint === "scrape" && (
                    <div className="space-y-3 pt-4 border-t border-white/[0.08]">
                      <label className="text-[11px] font-mono text-white/40 uppercase tracking-[0.2em]">Headers & Cookies</label>
                      <textarea className="w-full border border-white/10 bg-transparent px-5 py-3 text-[13px] font-mono text-white/80 placeholder:text-white/20 focus:outline-none focus:border-emerald-500/30 min-h-[60px] resize-none" placeholder='{"Authorization": "Bearer ..."}' value={headersText} onChange={(e) => setHeadersText(e.target.value)} />
                      <textarea className="w-full border border-white/10 bg-transparent px-5 py-3 text-[13px] font-mono text-white/80 placeholder:text-white/20 focus:outline-none focus:border-emerald-500/30 min-h-[60px] resize-none" placeholder='{"session_id": "abc123"}' value={cookiesText} onChange={(e) => setCookiesText(e.target.value)} />
                    </div>
                  )}
                  <div className="space-y-3 pt-4 border-t border-white/[0.08]">
                    <div className="flex items-center justify-between">
                      <label className="text-[13px] font-mono text-white/70 flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-amber-400" /> AI Extraction (BYOK)
                      </label>
                      <button onClick={() => setExtractEnabled(!extractEnabled)} className={cn("px-4 py-1.5 text-[11px] font-mono font-bold uppercase tracking-[0.2em] transition-all", extractEnabled ? "bg-white text-black" : "bg-white/[0.04] text-white/40")}>{extractEnabled ? "ON" : "OFF"}</button>
                    </div>
                    {extractEnabled && (
                      <textarea className="w-full border border-white/10 bg-transparent px-5 py-3 text-[14px] font-mono text-white/80 placeholder:text-white/20 focus:outline-none focus:border-emerald-500/30 min-h-[80px] resize-none" placeholder="Extract product name, price, and description" value={extractPrompt} onChange={(e) => setExtractPrompt(e.target.value)} />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── ACTIVE JOB ── */}
        {activeJob && (
          <section className="px-6 md:px-10 py-12 border-b border-white/[0.06] animate-fade-in">
            <div className="max-w-[1400px] mx-auto">
              <div className="flex items-center gap-3 mb-8">
                <span className="text-[12px] uppercase tracking-[0.25em] text-emerald-500/60 font-mono">Active Job</span>
                <div className="h-px flex-1 bg-emerald-500/10" />
                <span className="text-[11px] text-emerald-500/40 font-mono">{activeJob.status.toUpperCase()}</span>
              </div>

              <div className={cn("border overflow-hidden", activeJob.status === "completed" ? "border-emerald-500/20" : activeJob.status === "failed" || activeJob.status === "cancelled" ? "border-red-500/20" : "border-white/10")}>
                <div className={cn("h-[2px]", activeJob.status === "completed" ? "bg-gradient-to-r from-emerald-600 to-emerald-400" : activeJob.status === "failed" ? "bg-red-500" : "bg-emerald-500/50")} />

                <div className="flex items-center justify-between px-6 md:px-10 py-6 border-b border-white/[0.06]">
                  <div className="flex items-center gap-5 md:gap-6">
                    <div className={cn("h-12 w-12 border grid place-items-center shrink-0", activeJob.status === "completed" ? "border-emerald-500/20 bg-emerald-500/[0.04]" : activeJob.status === "failed" ? "border-red-500/20 bg-red-500/[0.04]" : "border-emerald-500/10 bg-emerald-500/[0.04]")}>
                      {activeJob.status === "running" ? <Loader2 className="h-5 w-5 text-emerald-500 animate-spin" /> : activeJob.status === "completed" ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <XCircle className="h-5 w-5 text-red-400" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-4">
                        <span className="text-[20px] font-bold uppercase tracking-[0.1em] text-white">{activeJob.type}</span>
                        <span className={cn("text-[11px] font-mono uppercase tracking-[0.25em] px-4 py-1 border", activeJob.status === "running" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/15" : activeJob.status === "completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/15" : "bg-red-500/10 text-red-400 border-red-500/20")}>
                          {activeJob.status === "running" ? "Running" : activeJob.status}
                        </span>
                      </div>
                      <span className="text-[14px] font-mono text-white/50 mt-1 block">{activeJob.target}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {activeJob.status === "running" && (
                      <button onClick={async () => { try { await api.cancelJob(activeJob.id); setActiveJob((p: any) => p ? { ...p, status: "cancelled" } : null); } catch {} }} className="h-9 px-3 flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-all"><Square className="h-3.5 w-3.5" /> Stop</button>
                    )}
                    <button onClick={dismissJob} className="h-9 w-9 grid place-items-center text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-all"><X className="h-4 w-4" /></button>
                  </div>
                </div>

                {/* Progress */}
                <div className="px-6 md:px-10 py-6">
                  <div className="flex items-center justify-between text-[13px] font-mono mb-3">
                    <span className="text-white/60">{activeJob.completed} <span className="text-white/30">/</span> {activeJob.total > 0 ? activeJob.total : "—"} pages</span>
                    <span className="text-emerald-400 font-bold text-[24px]">{pct}%</span>
                  </div>
                  <div className="h-1.5 bg-white/[0.06] overflow-hidden">
                    <div className={cn("h-full transition-all duration-500", activeJob.status === "completed" ? "bg-gradient-to-r from-emerald-600 to-emerald-400" : activeJob.status === "failed" ? "bg-red-500" : "bg-emerald-500")} style={{ width: `${activeJob.total > 0 ? Math.min(100, (activeJob.completed / activeJob.total) * 100) : 0}%` }} />
                  </div>
                  {activeJob.error && <div className="mt-4 border border-red-500/20 bg-red-500/[0.05] px-6 py-3 text-[13px] font-mono text-red-400"><span className="text-red-500/60 mr-2 font-bold">ERR</span>{activeJob.error}</div>}

                  {/* Actions */}
                  {activeJob.status === "completed" && (
                    <div className="flex items-center gap-4 mt-6">
                      <button onClick={handleDownloadActiveJob} className="flex items-center gap-2 bg-white text-black px-8 py-3.5 text-[13px] font-mono font-bold uppercase tracking-[0.15em] hover:bg-emerald-400 transition-colors">
                        <Download className="h-4 w-4" /> Export JSON
                      </button>
                      <Link href={getJobDetailPath({ id: activeJob.id, type: activeJob.type })} className="flex items-center gap-2 border border-white/10 text-white/50 px-8 py-3.5 text-[13px] font-mono uppercase tracking-[0.15em] hover:text-white/80 hover:border-white/20 transition-all">
                        <ExternalLink className="h-4 w-4" /> View Full Results
                      </Link>
                    </div>
                  )}
                  {(activeJob.status === "failed" || activeJob.status === "cancelled") && (
                    <div className="flex items-center gap-3 mt-6">
                      <button onClick={async () => { try { const res = await api.retryJob(activeJob.id); setActiveJob({ id: res.new_job_id, type: activeJob.type, status: "running", target: activeJob.target, completed: 0, total: activeJob.total || 0, data: [], error: undefined }); } catch {} }} className="flex items-center gap-2 bg-white text-black px-8 py-3.5 text-[13px] font-mono font-bold uppercase tracking-[0.15em] hover:bg-emerald-400 transition-colors"><RefreshCw className="h-4 w-4" /> Retry</button>
                      <Link href={getJobDetailPath({ id: activeJob.id, type: activeJob.type })} className="flex items-center gap-2 border border-white/10 text-white/50 px-8 py-3.5 text-[13px] font-mono uppercase tracking-[0.15em] hover:text-white/80 hover:border-white/20 transition-all"><ExternalLink className="h-4 w-4" /> Details</Link>
                    </div>
                  )}
                </div>

                {/* Inline results */}
                {activeJob.data && activeJob.data.length > 0 && activeJob.type !== "map" && (
                  <div className="border-t border-white/[0.08]">
                    <div className="px-6 md:px-10 py-4 flex items-center justify-between bg-white/[0.01]">
                      <div className="flex items-center gap-3">
                        <Globe className="h-4 w-4 text-emerald-500/60" />
                        <span className="text-[12px] font-mono font-bold text-white/50 uppercase tracking-[0.2em]">{activeJob.data.length} {activeJob.data.length === 1 ? "result" : "results"}</span>
                      </div>
                      {activeJob.status === "running" && <div className="flex items-center gap-2 text-[11px] font-mono text-emerald-400/60 uppercase tracking-[0.2em]"><div className="h-2 w-2 bg-emerald-400 animate-pulse" /> Live</div>}
                    </div>
                    <div className="px-4 md:px-6 pb-6 space-y-2 max-h-[600px] overflow-auto">
                      {activeJob.data.map((page: any, i: number) => <InlineResultCard key={page.id || page.url || i} page={page} index={i} jobId={activeJob.id} />)}
                    </div>
                  </div>
                )}
                {activeJob.data && activeJob.data.length > 0 && activeJob.type === "map" && (
                  <div className="border-t border-white/[0.08]">
                    <div className="px-6 md:px-10 py-4 flex items-center gap-3 bg-white/[0.01]">
                      <Network className="h-4 w-4 text-emerald-500/60" />
                      <span className="text-[12px] font-mono font-bold text-white/50 uppercase tracking-[0.2em]">{activeJob.data.length} URLs</span>
                    </div>
                    <div className="max-h-[400px] overflow-auto">
                      {activeJob.data.map((link: any, i: number) => (
                        <div key={i} className="flex items-center justify-between px-6 md:px-8 py-3 hover:bg-white/[0.02] group transition-colors border-b border-white/[0.04] last:border-0">
                          <a href={link.url || link} target="_blank" rel="noopener noreferrer" className="text-[14px] font-mono text-emerald-400 hover:text-emerald-300 truncate">{link.url || link}</a>
                          <ExternalLink className="h-3.5 w-3.5 text-white/15 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-3" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* ── MAP RESULTS ── */}
        {activeEndpoint === "map" && mapResult && (
          <section className="px-6 md:px-10 py-12 border-b border-white/[0.06] animate-fade-in">
            <div className="max-w-[1400px] mx-auto">
              <div className="border border-white/10 overflow-hidden">
                <div className="h-[2px] bg-gradient-to-r from-emerald-600 to-emerald-400" />
                <div className="flex items-center justify-between px-6 md:px-8 py-4 border-b border-white/[0.08]">
                  <div className="flex items-center gap-3">
                    <Network className="h-5 w-5 text-emerald-500/60" />
                    <span className="text-[14px] font-mono font-bold text-white/70 uppercase tracking-[0.15em]">Sitemap</span>
                    <span className="text-[14px] font-mono text-emerald-400 font-bold">{mapResult.total}</span>
                  </div>
                  <button onClick={copyMapUrls} className="flex items-center gap-2 px-4 py-2 text-[12px] font-mono uppercase tracking-wider border border-white/10 text-white/40 hover:text-white/70 hover:bg-white/[0.03] transition-all">
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />} Copy All
                  </button>
                </div>
                <div className="max-h-[400px] overflow-auto">
                  {mapResult.links?.map((link: any, i: number) => (
                    <div key={i} className="flex items-center justify-between px-6 md:px-8 py-3 hover:bg-white/[0.02] group transition-colors border-b border-white/[0.04] last:border-0">
                      <div className="min-w-0 flex-1">
                        <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-[14px] font-mono text-emerald-400 hover:text-emerald-300 truncate block">{link.url}</a>
                        {link.title && <p className="text-[12px] text-white/35 truncate">{link.title}</p>}
                      </div>
                      <a href={link.url} target="_blank" rel="noopener noreferrer" className="opacity-0 group-hover:opacity-100 ml-3 transition-opacity"><ExternalLink className="h-3.5 w-3.5 text-white/30" /></a>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── RECENT RUNS ── */}
        {hasRuns && (
          <section className="px-6 md:px-10 py-16">
            <div className="max-w-[1400px] mx-auto">
              <div className="flex items-center justify-between mb-10">
                <div className="flex items-center gap-3">
                  <span className="text-[12px] font-mono text-white/40 uppercase tracking-[0.25em]">Recent Activity</span>
                  <div className="h-px w-16 bg-white/[0.06]" />
                </div>
                <Link href="/jobs" className="text-[12px] font-mono text-white/30 hover:text-white/60 transition-colors uppercase tracking-[0.2em]">View All →</Link>
              </div>
              <div className="grid gap-px md:grid-cols-2 lg:grid-cols-3 bg-white/[0.06]">
                {recentJobs.map((job) => {
                  const jobUrl = getJobUrl(job);
                  const domain = getDomain(jobUrl);
                  const TypeIcon = getTypeIcon(job.type);
                  const { date, time } = job.created_at ? formatDate(job.created_at) : { date: "", time: "" };
                  const jobFormats: string[] = job.config?.formats || [];
                  const isCompleted = job.status === "completed";
                  return (
                    <div key={job.id} className="bg-[#050505] group">
                      <Link href={getJobDetailPath(job)} className="block p-8 md:p-10 hover:bg-white/[0.02] transition-all">
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-2.5">
                            <TypeIcon className={cn("h-4 w-4", getTypeColor(job.type))} />
                            <span className={cn("text-[11px] font-mono font-bold uppercase tracking-[0.25em]", getTypeColor(job.type))}>{job.type}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className={cn("h-2.5 w-2.5", job.status === "completed" ? "bg-emerald-400" : job.status === "failed" ? "bg-red-400" : job.status === "running" ? "bg-amber-400 animate-pulse" : "bg-white/30")} />
                            <span className="text-[11px] font-mono text-white/35 uppercase tracking-wider">{job.status === "completed" ? "Done" : job.status}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 mb-5">
                          {jobUrl && !jobUrl.includes("URLs") && <img src={getFavicon(jobUrl)} alt="" className="h-6 w-6 shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />}
                          <span className="text-[18px] font-mono font-medium text-white/80 truncate">{domain || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2 text-white/30 mb-5">
                          <Clock className="h-3.5 w-3.5" />
                          <span className="text-[12px] font-mono">{date} {time}</span>
                        </div>
                        {jobFormats.length > 0 && (
                          <div className="flex flex-wrap gap-2 mb-8">
                            {jobFormats.slice(0, 4).map((fmt: string) => {
                              const fmtInfo = formatIcons[fmt];
                              return <span key={fmt} className="px-3 py-1.5 text-[10px] font-mono text-white/30 uppercase tracking-[0.2em] border border-white/[0.06]">{fmtInfo?.label || fmt}</span>;
                            })}
                            {jobFormats.length > 4 && <span className="text-[10px] font-mono text-white/25 self-center">+{jobFormats.length - 4}</span>}
                          </div>
                        )}
                      </Link>
                      {isCompleted && (
                        <div className="px-8 md:px-10 pb-6">
                          <button onClick={(e) => { e.preventDefault(); handleDownload(job); }} className="flex items-center justify-center gap-2.5 w-full py-3 text-[11px] font-mono font-bold uppercase tracking-[0.2em] border border-white/10 text-white/40 hover:bg-white/[0.04] hover:text-white/70 hover:border-white/20 transition-all">
                            <Download className="h-3.5 w-3.5" /> Export
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        )}

        {!hasRuns && jobsLoaded && (
          <section className="px-6 md:px-10 py-20">
            <div className="max-w-[1400px] mx-auto text-center">
              <p className="text-[14px] font-mono text-white/40 uppercase tracking-[0.2em]">No runs yet — enter a URL above to get started</p>
            </div>
          </section>
        )}
      </main>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-white/[0.06]">
        <div className="flex flex-col md:flex-row items-center justify-between px-6 md:px-10 max-w-[1400px] mx-auto py-8 gap-4">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-3 w-3 bg-gradient-to-br from-emerald-400 to-cyan-500" />
            <span className="text-[14px] font-bold uppercase tracking-[0.1em] text-white/50 font-mono">WebHarvest</span>
          </Link>
          <div className="flex items-center gap-8">
            <Link href="/docs" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">Documentation</Link>
            <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">GitHub</a>
            <Link href="/docs" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">API Reference</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function PlaygroundPage() {
  return (<Suspense fallback={null}><PlaygroundContent /></Suspense>);
}
