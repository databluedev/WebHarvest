"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import Link from "next/link";
import {
  Activity,
  FileText,
  Clock,
  CheckCircle,
  TrendingUp,
  RefreshCw,
  Loader2,
  Globe,
  AlertCircle,
  Search,
  Map,
  Layers,
  Zap,
  BarChart3,
  ArrowRight,
  ExternalLink,
  XCircle,
  Timer,
  Database,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts";

// ---- Types ----

interface UsageStats {
  total_jobs: number;
  total_pages_scraped: number;
  avg_pages_per_job: number;
  avg_duration_seconds: number;
  success_rate: number;
  jobs_per_day: Array<{ date: string; count: number }>;
  jobs_by_type: Record<string, number>;
  jobs_by_status: Record<string, number>;
}

interface TopDomain {
  domain: string;
  count: number;
}

interface Job {
  id: string;
  type: string;
  status: string;
  config: any;
  total_pages: number;
  completed_pages: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  duration_seconds: number | null;
}

interface QuotaData {
  success: boolean;
  period: string;
  total_pages_scraped: number;
  total_bytes_processed: number;
  operations: Record<string, { limit: number; used: number; remaining: number; unlimited: boolean }>;
}

// ---- Chart color palette ----

const PIE_COLORS = [
  "hsl(142, 76%, 36%)",
  "hsl(200, 80%, 50%)",
  "hsl(45, 93%, 58%)",
  "hsl(280, 65%, 55%)",
  "hsl(15, 80%, 55%)",
  "hsl(340, 75%, 55%)",
];

const GREEN_PRIMARY = "hsl(142, 76%, 36%)";
const GREEN_LIGHT = "hsl(142, 76%, 46%)";

// ---- Helpers ----

function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
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

function getJobUrl(job: Job): string {
  if (!job.config) return "";
  if (job.config.url) return job.config.url;
  if (job.config.query) return job.config.query;
  if (job.config.urls?.length === 1) return job.config.urls[0];
  if (job.config.urls?.length > 1) return `${job.config.urls.length} URLs`;
  return "";
}

function getJobDetailPath(job: Job): string {
  switch (job.type) {
    case "scrape": return `/scrape/${job.id}`;
    case "crawl": return `/crawl/${job.id}`;
    case "batch": return `/batch/${job.id}`;
    case "search": return `/search/${job.id}`;
    case "map": return `/map/${job.id}`;
    default: return `/crawl/${job.id}`;
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

function getStatusVariant(status: string): "success" | "destructive" | "warning" | "secondary" {
  switch (status) {
    case "completed": return "success";
    case "failed": return "destructive";
    case "running": return "warning";
    default: return "secondary";
  }
}

// ---- Custom Tooltip components ----

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-md">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

function PieTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0];
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-md">
      <p className="text-sm font-medium capitalize">{data.name}</p>
      <p className="text-xs text-muted-foreground">{data.value} jobs</p>
    </div>
  );
}

// ---- Dashboard Component ----

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [topDomains, setTopDomains] = useState<TopDomain[]>([]);
  const [totalUniqueDomains, setTotalUniqueDomains] = useState(0);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [statsRes, domainsRes, historyRes, activeRes, quotaRes] = await Promise.all([
        api.getUsageStats(),
        api.getTopDomains(),
        api.getUsageHistory({ per_page: 15, sort_by: "created_at", sort_dir: "desc" }),
        api.getUsageHistory({ per_page: 10, status: "running", sort_by: "created_at", sort_dir: "desc" }),
        api.getQuota().catch(() => null),
      ]);

      setStats(statsRes as UsageStats);

      const raw = domainsRes as any;
      setTopDomains(Array.isArray(raw) ? raw : (raw?.domains ?? []) as TopDomain[]);
      setTotalUniqueDomains(raw?.total_unique_domains ?? 0);

      const historyRaw = historyRes as any;
      setRecentJobs(historyRaw?.jobs ?? []);

      const activeRaw = activeRes as any;
      setActiveJobs((activeRaw?.jobs ?? []).filter((j: Job) => j.status === "running" || j.status === "pending"));

      if (quotaRes) setQuota(quotaRes as QuotaData);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }
    loadData();
  }, [router, loadData]);

  // Auto-refresh active jobs every 10s
  useEffect(() => {
    if (activeJobs.length === 0) return;
    const interval = setInterval(async () => {
      try {
        const activeRes = await api.getUsageHistory({ per_page: 10, status: "running", sort_by: "created_at", sort_dir: "desc" });
        const raw = activeRes as any;
        setActiveJobs((raw?.jobs ?? []).filter((j: Job) => j.status === "running" || j.status === "pending"));
      } catch {}
    }, 10000);
    return () => clearInterval(interval);
  }, [activeJobs.length]);

  // Build chart-ready data
  const jobsPerDay = (stats?.jobs_per_day ?? []).map((d) => ({
    ...d,
    label: formatDate(d.date),
  }));

  const jobsByType = Object.entries(stats?.jobs_by_type ?? {}).map(([type, count]) => ({
    name: type,
    value: count,
  }));

  const domainsChart = topDomains.slice(0, 10);

  // Compute extra stats
  const failedJobs = stats?.jobs_by_status?.["failed"] ?? 0;
  const runningJobs = stats?.jobs_by_status?.["running"] ?? 0;
  const pendingJobs = stats?.jobs_by_status?.["pending"] ?? 0;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-[1400px] mx-auto">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Dashboard</h1>
              <p className="mt-1 text-muted-foreground">
                Real-time analytics, active jobs, and usage overview
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Refresh
            </button>
          </div>

          {/* Error state */}
          {error && (
            <div className="mb-6 flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
              <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-400">Failed to load dashboard data</p>
                <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Loading skeleton */}
          {loading && !stats && (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                {[...Array(6)].map((_, i) => (
                  <Card key={i}>
                    <CardContent className="pt-5 pb-4">
                      <div className="h-4 w-20 rounded bg-muted animate-pulse mb-2" />
                      <div className="h-7 w-16 rounded bg-muted animate-pulse mb-1" />
                      <div className="h-3 w-24 rounded bg-muted animate-pulse" />
                    </CardContent>
                  </Card>
                ))}
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                {[...Array(2)].map((_, i) => (
                  <Card key={i}>
                    <CardContent className="pt-6">
                      <div className="h-[300px] rounded bg-muted animate-pulse" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Stats content */}
          {stats && (
            <>
              {/* ── Stat Cards (6-column grid) ── */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 mb-8">
                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Total Jobs</span>
                      <Activity className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">{stats.total_jobs.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">All time</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Pages Scraped</span>
                      <FileText className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">{stats.total_pages_scraped.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      ~{stats.avg_pages_per_job.toFixed(1)} per job
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Avg Duration</span>
                      <Clock className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">{formatDuration(stats.avg_duration_seconds)}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Per job completion</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Success Rate</span>
                      <CheckCircle className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">{stats.success_rate.toFixed(1)}%</p>
                    <div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(stats.success_rate, 100)}%`,
                          backgroundColor: stats.success_rate >= 90 ? GREEN_PRIMARY : stats.success_rate >= 70 ? "hsl(45, 93%, 58%)" : "hsl(0, 84%, 60%)",
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Unique Domains</span>
                      <Globe className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">{totalUniqueDomains.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Distinct domains scraped</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-5 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground">Active Now</span>
                      <Zap className="h-4 w-4 text-yellow-500" />
                    </div>
                    <p className="text-2xl font-bold tabular-nums">
                      {runningJobs + pendingJobs}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {runningJobs} running, {pendingJobs} pending
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* ── Active Jobs (only shown when there are running/pending jobs) ── */}
              {activeJobs.length > 0 && (
                <Card className="mb-8 border-yellow-500/30">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Loader2 className="h-5 w-5 text-yellow-500 animate-spin" />
                      Active Jobs
                      <Badge variant="warning" className="ml-1 text-xs">{activeJobs.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {activeJobs.map((job) => {
                        const Icon = getTypeIcon(job.type);
                        const progress = job.total_pages > 0 ? (job.completed_pages / job.total_pages) * 100 : 0;
                        return (
                          <Link key={job.id} href={getJobDetailPath(job)}>
                            <div className="flex items-center gap-4 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors cursor-pointer">
                              <div className="shrink-0">
                                <Icon className="h-5 w-5 text-yellow-500" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-sm font-medium capitalize">{job.type}</span>
                                  <Badge variant="warning" className="text-[10px]">{job.status}</Badge>
                                </div>
                                <p className="text-xs text-muted-foreground truncate">
                                  {getJobUrl(job) || job.id.slice(0, 8)}
                                </p>
                              </div>
                              <div className="shrink-0 w-32">
                                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                  <span>{job.completed_pages}/{job.total_pages} pages</span>
                                  <span>{progress.toFixed(0)}%</span>
                                </div>
                                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-yellow-500 transition-all duration-300"
                                    style={{ width: `${Math.min(progress, 100)}%` }}
                                  />
                                </div>
                              </div>
                              <div className="shrink-0 text-xs text-muted-foreground">
                                {job.started_at ? timeAgo(job.started_at) : "Queued"}
                              </div>
                              <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ── Quota & Usage (if available) ── */}
              {quota && Object.keys(quota.operations).length > 0 && (
                <Card className="mb-8">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Database className="h-5 w-5 text-primary" />
                      Usage Quota
                      <span className="text-xs font-normal text-muted-foreground ml-1">
                        ({quota.period})
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(quota.operations).map(([op, data]) => {
                        const pct = data.unlimited ? 0 : data.limit > 0 ? (data.used / data.limit) * 100 : 0;
                        return (
                          <div key={op} className="rounded-lg border p-4">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium capitalize">{op.replace(/_/g, " ")}</span>
                              {data.unlimited ? (
                                <Badge variant="secondary" className="text-[10px]">Unlimited</Badge>
                              ) : (
                                <span className="text-xs text-muted-foreground">
                                  {data.used.toLocaleString()} / {data.limit.toLocaleString()}
                                </span>
                              )}
                            </div>
                            {!data.unlimited && (
                              <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-500"
                                  style={{
                                    width: `${Math.min(pct, 100)}%`,
                                    backgroundColor: pct > 90 ? "hsl(0, 84%, 60%)" : pct > 70 ? "hsl(45, 93%, 58%)" : GREEN_PRIMARY,
                                  }}
                                />
                              </div>
                            )}
                            {!data.unlimited && (
                              <p className="text-xs text-muted-foreground mt-1.5">
                                {data.remaining.toLocaleString()} remaining
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {quota.total_bytes_processed > 0 && (
                      <p className="text-xs text-muted-foreground mt-3">
                        Total data processed: {formatBytes(quota.total_bytes_processed)}
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* ── Charts Row 1: Area chart + Pie chart ── */}
              <div className="grid gap-6 lg:grid-cols-3 mb-8">
                <Card className="lg:col-span-2">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <TrendingUp className="h-5 w-5 text-primary" />
                      Jobs Per Day
                      <span className="text-xs font-normal text-muted-foreground ml-1">(last 30 days)</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {jobsPerDay.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-[280px] text-muted-foreground">
                        <Activity className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No job data for the last 30 days</p>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={jobsPerDay}>
                          <defs>
                            <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={GREEN_PRIMARY} stopOpacity={0.3} />
                              <stop offset="95%" stopColor={GREEN_PRIMARY} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 14.9%)" />
                          <XAxis
                            dataKey="label"
                            tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 11 }}
                            tickLine={false}
                            axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                          />
                          <YAxis
                            tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 11 }}
                            tickLine={false}
                            axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                            allowDecimals={false}
                          />
                          <Tooltip content={<ChartTooltip />} />
                          <Area
                            type="monotone"
                            dataKey="count"
                            name="Jobs"
                            stroke={GREEN_PRIMARY}
                            strokeWidth={2}
                            fill="url(#greenGradient)"
                            dot={{ fill: GREEN_PRIMARY, r: 2 }}
                            activeDot={{ r: 5, fill: GREEN_LIGHT }}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Jobs by Type</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {jobsByType.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-[280px] text-muted-foreground">
                        <Activity className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No job type data available</p>
                      </div>
                    ) : (
                      <>
                        <ResponsiveContainer width="100%" height={200}>
                          <PieChart>
                            <Pie
                              data={jobsByType}
                              cx="50%"
                              cy="50%"
                              innerRadius={50}
                              outerRadius={80}
                              paddingAngle={4}
                              dataKey="value"
                            >
                              {jobsByType.map((_, index) => (
                                <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip content={<PieTooltip />} />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="space-y-1.5 mt-2">
                          {jobsByType.map((item, i) => (
                            <div key={item.name} className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-2">
                                <div
                                  className="h-2.5 w-2.5 rounded-full"
                                  style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                                />
                                <span className="capitalize text-muted-foreground">{item.name}</span>
                              </div>
                              <span className="font-medium tabular-nums">{item.value}</span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* ── Charts Row 2: Status breakdown + Top domains ── */}
              <div className="grid gap-6 lg:grid-cols-2 mb-8">
                {/* Status breakdown */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <BarChart3 className="h-5 w-5 text-primary" />
                      Status Breakdown
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {Object.keys(stats.jobs_by_status ?? {}).length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Activity className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No job data available</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {Object.entries(stats.jobs_by_status).map(([status, count]) => {
                          const pct = stats.total_jobs > 0 ? (count / stats.total_jobs) * 100 : 0;
                          const color = status === "completed" ? GREEN_PRIMARY
                            : status === "failed" ? "hsl(0, 84%, 60%)"
                            : status === "running" ? "hsl(45, 93%, 58%)"
                            : "hsl(0 0% 45%)";
                          return (
                            <div key={status}>
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                  <Badge variant={getStatusVariant(status)} className="text-[10px]">{status}</Badge>
                                </div>
                                <span className="text-sm font-medium tabular-nums">
                                  {count} <span className="text-xs text-muted-foreground">({pct.toFixed(1)}%)</span>
                                </span>
                              </div>
                              <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-500"
                                  style={{ width: `${pct}%`, backgroundColor: color }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Top domains */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Globe className="h-5 w-5 text-primary" />
                      Top 10 Domains
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {domainsChart.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Globe className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No domain data available yet</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {domainsChart.map((d, i) => {
                          const maxCount = domainsChart[0]?.count ?? 1;
                          const pct = (d.count / maxCount) * 100;
                          return (
                            <div key={d.domain} className="group">
                              <div className="flex items-center justify-between mb-0.5">
                                <span className="text-sm text-muted-foreground truncate max-w-[200px]">
                                  {d.domain}
                                </span>
                                <span className="text-sm font-medium tabular-nums ml-2">{d.count}</span>
                              </div>
                              <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-500"
                                  style={{
                                    width: `${pct}%`,
                                    backgroundColor: PIE_COLORS[i % PIE_COLORS.length],
                                  }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* ── Recent Jobs Table ── */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Timer className="h-5 w-5 text-primary" />
                      Recent Jobs
                    </span>
                    <Link
                      href="/jobs"
                      className="text-sm font-normal text-primary hover:underline flex items-center gap-1"
                    >
                      View all <ArrowRight className="h-3 w-3" />
                    </Link>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {recentJobs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Activity className="h-10 w-10 mb-3 opacity-40" />
                      <p className="text-sm">No recent jobs</p>
                      <p className="text-xs mt-1">Start a scrape, crawl, or search to see jobs here</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left">
                            <th className="pb-2 font-medium text-muted-foreground text-xs">Type</th>
                            <th className="pb-2 font-medium text-muted-foreground text-xs">URL / Query</th>
                            <th className="pb-2 font-medium text-muted-foreground text-xs">Status</th>
                            <th className="pb-2 font-medium text-muted-foreground text-xs text-right">Pages</th>
                            <th className="pb-2 font-medium text-muted-foreground text-xs text-right">Duration</th>
                            <th className="pb-2 font-medium text-muted-foreground text-xs text-right">When</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recentJobs.map((job) => {
                            const Icon = getTypeIcon(job.type);
                            const jobUrl = getJobUrl(job);
                            return (
                              <tr
                                key={job.id}
                                className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
                                onClick={() => router.push(getJobDetailPath(job))}
                              >
                                <td className="py-2.5 pr-3">
                                  <div className="flex items-center gap-1.5">
                                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                                    <span className="capitalize">{job.type}</span>
                                  </div>
                                </td>
                                <td className="py-2.5 pr-3 max-w-[300px]">
                                  <span className="text-muted-foreground truncate block">
                                    {jobUrl || job.id.slice(0, 12)}
                                  </span>
                                </td>
                                <td className="py-2.5 pr-3">
                                  <Badge variant={getStatusVariant(job.status)} className="text-[10px]">
                                    {job.status}
                                  </Badge>
                                </td>
                                <td className="py-2.5 pr-3 text-right tabular-nums text-muted-foreground">
                                  {job.completed_pages}/{job.total_pages}
                                </td>
                                <td className="py-2.5 pr-3 text-right tabular-nums text-muted-foreground">
                                  {job.duration_seconds != null ? formatDuration(job.duration_seconds) : "—"}
                                </td>
                                <td className="py-2.5 text-right text-muted-foreground whitespace-nowrap">
                                  {job.created_at ? timeAgo(job.created_at) : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
