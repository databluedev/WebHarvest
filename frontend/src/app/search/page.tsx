"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Search, Loader2, Play, Info } from "lucide-react";

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [engine, setEngine] = useState("duckduckgo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Format toggles
  const [formats, setFormats] = useState<string[]>(["markdown"]);
  const allFormats = ["markdown", "html", "links"];

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

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
      const res = await api.startSearch({
        query: query.trim(),
        num_results: numResults,
        engine,
        formats,
      });
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
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-4xl mx-auto">
          <div className="mb-8">
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
      </main>
    </div>
  );
}
