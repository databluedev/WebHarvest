"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Webhook,
  Send,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Filter,
  Loader2,
  AlertCircle,
  ChevronLeft,
  Activity,
} from "lucide-react";

// ---- Types ----------------------------------------------------------------

interface WebhookDelivery {
  id: string;
  job_id?: string;
  url: string;
  event: string;
  payload: any;
  status_code?: number;
  response_body?: string;
  response_time_ms?: number;
  success: boolean;
  attempt: number;
  max_attempts: number;
  error?: string;
  created_at: string;
}

interface WebhookStats {
  total_deliveries: number;
  successful: number;
  failed: number;
  success_rate: number;
  avg_response_time_ms: number;
  events_breakdown: Record<string, number>;
}

interface TestResult {
  success: boolean;
  status_code?: number;
  response_body?: string;
  response_time_ms: number;
  error?: string;
}

// ---- Constants -------------------------------------------------------------

const EVENT_TYPES = [
  { value: "", label: "All Events" },
  { value: "crawl.completed", label: "crawl.completed" },
  { value: "crawl.failed", label: "crawl.failed" },
  { value: "crawl.page", label: "crawl.page" },
  { value: "batch.completed", label: "batch.completed" },
  { value: "batch.failed", label: "batch.failed" },
  { value: "search.completed", label: "search.completed" },
  { value: "search.failed", label: "search.failed" },
  { value: "monitor.change", label: "monitor.change" },
  { value: "schedule.completed", label: "schedule.completed" },
  { value: "schedule.failed", label: "schedule.failed" },
];

const STATUS_FILTERS = [
  { value: "", label: "All Statuses" },
  { value: "true", label: "Success" },
  { value: "false", label: "Failed" },
];

const PER_PAGE = 20;

// ---- Helpers ---------------------------------------------------------------

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(dateStr);
}

function formatMs(ms?: number): string {
  if (ms === undefined || ms === null) return "-";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function truncateUrl(url: string, max = 50): string {
  if (url.length <= max) return url;
  return url.slice(0, max - 3) + "...";
}

function statusCodeColor(code?: number): string {
  if (!code) return "text-muted-foreground";
  if (code >= 200 && code < 300) return "text-emerald-400";
  if (code >= 300 && code < 400) return "text-amber-400";
  return "text-red-400";
}

// ---- Component -------------------------------------------------------------

export default function WebhooksPage() {
  const router = useRouter();

  // Stats
  const [stats, setStats] = useState<WebhookStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Deliveries
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [deliveriesLoading, setDeliveriesLoading] = useState(true);

  // Filters
  const [eventFilter, setEventFilter] = useState("");
  const [successFilter, setSuccessFilter] = useState("");

  // Expanded rows
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // Test webhook
  const [testUrl, setTestUrl] = useState("");
  const [testSecret, setTestSecret] = useState("");
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testError, setTestError] = useState("");

  // General
  const [error, setError] = useState("");

  // ---- Auth check ----------------------------------------------------------

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
    }
  }, [router]);

  // ---- Data loading --------------------------------------------------------

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await api.getWebhookStats();
      setStats(res.stats);
    } catch (err: any) {
      console.error("Failed to load webhook stats:", err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadDeliveries = useCallback(async () => {
    setDeliveriesLoading(true);
    setError("");
    try {
      const params: {
        limit: number;
        offset: number;
        event?: string;
        success?: boolean;
      } = {
        limit: PER_PAGE,
        offset: (page - 1) * PER_PAGE,
      };
      if (eventFilter) params.event = eventFilter;
      if (successFilter !== "") params.success = successFilter === "true";

      const res = await api.listWebhookDeliveries(params);
      setDeliveries(res.deliveries);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load webhook deliveries");
    } finally {
      setDeliveriesLoading(false);
    }
  }, [page, eventFilter, successFilter]);

  useEffect(() => {
    if (api.getToken()) {
      loadStats();
      loadDeliveries();
    }
  }, [loadStats, loadDeliveries]);

  // ---- Handlers ------------------------------------------------------------

  const handleRefresh = () => {
    loadStats();
    loadDeliveries();
  };

  const handleFilterChange = () => {
    setPage(1);
  };

  const handleEventFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setEventFilter(e.target.value);
    handleFilterChange();
  };

  const handleSuccessFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSuccessFilter(e.target.value);
    handleFilterChange();
  };

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleTestWebhook = async () => {
    if (!testUrl.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    setTestError("");

    try {
      const res = await api.testWebhook(
        testUrl.trim(),
        testSecret.trim() || undefined
      );
      setTestResult(res.test_result);
    } catch (err: any) {
      setTestError(err.message || "Failed to send test webhook");
    } finally {
      setTestLoading(false);
    }
  };

  const handleTestKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !testLoading) {
      handleTestWebhook();
    }
  };

  // ---- Derived values ------------------------------------------------------

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  // ---- Render --------------------------------------------------------------

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between animate-float-in">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <Webhook className="h-8 w-8 text-primary" />
                Webhooks
              </h1>
              <p className="mt-1 text-muted-foreground">
                Delivery logs, debugging, and endpoint testing
              </p>
            </div>
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={statsLoading || deliveriesLoading}
              className="gap-2"
            >
              {statsLoading || deliveriesLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Refresh
            </Button>
          </div>

          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Total Deliveries
                </CardTitle>
                <Send className="h-5 w-5 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <div className="h-8 w-20 rounded bg-muted animate-pulse" />
                ) : (
                  <p className="text-3xl font-bold tabular-nums">
                    {(stats?.total_deliveries ?? 0).toLocaleString()}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  All-time webhook deliveries
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Success Rate
                </CardTitle>
                <CheckCircle2 className="h-5 w-5 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <div className="h-8 w-20 rounded bg-muted animate-pulse" />
                ) : (
                  <p className="text-3xl font-bold tabular-nums">
                    {(stats?.success_rate ?? 0).toFixed(1)}%
                  </p>
                )}
                <div className="mt-2 h-2 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                    style={{
                      width: `${Math.min(stats?.success_rate ?? 0, 100)}%`,
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Avg Response Time
                </CardTitle>
                <Clock className="h-5 w-5 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <div className="h-8 w-20 rounded bg-muted animate-pulse" />
                ) : (
                  <p className="text-3xl font-bold tabular-nums">
                    {formatMs(stats?.avg_response_time_ms)}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  Average endpoint response latency
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Failed Deliveries
                </CardTitle>
                <XCircle className="h-5 w-5 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <div className="h-8 w-20 rounded bg-muted animate-pulse" />
                ) : (
                  <p className="text-3xl font-bold tabular-nums text-red-400">
                    {(stats?.failed ?? 0).toLocaleString()}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  Deliveries that exhausted all retries
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Test Webhook Section */}
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Send className="h-5 w-5 text-primary" />
                Test Webhook Endpoint
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-3">
                <Input
                  placeholder="https://your-server.com/webhook"
                  value={testUrl}
                  onChange={(e) => setTestUrl(e.target.value)}
                  onKeyDown={handleTestKeyDown}
                  className="flex-1"
                />
                <Input
                  placeholder="Secret (optional)"
                  value={testSecret}
                  onChange={(e) => setTestSecret(e.target.value)}
                  onKeyDown={handleTestKeyDown}
                  type="password"
                  className="sm:w-48"
                />
                <Button
                  onClick={handleTestWebhook}
                  disabled={testLoading || !testUrl.trim()}
                  className="gap-2 shrink-0"
                >
                  {testLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  Send Test
                </Button>
              </div>

              {/* Test Result */}
              {testResult && (
                <div
                  className={`mt-4 rounded-lg border p-4 ${
                    testResult.success
                      ? "border-emerald-500/30 bg-emerald-500/5"
                      : "border-red-500/30 bg-red-500/5"
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    {testResult.success ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-400 shrink-0" />
                    )}
                    <span className="text-sm font-medium">
                      {testResult.success
                        ? "Webhook delivered successfully"
                        : "Webhook delivery failed"}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">
                        Status Code
                      </p>
                      <p
                        className={`text-sm font-mono font-medium ${statusCodeColor(
                          testResult.status_code
                        )}`}
                      >
                        {testResult.status_code ?? "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">
                        Response Time
                      </p>
                      <p className="text-sm font-mono font-medium">
                        {formatMs(testResult.response_time_ms)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">
                        Error
                      </p>
                      <p className="text-sm font-mono text-red-400">
                        {testResult.error || "None"}
                      </p>
                    </div>
                  </div>

                  {testResult.response_body && (
                    <div className="mt-3">
                      <p className="text-xs text-muted-foreground mb-1">
                        Response Body
                      </p>
                      <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto max-h-40 overflow-y-auto">
                        {testResult.response_body}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* Test Error */}
              {testError && (
                <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-4 flex items-center gap-3">
                  <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
                  <p className="text-sm text-red-400">{testError}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Delivery Log */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-primary" />
                  Delivery Log
                </span>
                {!deliveriesLoading && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {total} deliver{total !== 1 ? "ies" : "y"}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Filters */}
              <div className="flex flex-col sm:flex-row gap-3 mb-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Filter className="h-4 w-4 shrink-0" />
                </div>
                <select
                  value={eventFilter}
                  onChange={handleEventFilterChange}
                  className="h-10 rounded-lg border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring/50 focus:border-ring/30 transition-all duration-200"
                >
                  {EVENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <select
                  value={successFilter}
                  onChange={handleSuccessFilterChange}
                  className="h-10 rounded-lg border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring/50 focus:border-ring/30 transition-all duration-200"
                >
                  {STATUS_FILTERS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Error */}
              {error && (
                <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 p-3 flex items-center gap-2 text-sm text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              {/* Loading state */}
              {deliveriesLoading ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">
                    Loading deliveries...
                  </p>
                </div>
              ) : deliveries.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Webhook className="h-12 w-12 text-muted-foreground/40 mb-4" />
                  <p className="text-lg font-medium">No deliveries found</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {eventFilter || successFilter
                      ? "Try adjusting your filters."
                      : "Webhook deliveries will appear here when jobs with webhook URLs complete."}
                  </p>
                </div>
              ) : (
                <>
                  {/* Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground w-8" />
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            Event
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            URL
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            Status
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            Response Time
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            Attempt
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">
                            Time
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.map((delivery) => {
                          const isExpanded = expandedRows.has(delivery.id);
                          return (
                            <DeliveryRow
                              key={delivery.id}
                              delivery={delivery}
                              isExpanded={isExpanded}
                              onToggle={() => toggleRow(delivery.id)}
                            />
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                      <p className="text-sm text-muted-foreground">
                        Page {page} of {totalPages}
                      </p>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage((p) => Math.max(1, p - 1))}
                          disabled={page <= 1}
                          className="gap-1"
                        >
                          <ChevronLeft className="h-4 w-4" />
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setPage((p) => Math.min(totalPages, p + 1))
                          }
                          disabled={page >= totalPages}
                          className="gap-1"
                        >
                          Next
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}

// ---- Delivery Row Component ------------------------------------------------

function DeliveryRow({
  delivery,
  isExpanded,
  onToggle,
}: {
  delivery: WebhookDelivery;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const payloadStr = (() => {
    try {
      return typeof delivery.payload === "string"
        ? JSON.stringify(JSON.parse(delivery.payload), null, 2)
        : JSON.stringify(delivery.payload, null, 2);
    } catch {
      return String(delivery.payload ?? "");
    }
  })();

  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-border/50 hover:bg-muted/50 cursor-pointer transition-colors"
      >
        {/* Expand chevron */}
        <td className="py-3 px-3">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>

        {/* Event */}
        <td className="py-3 px-3">
          <Badge variant="outline" className="font-mono text-xs">
            {delivery.event}
          </Badge>
        </td>

        {/* URL */}
        <td className="py-3 px-3 max-w-[200px]">
          <span
            className="truncate block font-mono text-xs text-muted-foreground"
            title={delivery.url}
          >
            {truncateUrl(delivery.url, 45)}
          </span>
        </td>

        {/* Status */}
        <td className="py-3 px-3">
          {delivery.success ? (
            <Badge variant="success" className="gap-1">
              <CheckCircle2 className="h-3 w-3" />
              {delivery.status_code ?? "OK"}
            </Badge>
          ) : (
            <Badge variant="destructive" className="gap-1">
              <XCircle className="h-3 w-3" />
              {delivery.status_code ?? "ERR"}
            </Badge>
          )}
        </td>

        {/* Response Time */}
        <td className="py-3 px-3 tabular-nums font-mono text-xs">
          {formatMs(delivery.response_time_ms)}
        </td>

        {/* Attempt */}
        <td className="py-3 px-3 tabular-nums text-xs">
          <span className="text-muted-foreground">
            {delivery.attempt}/{delivery.max_attempts}
          </span>
        </td>

        {/* Time */}
        <td className="py-3 px-3 whitespace-nowrap text-xs text-muted-foreground">
          <span title={formatDate(delivery.created_at)}>
            {timeAgo(delivery.created_at)}
          </span>
        </td>
      </tr>

      {/* Expanded details */}
      {isExpanded && (
        <tr className="border-b border-border/50">
          <td colSpan={7} className="p-0">
            <div className="bg-muted/30 px-6 py-4 space-y-4 animate-fade-in">
              {/* Meta row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Delivery ID
                  </p>
                  <p className="text-xs font-mono break-all">{delivery.id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Job ID</p>
                  <p className="text-xs font-mono break-all">
                    {delivery.job_id || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Full URL
                  </p>
                  <p className="text-xs font-mono break-all">{delivery.url}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Timestamp
                  </p>
                  <p className="text-xs font-mono">
                    {formatDate(delivery.created_at)}
                  </p>
                </div>
              </div>

              {/* Error */}
              {delivery.error && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Error</p>
                  <div className="rounded-md border border-red-500/20 bg-red-500/5 p-3">
                    <p className="text-xs font-mono text-red-400">
                      {delivery.error}
                    </p>
                  </div>
                </div>
              )}

              {/* Payload */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">
                  Request Payload
                </p>
                <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto border border-border">
                  {payloadStr || "No payload"}
                </pre>
              </div>

              {/* Response */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">
                  Response Body
                </p>
                <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto border border-border">
                  {delivery.response_body || "No response body"}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
