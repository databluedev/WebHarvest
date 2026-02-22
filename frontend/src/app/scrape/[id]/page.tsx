"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import {
  Loader2,
  ArrowLeft,
  FileText,
  ExternalLink,
  Code,
  Image as ImageIcon,
  Link2,
  Camera,
  Braces,
  List,
  Clock,
  FileCode,
  ArrowUpRight,
  ArrowDownLeft,
  Copy,
  Check,
  Sparkles,
  Table2,
} from "lucide-react";
import Link from "next/link";

type TabId = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract" | "table";

export default function ScrapeDetailPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabId>("markdown");
  const [copied, setCopied] = useState(false);
  const [tsvCopied, setTsvCopied] = useState(false);
  const [polling, setPolling] = useState(true);
  const [screenshotData, setScreenshotData] = useState<Record<string, string>>({});
  const [screenshotLoading, setScreenshotLoading] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    fetchStatus();
  }, [jobId]);

  // SSE for real-time updates — falls back to polling on failure
  const sseRef = useRef<EventSource | null>(null);
  useEffect(() => {
    if (!polling || !jobId) return;
    if (status && ["completed", "failed"].includes(status.status)) {
      setPolling(false);
      return;
    }

    const token = api.getToken();
    if (!token) return;

    const { API_BASE_URL } = require("@/lib/api");
    const url = `${API_BASE_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;

    try {
      const es = new EventSource(url);
      sseRef.current = es;
      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.done || data.status === "completed" || data.status === "failed") {
            fetchStatus();
            setPolling(false);
            es.close();
          } else {
            fetchStatus();
          }
        } catch {}
      };
      es.onerror = () => {
        es.close();
        sseRef.current = null;
        // Fall back to polling
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
      };
      return () => { es.close(); sseRef.current = null; };
    } catch {
      // No SSE support — poll
      const interval = setInterval(fetchStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [polling, status?.status]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.getScrapeStatus(jobId);
      setStatus(res);
      if (["completed", "failed"].includes(res.status)) {
        setPolling(false);
      }
    } catch (err: any) {
      setError(err.message);
      setPolling(false);
    }
  }, [jobId]);

  const handleExport = async (format: "zip" | "json" | "csv") => {
    try {
      await api.downloadScrapeExport(jobId, format);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const result = status?.data?.[0];

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const loadScreenshot = useCallback(async (resultId: string) => {
    if (screenshotData[resultId] || screenshotLoading[resultId]) return;
    setScreenshotLoading((prev) => ({ ...prev, [resultId]: true }));
    try {
      const detail = await api.getJobResultDetail(jobId, resultId);
      if (detail.screenshot) {
        setScreenshotData((prev) => ({ ...prev, [resultId]: detail.screenshot as string }));
      }
    } catch (err: any) {
      setError(`Failed to load screenshot: ${err.message}`);
    } finally {
      setScreenshotLoading((prev) => ({ ...prev, [resultId]: false }));
    }
  }, [jobId, screenshotData, screenshotLoading]);

  const resultTabs: { id: TabId; label: string; icon: any; available: boolean }[] = result
    ? [
        { id: "markdown", label: "Markdown", icon: FileText, available: !!result.markdown },
        { id: "html", label: "HTML", icon: Code, available: !!result.html },
        { id: "screenshot", label: "Screenshot", icon: Camera, available: !!result.screenshot },
        { id: "links", label: `Links${result.links ? ` (${result.links.length})` : ""}`, icon: Link2, available: !!(result.links?.length || result.links_detail) },
        { id: "structured", label: "Structured Data", icon: Braces, available: !!(result.structured_data && Object.keys(result.structured_data).length > 0) },
        { id: "headings", label: `Headings${result.headings ? ` (${result.headings.length})` : ""}`, icon: List, available: !!result.headings?.length },
        { id: "images", label: `Images${result.images ? ` (${result.images.length})` : ""}`, icon: ImageIcon, available: !!result.images?.length },
        { id: "extract", label: "AI Extract", icon: Sparkles, available: !!result.extract },
        { id: "table", label: "Table", icon: Table2, available: true },
      ]
    : [];

  const availableTabs = resultTabs.filter((t) => t.available);

  // Auto-select first available tab when result loads
  useEffect(() => {
    if (result && availableTabs.length > 0) {
      if (!availableTabs.find((t) => t.id === activeTab)) {
        setActiveTab(availableTabs[0].id);
      }
    }
  }, [result]);

  const getCopyText = (): string => {
    if (!result) return "";
    switch (activeTab) {
      case "markdown": return result.markdown || "";
      case "html": return result.html || "";
      case "links": return result.links?.join("\n") || "";
      case "extract": return JSON.stringify(result.extract, null, 2);
      case "structured": return JSON.stringify(result.structured_data, null, 2);
      case "headings": return JSON.stringify(result.headings, null, 2);
      case "images": return JSON.stringify(result.images, null, 2);
      case "table": return "";
      default: return "";
    }
  };

  return (
    <PageLayout activePage="">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 py-10">
        {/* Header */}
        <div className="mb-6 flex items-center gap-4">
          <Link href="/scrape">
            <button className="border border-white/20 p-2 text-white/50 hover:text-white hover:border-white/40 transition-colors">
              <ArrowLeft className="h-4 w-4" />
            </button>
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono text-white">Scrape Result</h1>
            <p className="text-[13px] text-white/40 font-mono">{jobId}</p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="border border-red-500/30 bg-red-500/10 text-red-400 p-4 mb-6">
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Loading */}
        {!status && !error && (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-white/40 mb-4" />
            <p className="text-sm text-white/40">Loading scrape result...</p>
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
                      className={`text-sm px-3 py-1 border ${
                        status.status === "completed"
                          ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                          : status.status === "failed"
                          ? "border-red-500/30 text-red-400 bg-red-500/10"
                          : "border-amber-500/30 text-amber-400 bg-amber-500/10"
                      }`}
                    >
                      {status.status}
                    </span>
                    {result?.url && (
                      <a
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1 truncate max-w-md transition-colors"
                      >
                        {result.url}
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {result && (
                      <ExportDropdown onExport={handleExport} />
                    )}
                  </div>
                </div>

                {result?.metadata && (
                  <div className="flex gap-3 mt-4 pt-4 border-t border-white/10">
                    {result.metadata.status_code && (
                      <span
                        className={`text-[11px] font-mono px-2 py-0.5 border ${
                          result.metadata.status_code === 200
                            ? "border-emerald-500/30 text-emerald-400"
                            : result.metadata.status_code >= 400
                            ? "border-red-500/30 text-red-400"
                            : "border-white/20 text-white/50"
                        }`}
                      >
                        {result.metadata.status_code}
                      </span>
                    )}
                    {result.metadata.word_count > 0 && (
                      <span className="text-[11px] font-mono px-2 py-0.5 border border-white/20 text-white/50">
                        {result.metadata.word_count.toLocaleString()} words
                      </span>
                    )}
                    {result.metadata.reading_time_seconds > 0 && (
                      <span className="text-[11px] font-mono px-2 py-0.5 border border-white/20 text-white/50 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {Math.ceil(result.metadata.reading_time_seconds / 60)}m read
                      </span>
                    )}
                    {result.metadata.title && (
                      <span className="text-xs text-white/40 truncate">{result.metadata.title}</span>
                    )}
                    {result.metadata.canonical_url && result.metadata.canonical_url !== result.url && (
                      <span className="text-xs text-white/40 truncate flex items-center gap-1">
                        Canonical: <a href={result.metadata.canonical_url} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 transition-colors">{result.metadata.canonical_url}</a>
                      </span>
                    )}
                  </div>
                )}

                {status.error && (
                  <div className="mt-4 border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                    {status.error}
                  </div>
                )}
              </div>
            </div>

            {/* Result Content */}
            {result && (
              <div className="border border-white/10 bg-white/[0.02]">
                <div className="p-6">
                  {/* Tab bar */}
                  <div className="flex gap-1 mb-4 pb-2 border-b border-white/10 overflow-x-auto">
                    {availableTabs.map((tab) => {
                      const Icon = tab.icon;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-mono transition-colors whitespace-nowrap ${
                            activeTab === tab.id
                              ? "bg-white text-black"
                              : "text-white/40 hover:text-white/70"
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Copy button + content */}
                  <div className="relative">
                    {activeTab !== "screenshot" && (
                      <button
                        className="absolute right-2 top-2 z-10 text-white/30 hover:text-white p-1.5 transition-colors"
                        onClick={() => {
                          const text = getCopyText();
                          if (text) copyToClipboard(text);
                        }}
                      >
                        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    )}

                    {activeTab === "markdown" && result.markdown && (
                      <pre className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 font-mono text-[13px] text-white/70 whitespace-pre-wrap">
                        {result.markdown}
                      </pre>
                    )}

                    {activeTab === "html" && result.html && (
                      <pre className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 font-mono text-[13px] text-white/70 whitespace-pre-wrap">
                        {result.html}
                      </pre>
                    )}

                    {activeTab === "screenshot" && (
                      <div className="flex justify-center bg-[#0a0a0a] border border-white/10 p-4">
                        {screenshotData[result.id] ? (
                          <img
                            src={`data:image/jpeg;base64,${screenshotData[result.id]}`}
                            alt={`Screenshot of ${result.url}`}
                            className="max-w-full border border-white/10 shadow-lg"
                            style={{ maxHeight: "600px" }}
                          />
                        ) : screenshotLoading[result.id] ? (
                          <div className="flex flex-col items-center justify-center py-12">
                            <Loader2 className="h-6 w-6 animate-spin text-white/40 mb-2" />
                            <p className="text-sm text-white/40">Loading screenshot...</p>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center py-12">
                            <Camera className="h-10 w-10 text-white/20 mb-3" />
                            <button
                              onClick={() => loadScreenshot(result.id)}
                              className="border border-white/20 px-4 py-2 text-[12px] font-mono text-white/50 hover:text-white hover:border-white/40 transition-colors flex items-center gap-2"
                            >
                              <Camera className="h-4 w-4" />
                              Load Screenshot
                            </button>
                            <p className="text-xs text-white/40 mt-2">Screenshots are loaded on demand</p>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "links" && (
                      <div className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 space-y-4">
                        {result.links_detail && (
                          <div className="flex gap-4 text-sm pb-3 border-b border-white/10">
                            <div className="flex items-center gap-1.5">
                              <Link2 className="h-4 w-4 text-white/40" />
                              <span className="font-medium text-white/70">{result.links_detail.total}</span>
                              <span className="text-white/40">total</span>
                            </div>
                            {result.links_detail.internal && (
                              <div className="flex items-center gap-1.5">
                                <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                                <span className="font-medium text-white/70">{result.links_detail.internal.count}</span>
                                <span className="text-white/40">internal</span>
                              </div>
                            )}
                            {result.links_detail.external && (
                              <div className="flex items-center gap-1.5">
                                <ArrowUpRight className="h-4 w-4 text-orange-400" />
                                <span className="font-medium text-white/70">{result.links_detail.external.count}</span>
                                <span className="text-white/40">external</span>
                              </div>
                            )}
                          </div>
                        )}

                        {result.links_detail?.internal?.links?.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Internal Links</h4>
                            <div className="space-y-1">
                              {result.links_detail.internal.links.map((link: any, i: number) => (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                  <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                                  <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 truncate transition-colors">
                                    {link.url}
                                  </a>
                                  {link.text && <span className="text-white/40 truncate shrink-0 max-w-40">&quot;{link.text}&quot;</span>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {result.links_detail?.external?.links?.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">External Links</h4>
                            <div className="space-y-1">
                              {result.links_detail.external.links.map((link: any, i: number) => (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                  <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                                  <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 truncate transition-colors">
                                    {link.url}
                                  </a>
                                  {link.text && <span className="text-white/40 truncate shrink-0 max-w-40">&quot;{link.text}&quot;</span>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {!result.links_detail && result.links && (
                          <div className="space-y-1">
                            {result.links.map((link: string, i: number) => (
                              <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-xs text-emerald-400 hover:text-emerald-300 truncate transition-colors">
                                {link}
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "structured" && result.structured_data && (
                      <div className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 space-y-4">
                        {result.structured_data.json_ld && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2 flex items-center gap-1.5">
                              <Braces className="h-3.5 w-3.5" /> JSON-LD (Schema.org)
                            </h4>
                            <pre className="text-xs font-mono text-white/70 bg-[#0a0a0a] border border-white/10 rounded p-3 overflow-auto max-h-48">
                              {JSON.stringify(result.structured_data.json_ld, null, 2)}
                            </pre>
                          </div>
                        )}
                        {result.structured_data.open_graph && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">OpenGraph</h4>
                            <div className="grid grid-cols-1 gap-1">
                              {Object.entries(result.structured_data.open_graph).map(([key, val]) => (
                                <div key={key} className="text-xs">
                                  <span className="text-white/40">og:{key}:</span>{" "}
                                  <span className="text-white/70 font-mono">{String(val)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {result.structured_data.twitter_card && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">Twitter Card</h4>
                            <div className="grid grid-cols-1 gap-1">
                              {Object.entries(result.structured_data.twitter_card).map(([key, val]) => (
                                <div key={key} className="text-xs">
                                  <span className="text-white/40">twitter:{key}:</span>{" "}
                                  <span className="text-white/70 font-mono">{String(val)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {result.structured_data.meta_tags && (
                          <div>
                            <h4 className="text-xs font-semibold text-white/40 uppercase mb-2">All Meta Tags</h4>
                            <div className="space-y-1 max-h-48 overflow-auto">
                              {Object.entries(result.structured_data.meta_tags).map(([key, val]) => (
                                <div key={key} className="text-xs font-mono">
                                  <span className="text-white/40">{key}:</span> <span className="text-white/70">{String(val)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "headings" && result.headings && (
                      <div className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 space-y-1">
                        {result.headings.map((h: any, i: number) => (
                          <div
                            key={i}
                            className="flex items-center gap-2 text-xs"
                            style={{ paddingLeft: `${(h.level - 1) * 16}px` }}
                          >
                            <span className="border border-white/20 text-white/40 text-[10px] font-mono px-1.5 py-0 shrink-0">
                              H{h.level}
                            </span>
                            <span className={`text-white/70 ${h.level === 1 ? "font-semibold" : ""}`}>{h.text}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {activeTab === "images" && result.images && (
                      <div className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4">
                        <div className="grid grid-cols-2 gap-3">
                          {result.images.map((img: any, i: number) => (
                            <div key={i} className="border border-white/10 bg-[#0a0a0a] overflow-hidden">
                              <div className="aspect-video bg-white/[0.02] flex items-center justify-center">
                                <img
                                  src={img.src}
                                  alt={img.alt || ""}
                                  className="max-w-full max-h-full object-contain"
                                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                                />
                              </div>
                              <div className="p-2">
                                <p className="text-[11px] text-white/40 truncate" title={img.src}>
                                  {img.src.split("/").pop()}
                                </p>
                                {img.alt && <p className="text-[11px] text-white/70 truncate mt-0.5">{img.alt}</p>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {activeTab === "extract" && result.extract && (
                      <pre className="max-h-[600px] overflow-auto bg-[#0a0a0a] border border-white/10 p-4 font-mono text-[13px] text-white/70 whitespace-pre-wrap">
                        {JSON.stringify(result.extract, null, 2)}
                      </pre>
                    )}

                    {activeTab === "table" && (() => {
                      const meta = result.metadata || {};
                      const tableRows: [string, string][] = [
                        ["URL", result.url || "\u2014"],
                        ["Title", meta.title || "\u2014"],
                        ["Status Code", meta.status_code ? String(meta.status_code) : "\u2014"],
                        ["Word Count", meta.word_count ? meta.word_count.toLocaleString() : "\u2014"],
                        ["Reading Time", meta.reading_time_seconds ? `${Math.ceil(meta.reading_time_seconds / 60)} min` : "\u2014"],
                        ["Language", meta.language || "\u2014"],
                        ["Content Length", meta.content_length ? meta.content_length.toLocaleString() : "\u2014"],
                        ["Canonical URL", meta.canonical_url || "\u2014"],
                        ["Robots", meta.robots || "\u2014"],
                        ["Internal Links", result.links_detail?.internal?.count != null ? String(result.links_detail.internal.count) : "\u2014"],
                        ["External Links", result.links_detail?.external?.count != null ? String(result.links_detail.external.count) : "\u2014"],
                        ["Images", result.images?.length != null ? String(result.images.length) : "\u2014"],
                        ["Headings", result.headings?.length != null ? String(result.headings.length) : "\u2014"],
                      ];
                      return (
                        <div>
                          <div className="flex justify-end mb-2">
                            <button
                              onClick={() => {
                                const tsv = tableRows.map(([k, v]) => `${k}\t${v}`).join("\n");
                                navigator.clipboard.writeText(tsv);
                                setTsvCopied(true);
                                setTimeout(() => setTsvCopied(false), 2000);
                              }}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-mono text-white/30 hover:text-white transition-colors"
                            >
                              {tsvCopied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                              {tsvCopied ? "Copied!" : "Copy Table"}
                            </button>
                          </div>
                          <div className="border border-white/10 overflow-hidden">
                            <table className="w-full text-sm">
                              <tbody>
                                {tableRows.map(([label, value]) => (
                                  <tr key={label} className="border-b border-white/10 last:border-0 hover:bg-white/[0.02] transition-colors">
                                    <td className="px-4 py-2.5 text-xs text-white/40 w-40 bg-white/[0.02]">
                                      {label}
                                    </td>
                                    <td className="px-4 py-2.5 text-xs text-white font-mono">
                                      {label === "URL" || label === "Canonical URL" ? (
                                        value !== "\u2014" ? (
                                          <a
                                            href={value}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-emerald-400 hover:text-emerald-300 transition-colors"
                                          >
                                            {value}
                                          </a>
                                        ) : "\u2014"
                                      ) : value}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      );
                    })()}

                  </div>
                </div>
              </div>
            )}

            {!result && status.status === "failed" && (
              <div className="border border-white/10 bg-white/[0.02] flex flex-col items-center justify-center py-16 text-center">
                <FileText className="h-12 w-12 text-white/20 mb-4" />
                <p className="text-sm text-white/40">Scrape failed. No results available.</p>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
