"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
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
    <PageLayout activePage="">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 py-10">
        {/* Header */}
        <div className="mb-6 flex items-center gap-4">
          <Link href="/map">
            <button className="border border-white/20 p-2 text-white/50 hover:text-white hover:border-white/40 transition-colors">
              <ArrowLeft className="h-4 w-4" />
            </button>
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono text-white">Map Result</h1>
            <p className="text-[13px] text-white/40 font-mono">{jobId}</p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="border border-red-500/30 bg-red-500/10 mb-6 p-4">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Loading */}
        {!status && !error && (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
            <p className="text-sm text-white/40">Loading map result...</p>
          </div>
        )}

        {status && (
          <>
            {/* Status Card */}
            <div className="border border-white/10 bg-white/[0.02] mb-6">
              <div className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center border px-3 py-1 text-sm ${
                        status.status === "completed"
                          ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                          : status.status === "failed"
                          ? "border-red-500/30 text-red-400 bg-red-500/10"
                          : "border-amber-500/30 text-amber-400 bg-amber-500/10"
                      }`}
                    >
                      {isRunning && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                      {status.status === "running" ? "Mapping..." : status.status}
                    </span>
                    {status.url && (
                      <a
                        href={status.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1 truncate max-w-md transition-colors"
                      >
                        {status.url}
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {status.links?.length > 0 && (
                      <>
                        <button
                          onClick={copyAllUrls}
                          className="border border-white/20 px-4 py-2 text-[12px] font-mono text-white/50 hover:text-white transition-colors inline-flex items-center gap-1"
                        >
                          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          Copy All
                        </button>
                        <ExportDropdown onExport={handleExport} formats={["json", "csv"]} />
                      </>
                    )}
                  </div>
                </div>

                {/* Progress */}
                <div className="space-y-2 mt-4 pt-4 border-t border-white/10">
                  <div className="flex items-center justify-between">
                    <span className="text-white/50 font-mono text-[13px]">
                      {status.completed_pages || status.total || 0} URL{(status.completed_pages || status.total || 0) !== 1 ? "s" : ""}{" "}
                      discovered
                      {isRunning && status.total_pages > 0 && (
                        <span> of {status.total_pages} target</span>
                      )}
                    </span>
                    {progressPercent > 0 && (
                      <span className="text-white/50 font-mono text-[13px]">{isFinished ? 100 : progressPercent}%</span>
                    )}
                  </div>
                  <div className="w-full h-2 bg-white/[0.06] overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${
                        isRunning
                          ? "bg-amber-500"
                          : status.status === "completed"
                          ? "bg-emerald-500"
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
                  <div className="mt-4 border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                    {status.error}
                  </div>
                )}
              </div>
            </div>

            {/* Links List */}
            {status.links?.length > 0 ? (
              <div className="border border-white/10 bg-white/[0.02]">
                <div className="p-6 pb-0">
                  <div className="flex items-center gap-2 mb-4">
                    <h2 className="text-[16px] font-bold text-white font-mono uppercase">Discovered URLs</h2>
                    <span className="border border-white/20 text-white/40 text-[11px] font-mono px-2 py-0.5">{status.total}</span>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <div className="mb-3 flex items-center gap-3">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30" />
                      <input
                        placeholder="Filter URLs..."
                        value={urlFilter}
                        onChange={(e) => { setUrlFilter(e.target.value); setVisibleCount(100); }}
                        className="w-full bg-transparent border border-white/10 text-white font-mono placeholder:text-white/30 pl-9 h-9 px-3 py-1 text-sm outline-none focus:border-white/20 transition-colors"
                      />
                    </div>
                    <span className="text-white/40 text-[12px] font-mono">
                      {filteredLinks.length} of {status.links.length} URLs
                    </span>
                  </div>
                  <div className="max-h-[600px] overflow-auto space-y-1">
                    {filteredLinks.slice(0, visibleCount).map((link: any, i: number) => (
                      <div key={i} className="flex items-center justify-between hover:bg-white/[0.03] px-3 py-2 group">
                        <div className="min-w-0 flex-1">
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-emerald-400 hover:text-emerald-300 text-[13px] font-mono truncate block transition-colors"
                          >
                            {link.url}
                          </a>
                          {link.title && (
                            <p className="text-white/40 text-[12px] truncate">{link.title}</p>
                          )}
                          {link.description && (
                            <p className="text-white/30 text-[12px] truncate">{link.description}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0 ml-2">
                          {link.lastmod && (
                            <span className="text-white/30 text-[12px] font-mono">{link.lastmod}</span>
                          )}
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <ExternalLink className="h-3.5 w-3.5 text-white/30" />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                  {visibleCount < filteredLinks.length && (
                    <div className="mt-3 text-center">
                      <button
                        onClick={() => setVisibleCount((c) => c + 100)}
                        className="border border-white/20 text-white/50 hover:text-white font-mono px-4 py-2 text-sm transition-colors"
                      >
                        Load more ({filteredLinks.length - visibleCount} remaining)
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : isRunning ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
                <p className="text-sm text-white/40">
                  Discovering URLs...
                </p>
                <p className="text-xs text-white/30 mt-1">
                  Crawling sitemaps, homepage links, and following internal pages
                </p>
              </div>
            ) : status.status === "failed" ? (
              <div className="border border-white/10 bg-white/[0.02]">
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <MapIcon className="h-12 w-12 text-white/20 mb-4" />
                  <p className="text-sm text-white/40">Map failed. No URLs discovered.</p>
                </div>
              </div>
            ) : (
              <div className="border border-white/10 bg-white/[0.02]">
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <MapIcon className="h-12 w-12 text-white/20 mb-4" />
                  <p className="text-sm text-white/40">No URLs discovered.</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
