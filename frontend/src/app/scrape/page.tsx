"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import {
  Search,
  Loader2,
  Copy,
  Check,
  FileText,
  Code,
  Link2,
  Camera,
  Braces,
  List,
  Image as ImageIcon,
  FileCode,
  ChevronDown,
  ChevronUp,
  Settings2,
  Info,
  Clock,
  ArrowUpRight,
  ArrowDownLeft,
  Sparkles,
} from "lucide-react";

type TabId = "markdown" | "html" | "screenshot" | "links" | "structured" | "headings" | "images" | "extract" | "json";

export default function ScrapePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [formats, setFormats] = useState<string[]>(["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"]);
  const [onlyMainContent, setOnlyMainContent] = useState(true);
  const [waitFor, setWaitFor] = useState(0);
  const [extractEnabled, setExtractEnabled] = useState(false);
  const [extractPrompt, setExtractPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("markdown");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [useProxy, setUseProxy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobileDevice, setMobileDevice] = useState("");
  const [devicePresets, setDevicePresets] = useState<any[]>([]);
  const [headersText, setHeadersText] = useState("");
  const [cookiesText, setCookiesText] = useState("");

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then(res => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

  const toggleFormat = (format: string) => {
    setFormats((prev) =>
      prev.includes(format) ? prev.filter((f) => f !== format) : [...prev, format]
    );
  };

  const handleScrape = async () => {
    if (!url) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const params: any = {
        url,
        formats,
        only_main_content: onlyMainContent,
        wait_for: waitFor,
        use_proxy: useProxy || undefined,
        mobile: mobile || undefined,
        mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined,
      };
      if (extractEnabled && extractPrompt) {
        params.extract = { prompt: extractPrompt };
      }
      if (headersText.trim()) {
        try { params.headers = JSON.parse(headersText); } catch {}
      }
      if (cookiesText.trim()) {
        try { params.cookies = JSON.parse(cookiesText); } catch {}
      }
      const res = await api.scrape(params);
      if (!res.success) {
        setError(res.error || "Scrape failed — the site may be blocking requests.");
        if (res.data) setResult(res.data);
      } else if (res.job_id) {
        router.push(`/scrape/${res.job_id}`);
        return;
      } else if (res.data) {
        setResult(res.data);
        // Auto-select first available tab
        if (res.data.markdown) setActiveTab("markdown");
        else if (res.data.screenshot) setActiveTab("screenshot");
        else setActiveTab("json");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatToggles = [
    { id: "markdown", label: "Markdown", icon: FileText },
    { id: "html", label: "HTML", icon: Code },
    { id: "links", label: "Links", icon: Link2 },
    { id: "screenshot", label: "Screenshot", icon: Camera },
    { id: "structured_data", label: "Structured Data", icon: Braces },
    { id: "headings", label: "Headings", icon: List },
    { id: "images", label: "Images", icon: ImageIcon },
  ];

  // Build tabs from result data
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

  const handleExport = (format: "zip" | "json" | "csv") => {
    if (!result) return;
    const safeName = url.replace(/https?:\/\//, "").replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 60);

    if (format === "json") {
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `scrape-${safeName}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      return;
    }

    if (format === "csv") {
      const meta = result.metadata || {};
      const rows = [
        ["url", "title", "status_code", "word_count", "reading_time_min", "markdown_length", "html_length", "links_count"],
        [url, meta.title || "", meta.status_code || "", meta.word_count || "", meta.reading_time_seconds ? Math.ceil(meta.reading_time_seconds / 60) : "", (result.markdown || "").length, (result.html || "").length, (result.links || []).length],
      ];
      const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `scrape-${safeName}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
      return;
    }

    // ZIP — since no server endpoint for single scrape, build a simple multi-file download
    // We'll export as JSON for zip since we can't create real ZIP client-side without a library
    // But we can create a structured JSON file that mirrors the ZIP structure
    const zipContent: Record<string, string> = {};
    if (result.markdown) zipContent["content.md"] = result.markdown;
    if (result.html) zipContent["content.html"] = result.html;
    zipContent["metadata.json"] = JSON.stringify({ url, metadata: result.metadata, structured_data: result.structured_data, headings: result.headings, images: result.images, links: result.links }, null, 2);
    zipContent["full_data.json"] = JSON.stringify(result, null, 2);

    // Download as combined JSON (since true ZIP requires a library)
    const blob = new Blob([JSON.stringify(zipContent, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `scrape-${safeName}-bundle.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-6xl mx-auto">
          <div className="mb-6">
            <h1 className="text-3xl font-bold">Scrape</h1>
            <p className="text-muted-foreground">Extract rich content from any URL</p>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            {/* Config Panel - narrower */}
            <div className="lg:col-span-2 space-y-4">
              {/* URL Input */}
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex gap-2">
                    <Input
                      placeholder="https://example.com/page"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !loading && url && handleScrape()}
                      className="h-11"
                    />
                    <Button onClick={handleScrape} disabled={loading || !url} className="h-11 px-4">
                      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    </Button>
                  </div>

                  {/* Format toggles */}
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase mb-2 block">Output Formats</label>
                    <div className="flex flex-wrap gap-1.5">
                      {formatToggles.map((fmt) => (
                        <button
                          key={fmt.id}
                          onClick={() => toggleFormat(fmt.id)}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                            formats.includes(fmt.id)
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          <fmt.icon className="h-3 w-3" />
                          {fmt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Advanced Options */}
              <Card>
                <CardContent className="pt-4">
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full"
                  >
                    <Settings2 className="h-4 w-4" />
                    <span>Advanced Options</span>
                    {showAdvanced ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
                  </button>

                  {showAdvanced && (
                    <div className="mt-4 space-y-4 pt-3 border-t border-border">
                      <div className="flex items-center justify-between">
                        <label className="text-sm">Main content only</label>
                        <button
                          onClick={() => setOnlyMainContent(!onlyMainContent)}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            onlyMainContent
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {onlyMainContent ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-sm">Wait after load (ms)</label>
                        <Input
                          type="number"
                          value={waitFor}
                          onChange={(e) => setWaitFor(parseInt(e.target.value) || 0)}
                          placeholder="0"
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-sm">Use Proxy</label>
                        <button
                          onClick={() => setUseProxy(!useProxy)}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            useProxy
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {useProxy ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <label className="text-sm">Mobile Emulation</label>
                        <button
                          onClick={() => setMobile(!mobile)}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            mobile
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {mobile ? "On" : "Off"}
                        </button>
                      </div>
                      {mobile && devicePresets.length > 0 && (
                        <div className="space-y-1.5">
                          <label className="text-sm">Device</label>
                          <select
                            value={mobileDevice}
                            onChange={(e) => setMobileDevice(e.target.value)}
                            className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                          >
                            <option value="">Default mobile</option>
                            {devicePresets.map((d: any) => (
                              <option key={d.id} value={d.id}>{d.name} ({d.width}x{d.height})</option>
                            ))}
                          </select>
                        </div>
                      )}
                      <div className="space-y-1.5">
                        <label className="text-sm">Custom Headers (JSON)</label>
                        <textarea
                          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[60px]"
                          placeholder='{"Authorization": "Bearer ..."}'
                          value={headersText}
                          onChange={(e) => setHeadersText(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-sm">Cookies (JSON)</label>
                        <textarea
                          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[60px]"
                          placeholder='{"session_id": "abc123"}'
                          value={cookiesText}
                          onChange={(e) => setCookiesText(e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* AI Extraction */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4" />
                      AI Extraction (BYOK)
                    </CardTitle>
                    <button
                      onClick={() => setExtractEnabled(!extractEnabled)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        extractEnabled
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {extractEnabled ? "On" : "Off"}
                    </button>
                  </div>
                  <CardDescription className="text-xs">Requires an LLM key in Settings</CardDescription>
                </CardHeader>
                {extractEnabled && (
                  <CardContent>
                    <Textarea
                      placeholder="e.g., Extract the product name, price, and description"
                      value={extractPrompt}
                      onChange={(e) => setExtractPrompt(e.target.value)}
                      rows={3}
                      className="text-sm"
                    />
                  </CardContent>
                )}
              </Card>
            </div>

            {/* Results Panel - wider */}
            <div className="lg:col-span-3">
              {error && (
                <Card className="border-destructive mb-4">
                  <CardContent className="p-4">
                    <p className="text-sm text-red-400">{error}</p>
                  </CardContent>
                </Card>
              )}

              {result && (
                <Card>
                  {/* Result header with metadata */}
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Result</CardTitle>
                      <div className="flex gap-2">
                        <ExportDropdown onExport={handleExport} formats={["json", "csv"]} />
                        {result.metadata?.status_code && (
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
                        {result.metadata?.word_count > 0 && (
                          <Badge variant="outline">{result.metadata.word_count.toLocaleString()} words</Badge>
                        )}
                        {result.metadata?.reading_time_seconds > 0 && (
                          <Badge variant="outline" className="gap-1">
                            <Clock className="h-3 w-3" />
                            {Math.ceil(result.metadata.reading_time_seconds / 60)}m read
                          </Badge>
                        )}
                      </div>
                    </div>
                    {result.metadata?.title && (
                      <CardDescription className="truncate">{result.metadata.title}</CardDescription>
                    )}
                  </CardHeader>

                  <CardContent>
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

                      {/* Tab content */}
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
                            alt={`Screenshot of ${url}`}
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

                          {/* Fallback: simple link list */}
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

              {!result && !error && !loading && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-20 text-center">
                    <Search className="h-12 w-12 text-muted-foreground/40 mb-4" />
                    <p className="text-lg font-medium">Enter a URL to scrape</p>
                    <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                      Get markdown, HTML, screenshots, links, structured data, headings, images, and more
                    </p>
                  </CardContent>
                </Card>
              )}

              {loading && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-20 text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
                    <p className="text-sm text-muted-foreground">
                      Scraping {url}...
                    </p>
                    {formats.includes("screenshot") && (
                      <p className="text-xs text-muted-foreground/70 mt-1">
                        Taking screenshot (this may take a few seconds)
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
