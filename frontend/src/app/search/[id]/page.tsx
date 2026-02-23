"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import {
  Loader2,
  ArrowLeft,
  Search,
  FileText,
  ExternalLink,
  Code,
  Image as ImageIcon,
  Link2,
  Camera,
  Braces,
  List,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Globe,
  Clock,
  FileCode,
  ArrowUpRight,
  ArrowDownLeft,
  Sparkles,
  LayoutGrid,
  Table2,
  Copy,
  Check,
} from "lucide-react";
import Link from "next/link";

type TabType = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract";

function SearchResultCard({ item, index, jobId }: { item: any; index: number; jobId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("markdown");
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);

  const hasMarkdown = !!item.markdown;
  const hasHtml = !!item.html;
  const hasScreenshot = !!item.screenshot;
  const hasLinks = item.links?.length > 0 || item.links_detail;
  const hasStructured = item.structured_data && Object.keys(item.structured_data).length > 0;
  const hasHeadings = item.headings?.length > 0;
  const hasImages = item.images?.length > 0;
  const hasExtract = !!item.extract;

  const loadScreenshot = useCallback(async () => {
    if (screenshotData || screenshotLoading) return;
    setScreenshotLoading(true);
    try {
      const detail = await api.getJobResultDetail(jobId, item.id);
      if (detail.screenshot) {
        setScreenshotData(detail.screenshot);
      }
    } catch {
      // Silently fail for search result items
    } finally {
      setScreenshotLoading(false);
    }
  }, [jobId, item.id, screenshotData, screenshotLoading]);

  const tabs: { id: TabType; label: string; icon: any; available: boolean }[] = [
    { id: "markdown", label: "Markdown", icon: FileText, available: hasMarkdown },
    { id: "html", label: "HTML", icon: Code, available: hasHtml },
    { id: "screenshot", label: "Screenshot", icon: Camera, available: hasScreenshot },
    { id: "links", label: "Links", icon: Link2, available: hasLinks },
    { id: "structured", label: "Structured Data", icon: Braces, available: hasStructured },
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

  // Auto-load screenshot when tab is selected
  useEffect(() => {
    if (activeTab === "screenshot" && hasScreenshot && !screenshotData && !screenshotLoading) {
      loadScreenshot();
    }
  }, [activeTab]);

  const wordCount = item.metadata?.word_count || 0;

  return (
    <div className="border border-white/10 bg-white/[0.02] overflow-hidden">
      <div
        className="flex items-start gap-3 p-4 cursor-pointer hover:bg-white/[0.03] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-white/30 font-mono w-6 shrink-0 text-right mt-1">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {item.success ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
            )}
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-amber-400 hover:text-amber-300 truncate flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              {item.title || item.url}
              <ExternalLink className="h-3 w-3 shrink-0 opacity-50" />
            </a>
          </div>
          <p className="text-xs text-white/40 mt-0.5 truncate">{item.url}</p>
          {item.snippet && (
            <p className="text-xs text-white/40 mt-1 line-clamp-2">{item.snippet}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {wordCount > 0 && (
            <span className="text-xs border border-white/20 text-white/50 px-2 py-0.5 rounded-md">
              {wordCount.toLocaleString()} words
            </span>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-white/40" />
          ) : (
            <ChevronDown className="h-4 w-4 text-white/40" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10">
          {item.error && (
            <div className="mx-4 mt-4 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
              {item.error}
            </div>
          )}

          {/* Tab bar */}
          <div className="flex gap-1 p-2 border-b border-white/10 bg-white/[0.02] overflow-x-auto">
            {availableTabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? "border-amber-500 text-amber-400 bg-amber-500/[0.03]"
                      : "text-white/40 hover:text-white/70"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab content */}
          <div className="p-4">
            {activeTab === "markdown" && hasMarkdown && (
              <pre className="max-h-96 overflow-auto text-xs text-white/70 whitespace-pre-wrap font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-4">
                {item.markdown}
              </pre>
            )}

            {activeTab === "html" && hasHtml && (
              <pre className="max-h-96 overflow-auto text-xs text-white/70 whitespace-pre-wrap font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-4">
                {item.html}
              </pre>
            )}

            {activeTab === "screenshot" && (
              <div className="flex justify-center">
                {screenshotData ? (
                  <img
                    src={`data:image/jpeg;base64,${screenshotData}`}
                    alt={`Screenshot of ${item.url}`}
                    className="max-w-full rounded-md border border-white/10 shadow-lg"
                    style={{ maxHeight: "600px" }}
                  />
                ) : screenshotLoading ? (
                  <div className="flex flex-col items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-white/40 mb-2" />
                    <p className="text-sm text-white/40">Loading screenshot...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12">
                    <Camera className="h-10 w-10 text-white/20 mb-3" />
                    <button
                      onClick={loadScreenshot}
                      className="flex items-center gap-2 px-4 py-2 rounded-md border border-white/20 text-sm font-medium text-white/50 hover:text-white hover:border-white/40 transition-colors"
                    >
                      <Camera className="h-4 w-4" />
                      Load Screenshot
                    </button>
                    <p className="text-xs text-white/40 mt-2">Screenshots are loaded on demand</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === "links" && hasLinks && (
              <div className="space-y-4">
                {item.links_detail && (
                  <div className="flex gap-4 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Link2 className="h-4 w-4 text-white/40" />
                      <span className="font-medium text-white/70">{item.links_detail.total}</span>
                      <span className="text-white/40">total</span>
                    </div>
                    {item.links_detail.internal && (
                      <div className="flex items-center gap-1.5">
                        <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                        <span className="font-medium text-white/70">{item.links_detail.internal.count}</span>
                        <span className="text-white/40">internal</span>
                      </div>
                    )}
                    {item.links_detail.external && (
                      <div className="flex items-center gap-1.5">
                        <ArrowUpRight className="h-4 w-4 text-orange-400" />
                        <span className="font-medium text-white/70">{item.links_detail.external.count}</span>
                        <span className="text-white/40">external</span>
                      </div>
                    )}
                  </div>
                )}
                {item.links_detail?.internal?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Internal Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {item.links_detail.internal.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-amber-400 hover:text-amber-300 truncate">{link.url}</a>
                          {link.text && <span className="text-white/40 truncate shrink-0 max-w-48">&quot;{link.text}&quot;</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.links_detail?.external?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">External Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {item.links_detail.external.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-amber-400 hover:text-amber-300 truncate">{link.url}</a>
                          {link.text && <span className="text-white/40 truncate shrink-0 max-w-48">&quot;{link.text}&quot;</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {!item.links_detail && item.links && (
                  <div className="space-y-1 max-h-64 overflow-auto">
                    {item.links.map((link: string, i: number) => (
                      <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-xs text-amber-400 hover:text-amber-300 truncate">{link}</a>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "structured" && hasStructured && (
              <div className="space-y-4">
                {item.structured_data.json_ld && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">JSON-LD (Schema.org)</h4>
                    <pre className="max-h-64 overflow-auto text-xs font-mono bg-[#0a0a0a] border border-white/10 text-white/70 rounded-md p-3">
                      {JSON.stringify(item.structured_data.json_ld, null, 2)}
                    </pre>
                  </div>
                )}
                {item.structured_data.open_graph && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">OpenGraph</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(item.structured_data.open_graph).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-white/40">og:{key}:</span> <span className="font-mono text-white/70">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.structured_data.twitter_card && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Twitter Card</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(item.structured_data.twitter_card).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-white/40">twitter:{key}:</span> <span className="font-mono text-white/70">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.structured_data.meta_tags && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Meta Tags</h4>
                    <div className="space-y-1 max-h-48 overflow-auto">
                      {Object.entries(item.structured_data.meta_tags).map(([key, val]) => (
                        <div key={key} className="text-xs font-mono">
                          <span className="text-white/40">{key}:</span> <span className="text-white/70">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "headings" && hasHeadings && (
              <div className="space-y-1">
                {item.headings.map((h: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs" style={{ paddingLeft: `${(h.level - 1) * 16}px` }}>
                    <span className="text-[10px] px-1.5 py-0 shrink-0 border border-white/20 text-white/50 rounded-md">H{h.level}</span>
                    <span className={`text-white/70 ${h.level === 1 ? "font-semibold" : ""}`}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {item.images.map((img: any, i: number) => (
                  <div key={i} className="border border-white/10 rounded-md overflow-hidden">
                    <div className="aspect-video bg-white/[0.02] flex items-center justify-center">
                      <img src={img.src} alt={img.alt || ""} className="max-w-full max-h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                    </div>
                    <div className="p-2">
                      <p className="text-xs text-white/40 truncate" title={img.src}>{img.src.split("/").pop()}</p>
                      {img.alt && <p className="text-xs text-white/70 truncate mt-0.5">{img.alt}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "extract" && hasExtract && (
              <pre className="max-h-96 overflow-auto text-xs text-white/70 whitespace-pre-wrap font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-4">
                {JSON.stringify(item.extract, null, 2)}
              </pre>
            )}

          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchStatusPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(true);
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">("all");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [tsvCopied, setTsvCopied] = useState(false);

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    fetchStatus();
  }, [jobId]);

  // SSE for real-time updates — falls back to polling on failure
  useEffect(() => {
    if (!polling || !jobId) return;
    if (status && ["completed", "failed", "cancelled"].includes(status.status)) {
      setPolling(false);
      return;
    }

    const token = api.getToken();
    if (!token) return;

    const { API_BASE_URL } = require("@/lib/api");
    const url = `${API_BASE_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;

    try {
      const es = new EventSource(url);
      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          fetchStatus();
          if (data.done || ["completed", "failed", "cancelled"].includes(data.status)) {
            setPolling(false);
            es.close();
          }
        } catch {}
      };
      es.onerror = () => {
        es.close();
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
      };
      return () => es.close();
    } catch {
      const interval = setInterval(fetchStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [polling, status?.status]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.getSearchStatus(jobId);
      setStatus(res);
      if (["completed", "failed", "cancelled"].includes(res.status)) {
        setPolling(false);
      }
    } catch (err: any) {
      setError(err.message);
      setPolling(false);
    }
  }, [jobId]);

  const handleExport = async (format: "zip" | "json" | "csv") => {
    try {
      await api.downloadSearchExport(jobId, format);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const isRunning = status?.status === "running" || status?.status === "pending";
  const progressPercent =
    status?.total_results > 0
      ? Math.min(100, Math.round((status.completed_results / status.total_results) * 100))
      : 0;

  const successCount = useMemo(() => status?.data?.filter((d: any) => d.success)?.length || 0, [status?.data]);
  const failCount = useMemo(() => status?.data?.filter((d: any) => !d.success)?.length || 0, [status?.data]);
  const totalWords = useMemo(() => status?.data?.reduce((sum: number, d: any) => sum + (d.metadata?.word_count || 0), 0) || 0, [status?.data]);
  const screenshotCount = useMemo(() => status?.data?.filter((d: any) => d.screenshot)?.length || 0, [status?.data]);

  const filteredData = useMemo(() => {
    if (!status?.data) return [];
    let data = status.data.map((d: any, i: number) => ({ ...d, _index: i }));
    if (searchFilter) {
      const q = searchFilter.toLowerCase();
      data = data.filter((d: any) => d.url?.toLowerCase().includes(q) || d.title?.toLowerCase().includes(q));
    }
    if (statusFilter === "success") {
      data = data.filter((d: any) => d.success);
    } else if (statusFilter === "error") {
      data = data.filter((d: any) => !d.success);
    }
    return data;
  }, [status?.data, searchFilter, statusFilter]);

  return (
    <PageLayout activePage="">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 py-10">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/search">
            <button className="border border-white/20 p-2 text-white/50 hover:text-white hover:border-white/40 transition-colors">
              <ArrowLeft className="h-4 w-4" />
            </button>
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text">Search Results</h1>
            {status?.query && (
              <p className="text-sm mt-0.5">
                <span className="text-white/50">Query:</span> <span className="text-white font-mono">&quot;{status.query}&quot;</span>
              </p>
            )}
            <p className="text-[13px] text-white/40 font-mono">{jobId}</p>
          </div>
        </div>

        {error && (
          <div className="border border-red-500/30 bg-red-500/10 mb-6 p-4 rounded-md">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {!status && !error && (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
            <p className="text-sm text-white/40">Loading search status...</p>
          </div>
        )}

        {status && (
          <>
            <div className="border border-white/10 bg-white/[0.02] mb-6 p-6 rounded-md relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-500 to-emerald-500" />
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span
                    className={`text-sm px-3 py-1 rounded-md border font-medium inline-flex items-center ${
                      status.status === "completed"
                        ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                        : status.status === "failed"
                        ? "border-red-500/30 text-red-400 bg-red-500/10"
                        : "border-amber-500/30 text-amber-400 bg-amber-500/10"
                    }`}
                  >
                    {isRunning && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                    {isRunning ? "Searching & scraping..." : status.status}
                  </span>
                </div>
                {status.data && status.data.length > 0 && (
                  <ExportDropdown onExport={handleExport} />
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white/50 text-[12px] font-mono">
                    {status.completed_results} of {status.total_results} results scraped
                  </span>
                  {progressPercent > 0 && (
                    <span className="text-white/50 text-[12px] font-mono">{progressPercent}%</span>
                  )}
                </div>
                <div className="w-full h-2 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isRunning ? "bg-amber-500" : status.status === "completed" ? "bg-emerald-500" : "bg-red-500"
                    }`}
                    style={{ width: `${status.status === "completed" ? 100 : progressPercent}%` }}
                  />
                </div>
              </div>

              {/* Stats row */}
              {status.data && status.data.length > 0 && (
                <div className="flex gap-6 mt-4 pt-4 border-t border-white/10 text-white/50 text-[12px] font-mono">
                  <div className="flex items-center gap-1.5">
                    <Globe className="h-3.5 w-3.5" />
                    <span>{status.data.length} results</span>
                  </div>
                  {successCount > 0 && (
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      <span>{successCount} succeeded</span>
                    </div>
                  )}
                  {failCount > 0 && (
                    <div className="flex items-center gap-1.5">
                      <XCircle className="h-3.5 w-3.5 text-red-400" />
                      <span>{failCount} failed</span>
                    </div>
                  )}
                  {totalWords > 0 && (
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5" />
                      <span>{totalWords.toLocaleString()} total words</span>
                    </div>
                  )}
                  {screenshotCount > 0 && (
                    <div className="flex items-center gap-1.5">
                      <Camera className="h-3.5 w-3.5" />
                      <span>{screenshotCount} screenshots</span>
                    </div>
                  )}
                </div>
              )}

              {status.error && (
                <div className="mt-4 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                  {status.error}
                </div>
              )}
            </div>

            {/* Filter Bar */}
            {status.data && status.data.length > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" />
                  <input
                    placeholder="Filter by URL..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="w-full pl-9 h-9 bg-transparent border border-white/10 text-white font-mono text-sm rounded-md px-3 placeholder:text-white/30 focus:outline-none focus:border-white/30 transition-colors"
                  />
                </div>
                <div className="flex gap-1">
                  {(["all", "success", "error"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setStatusFilter(f)}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        statusFilter === f
                          ? "bg-white text-black"
                          : "bg-white/[0.03] text-white/40 hover:text-white/70"
                      }`}
                    >
                      {f === "all" ? "All" : f === "success" ? "Success" : "Errors"}
                    </button>
                  ))}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => setViewMode("cards")}
                    className={`p-1.5 rounded-md transition-colors ${
                      viewMode === "cards"
                        ? "bg-white text-black"
                        : "bg-white/[0.03] text-white/40 hover:text-white/70"
                    }`}
                    title="Card view"
                  >
                    <LayoutGrid className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setViewMode("table")}
                    className={`p-1.5 rounded-md transition-colors ${
                      viewMode === "table"
                        ? "bg-white text-black"
                        : "bg-white/[0.03] text-white/40 hover:text-white/70"
                    }`}
                    title="Table view"
                  >
                    <Table2 className="h-4 w-4" />
                  </button>
                </div>
                <span className="text-xs text-white/40 font-mono">
                  {filteredData.length} of {status.data.length} results
                </span>
              </div>
            )}

            {status.data && status.data.length > 0 ? (
              <div className="space-y-3">
                <h2 className="text-lg font-semibold flex items-center gap-2 mb-3 text-white font-mono">
                  <Globe className="h-5 w-5" />
                  Search Results
                </h2>

                {viewMode === "table" ? (
                  <div>
                    <div className="flex justify-end mb-2">
                      <button
                        onClick={() => {
                          const header = ["#", "URL", "Title", "Status", "Snippet", "Words", "Status Code"].join("\t");
                          const rows = filteredData.map((d: any) => [
                            d._index + 1,
                            d.url || "",
                            d.title || "",
                            d.success ? "Success" : "Error",
                            (d.snippet || "").replace(/[\t\n]/g, " "),
                            d.metadata?.word_count || 0,
                            d.metadata?.status_code || "",
                          ].join("\t"));
                          navigator.clipboard.writeText([header, ...rows].join("\n"));
                          setTsvCopied(true);
                          setTimeout(() => setTsvCopied(false), 2000);
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white/30 hover:text-white transition-colors"
                      >
                        {tsvCopied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                        {tsvCopied ? "Copied!" : "Copy Table"}
                      </button>
                    </div>
                    <div className="rounded-md border border-white/10 overflow-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono w-10">#</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono">URL</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono">Title</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono w-16">Status</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono max-w-[200px]">Snippet</th>
                            <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-white/40 font-mono w-20">Words</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono w-20">Code</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredData.map((item: any) => (
                            <tr key={item._index} className="border-b border-white/[0.06] last:border-0 hover:bg-white/[0.03] transition-colors">
                              <td className="px-3 py-2 text-xs text-white/40 font-mono">{item._index + 1}</td>
                              <td className="px-3 py-2 max-w-xs">
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-amber-400 hover:text-amber-300 truncate block"
                                >
                                  {item.url}
                                </a>
                              </td>
                              <td className="px-3 py-2 text-xs text-white/40 truncate max-w-[200px]">
                                {item.title || "\u2014"}
                              </td>
                              <td className="px-3 py-2">
                                {item.success ? (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                                ) : (
                                  <XCircle className="h-3.5 w-3.5 text-red-400" />
                                )}
                              </td>
                              <td className="px-3 py-2 text-xs text-white/40 truncate max-w-[200px]">
                                {item.snippet || "\u2014"}
                              </td>
                              <td className="px-3 py-2 text-xs text-white/40 text-right font-mono">
                                {item.metadata?.word_count > 0 ? item.metadata.word_count.toLocaleString() : "\u2014"}
                              </td>
                              <td className="px-3 py-2">
                                {item.metadata?.status_code && (
                                  <span
                                    className={`text-[10px] px-1.5 py-0.5 rounded-md border ${
                                      item.metadata.status_code >= 200 && item.metadata.status_code < 400
                                        ? "border-emerald-500/30 text-emerald-400"
                                        : item.metadata.status_code >= 400
                                        ? "border-red-500/30 text-red-400"
                                        : "border-white/20 text-white/50"
                                    }`}
                                  >
                                    {item.metadata.status_code}
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <>
                    {filteredData.map((item: any) => (
                      <SearchResultCard key={item._index} item={item} index={item._index} jobId={jobId} />
                    ))}
                  </>
                )}
              </div>
            ) : isRunning ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
                <p className="text-sm text-white/40">
                  Searching the web and scraping results...
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Search className="h-12 w-12 text-white/20 mb-4" />
                <p className="text-sm text-white/40">No results found.</p>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
