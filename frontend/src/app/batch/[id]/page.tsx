"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import {
  Loader2,
  ArrowLeft,
  Layers,
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
  Clock,
  FileCode,
  ArrowUpRight,
  ArrowDownLeft,
} from "lucide-react";
import Link from "next/link";

type TabType = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "json";

function BatchResultCard({ item, index }: { item: any; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("markdown");

  const hasMarkdown = !!item.markdown;
  const hasHtml = !!item.html;
  const hasScreenshot = !!item.screenshot;
  const hasLinks = item.links?.length > 0 || item.links_detail;
  const hasStructured = item.structured_data && Object.keys(item.structured_data).length > 0;
  const hasHeadings = item.headings?.length > 0;
  const hasImages = item.images?.length > 0;

  const tabs: { id: TabType; label: string; icon: any; available: boolean }[] = [
    { id: "markdown", label: "Markdown", icon: FileText, available: hasMarkdown },
    { id: "html", label: "HTML", icon: Code, available: hasHtml },
    { id: "screenshot", label: "Screenshot", icon: Camera, available: hasScreenshot },
    { id: "links", label: "Links", icon: Link2, available: hasLinks },
    { id: "structured", label: "Structured Data", icon: Braces, available: hasStructured },
    { id: "headings", label: "Headings", icon: List, available: hasHeadings },
    { id: "images", label: "Images", icon: ImageIcon, available: hasImages },
    { id: "json", label: "Full JSON", icon: FileCode, available: true },
  ];

  const availableTabs = tabs.filter((t) => t.available);

  useEffect(() => {
    if (!availableTabs.find((t) => t.id === activeTab)) {
      setActiveTab(availableTabs[0]?.id || "json");
    }
  }, []);

  const wordCount = item.metadata?.word_count || 0;
  const readingTime = item.metadata?.reading_time_seconds
    ? Math.ceil(item.metadata.reading_time_seconds / 60)
    : 0;

  return (
    <Card className="overflow-hidden">
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-muted-foreground font-mono w-6 shrink-0 text-right">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {item.success ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
            )}
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline truncate flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              {item.url}
              <ExternalLink className="h-3 w-3 shrink-0 opacity-50" />
            </a>
          </div>
          {item.metadata?.title && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{item.metadata.title}</p>
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
          {item.metadata?.status_code && (
            <Badge
              variant="outline"
              className={`text-xs ${
                item.metadata.status_code === 200
                  ? "border-green-500/50 text-green-400"
                  : item.metadata.status_code >= 400
                  ? "border-red-500/50 text-red-400"
                  : ""
              }`}
            >
              {item.metadata.status_code}
            </Badge>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border">
          {item.error && (
            <div className="mx-4 mt-4 rounded-md bg-destructive/10 p-3 text-sm text-red-400">
              {item.error}
            </div>
          )}

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
                {item.markdown}
              </pre>
            )}

            {activeTab === "html" && hasHtml && (
              <pre className="max-h-96 overflow-auto text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-4">
                {item.html}
              </pre>
            )}

            {activeTab === "screenshot" && hasScreenshot && (
              <div className="flex justify-center">
                <img
                  src={`data:image/png;base64,${item.screenshot}`}
                  alt={`Screenshot of ${item.url}`}
                  className="max-w-full rounded-md border border-border shadow-lg"
                  style={{ maxHeight: "600px" }}
                />
              </div>
            )}

            {activeTab === "links" && hasLinks && (
              <div className="space-y-4">
                {item.links_detail && (
                  <div className="flex gap-4 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Link2 className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{item.links_detail.total}</span>
                      <span className="text-muted-foreground">total</span>
                    </div>
                    {item.links_detail.internal && (
                      <div className="flex items-center gap-1.5">
                        <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                        <span className="font-medium">{item.links_detail.internal.count}</span>
                        <span className="text-muted-foreground">internal</span>
                      </div>
                    )}
                    {item.links_detail.external && (
                      <div className="flex items-center gap-1.5">
                        <ArrowUpRight className="h-4 w-4 text-orange-400" />
                        <span className="font-medium">{item.links_detail.external.count}</span>
                        <span className="text-muted-foreground">external</span>
                      </div>
                    )}
                  </div>
                )}
                {item.links_detail?.internal?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Internal Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {item.links_detail.internal.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">{link.url}</a>
                          {link.text && <span className="text-muted-foreground truncate shrink-0 max-w-48">"{link.text}"</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.links_detail?.external?.links?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">External Links</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {item.links_detail.external.links.map((link: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">{link.url}</a>
                          {link.text && <span className="text-muted-foreground truncate shrink-0 max-w-48">"{link.text}"</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {!item.links_detail && item.links && (
                  <div className="space-y-1 max-h-64 overflow-auto">
                    {item.links.map((link: string, i: number) => (
                      <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-xs text-primary hover:underline truncate">{link}</a>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "structured" && hasStructured && (
              <div className="space-y-4">
                {item.structured_data.json_ld && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">JSON-LD (Schema.org)</h4>
                    <pre className="max-h-64 overflow-auto text-xs font-mono bg-muted/30 rounded-md p-3">
                      {JSON.stringify(item.structured_data.json_ld, null, 2)}
                    </pre>
                  </div>
                )}
                {item.structured_data.open_graph && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">OpenGraph</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(item.structured_data.open_graph).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-muted-foreground">og:{key}:</span> <span className="font-mono">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.structured_data.twitter_card && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Twitter Card</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(item.structured_data.twitter_card).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="text-muted-foreground">twitter:{key}:</span> <span className="font-mono">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {item.structured_data.meta_tags && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Meta Tags</h4>
                    <div className="space-y-1 max-h-48 overflow-auto">
                      {Object.entries(item.structured_data.meta_tags).map(([key, val]) => (
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
                {item.headings.map((h: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs" style={{ paddingLeft: `${(h.level - 1) * 16}px` }}>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">H{h.level}</Badge>
                    <span className={h.level === 1 ? "font-semibold" : ""}>{h.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "images" && hasImages && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {item.images.map((img: any, i: number) => (
                  <div key={i} className="border border-border rounded-md overflow-hidden">
                    <div className="aspect-video bg-muted flex items-center justify-center">
                      <img src={img.src} alt={img.alt || ""} className="max-w-full max-h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                    </div>
                    <div className="p-2">
                      <p className="text-xs text-muted-foreground truncate" title={img.src}>{img.src.split("/").pop()}</p>
                      {img.alt && <p className="text-xs truncate mt-0.5">{img.alt}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "json" && (
              <pre className="max-h-96 overflow-auto text-xs font-mono bg-muted/30 rounded-md p-4">
                {JSON.stringify(item, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function BatchStatusPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    fetchStatus();
  }, [jobId]);

  useEffect(() => {
    if (!polling) return;
    if (status && ["completed", "failed", "cancelled"].includes(status.status)) {
      setPolling(false);
      return;
    }
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [polling, status?.status]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.getBatchStatus(jobId);
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
      await api.downloadBatchExport(jobId, format);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const isRunning = status?.status === "running" || status?.status === "pending";
  const progressPercent =
    status?.total_urls > 0
      ? Math.min(100, Math.round((status.completed_urls / status.total_urls) * 100))
      : 0;
  const successCount = status?.data?.filter((d: any) => d.success)?.length || 0;
  const failCount = status?.data?.filter((d: any) => !d.success)?.length || 0;
  const totalWords = status?.data?.reduce((sum: number, d: any) => sum + (d.metadata?.word_count || 0), 0) || 0;
  const screenshotCount = status?.data?.filter((d: any) => d.screenshot)?.length || 0;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-5xl mx-auto">
          <div className="mb-6 flex items-center gap-4">
            <Link href="/batch">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold">Batch Results</h1>
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
              <p className="text-sm text-muted-foreground">Loading batch status...</p>
            </div>
          )}

          {status && (
            <>
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
                        {status.status === "running" ? "Processing..." : status.status}
                      </Badge>
                    </div>
                    {status.data && status.data.length > 0 && (
                      <ExportDropdown onExport={handleExport} />
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {status.completed_urls} of {status.total_urls} URLs processed
                      </span>
                      {progressPercent > 0 && (
                        <span className="text-muted-foreground">{progressPercent}%</span>
                      )}
                    </div>
                    <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isRunning ? "bg-yellow-500" : status.status === "completed" ? "bg-green-500" : "bg-red-500"
                        }`}
                        style={{ width: `${status.status === "completed" ? 100 : progressPercent}%` }}
                      />
                    </div>
                  </div>

                  {status.data && status.data.length > 0 && (
                    <div className="flex gap-6 mt-4 pt-4 border-t border-border text-xs text-muted-foreground">
                      <div className="flex items-center gap-1.5">
                        <Layers className="h-3.5 w-3.5" />
                        <span>{status.data.length} results</span>
                      </div>
                      {successCount > 0 && (
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                          <span>{successCount} succeeded</span>
                        </div>
                      )}
                      {failCount > 0 && (
                        <div className="flex items-center gap-1.5">
                          <XCircle className="h-3.5 w-3.5 text-red-400" />
                          <span>{failCount} failed</span>
                        </div>
                      )}
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

              {status.data && status.data.length > 0 ? (
                <div className="space-y-3">
                  <h2 className="text-lg font-semibold flex items-center gap-2 mb-3">
                    <Layers className="h-5 w-5" />
                    Results
                  </h2>
                  {status.data.map((item: any, i: number) => (
                    <BatchResultCard key={i} item={item} index={i} />
                  ))}
                </div>
              ) : isRunning ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground/50 mb-4" />
                  <p className="text-sm text-muted-foreground">Processing URLs...</p>
                </div>
              ) : null}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
