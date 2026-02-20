"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
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

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

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
    if (scheduleType === "crawl") {
      config = { url: configUrl, max_pages: configMaxPages };
    } else if (scheduleType === "scrape") {
      config = { url: configUrl, formats: ["markdown"] };
    } else if (scheduleType === "batch") {
      config = { urls: configUrl.split("\n").filter(Boolean), formats: ["markdown"] };
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
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto grid-bg">
        <div className="mesh-gradient min-h-full">
        <div className="p-8 max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-8 animate-float-in">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Schedules</h1>
              <p className="text-muted-foreground mt-1">
                Set up recurring scrapes, crawls, and batch jobs
              </p>
            </div>
            <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
              <Plus className="h-4 w-4" />
              New Schedule
            </Button>
          </div>

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
                      {["crawl", "scrape", "batch"].map((t) => (
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
                  <label className="text-sm font-medium">
                    {scheduleType === "batch" ? "URLs (one per line)" : "URL"}
                  </label>
                  {scheduleType === "batch" ? (
                    <textarea
                      className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                      placeholder="https://example.com&#10;https://another.com"
                      value={configUrl}
                      onChange={(e) => setConfigUrl(e.target.value)}
                    />
                  ) : (
                    <Input
                      placeholder="https://example.com"
                      value={configUrl}
                      onChange={(e) => setConfigUrl(e.target.value)}
                    />
                  )}
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
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Your Schedules</CardTitle>
              <CardDescription>{schedules.length} schedule(s)</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : schedules.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Clock className="h-12 w-12 text-muted-foreground/40 mb-4" />
                  <p className="text-sm text-muted-foreground">
                    No schedules yet. Create one to automate your scraping.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {schedules.map((s) => (
                    <div key={s.id} className="rounded-md border p-4">
                      <div className="flex items-center justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{s.name}</span>
                            <Badge variant={s.is_active ? "success" : "outline"} className="text-xs">
                              {s.is_active ? "Active" : "Paused"}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {s.schedule_type}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                            <code>{s.cron_expression}</code>
                            <span>{s.run_count} runs</span>
                            {s.next_run_human && s.is_active && (
                              <span>Next: {s.next_run_human}</span>
                            )}
                            {s.last_run_at && (
                              <span>Last: {new Date(s.last_run_at).toLocaleString()}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 ml-4">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => startEditing(s)}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => handleTrigger(s.id)}
                            title="Run now"
                          >
                            <Zap className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => handleToggle(s.id, s.is_active)}
                            title={s.is_active ? "Pause" : "Resume"}
                          >
                            {s.is_active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                          </Button>
                          <Link href={`/schedules/${s.id}`}>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(s.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      {editingSchedule === s.id && (
                        <div className="mt-4 pt-4 border-t border-border space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Name</label>
                              <Input
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Cron Expression</label>
                              <Input
                                value={editCron}
                                onChange={(e) => setEditCron(e.target.value)}
                                className="font-mono"
                              />
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
                              <Input
                                value={editWebhookUrl}
                                onChange={(e) => setEditWebhookUrl(e.target.value)}
                              />
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => handleSaveEdit(s.id)}
                              disabled={editSaving}
                              className="gap-1"
                            >
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
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        </div>
      </main>
    </div>
  );
}
