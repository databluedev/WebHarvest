"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Search,
  ShoppingCart,
  MapPin,
  Newspaper,
  Briefcase,
  Package,
  Linkedin,
  Menu,
  Lock,
  Play,
  Loader2,
  ChevronDown,
  X,
  ExternalLink,
  Copy,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";

type ApiStatus = "active" | "coming-soon";

const SCRAPER_APIS: Array<{
  id: string;
  name: string;
  endpoint: string;
  description: string;
  icon: typeof Search;
  accent: string;
  status: ApiStatus;
}> = [
  {
    id: "google-search",
    name: "Google Search",
    endpoint: "/v1/data/google/search",
    description: "Search results with titles, links, snippets, and positions",
    icon: Search,
    accent: "cyan",
    status: "active",
  },
  {
    id: "google-shopping",
    name: "Google Shopping",
    endpoint: "/v1/data/google/shopping",
    description: "Product listings with prices, merchants, and ratings",
    icon: ShoppingCart,
    accent: "amber",
    status: "coming-soon",
  },
  {
    id: "google-maps",
    name: "Google Maps",
    endpoint: "/v1/data/google/maps",
    description: "Business listings with addresses, ratings, reviews, and coordinates",
    icon: MapPin,
    accent: "emerald",
    status: "coming-soon",
  },
  {
    id: "google-news",
    name: "Google News",
    endpoint: "/v1/data/google/news",
    description: "News articles with sources, dates, and snippets",
    icon: Newspaper,
    accent: "violet",
    status: "coming-soon",
  },
  {
    id: "google-jobs",
    name: "Google Jobs",
    endpoint: "/v1/data/google/jobs",
    description: "Job listings with company, location, salary, and requirements",
    icon: Briefcase,
    accent: "pink",
    status: "coming-soon",
  },
  {
    id: "amazon-product",
    name: "Amazon Product",
    endpoint: "/v1/data/amazon/product",
    description: "Product details with pricing, reviews, images, and ASIN data",
    icon: Package,
    accent: "amber",
    status: "coming-soon",
  },
  {
    id: "linkedin-profile",
    name: "LinkedIn Profile",
    endpoint: "/v1/data/linkedin/profile",
    description: "Professional profiles with experience, education, and skills",
    icon: Linkedin,
    accent: "cyan",
    status: "coming-soon",
  },
];

const ACCENT_MAP: Record<string, { text: string; border: string; bg: string }> = {
  cyan: { text: "text-cyan-400", border: "border-cyan-500/20", bg: "bg-cyan-500/10" },
  amber: { text: "text-amber-400", border: "border-amber-500/20", bg: "bg-amber-500/10" },
  emerald: { text: "text-emerald-400", border: "border-emerald-500/20", bg: "bg-emerald-500/10" },
  violet: { text: "text-violet-400", border: "border-violet-500/20", bg: "bg-violet-500/10" },
  pink: { text: "text-pink-400", border: "border-pink-500/20", bg: "bg-pink-500/10" },
};

const TICKER_ITEMS = [
  { label: "TOTAL_APIS", value: String(SCRAPER_APIS.length), color: "text-cyan-400" },
  { label: "ACTIVE", value: String(SCRAPER_APIS.filter((a) => a.status === "active").length), color: "text-emerald-400" },
  { label: "COMING_SOON", value: String(SCRAPER_APIS.filter((a) => a.status === "coming-soon").length), color: "text-amber-400" },
  { label: "STRUCTURED_OUTPUT", value: "JSON", color: "text-violet-400" },
  { label: "ANTI_BOT", value: "ACTIVE", color: "text-pink-400" },
  { label: "PROXY_ROTATION", value: "ENABLED", color: "text-emerald-400" },
  { label: "RATE_LIMIT", value: "MANAGED", color: "text-cyan-400" },
  { label: "RESPONSE_FORMAT", value: "NORMALIZED", color: "text-amber-400" },
];

export default function ScrapperPoolPage() {
  const [mobileNav, setMobileNav] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);

  // Google Search tryout state
  const [query, setQuery] = useState("");
  const [numResults, setNumResults] = useState(10);
  const [language, setLanguage] = useState("en");
  const [country, setCountry] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [safeSearch, setSafeSearch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const handleCardClick = (apiId: string, status: ApiStatus) => {
    if (status !== "active") return;
    if (activePanel === apiId) {
      setActivePanel(null);
    } else {
      setActivePanel(apiId);
      setTimeout(() => panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    }
  };

  const handleGoogleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleSearch({
        query: query.trim(),
        num_results: numResults,
        language,
        ...(country && { country }),
        ...(timeRange && { time_range: timeRange }),
        safe_search: safeSearch,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyResult = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    if (!activePanel) {
      setResult(null);
      setError(null);
    }
  }, [activePanel]);

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      {/* ═══ NAV ═══ */}
      <nav className="relative fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-[#050505]/95 backdrop-blur-sm">
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-emerald-500 via-cyan-500 to-violet-500" />
        <div className="flex items-center justify-between px-6 md:px-10 h-16">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-4 w-4 bg-gradient-to-br from-emerald-400 to-cyan-500" />
            <span className="text-[18px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
          </Link>
          <div className="hidden md:flex items-center gap-10">
            <Link href="/dashboard" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">Dashboard</Link>
            <Link href="/playground" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">Playground</Link>
            <span className="text-[12px] uppercase tracking-[0.2em] text-white border-b border-white/40 pb-0.5 font-mono cursor-default">Scrapper Pool</span>
            <Link href="/docs" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">API Docs</Link>
            <Link href="/jobs" className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">Jobs</Link>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden sm:flex text-[11px] text-white/40 items-center gap-1.5 font-mono">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              ONLINE
            </span>
            <Link href="/settings" className="hidden sm:block border border-white/20 px-5 py-2 text-[12px] uppercase tracking-[0.15em] hover:bg-white hover:text-black transition-all font-mono">Settings</Link>
            <button onClick={() => setMobileNav(!mobileNav)} className="md:hidden h-10 w-10 grid place-items-center text-white/60"><Menu className="h-5 w-5" /></button>
          </div>
        </div>
        {mobileNav && (
          <div className="md:hidden border-t border-white/10 bg-[#050505] px-6 py-4 space-y-3">
            <Link href="/dashboard" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Dashboard</Link>
            <Link href="/playground" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Playground</Link>
            <span className="block text-[12px] uppercase tracking-[0.2em] text-white font-mono py-2">Scrapper Pool</span>
            <Link href="/docs" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">API Docs</Link>
            <Link href="/jobs" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Jobs</Link>
            <Link href="/settings" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Settings</Link>
          </div>
        )}
      </nav>

      {/* ═══ TICKER ═══ */}
      <div className="mt-16 border-b border-white/[0.06] bg-[#050505] overflow-hidden h-8 flex items-center">
        <div className="flex whitespace-nowrap animate-ticker">
          {[0, 1].map((dup) => (
            <div key={dup} className="flex">
              {TICKER_ITEMS.map((item, i) => (
                <span key={`${dup}-${i}`} className="text-[11px] tracking-wider mx-8 text-white/30 font-mono">
                  {item.label} <span className={item.color}>{item.value}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <main>
        {/* Grid bg */}
        <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />

        {/* ── HERO ── */}
        <section className="px-6 md:px-10 pt-16 pb-12 border-b border-white/[0.06]">
          <div className="max-w-[1400px] mx-auto">
            <div className="flex flex-col lg:flex-row items-start justify-between gap-10 lg:gap-0">
              <div>
                <div className="inline-block border border-cyan-500 text-cyan-400 text-[11px] uppercase tracking-[0.25em] px-4 py-1.5 mb-8 font-mono">Data APIs</div>
                <h1 className="font-display text-[48px] md:text-[72px] leading-[0.9] tracking-[-3px] uppercase mb-6">
                  <span className="animate-gradient-text-blue">SCRAPPER</span><br />
                  <span className="text-white/30">POOL.</span>
                </h1>
                <p className="text-[16px] text-white/50 max-w-[500px] leading-[1.8] border-l-2 border-cyan-500/40 pl-6 font-mono">
                  Domain-specific scraping APIs. Structured JSON output from any platform — Google, Amazon, LinkedIn, and more.
                </p>
              </div>

              {/* Stats panel */}
              <div className="border border-white/10 w-full lg:w-auto lg:min-w-[280px]">
                <div className="text-[10px] uppercase tracking-[0.3em] text-white/40 px-6 py-3 border-b border-white/[0.06] font-mono">Status</div>
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
                  <span className="text-[12px] text-white/40 font-mono uppercase tracking-[0.1em]">Total APIs</span>
                  <span className="text-[20px] font-bold font-mono">{SCRAPER_APIS.length}</span>
                </div>
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
                  <span className="text-[12px] text-white/40 font-mono uppercase tracking-[0.1em]">Active</span>
                  <span className="text-[20px] font-bold font-mono text-emerald-400">{SCRAPER_APIS.filter((a) => a.status === "active").length}</span>
                </div>
                <div className="px-6 py-4 flex items-center justify-between">
                  <span className="text-[12px] text-white/40 font-mono uppercase tracking-[0.1em]">Coming Soon</span>
                  <span className="text-[20px] font-bold font-mono text-amber-400">{SCRAPER_APIS.filter((a) => a.status === "coming-soon").length}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── API CARDS ── */}
        <section className="px-6 md:px-10 py-16 relative z-10">
          <div className="max-w-[1400px] mx-auto">
            <div className="flex items-center justify-between mb-10">
              <div>
                <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono mb-2">Available Endpoints</div>
                <h2 className="text-[24px] font-bold uppercase tracking-[-1px]">Domain APIs</h2>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[1px] bg-white/[0.06]">
              {SCRAPER_APIS.map((scraperApi) => {
                const Icon = scraperApi.icon;
                const colors = ACCENT_MAP[scraperApi.accent];
                const isActive = scraperApi.status === "active";
                const isOpen = activePanel === scraperApi.id;

                return (
                  <div
                    key={scraperApi.id}
                    onClick={() => handleCardClick(scraperApi.id, scraperApi.status)}
                    className={`bg-[#050505] p-8 group transition-colors relative ${
                      isActive ? "cursor-pointer hover:bg-white/[0.02]" : ""
                    } ${isOpen ? "bg-white/[0.03] border-l-2 border-l-cyan-500" : ""}`}
                  >
                    {/* Status badge */}
                    <div className="absolute top-6 right-6">
                      {isActive ? (
                        <span className="text-[10px] uppercase tracking-[0.2em] text-emerald-400 font-mono flex items-center gap-1.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                          Active
                        </span>
                      ) : (
                        <span className="text-[10px] uppercase tracking-[0.2em] text-white/25 font-mono flex items-center gap-1.5">
                          <Lock className="h-3 w-3" />
                          Soon
                        </span>
                      )}
                    </div>

                    {/* Icon */}
                    <div className={`h-10 w-10 border ${colors.border} grid place-items-center mb-6`}>
                      <Icon className={`h-5 w-5 ${colors.text}`} />
                    </div>

                    {/* Name */}
                    <h3 className="text-[16px] font-bold uppercase tracking-[0.05em] mb-2 font-mono">{scraperApi.name}</h3>

                    {/* Description */}
                    <p className="text-[13px] text-white/40 leading-[1.7] mb-6 font-mono">{scraperApi.description}</p>

                    {/* Endpoint + Try It */}
                    <div className="border-t border-white/[0.06] pt-4 flex items-center justify-between">
                      <code className={`text-[11px] ${colors.text} font-mono tracking-wider`}>
                        {scraperApi.endpoint}
                      </code>
                      {isActive && (
                        <span className={`text-[10px] uppercase tracking-[0.2em] font-mono flex items-center gap-1.5 ${isOpen ? "text-cyan-400" : "text-white/30 group-hover:text-white/60"} transition-colors`}>
                          <Play className="h-3 w-3" />
                          {isOpen ? "Close" : "Try it"}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ── TRYOUT PANEL: Google Search ── */}
            {activePanel === "google-search" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                {/* Panel header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-cyan-500/20 grid place-items-center">
                      <Search className="h-4 w-4 text-cyan-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Search API</h3>
                      <code className="text-[11px] text-cyan-400/60 font-mono">POST /v1/data/google/search</code>
                    </div>
                  </div>
                  <button onClick={() => setActivePanel(null)} className="h-8 w-8 grid place-items-center text-white/30 hover:text-white transition-colors">
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
                  {/* Left: Input form */}
                  <div className="p-6 space-y-5">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono mb-4">Request Parameters</div>

                    {/* Query input */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Query *</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleSearch()}
                          placeholder="e.g. best web scraping tools 2026"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-cyan-500/40 transition-colors"
                        />
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    {/* Parameters row */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select
                            value={numResults}
                            onChange={(e) => setNumResults(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-cyan-500/40 transition-colors"
                          >
                            {[5, 10, 20, 30, 50, 75, 100].map((n) => (
                              <option key={n} value={n}>{n}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Language</label>
                        <div className="relative">
                          <select
                            value={language}
                            onChange={(e) => setLanguage(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-cyan-500/40 transition-colors"
                          >
                            <option value="en">English</option>
                            <option value="es">Spanish</option>
                            <option value="fr">French</option>
                            <option value="de">German</option>
                            <option value="pt">Portuguese</option>
                            <option value="ja">Japanese</option>
                            <option value="ko">Korean</option>
                            <option value="zh">Chinese</option>
                            <option value="ar">Arabic</option>
                            <option value="hi">Hindi</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Country</label>
                        <div className="relative">
                          <select
                            value={country}
                            onChange={(e) => setCountry(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-cyan-500/40 transition-colors"
                          >
                            <option value="">Any</option>
                            <option value="us">United States</option>
                            <option value="gb">United Kingdom</option>
                            <option value="ca">Canada</option>
                            <option value="au">Australia</option>
                            <option value="de">Germany</option>
                            <option value="fr">France</option>
                            <option value="in">India</option>
                            <option value="jp">Japan</option>
                            <option value="br">Brazil</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Time Range</label>
                        <div className="relative">
                          <select
                            value={timeRange}
                            onChange={(e) => setTimeRange(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-cyan-500/40 transition-colors"
                          >
                            <option value="">Any time</option>
                            <option value="hour">Past hour</option>
                            <option value="day">Past 24 hours</option>
                            <option value="week">Past week</option>
                            <option value="month">Past month</option>
                            <option value="year">Past year</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Safe search toggle */}
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setSafeSearch(!safeSearch)}
                        className={`h-5 w-9 rounded-full transition-colors relative ${safeSearch ? "bg-cyan-500" : "bg-white/10"}`}
                      >
                        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${safeSearch ? "left-[18px]" : "left-0.5"}`} />
                      </button>
                      <span className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono">Safe Search</span>
                    </div>

                    {/* Submit button */}
                    <button
                      onClick={handleGoogleSearch}
                      disabled={loading || !query.trim()}
                      className="w-full border border-cyan-500/40 bg-cyan-500/10 text-cyan-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-cyan-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Execute Search
                        </>
                      )}
                    </button>

                    {error && (
                      <div className="border border-red-500/20 bg-red-500/5 px-4 py-3 text-[12px] text-red-400 font-mono">
                        {error}
                      </div>
                    )}
                  </div>

                  {/* Right: Response */}
                  <div className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Response</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.organic_results?.length || 0} results &middot; {result.time_taken?.toFixed(2)}s
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Search className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Enter a query and hit Execute</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-cyan-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching search results...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Quick result cards */}
                        {result.featured_snippet && (
                          <div className="border border-violet-500/20 bg-violet-500/5 p-4">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-violet-400 font-mono mb-2">Featured Snippet</div>
                            <p className="text-[13px] text-white/70 font-mono leading-relaxed">{result.featured_snippet.content}</p>
                            <a href={result.featured_snippet.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-violet-400 font-mono mt-2 inline-flex items-center gap-1 hover:underline">
                              {result.featured_snippet.title} <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        )}

                        {/* Organic results */}
                        <div className="max-h-[500px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.organic_results?.map((item: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-4 hover:border-white/[0.08] transition-colors">
                              <div className="flex items-start justify-between gap-4">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] text-white/20 font-mono">#{item.position}</span>
                                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-cyan-400 font-mono hover:underline truncate block">
                                      {item.title}
                                    </a>
                                  </div>
                                  <p className="text-[11px] text-emerald-400/60 font-mono truncate mb-1">{item.displayed_url || item.url}</p>
                                  {item.snippet && (
                                    <p className="text-[12px] text-white/40 font-mono leading-relaxed">{item.snippet}</p>
                                  )}
                                </div>
                                <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0">
                                  <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* People also ask */}
                        {result.people_also_ask && result.people_also_ask.length > 0 && (
                          <div className="border border-white/[0.06] p-4">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-white/30 font-mono mb-3">People Also Ask</div>
                            <div className="space-y-2">
                              {result.people_also_ask.map((paa: any, i: number) => (
                                <div key={i} className="text-[12px] text-white/50 font-mono pl-3 border-l border-white/[0.06]">
                                  {paa.question}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Related searches */}
                        {result.related_searches && result.related_searches.length > 0 && (
                          <div className="border border-white/[0.06] p-4">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-white/30 font-mono mb-3">Related Searches</div>
                            <div className="flex flex-wrap gap-2">
                              {result.related_searches.map((rs: any, i: number) => (
                                <button
                                  key={i}
                                  onClick={() => { setQuery(rs.query); }}
                                  className="text-[11px] text-white/40 font-mono border border-white/[0.08] px-3 py-1.5 hover:text-cyan-400 hover:border-cyan-500/20 transition-colors"
                                >
                                  {rs.query}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Raw JSON toggle */}
                        <details className="border border-white/[0.06]">
                          <summary className="px-4 py-3 text-[10px] uppercase tracking-[0.2em] text-white/30 font-mono cursor-pointer hover:text-white/50 transition-colors">
                            Raw JSON Response
                          </summary>
                          <pre className="px-4 pb-4 text-[11px] text-white/50 font-mono overflow-x-auto max-h-[400px] overflow-y-auto leading-relaxed">
                            {JSON.stringify(result, null, 2)}
                          </pre>
                        </details>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-white/[0.06] relative z-10">
        <div className="flex flex-col md:flex-row items-center justify-between px-6 md:px-10 max-w-[1400px] mx-auto py-8 gap-4">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-3 w-3 bg-gradient-to-br from-emerald-400 to-cyan-500" />
            <span className="text-[14px] font-bold uppercase tracking-[0.1em] text-white/50 font-mono">WebHarvest</span>
          </Link>
          <div className="flex items-center gap-8">
            <Link href="/docs" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">Documentation</Link>
            <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">GitHub</a>
            <Link href="/docs" className="text-[11px] uppercase tracking-[0.2em] text-white/30 hover:text-white/60 transition-colors font-mono">API Reference</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
