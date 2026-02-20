"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { ModeSwitcher } from "@/components/layout/mode-switcher";
import { Footer } from "@/components/layout/footer";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  Globe,
  Search,
  Map,
  Layers,
  ArrowRight,
  Clock,
  FileText,
  Code,
  Link2,
  Camera,
  Braces,
  List,
  Image as ImageIcon,
  ExternalLink,
  Loader2,
  Settings2,
  LayoutGrid,
  FileCode,
  ChevronDown,
  Radar,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

function getJobDetailPath(job: any): string {
  switch (job.type) {
    case "scrape": return `/scrape/${job.id}`;
    case "crawl": return `/crawl/${job.id}`;
    case "batch": return `/batch/${job.id}`;
    case "search": return `/search/${job.id}`;
    case "map": return `/map/${job.id}`;
    default: return `/crawl/${job.id}`;
  }
}

function getJobUrl(job: any): string {
  if (!job.config) return "";
  if (job.config.url) return job.config.url;
  if (job.config.query) return job.config.query;
  if (job.config.urls?.length === 1) return job.config.urls[0];
  if (job.config.urls?.length > 1) return `${job.config.urls.length} URLs`;
  return "";
}

function getDomain(url: string): string {
  try {
    const parsed = new URL(url.startsWith("http") ? url : `https://${url}`);
    return parsed.hostname;
  } catch {
    return url;
  }
}

function getFavicon(url: string): string {
  const domain = getDomain(url);
  return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
}

function getTypeIcon(type: string) {
  switch (type) {
    case "scrape": return Search;
    case "crawl": return Globe;
    case "map": return Map;
    case "search": return Radar;
    case "batch": return Layers;
    default: return FileText;
  }
}

function getTypeColor(type: string) {
  switch (type) {
    case "scrape": return "text-orange-400";
    case "crawl": return "text-blue-400";
    case "map": return "text-violet-400";
    case "search": return "text-emerald-400";
    case "batch": return "text-cyan-400";
    default: return "text-muted-foreground";
  }
}

function formatDate(dateStr: string): { date: string; time: string } {
  const d = new Date(dateStr);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
    time: d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
  };
}

// Format badge icons
const formatIcons: Record<string, { icon: any; label: string }> = {
  markdown: { icon: FileText, label: "Markdown" },
  html: { icon: Code, label: "HTML" },
  links: { icon: Link2, label: "Links" },
  screenshot: { icon: Camera, label: "Screenshot" },
  structured_data: { icon: Braces, label: "JSON" },
  headings: { icon: List, label: "Summary" },
  images: { icon: ImageIcon, label: "Images" },
};

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [selectedFormat, setSelectedFormat] = useState("markdown");
  const [showFormatDropdown, setShowFormatDropdown] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }
    api.getMe().then(setUser).catch(() => router.push("/auth/login"));
    api
      .getUsageHistory({ per_page: 9 })
      .then((res) => setRecentJobs(res.jobs))
      .catch(() => {});
  }, [router]);

  const handleScrape = async () => {
    if (!url.trim()) return;
    setLoading(true);
    try {
      const fullUrl = url.startsWith("http") ? url : `https://${url}`;
      const res = await api.scrape({
        url: fullUrl,
        formats: [selectedFormat],
        only_main_content: true,
      });
      if (res.job_id) {
        router.push(`/scrape/${res.job_id}`);
      } else if (res.data) {
        // Synchronous result — go to scrape page with result
        router.push("/scrape");
      }
    } catch {
      router.push("/scrape");
    } finally {
      setLoading(false);
    }
  };

  const handleGetCode = () => {
    const fullUrl = url.startsWith("http") ? url : `https://${url}`;
    const code = `curl -X POST ${window.location.origin}/v1/scrape \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"url": "${fullUrl || "https://example.com"}", "formats": ["${selectedFormat}"]}'`;
    navigator.clipboard.writeText(code);
  };

  if (!user) return null;

  return (
    <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background">
          <MobileMenuButton />
          <div className="min-h-screen flex flex-col">
            <div className="flex-1 p-6 lg:p-8 max-w-6xl mx-auto w-full">
              {/* Mode Switcher */}
              <div className="pt-4 pb-8 animate-float-in">
                <ModeSwitcher />
              </div>

              {/* Decorative grid lines (subtle) */}
              <div className="relative">
                {/* URL Input Section */}
                <section className="max-w-2xl mx-auto mb-12 animate-float-in" style={{ animationDelay: "0.05s" }}>
                  <div className="rounded-xl border border-border/50 bg-card/80 backdrop-blur-sm p-4 shadow-lg shadow-black/5">
                    {/* URL Input */}
                    <div className="flex items-center gap-0 rounded-lg bg-background border border-border/50 px-3 h-11 mb-3">
                      <span className="text-sm text-muted-foreground/50 shrink-0 select-none">
                        https://
                      </span>
                      <input
                        type="text"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && !loading && handleScrape()}
                        placeholder="example.com"
                        className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/30 ml-1"
                      />
                    </div>

                    {/* Controls Row */}
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        {/* Settings icon */}
                        <button
                          onClick={() => router.push("/scrape")}
                          className="h-8 w-8 rounded-md bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                          title="Advanced settings"
                        >
                          <Settings2 className="h-3.5 w-3.5" />
                        </button>
                        {/* Grid icon */}
                        <button
                          onClick={() => router.push("/batch")}
                          className="h-8 w-8 rounded-md bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                          title="Batch scrape"
                        >
                          <LayoutGrid className="h-3.5 w-3.5" />
                        </button>
                        {/* File icon */}
                        <button
                          onClick={() => router.push("/docs")}
                          className="h-8 w-8 rounded-md bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                          title="API Docs"
                        >
                          <FileCode className="h-3.5 w-3.5" />
                        </button>

                        {/* Format Dropdown */}
                        <div className="relative">
                          <button
                            onClick={() => setShowFormatDropdown(!showFormatDropdown)}
                            className="flex items-center gap-1.5 h-8 rounded-md bg-muted/50 px-2.5 text-[12px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            <span>Format: {selectedFormat.charAt(0).toUpperCase() + selectedFormat.slice(1)}</span>
                            <ChevronDown className="h-3 w-3" />
                          </button>
                          {showFormatDropdown && (
                            <div className="absolute top-10 left-0 z-50 w-44 rounded-lg border border-border/60 bg-card shadow-xl p-1 animate-scale-in">
                              {["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"].map(
                                (fmt) => (
                                  <button
                                    key={fmt}
                                    onClick={() => {
                                      setSelectedFormat(fmt);
                                      setShowFormatDropdown(false);
                                    }}
                                    className={`flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-[12px] transition-colors ${
                                      selectedFormat === fmt
                                        ? "bg-primary/10 text-primary"
                                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                    }`}
                                  >
                                    {(() => {
                                      const FIcon = formatIcons[fmt]?.icon;
                                      return FIcon ? <FIcon className="h-3 w-3" /> : null;
                                    })()}
                                    {fmt.charAt(0).toUpperCase() + fmt.slice(1).replace("_", " ")}
                                  </button>
                                )
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {/* Get Code */}
                        <button
                          onClick={handleGetCode}
                          className="flex items-center gap-1.5 h-8 rounded-md px-3 text-[12px] font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted transition-colors"
                        >
                          <Code className="h-3.5 w-3.5" />
                          Get code
                        </button>

                        {/* Start Scraping */}
                        <button
                          onClick={handleScrape}
                          disabled={loading || !url.trim()}
                          className="flex items-center gap-1.5 h-8 rounded-md px-4 text-[12px] font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm shadow-primary/20"
                        >
                          {loading ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <>Start scraping</>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* No format warning */}
                  {!selectedFormat && (
                    <p className="text-[11px] text-amber-400/70 mt-2 text-center">
                      No format selected — only metadata will be returned
                    </p>
                  )}
                </section>

                {/* Recent Runs */}
                {recentJobs.length > 0 && (
                  <section className="animate-float-in" style={{ animationDelay: "0.1s" }}>
                    <div className="flex items-center justify-between mb-5">
                      <h2 className="text-lg font-semibold tracking-tight">Recent Runs</h2>
                      <Link
                        href="/jobs"
                        className="text-[12px] text-muted-foreground/60 hover:text-foreground transition-colors flex items-center gap-1"
                      >
                        View all
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </div>

                    {/* Scrollbar indicator dots */}
                    <div className="flex items-center gap-2 mb-4">
                      <div className="flex-1 h-[2px] rounded-full bg-primary/30" />
                      <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/20" />
                      <div className="flex-1 h-[2px] rounded-full bg-muted-foreground/10" />
                    </div>

                    {/* Cards Grid */}
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                      {recentJobs.map((job) => {
                        const jobUrl = getJobUrl(job);
                        const domain = getDomain(jobUrl);
                        const TypeIcon = getTypeIcon(job.type);
                        const typeColor = getTypeColor(job.type);
                        const { date, time } = job.created_at
                          ? formatDate(job.created_at)
                          : { date: "", time: "" };
                        const jobFormats: string[] = job.config?.formats || [];

                        return (
                          <Link key={job.id} href={getJobDetailPath(job)}>
                            <div className="rounded-xl border border-border/40 bg-card hover:bg-card/80 hover:border-border/60 transition-all duration-200 cursor-pointer group">
                              {/* Domain Header */}
                              <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-border/30">
                                <div className="flex items-center gap-2 min-w-0">
                                  {jobUrl && !jobUrl.includes("URLs") && (
                                    <img
                                      src={getFavicon(jobUrl)}
                                      alt=""
                                      className="h-4 w-4 rounded-sm shrink-0"
                                      onError={(e) => {
                                        (e.target as HTMLImageElement).style.display = "none";
                                      }}
                                    />
                                  )}
                                  <span className="text-sm font-medium truncate">
                                    {domain || "No URL"}
                                  </span>
                                </div>
                                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-muted-foreground/60 transition-colors shrink-0" />
                              </div>

                              {/* Details */}
                              <div className="px-4 py-3 space-y-2.5">
                                {/* Endpoint */}
                                <div className="flex items-center justify-between">
                                  <span className="text-[12px] text-muted-foreground/50">Endpoint</span>
                                  <div className="flex items-center gap-1.5">
                                    <TypeIcon className={`h-3.5 w-3.5 ${typeColor}`} />
                                    <span className="text-[12px] font-medium capitalize">{job.type}</span>
                                  </div>
                                </div>

                                {/* Status */}
                                <div className="flex items-center justify-between">
                                  <span className="text-[12px] text-muted-foreground/50">Status</span>
                                  <div className="flex items-center gap-1.5">
                                    <div
                                      className={`h-2 w-2 rounded-full ${
                                        job.status === "completed"
                                          ? "bg-emerald-400"
                                          : job.status === "failed"
                                          ? "bg-red-400"
                                          : job.status === "running"
                                          ? "bg-amber-400 animate-pulse"
                                          : "bg-muted-foreground/40"
                                      }`}
                                    />
                                    <span className="text-[12px] font-medium capitalize">
                                      {job.status === "completed" ? "Success" : job.status}
                                    </span>
                                  </div>
                                </div>

                                {/* Started */}
                                <div className="flex items-center justify-between">
                                  <span className="text-[12px] text-muted-foreground/50">Started</span>
                                  <div className="text-right">
                                    <span className="text-[12px] font-medium">{date}</span>
                                    {time && (
                                      <span className="text-[11px] text-muted-foreground/40 ml-1.5">
                                        {time}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                {/* Formats */}
                                {jobFormats.length > 0 && (
                                  <div className="pt-1">
                                    <span className="text-[12px] text-muted-foreground/50 block mb-1.5">
                                      Formats
                                    </span>
                                    <div className="flex flex-wrap gap-1">
                                      {jobFormats.map((fmt: string) => {
                                        const fmtInfo = formatIcons[fmt];
                                        const FmtIcon = fmtInfo?.icon || FileText;
                                        const fmtLabel = fmtInfo?.label || fmt;
                                        return (
                                          <span
                                            key={fmt}
                                            className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground/70"
                                          >
                                            <FmtIcon className="h-2.5 w-2.5" />
                                            {fmtLabel}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                  </section>
                )}

                {/* Empty state when no recent jobs */}
                {recentJobs.length === 0 && (
                  <section className="text-center py-16 animate-float-in" style={{ animationDelay: "0.1s" }}>
                    <Search className="h-12 w-12 text-muted-foreground/20 mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-1">No recent runs</h3>
                    <p className="text-sm text-muted-foreground/50">
                      Enter a URL above to start scraping
                    </p>
                  </section>
                )}
              </div>
            </div>

            {/* Footer */}
            <Footer />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
