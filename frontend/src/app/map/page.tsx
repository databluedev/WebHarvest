"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExportDropdown } from "@/components/ui/export-dropdown";
import { api } from "@/lib/api";
import { Map as MapIcon, Loader2, Search, ExternalLink, Copy, Check } from "lucide-react";

export default function MapPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [useSitemap, setUseSitemap] = useState(true);

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  const handleMap = async () => {
    if (!url) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await api.mapSite({
        url,
        search: search || undefined,
        limit,
        include_subdomains: includeSubdomains || undefined,
        use_sitemap: useSitemap,
      });
      if (res.success && res.job_id) {
        router.push(`/map/${res.job_id}`);
        return;
      } else if (res.success) {
        setResult(res);
      } else {
        setError("Map failed");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyAllUrls = () => {
    if (!result?.links) return;
    const urls = result.links.map((l: any) => l.url).join("\n");
    navigator.clipboard.writeText(urls);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = (format: "zip" | "json" | "csv") => {
    if (!result?.links) return;
    const safeName = url.replace(/https?:\/\//, "").replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 60);

    if (format === "json") {
      const blob = new Blob([JSON.stringify(result.links, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `map-${safeName}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      return;
    }

    if (format === "csv") {
      const rows = [["url", "title", "description"]];
      result.links.forEach((l: any) => {
        rows.push([l.url, l.title || "", l.description || ""]);
      });
      const csv = rows.map((r) => r.map((v: string) => `"${v.replace(/"/g, '""')}"`).join(",")).join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `map-${safeName}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
      return;
    }

    // "zip" — export plain text URL list
    const urls = result.links.map((l: any) => l.url).join("\n");
    const blob = new Blob([urls], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `map-${safeName}-urls.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8">
          <div className="mb-6 animate-float-in">
            <h1 className="text-3xl font-bold">Map</h1>
            <p className="text-muted-foreground">Discover all URLs on a website</p>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Config */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Map a Website</CardTitle>
                  <CardDescription>Fast URL discovery via sitemaps and link crawling</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Website URL</label>
                    <Input
                      placeholder="https://example.com"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Filter by keyword (optional)</label>
                    <Input
                      placeholder="e.g., blog, pricing, documentation"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Max URLs</label>
                    <Input
                      type="number"
                      value={limit}
                      onChange={(e) => setLimit(parseInt(e.target.value) || 100)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Include subdomains</label>
                    <button
                      onClick={() => setIncludeSubdomains(!includeSubdomains)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        includeSubdomains ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {includeSubdomains ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Use sitemap</label>
                    <button
                      onClick={() => setUseSitemap(!useSitemap)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        useSitemap ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {useSitemap ? "On" : "Off"}
                    </button>
                  </div>

                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                      {error}
                    </div>
                  )}

                  <Button onClick={handleMap} disabled={loading || !url} className="w-full gap-2">
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    Map Website
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Results */}
            <div>
              {result ? (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        Discovered URLs
                        <Badge variant="outline" className="ml-2">{result.total}</Badge>
                      </CardTitle>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={copyAllUrls} className="gap-1">
                          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          Copy All
                        </Button>
                        <ExportDropdown onExport={handleExport} formats={["json", "csv"]} />
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-[600px] overflow-auto space-y-1">
                      {result.links.map((link: any, i: number) => (
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
                          </div>
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="opacity-0 group-hover:opacity-100 transition-opacity ml-2"
                          >
                            <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                          </a>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <MapIcon className="h-12 w-12 text-muted-foreground mb-4" />
                    <p className="text-lg font-medium">Map a website</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Discover all URLs via sitemaps and homepage crawl
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
