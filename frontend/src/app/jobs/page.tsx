"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
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

function getTypeColorClasses(type: string): string {
  switch (type) {
    case "scrape": return "border-cyan-500/30 text-cyan-400 bg-cyan-500/10";
    case "crawl": return "border-violet-500/30 text-violet-400 bg-violet-500/10";
    case "search": return "border-amber-500/30 text-amber-400 bg-amber-500/10";
    case "map": return "border-pink-500/30 text-pink-400 bg-pink-500/10";
    default: return "border-border text-muted-foreground bg-muted/30";
  }
}

function getStatusClasses(status: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-500/30 text-emerald-400 bg-emerald-500/10";
    case "failed":
      return "border-red-500/30 text-red-400 bg-red-500/10";
    case "running":
      return "border-amber-500/30 text-amber-400 bg-amber-500/10";
    case "pending":
    case "cancelled":
    default:
      return "border-border text-muted-foreground bg-muted/30";
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
    if (sortBy !== column) return <ArrowUpDown className="h-3 w-3 ml-1 text-muted-foreground" />;
    return sortDir === "asc"
      ? <ArrowUp className="h-3 w-3 ml-1 text-foreground" />
      : <ArrowDown className="h-3 w-3 ml-1 text-foreground" />;
  };

  return (
    <PageLayout activePage="jobs">
      <div className="px-6 md:px-10 max-w-[1400px] mx-auto py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-[36px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text-blue">
            Job History
          </h1>
          <p className="text-muted-foreground font-mono text-[14px] mt-1">
            View all your past scrape, crawl, search, and map jobs
          </p>
        </div>

        {/* Filters */}
        <div className="border border-border bg-card/50 p-5 mb-6">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                placeholder="Search by URL or query..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="h-10 w-full bg-transparent border border-border pl-9 pr-3 text-[14px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30"
              />
            </div>
            <select
              value={typeFilter}
              onChange={handleTypeChange}
              className="h-10 bg-background border border-border px-3 text-[13px] font-mono text-foreground focus:outline-none focus:border-foreground/30"
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
              className="h-10 bg-background border border-border px-3 text-[13px] font-mono text-foreground focus:outline-none focus:border-foreground/30"
            >
              {JOB_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleSearch}
              className="border border-border px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-foreground hover:bg-foreground hover:text-background transition-all flex items-center gap-2"
            >
              <Search className="h-4 w-4" />
              Search
            </button>
            {selectedJobs.size > 0 && (
              <button
                onClick={handleBulkDelete}
                className="border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20 px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono flex items-center gap-2 transition-all"
              >
                <Trash2 className="h-4 w-4" />
                Delete {selectedJobs.size}
              </button>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 border border-red-500/30 bg-red-500/10 p-3 flex items-center gap-2 text-[13px] font-mono text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Jobs Table */}
        <div className="border border-border bg-card/50 relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-500 via-violet-500 to-pink-500" />
          {/* Table header bar */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <span className="text-[16px] font-mono font-bold text-foreground">Jobs</span>
            {!loading && (
              <span className="text-[13px] font-mono text-muted-foreground">
                {total} total job{total !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          <div className="px-5 pb-5">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-3" />
                <p className="text-[13px] font-mono text-muted-foreground">Loading jobs...</p>
              </div>
            ) : jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <History className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-[16px] font-mono font-bold text-foreground">No jobs found</p>
                <p className="text-[13px] font-mono text-muted-foreground mt-1">
                  {searchQuery || typeFilter !== "all" || statusFilter !== "all"
                    ? "Try adjusting your filters or search query."
                    : "Start a scrape, crawl, or search to see your job history here."}
                </p>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px] font-mono">
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
                        <th className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono">Type</th>
                        <th className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono">URL / Query</th>
                        <th
                          className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono cursor-pointer hover:text-foreground/60 select-none"
                          onClick={() => handleSort("status")}
                        >
                          <span className="flex items-center">Status<SortIcon column="status" /></span>
                        </th>
                        <th
                          className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono cursor-pointer hover:text-foreground/60 select-none"
                          onClick={() => handleSort("total_pages")}
                        >
                          <span className="flex items-center">Pages<SortIcon column="total_pages" /></span>
                        </th>
                        <th
                          className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono cursor-pointer hover:text-foreground/60 select-none"
                          onClick={() => handleSort("duration_seconds")}
                        >
                          <span className="flex items-center">Duration<SortIcon column="duration_seconds" /></span>
                        </th>
                        <th
                          className="text-left py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono cursor-pointer hover:text-foreground/60 select-none"
                          onClick={() => handleSort("created_at")}
                        >
                          <span className="flex items-center">Created<SortIcon column="created_at" /></span>
                        </th>
                        <th className="text-right py-3 px-3 text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-mono"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((job) => (
                        <tr
                          key={job.id}
                          onClick={() => handleRowClick(job)}
                          className="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
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
                            <span className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border ${getTypeColorClasses(job.type)}`}>
                              {job.type}
                            </span>
                          </td>
                          <td className="py-3 px-3 max-w-[300px]">
                            <span className="truncate block text-foreground font-mono" title={getJobUrl(job) || "-"}>
                              {getJobUrl(job) || "-"}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border ${getStatusClasses(job.status)}`}>
                              {job.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 tabular-nums text-foreground font-mono">
                            {job.completed_pages !== null && job.total_pages !== null
                              ? `${job.completed_pages} / ${job.total_pages}`
                              : job.total_pages !== null
                              ? job.total_pages
                              : "-"}
                          </td>
                          <td className="py-3 px-3 tabular-nums text-foreground font-mono">
                            {formatDuration(job.duration_seconds)}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap text-muted-foreground font-mono">
                            {formatDate(job.created_at ?? "")}
                          </td>
                          <td className="py-3 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                            <button
                              className="inline-flex items-center justify-center h-8 w-8 text-muted-foreground hover:text-foreground transition-colors"
                              onClick={() => router.push(getRerunPath(job))}
                              title="Rerun"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </button>
                            <button
                              className={`inline-flex items-center justify-center h-8 w-8 transition-colors ${
                                deleteConfirm === job.id
                                  ? "text-red-400 bg-red-500/10"
                                  : "text-muted-foreground hover:text-red-400"
                              }`}
                              onClick={() => handleDelete(job.id)}
                              disabled={deleting === job.id}
                              title={deleteConfirm === job.id ? "Click again to confirm delete" : "Delete job"}
                            >
                              {deleting === job.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                    <p className="text-[13px] font-mono text-muted-foreground">
                      Page {page} of {totalPages}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        className="border border-border px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-foreground hover:bg-foreground hover:text-background transition-all disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-foreground flex items-center gap-1"
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </button>
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="border border-border px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-foreground hover:bg-foreground hover:text-background transition-all disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-foreground flex items-center gap-1"
                      >
                        Next
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
