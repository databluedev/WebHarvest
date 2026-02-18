"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Activity, FileText, Clock, CheckCircle, TrendingUp, RefreshCw, Loader2, Globe, AlertCircle } from "lucide-react";
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

// ---- Chart color palette ----

const PIE_COLORS = [
  "hsl(142, 76%, 36%)",  // green primary
  "hsl(200, 80%, 50%)",  // blue
  "hsl(45, 93%, 58%)",   // amber
  "hsl(280, 65%, 55%)",  // purple
  "hsl(15, 80%, 55%)",   // orange
  "hsl(340, 75%, 55%)",  // pink
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

function statusVariant(status: string) {
  switch (status) {
    case "completed":
      return "success" as const;
    case "failed":
    case "error":
      return "destructive" as const;
    case "running":
    case "in_progress":
    case "scraping":
      return "warning" as const;
    default:
      return "secondary" as const;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [statsRes, domainsRes] = await Promise.all([
        api.getUsageStats(),
        api.getTopDomains(),
      ]);
      setStats(statsRes as UsageStats);
      setTopDomains((domainsRes as any)?.domains ?? domainsRes as TopDomain[]);
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

  // ---- Render ----

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Dashboard</h1>
              <p className="mt-1 text-muted-foreground">
                Usage analytics and job overview
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
                <p className="text-sm font-medium text-red-400">
                  Failed to load dashboard data
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Loading skeleton */}
          {loading && !stats && (
            <div className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                  <Card key={i}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                      <div className="h-5 w-5 rounded bg-muted animate-pulse" />
                    </CardHeader>
                    <CardContent>
                      <div className="h-8 w-20 rounded bg-muted animate-pulse mb-1" />
                      <div className="h-3 w-32 rounded bg-muted animate-pulse" />
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
              {/* Stat cards */}
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      Total Jobs
                    </CardTitle>
                    <Activity className="h-5 w-5 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold">
                      {stats.total_jobs.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      All-time scrape, crawl, and map jobs
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      Pages Scraped
                    </CardTitle>
                    <FileText className="h-5 w-5 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold">
                      {stats.total_pages_scraped.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Total pages processed across all jobs
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      Avg Duration
                    </CardTitle>
                    <Clock className="h-5 w-5 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold">
                      {formatDuration(stats.avg_duration_seconds)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Average job completion time
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      Success Rate
                    </CardTitle>
                    <CheckCircle className="h-5 w-5 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold">
                      {stats.success_rate.toFixed(1)}%
                    </p>
                    <div className="mt-2 h-2 w-full rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(stats.success_rate, 100)}%`,
                          backgroundColor: GREEN_PRIMARY,
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Charts row 1: Line chart + Pie chart */}
              <div className="grid gap-6 lg:grid-cols-3 mb-8">
                {/* Jobs per day - line chart */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <TrendingUp className="h-5 w-5 text-primary" />
                      Jobs Per Day
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {jobsPerDay.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground">
                        <Activity className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No job data for the last 30 days</p>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={jobsPerDay}>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="hsl(0 0% 14.9%)"
                          />
                          <XAxis
                            dataKey="label"
                            tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 12 }}
                            tickLine={false}
                            axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                          />
                          <YAxis
                            tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 12 }}
                            tickLine={false}
                            axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                            allowDecimals={false}
                          />
                          <Tooltip content={<ChartTooltip />} />
                          <Line
                            type="monotone"
                            dataKey="count"
                            name="Jobs"
                            stroke={GREEN_PRIMARY}
                            strokeWidth={2}
                            dot={{ fill: GREEN_PRIMARY, r: 3 }}
                            activeDot={{ r: 5, fill: GREEN_LIGHT }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Jobs by type - pie chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Jobs by Type</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {jobsByType.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground">
                        <Activity className="h-10 w-10 mb-3 opacity-40" />
                        <p className="text-sm">No job type data available</p>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={jobsByType}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={90}
                            paddingAngle={4}
                            dataKey="value"
                          >
                            {jobsByType.map((_, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={PIE_COLORS[index % PIE_COLORS.length]}
                              />
                            ))}
                          </Pie>
                          <Tooltip content={<PieTooltip />} />
                          <Legend
                            formatter={(value: string) => (
                              <span className="text-xs text-muted-foreground capitalize">
                                {value}
                              </span>
                            )}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Charts row 2: Bar chart (top domains) */}
              <Card className="mb-8">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Globe className="h-5 w-5 text-primary" />
                    Top 10 Domains
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {domainsChart.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[300px] text-muted-foreground">
                      <Globe className="h-10 w-10 mb-3 opacity-40" />
                      <p className="text-sm">No domain data available yet</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart
                        data={domainsChart}
                        layout="vertical"
                        margin={{ left: 20, right: 20, top: 5, bottom: 5 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="hsl(0 0% 14.9%)"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 12 }}
                          tickLine={false}
                          axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                          allowDecimals={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="domain"
                          width={180}
                          tick={{ fill: "hsl(0 0% 63.9%)", fontSize: 12 }}
                          tickLine={false}
                          axisLine={{ stroke: "hsl(0 0% 14.9%)" }}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar
                          dataKey="count"
                          name="Jobs"
                          fill={GREEN_PRIMARY}
                          radius={[0, 4, 4, 0]}
                          maxBarSize={28}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>

              {/* Status breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center justify-between">
                    <span>Job Status Breakdown</span>
                    <a
                      href="/jobs"
                      className="text-sm font-normal text-primary hover:underline"
                    >
                      View all jobs
                    </a>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {Object.keys(stats.jobs_by_status ?? {}).length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Activity className="h-10 w-10 mb-3 opacity-40" />
                      <p className="text-sm">No job data available</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.entries(stats.jobs_by_status).map(([status, count]) => (
                        <div key={status} className="rounded-lg border p-4 text-center">
                          <Badge variant={statusVariant(status)} className="text-xs mb-2">
                            {status}
                          </Badge>
                          <p className="text-2xl font-bold tabular-nums">{count}</p>
                        </div>
                      ))}
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
