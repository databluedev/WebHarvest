"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Layers, Loader2, Play, Info, Eye } from "lucide-react";
import Link from "next/link";

export default function BatchPage() {
  const router = useRouter();
  const [urlText, setUrlText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [concurrency, setConcurrency] = useState(5);
  const [recentJobs, setRecentJobs] = useState<any[]>([]);

  // Format toggles
  const [formats, setFormats] = useState<string[]>(["markdown"]);

  const allFormats = ["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"];

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    api.getUsageHistory({ type: "batch", per_page: 10, sort_by: "created_at", sort_dir: "desc" })
      .then((res) => {
        setRecentJobs(res.jobs.map((j: any) => ({
          id: j.id,
          total: j.total_pages,
          completed: j.completed_pages,
          status: j.status,
          created_at: j.created_at,
        })));
      })
      .catch(() => {});
  }, [router]);

  const toggleFormat = (f: string) => {
    setFormats((prev) =>
      prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]
    );
  };

  const handleStart = async () => {
    const urls = urlText.split("\n").map((l) => l.trim()).filter(Boolean);
    if (urls.length === 0) return;
    setLoading(true);
    setError("");

    try {
      const res = await api.startBatch({
        urls,
        formats,
        concurrency,
      });
      if (res.success) {
        router.push(`/batch/${res.job_id}`);
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const urlCount = urlText.split("\n").filter((l) => l.trim()).length;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-3xl font-bold">Batch Scrape</h1>
            <p className="text-muted-foreground mt-1">
              Scrape multiple URLs in one go. Enter URLs below (one per line) and we'll process them concurrently.
            </p>
          </div>

          <Card className="mb-6">
            <CardContent className="pt-6 space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">URLs (one per line)</label>
                <textarea
                  className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 font-mono"
                  placeholder={"https://example.com\nhttps://another-site.com/page\nhttps://docs.example.com/api"}
                  value={urlText}
                  onChange={(e) => setUrlText(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  {urlCount} URL{urlCount !== 1 ? "s" : ""} entered (max 100)
                </p>
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
                      {f.replace("_", " ")}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Concurrency */}
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Concurrency: {concurrency}
                </label>
                <input
                  type="range"
                  min={1}
                  max={20}
                  value={concurrency}
                  onChange={(e) => setConcurrency(parseInt(e.target.value))}
                  className="w-full accent-primary"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>1 (slow, gentle)</span>
                  <span>20 (fast, aggressive)</span>
                </div>
              </div>

              <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3">
                <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-xs text-muted-foreground">
                  Each URL is scraped independently with the selected formats. Results include markdown, HTML, metadata,
                  and more depending on selected formats.
                </p>
              </div>

              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              <Button
                onClick={handleStart}
                disabled={loading || urlCount === 0}
                className="gap-2"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Start Batch ({urlCount} URL{urlCount !== 1 ? "s" : ""})
              </Button>
            </CardContent>
          </Card>

          {/* Recent Batch Jobs */}
          {recentJobs.length > 0 && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-lg">Recent Batches</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {recentJobs.map((job) => (
                    <Link
                      key={job.id}
                      href={`/batch/${job.id}`}
                      className="flex items-center justify-between rounded-lg border border-border/50 p-3 hover:border-border transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-muted-foreground">{job.id.slice(0, 8)}</span>
                        <span className="text-sm">{job.completed}/{job.total} URLs</span>
                        {job.created_at && (
                          <span className="text-xs text-muted-foreground">
                            {new Date(job.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={job.status === "completed" ? "success" : job.status === "failed" ? "destructive" : "warning"}>
                          {job.status}
                        </Badge>
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* How It Works */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">How It Works</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">1</div>
                  <p className="text-sm font-medium">Add URLs</p>
                  <p className="text-xs text-muted-foreground mt-1">Paste up to 100 URLs, one per line</p>
                </div>
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">2</div>
                  <p className="text-sm font-medium">Configure</p>
                  <p className="text-xs text-muted-foreground mt-1">Choose formats and concurrency level</p>
                </div>
                <div className="text-center p-4">
                  <div className="text-2xl font-bold text-primary mb-1">3</div>
                  <p className="text-sm font-medium">Get Results</p>
                  <p className="text-xs text-muted-foreground mt-1">View or export all results as JSON</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
