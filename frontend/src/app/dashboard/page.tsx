"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
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
  Zap,
  BarChart3,
  ArrowRight,
  ExternalLink,
  XCircle,
  Timer,
  Database,
  Key,
  Plus,
  Copy,
  Check,
  Trash2,
  Eye,
  EyeOff,
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

interface ApiKeyItem {
  id: string;
  key_prefix: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

// ---- Chart color palette ----

const PIE_COLORS = [
  "hsl(160, 84%, 45%)",
  "hsl(200, 80%, 50%)",
  "hsl(45, 93%, 58%)",
  "hsl(280, 65%, 55%)",
  "hsl(15, 80%, 55%)",
  "hsl(340, 75%, 55%)",
];

const PRIMARY_CHART = "hsl(160, 84%, 45%)";
const PRIMARY_CHART_LIGHT = "hsl(160, 84%, 55%)";
const GRID_STROKE = "hsl(var(--border))";
const AXIS_TICK = "hsl(var(--muted-foreground))";

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

// ---- Status badge colors ----

function getStatusClasses(status: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/30 text-emerald-400";
    case "failed":
      return "border-red-400/30 text-red-400";
    case "running":
      return "border-amber-400/30 text-amber-400";
    default:
      return "border-border text-muted-foreground";
  }
}

// ---- Custom Tooltip components ----

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-border bg-card px-3 py-2 shadow-md">
      <p className="text-xs text-muted-foreground mb-1 font-mono">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-bold font-mono" style={{ color: entry.color }}>
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
    <div className="border border-border bg-card px-3 py-2 shadow-md">
      <p className="text-sm font-medium capitalize text-foreground font-mono">{data.name}</p>
      <p className="text-xs text-muted-foreground font-mono">{data.value} jobs</p>
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
  const [dataQueries, setDataQueries] = useState<Array<{
    id: string; platform: string; operation: string; query_summary: string;
    result_count: number; time_taken: number | null; status: string; created_at: string | null;
  }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  const [showKeyValue, setShowKeyValue] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [statsRes, domainsRes, historyRes, activeRes, quotaRes, dataQueriesRes] = await Promise.all([
        api.getUsageStats(),
        api.getTopDomains(),
        api.getUsageHistory({ per_page: 15, sort_by: "created_at", sort_dir: "desc" }),
        api.getUsageHistory({ per_page: 10, status: "running", sort_by: "created_at", sort_dir: "desc" }),
        api.getQuota().catch(() => null),
        api.getDataHistory({ limit: 10 }).catch(() => null),
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
      if (dataQueriesRes) setDataQueries((dataQueriesRes as any)?.queries ?? []);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadApiKeys = useCallback(async () => {
    setApiKeysLoading(true);
    try {
      const keys = await api.listApiKeys();
      setApiKeys(keys as ApiKeyItem[]);
    } catch {
    } finally {
      setApiKeysLoading(false);
    }
  }, []);

  const handleGenerateKey = async () => {
    setApiKeysLoading(true);
    try {
      const res = await api.createApiKey(newKeyName.trim() || undefined) as any;
      setGeneratedKey(res.full_key);
      setNewKeyName("");
      setShowKeyValue(true);
      await loadApiKeys();
    } catch {
    } finally {
      setApiKeysLoading(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    setRevokingKeyId(keyId);
    try {
      await api.revokeApiKey(keyId);
      await loadApiKeys();
    } catch {
    } finally {
      setRevokingKeyId(null);
    }
  };

  const handleCopyKey = (text: string) => {
    navigator.clipboard.writeText(text);
    setKeyCopied(true);
    setTimeout(() => setKeyCopied(false), 2000);
  };

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }
    loadData();
    loadApiKeys();
  }, [router, loadData, loadApiKeys]);

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
    <PageLayout activePage="dashboard">
      <div className="px-6 md:px-10 max-w-[1400px] mx-auto py-10">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-[36px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text">Dashboard</h1>
            <p className="mt-1 text-muted-foreground font-mono text-sm">
              Real-time analytics, active jobs, and usage overview
            </p>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 border border-border px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono hover:bg-foreground hover:text-background transition-all disabled:opacity-50"
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
          <div className="mb-6 flex items-center gap-3 border border-red-500/30 bg-red-500/10 p-4">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-400 font-mono">Failed to load dashboard data</p>
              <p className="text-xs text-muted-foreground mt-0.5 font-mono">{error}</p>
            </div>
          </div>
        )}

        {/* ── API Keys ── */}
        <div className="mb-8 border border-border bg-card/50 p-6 relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-500 to-emerald-500" />
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Key className="h-5 w-5 text-cyan-400" />
              <h2 className="text-lg font-bold text-foreground font-mono">API Keys</h2>
              <span className="text-xs font-mono text-muted-foreground ml-1">
                ({apiKeys.filter((k) => k.is_active).length} active)
              </span>
            </div>
          </div>

          {/* Generate new key */}
          <div className="flex items-center gap-3 mb-5">
            <input
              type="text"
              placeholder="Key name (optional)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGenerateKey()}
              className="flex-1 max-w-[300px] bg-transparent border border-border px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-cyan-500/40 transition-colors"
            />
            <button
              onClick={handleGenerateKey}
              disabled={apiKeysLoading}
              className="flex items-center gap-2 border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-cyan-400 hover:bg-cyan-500/20 transition-all disabled:opacity-50"
            >
              {apiKeysLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
              Generate Key
            </button>
          </div>

          {/* Newly generated key (shown once) */}
          {generatedKey && (
            <div className="mb-5 border border-emerald-500/30 bg-emerald-500/[0.06] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span className="text-sm font-bold text-emerald-400 font-mono">Key Generated</span>
                <span className="text-[10px] uppercase tracking-wider text-amber-400 font-mono ml-2">Save it now — it won&apos;t be shown again</span>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-muted/50 border border-border px-3 py-2 text-sm font-mono text-foreground break-all select-all">
                  {showKeyValue ? generatedKey : "•".repeat(40)}
                </code>
                <button
                  onClick={() => setShowKeyValue(!showKeyValue)}
                  className="h-9 w-9 grid place-items-center border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                  title={showKeyValue ? "Hide" : "Reveal"}
                >
                  {showKeyValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => handleCopyKey(generatedKey)}
                  className="h-9 w-9 grid place-items-center border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                  title="Copy"
                >
                  {keyCopied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}

          {/* Key list */}
          {apiKeys.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Name</th>
                    <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Key</th>
                    <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Status</th>
                    <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Created</th>
                    <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((k) => (
                    <tr key={k.id} className="border-b border-border">
                      <td className="py-2.5 pr-3">
                        <span className="text-foreground font-mono">{k.name || "—"}</span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <code className="text-cyan-400/70 font-mono text-xs">{k.key_prefix}••••••••</code>
                      </td>
                      <td className="py-2.5 pr-3">
                        {k.is_active ? (
                          <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-emerald-400/30 text-emerald-400">Active</span>
                        ) : (
                          <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-border text-muted-foreground">Revoked</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-muted-foreground font-mono text-xs">{timeAgo(k.created_at)}</span>
                      </td>
                      <td className="py-2.5 text-right">
                        {k.is_active && (
                          <button
                            onClick={() => handleRevokeKey(k.id)}
                            disabled={revokingKeyId === k.id}
                            className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-red-400/30 text-red-400 hover:bg-red-400/10 transition-colors disabled:opacity-50"
                          >
                            {revokingKeyId === k.id ? (
                              <Loader2 className="h-3 w-3 animate-spin inline" />
                            ) : (
                              "Revoke"
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <Key className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-mono">No API keys yet</p>
              <p className="text-xs font-mono mt-1">Generate a key to use the API programmatically</p>
            </div>
          )}
        </div>

        {/* Loading skeleton */}
        {loading && !stats && (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="border border-border bg-card/50 p-6">
                  <div className="h-4 w-20 bg-muted animate-pulse mb-2" />
                  <div className="h-7 w-16 bg-muted animate-pulse mb-1" />
                  <div className="h-3 w-24 bg-muted animate-pulse" />
                </div>
              ))}
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              {[...Array(2)].map((_, i) => (
                <div key={i} className="border border-border bg-card/50 p-6">
                  <div className="h-[300px] bg-muted animate-pulse" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stats content */}
        {stats && (
          <>
            {/* Stat Cards (6-column grid) */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 mb-8">
              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Total Jobs</span>
                  <div className="h-7 w-7 bg-emerald-400/10 grid place-items-center">
                    <Activity className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">{stats.total_jobs.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">All time</p>
              </div>

              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Pages Scraped</span>
                  <div className="h-7 w-7 bg-blue-500/10 grid place-items-center">
                    <FileText className="h-3.5 w-3.5 text-blue-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">{stats.total_pages_scraped.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                  ~{stats.avg_pages_per_job.toFixed(1)} per job
                </p>
              </div>

              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Avg Duration</span>
                  <div className="h-7 w-7 bg-violet-500/10 grid place-items-center">
                    <Clock className="h-3.5 w-3.5 text-violet-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">{formatDuration(stats.avg_duration_seconds)}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">Per job completion</p>
              </div>

              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Success Rate</span>
                  <div className="h-7 w-7 bg-emerald-500/10 grid place-items-center">
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">{stats.success_rate.toFixed(1)}%</p>
                <div className="mt-1.5 h-1.5 w-full bg-foreground/[0.06] overflow-hidden">
                  <div
                    className="h-full transition-all duration-500"
                    style={{
                      width: `${Math.min(stats.success_rate, 100)}%`,
                      backgroundColor: stats.success_rate >= 90 ? PRIMARY_CHART : stats.success_rate >= 70 ? "hsl(45, 93%, 58%)" : "hsl(0, 84%, 60%)",
                    }}
                  />
                </div>
              </div>

              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Unique Domains</span>
                  <div className="h-7 w-7 bg-cyan-500/10 grid place-items-center">
                    <Globe className="h-3.5 w-3.5 text-cyan-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">{totalUniqueDomains.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">Distinct domains scraped</p>
              </div>

              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Active Now</span>
                  <div className="h-7 w-7 bg-amber-500/10 grid place-items-center">
                    <Zap className="h-3.5 w-3.5 text-amber-400" />
                  </div>
                </div>
                <p className="text-2xl font-bold tracking-tight tabular-nums font-mono text-foreground">
                  {runningJobs + pendingJobs}
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                  {runningJobs} running, {pendingJobs} pending
                </p>
              </div>
            </div>

            {/* Active Jobs (only shown when there are running/pending jobs) */}
            {activeJobs.length > 0 && (
              <div className="mb-8 border border-border bg-card/50 p-6 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-400 to-pink-500" />
                <div className="flex items-center gap-2 mb-4">
                  <Loader2 className="h-5 w-5 text-amber-400 animate-spin" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Active Jobs</h2>
                  <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-amber-400/30 text-amber-400">{activeJobs.length}</span>
                </div>
                <div className="space-y-3">
                  {activeJobs.map((job) => {
                    const Icon = getTypeIcon(job.type);
                    const progress = job.total_pages > 0 ? (job.completed_pages / job.total_pages) * 100 : 0;
                    return (
                      <Link key={job.id} href={getJobDetailPath(job)}>
                        <div className="flex items-center gap-4 p-3 border border-border hover:bg-muted/50 transition-all duration-150 cursor-pointer">
                          <div className="shrink-0">
                            <Icon className="h-5 w-5 text-amber-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium capitalize text-foreground font-mono">{job.type}</span>
                              <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-amber-400/30 text-amber-400">{job.status}</span>
                            </div>
                            <p className="text-xs text-muted-foreground truncate font-mono">
                              {getJobUrl(job) || job.id.slice(0, 8)}
                            </p>
                          </div>
                          <div className="shrink-0 w-32">
                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1 font-mono">
                              <span>{job.completed_pages}/{job.total_pages} pages</span>
                              <span>{progress.toFixed(0)}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-foreground/[0.06] overflow-hidden">
                              <div
                                className="h-full bg-amber-400 transition-all duration-300"
                                style={{ width: `${Math.min(progress, 100)}%` }}
                              />
                            </div>
                          </div>
                          <div className="shrink-0 text-xs text-muted-foreground font-mono">
                            {job.started_at ? timeAgo(job.started_at) : "Queued"}
                          </div>
                          <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Quota & Usage (if available) */}
            {quota && Object.keys(quota.operations).length > 0 && (
              <div className="mb-8 border border-border bg-card/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Database className="h-5 w-5 text-cyan-400" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Usage Quota</h2>
                  <span className="text-xs font-mono text-muted-foreground ml-1">
                    ({quota.period})
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(quota.operations).map(([op, data]) => {
                    const pct = data.unlimited ? 0 : data.limit > 0 ? (data.used / data.limit) * 100 : 0;
                    return (
                      <div key={op} className="border border-border p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium capitalize text-foreground font-mono">{op.replace(/_/g, " ")}</span>
                          {data.unlimited ? (
                            <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-border text-muted-foreground">Unlimited</span>
                          ) : (
                            <span className="text-xs text-muted-foreground font-mono">
                              {data.used.toLocaleString()} / {data.limit.toLocaleString()}
                            </span>
                          )}
                        </div>
                        {!data.unlimited && (
                          <div className="h-2 w-full bg-foreground/[0.06] overflow-hidden">
                            <div
                              className="h-full transition-all duration-500"
                              style={{
                                width: `${Math.min(pct, 100)}%`,
                                backgroundColor: pct > 90 ? "hsl(0, 84%, 60%)" : pct > 70 ? "hsl(45, 93%, 58%)" : PRIMARY_CHART,
                              }}
                            />
                          </div>
                        )}
                        {!data.unlimited && (
                          <p className="text-xs text-muted-foreground mt-1.5 font-mono">
                            {data.remaining.toLocaleString()} remaining
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
                {quota.total_bytes_processed > 0 && (
                  <p className="text-xs text-muted-foreground mt-3 font-mono">
                    Total data processed: {formatBytes(quota.total_bytes_processed)}
                  </p>
                )}
              </div>
            )}

            {/* Charts Row 1: Area chart + Pie chart */}
            <div className="grid gap-6 lg:grid-cols-3 mb-8">
              <div className="lg:col-span-2 border border-border bg-card/50 p-6 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500 via-cyan-500 to-violet-500" />
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="h-5 w-5 text-cyan-400" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Jobs Per Day</h2>
                  <span className="text-xs font-mono text-muted-foreground ml-1">(last 30 days)</span>
                </div>
                {jobsPerDay.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[280px] text-muted-foreground">
                    <Activity className="h-10 w-10 mb-3 opacity-40" />
                    <p className="text-sm font-mono">No job data for the last 30 days</p>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={jobsPerDay}>
                      <defs>
                        <linearGradient id="greenGradient" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="50%" stopColor="#06b6d4" stopOpacity={0.2} />
                          <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.1} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
                      <XAxis
                        dataKey="label"
                        tick={{ fill: AXIS_TICK, fontSize: 11 }}
                        tickLine={false}
                        axisLine={{ stroke: GRID_STROKE }}
                      />
                      <YAxis
                        tick={{ fill: AXIS_TICK, fontSize: 11 }}
                        tickLine={false}
                        axisLine={{ stroke: GRID_STROKE }}
                        allowDecimals={false}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="count"
                        name="Jobs"
                        stroke={PRIMARY_CHART}
                        strokeWidth={2}
                        fill="url(#greenGradient)"
                        dot={{ fill: PRIMARY_CHART, r: 2 }}
                        activeDot={{ r: 5, fill: PRIMARY_CHART_LIGHT }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="border border-border bg-card/50 p-6">
                <h2 className="text-lg font-bold text-foreground font-mono mb-4">Jobs by Type</h2>
                {jobsByType.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[280px] text-muted-foreground">
                    <Activity className="h-10 w-10 mb-3 opacity-40" />
                    <p className="text-sm font-mono">No job type data available</p>
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
                            <span className="capitalize text-muted-foreground font-mono">{item.name}</span>
                          </div>
                          <span className="font-bold tabular-nums text-foreground font-mono">{item.value}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Charts Row 2: Status breakdown + Top domains */}
            <div className="grid gap-6 lg:grid-cols-2 mb-8">
              {/* Status breakdown */}
              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="h-5 w-5 text-amber-400" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Status Breakdown</h2>
                </div>
                {Object.keys(stats.jobs_by_status ?? {}).length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Activity className="h-10 w-10 mb-3 opacity-40" />
                    <p className="text-sm font-mono">No job data available</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(stats.jobs_by_status).map(([status, count]) => {
                      const pct = stats.total_jobs > 0 ? (count / stats.total_jobs) * 100 : 0;
                      const color = status === "completed" ? PRIMARY_CHART
                        : status === "failed" ? "hsl(0, 84%, 60%)"
                        : status === "running" ? "hsl(45, 93%, 58%)"
                        : "hsl(0 0% 45%)";
                      return (
                        <div key={status}>
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border ${getStatusClasses(status)}`}>{status}</span>
                            </div>
                            <span className="text-sm font-medium tabular-nums text-foreground font-mono">
                              {count} <span className="text-xs text-muted-foreground">({pct.toFixed(1)}%)</span>
                            </span>
                          </div>
                          <div className="h-2 w-full bg-foreground/[0.06] overflow-hidden">
                            <div
                              className="h-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: color }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Top domains */}
              <div className="border border-border bg-card/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Globe className="h-5 w-5 text-violet-400" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Top 10 Domains</h2>
                </div>
                {domainsChart.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Globe className="h-10 w-10 mb-3 opacity-40" />
                    <p className="text-sm font-mono">No domain data available yet</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {domainsChart.map((d, i) => {
                      const maxCount = domainsChart[0]?.count ?? 1;
                      const pct = (d.count / maxCount) * 100;
                      return (
                        <div key={d.domain} className="group">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-sm text-muted-foreground truncate max-w-[200px] font-mono">
                              {d.domain}
                            </span>
                            <span className="text-sm font-bold tabular-nums ml-2 text-foreground font-mono">{d.count}</span>
                          </div>
                          <div className="h-1.5 w-full bg-foreground/[0.06] overflow-hidden">
                            <div
                              className="h-full transition-all duration-500"
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
              </div>
            </div>

            {/* Recent Jobs Table */}
            <div className="border border-border bg-card/50 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Timer className="h-5 w-5 text-pink-400" />
                  <h2 className="text-lg font-bold text-foreground font-mono">Recent Jobs</h2>
                </div>
                <Link
                  href="/jobs"
                  className="text-sm font-mono text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              {recentJobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Activity className="h-10 w-10 mb-3 opacity-40" />
                  <p className="text-sm font-mono">No recent jobs</p>
                  <p className="text-xs mt-1 font-mono">Start a scrape, crawl, or search to see jobs here</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Type</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">URL / Query</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Status</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">Pages</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">Duration</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentJobs.map((job) => {
                        const Icon = getTypeIcon(job.type);
                        const jobUrl = getJobUrl(job);
                        return (
                          <tr
                            key={job.id}
                            className="border-b border-border hover:bg-muted/50 cursor-pointer transition-colors"
                            onClick={() => router.push(getJobDetailPath(job))}
                          >
                            <td className="py-2.5 pr-3">
                              <div className="flex items-center gap-1.5">
                                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                                <span className="capitalize text-foreground font-mono">{job.type}</span>
                              </div>
                            </td>
                            <td className="py-2.5 pr-3 max-w-[300px]">
                              <span className="text-muted-foreground truncate block font-mono">
                                {jobUrl || job.id.slice(0, 12)}
                              </span>
                            </td>
                            <td className="py-2.5 pr-3">
                              <span className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border ${getStatusClasses(job.status)}`}>
                                {job.status}
                              </span>
                            </td>
                            <td className="py-2.5 pr-3 text-right tabular-nums text-foreground font-mono">
                              {job.completed_pages}/{job.total_pages}
                            </td>
                            <td className="py-2.5 pr-3 text-right tabular-nums text-foreground font-mono">
                              {job.duration_seconds != null ? formatDuration(job.duration_seconds) : "\u2014"}
                            </td>
                            <td className="py-2.5 text-right text-muted-foreground whitespace-nowrap font-mono">
                              {job.created_at ? timeAgo(job.created_at) : "\u2014"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Recent Data Queries */}
            {dataQueries.length > 0 && (
              <div className="border border-border bg-card/50 p-6 mt-8">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-violet-400" />
                    <h2 className="text-lg font-bold text-foreground font-mono">Recent Data Queries</h2>
                    <span className="text-xs font-mono text-muted-foreground ml-1">(Scrapper Pool)</span>
                  </div>
                  <Link
                    href="/scrapper-pool"
                    className="text-sm font-mono text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                  >
                    View all <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Platform</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Operation</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono">Query</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">Results</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">Time</th>
                        <th className="pb-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider font-mono text-right">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataQueries.map((q) => (
                        <tr
                          key={q.id}
                          className="border-b border-border hover:bg-muted/50 cursor-pointer transition-colors"
                          onClick={() => router.push(`/scrapper-pool?view=${q.id}`)}
                        >
                          <td className="py-2.5 pr-3">
                            <span className="capitalize text-foreground font-mono">{q.platform}</span>
                          </td>
                          <td className="py-2.5 pr-3">
                            <span className="capitalize text-foreground font-mono">{q.operation}</span>
                          </td>
                          <td className="py-2.5 pr-3 max-w-[300px]">
                            <span className="text-muted-foreground truncate block font-mono">
                              {q.query_summary || "\u2014"}
                            </span>
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums text-foreground font-mono">
                            {q.result_count}
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums text-foreground font-mono">
                            {q.time_taken != null ? `${q.time_taken.toFixed(1)}s` : "\u2014"}
                          </td>
                          <td className="py-2.5 text-right text-muted-foreground whitespace-nowrap font-mono">
                            {q.created_at ? timeAgo(q.created_at) : "\u2014"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
