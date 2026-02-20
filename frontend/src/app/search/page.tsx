"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { ModeSwitcher } from "@/components/layout/mode-switcher";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Search, Loader2, Play, Info, Sparkles, ChevronDown, ChevronUp, Settings2 } from "lucide-react";

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [engine, setEngine] = useState("duckduckgo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [extractEnabled, setExtractEnabled] = useState(false);
  const [extractPrompt, setExtractPrompt] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [onlyMainContent, setOnlyMainContent] = useState(true);
  const [useProxy, setUseProxy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobileDevice, setMobileDevice] = useState("");
  const [devicePresets, setDevicePresets] = useState<any[]>([]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  // Format toggles — now all 7 formats
  const [formats, setFormats] = useState<string[]>(["markdown"]);
  const allFormats = ["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"];

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  useEffect(() => {
    if (mobile && devicePresets.length === 0) {
      api.getDevicePresets().then(res => setDevicePresets(res.devices || [])).catch(() => {});
    }
  }, [mobile]);

  const toggleFormat = (f: string) => {
    setFormats((prev) =>
      prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]
    );
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");

    try {
      const params: any = {
        query: query.trim(),
        num_results: numResults,
        engine,
        formats,
        only_main_content: onlyMainContent,
        use_proxy: useProxy || undefined,
        mobile: mobile || undefined,
        mobile_device: (mobile && mobileDevice) ? mobileDevice : undefined,
        webhook_url: webhookUrl.trim() || undefined,
        webhook_secret: webhookSecret.trim() || undefined,
      };
      if (extractEnabled && extractPrompt.trim()) {
        params.extract = { prompt: extractPrompt.trim() };
      }
      const res = await api.startSearch(params);
      if (res.success) {
        router.push(`/search/${res.job_id}`);
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && query.trim() && !loading) {
      handleSearch();
    }
  };

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="min-h-screen flex flex-col">
        <div className="flex-1 p-6 lg:p-8 max-w-4xl mx-auto w-full">
          {/* Mode Switcher */}
          <div className="pt-4 pb-6 animate-float-in">
            <ModeSwitcher />
          </div>

          <div className="mb-8 animate-float-in" style={{ animationDelay: "0.05s" }}>
            <h1 className="text-3xl font-bold">Search & Scrape</h1>
            <p className="text-muted-foreground mt-1">
              Search the web and automatically scrape the top results. Get structured content from any search query.
            </p>
          </div>

          <Card className="mb-6">
            <CardContent className="pt-6 space-y-4">
              {/* Search input */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Search the web..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="h-12 text-base"
                  />
                </div>
                <Button
                  onClick={handleSearch}
                  disabled={loading || !query.trim()}
                  className="h-12 px-6 gap-2"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  Search
                </Button>
              </div>

              {/* Engine selector */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Search Engine</label>
                <div className="flex gap-2">
                  <Button
                    variant={engine === "duckduckgo" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setEngine("duckduckgo")}
                  >
                    DuckDuckGo
                  </Button>
                  <Button
                    variant={engine === "brave" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setEngine("brave")}
                  >
                    Brave
                  </Button>
                  <Button
                    variant={engine === "google" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setEngine("google")}
                  >
                    Google (BYOK)
                  </Button>
                </div>
              </div>

              {/* Number of results slider */}
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Number of results to scrape: {numResults}
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={numResults}
                  onChange={(e) => setNumResults(parseInt(e.target.value))}
                  className="w-full accent-primary"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>1</span>
                  <span>10</span>
                </div>
              </div>

              {/* Formats */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Output Formats</label>
                <div className="flex flex-wrap gap-2">
                  {allFormats.map((f) => (
                    <Button
                      key={f}
                      variant={formats.includes(f) ? "default" : "outline"}
                      size="sm"
                      onClick={() => toggleFormat(f)}
                      className="text-xs"
                    >
                      {f}
                    </Button>
                  ))}
                </div>
              </div>

              {/* AI Extraction */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4" />
                    AI Extraction (BYOK)
                    <span className="text-xs text-muted-foreground font-normal">
                      (requires LLM key in Settings)
                    </span>
                  </label>
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
                {extractEnabled && (
                  <Textarea
                    placeholder="e.g., Extract the main topic, key facts, and sentiment from each result"
                    value={extractPrompt}
                    onChange={(e) => setExtractPrompt(e.target.value)}
                    rows={3}
                    className="text-sm"
                  />
                )}
              </div>

              {/* Advanced Options */}
              <div className="space-y-2">
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Settings2 className="h-4 w-4" />
                  Advanced Options
                  {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>

                {showAdvanced && (
                  <div className="space-y-4 pt-3 border-t border-border">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Main content only</label>
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
                      <label className="text-sm font-medium">Use Proxy</label>
                      <button
                        onClick={() => setUseProxy(!useProxy)}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          useProxy ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {useProxy ? "On" : "Off"}
                      </button>
                    </div>

                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Mobile Emulation</label>
                      <button
                        onClick={() => setMobile(!mobile)}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          mobile ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {mobile ? "On" : "Off"}
                      </button>
                    </div>
                    {mobile && devicePresets.length > 0 && (
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Device</label>
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

                    <div className="space-y-2">
                      <label className="text-sm font-medium">Webhook URL</label>
                      <Input
                        placeholder="https://your-server.com/webhook"
                        value={webhookUrl}
                        onChange={(e) => setWebhookUrl(e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium">Webhook Secret</label>
                      <Input
                        placeholder="your-secret-key"
                        value={webhookSecret}
                        onChange={(e) => setWebhookSecret(e.target.value)}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3">
                <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-xs text-muted-foreground">
                  We search the web using {engine === "duckduckgo" ? "DuckDuckGo (no API key needed)" : "Google Custom Search (requires your API key)"},
                  then scrape the top {numResults} result{numResults !== 1 ? "s" : ""} for content.
                </p>
              </div>

              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}
            </CardContent>
          </Card>

          {/* How it works */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">How It Works</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">1</div>
                  <p className="text-sm font-medium">Search</p>
                  <p className="text-xs text-muted-foreground mt-1">Your query is sent to the search engine</p>
                </div>
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">2</div>
                  <p className="text-sm font-medium">Scrape</p>
                  <p className="text-xs text-muted-foreground mt-1">Top results are scraped for content</p>
                </div>
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">3</div>
                  <p className="text-sm font-medium">Extract</p>
                  <p className="text-xs text-muted-foreground mt-1">Get markdown, HTML, and metadata</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        <Footer />
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
