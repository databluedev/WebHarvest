"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Globe, Search, Map, Zap, ArrowRight, Key, Clock, FileText, Activity } from "lucide-react";
import Link from "next/link";

function getJobDetailPath(job: any): string {
  switch (job.type) {
    case "scrape": return `/scrape/${job.id}`;
    case "crawl": return `/crawl/${job.id}`;
    case "batch": return `/batch/${job.id}`;
    case "search": return `/search/${job.id}`;
    case "map": return `/map/${job.id}`;
    default: return `/crawl/${job.id}`;
  }
}

function getJobUrl(job: any): string {
  if (!job.config) return "";
  if (job.config.url) return job.config.url;
  if (job.config.query) return job.config.query;
  if (job.config.urls?.length === 1) return job.config.urls[0];
  if (job.config.urls?.length > 1) return `${job.config.urls.length} URLs`;
  return "";
}

function getStatusVariant(status: string): "success" | "destructive" | "warning" | "secondary" {
  switch (status) {
    case "completed": return "success";
    case "failed": return "destructive";
    case "running": return "warning";
    default: return "secondary";
  }
}

function getTypeIcon(type: string) {
  switch (type) {
    case "scrape": return Search;
    case "crawl": return Globe;
    case "map": return Map;
    case "search": return Search;
    default: return FileText;
  }
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [recentJobs, setRecentJobs] = useState<any[]>([]);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }
    api.getMe().then(setUser).catch(() => router.push("/auth/login"));
    api.getUsageHistory({ per_page: 6 }).then((res) => setRecentJobs(res.jobs)).catch(() => {});
  }, [router]);

  if (!user) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          {/* Welcome Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold">
              Welcome back{user.name ? `, ${user.name}` : ""}
            </h1>
            <p className="mt-1 text-muted-foreground">
              Your open-source web crawling platform
            </p>
          </div>

          {/* Quick Actions */}
          <div className="grid gap-6 md:grid-cols-3 mb-8">
            <Card className="group cursor-pointer transition-colors hover:border-primary/50">
              <Link href="/scrape">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Scrape</CardTitle>
                  <Search className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">Single Page</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Extract content from any URL with JS rendering
                  </p>
                </CardContent>
              </Link>
            </Card>

            <Card className="group cursor-pointer transition-colors hover:border-primary/50">
              <Link href="/crawl">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Crawl</CardTitle>
                  <Globe className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">Full Website</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Recursively crawl entire sites with BFS
                  </p>
                </CardContent>
              </Link>
            </Card>

            <Card className="group cursor-pointer transition-colors hover:border-primary/50">
              <Link href="/map">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Map</CardTitle>
                  <Map className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">URL Discovery</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Fast sitemap discovery without content scraping
                  </p>
                </CardContent>
              </Link>
            </Card>
          </div>

          {/* Recent Activity */}
          {recentJobs.length > 0 && (
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Activity className="h-5 w-5 text-primary" />
                  Recent Activity
                </h2>
                <Link href="/jobs">
                  <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground">
                    View All
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {recentJobs.map((job) => {
                  const Icon = getTypeIcon(job.type);
                  const jobUrl = getJobUrl(job);
                  return (
                    <Link key={job.id} href={getJobDetailPath(job)}>
                      <Card className="cursor-pointer transition-colors hover:border-primary/50 h-full">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="capitalize text-xs gap-1">
                                <Icon className="h-3 w-3" />
                                {job.type}
                              </Badge>
                              <Badge variant={getStatusVariant(job.status)} className="text-xs">
                                {job.status}
                              </Badge>
                            </div>
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {timeAgo(job.created_at)}
                            </span>
                          </div>
                          {jobUrl && (
                            <p className="text-sm truncate text-foreground" title={jobUrl}>
                              {jobUrl}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                            {job.total_pages > 0 && (
                              <span>{job.completed_pages}/{job.total_pages} pages</span>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Features */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Zap className="h-5 w-5 text-primary" />
                  Key Advantages
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-start gap-3">
                  <Badge variant="success">BYOK</Badge>
                  <div>
                    <p className="text-sm font-medium">Bring Your Own Key</p>
                    <p className="text-xs text-muted-foreground">
                      Use your own OpenAI, Anthropic, or Groq keys for LLM extraction
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="success">Fast</Badge>
                  <div>
                    <p className="text-sm font-medium">Smart Pre-Processing</p>
                    <p className="text-xs text-muted-foreground">
                      Trafilatura strips 90% of HTML junk before LLM - 5x faster
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="success">Free</Badge>
                  <div>
                    <p className="text-sm font-medium">Open Source</p>
                    <p className="text-xs text-muted-foreground">
                      Self-hosted, no usage limits, no vendor lock-in
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Key className="h-5 w-5 text-primary" />
                  Getting Started
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">1. Generate an API key</p>
                    <p className="text-xs text-muted-foreground">For programmatic access</p>
                  </div>
                  <Link href="/api-keys">
                    <Button variant="ghost" size="sm">
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">2. Add your LLM key (optional)</p>
                    <p className="text-xs text-muted-foreground">For AI-powered extraction</p>
                  </div>
                  <Link href="/settings">
                    <Button variant="ghost" size="sm">
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">3. Start scraping</p>
                    <p className="text-xs text-muted-foreground">Try the scrape playground</p>
                  </div>
                  <Link href="/scrape">
                    <Button variant="ghost" size="sm">
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
