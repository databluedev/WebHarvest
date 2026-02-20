"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  Globe,
  Search,
  Map,
  ArrowRight,
  Clock,
  FileText,
  Activity,
  Shield,
  Cpu,
  Layers,
  Zap,
  Lock,
  Play,
} from "lucide-react";
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

const features = [
  { icon: Cpu, label: "5-Tier engine" },
  { icon: Shield, label: "Stealth mode" },
  { icon: Lock, label: "Self-hosted" },
];

const metrics = [
  { label: "Engine", value: "5-Tier", desc: "Parallel extraction" },
  { label: "Strategies", value: "4+", desc: "Per page fallback" },
  { label: "License", value: "OSS", desc: "No vendor lock-in" },
];

const actions = [
  {
    href: "/scrape",
    icon: Search,
    title: "Scrape",
    subtitle: "Single Page",
    desc: "Extract content from any URL with JS rendering and stealth mode",
    color: "text-emerald-400",
    bg: "bg-emerald-500/8",
  },
  {
    href: "/crawl",
    icon: Globe,
    title: "Crawl",
    subtitle: "Full Website",
    desc: "Recursively crawl entire sites with BFS and persistent sessions",
    color: "text-blue-400",
    bg: "bg-blue-500/8",
  },
  {
    href: "/map",
    icon: Map,
    title: "Map",
    subtitle: "URL Discovery",
    desc: "Fast sitemap discovery and URL mapping without content extraction",
    color: "text-violet-400",
    bg: "bg-violet-500/8",
  },
];

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
    <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background">
          <MobileMenuButton />
          <div className="p-6 lg:p-8 md:p-14 max-w-5xl mx-auto">

            {/* Hero Section */}
            <section className="mb-16 animate-float-in">
              {/* Pill badge */}
              <div className="bg-muted/50 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 mb-6 border border-border/30">
                <div className="h-5 w-5 grid place-items-center rounded-full bg-emerald-500/10 text-emerald-400">
                  <Shield className="h-3 w-3" />
                </div>
                <span className="text-[11px] text-foreground/50 font-medium">Open source platform</span>
              </div>

              {/* Large heading */}
              <h1 className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight leading-[0.92]">
                {user.name ? "Welcome back," : "Web scraping"}
                <br />
                <span className="text-foreground">
                  {user.name ? `${user.name}.` : "made simple."}
                </span>
              </h1>

              {/* Description */}
              <p className="text-sm sm:text-base text-muted-foreground max-w-lg mt-6 leading-relaxed font-light">
                A self-hosted web crawling platform with 5-tier parallel extraction,
                stealth browsing, and AI-powered content analysis.
              </p>

              {/* Feature chips */}
              <div className="mt-6 flex flex-wrap gap-2">
                {features.map((f) => (
                  <div
                    key={f.label}
                    className="bg-muted/50 inline-flex items-center gap-2 rounded-full px-3 py-1.5 border border-border/20 hover:border-border/40 transition-colors cursor-default"
                  >
                    <f.icon className="h-3.5 w-3.5 text-muted-foreground/60" />
                    <span className="text-[11px] text-foreground/50">{f.label}</span>
                  </div>
                ))}
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-3 mt-8">
                <Link href="/scrape">
                  <Button variant="default" size="lg" className="rounded-lg px-6 gap-2 hover:-translate-y-0.5 transition-all">
                    <Play className="h-4 w-4" />
                    Start scraping
                  </Button>
                </Link>
                <Link href="/api-keys">
                  <Button variant="outline" size="lg" className="rounded-lg px-6 gap-2 hover:-translate-y-0.5 transition-all">
                    <ArrowRight className="h-4 w-4" />
                    Get API key
                  </Button>
                </Link>
              </div>

              {/* Divider */}
              <div className="mt-10 h-px w-full bg-gradient-to-r from-transparent via-border/50 to-transparent" />

              {/* Mini metrics */}
              <div className="mt-6 grid grid-cols-3 gap-3 max-w-md">
                {metrics.map((m) => (
                  <div key={m.label} className="rounded-lg border border-border/50 bg-card p-4 hover:bg-muted/50 transition-colors">
                    <div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground/50">{m.label}</div>
                    <div className="mt-1 text-lg font-bold tracking-tight">{m.value}</div>
                  </div>
                ))}
              </div>
            </section>

            {/* Action Cards */}
            <section className="mb-12">
              <div className="grid gap-3 md:grid-cols-3 stagger-children">
                {actions.map((item) => (
                  <Link key={item.href} href={item.href}>
                    <div className="group rounded-lg border border-border/50 bg-card p-5 hover:bg-muted/50 transition-colors cursor-pointer h-full">
                      <div className="flex items-center justify-between mb-3">
                        <div className={`h-9 w-9 rounded-xl ${item.bg} grid place-items-center`}>
                          <item.icon className={`h-4 w-4 ${item.color}`} />
                        </div>
                        <ArrowRight className="h-4 w-4 text-foreground/15 group-hover:text-foreground/40 group-hover:translate-x-0.5 transition-all" />
                      </div>
                      <h3 className="font-semibold tracking-tight">{item.title}</h3>
                      <p className="text-xs text-muted-foreground/70 mt-0.5">{item.subtitle}</p>
                      <p className="text-[11px] text-muted-foreground/50 mt-2 leading-relaxed">{item.desc}</p>
                    </div>
                  </Link>
                ))}
              </div>
            </section>

            {/* Recent Activity */}
            {recentJobs.length > 0 && (
              <section className="mb-12 animate-float-in" style={{ animationDelay: "0.15s" }}>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-medium flex items-center gap-2 text-foreground/70">
                    <Activity className="h-4 w-4 text-muted-foreground/50" />
                    Recent activity
                  </h2>
                  <Link href="/jobs">
                    <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground/60 text-xs">
                      View all
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
                <div className="grid gap-2.5 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                  {recentJobs.map((job) => {
                    const Icon = getTypeIcon(job.type);
                    const jobUrl = getJobUrl(job);
                    return (
                      <Link key={job.id} href={getJobDetailPath(job)}>
                        <div className="rounded-lg border border-border/50 bg-card p-4 hover:bg-muted/50 transition-colors cursor-pointer h-full">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-1.5">
                              <Badge variant="outline" className="capitalize text-[10px] gap-1">
                                <Icon className="h-3 w-3" />
                                {job.type}
                              </Badge>
                              <Badge variant={getStatusVariant(job.status)} className="text-[10px]">
                                {job.status}
                              </Badge>
                            </div>
                            <span className="text-[10px] text-muted-foreground/50 flex items-center gap-1">
                              <Clock className="h-2.5 w-2.5" />
                              {timeAgo(job.created_at)}
                            </span>
                          </div>
                          {jobUrl && (
                            <p className="text-xs font-mono truncate text-foreground/60" title={jobUrl}>
                              {jobUrl}
                            </p>
                          )}
                          {job.total_pages > 0 && (
                            <div className="flex items-center gap-2 mt-2">
                              <div className="flex-1 h-1 bg-foreground/5 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary/40 rounded-full transition-all duration-500"
                                  style={{ width: `${Math.min(100, (job.completed_pages / job.total_pages) * 100)}%` }}
                                />
                              </div>
                              <span className="text-[10px] font-mono text-muted-foreground/50">
                                {job.completed_pages}/{job.total_pages}
                              </span>
                            </div>
                          )}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Bottom Grid: Capabilities + Quickstart */}
            <section className="animate-float-in" style={{ animationDelay: "0.25s" }}>
              <div className="grid gap-3 md:grid-cols-2">
                {/* Capabilities */}
                <div className="rounded-lg border border-border/50 bg-card p-6">
                  <h3 className="text-sm font-medium flex items-center gap-2 mb-4 text-foreground/80">
                    <Zap className="h-4 w-4 text-emerald-400" />
                    Capabilities
                  </h3>
                  <div className="space-y-2.5">
                    {[
                      { label: "Bring Your Own Key", desc: "Use your own OpenAI, Anthropic, or Groq keys", tag: "BYOK" },
                      { label: "5-Tier Parallel Engine", desc: "HTTP race, browser stealth, and archive fallback", tag: "FAST" },
                      { label: "Open Source", desc: "Self-hosted, no limits, no vendor lock-in", tag: "OSS" },
                    ].map((item) => (
                      <div key={item.tag} className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-foreground/[0.02] transition-colors">
                        <Badge variant="outline" className="text-[10px] mt-0.5 text-emerald-400 border-emerald-500/15">
                          {item.tag}
                        </Badge>
                        <div>
                          <p className="text-xs font-medium">{item.label}</p>
                          <p className="text-[11px] text-muted-foreground/50 mt-0.5">{item.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Quickstart */}
                <div className="rounded-lg border border-border/50 bg-card p-6">
                  <h3 className="text-sm font-medium flex items-center gap-2 mb-4 text-foreground/80">
                    <Play className="h-4 w-4 text-blue-400" />
                    Quickstart
                  </h3>
                  <div className="space-y-1">
                    {[
                      { step: "01", label: "Generate an API key", desc: "For programmatic access", href: "/api-keys" },
                      { step: "02", label: "Add your LLM key", desc: "For AI-powered extraction", href: "/settings" },
                      { step: "03", label: "Start scraping", desc: "Try the scrape playground", href: "/scrape" },
                    ].map((item) => (
                      <Link key={item.step} href={item.href}>
                        <div className="flex items-center justify-between p-2.5 rounded-xl hover:bg-foreground/[0.02] transition-colors group">
                          <div className="flex items-center gap-3">
                            <span className="text-primary/70 font-mono text-xs font-bold">{item.step}</span>
                            <div>
                              <p className="text-xs font-medium">{item.label}</p>
                              <p className="text-[11px] text-muted-foreground/40">{item.desc}</p>
                            </div>
                          </div>
                          <ArrowRight className="h-3.5 w-3.5 text-foreground/15 group-hover:text-foreground/40 transition-colors" />
                        </div>
                      </Link>
                    ))}
                  </div>

                  <div className="mt-4 p-3 rounded-xl bg-foreground/[0.02] border border-border/30">
                    <p className="text-[11px] font-mono text-foreground/40">
                      <span className="text-primary/60">$</span> curl -X POST /api/v1/scrape \
                    </p>
                    <p className="text-[11px] font-mono text-foreground/40 pl-4">
                      -H &quot;Authorization: Bearer wh_...&quot; \
                    </p>
                    <p className="text-[11px] font-mono text-foreground/40 pl-4">
                      -d &apos;{`{"url": "https://example.com"}`}&apos;
                    </p>
                  </div>
                </div>
              </div>
            </section>

          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
