"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
} from "lucide-react";
import Link from "next/link";

type TabId = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract" | "json";

export default function ScrapeDetailPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabId>("markdown");
  const [copied, setCopied] = useState(false);
  const [polling, setPolling] = useState(true);

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
        { id: "json", label: "Full JSON", icon: FileCode, available: true },
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
      case "json": return JSON.stringify(result, null, 2);
      default: return "";
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto grid-bg">
        <div className="mesh-gradient min-h-full">
        <div className="p-8 max-w-5xl mx-auto">
          <div className="mb-6 flex items-center gap-4">
            <Link href="/scrape">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Scrape Result</h1>
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
              <p className="text-sm text-muted-foreground">Loading scrape result...</p>
            </div>
          )}

          {status && (
            <>
              {/* Status Badge */}
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
                        {status.status}
                      </Badge>
                      {result?.url && (
                        <a
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-primary hover:underline flex items-center gap-1 truncate max-w-md"
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
                    <div className="flex gap-3 mt-4 pt-4 border-t border-border">
                      {result.metadata.status_code && (
                        <Badge
                          variant="outline"
                          className={
                            result.metadata.status_code === 200
                              ? "border-green-500/50 text-green-400"
                              : result.metadata.status_code >= 400
                              ? "border-red-500/50 text-red-400"
                              : ""
                          }
                        >
                          {result.metadata.status_code}
                        </Badge>
                      )}
                      {result.metadata.word_count > 0 && (
                        <Badge variant="outline">{result.metadata.word_count.toLocaleString()} words</Badge>
                      )}
                      {result.metadata.reading_time_seconds > 0 && (
                        <Badge variant="outline" className="gap-1">
                          <Clock className="h-3 w-3" />
                          {Math.ceil(result.metadata.reading_time_seconds / 60)}m read
                        </Badge>
                      )}
                      {result.metadata.title && (
                        <span className="text-xs text-muted-foreground truncate">{result.metadata.title}</span>
                      )}
                      {result.metadata.canonical_url && result.metadata.canonical_url !== result.url && (
                        <span className="text-xs text-muted-foreground truncate flex items-center gap-1">
                          Canonical: <a href={result.metadata.canonical_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{result.metadata.canonical_url}</a>
                        </span>
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

              {/* Result Content */}
              {result && (
                <Card>
                  <CardContent className="p-6">
                    {/* Tab bar */}
                    <div className="flex gap-1 mb-4 pb-2 border-b border-border overflow-x-auto">
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

                    {/* Copy button */}
                    <div className="relative">
                      {activeTab !== "screenshot" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute right-2 top-2 h-7 w-7 z-10"
                          onClick={() => {
                            const text = getCopyText();
                            if (text) copyToClipboard(text);
                          }}
                        >
                          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                        </Button>
                      )}

                      {activeTab === "markdown" && result.markdown && (
                        <pre className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 text-sm whitespace-pre-wrap">
                          {result.markdown}
                        </pre>
                      )}

                      {activeTab === "html" && result.html && (
                        <pre className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 text-xs whitespace-pre-wrap font-mono">
                          {result.html}
                        </pre>
                      )}

                      {activeTab === "screenshot" && result.screenshot && (
                        <div className="flex justify-center rounded-md bg-muted p-4">
                          <img
                            src={`data:image/jpeg;base64,${result.screenshot}`}
                            alt={`Screenshot of ${result.url}`}
                            className="max-w-full rounded-md border border-border shadow-lg"
                            style={{ maxHeight: "600px" }}
                          />
                        </div>
                      )}

                      {activeTab === "links" && (
                        <div className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 space-y-4">
                          {result.links_detail && (
                            <div className="flex gap-4 text-sm pb-3 border-b border-border">
                              <div className="flex items-center gap-1.5">
                                <Link2 className="h-4 w-4 text-muted-foreground" />
                                <span className="font-medium">{result.links_detail.total}</span>
                                <span className="text-muted-foreground">total</span>
                              </div>
                              {result.links_detail.internal && (
                                <div className="flex items-center gap-1.5">
                                  <ArrowDownLeft className="h-4 w-4 text-blue-400" />
                                  <span className="font-medium">{result.links_detail.internal.count}</span>
                                  <span className="text-muted-foreground">internal</span>
                                </div>
                              )}
                              {result.links_detail.external && (
                                <div className="flex items-center gap-1.5">
                                  <ArrowUpRight className="h-4 w-4 text-orange-400" />
                                  <span className="font-medium">{result.links_detail.external.count}</span>
                                  <span className="text-muted-foreground">external</span>
                                </div>
                              )}
                            </div>
                          )}

                          {result.links_detail?.internal?.links?.length > 0 && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Internal Links</h4>
                              <div className="space-y-1">
                                {result.links_detail.internal.links.map((link: any, i: number) => (
                                  <div key={i} className="flex items-center gap-2 text-xs">
                                    <ArrowDownLeft className="h-3 w-3 text-blue-400 shrink-0" />
                                    <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                                      {link.url}
                                    </a>
                                    {link.text && <span className="text-muted-foreground truncate shrink-0 max-w-40">"{link.text}"</span>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {result.links_detail?.external?.links?.length > 0 && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">External Links</h4>
                              <div className="space-y-1">
                                {result.links_detail.external.links.map((link: any, i: number) => (
                                  <div key={i} className="flex items-center gap-2 text-xs">
                                    <ArrowUpRight className="h-3 w-3 text-orange-400 shrink-0" />
                                    <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                                      {link.url}
                                    </a>
                                    {link.text && <span className="text-muted-foreground truncate shrink-0 max-w-40">"{link.text}"</span>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {!result.links_detail && result.links && (
                            <div className="space-y-1">
                              {result.links.map((link: string, i: number) => (
                                <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="block text-xs text-primary hover:underline truncate">
                                  {link}
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {activeTab === "structured" && result.structured_data && (
                        <div className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 space-y-4">
                          {result.structured_data.json_ld && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2 flex items-center gap-1.5">
                                <Braces className="h-3.5 w-3.5" /> JSON-LD (Schema.org)
                              </h4>
                              <pre className="text-xs font-mono bg-background/50 rounded p-3 overflow-auto max-h-48">
                                {JSON.stringify(result.structured_data.json_ld, null, 2)}
                              </pre>
                            </div>
                          )}
                          {result.structured_data.open_graph && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">OpenGraph</h4>
                              <div className="grid grid-cols-1 gap-1">
                                {Object.entries(result.structured_data.open_graph).map(([key, val]) => (
                                  <div key={key} className="text-xs">
                                    <span className="text-muted-foreground">og:{key}:</span>{" "}
                                    <span className="font-mono">{String(val)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {result.structured_data.twitter_card && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Twitter Card</h4>
                              <div className="grid grid-cols-1 gap-1">
                                {Object.entries(result.structured_data.twitter_card).map(([key, val]) => (
                                  <div key={key} className="text-xs">
                                    <span className="text-muted-foreground">twitter:{key}:</span>{" "}
                                    <span className="font-mono">{String(val)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {result.structured_data.meta_tags && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">All Meta Tags</h4>
                              <div className="space-y-1 max-h-48 overflow-auto">
                                {Object.entries(result.structured_data.meta_tags).map(([key, val]) => (
                                  <div key={key} className="text-xs font-mono">
                                    <span className="text-muted-foreground">{key}:</span> {String(val)}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {activeTab === "headings" && result.headings && (
                        <div className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 space-y-1">
                          {result.headings.map((h: any, i: number) => (
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

                      {activeTab === "images" && result.images && (
                        <div className="max-h-[600px] overflow-auto rounded-md bg-muted p-4">
                          <div className="grid grid-cols-2 gap-3">
                            {result.images.map((img: any, i: number) => (
                              <div key={i} className="border border-border rounded-md overflow-hidden bg-background">
                                <div className="aspect-video bg-muted/50 flex items-center justify-center">
                                  <img
                                    src={img.src}
                                    alt={img.alt || ""}
                                    className="max-w-full max-h-full object-contain"
                                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                                  />
                                </div>
                                <div className="p-2">
                                  <p className="text-[11px] text-muted-foreground truncate" title={img.src}>
                                    {img.src.split("/").pop()}
                                  </p>
                                  {img.alt && <p className="text-[11px] truncate mt-0.5">{img.alt}</p>}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {activeTab === "extract" && result.extract && (
                        <pre className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 text-sm whitespace-pre-wrap font-mono">
                          {JSON.stringify(result.extract, null, 2)}
                        </pre>
                      )}

                      {activeTab === "json" && (
                        <pre className="max-h-[600px] overflow-auto rounded-md bg-muted p-4 text-xs whitespace-pre-wrap font-mono">
                          {JSON.stringify(result, null, 2)}
                        </pre>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {!result && status.status === "failed" && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <FileText className="h-12 w-12 text-muted-foreground/30 mb-4" />
                    <p className="text-sm text-muted-foreground">Scrape failed. No results available.</p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
        </div>
      </main>
    </div>
  );
}
