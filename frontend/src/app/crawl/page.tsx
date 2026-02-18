"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Globe, Loader2, Play, Eye, ChevronDown, ChevronUp, Settings2, Info } from "lucide-react";
import Link from "next/link";

export default function CrawlPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);
  const [error, setError] = useState("");

  // Advanced options (collapsed by default)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxPages, setMaxPages] = useState(100);
  const [maxDepth, setMaxDepth] = useState(3);
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  const handleStartCrawl = async () => {
    if (!url) return;
    setLoading(true);
    setError("");

    try {
      const params: any = { url };

      // Only send advanced options if user explicitly configured them
      if (showAdvanced) {
        params.max_pages = maxPages;
        params.max_depth = maxDepth;
        if (includePaths.trim()) params.include_paths = includePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
        if (excludePaths.trim()) params.exclude_paths = excludePaths.split(",").map((p: string) => p.trim()).filter(Boolean);
      }

      const res = await api.startCrawl(params);
      if (res.success) {
        // Redirect immediately to the crawl status page
        router.push(`/crawl/${res.job_id}`);
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && url && !loading) {
      handleStartCrawl();
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-3xl font-bold">Crawl</h1>
            <p className="text-muted-foreground mt-1">
              Enter a website URL and we'll recursively discover and scrape every page.
            </p>
          </div>

          {/* Main crawl input */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="https://example.com"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="h-12 text-base"
                  />
                </div>
                <Button
                  onClick={handleStartCrawl}
                  disabled={loading || !url}
                  className="h-12 px-6 gap-2"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Start Crawl
                </Button>
              </div>

              {error && (
                <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {/* Advanced Options Toggle */}
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="mt-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <Settings2 className="h-4 w-4" />
                Advanced Options
                {showAdvanced ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </button>

              {/* Advanced Options Panel */}
              {showAdvanced && (
                <div className="mt-4 pt-4 border-t border-border space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-1.5">
                        Page Limit
                        <span className="text-xs text-muted-foreground font-normal">
                          (max pages to crawl)
                        </span>
                      </label>
                      <Input
                        type="number"
                        value={maxPages}
                        onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)}
                        min={1}
                        max={10000}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-1.5">
                        Link Depth
                        <span className="text-xs text-muted-foreground font-normal">
                          (how many clicks deep)
                        </span>
                      </label>
                      <Input
                        type="number"
                        value={maxDepth}
                        onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)}
                        min={1}
                        max={20}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Only Crawl These Paths
                      <span className="text-xs text-muted-foreground font-normal">
                        (comma-separated, e.g. /blog/*, /docs/*)
                      </span>
                    </label>
                    <Input
                      placeholder="Leave empty to crawl everything"
                      value={includePaths}
                      onChange={(e) => setIncludePaths(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-1.5">
                      Skip These Paths
                      <span className="text-xs text-muted-foreground font-normal">
                        (comma-separated, e.g. /admin/*, /login)
                      </span>
                    </label>
                    <Input
                      placeholder="Leave empty to skip nothing"
                      value={excludePaths}
                      onChange={(e) => setExcludePaths(e.target.value)}
                    />
                  </div>

                  <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3">
                    <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <p className="text-xs text-muted-foreground">
                      Default: crawl up to 100 pages, 3 links deep, staying on the same domain.
                      The crawler respects robots.txt and skips files like images, PDFs, and stylesheets.
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Crawls */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Crawls</CardTitle>
              <CardDescription>Your crawl history from this session</CardDescription>
            </CardHeader>
            <CardContent>
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Globe className="h-12 w-12 text-muted-foreground/40 mb-4" />
                  <p className="text-sm text-muted-foreground">
                    No crawls started yet. Enter a URL above to begin.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {jobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{job.url}</p>
                        <p className="text-xs text-muted-foreground font-mono">{job.id}</p>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <Badge
                          variant={
                            job.status === "completed"
                              ? "success"
                              : job.status === "failed"
                              ? "destructive"
                              : "warning"
                          }
                        >
                          {job.status}
                        </Badge>
                        <Link href={`/crawl/${job.id}`}>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
