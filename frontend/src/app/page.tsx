"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { ModeSwitcher } from "@/components/layout/mode-switcher";
import { Footer } from "@/components/layout/footer";
import { api } from "@/lib/api";
import {
  FileText,
  Code,
  Link2,
  Camera,
  Braces,
  List,
  Image as ImageIcon,
  ExternalLink,
  Loader2,
  SlidersHorizontal,
  FileCode,
  ChevronDown,
  Download,
  ArrowRight,
  Clock,
  Search,
  Crosshair,
  Satellite,
  Bug,
  Network,
  Boxes,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

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
  } catch { return url; }
}

function getFavicon(url: string): string {
  return `https://www.google.com/s2/favicons?domain=${getDomain(url)}&sz=32`;
}

function getTypeIcon(type: string) {
  switch (type) {
    case "scrape": return Crosshair;
    case "crawl": return Bug;
    case "map": return Network;
    case "search": return Satellite;
    case "batch": return Boxes;
    default: return FileText;
  }
}

function formatDate(dateStr: string): { date: string; time: string } {
  const d = new Date(dateStr);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
  };
}

const formatIcons: Record<string, { icon: any; label: string }> = {
  markdown: { icon: FileText, label: "MD" },
  html: { icon: Code, label: "HTML" },
  links: { icon: Link2, label: "Links" },
  screenshot: { icon: Camera, label: "SS" },
  structured_data: { icon: Braces, label: "JSON" },
  headings: { icon: List, label: "Sum" },
  images: { icon: ImageIcon, label: "Img" },
};

async function handleDownload(job: any) {
  try {
    switch (job.type) {
      case "scrape": await api.downloadScrapeExport(job.id, "json"); break;
      case "crawl": await api.downloadCrawlExport(job.id, "json"); break;
      case "search": await api.downloadSearchExport(job.id, "json"); break;
      case "map": await api.downloadMapExport(job.id, "json"); break;
      case "batch": await api.downloadBatchExport(job.id, "json"); break;
    }
  } catch {}
}

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState("markdown");
  const [showFormatDropdown, setShowFormatDropdown] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (!token) { router.push("/auth/login"); return; }
    api.getMe().then(setUser).catch(() => router.push("/auth/login"));
    api.getUsageHistory({ per_page: 9 })
      .then((res) => { setRecentJobs(res.jobs || []); setJobsLoaded(true); })
      .catch(() => setJobsLoaded(true));
  }, [router]);

  const handleScrape = async () => {
    if (!url.trim()) return;
    setLoading(true);
    try {
      const fullUrl = url.startsWith("http") ? url : `https://${url}`;
      const res = await api.scrape({ url: fullUrl, formats: [selectedFormat], only_main_content: true });
      if (res.job_id) router.push(`/scrape/${res.job_id}`);
      else router.push("/playground?endpoint=scrape");
    } catch {
      router.push("/playground?endpoint=scrape");
    } finally {
      setLoading(false);
    }
  };

  const handleGetCode = () => {
    const fullUrl = url.startsWith("http") ? url : `https://${url}`;
    const code = `curl -X POST ${window.location.origin}/v1/scrape \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url": "${fullUrl || "https://example.com"}", "formats": ["${selectedFormat}"]}'`;
    navigator.clipboard.writeText(code);
  };

  if (!user) return null;

  const hasRuns = recentJobs.length > 0;

  return (
    <SidebarProvider>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background">
          <MobileMenuButton />
          <div className="min-h-screen flex flex-col">
            <div className={cn(
              "flex-1 flex flex-col max-w-6xl mx-auto w-full px-6 lg:px-8 transition-all duration-500",
              !hasRuns && jobsLoaded ? "justify-center" : "pt-6"
            )}>
              {/* Mode Switcher */}
              <div className={cn("animate-float-in", hasRuns ? "pb-8" : "pb-10")}>
                <ModeSwitcher />
              </div>

              {/* URL Input */}
              <section className={cn("max-w-2xl mx-auto w-full animate-float-in", hasRuns ? "mb-10" : "mb-6")} style={{ animationDelay: "0.05s" }}>
                <div className="rounded-2xl border border-primary/15 bg-card/80 backdrop-blur-sm p-5 shadow-xl shadow-primary/5">
                  <div className="flex items-center gap-0 rounded-xl bg-background border border-border/50 px-5 h-14 mb-4 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/25 transition-all">
                    <span className="text-base text-muted-foreground shrink-0 select-none font-mono">https://</span>
                    <input
                      type="text" value={url} onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !loading && handleScrape()}
                      placeholder="example.com"
                      className="flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground/50 ml-1"
                    />
                    <Crosshair className="h-5 w-5 text-primary/40 shrink-0 ml-2" />
                  </div>

                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <button onClick={() => router.push("/playground?endpoint=scrape")} className="h-10 w-10 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="Advanced settings">
                        <SlidersHorizontal className="h-[18px] w-[18px]" />
                      </button>
                      <button onClick={() => router.push("/playground?endpoint=batch")} className="h-10 w-10 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="Batch mode">
                        <Boxes className="h-[18px] w-[18px]" />
                      </button>
                      <button onClick={() => router.push("/docs")} className="h-10 w-10 rounded-lg bg-muted/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all" title="API Docs">
                        <FileCode className="h-[18px] w-[18px]" />
                      </button>

                      <div className="relative">
                        <button onClick={() => setShowFormatDropdown(!showFormatDropdown)} className="flex items-center gap-2 h-10 rounded-lg bg-muted/60 px-3.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all">
                          <FileText className="h-[18px] w-[18px]" />
                          <span>{selectedFormat.charAt(0).toUpperCase() + selectedFormat.slice(1)}</span>
                          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
                        </button>
                        {showFormatDropdown && (
                          <div className="absolute top-12 left-0 z-50 w-48 rounded-xl border border-border/60 bg-card shadow-xl p-1.5 animate-scale-in">
                            {["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"].map((fmt) => (
                              <button key={fmt} onClick={() => { setSelectedFormat(fmt); setShowFormatDropdown(false); }} className={cn("flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm transition-all", selectedFormat === fmt ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground")}>
                                {(() => { const FIcon = formatIcons[fmt]?.icon; return FIcon ? <FIcon className="h-4 w-4" /> : null; })()}
                                {fmt.charAt(0).toUpperCase() + fmt.slice(1).replace("_", " ")}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <button onClick={handleGetCode} className="flex items-center gap-2 h-10 rounded-lg px-4 text-sm font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted/50 transition-all">
                        <Code className="h-[18px] w-[18px]" />
                        <span className="hidden sm:inline">Get code</span>
                      </button>
                      <button onClick={handleScrape} disabled={loading || !url.trim()} className="flex items-center gap-2 h-11 rounded-lg px-6 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/15">
                        {loading ? <Loader2 className="h-[18px] w-[18px] animate-spin" /> : <>Start scraping</>}
                      </button>
                    </div>
                  </div>
                </div>
              </section>

              {/* Recent Runs */}
              {hasRuns && (
                <section className="animate-float-in" style={{ animationDelay: "0.1s" }}>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <h2 className="text-xl font-bold tracking-tight">Recent Runs</h2>
                      <div className="h-px flex-1 bg-gradient-to-r from-border to-transparent min-w-[40px]" />
                    </div>
                    <Link href="/jobs" className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 font-medium">
                      View all <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 stagger-children">
                    {recentJobs.map((job) => {
                      const jobUrl = getJobUrl(job);
                      const domain = getDomain(jobUrl);
                      const TypeIcon = getTypeIcon(job.type);
                      const { date, time } = job.created_at ? formatDate(job.created_at) : { date: "", time: "" };
                      const jobFormats: string[] = job.config?.formats || [];
                      const isCompleted = job.status === "completed";

                      return (
                        <div key={job.id} className="rounded-xl border border-border/50 bg-card/70 hover:bg-card transition-all duration-200 group overflow-hidden">
                          <div className="h-[2px] bg-primary" />
                          <Link href={getJobDetailPath(job)}>
                            <div className="flex items-center justify-between px-5 pt-4 pb-3">
                              <div className="flex items-center gap-2.5 min-w-0">
                                {jobUrl && !jobUrl.includes("URLs") && (
                                  <img src={getFavicon(jobUrl)} alt="" className="h-5 w-5 rounded-sm shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                                )}
                                <span className="text-base font-semibold truncate">{domain || "No URL"}</span>
                              </div>
                              <ExternalLink className="h-4 w-4 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors shrink-0" />
                            </div>
                            <div className="px-5 pb-4 space-y-2.5">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <TypeIcon className="h-[18px] w-[18px] text-primary" />
                                  <span className="text-[13px] font-bold uppercase tracking-wider text-primary">{job.type}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className={cn("h-2 w-2 rounded-full", job.status === "completed" ? "bg-emerald-400" : job.status === "failed" ? "bg-red-400" : job.status === "running" ? "bg-amber-400 animate-pulse" : "bg-muted-foreground")} />
                                  <span className="text-[13px] font-medium text-muted-foreground capitalize">{job.status === "completed" ? "Done" : job.status}</span>
                                </div>
                              </div>
                              <div className="flex items-center gap-2 text-muted-foreground">
                                <Clock className="h-4 w-4" />
                                <span className="text-[13px] font-medium">{date} {time}</span>
                              </div>
                              {jobFormats.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pt-0.5">
                                  {jobFormats.slice(0, 4).map((fmt: string) => {
                                    const fmtInfo = formatIcons[fmt];
                                    const FmtIcon = fmtInfo?.icon || FileText;
                                    return (<span key={fmt} className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider"><FmtIcon className="h-3 w-3" /> {fmtInfo?.label || fmt}</span>);
                                  })}
                                </div>
                              )}
                            </div>
                          </Link>
                          {isCompleted && (
                            <div className="px-5 pb-4 pt-0">
                              <button onClick={(e) => { e.preventDefault(); handleDownload(job); }} className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-bold transition-all border border-primary/20 text-primary hover:bg-primary/10">
                                <Download className="h-[18px] w-[18px]" /> Download JSON
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {!hasRuns && jobsLoaded && (
                <div className="text-center py-4 animate-fade-in">
                  <p className="text-base text-muted-foreground font-medium">Your runs will appear here</p>
                </div>
              )}
            </div>
            <Footer />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
