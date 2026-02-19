"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  Globe,
  Search,
  Map,
  ArrowRight,
  Key,
  Clock,
  FileText,
  Activity,
  Terminal,
  Zap,
  Shield,
  Cpu,
  Layers,
} from "lucide-react";
import Link from "next/link";

const ASCII_LOGO = `
 ██╗    ██╗███████╗██████╗ ██╗  ██╗ █████╗ ██████╗ ██╗   ██╗███████╗███████╗████████╗
 ██║    ██║██╔════╝██╔══██╗██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝
 ██║ █╗ ██║█████╗  ██████╔╝███████║███████║██████╔╝██║   ██║█████╗  ███████╗   ██║
 ██║███╗██║██╔══╝  ██╔══██╗██╔══██║██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝  ╚════██║   ██║
 ╚███╔███╔╝███████╗██████╔╝██║  ██║██║  ██║██║  ██║ ╚████╔╝ ███████╗███████║   ██║
  ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝   ╚═╝
`.trimStart();

/** Animated ASCII typing effect */
function AsciiTyper({ text, className }: { text: string; className?: string }) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const idx = useRef(0);

  useEffect(() => {
    if (idx.current >= text.length) { setDone(true); return; }
    const speed = text[idx.current] === '\n' ? 5 : 1;
    const timer = setTimeout(() => {
      // Reveal line-by-line for speed — find next newline
      const nextNl = text.indexOf('\n', idx.current);
      const end = nextNl === -1 ? text.length : nextNl + 1;
      idx.current = end;
      setDisplayed(text.slice(0, end));
      if (end >= text.length) setDone(true);
    }, speed);
    return () => clearTimeout(timer);
  }, [displayed, text]);

  return (
    <pre className={className}>
      {displayed}
      {!done && <span className="animate-blink text-primary">_</span>}
    </pre>
  );
}

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
    case "batch": return Layers;
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
      <main className="flex-1 overflow-auto grid-bg mesh-gradient">
        <div className="p-8 max-w-6xl mx-auto">
          {/* ASCII Art Hero */}
          <div className="mb-10 animate-fade-in">
            <div className="overflow-x-auto pb-2">
              <AsciiTyper text={ASCII_LOGO} className="ascii-art text-primary/70 glow-green-sm select-none" />
            </div>
            <div className="flex items-center gap-3 mt-4">
              <div className="h-px flex-1 bg-gradient-to-r from-primary/30 to-transparent" />
              <span className="text-xs font-mono text-muted-foreground">
                {user.name ? `Welcome back, ${user.name}` : "Welcome back"}
              </span>
              <span className="text-primary animate-blink font-mono">_</span>
              <div className="h-px flex-1 bg-gradient-to-l from-primary/30 to-transparent" />
            </div>
          </div>

          {/* Terminal Status Bar */}
          <div className="mb-8 animate-fade-in" style={{ animationDelay: "0.1s" }}>
            <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border/50 bg-card/50 backdrop-blur-sm font-mono text-xs">
              <span className="text-primary">$</span>
              <span className="text-muted-foreground">status</span>
              <span className="text-foreground/70">--</span>
              <span className="text-emerald-400">online</span>
              <span className="mx-2 text-border">|</span>
              <span className="text-muted-foreground">engine</span>
              <span className="text-foreground/70">--</span>
              <span className="text-cyan-400">5-tier parallel</span>
              <span className="mx-2 text-border">|</span>
              <span className="text-muted-foreground">mode</span>
              <span className="text-foreground/70">--</span>
              <span className="text-amber-400">stealth</span>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="grid gap-4 md:grid-cols-3 mb-8">
            {[
              {
                href: "/scrape",
                icon: Search,
                title: "Scrape",
                subtitle: "Single Page",
                desc: "Extract content from any URL with JS rendering",
                color: "text-emerald-400",
                glow: "group-hover:shadow-[0_0_30px_-5px_hsla(142,100%,50%,0.15)]",
              },
              {
                href: "/crawl",
                icon: Globe,
                title: "Crawl",
                subtitle: "Full Website",
                desc: "Recursively crawl entire sites with BFS",
                color: "text-cyan-400",
                glow: "group-hover:shadow-[0_0_30px_-5px_hsla(187,100%,50%,0.15)]",
              },
              {
                href: "/map",
                icon: Map,
                title: "Map",
                subtitle: "URL Discovery",
                desc: "Fast sitemap discovery without content scraping",
                color: "text-violet-400",
                glow: "group-hover:shadow-[0_0_30px_-5px_hsla(263,100%,60%,0.15)]",
              },
            ].map((item, i) => (
              <Link key={item.href} href={item.href}>
                <Card
                  className={`group cursor-pointer transition-all duration-300 border-border/50 bg-card/50 backdrop-blur-sm ${item.glow} animate-fade-in`}
                  style={{ animationDelay: `${0.15 + i * 0.05}s` }}
                >
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full bg-current ${item.color} animate-pulse-glow`} />
                      <CardTitle className="text-sm font-mono font-medium">{item.title}</CardTitle>
                    </div>
                    <item.icon className={`h-5 w-5 ${item.color} opacity-60 group-hover:opacity-100 transition-opacity`} />
                  </CardHeader>
                  <CardContent>
                    <p className="text-xl font-bold font-mono">{item.subtitle}</p>
                    <p className="text-xs text-muted-foreground mt-1 font-mono">
                      {item.desc}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>

          {/* Recent Activity */}
          {recentJobs.length > 0 && (
            <div className="mb-8 animate-fade-in" style={{ animationDelay: "0.3s" }}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-mono font-semibold flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <span className="text-muted-foreground">~/</span>recent-activity
                </h2>
                <Link href="/jobs">
                  <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground font-mono text-xs">
                    view all
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </div>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                {recentJobs.map((job) => {
                  const Icon = getTypeIcon(job.type);
                  const jobUrl = getJobUrl(job);
                  return (
                    <Link key={job.id} href={getJobDetailPath(job)}>
                      <Card className="cursor-pointer h-full border-border/50 bg-card/50 backdrop-blur-sm">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-1.5">
                              <Badge variant="outline" className="capitalize text-[10px] gap-1 font-mono">
                                <Icon className="h-3 w-3" />
                                {job.type}
                              </Badge>
                              <Badge variant={getStatusVariant(job.status)} className="text-[10px] font-mono">
                                {job.status}
                              </Badge>
                            </div>
                            <span className="text-[10px] text-muted-foreground flex items-center gap-1 font-mono">
                              <Clock className="h-2.5 w-2.5" />
                              {timeAgo(job.created_at)}
                            </span>
                          </div>
                          {jobUrl && (
                            <p className="text-xs font-mono truncate text-foreground/80" title={jobUrl}>
                              {jobUrl}
                            </p>
                          )}
                          {job.total_pages > 0 && (
                            <div className="flex items-center gap-2 mt-1.5">
                              <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary/60 rounded-full transition-all duration-500"
                                  style={{ width: `${Math.min(100, (job.completed_pages / job.total_pages) * 100)}%` }}
                                />
                              </div>
                              <span className="text-[10px] font-mono text-muted-foreground">
                                {job.completed_pages}/{job.total_pages}
                              </span>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Features Grid */}
          <div className="grid gap-4 md:grid-cols-2 animate-fade-in" style={{ animationDelay: "0.4s" }}>
            <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm font-mono">
                  <Zap className="h-4 w-4 text-primary" />
                  <span className="text-muted-foreground">~/</span>capabilities
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { badge: "BYOK", icon: Key, title: "Bring Your Own Key", desc: "Use your own OpenAI, Anthropic, or Groq keys" },
                  { badge: "FAST", icon: Cpu, title: "5-Tier Parallel Engine", desc: "HTTP race + browser stealth + fallback archive" },
                  { badge: "OSS", icon: Shield, title: "Open Source", desc: "Self-hosted, no usage limits, no vendor lock-in" },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-3 p-2 rounded-lg hover:bg-accent/50 transition-colors">
                    <Badge variant="success" className="mt-0.5 font-mono text-[10px]">{item.badge}</Badge>
                    <div>
                      <p className="text-xs font-mono font-medium">{item.title}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm font-mono">
                  <Terminal className="h-4 w-4 text-primary" />
                  <span className="text-muted-foreground">~/</span>quickstart
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {[
                  { step: "01", label: "Generate an API key", desc: "For programmatic access", href: "/api-keys" },
                  { step: "02", label: "Add your LLM key", desc: "For AI-powered extraction", href: "/settings" },
                  { step: "03", label: "Start scraping", desc: "Try the scrape playground", href: "/scrape" },
                ].map((item) => (
                  <Link key={item.step} href={item.href}>
                    <div className="flex items-center justify-between p-2.5 rounded-lg hover:bg-accent/50 transition-colors group">
                      <div className="flex items-center gap-3">
                        <span className="text-primary font-mono text-xs font-bold">{item.step}</span>
                        <div>
                          <p className="text-xs font-mono font-medium">{item.label}</p>
                          <p className="text-[11px] text-muted-foreground">{item.desc}</p>
                        </div>
                      </div>
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                  </Link>
                ))}

                <div className="mt-3 p-3 rounded-lg border border-border/50 bg-background/50">
                  <p className="text-[11px] font-mono text-muted-foreground">
                    <span className="text-primary">$</span> curl -X POST /api/v1/scrape \
                  </p>
                  <p className="text-[11px] font-mono text-muted-foreground pl-4">
                    -H &quot;Authorization: Bearer wh_...&quot; \
                  </p>
                  <p className="text-[11px] font-mono text-muted-foreground pl-4">
                    -d &apos;{`{"url": "https://example.com"}`}&apos;
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
