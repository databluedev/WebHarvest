"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  Copy,
  Check,
  Loader2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Globe,
  FileText,
  Code,
  Play,
} from "lucide-react";

type InputMode = "url" | "content" | "html";

const PROVIDERS = [
  { value: "", label: "Default (auto)" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "groq", label: "Groq" },
  { value: "ollama", label: "Ollama" },
  { value: "deepseek", label: "DeepSeek" },
];

const INPUT_TABS: { id: InputMode; label: string; icon: typeof Globe }[] = [
  { id: "url", label: "URL", icon: Globe },
  { id: "content", label: "Content", icon: FileText },
  { id: "html", label: "HTML", icon: Code },
];

export default function ExtractPage() {
  const router = useRouter();

  // -- Input state --
  const [inputMode, setInputMode] = useState<InputMode>("url");
  const [url, setUrl] = useState("");
  const [multiUrls, setMultiUrls] = useState("");
  const [content, setContent] = useState("");
  const [html, setHtml] = useState("");
  const [prompt, setPrompt] = useState("");
  const [schemaText, setSchemaText] = useState("");
  const [provider, setProvider] = useState("");
  const [showSchema, setShowSchema] = useState(false);
  const [onlyMainContent, setOnlyMainContent] = useState(true);
  const [useProxy, setUseProxy] = useState(false);

  // -- Result state --
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // -- Async polling --
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<{ completed: number; total: number } | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollJob = useCallback(
    (id: string) => {
      setJobId(id);
      setJobStatus("running");

      pollingRef.current = setInterval(async () => {
        try {
          const res = await api.getExtractStatus(id);
          setJobProgress({
            completed: res.completed_urls ?? 0,
            total: res.total_urls ?? 0,
          });
          setJobStatus(res.status);

          if (res.status === "completed" || res.status === "failed") {
            stopPolling();
            if (res.status === "completed" && res.data) {
              setResult(res.data);
              setLoading(false);
            } else if (res.status === "failed") {
              setError(res.error || "Extraction job failed.");
              setLoading(false);
            }
          }
        } catch (err: any) {
          stopPolling();
          setError(err.message || "Failed to poll job status.");
          setLoading(false);
        }
      }, 2000);
    },
    [stopPolling]
  );

  const isMultiUrl = inputMode === "url" && multiUrls.trim().length > 0;

  const handleExtract = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    setJobId(null);
    setJobStatus(null);
    setJobProgress(null);
    stopPolling();

    try {
      // Parse optional JSON schema
      let parsedSchema: object | undefined;
      if (schemaText.trim()) {
        try {
          parsedSchema = JSON.parse(schemaText);
        } catch {
          setError("Invalid JSON schema. Please check the syntax.");
          setLoading(false);
          return;
        }
      }

      // Build request params
      const params: Parameters<typeof api.extract>[0] = {};

      if (inputMode === "url") {
        if (isMultiUrl) {
          const urls = multiUrls
            .split("\n")
            .map((l) => l.trim())
            .filter(Boolean);
          if (urls.length === 0) {
            setError("Please enter at least one URL.");
            setLoading(false);
            return;
          }
          params.urls = urls;
        } else {
          if (!url.trim()) {
            setError("Please enter a URL.");
            setLoading(false);
            return;
          }
          params.url = url.trim();
        }
      } else if (inputMode === "content") {
        if (!content.trim()) {
          setError("Please enter content text.");
          setLoading(false);
          return;
        }
        params.content = content;
      } else if (inputMode === "html") {
        if (!html.trim()) {
          setError("Please enter HTML.");
          setLoading(false);
          return;
        }
        params.html = html;
      }

      if (prompt.trim()) params.prompt = prompt.trim();
      if (parsedSchema) params.schema_ = parsedSchema;
      if (provider) params.provider = provider;
      if (onlyMainContent) params.only_main_content = true;
      if (useProxy) params.use_proxy = true;

      const res = await api.extract(params);

      if (res.job_id) {
        // Async mode -- start polling
        pollJob(res.job_id);
        return;
      }

      if (!res.success) {
        setError(res.error || "Extraction failed.");
        if (res.data) setResult(res.data);
      } else if (res.data) {
        setResult(res.data);
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      // Only clear loading for sync responses; async is handled by pollJob
      if (!jobId) setLoading(false);
    }
  };

  const copyToClipboard = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, []);

  const formattedResult = result ? JSON.stringify(result, null, 2) : "";

  const canSubmit = (() => {
    if (loading) return false;
    if (inputMode === "url") return !!(url.trim() || multiUrls.trim());
    if (inputMode === "content") return !!content.trim();
    if (inputMode === "html") return !!html.trim();
    return false;
  })();

  const multiUrlCount = multiUrls
    .split("\n")
    .filter((l) => l.trim()).length;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto grid-bg">
        <div className="mesh-gradient min-h-full">
        <div className="p-8 max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6 animate-float-in">
            <div className="flex items-center gap-3 mb-1">
              <div className="h-9 w-9 rounded-xl bg-purple-500/10 grid place-items-center animate-glow-pulse">
                <Sparkles className="h-4.5 w-4.5 text-purple-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Extract</h1>
                <p className="text-sm text-muted-foreground">
                  AI-powered structured data extraction from URLs, text, or HTML
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            {/* ====== LEFT PANEL: Configuration ====== */}
            <div className="lg:col-span-2 space-y-4">
              {/* Input Source */}
              <Card>
                <CardContent className="pt-6 space-y-4">
                  {/* Tab selector */}
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase mb-2 block">
                      Input Source
                    </label>
                    <div className="flex gap-1 p-1 rounded-lg bg-muted/50">
                      {INPUT_TABS.map((tab) => {
                        const Icon = tab.icon;
                        return (
                          <button
                            key={tab.id}
                            onClick={() => setInputMode(tab.id)}
                            className={`flex items-center gap-1.5 flex-1 justify-center px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                              inputMode === tab.id
                                ? "bg-primary text-primary-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                            }`}
                          >
                            <Icon className="h-3.5 w-3.5" />
                            {tab.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* URL input */}
                  {inputMode === "url" && (
                    <div className="space-y-3">
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground">
                          Single URL
                        </label>
                        <Input
                          placeholder="https://example.com/page"
                          value={url}
                          onChange={(e) => setUrl(e.target.value)}
                          onKeyDown={(e) =>
                            e.key === "Enter" && canSubmit && handleExtract()
                          }
                          className="h-10 font-mono text-sm"
                          disabled={multiUrls.trim().length > 0}
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-px bg-border" />
                        <span className="text-[10px] text-muted-foreground uppercase">
                          or batch
                        </span>
                        <div className="flex-1 h-px bg-border" />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground">
                          Multiple URLs{" "}
                          {multiUrlCount > 0 && (
                            <span className="text-foreground/60">
                              ({multiUrlCount})
                            </span>
                          )}
                        </label>
                        <Textarea
                          placeholder={"https://example.com/page-1\nhttps://example.com/page-2\nhttps://example.com/page-3"}
                          value={multiUrls}
                          onChange={(e) => setMultiUrls(e.target.value)}
                          rows={4}
                          className="font-mono text-sm resize-none"
                          disabled={url.trim().length > 0}
                        />
                        {multiUrlCount > 0 && (
                          <p className="text-[11px] text-muted-foreground">
                            Batch mode: extraction runs asynchronously
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Content input */}
                  {inputMode === "content" && (
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">
                        Text Content
                      </label>
                      <Textarea
                        placeholder="Paste the text content you want to extract data from..."
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        rows={8}
                        className="text-sm resize-none"
                      />
                    </div>
                  )}

                  {/* HTML input */}
                  {inputMode === "html" && (
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">
                        Raw HTML
                      </label>
                      <Textarea
                        placeholder={'<html>\n  <body>\n    <h1>Product Name</h1>\n    <span class="price">$29.99</span>\n  </body>\n</html>'}
                        value={html}
                        onChange={(e) => setHtml(e.target.value)}
                        rows={8}
                        className="font-mono text-xs resize-none"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Extraction Prompt */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-purple-400" />
                    Extraction Prompt
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Textarea
                    placeholder="e.g., Extract the product name, price, rating, and all review summaries as a list"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={3}
                    className="text-sm resize-none"
                  />
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Describe what data you want extracted. Be specific for better results.
                  </p>
                </CardContent>
              </Card>

              {/* JSON Schema (collapsible) */}
              <Card>
                <CardContent className="pt-4">
                  <button
                    onClick={() => setShowSchema(!showSchema)}
                    className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full"
                  >
                    {showSchema ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <Code className="h-4 w-4" />
                    <span>JSON Schema</span>
                    <Badge variant="outline" className="ml-auto text-[10px]">
                      Optional
                    </Badge>
                  </button>

                  {showSchema && (
                    <div className="mt-4 space-y-2 pt-3 border-t border-border">
                      <Textarea
                        placeholder={'{\n  "type": "object",\n  "properties": {\n    "name": { "type": "string" },\n    "price": { "type": "number" },\n    "features": {\n      "type": "array",\n      "items": { "type": "string" }\n    }\n  },\n  "required": ["name", "price"]\n}'}
                        value={schemaText}
                        onChange={(e) => setSchemaText(e.target.value)}
                        rows={8}
                        className="font-mono text-xs resize-none"
                      />
                      <p className="text-[11px] text-muted-foreground">
                        Provide a JSON Schema to enforce the structure of the extracted data.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Provider */}
              <Card>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-muted-foreground">
                      LLM Provider
                    </label>
                    <select
                      value={provider}
                      onChange={(e) => setProvider(e.target.value)}
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Requires a configured LLM key in Settings (BYOK).
                  </p>
                </CardContent>
              </Card>

              {/* Options */}
              <Card>
                <CardContent className="pt-4 pb-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-muted-foreground">Main content only</label>
                    <button
                      onClick={() => setOnlyMainContent(!onlyMainContent)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        onlyMainContent ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {onlyMainContent ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-muted-foreground">Use Proxy</label>
                    <button
                      onClick={() => setUseProxy(!useProxy)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        useProxy ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {useProxy ? "On" : "Off"}
                    </button>
                  </div>
                </CardContent>
              </Card>

              {/* Submit */}
              <Button
                onClick={handleExtract}
                disabled={!canSubmit}
                className="w-full h-11 gap-2 text-sm"
                size="lg"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {loading
                  ? jobId
                    ? "Extracting..."
                    : "Processing..."
                  : isMultiUrl
                  ? `Extract from ${multiUrlCount} URLs`
                  : "Extract Data"}
              </Button>
            </div>

            {/* ====== RIGHT PANEL: Results ====== */}
            <div className="lg:col-span-3">
              {/* Error display */}
              {error && (
                <Card className="border-destructive/50 mb-4">
                  <CardContent className="p-4 flex items-start gap-3">
                    <AlertCircle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-sm text-red-400">{error}</p>
                  </CardContent>
                </Card>
              )}

              {/* Async job status indicator */}
              {jobId && jobStatus && jobStatus !== "completed" && jobStatus !== "failed" && (
                <Card className="mb-4">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                        <span className="text-sm font-medium">
                          Async Extraction
                        </span>
                      </div>
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {jobStatus}
                      </Badge>
                    </div>
                    {jobProgress && jobProgress.total > 0 && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>
                            {jobProgress.completed} of {jobProgress.total} URLs
                          </span>
                          <span>
                            {Math.round(
                              (jobProgress.completed / jobProgress.total) * 100
                            )}
                            %
                          </span>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-purple-500 rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.min(
                                100,
                                (jobProgress.completed / jobProgress.total) * 100
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                    <p className="text-[11px] text-muted-foreground mt-2 font-mono">
                      Job: {jobId}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Result viewer */}
              {result && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-purple-400" />
                        Extracted Data
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        {jobId && (
                          <Badge
                            variant="outline"
                            className="text-[10px] border-green-500/50 text-green-400"
                          >
                            completed
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 gap-1.5 text-xs"
                          onClick={() => copyToClipboard(formattedResult)}
                        >
                          {copied ? (
                            <>
                              <Check className="h-3 w-3" />
                              Copied
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3" />
                              Copy JSON
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="max-h-[650px] overflow-auto rounded-lg bg-muted p-4 text-xs whitespace-pre-wrap font-mono leading-relaxed">
                      {formattedResult}
                    </pre>
                  </CardContent>
                </Card>
              )}

              {/* Empty state */}
              {!result && !error && !loading && !jobId && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="h-16 w-16 rounded-2xl bg-purple-500/10 grid place-items-center mb-5">
                      <Sparkles className="h-7 w-7 text-purple-400/60" />
                    </div>
                    <p className="text-lg font-medium">
                      AI-Powered Extraction
                    </p>
                    <p className="text-sm text-muted-foreground mt-2 max-w-md leading-relaxed">
                      Provide a URL, text content, or raw HTML along with an extraction prompt.
                      The AI will return structured JSON data based on your instructions.
                    </p>
                    <div className="mt-6 grid grid-cols-3 gap-3 max-w-sm w-full">
                      {[
                        { step: "1", label: "Choose input", desc: "URL, text, or HTML" },
                        { step: "2", label: "Write prompt", desc: "What to extract" },
                        { step: "3", label: "Get JSON", desc: "Structured output" },
                      ].map((item) => (
                        <div
                          key={item.step}
                          className="glass-card rounded-xl p-3 text-center"
                        >
                          <div className="text-xs font-bold text-purple-400 font-mono mb-1">
                            {item.step}
                          </div>
                          <p className="text-xs font-medium">{item.label}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            {item.desc}
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Loading state (sync) */}
              {loading && !jobId && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-20 text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-purple-400 mb-4" />
                    <p className="text-sm text-muted-foreground">
                      Extracting structured data...
                    </p>
                    <p className="text-xs text-muted-foreground/70 mt-1">
                      This may take a few seconds depending on the content size
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
        </div>
      </main>
    </div>
  );
}
