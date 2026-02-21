"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  History,
  Search,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  CheckSquare,
  Square,
} from "lucide-react";

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

const JOB_TYPES = [
  { value: "all", label: "All Types" },
  { value: "scrape", label: "Scrape" },
  { value: "crawl", label: "Crawl" },
  { value: "search", label: "Search" },
  { value: "map", label: "Map" },
];

const JOB_STATUSES = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

function getStatusBadgeVariant(status: string): "success" | "destructive" | "warning" | "secondary" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "destructive";
    case "running":
      return "warning";
    case "pending":
    case "cancelled":
    default:
      return "secondary";
  }
}

function getJobUrl(job: Job): string | null {
  if (!job.config) return null;
  if (job.config.url) return job.config.url;
  if (job.config.query) return job.config.query;
  if (job.config.urls && Array.isArray(job.config.urls)) {
    if (job.config.urls.length === 1) return job.config.urls[0];
    return `${job.config.urls.length} URLs`;
  }
  return null;
}

function getJobDetailPath(job: Job): string {
  switch (job.type) {
    case "scrape":
      return `/scrape/${job.id}`;
    case "crawl":
      return `/crawl/${job.id}`;
    case "search":
      return `/search/${job.id}`;
    case "map":
      return `/map/${job.id}`;
    default:
      return `/crawl/${job.id}`;
  }
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hrs = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hrs}h ${remainMins}m`;
}

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

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());

  const PER_PAGE = 20;

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
  }, [router]);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getUsageHistory({
        page,
        per_page: PER_PAGE,
        type: typeFilter,
        status: statusFilter,
        search: searchQuery || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setJobs(res.jobs);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load job history");
    } finally {
      setLoading(false);
    }
  }, [page, typeFilter, statusFilter, searchQuery, sortBy, sortDir]);

  useEffect(() => {
    if (api.getToken()) {
      loadJobs();
    }
  }, [loadJobs]);

  const handleSearch = () => {
    setPage(1);
    setSearchQuery(searchInput);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setTypeFilter(e.target.value);
    setPage(1);
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(e.target.value);
    setPage(1);
  };

  const handleDelete = async (jobId: string) => {
    if (deleteConfirm !== jobId) {
      setDeleteConfirm(jobId);
      return;
    }
    setDeleting(jobId);
    try {
      await api.deleteJob(jobId);
      setDeleteConfirm(null);
      loadJobs();
    } catch (err: any) {
      setError(err.message || "Failed to delete job");
    } finally {
      setDeleting(null);
    }
  };

  const handleRowClick = (job: Job) => {
    router.push(getJobDetailPath(job));
  };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortDir("desc");
    }
    setPage(1);
  };

  const toggleSelectJob = (jobId: string) => {
    setSelectedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedJobs.size === jobs.length) {
      setSelectedJobs(new Set());
    } else {
      setSelectedJobs(new Set(jobs.map((j) => j.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selectedJobs.size} selected job(s)?`)) return;
    for (const jobId of Array.from(selectedJobs)) {
      try {
        await api.deleteJob(jobId);
      } catch {}
    }
    setSelectedJobs(new Set());
    loadJobs();
  };

  const getRerunPath = (job: Job): string => {
    switch (job.type) {
      case "scrape": return "/scrape";
      case "crawl": return "/crawl";
      case "search": return "/search";
      case "map": return "/map";
      default: return "/";
    }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-30" />;
    return sortDir === "asc" ? <ArrowUp className="h-3 w-3 ml-1" /> : <ArrowDown className="h-3 w-3 ml-1" />;
  };

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8">
          <div className="mb-8 animate-float-in">
            <h1 className="text-3xl font-bold tracking-tight">Job History</h1>
            <p className="text-muted-foreground mt-1">
              View all your past scrape, crawl, search, and map jobs
            </p>
          </div>

          {/* Filters */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by URL or query..."
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    className="pl-9"
                  />
                </div>
                <select
                  value={typeFilter}
                  onChange={handleTypeChange}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  {JOB_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <select
                  value={statusFilter}
                  onChange={handleStatusChange}
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  {JOB_STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <Button onClick={handleSearch} variant="secondary" className="gap-2">
                  <Search className="h-4 w-4" />
                  Search
                </Button>
                {selectedJobs.size > 0 && (
                  <Button onClick={handleBulkDelete} variant="destructive" size="sm" className="gap-2">
                    <Trash2 className="h-4 w-4" />
                    Delete {selectedJobs.size}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 p-3 flex items-center gap-2 text-sm text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {/* Jobs Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <span>Jobs</span>
                {!loading && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {total} total job{total !== 1 ? "s" : ""}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">Loading jobs...</p>
                </div>
              ) : jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <History className="h-12 w-12 text-muted-foreground/40 mb-4" />
                  <p className="text-lg font-medium">No jobs found</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {searchQuery || typeFilter !== "all" || statusFilter !== "all"
                      ? "Try adjusting your filters or search query."
                      : "Start a scrape, crawl, or search to see your job history here."}
                  </p>
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="py-3 px-3 w-8">
                            <button onClick={toggleSelectAll} className="text-muted-foreground hover:text-foreground">
                              {selectedJobs.size === jobs.length && jobs.length > 0 ? (
                                <CheckSquare className="h-4 w-4" />
                              ) : (
                                <Square className="h-4 w-4" />
                              )}
                            </button>
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">Type</th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground">URL / Query</th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("status")}>
                            <span className="flex items-center">Status<SortIcon column="status" /></span>
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("total_pages")}>
                            <span className="flex items-center">Pages<SortIcon column="total_pages" /></span>
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("duration_seconds")}>
                            <span className="flex items-center">Duration<SortIcon column="duration_seconds" /></span>
                          </th>
                          <th className="text-left py-3 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("created_at")}>
                            <span className="flex items-center">Created<SortIcon column="created_at" /></span>
                          </th>
                          <th className="text-right py-3 px-3 font-medium text-muted-foreground"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobs.map((job) => (
                          <tr
                            key={job.id}
                            onClick={() => handleRowClick(job)}
                            className="border-b border-border/50 hover:bg-muted/50 cursor-pointer transition-colors"
                          >
                            <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                              <button onClick={() => toggleSelectJob(job.id)} className="text-muted-foreground hover:text-foreground">
                                {selectedJobs.has(job.id) ? (
                                  <CheckSquare className="h-4 w-4" />
                                ) : (
                                  <Square className="h-4 w-4" />
                                )}
                              </button>
                            </td>
                            <td className="py-3 px-3">
                              <Badge variant="outline" className="capitalize">
                                {job.type}
                              </Badge>
                            </td>
                            <td className="py-3 px-3 max-w-[300px]">
                              <span className="truncate block" title={getJobUrl(job) || "-"}>
                                {getJobUrl(job) || "-"}
                              </span>
                            </td>
                            <td className="py-3 px-3">
                              <Badge variant={getStatusBadgeVariant(job.status)}>
                                {job.status}
                              </Badge>
                            </td>
                            <td className="py-3 px-3 tabular-nums">
                              {job.completed_pages !== null && job.total_pages !== null
                                ? `${job.completed_pages} / ${job.total_pages}`
                                : job.total_pages !== null
                                ? job.total_pages
                                : "-"}
                            </td>
                            <td className="py-3 px-3 tabular-nums">
                              {formatDuration(job.duration_seconds)}
                            </td>
                            <td className="py-3 px-3 whitespace-nowrap text-muted-foreground">
                              {formatDate(job.created_at ?? "")}
                            </td>
                            <td className="py-3 px-3 text-right">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  router.push(getRerunPath(job));
                                }}
                                title="Rerun"
                              >
                                <RotateCcw className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className={`h-8 w-8 ${
                                  deleteConfirm === job.id
                                    ? "text-destructive hover:text-destructive bg-destructive/10"
                                    : "text-muted-foreground hover:text-destructive"
                                }`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDelete(job.id);
                                }}
                                disabled={deleting === job.id}
                                title={deleteConfirm === job.id ? "Click again to confirm delete" : "Delete job"}
                              >
                                {deleting === job.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                              </Button>
                            </td>
                          </tr>
                        ))}
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
                          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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
