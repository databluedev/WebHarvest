"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  Clock,
  Plus,
  Play,
  Pause,
  Trash2,
  Eye,
  Loader2,
  Zap,
  ChevronDown,
  ChevronUp,
  Pencil,
  Save,
  CheckCircle2,
  Globe,
  Search,
  CalendarClock,
  Activity,
} from "lucide-react";
import Link from "next/link";

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Every 12 hours", value: "0 */12 * * *" },
  { label: "Daily (midnight)", value: "0 0 * * *" },
  { label: "Daily (9am)", value: "0 9 * * *" },
  { label: "Weekly (Monday)", value: "0 0 * * 1" },
  { label: "Custom", value: "custom" },
];

const TIMEZONES = [
  "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo",
  "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney", "America/Sao_Paulo",
];

function cronToHuman(cron: string): string {
  const presetMap: Record<string, string> = {
    "0 * * * *": "Every hour",
    "0 */6 * * *": "Every 6 hours",
    "0 */12 * * *": "Every 12 hours",
    "0 0 * * *": "Daily at midnight",
    "0 9 * * *": "Daily at 9:00 AM",
    "0 0 * * 1": "Weekly on Monday",
    "0 0 * * 0": "Weekly on Sunday",
    "*/5 * * * *": "Every 5 minutes",
    "*/15 * * * *": "Every 15 minutes",
    "*/30 * * * *": "Every 30 minutes",
  };
  return presetMap[cron] || cron;
}

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "paused">("all");

  // Create form state
  const [name, setName] = useState("");
  const [scheduleType, setScheduleType] = useState("crawl");
  const [cronPreset, setCronPreset] = useState("0 0 * * *");
  const [customCron, setCustomCron] = useState("");
  const [configUrl, setConfigUrl] = useState("");
  const [configMaxPages, setConfigMaxPages] = useState(100);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [editingSchedule, setEditingSchedule] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editCron, setEditCron] = useState("");
  const [editTimezone, setEditTimezone] = useState("");
  const [editWebhookUrl, setEditWebhookUrl] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    loadSchedules();
  }, [router]);

  const loadSchedules = async () => {
    try {
      const res = await api.listSchedules();
      setSchedules(res.schedules);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!name || !configUrl) return;
    setCreating(true);
    setError("");

    const cron = cronPreset === "custom" ? customCron : cronPreset;

    let config: any = {};
    const fullConfigUrl = configUrl.startsWith("http") ? configUrl : `https://${configUrl}`;
    if (scheduleType === "crawl") {
      config = { url: fullConfigUrl, max_pages: configMaxPages };
    } else if (scheduleType === "scrape") {
      config = { url: fullConfigUrl, formats: ["markdown"] };
    }

    try {
      await api.createSchedule({
        name,
        schedule_type: scheduleType,
        config,
        cron_expression: cron,
        timezone,
        webhook_url: webhookUrl || undefined,
      });
      setName("");
      setConfigUrl("");
      setWebhookUrl("");
      setShowCreate(false);
      loadSchedules();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (id: string, isActive: boolean) => {
    try {
      await api.updateSchedule(id, { is_active: !isActive });
      loadSchedules();
    } catch (err) {
      console.error(err);
    }
  };

  const handleTrigger = async (id: string) => {
    try {
      await api.triggerSchedule(id);
      loadSchedules();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this schedule?")) return;
    try {
      await api.deleteSchedule(id);
      loadSchedules();
    } catch (err) {
      console.error(err);
    }
  };

  const startEditing = (s: any) => {
    setEditingSchedule(s.id);
    setEditName(s.name);
    setEditCron(s.cron_expression);
    setEditTimezone(s.timezone || "UTC");
    setEditWebhookUrl(s.webhook_url || "");
  };

  const handleSaveEdit = async (id: string) => {
    setEditSaving(true);
    try {
      await api.updateSchedule(id, {
        name: editName,
        cron_expression: editCron,
        timezone: editTimezone,
        webhook_url: editWebhookUrl || undefined,
      });
      setEditingSchedule(null);
      loadSchedules();
    } catch (err: any) {
      console.error("Edit failed:", err);
    } finally {
      setEditSaving(false);
    }
  };

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-8 animate-float-in">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-primary/10 grid place-items-center">
                  <Clock className="h-4.5 w-4.5 text-primary" />
                </div>
                Schedules
              </h1>
              <p className="text-muted-foreground mt-1">
                Set up recurring scrapes and crawls
              </p>
            </div>
            <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
              <Plus className="h-4 w-4" />
              New Schedule
            </Button>
          </div>

          {/* Summary Stats */}
          {schedules.length > 0 && (
            <div className="mb-6 grid grid-cols-4 gap-4">
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{schedules.length}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Total</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{schedules.filter((s: any) => s.is_active).length}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Active</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-2xl font-bold tabular-nums">{schedules.reduce((sum: number, s: any) => sum + (s.run_count || 0), 0)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Total Runs</p>
              </div>
              <div className="rounded-2xl border border-border/40 bg-card p-4 text-center">
                <p className="text-sm font-medium text-primary truncate">
                  {schedules.find((s: any) => s.is_active && s.next_run_human)?.next_run_human || "—"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">Next Run</p>
              </div>
            </div>
          )}

          {/* Search & Filter Bar */}
          {schedules.length > 0 && (
            <div className="mb-4 flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search schedules..."
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

          {/* Create Form */}
          {showCreate && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-lg">Create Schedule</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Name</label>
                    <Input
                      placeholder="My daily crawl"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Type</label>
                    <div className="flex gap-2">
                      {["crawl", "scrape"].map((t) => (
                        <Button
                          key={t}
                          variant={scheduleType === t ? "default" : "outline"}
                          size="sm"
                          onClick={() => setScheduleType(t)}
                        >
                          {t.charAt(0).toUpperCase() + t.slice(1)}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">URL</label>
                  <div className="flex items-center rounded-md border border-input bg-background px-3 h-9 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
                    <span className="text-sm text-muted-foreground shrink-0 select-none font-mono">https://</span>
                    <input
                      placeholder="example.com"
                      value={configUrl}
                      onChange={(e) => setConfigUrl(e.target.value.replace(/^https?:\/\//, ""))}
                      className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50 ml-1"
                    />
                  </div>
                </div>

                {scheduleType === "crawl" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Max Pages</label>
                    <Input
                      type="number"
                      value={configMaxPages}
                      onChange={(e) => setConfigMaxPages(parseInt(e.target.value) || 100)}
                      min={1}
                      max={1000}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium">Schedule</label>
                  <div className="flex flex-wrap gap-2">
                    {CRON_PRESETS.map((preset) => (
                      <Button
                        key={preset.value}
                        variant={cronPreset === preset.value ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCronPreset(preset.value)}
                        className="text-xs"
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                  {cronPreset === "custom" && (
                    <Input
                      placeholder="0 */6 * * * (min hour dom mon dow)"
                      value={customCron}
                      onChange={(e) => setCustomCron(e.target.value)}
                      className="mt-2 font-mono"
                    />
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Timezone</label>
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Webhook URL (optional)</label>
                  <Input
                    placeholder="https://your-server.com/webhook"
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                  />
                </div>

                {error && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">
                    {error}
                  </div>
                )}

                <div className="flex gap-2">
                  <Button onClick={handleCreate} disabled={creating || !name || !configUrl} className="gap-2">
                    {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    Create
                  </Button>
                  <Button variant="outline" onClick={() => setShowCreate(false)}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Schedule List */}
          {(() => {
            const filteredSchedules = schedules.filter((s: any) => {
              const matchesSearch = !searchQuery || s.name.toLowerCase().includes(searchQuery.toLowerCase());
              const matchesStatus = statusFilter === "all" || (statusFilter === "active" && s.is_active) || (statusFilter === "paused" && !s.is_active);
              return matchesSearch && matchesStatus;
            });

            if (loading) {
              return (
                <div className="rounded-2xl border border-border/40 bg-card">
                  <div className="flex justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                </div>
              );
            }

            if (schedules.length === 0) {
              return (
                <div className="rounded-2xl border border-border/40 bg-card">
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="h-14 w-14 rounded-2xl bg-primary/10 grid place-items-center mb-4">
                      <Clock className="h-7 w-7 text-primary/60" />
                    </div>
                    <p className="text-sm font-medium mb-1">No schedules yet</p>
                    <p className="text-xs text-muted-foreground max-w-sm">
                      Create a schedule to automate your scraping and crawling jobs.
                    </p>
                    <Button onClick={() => setShowCreate(true)} className="mt-6 gap-2" size="sm">
                      <Plus className="h-4 w-4" />
                      Create your first schedule
                    </Button>
                  </div>
                </div>
              );
            }

            if (filteredSchedules.length === 0) {
              return (
                <div className="rounded-2xl border border-border/40 bg-card">
                  <div className="p-12 flex flex-col items-center justify-center text-center">
                    <Search className="h-8 w-8 text-muted-foreground/30 mb-3" />
                    <p className="text-sm font-medium mb-1">No schedules match your filter</p>
                    <p className="text-xs text-muted-foreground">Try adjusting your search or filter criteria</p>
                  </div>
                </div>
              );
            }

            return (
              <div className="space-y-3 stagger-children">
                {filteredSchedules.map((s: any) => {
                  const configUrl = s.config?.url || s.config?.urls?.[0] || "";
                  let faviconHost = "";
                  try { faviconHost = new URL(configUrl).hostname; } catch {}

                  return (
                    <div key={s.id} className="rounded-2xl border border-border/40 bg-card hover:border-border/60 transition-all duration-200">
                      <div className="p-5">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`h-2 w-2 rounded-full shrink-0 ${s.is_active ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
                              <span className="text-sm font-semibold tracking-tight">{s.name}</span>
                              <Badge variant={s.is_active ? "success" : "outline"} className="text-[10px]">
                                {s.is_active ? "Active" : "Paused"}
                              </Badge>
                              <Badge variant="outline" className="text-[10px]">
                                {s.schedule_type}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-1.5 mt-1.5">
                              {faviconHost && (
                                <img
                                  src={`https://www.google.com/s2/favicons?domain=${faviconHost}&sz=16`}
                                  alt=""
                                  className="h-3.5 w-3.5 rounded-sm shrink-0"
                                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                />
                              )}
                              {configUrl && (
                                <span className="text-xs font-mono text-foreground/60 truncate max-w-[300px]">{configUrl}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                              <span className="flex items-center gap-1">
                                <CalendarClock className="h-3 w-3" />
                                {cronToHuman(s.cron_expression)}
                              </span>
                              <code className="text-[10px] bg-muted px-1.5 py-0.5 rounded">{s.cron_expression}</code>
                              <span className="flex items-center gap-1">
                                <Activity className="h-3 w-3" />
                                {s.run_count} runs
                              </span>
                              {s.next_run_human && s.is_active && (
                                <span className="text-primary">Next: {s.next_run_human}</span>
                              )}
                              {s.last_run_at && (
                                <span>Last: {new Date(s.last_run_at).toLocaleString()}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => startEditing(s)} title="Edit">
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleTrigger(s.id)} title="Run now">
                              <Zap className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleToggle(s.id, s.is_active)} title={s.is_active ? "Pause" : "Resume"}>
                              {s.is_active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                            </Button>
                            <Link href={`/schedules/${s.id}`}>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <Eye className="h-4 w-4" />
                              </Button>
                            </Link>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => handleDelete(s.id)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {editingSchedule === s.id && (
                          <div className="mt-4 pt-4 border-t border-border/50 space-y-3 animate-fade-in">
                            <div className="grid grid-cols-2 gap-3">
                              <div className="space-y-1">
                                <label className="text-xs font-medium">Name</label>
                                <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                              </div>
                              <div className="space-y-1">
                                <label className="text-xs font-medium">Cron Expression</label>
                                <Input value={editCron} onChange={(e) => setEditCron(e.target.value)} className="font-mono" />
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <div className="space-y-1">
                                <label className="text-xs font-medium">Timezone</label>
                                <select
                                  value={editTimezone}
                                  onChange={(e) => setEditTimezone(e.target.value)}
                                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                                >
                                  {TIMEZONES.map((tz) => (
                                    <option key={tz} value={tz}>{tz}</option>
                                  ))}
                                </select>
                              </div>
                              <div className="space-y-1">
                                <label className="text-xs font-medium">Webhook URL</label>
                                <Input value={editWebhookUrl} onChange={(e) => setEditWebhookUrl(e.target.value)} />
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" onClick={() => handleSaveEdit(s.id)} disabled={editSaving} className="gap-1">
                                {editSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                                Save
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => setEditingSchedule(null)}>
                                Cancel
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
