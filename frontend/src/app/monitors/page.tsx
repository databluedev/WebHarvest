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
  Eye,
  Plus,
  Trash2,
  Play,
  Pause,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  History,
  Activity,
  Pencil,
  Search,
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";

// ── Types ──────────────────────────────────────────────────

interface Monitor {
  id: string;
  name: string;
  url: string;
  is_active: boolean;
  check_interval_minutes: number;
  css_selector?: string;
  notify_on: string;
  keywords?: string[];
  webhook_url?: string;
  threshold?: number;
  total_checks: number;
  total_changes: number;
  last_checked_at?: string;
  next_check_at?: string;
  created_at: string;
  updated_at: string;
}

interface CheckRecord {
  id: string;
  checked_at: string;
  status_code: number;
  content_hash: string;
  has_changed: boolean;
  change_detail?: {
    type?: string;
    diff_percent?: number;
    keywords_found?: string[];
    keywords_removed?: string[];
  };
  word_count: number;
  response_time_ms: number;
}

// ── Constants ──────────────────────────────────────────────

const INTERVAL_OPTIONS = [
  { label: "5 min", value: 5 },
  { label: "15 min", value: 15 },
  { label: "30 min", value: 30 },
  { label: "1 hr", value: 60 },
  { label: "6 hr", value: 360 },
  { label: "12 hr", value: 720 },
  { label: "24 hr", value: 1440 },
];

const NOTIFY_OPTIONS = [
  { label: "Any Change", value: "any_change" },
  { label: "Content Change", value: "content_change" },
  { label: "Status Change", value: "status_change" },
  { label: "Keyword Added", value: "keyword_added" },
  { label: "Keyword Removed", value: "keyword_removed" },
];

// ── Helpers ────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function timeUntil(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((date.getTime() - now.getTime()) / 1000);
  if (seconds <= 0) return "now";
  if (seconds < 60) return `in ${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `in ${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `in ${hours}h`;
  const days = Math.floor(hours / 24);
  return `in ${days}d`;
}

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 1440) return `${minutes / 60}h`;
  return `${minutes / 1440}d`;
}

function truncateUrl(url: string, maxLen = 60): string {
  if (url.length <= maxLen) return url;
  return url.slice(0, maxLen - 3) + "...";
}

// ── Component ──────────────────────────────────────────────

export default function MonitorsPage() {
  const router = useRouter();

  // Monitor list state
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formInterval, setFormInterval] = useState(60);
  const [formSelector, setFormSelector] = useState("");
  const [formNotifyOn, setFormNotifyOn] = useState("any_change");
  const [formKeywords, setFormKeywords] = useState("");
  const [formThreshold, setFormThreshold] = useState(5);
  const [formWebhook, setFormWebhook] = useState("");

  // Expandable history per monitor
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});
  const [historyData, setHistoryData] = useState<Record<string, CheckRecord[]>>({});
  const [historyLoading, setHistoryLoading] = useState<Record<string, boolean>>({});

  // Action loading states
  const [actionLoading, setActionLoading] = useState<Record<string, string>>({});

  const [editingMonitor, setEditingMonitor] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{
    name: string;
    check_interval_minutes: number;
    css_selector: string;
    notify_on: string;
    keywords: string;
    webhook_url: string;
    threshold: number;
  }>({ name: "", check_interval_minutes: 60, css_selector: "", notify_on: "any_change", keywords: "", webhook_url: "", threshold: 5 });

  // History pagination
  const [historyTotal, setHistoryTotal] = useState<Record<string, number>>({});
  const [historyOffset, setHistoryOffset] = useState<Record<string, number>>({});

  // Search & filter
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "paused">("all");

  // ── Auth check & initial load ────────────────────────────

  const loadMonitors = useCallback(async () => {
    try {
      const res = await api.listMonitors();
      setMonitors(res.monitors || []);
    } catch (err: any) {
      setError(err.message || "Failed to load monitors");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    loadMonitors();
  }, [router, loadMonitors]);

  // ── CRUD handlers ────────────────────────────────────────

  const handleCreate = async () => {
    if (!formName.trim() || !formUrl.trim()) return;
    setCreating(true);
    setCreateError("");

    const keywords =
      formKeywords.trim()
        ? formKeywords.split(",").map((k) => k.trim()).filter(Boolean)
        : undefined;

    try {
      await api.createMonitor({
        name: formName.trim(),
        url: formUrl.trim().startsWith("http") ? formUrl.trim() : `https://${formUrl.trim()}`,
        check_interval_minutes: formInterval,
        css_selector: formSelector.trim() || undefined,
        notify_on: formNotifyOn,
        keywords,
        threshold: formThreshold,
        webhook_url: formWebhook.trim() || undefined,
      });
      // Reset form
      setFormName("");
      setFormUrl("");
      setFormInterval(60);
      setFormSelector("");
      setFormNotifyOn("any_change");
      setFormKeywords("");
      setFormThreshold(5);
      setFormWebhook("");
      setShowCreate(false);
      loadMonitors();
    } catch (err: any) {
      setCreateError(err.message || "Failed to create monitor");
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (monitor: Monitor) => {
    setActionLoading((prev) => ({ ...prev, [monitor.id]: "toggle" }));
    try {
      await api.updateMonitor(monitor.id, { is_active: !monitor.is_active });
      loadMonitors();
    } catch (err: any) {
      console.error("Toggle failed:", err);
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[monitor.id];
        return next;
      });
    }
  };

  const handleCheckNow = async (monitorId: string) => {
    setActionLoading((prev) => ({ ...prev, [monitorId]: "check" }));
    try {
      await api.triggerMonitorCheck(monitorId);
      // Brief delay to let the check complete on backend
      setTimeout(() => loadMonitors(), 1500);
    } catch (err: any) {
      console.error("Check failed:", err);
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[monitorId];
        return next;
      });
    }
  };

  const handleDelete = async (monitorId: string) => {
    if (!confirm("Delete this monitor? This action cannot be undone.")) return;
    setActionLoading((prev) => ({ ...prev, [monitorId]: "delete" }));
    try {
      await api.deleteMonitor(monitorId);
      setMonitors((prev) => prev.filter((m) => m.id !== monitorId));
    } catch (err: any) {
      console.error("Delete failed:", err);
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[monitorId];
        return next;
      });
    }
  };

  const startEditing = (monitor: Monitor) => {
    setEditingMonitor(monitor.id);
    setEditForm({
      name: monitor.name,
      check_interval_minutes: monitor.check_interval_minutes,
      css_selector: monitor.css_selector || "",
      notify_on: monitor.notify_on,
      keywords: monitor.keywords?.join(", ") || "",
      webhook_url: monitor.webhook_url || "",
      threshold: monitor.threshold || 5,
    });
  };

  const handleSaveEdit = async (monitorId: string) => {
    setActionLoading((prev) => ({ ...prev, [monitorId]: "edit" }));
    try {
      const keywords = editForm.keywords.trim()
        ? editForm.keywords.split(",").map((k) => k.trim()).filter(Boolean)
        : undefined;
      await api.updateMonitor(monitorId, {
        name: editForm.name,
        check_interval_minutes: editForm.check_interval_minutes,
        css_selector: editForm.css_selector || undefined,
        notify_on: editForm.notify_on,
        keywords,
        webhook_url: editForm.webhook_url || undefined,
        threshold: editForm.threshold,
      });
      setEditingMonitor(null);
      loadMonitors();
    } catch (err: any) {
      console.error("Edit failed:", err);
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[monitorId];
        return next;
      });
    }
  };

  const cancelEditing = () => {
    setEditingMonitor(null);
  };

  // ── History toggle ───────────────────────────────────────

  const toggleHistory = async (monitorId: string) => {
    const isExpanded = expandedHistory[monitorId];
    setExpandedHistory((prev) => ({ ...prev, [monitorId]: !isExpanded }));

    if (!isExpanded && !historyData[monitorId]) {
      setHistoryLoading((prev) => ({ ...prev, [monitorId]: true }));
      try {
        const res = await api.getMonitorHistory(monitorId, 20, 0);
        setHistoryData((prev) => ({ ...prev, [monitorId]: res.checks || [] }));
        setHistoryTotal((prev) => ({ ...prev, [monitorId]: res.total || 0 }));
        setHistoryOffset((prev) => ({ ...prev, [monitorId]: 0 }));
      } catch (err: any) {
        console.error("Failed to load history:", err);
        setHistoryData((prev) => ({ ...prev, [monitorId]: [] }));
      } finally {
        setHistoryLoading((prev) => ({ ...prev, [monitorId]: false }));
      }
    }
  };

  const loadMoreHistory = async (monitorId: string) => {
    const currentOffset = (historyOffset[monitorId] || 0) + 20;
    setHistoryLoading((prev) => ({ ...prev, [monitorId]: true }));
    try {
      const res = await api.getMonitorHistory(monitorId, 20, currentOffset);
      setHistoryData((prev) => ({
        ...prev,
        [monitorId]: [...(prev[monitorId] || []), ...(res.checks || [])],
      }));
      setHistoryOffset((prev) => ({ ...prev, [monitorId]: currentOffset }));
    } catch (err: any) {
      console.error("Failed to load more history:", err);
    } finally {
      setHistoryLoading((prev) => ({ ...prev, [monitorId]: false }));
    }
  };

  // ── Render ───────────────────────────────────────────────

  const showKeywordsField =
    formNotifyOn === "keyword_added" || formNotifyOn === "keyword_removed";

  const filteredMonitors = monitors.filter((m) => {
    const matchesSearch = !searchQuery || m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.url.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || (statusFilter === "active" && m.is_active) || (statusFilter === "paused" && !m.is_active);
    return matchesSearch && matchesStatus;
  });

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-5xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8 animate-float-in">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-primary/10 grid place-items-center">
                  <Eye className="h-4.5 w-4.5 text-primary" />
                </div>
                Monitors
              </h1>
              <p className="text-muted-foreground mt-1">
                Track URL changes and get notified when content updates
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setLoading(true); loadMonitors(); }}
                disabled={loading}
                className="gap-2"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh
              </Button>
              <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
                <Plus className="h-4 w-4" />
                New Monitor
              </Button>
            </div>
          </div>

          {/* Summary Stats */}
          {monitors.length > 0 && (
            <div className="mb-6 grid grid-cols-3 gap-4">
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{monitors.filter((m) => m.is_active).length}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Active Monitors</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{monitors.reduce((sum, m) => sum + (m.total_checks ?? 0), 0)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Total Checks</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{monitors.reduce((sum, m) => sum + (m.total_changes ?? 0), 0)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Total Changes</p>
              </div>
            </div>
          )}

          {/* Search & Filter Bar */}
          {monitors.length > 0 && (
            <div className="mb-4 flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search monitors by name or URL..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex items-center rounded-lg border border-border/40 p-0.5">
                {(["all", "active", "paused"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setStatusFilter(filter)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      statusFilter === filter
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {filter === "all" ? "All" : filter === "active" ? "Active" : "Paused"}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="mb-6 flex items-center gap-3 rounded-xl border border-destructive/50 bg-destructive/10 p-4">
              <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-400">Failed to load monitors</p>
                <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* ── Create Monitor Form ─────────────────────────── */}
          {showCreate && (
            <div className="rounded-2xl mb-6 animate-fade-in">
              <Card className="border-0 bg-transparent">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Plus className="h-4 w-4 text-primary" />
                    Create Monitor
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  {/* Row 1: Name & URL */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Name</label>
                      <Input
                        placeholder="My blog monitor"
                        value={formName}
                        onChange={(e) => setFormName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">URL</label>
                      <div className="flex items-center rounded-md border border-input bg-background px-3 h-9 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
                        <span className="text-sm text-muted-foreground shrink-0 select-none font-mono">https://</span>
                        <input
                          placeholder="example.com/page"
                          value={formUrl}
                          onChange={(e) => setFormUrl(e.target.value.replace(/^https?:\/\//, ""))}
                          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50 ml-1"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Row 2: Interval & Notify On */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Check Interval</label>
                      <div className="flex flex-wrap gap-2">
                        {INTERVAL_OPTIONS.map((opt) => (
                          <Button
                            key={opt.value}
                            variant={formInterval === opt.value ? "default" : "outline"}
                            size="sm"
                            onClick={() => setFormInterval(opt.value)}
                            className="text-xs"
                          >
                            {opt.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Notify On</label>
                      <select
                        className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/50 focus-visible:border-ring/30 transition-all duration-200"
                        value={formNotifyOn}
                        onChange={(e) => setFormNotifyOn(e.target.value)}
                      >
                        {NOTIFY_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Conditional: Keywords input */}
                  {showKeywordsField && (
                    <div className="space-y-2 animate-fade-in">
                      <label className="text-sm font-medium">
                        Keywords
                        <span className="text-muted-foreground font-normal ml-1">(comma-separated)</span>
                      </label>
                      <Input
                        placeholder="pricing, launch, update, breaking"
                        value={formKeywords}
                        onChange={(e) => setFormKeywords(e.target.value)}
                      />
                    </div>
                  )}

                  {/* Row 3: CSS Selector & Threshold */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">
                        CSS Selector
                        <span className="text-muted-foreground font-normal ml-1">(optional)</span>
                      </label>
                      <Input
                        placeholder="#main-content, .article-body"
                        value={formSelector}
                        onChange={(e) => setFormSelector(e.target.value)}
                        className="font-mono text-xs"
                      />
                      <p className="text-[11px] text-muted-foreground">
                        Monitor a specific element instead of the full page
                      </p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">
                        Change Threshold
                        <span className="text-muted-foreground font-normal ml-2 tabular-nums">
                          {formThreshold}%
                        </span>
                      </label>
                      <input
                        type="range"
                        min={1}
                        max={100}
                        value={formThreshold}
                        onChange={(e) => setFormThreshold(parseInt(e.target.value))}
                        className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                      <div className="flex justify-between text-[10px] text-muted-foreground">
                        <span>1% - Sensitive</span>
                        <span>100% - Major only</span>
                      </div>
                    </div>
                  </div>

                  {/* Webhook URL */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Webhook URL
                      <span className="text-muted-foreground font-normal ml-1">(optional)</span>
                    </label>
                    <Input
                      placeholder="https://your-server.com/webhook"
                      value={formWebhook}
                      onChange={(e) => setFormWebhook(e.target.value)}
                    />
                  </div>

                  {/* Create error */}
                  {createError && (
                    <div className="rounded-lg bg-destructive/10 border border-destructive/30 p-3 text-sm text-red-400 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {createError}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-1">
                    <Button
                      onClick={handleCreate}
                      disabled={creating || !formName.trim() || !formUrl.trim()}
                      className="gap-2"
                    >
                      {creating ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      Create Monitor
                    </Button>
                    <Button variant="outline" onClick={() => setShowCreate(false)}>
                      Cancel
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ── Monitor List ────────────────────────────────── */}
          {loading && monitors.length === 0 ? (
            <div className="rounded-2xl">
              <div className="p-12 flex flex-col items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-3" />
                <p className="text-sm text-muted-foreground">Loading monitors...</p>
              </div>
            </div>
          ) : filteredMonitors.length === 0 && monitors.length === 0 ? (
            <div className="rounded-2xl">
              <div className="p-16 flex flex-col items-center justify-center text-center">
                <div className="h-14 w-14 rounded-2xl bg-primary/10 grid place-items-center mb-4">
                  <Eye className="h-7 w-7 text-primary/60" />
                </div>
                <p className="text-sm font-medium mb-1">No monitors yet</p>
                <p className="text-xs text-muted-foreground max-w-sm">
                  Create a monitor to track URL changes. You will be notified when content updates based on your rules.
                </p>
                <Button
                  onClick={() => setShowCreate(true)}
                  className="mt-6 gap-2"
                  size="sm"
                >
                  <Plus className="h-4 w-4" />
                  Create your first monitor
                </Button>
              </div>
            </div>
          ) : filteredMonitors.length === 0 ? (
            <div className="rounded-2xl border border-border/40 bg-card">
              <div className="p-12 flex flex-col items-center justify-center text-center">
                <Search className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm font-medium mb-1">No monitors match your filter</p>
                <p className="text-xs text-muted-foreground">Try adjusting your search or filter criteria</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3 stagger-children">
              {filteredMonitors.map((monitor) => {
                const isExpanded = expandedHistory[monitor.id];
                const checks = historyData[monitor.id] || [];
                const isHistoryLoading = historyLoading[monitor.id];
                const currentAction = actionLoading[monitor.id];

                return (
                  <div key={monitor.id} className="rounded-2xl border border-border/40 bg-card hover:border-border/60 transition-all duration-200">
                    <div className="p-5">
                      {/* Main row */}
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          {/* Name & badges */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`h-2 w-2 rounded-full shrink-0 ${monitor.is_active ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
                            <span className="text-sm font-semibold tracking-tight">
                              {monitor.name}
                            </span>
                            <Badge
                              variant={monitor.is_active ? "success" : "outline"}
                              className="text-[10px]"
                            >
                              {monitor.is_active ? "Active" : "Paused"}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] gap-1">
                              <Clock className="h-2.5 w-2.5" />
                              {formatInterval(monitor.check_interval_minutes)}
                            </Badge>
                            {monitor.css_selector && (
                              <Badge variant="info" className="text-[10px] font-mono">
                                {monitor.css_selector.length > 24
                                  ? monitor.css_selector.slice(0, 24) + "..."
                                  : monitor.css_selector}
                              </Badge>
                            )}
                          </div>

                          {/* URL with favicon */}
                          <a
                            href={monitor.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs font-mono text-foreground/60 hover:text-primary transition-colors mt-1.5 group"
                            title={monitor.url}
                          >
                            <img
                              src={(() => { try { return `https://www.google.com/s2/favicons?domain=${new URL(monitor.url).hostname}&sz=16`; } catch { return ''; } })()}
                              alt=""
                              className="h-3.5 w-3.5 rounded-sm shrink-0"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                            />
                            {truncateUrl(monitor.url)}
                            <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </a>

                          {/* Metadata row */}
                          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                            {monitor.last_checked_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                Last: {timeAgo(monitor.last_checked_at)}
                              </span>
                            )}
                            {monitor.next_check_at && monitor.is_active && (
                              <span className="flex items-center gap-1">
                                <RefreshCw className="h-3 w-3" />
                                Next: {timeUntil(monitor.next_check_at)}
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <Activity className="h-3 w-3" />
                              {monitor.total_checks ?? 0} checks
                            </span>
                            <span className="flex items-center gap-1">
                              <AlertCircle className="h-3 w-3" />
                              {monitor.total_changes ?? 0} changes
                            </span>
                            {monitor.notify_on !== "any_change" && (
                              <Badge variant="secondary" className="text-[10px]">
                                {NOTIFY_OPTIONS.find((o) => o.value === monitor.notify_on)?.label ?? monitor.notify_on}
                              </Badge>
                            )}
                          </div>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => handleCheckNow(monitor.id)}
                            disabled={!!currentAction}
                            title="Check now"
                          >
                            {currentAction === "check" ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RefreshCw className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => handleToggle(monitor)}
                            disabled={!!currentAction}
                            title={monitor.is_active ? "Pause" : "Resume"}
                          >
                            {currentAction === "toggle" ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : monitor.is_active ? (
                              <Pause className="h-4 w-4" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => startEditing(monitor)}
                            disabled={!!currentAction}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => toggleHistory(monitor.id)}
                            title="View history"
                          >
                            <History className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(monitor.id)}
                            disabled={!!currentAction}
                            title="Delete"
                          >
                            {currentAction === "delete" ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </div>

                      {/* Inline Edit Form */}
                      {editingMonitor === monitor.id && (
                        <div className="mt-4 pt-4 border-t border-border/50 space-y-3 animate-fade-in">
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Name</label>
                              <Input
                                value={editForm.name}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Interval</label>
                              <select
                                value={editForm.check_interval_minutes}
                                onChange={(e) => setEditForm({ ...editForm, check_interval_minutes: parseInt(e.target.value) })}
                                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                              >
                                {INTERVAL_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                              </select>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                              <label className="text-xs font-medium">CSS Selector</label>
                              <Input
                                value={editForm.css_selector}
                                onChange={(e) => setEditForm({ ...editForm, css_selector: e.target.value })}
                                className="font-mono text-xs"
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Notify On</label>
                              <select
                                value={editForm.notify_on}
                                onChange={(e) => setEditForm({ ...editForm, notify_on: e.target.value })}
                                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                              >
                                {NOTIFY_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                              </select>
                            </div>
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium">Keywords (comma-separated)</label>
                            <Input
                              value={editForm.keywords}
                              onChange={(e) => setEditForm({ ...editForm, keywords: e.target.value })}
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium">Webhook URL</label>
                            <Input
                              value={editForm.webhook_url}
                              onChange={(e) => setEditForm({ ...editForm, webhook_url: e.target.value })}
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium">Threshold: {editForm.threshold}%</label>
                            <input
                              type="range"
                              min={1}
                              max={100}
                              value={editForm.threshold}
                              onChange={(e) => setEditForm({ ...editForm, threshold: parseInt(e.target.value) })}
                              className="w-full accent-primary"
                            />
                          </div>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => handleSaveEdit(monitor.id)}
                              disabled={currentAction === "edit"}
                              className="gap-1"
                            >
                              {currentAction === "edit" ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                              Save
                            </Button>
                            <Button size="sm" variant="outline" onClick={cancelEditing}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}

                      {/* ── Expandable History Section ──────── */}
                      {isExpanded && (
                        <div className="mt-4 pt-4 border-t border-border/50 animate-fade-in">
                          <div className="flex items-center gap-2 mb-3">
                            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-xs font-medium text-muted-foreground">
                              Recent Checks
                            </span>
                          </div>

                          {/* Response Time Chart */}
                          {checks.length >= 2 && (
                            <div className="mb-4 rounded-xl bg-foreground/[0.02] border border-border/30 p-3">
                              <div className="text-[11px] text-muted-foreground mb-2 font-medium">Response Time Trend</div>
                              <ResponsiveContainer width="100%" height={120}>
                                <LineChart data={[...checks].reverse().map((c) => ({
                                  time: new Date(c.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                                  ms: c.response_time_ms,
                                  changed: c.has_changed,
                                }))}>
                                  <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="#666" />
                                  <YAxis tick={{ fontSize: 10 }} stroke="#666" width={40} />
                                  <Tooltip
                                    contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                                    formatter={(val: number) => [`${val}ms`, "Response time"]}
                                  />
                                  <Line type="monotone" dataKey="ms" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                                  {[...checks].reverse().map((c, i) => c.has_changed ? (
                                    <ReferenceDot
                                      key={c.id}
                                      x={new Date(c.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                      y={c.response_time_ms}
                                      r={4}
                                      fill="#f59e0b"
                                      stroke="#f59e0b"
                                    />
                                  ) : null)}
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          )}

                          {isHistoryLoading ? (
                            <div className="flex items-center justify-center py-6">
                              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            </div>
                          ) : checks.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-6 text-center">
                              <Clock className="h-8 w-8 text-muted-foreground/30 mb-2" />
                              <p className="text-xs text-muted-foreground">
                                No checks recorded yet
                              </p>
                            </div>
                          ) : (
                            <>
                            <div className="space-y-1.5 max-h-64 overflow-y-auto">
                              {checks.map((check) => (
                                <div
                                  key={check.id}
                                  className={`flex items-center justify-between rounded-xl px-3 py-2.5 text-xs transition-colors ${
                                    check.has_changed
                                      ? "bg-amber-500/5 border border-amber-500/15"
                                      : "bg-foreground/[0.02] border border-transparent"
                                  }`}
                                >
                                  <div className="flex items-center gap-3 min-w-0">
                                    {/* Change indicator */}
                                    <div className="shrink-0">
                                      {check.has_changed ? (
                                        <div className="h-6 w-6 rounded-lg bg-amber-500/15 grid place-items-center">
                                          <AlertCircle className="h-3.5 w-3.5 text-amber-400" />
                                        </div>
                                      ) : (
                                        <div className="h-6 w-6 rounded-lg bg-emerald-500/10 grid place-items-center">
                                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                                        </div>
                                      )}
                                    </div>

                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="font-medium">
                                          {check.has_changed ? "Changed" : "No change"}
                                        </span>
                                        <Badge
                                          variant={
                                            check.status_code >= 200 && check.status_code < 300
                                              ? "success"
                                              : check.status_code >= 400
                                                ? "destructive"
                                                : "warning"
                                          }
                                          className="text-[9px] px-1.5"
                                        >
                                          {check.status_code}
                                        </Badge>
                                        {check.has_changed && check.change_detail?.diff_percent != null && (
                                          <span className="text-amber-400 tabular-nums">
                                            {check.change_detail.diff_percent.toFixed(1)}% diff
                                          </span>
                                        )}
                                      </div>
                                      {/* Keywords info */}
                                      {check.has_changed && check.change_detail?.keywords_found && check.change_detail.keywords_found.length > 0 && (
                                        <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                                          <span className="text-emerald-400">+keywords:</span>
                                          {check.change_detail.keywords_found.map((kw) => (
                                            <Badge key={kw} variant="success" className="text-[9px] px-1.5">
                                              {kw}
                                            </Badge>
                                          ))}
                                        </div>
                                      )}
                                      {check.has_changed && check.change_detail?.keywords_removed && check.change_detail.keywords_removed.length > 0 && (
                                        <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                                          <span className="text-red-400">-keywords:</span>
                                          {check.change_detail.keywords_removed.map((kw) => (
                                            <Badge key={kw} variant="destructive" className="text-[9px] px-1.5">
                                              {kw}
                                            </Badge>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-3 text-muted-foreground shrink-0 ml-3">
                                    <span className="tabular-nums">{check.word_count} words</span>
                                    <span className="tabular-nums">{check.response_time_ms}ms</span>
                                    <span className="text-foreground/40 min-w-[72px] text-right">
                                      {timeAgo(check.checked_at)}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                            {(historyTotal[monitor.id] || 0) > (historyData[monitor.id]?.length || 0) && (
                              <div className="mt-3 text-center">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => loadMoreHistory(monitor.id)}
                                  disabled={isHistoryLoading}
                                >
                                  {isHistoryLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                                  Load more ({(historyTotal[monitor.id] || 0) - (historyData[monitor.id]?.length || 0)} remaining)
                                </Button>
                              </div>
                            )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Stats footer */}
          {monitors.length > 0 && (
            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-muted-foreground">
              <span>
                {monitors.filter((m) => m.is_active).length} active /{" "}
                {monitors.length} total
              </span>
              <span className="h-3 w-px bg-border" />
              <span>
                {monitors.reduce((sum, m) => sum + (m.total_checks ?? 0), 0)} total checks
              </span>
              <span className="h-3 w-px bg-border" />
              <span>
                {monitors.reduce((sum, m) => sum + (m.total_changes ?? 0), 0)} total changes
              </span>
            </div>
          )}
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
