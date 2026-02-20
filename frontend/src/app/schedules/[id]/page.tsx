"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  Clock,
  ArrowLeft,
  Play,
  Pause,
  Zap,
  Trash2,
  Loader2,
  Eye,
  Pencil,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";

const TIMEZONES = [
  "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo",
  "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney", "America/Sao_Paulo",
];

export default function ScheduleDetailPage() {
  const router = useRouter();
  const params = useParams();
  const scheduleId = params.id as string;

  const [schedule, setSchedule] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editCron, setEditCron] = useState("");
  const [editTimezone, setEditTimezone] = useState("");
  const [editWebhookUrl, setEditWebhookUrl] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [runPage, setRunPage] = useState(0);
  const RUNS_PER_PAGE = 10;

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    loadData();
  }, [router, scheduleId]);

  const loadData = async () => {
    try {
      const [scheduleData, runsData] = await Promise.all([
        api.getSchedule(scheduleId),
        api.getScheduleRuns(scheduleId),
      ]);
      setSchedule(scheduleData);
      setRuns(runsData.runs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (!schedule) return;
    try {
      await api.updateSchedule(scheduleId, { is_active: !schedule.is_active });
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleTrigger = async () => {
    try {
      await api.triggerSchedule(scheduleId);
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this schedule? This cannot be undone.")) return;
    try {
      await api.deleteSchedule(scheduleId);
      router.push("/schedules");
    } catch (err) {
      console.error(err);
    }
  };

  const startEditing = () => {
    if (!schedule) return;
    setEditName(schedule.name);
    setEditCron(schedule.cron_expression);
    setEditTimezone(schedule.timezone || "UTC");
    setEditWebhookUrl(schedule.webhook_url || "");
    setEditing(true);
  };

  const handleSaveEdit = async () => {
    setEditSaving(true);
    try {
      await api.updateSchedule(scheduleId, {
        name: editName,
        cron_expression: editCron,
        timezone: editTimezone,
        webhook_url: editWebhookUrl || undefined,
      });
      setEditing(false);
      loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setEditSaving(false);
    }
  };

  const getJobLink = (run: any) => {
    const type = run.type;
    if (type === "crawl") return `/crawl/${run.id}`;
    if (type === "batch") return `/batch/${run.id}`;
    if (type === "search") return `/search/${run.id}`;
    return `/jobs`;
  };

  if (loading) {
    return (
      <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </main>
      </div>
      </SidebarProvider>
    );
  }

  if (!schedule) {
    return (
      <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-muted-foreground">Schedule not found</p>
        </main>
      </div>
      </SidebarProvider>
    );
  }

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <Link href="/schedules">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-primary/10 grid place-items-center">
                  <Clock className="h-4.5 w-4.5 text-primary" />
                </div>
                <h1 className="text-3xl font-bold tracking-tight">{schedule.name}</h1>
                <Badge variant={schedule.is_active ? "success" : "outline"}>
                  {schedule.is_active ? "Active" : "Paused"}
                </Badge>
              </div>
              <p className="text-muted-foreground mt-1 ml-12">
                {schedule.schedule_type} schedule
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={startEditing} className="gap-1">
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
              <Button variant="outline" size="sm" onClick={handleTrigger} className="gap-1">
                <Zap className="h-4 w-4" />
                Run Now
              </Button>
              <Button variant="outline" size="sm" onClick={handleToggle} className="gap-1">
                {schedule.is_active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {schedule.is_active ? "Pause" : "Resume"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDelete}
                className="gap-1 text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            </div>
          </div>

          {/* Edit Form */}
          {editing && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-lg">Edit Schedule</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Name</label>
                    <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Cron Expression</label>
                    <Input value={editCron} onChange={(e) => setEditCron(e.target.value)} className="font-mono" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Timezone</label>
                    <select
                      value={editTimezone}
                      onChange={(e) => setEditTimezone(e.target.value)}
                      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    >
                      {TIMEZONES.map((tz) => (
                        <option key={tz} value={tz}>{tz}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Webhook URL</label>
                    <Input value={editWebhookUrl} onChange={(e) => setEditWebhookUrl(e.target.value)} />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleSaveEdit} disabled={editSaving} className="gap-1">
                    {editSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    Save
                  </Button>
                  <Button variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Schedule Info */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Schedule
                </CardTitle>
              </CardHeader>
              <CardContent>
                <code className="text-lg font-mono">{schedule.cron_expression}</code>
                <p className="text-sm text-muted-foreground mt-2">
                  Timezone: {schedule.timezone}
                </p>
                {schedule.next_run_human && schedule.is_active && (
                  <p className="text-sm text-primary mt-1">
                    Next run: {schedule.next_run_human}
                  </p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Statistics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-bold">{schedule.run_count} runs</p>
                {runs.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">Success rate:</span>
                      <span className="text-sm font-medium">
                        {Math.round((runs.filter((r: any) => r.status === "completed").length / runs.length) * 100)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">Last 10:</span>
                      {runs.slice(0, 10).map((r: any, i: number) => (
                        <div
                          key={i}
                          className={`h-3 w-3 rounded-full ${
                            r.status === "completed"
                              ? "bg-green-500"
                              : r.status === "failed"
                              ? "bg-red-500"
                              : "bg-yellow-500"
                          }`}
                          title={`${r.status}${r.created_at ? ` - ${new Date(r.created_at).toLocaleString()}` : ""}`}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {schedule.last_run_at && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Last run: {new Date(schedule.last_run_at).toLocaleString()}
                  </p>
                )}
                <p className="text-sm text-muted-foreground mt-1">
                  Created: {new Date(schedule.created_at).toLocaleString()}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Config */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              {schedule.config && typeof schedule.config === "object" ? (
                <div className="space-y-2">
                  {Object.entries(schedule.config).map(([key, value]) => (
                    <div key={key} className="flex items-start gap-3 rounded-lg bg-muted/50 px-4 py-2.5">
                      <span className="text-xs font-medium text-muted-foreground min-w-[120px] pt-0.5">
                        {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </span>
                      <span className="text-sm font-mono break-all">
                        {Array.isArray(value)
                          ? (value as string[]).join(", ")
                          : typeof value === "object" && value !== null
                            ? JSON.stringify(value, null, 2)
                            : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <pre className="bg-muted rounded-md p-4 text-sm font-mono overflow-x-auto">
                  {JSON.stringify(schedule.config, null, 2)}
                </pre>
              )}
            </CardContent>
          </Card>

          {/* Run History */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Run History</CardTitle>
              <CardDescription>Recent jobs triggered by this schedule</CardDescription>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Clock className="h-10 w-10 text-muted-foreground/40 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    No runs yet. This schedule hasn&apos;t triggered any jobs.
                  </p>
                </div>
              ) : (
                <>
                <div className="space-y-2">
                  {runs.slice(runPage * RUNS_PER_PAGE, (runPage + 1) * RUNS_PER_PAGE).map((run: any) => (
                    <div
                      key={run.id}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={
                              run.status === "completed"
                                ? "success"
                                : run.status === "failed"
                                ? "destructive"
                                : run.status === "running"
                                ? "warning"
                                : "outline"
                            }
                            className="text-xs"
                          >
                            {run.status}
                          </Badge>
                          <span className="text-xs text-muted-foreground font-mono">
                            {run.id.slice(0, 8)}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                          <span>
                            {run.completed_pages}/{run.total_pages} pages
                          </span>
                          {run.created_at && (
                            <span>{new Date(run.created_at).toLocaleString()}</span>
                          )}
                          {run.error && (
                            <span className="text-red-400 truncate max-w-[200px]">
                              {run.error}
                            </span>
                          )}
                        </div>
                      </div>
                      <Link href={getJobLink(run)}>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
                {runs.length > RUNS_PER_PAGE && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                    <p className="text-sm text-muted-foreground">
                      Page {runPage + 1} of {Math.ceil(runs.length / RUNS_PER_PAGE)}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRunPage((p) => Math.max(0, p - 1))}
                        disabled={runPage === 0}
                        className="gap-1"
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRunPage((p) => Math.min(Math.ceil(runs.length / RUNS_PER_PAGE) - 1, p + 1))}
                        disabled={runPage >= Math.ceil(runs.length / RUNS_PER_PAGE) - 1}
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
