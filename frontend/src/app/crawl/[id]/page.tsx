"use client";

import { useState, useEffect, useCallback, memo, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import {
  Loader2,
  StopCircle,
  ArrowLeft,
  Globe,
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
  Clock,
  FileCode,
  ArrowUpRight,
  ArrowDownLeft,
  Sparkles,
  Search,
  LayoutGrid,
  Table2,
  Copy,
  Check,
} from "lucide-react";
import Link from "next/link";

type TabType = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract";

const PageResultCard = memo(function PageResultCard({ page, index, jobId }: { page: any; index: number; jobId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("markdown");
  // Heavy fields (screenshot, html) are loaded on demand via detail endpoint.
  // The paginated response sends "available" markers instead of full data.
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [htmlData, setHtmlData] = useState<string | null>(null);
  const [htmlLoading, setHtmlLoading] = useState(false);

  const hasMarkdown = !!page.markdown;
  const hasHtml = !!page.html;
  const hasScreenshot = !!page.screenshot;
  const hasLinks = page.links?.length > 0 || page.links_detail;
  const hasStructured = page.structured_data && Object.keys(page.structured_data).length > 0;
  const hasHeadings = page.headings?.length > 0;
  const hasImages = page.images?.length > 0;
  const hasExtract = !!page.extract;

  const loadDetail = useCallback(async (field: "screenshot" | "html") => {
    if (!page.id) return;
    if (field === "screenshot" && (screenshotData || screenshotLoading)) return;
    if (field === "html" && (htmlData || htmlLoading)) return;
    if (field === "screenshot") setScreenshotLoading(true);
    else setHtmlLoading(true);
    try {
      const detail = await api.getJobResultDetail(jobId, page.id);
      if (field === "screenshot") setScreenshotData(detail.screenshot || null);
      else setHtmlData(detail.html || null);
    } catch {
      if (field === "screenshot") setScreenshotData(null);
      else setHtmlData(null);
    } finally {
      if (field === "screenshot") setScreenshotLoading(false);
      else setHtmlLoading(false);
    }
  }, [jobId, page.id, screenshotData, screenshotLoading, htmlData, htmlLoading]);

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

  // Auto-select first available tab
  useEffect(() => {
    if (!availableTabs.find((t) => t.id === activeTab)) {
      setActiveTab(availableTabs[0]?.id || "markdown");
    }
  }, []);

  // Auto-load HTML and screenshot when their tab is selected
  useEffect(() => {
    if (activeTab === "html" && hasHtml && !htmlData && !htmlLoading) {
      loadDetail("html");
    }
    if (activeTab === "screenshot" && hasScreenshot && !screenshotData && !screenshotLoading) {
      loadDetail("screenshot");
    }
  }, [activeTab]);

  const linksSummary = page.links_detail || (page.links ? { total: page.links.length } : null);
  const wordCount = page.metadata?.word_count || 0;
  const readingTime = page.metadata?.reading_time_seconds
    ? Math.ceil(page.metadata.reading_time_seconds / 60)
    : 0;

  return (
    <div className="border border-white/10 bg-white/[0.02] overflow-hidden">
      {/* Header - always visible */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-white/[0.03] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-white/30 font-mono w-6 shrink-0 text-right">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <a
              href={page.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-violet-400 hover:text-violet-300 truncate flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              {page.url}
              <ExternalLink className="h-3 w-3 shrink-0 opacity-50" />
            </a>
          </div>
          {page.metadata?.title && (
            <p className="text-xs text-white/40 mt-0.5 truncate">
              {page.metadata.title}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasScreenshot && (
            <span className="inline-flex items-center gap-1 rounded-md border border-white/20 px-2 py-0.5 text-[11px] font-mono text-white/50">
              <Camera className="h-3 w-3" />
            </span>
          )}
          {wordCount > 0 && (
            <span className="inline-flex items-center rounded-md border border-white/20 px-2 py-0.5 text-[11px] font-mono text-white/50">
              {wordCount.toLocaleString()} words
            </span>
          )}
          {readingTime > 0 && (
            <span className="inline-flex items-center gap-1 rounded-md border border-white/20 px-2 py-0.5 text-[11px] font-mono text-white/50">
              <Clock className="h-3 w-3" />
              {readingTime}m
            </span>
          )}
          <span
            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-mono ${
              page.metadata?.status_code === 200
                ? "border-emerald-500/30 text-emerald-400"
                : page.metadata?.status_code >= 400
                ? "border-red-500/30 text-red-400"
                : "border-white/20 text-white/50"
            }`}
          >
            {page.metadata?.status_code || "?"}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-white/40" />
          ) : (
            <ChevronDown className="h-4 w-4 text-white/40" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-white/10">
          {/* Summary bar */}
          {(page.metadata || page.structured_data) && (
            <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02] space-y-2">
              {(page.structured_data?.open_graph?.description || page.structured_data?.meta_tags?.description) && (
                <p className="text-xs text-white/50 line-clamp-2">
                  {page.structured_data?.open_graph?.description || page.structured_data?.meta_tags?.description}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {page.metadata?.language && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    {page.metadata.language}
                  </span>
                )}
                {page.metadata?.canonical_url && page.metadata.canonical_url !== page.url && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40 truncate max-w-xs">
                    canonical: {page.metadata.canonical_url}
                  </span>
                )}
                {page.structured_data?.open_graph?.type && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    og:{page.structured_data.open_graph.type}
                  </span>
                )}
                {page.structured_data?.twitter_card?.card && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    twitter:{page.structured_data.twitter_card.card}
                  </span>
                )}
                {page.structured_data?.json_ld?.length > 0 && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    {page.structured_data.json_ld.length} JSON-LD
                  </span>
                )}
                {page.headings?.length > 0 && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    {page.headings.length} headings
                  </span>
                )}
                {page.images?.length > 0 && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    {page.images.length} images
                  </span>
                )}
                {(page.links_detail?.total || page.links?.length) > 0 && (
                  <span className="text-[10px] font-mono px-2 py-0.5 border border-white/10 text-white/40">
                    {page.links_detail?.total || page.links?.length} links
                  </span>
                )}
              </div>
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
                      ? "border-violet-500 text-violet-400 bg-violet-500/[0.03]"
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
                {page.markdown}
              </pre>
            )}

            {activeTab === "html" && hasHtml && (
              <div>
                {htmlData ? (
                  <pre className="max-h-96 overflow-auto text-xs text-white/70 whitespace-pre-wrap font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-4">
                    {htmlData}
                  </pre>
                ) : (
                  <div className="flex items-center gap-2 py-8 text-white/40 justify-center">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">Loading HTML...</span>
                  </div>
                )}
              </div>
            )}

            {activeTab === "screenshot" && hasScreenshot && (
              <div className="flex justify-center">
                {screenshotData ? (
                  <img
                    src={`data:image/jpeg;base64,${screenshotData}`}
                    alt={`Screenshot of ${page.url}`}
                    className="max-w-full rounded-md border border-white/10 shadow-lg"
                    style={{ maxHeight: "600px" }}
                  />
                ) : (
                  <div className="flex items-center gap-2 py-8 text-white/40">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">Loading screenshot...</span>
                  </div>
                )}
              </div>
            )}

            {activeTab === "links" && hasLinks && (
              <div className="space-y-4">
                {page.links_detail && (
                  <div className="flex gap-4 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Link2 className="h-4 w-4 text-white/40" />
                      <span className="font-medium text-white">{page.links_detail.total}</span>
                      <span className="text-white/40">total</span>
                    </div>
                    {page.links_detail.internal && (
                      <div className="flex items-center gap-1.5">
                        <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                        <span className="font-medium text-white">{page.links_detail.internal.count}</span>
                        <span className="text-white/40">internal</span>
                      </div>
                    )}
                    {page.links_detail.external && (
                      <div className="flex items-center gap-1.5">
                        <ArrowUpRight className="h-4 w-4 text-orange-400" />
                        <span className="font-medium text-white">{page.links_detail.external.count}</span>
                        <span className="text-white/40">external</span>
                      </div>
                    )}
                  </div>
                )}

                {page.links_detail?.internal?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Internal Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {page.links_detail.internal.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-violet-400 hover:text-violet-300 truncate"
                          >
                            {link.url}
                          </a>
                          {link.text && (
                            <span className="text-white/40 truncate shrink-0 max-w-48">
                              &quot;{link.text}&quot;
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {page.links_detail?.external?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">External Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {page.links_detail.external.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-violet-400 hover:text-violet-300 truncate"
                          >
                            {link.url}
                          </a>
                          {link.text && (
                            <span className="text-white/40 truncate shrink-0 max-w-48">
                              &quot;{link.text}&quot;
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Fallback to simple links list */}
                {!page.links_detail && page.links && (
                  <div className="space-y-1 max-h-64 overflow-auto">
                    {page.links.map((link: string, i: number) => (
                      <div key={i} className="text-xs">
                        <a
                          href={link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-violet-400 hover:text-violet-300"
                        >
                          {link}
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "structured" && hasStructured && (
              <div className="space-y-4">
                {page.structured_data.json_ld && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2 flex items-center gap-1.5">
                      <Braces className="h-3.5 w-3.5" />
                      JSON-LD (Schema.org)
                    </h4>
                    <pre className="max-h-64 overflow-auto text-xs font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-3 text-white/70">
                      {JSON.stringify(page.structured_data.json_ld, null, 2)}
                    </pre>
                  </div>
                )}
                {page.structured_data.open_graph && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">OpenGraph</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(page.structured_data.open_graph).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-white/40">og:{key}:</span>{" "}
                          <span className="font-mono text-white/70">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {page.structured_data.twitter_card && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Twitter Card</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(page.structured_data.twitter_card).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-white/40">twitter:{key}:</span>{" "}
                          <span className="font-mono text-white/70">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {page.structured_data.meta_tags && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Meta Tags</h4>
                    <div className="space-y-1 max-h-48 overflow-auto">
                      {Object.entries(page.structured_data.meta_tags).map(([key, val]) => (
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
                {page.headings.map((h: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs"
                    style={{ paddingLeft: `${(h.level - 1) * 16}px` }}
                  >
                    <span className="inline-flex items-center rounded-md border border-white/20 px-1.5 py-0 text-[10px] font-mono text-white/50 shrink-0">
                      H{h.level}
                    </span>
                    <span className={`text-white/70 ${h.level === 1 ? "font-semibold" : ""}`}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {page.images.map((img: any, i: number) => (
                  <div key={i} className="border border-white/10 bg-[#0a0a0a] overflow-hidden">
                    <div className="aspect-video flex items-center justify-center">
                      <img
                        src={img.src}
                        alt={img.alt || ""}
                        className="max-w-full max-h-full object-contain"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </div>
                    <div className="p-2">
                      <p className="text-xs text-white/40 truncate" title={img.src}>
                        {img.src.split("/").pop()}
                      </p>
                      {img.alt && (
                        <p className="text-xs text-white/70 truncate mt-0.5">{img.alt}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "extract" && hasExtract && (
              <pre className="max-h-96 overflow-auto text-xs text-white/70 whitespace-pre-wrap font-mono bg-[#0a0a0a] border border-white/10 rounded-md p-4">
                {JSON.stringify(page.extract, null, 2)}
              </pre>
            )}

          </div>
        </div>
      )}
    </div>
  );
});

export default function CrawlStatusPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [allData, setAllData] = useState<any[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(true);
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">("all");
  const [sortBy, setSortBy] = useState<"index" | "url" | "words">("index");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [tsvCopied, setTsvCopied] = useState(false);
  const PER_PAGE = 20;

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    fetchStatus(1);
  }, [jobId]);

  // SSE for real-time updates — falls back to polling on failure
  useEffect(() => {
    if (!polling || !jobId) return;
    if (status && ["completed", "failed", "cancelled"].includes(status.status)) {
      setPolling(false);
      return;
    }

    let cancelled = false;
    let es: EventSource | null = null;
    let interval: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (cancelled || interval) return;
      interval = setInterval(() => {
        if (!cancelled) fetchStatus(1);
      }, 2000);
    };

    const token = api.getToken();
    if (!token) return;

    const { API_BASE_URL } = require("@/lib/api");
    const sseUrl = `${API_BASE_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;

    try {
      es = new EventSource(sseUrl);
      es.onmessage = (event) => {
        if (cancelled) return;
        try {
          const data = JSON.parse(event.data);
          fetchStatus(1);
          if (data.done || ["completed", "failed", "cancelled"].includes(data.status)) {
            setPolling(false);
          }
        } catch {}
      };
      es.onerror = () => {
        es?.close();
        es = null;
        startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      cancelled = true;
      es?.close();
      if (interval) clearInterval(interval);
    };
  }, [polling, status?.status]);

  const fetchStatus = useCallback(async (page: number) => {
    try {
      const res = await api.getCrawlStatus(jobId, page, PER_PAGE);
      setStatus(res);
      setTotalResults(res.total_results || 0);
      if (page === 1) {
        setAllData(res.data || []);
      } else {
        setAllData((prev) => [...prev, ...(res.data || [])]);
      }
      setCurrentPage(page);
      if (["completed", "failed", "cancelled"].includes(res.status)) {
        setPolling(false);
      }
    } catch (err: any) {
      setError(err.message);
      setPolling(false);
    }
  }, [jobId]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    await fetchStatus(currentPage + 1);
    setLoadingMore(false);
  }, [currentPage, fetchStatus]);

  const handleCancel = async () => {
    try {
      await api.cancelCrawl(jobId);
      fetchStatus(1);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleExport = async (format: "zip" | "json" | "csv") => {
    try {
      await api.downloadCrawlExport(jobId, format);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const isRunning =
    status?.status === "running" || status?.status === "pending" || status?.status === "started";
  const isFinished =
    status?.status === "completed" || status?.status === "failed" || status?.status === "cancelled";
  const progressPercent =
    status?.total_pages > 0
      ? Math.min(100, Math.round((status.completed_pages / status.total_pages) * 100))
      : 0;

  // Count screenshots
  const screenshotCount = useMemo(() => allData.filter((p: any) => p.screenshot)?.length || 0, [allData]);
  const totalWords = useMemo(() => allData.reduce(
    (sum: number, p: any) => sum + (p.metadata?.word_count || 0),
    0
  ) || 0, [allData]);

  const hasMore = allData.length < totalResults;

  const filteredData = useMemo(() => {
    if (!allData.length) return [];
    let data = allData.map((p: any, i: number) => ({ ...p, _index: i }));
    if (searchFilter) {
      const q = searchFilter.toLowerCase();
      data = data.filter((p: any) => p.url?.toLowerCase().includes(q) || p.metadata?.title?.toLowerCase().includes(q));
    }
    if (statusFilter === "success") {
      data = data.filter((p: any) => p.metadata?.status_code >= 200 && p.metadata?.status_code < 400);
    } else if (statusFilter === "error") {
      data = data.filter((p: any) => !p.metadata?.status_code || p.metadata?.status_code >= 400);
    }
    if (sortBy === "url") {
      data.sort((a: any, b: any) => (a.url || "").localeCompare(b.url || ""));
    } else if (sortBy === "words") {
      data.sort((a: any, b: any) => (b.metadata?.word_count || 0) - (a.metadata?.word_count || 0));
    }
    return data;
  }, [allData, searchFilter, statusFilter, sortBy]);

  return (
    <PageLayout activePage="">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 py-10">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/crawl">
            <button className="border border-white/20 p-2 text-white/50 hover:text-white hover:border-white/40 transition-colors">
              <ArrowLeft className="h-4 w-4" />
            </button>
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text-violet">Crawl Results</h1>
            <p className="text-[13px] text-white/40 font-mono">{jobId}</p>
          </div>
        </div>

        {error && (
          <div className="border border-red-500/30 bg-red-500/10 mb-6 p-4">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {!status && !error && (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
            <p className="text-sm text-white/40">Loading crawl status...</p>
          </div>
        )}

        {status && (
          <>
            {/* Status Card */}
            <div className="border border-white/10 bg-white/[0.02] mb-6 relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-violet-500 to-pink-500" />
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center rounded-md border px-3 py-1 text-sm font-medium ${
                        status.status === "completed"
                          ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                          : status.status === "failed"
                          ? "border-red-500/30 text-red-400 bg-red-500/10"
                          : "border-amber-500/30 text-amber-400 bg-amber-500/10"
                      }`}
                    >
                      {isRunning && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                      {status.status === "running" ? "Crawling..." : status.status}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {isRunning && (
                      <button
                        onClick={handleCancel}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20 transition-colors"
                      >
                        <StopCircle className="h-4 w-4" />
                        Stop
                      </button>
                    )}
                    {totalResults > 0 && (
                      <ExportDropdown onExport={handleExport} />
                    )}
                  </div>
                </div>

                {/* Progress */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white/50 text-[12px] font-mono">
                      {status.completed_pages} page{status.completed_pages !== 1 ? "s" : ""}{" "}
                      scraped
                      {isRunning && status.total_pages > 0 && (
                        <span> of {status.total_pages} max</span>
                      )}
                    </span>
                    {isRunning && progressPercent > 0 && (
                      <span className="text-white/50 text-[12px] font-mono">{progressPercent}%</span>
                    )}
                  </div>
                  {(isRunning || status.completed_pages > 0) && (
                    <div className="w-full h-2 bg-white/[0.06] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isRunning
                            ? "bg-amber-500"
                            : status.status === "completed"
                            ? "bg-emerald-500"
                            : "bg-red-500"
                        }`}
                        style={{
                          width: isFinished
                            ? "100%"
                            : `${Math.max(progressPercent, status.completed_pages > 0 ? 5 : 0)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>

                {/* Stats row */}
                {totalResults > 0 && (
                  <div className="flex gap-6 mt-4 pt-4 border-t border-white/10 text-[12px] text-white/50 font-mono">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5" />
                      <span>{totalResults} pages</span>
                    </div>
                    {screenshotCount > 0 && (
                      <div className="flex items-center gap-1.5">
                        <Camera className="h-3.5 w-3.5" />
                        <span>{screenshotCount} screenshots</span>
                      </div>
                    )}
                    {totalWords > 0 && (
                      <div className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5" />
                        <span>{totalWords.toLocaleString()} total words</span>
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
            </div>

            {/* Filter Bar */}
            {allData.length > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30" />
                  <input
                    placeholder="Filter by URL..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="w-full h-9 pl-9 pr-3 rounded-md bg-transparent border border-white/10 text-white font-mono text-sm placeholder:text-white/30 outline-none focus:border-white/30 transition-colors"
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
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="h-9 rounded-md bg-[#0a0a0a] border border-white/10 text-white font-mono px-3 text-xs outline-none"
                >
                  <option value="index">Sort: Original</option>
                  <option value="url">Sort: URL</option>
                  <option value="words">Sort: Words</option>
                </select>
                <div className="flex gap-1">
                  <button
                    onClick={() => setViewMode("cards")}
                    className={`p-1.5 rounded-md transition-colors ${
                      viewMode === "cards"
                        ? "bg-white text-black"
                        : "text-white/40 hover:text-white"
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
                        : "text-white/40 hover:text-white"
                    }`}
                    title="Table view"
                  >
                    <Table2 className="h-4 w-4" />
                  </button>
                </div>
                <span className="text-xs text-white/40 font-mono">
                  {filteredData.length} of {totalResults} pages
                  {allData.length < totalResults && ` (${allData.length} loaded)`}
                </span>
              </div>
            )}

            {/* Results List */}
            {allData.length > 0 ? (
              <div className="space-y-3">
                <h2 className="text-lg font-semibold flex items-center gap-2 mb-3 text-white font-mono uppercase">
                  <Globe className="h-5 w-5" />
                  Crawled Pages
                </h2>

                {viewMode === "table" ? (
                  <div>
                    <div className="flex justify-end mb-2">
                      <button
                        onClick={() => {
                          const header = ["#", "URL", "Title", "Status Code", "Words", "Reading Time", "Links", "Images"].join("\t");
                          const rows = filteredData.map((p: any) => [
                            p._index + 1,
                            p.url || "",
                            p.metadata?.title || "",
                            p.metadata?.status_code || "",
                            p.metadata?.word_count || 0,
                            p.metadata?.reading_time_seconds ? `${Math.ceil(p.metadata.reading_time_seconds / 60)}m` : "",
                            p.links_detail?.total || p.links?.length || 0,
                            p.images?.length || 0,
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
                            <th
                              className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono cursor-pointer hover:text-white"
                              onClick={() => setSortBy(sortBy === "url" ? "index" : "url")}
                            >
                              URL {sortBy === "url" && "↑"}
                            </th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono">Title</th>
                            <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-white/40 font-mono w-20">Status</th>
                            <th
                              className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-white/40 font-mono cursor-pointer hover:text-white w-20"
                              onClick={() => setSortBy(sortBy === "words" ? "index" : "words")}
                            >
                              Words {sortBy === "words" && "↓"}
                            </th>
                            <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-white/40 font-mono w-16">Time</th>
                            <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-white/40 font-mono w-16">Links</th>
                            <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-white/40 font-mono w-16">Images</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredData.map((page: any) => {
                            const wordCount = page.metadata?.word_count || 0;
                            const readingTime = page.metadata?.reading_time_seconds
                              ? Math.ceil(page.metadata.reading_time_seconds / 60)
                              : 0;
                            const statusCode = page.metadata?.status_code;
                            const linksCount = page.links_detail?.total || page.links?.length || 0;
                            const imagesCount = page.images?.length || 0;
                            return (
                              <tr key={page._index} className="border-b border-white/[0.06] last:border-0 hover:bg-white/[0.03] transition-colors">
                                <td className="px-3 py-2 text-xs text-white/40 font-mono">{page._index + 1}</td>
                                <td className="px-3 py-2 max-w-xs">
                                  <a
                                    href={page.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-violet-400 hover:text-violet-300 truncate block"
                                  >
                                    {page.url}
                                  </a>
                                </td>
                                <td className="px-3 py-2 text-xs text-white/40 truncate max-w-[200px]">
                                  {page.metadata?.title || "\u2014"}
                                </td>
                                <td className="px-3 py-2">
                                  {statusCode && (
                                    <span
                                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-mono ${
                                        statusCode >= 200 && statusCode < 400
                                          ? "border-emerald-500/30 text-emerald-400"
                                          : statusCode >= 400
                                          ? "border-red-500/30 text-red-400"
                                          : "border-white/20 text-white/50"
                                      }`}
                                    >
                                      {statusCode}
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-2 text-xs text-white/40 text-right font-mono">
                                  {wordCount > 0 ? wordCount.toLocaleString() : "\u2014"}
                                </td>
                                <td className="px-3 py-2 text-xs text-white/40 text-right">
                                  {readingTime > 0 ? `${readingTime}m` : "\u2014"}
                                </td>
                                <td className="px-3 py-2 text-xs text-white/40 text-right font-mono">
                                  {linksCount > 0 ? linksCount : "\u2014"}
                                </td>
                                <td className="px-3 py-2 text-xs text-white/40 text-right font-mono">
                                  {imagesCount > 0 ? imagesCount : "\u2014"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <>
                    {filteredData.map((page: any) => (
                      <PageResultCard key={page._index} page={page} index={page._index} jobId={jobId} />
                    ))}
                  </>
                )}

                {hasMore && (
                  <div className="flex justify-center pt-4">
                    <button
                      onClick={loadMore}
                      disabled={loadingMore}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm border border-white/20 text-white/50 hover:text-white disabled:opacity-50 transition-colors"
                    >
                      {loadingMore ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : null}
                      {loadingMore
                        ? "Loading..."
                        : `Load More (${totalResults - allData.length} remaining)`}
                    </button>
                  </div>
                )}
              </div>
            ) : isRunning ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
                <p className="text-sm text-white/40">
                  Discovering and scraping pages...
                </p>
                <p className="text-xs text-white/40 mt-1">
                  Each page gets: markdown, HTML, screenshot, links, structured data, and more
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Globe className="h-12 w-12 text-white/40 mb-4" />
                <p className="text-sm text-white/40">No pages were crawled.</p>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
