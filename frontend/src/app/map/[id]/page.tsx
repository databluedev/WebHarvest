"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api, API_BASE_URL } from "@/lib/api";
import {
  Loader2,
  ArrowLeft,
  Map as MapIcon,
  ExternalLink,
  Copy,
  Check,
  Search,
} from "lucide-react";
import Link from "next/link";

export default function MapDetailPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [urlFilter, setUrlFilter] = useState("");
  const [visibleCount, setVisibleCount] = useState(100);
  const [polling, setPolling] = useState(true);
  const sseRef = useRef<EventSource | null>(null);

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

    const url = `${API_BASE_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;

    try {
      const es = new EventSource(url);
      sseRef.current = es;
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
        sseRef.current = null;
        // Fall back to polling
        const interval = setInterval(() => {
          fetchStatus();
        }, 2000);
        return () => clearInterval(interval);
      };
      return () => { es.close(); sseRef.current = null; };
    } catch {
      const interval = setInterval(() => {
        fetchStatus();
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [polling, status?.status]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.getMapStatus(jobId);
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
      await api.downloadMapExport(jobId, format as "json" | "csv");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const copyAllUrls = () => {
    if (!status?.links) return;
    const urls = status.links.map((l: any) => l.url).join("\n");
    navigator.clipboard.writeText(urls);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isRunning =
    status?.status === "running" || status?.status === "pending" || status?.status === "started";
  const isFinished =
    status?.status === "completed" || status?.status === "failed" || status?.status === "cancelled";
  const progressPercent =
    status?.total_pages > 0
      ? Math.min(100, Math.round((status.completed_pages / status.total_pages) * 100))
      : 0;

  const filteredLinks = useMemo(() => {
    if (!status?.links) return [];
    if (!urlFilter) return status.links;
    const q = urlFilter.toLowerCase();
    return status.links.filter((l: any) => l.url?.toLowerCase().includes(q) || l.title?.toLowerCase().includes(q));
  }, [status?.links, urlFilter]);

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-5xl mx-auto">
          <div className="mb-6 flex items-center gap-4">
            <Link href="/map">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Map Result</h1>
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
              <p className="text-sm text-muted-foreground">Loading map result...</p>
            </div>
          )}

          {status && (
            <>
              {/* Status Card */}
              <Card className="mb-6">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
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
                        {status.status === "running" ? "Mapping..." : status.status}
                      </Badge>
                      {status.url && (
                        <a
                          href={status.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-primary hover:underline flex items-center gap-1 truncate max-w-md"
                        >
                          {status.url}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {status.links?.length > 0 && (
                        <>
                          <Button variant="outline" size="sm" onClick={copyAllUrls} className="gap-1">
                            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                            Copy All
                          </Button>
                          <ExportDropdown onExport={handleExport} formats={["json", "csv"]} />
                        </>
                      )}
                    </div>
                  </div>

                  {/* Progress */}
                  <div className="space-y-2 mt-4 pt-4 border-t border-border">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {status.completed_pages || status.total || 0} URL{(status.completed_pages || status.total || 0) !== 1 ? "s" : ""}{" "}
                        discovered
                        {isRunning && status.total_pages > 0 && (
                          <span> of {status.total_pages} target</span>
                        )}
                      </span>
                      {progressPercent > 0 && (
                        <span className="text-muted-foreground">{isFinished ? 100 : progressPercent}%</span>
                      )}
                    </div>
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
                            : `${Math.max(progressPercent, status.total > 0 ? 5 : 0)}%`,
                        }}
                      />
                    </div>
                  </div>

                  {status.error && (
                    <div className="mt-4 rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                      {status.error}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Links List */}
              {status.links?.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">
                      Discovered URLs
                      <Badge variant="outline" className="ml-2">{status.total}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="mb-3 flex items-center gap-3">
                      <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Filter URLs..."
                          value={urlFilter}
                          onChange={(e) => { setUrlFilter(e.target.value); setVisibleCount(100); }}
                          className="pl-9 h-9"
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {filteredLinks.length} of {status.links.length} URLs
                      </span>
                    </div>
                    <div className="max-h-[600px] overflow-auto space-y-1">
                      {filteredLinks.slice(0, visibleCount).map((link: any, i: number) => (
                        <div key={i} className="flex items-center justify-between rounded px-2 py-1.5 hover:bg-muted group">
                          <div className="min-w-0 flex-1">
                            <a
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-primary hover:underline truncate block"
                            >
                              {link.url}
                            </a>
                            {link.title && (
                              <p className="text-xs text-muted-foreground truncate">{link.title}</p>
                            )}
                            {link.description && (
                              <p className="text-xs text-muted-foreground/70 truncate">{link.description}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-2">
                            {link.lastmod && (
                              <span className="text-xs text-muted-foreground">{link.lastmod}</span>
                            )}
                            <a
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                    {visibleCount < filteredLinks.length && (
                      <div className="mt-3 text-center">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setVisibleCount((c) => c + 100)}
                        >
                          Load more ({filteredLinks.length - visibleCount} remaining)
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : isRunning ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground/50 mb-4" />
                  <p className="text-sm text-muted-foreground">
                    Discovering URLs...
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    Crawling sitemaps, homepage links, and following internal pages
                  </p>
                </div>
              ) : status.status === "failed" ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <MapIcon className="h-12 w-12 text-muted-foreground/30 mb-4" />
                    <p className="text-sm text-muted-foreground">Map failed. No URLs discovered.</p>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <MapIcon className="h-12 w-12 text-muted-foreground/30 mb-4" />
                    <p className="text-sm text-muted-foreground">No URLs discovered.</p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
