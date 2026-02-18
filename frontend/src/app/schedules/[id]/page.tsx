"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
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
} from "lucide-react";
import Link from "next/link";

export default function ScheduleDetailPage() {
  const router = useRouter();
  const params = useParams();
  const scheduleId = params.id as string;

  const [schedule, setSchedule] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

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

  const getJobLink = (run: any) => {
    const type = run.type;
    if (type === "crawl") return `/crawl/${run.id}`;
    if (type === "batch") return `/batch/${run.id}`;
    if (type === "search") return `/search/${run.id}`;
    return `/jobs`;
  };

  if (loading) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </main>
      </div>
    );
  }

  if (!schedule) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-muted-foreground">Schedule not found</p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
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
                <h1 className="text-3xl font-bold">{schedule.name}</h1>
                <Badge variant={schedule.is_active ? "success" : "outline"}>
                  {schedule.is_active ? "Active" : "Paused"}
                </Badge>
              </div>
              <p className="text-muted-foreground mt-1">
                {schedule.schedule_type} schedule
              </p>
            </div>
            <div className="flex gap-2">
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
              <pre className="bg-muted rounded-md p-4 text-sm font-mono overflow-x-auto">
                {JSON.stringify(schedule.config, null, 2)}
              </pre>
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
                    No runs yet. This schedule hasn't triggered any jobs.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {runs.map((run) => (
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
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
