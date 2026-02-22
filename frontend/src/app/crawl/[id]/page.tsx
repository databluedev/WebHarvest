"use client";

import { useState, useEffect, useCallback, memo, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
  const [screenshotData, setScreenshotData] = useState<string | null>(page.screenshot || null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);

  const hasMarkdown = !!page.markdown;
  const hasHtml = !!page.html;
  const hasScreenshot = !!page.screenshot;
  const hasLinks = page.links?.length > 0 || page.links_detail;
  const hasStructured = page.structured_data && Object.keys(page.structured_data).length > 0;
  const hasHeadings = page.headings?.length > 0;
  const hasImages = page.images?.length > 0;
  const hasExtract = !!page.extract;

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

  const linksSummary = page.links_detail || (page.links ? { total: page.links.length } : null);
  const wordCount = page.metadata?.word_count || 0;
  const readingTime = page.metadata?.reading_time_seconds
    ? Math.ceil(page.metadata.reading_time_seconds / 60)
    : 0;

  return (
    <Card className="overflow-hidden">
      {/* Header - always visible */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-muted-foreground font-mono w-6 shrink-0 text-right">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <a
              href={page.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline truncate flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              {page.url}
              <ExternalLink className="h-3 w-3 shrink-0 opacity-50" />
            </a>
          </div>
          {page.metadata?.title && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {page.metadata.title}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasScreenshot && (
            <Badge variant="outline" className="text-xs gap-1">
              <Camera className="h-3 w-3" />
            </Badge>
          )}
          {wordCount > 0 && (
            <Badge variant="outline" className="text-xs">
              {wordCount.toLocaleString()} words
            </Badge>
          )}
          {readingTime > 0 && (
            <Badge variant="outline" className="text-xs gap-1">
              <Clock className="h-3 w-3" />
              {readingTime}m
            </Badge>
          )}
          <Badge
            variant="outline"
            className={`text-xs ${
              page.metadata?.status_code === 200
                ? "border-green-500/50 text-green-400"
                : page.metadata?.status_code >= 400
                ? "border-red-500/50 text-red-400"
                : ""
            }`}
          >
            {page.metadata?.status_code || "?"}
          </Badge>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border">
          {/* Tab bar */}
          <div className="flex gap-1 p-2 border-b border-border bg-muted/20 overflow-x-auto">
            {availableTabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
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
              <pre className="max-h-96 overflow-auto text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-4">
                {page.markdown}
              </pre>
            )}

            {activeTab === "html" && hasHtml && (
              <pre className="max-h-96 overflow-auto text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-4">
                {page.html}
              </pre>
            )}

            {activeTab === "screenshot" && hasScreenshot && (
              <div className="flex justify-center">
                {screenshotData ? (
                  <img
                    src={`data:image/jpeg;base64,${screenshotData}`}
                    alt={`Screenshot of ${page.url}`}
                    className="max-w-full rounded-md border border-border shadow-lg"
                    style={{ maxHeight: "600px" }}
                  />
                ) : screenshotLoading ? (
                  <div className="flex items-center gap-2 py-8 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">Loading screenshot...</span>
                  </div>
                ) : (
                  <Button variant="outline" size="sm" onClick={loadScreenshot} className="gap-2">
                    <Camera className="h-4 w-4" />
                    Load Screenshot
                  </Button>
                )}
              </div>
            )}

            {activeTab === "links" && hasLinks && (
              <div className="space-y-4">
                {page.links_detail && (
                  <div className="flex gap-4 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Link2 className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{page.links_detail.total}</span>
                      <span className="text-muted-foreground">total</span>
                    </div>
                    {page.links_detail.internal && (
                      <div className="flex items-center gap-1.5">
                        <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                        <span className="font-medium">{page.links_detail.internal.count}</span>
                        <span className="text-muted-foreground">internal</span>
                      </div>
                    )}
                    {page.links_detail.external && (
                      <div className="flex items-center gap-1.5">
                        <ArrowUpRight className="h-4 w-4 text-orange-400" />
                        <span className="font-medium">{page.links_detail.external.count}</span>
                        <span className="text-muted-foreground">external</span>
                      </div>
                    )}
                  </div>
                )}

                {page.links_detail?.internal?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Internal Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {page.links_detail.internal.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline truncate"
                          >
                            {link.url}
                          </a>
                          {link.text && (
                            <span className="text-muted-foreground truncate shrink-0 max-w-48">
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
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">External Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {page.links_detail.external.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline truncate"
                          >
                            {link.url}
                          </a>
                          {link.text && (
                            <span className="text-muted-foreground truncate shrink-0 max-w-48">
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
                          className="text-primary hover:underline"
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
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2 flex items-center gap-1.5">
                      <Braces className="h-3.5 w-3.5" />
                      JSON-LD (Schema.org)
                    </h4>
                    <pre className="max-h-64 overflow-auto text-xs font-mono bg-muted/30 rounded-md p-3">
                      {JSON.stringify(page.structured_data.json_ld, null, 2)}
                    </pre>
                  </div>
                )}
                {page.structured_data.open_graph && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">OpenGraph</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(page.structured_data.open_graph).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-muted-foreground">og:{key}:</span>{" "}
                          <span className="font-mono">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {page.structured_data.twitter_card && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Twitter Card</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(page.structured_data.twitter_card).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-muted-foreground">twitter:{key}:</span>{" "}
                          <span className="font-mono">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {page.structured_data.meta_tags && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Meta Tags</h4>
                    <div className="space-y-1 max-h-48 overflow-auto">
                      {Object.entries(page.structured_data.meta_tags).map(([key, val]) => (
                        <div key={key} className="text-xs font-mono">
                          <span className="text-muted-foreground">{key}:</span> {String(val)}
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
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
                      H{h.level}
                    </Badge>
                    <span className={h.level === 1 ? "font-semibold" : ""}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {page.images.map((img: any, i: number) => (
                  <div key={i} className="border border-border rounded-md overflow-hidden">
                    <div className="aspect-video bg-muted flex items-center justify-center">
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
                      <p className="text-xs text-muted-foreground truncate" title={img.src}>
                        {img.src.split("/").pop()}
                      </p>
                      {img.alt && (
                        <p className="text-xs truncate mt-0.5">{img.alt}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "extract" && hasExtract && (
              <pre className="max-h-96 overflow-auto text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-4">
                {JSON.stringify(page.extract, null, 2)}
              </pre>
            )}

          </div>
        </div>
      )}
    </Card>
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
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-5xl mx-auto">
          <div className="mb-6 flex items-center gap-4">
            <Link href="/crawl">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Crawl Results</h1>
              <p className="text-sm text-muted-foreground font-mono">{jobId}</p>
            </div>
          </div>

          {error && (
            <Card className="border-destructive mb-6">
              <CardContent className="p-4">
                <p className="text-sm text-red-400">{error}</p>
              </CardContent>
            </Card>
          )}

          {!status && !error && (
            <div className="flex flex-col items-center justify-center py-24">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
              <p className="text-sm text-muted-foreground">Loading crawl status...</p>
            </div>
          )}

          {status && (
            <>
              {/* Status Card */}
              <Card className="mb-6">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <Badge
                        variant={
                          status.status === "completed"
                            ? "success"
                            : status.status === "failed"
                            ? "destructive"
                            : "warning"
                        }
                        className="text-sm px-3 py-1"
                      >
                        {isRunning && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                        {status.status === "running" ? "Crawling..." : status.status}
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      {isRunning && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={handleCancel}
                          className="gap-1.5"
                        >
                          <StopCircle className="h-4 w-4" />
                          Stop
                        </Button>
                      )}
                      {totalResults > 0 && (
                        <ExportDropdown onExport={handleExport} />
                      )}
                    </div>
                  </div>

                  {/* Progress */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {status.completed_pages} page{status.completed_pages !== 1 ? "s" : ""}{" "}
                        scraped
                        {isRunning && status.total_pages > 0 && (
                          <span> of {status.total_pages} max</span>
                        )}
                      </span>
                      {isRunning && progressPercent > 0 && (
                        <span className="text-muted-foreground">{progressPercent}%</span>
                      )}
                    </div>
                    {(isRunning || status.completed_pages > 0) && (
                      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isRunning
                              ? "bg-yellow-500"
                              : status.status === "completed"
                              ? "bg-green-500"
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
                    <div className="flex gap-6 mt-4 pt-4 border-t border-border text-xs text-muted-foreground">
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
                    <div className="mt-4 rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                      {status.error}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Filter Bar */}
              {allData.length > 0 && (
                <div className="mb-4 flex flex-wrap items-center gap-3">
                  <div className="relative flex-1 min-w-[200px]">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Filter by URL..."
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      className="pl-9 h-9"
                    />
                  </div>
                  <div className="flex gap-1">
                    {(["all", "success", "error"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setStatusFilter(f)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                          statusFilter === f
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {f === "all" ? "All" : f === "success" ? "Success" : "Errors"}
                      </button>
                    ))}
                  </div>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as any)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-xs"
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
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted"
                      }`}
                      title="Card view"
                    >
                      <LayoutGrid className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setViewMode("table")}
                      className={`p-1.5 rounded-md transition-colors ${
                        viewMode === "table"
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted"
                      }`}
                      title="Table view"
                    >
                      <Table2 className="h-4 w-4" />
                    </button>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {filteredData.length} of {totalResults} pages
                    {allData.length < totalResults && ` (${allData.length} loaded)`}
                  </span>
                </div>
              )}

              {/* Results List */}
              {allData.length > 0 ? (
                <div className="space-y-3">
                  <h2 className="text-lg font-semibold flex items-center gap-2 mb-3">
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
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                        >
                          {tsvCopied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          {tsvCopied ? "Copied!" : "Copy Table"}
                        </button>
                      </div>
                      <div className="rounded-md border border-border overflow-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border bg-muted/50">
                              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground w-10">#</th>
                              <th
                                className="px-3 py-2 text-left text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                                onClick={() => setSortBy(sortBy === "url" ? "index" : "url")}
                              >
                                URL {sortBy === "url" && "↑"}
                              </th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Title</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground w-20">Status</th>
                              <th
                                className="px-3 py-2 text-right text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground w-20"
                                onClick={() => setSortBy(sortBy === "words" ? "index" : "words")}
                              >
                                Words {sortBy === "words" && "↓"}
                              </th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-16">Time</th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-16">Links</th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-16">Images</th>
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
                                <tr key={page._index} className="border-b border-border last:border-0 hover:bg-muted/50 transition-colors">
                                  <td className="px-3 py-2 text-xs text-muted-foreground font-mono">{page._index + 1}</td>
                                  <td className="px-3 py-2 max-w-xs">
                                    <a
                                      href={page.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-primary hover:underline truncate block"
                                    >
                                      {page.url}
                                    </a>
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground truncate max-w-[200px]">
                                    {page.metadata?.title || "—"}
                                  </td>
                                  <td className="px-3 py-2">
                                    {statusCode && (
                                      <Badge
                                        variant="outline"
                                        className={`text-[10px] ${
                                          statusCode >= 200 && statusCode < 400
                                            ? "border-green-500/50 text-green-400"
                                            : statusCode >= 400
                                            ? "border-red-500/50 text-red-400"
                                            : ""
                                        }`}
                                      >
                                        {statusCode}
                                      </Badge>
                                    )}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground text-right font-mono">
                                    {wordCount > 0 ? wordCount.toLocaleString() : "—"}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground text-right">
                                    {readingTime > 0 ? `${readingTime}m` : "—"}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground text-right font-mono">
                                    {linksCount > 0 ? linksCount : "—"}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground text-right font-mono">
                                    {imagesCount > 0 ? imagesCount : "—"}
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
                      <Button
                        variant="outline"
                        onClick={loadMore}
                        disabled={loadingMore}
                        className="gap-2"
                      >
                        {loadingMore ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : null}
                        {loadingMore
                          ? "Loading..."
                          : `Load More (${totalResults - allData.length} remaining)`}
                      </Button>
                    </div>
                  )}
                </div>
              ) : isRunning ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground/50 mb-4" />
                  <p className="text-sm text-muted-foreground">
                    Discovering and scraping pages...
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    Each page gets: markdown, HTML, screenshot, links, structured data, and more
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Globe className="h-12 w-12 text-muted-foreground/30 mb-4" />
                  <p className="text-sm text-muted-foreground">No pages were crawled.</p>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
