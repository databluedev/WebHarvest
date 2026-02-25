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
    description: "Product listings with prices, merchants, ratings, and filters",
    icon: ShoppingCart,
    accent: "amber",
    status: "active",
  },
  {
    id: "google-maps",
    name: "Google Maps",
    endpoint: "/v1/data/google/maps",
    description: "Business listings with addresses, ratings, reviews, and coordinates",
    icon: MapPin,
    accent: "emerald",
    status: "active",
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

  // Shared tryout state
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Google Search state
  const [query, setQuery] = useState("");
  const [numResults, setNumResults] = useState(10);
  const [language, setLanguage] = useState("en");
  const [country, setCountry] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [safeSearch, setSafeSearch] = useState(false);

  // Google Shopping state
  const [shopQuery, setShopQuery] = useState("");
  const [shopNumResults, setShopNumResults] = useState(10);
  const [shopLanguage, setShopLanguage] = useState("en");
  const [shopCountry, setShopCountry] = useState("");
  const [shopSortBy, setShopSortBy] = useState("");
  const [shopMinRating, setShopMinRating] = useState(0);

  // Google Maps state
  const [mapsQuery, setMapsQuery] = useState("");
  const [mapsCoordinates, setMapsCoordinates] = useState("");
  const [mapsPlaceId, setMapsPlaceId] = useState("");
  const [mapsCid, setMapsCid] = useState("");
  const [mapsType, setMapsType] = useState("");
  const [mapsLanguage, setMapsLanguage] = useState("en");
  const [mapsNumResults, setMapsNumResults] = useState(20);
  const [mapsSortBy, setMapsSortBy] = useState("");

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

  const handleGoogleShopping = async () => {
    if (!shopQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleShopping({
        query: shopQuery.trim(),
        num_results: shopNumResults,
        language: shopLanguage,
        ...(shopCountry && { country: shopCountry }),
        ...(shopSortBy && { sort_by: shopSortBy }),
        ...(shopMinRating > 0 && { min_rating: shopMinRating }),
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleMaps = async () => {
    if (!mapsQuery.trim() && !mapsCoordinates.trim() && !mapsPlaceId.trim() && !mapsCid.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleMaps({
        ...(mapsQuery && { query: mapsQuery.trim() }),
        ...(mapsCoordinates && { coordinates: mapsCoordinates.trim() }),
        ...(mapsPlaceId && { place_id: mapsPlaceId.trim() }),
        ...(mapsCid && { cid: mapsCid.trim() }),
        ...(mapsType && { type: mapsType }),
        language: mapsLanguage,
        num_results: mapsNumResults,
        ...(mapsSortBy && { sort_by: mapsSortBy }),
        include_reviews: true,
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

            {/* ── TRYOUT PANEL: Google Shopping ── */}
            {activePanel === "google-shopping" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                {/* Panel header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-amber-500/20 grid place-items-center">
                      <ShoppingCart className="h-4 w-4 text-amber-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Shopping API</h3>
                      <code className="text-[11px] text-amber-400/60 font-mono">POST /v1/data/google/shopping</code>
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
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Product Search *</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={shopQuery}
                          onChange={(e) => setShopQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleShopping()}
                          placeholder="e.g. wireless headphones noise cancelling"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-amber-500/40 transition-colors"
                        />
                        <ShoppingCart className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    {/* Sort + Results */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Sort By</label>
                        <div className="relative">
                          <select
                            value={shopSortBy}
                            onChange={(e) => setShopSortBy(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-amber-500/40 transition-colors"
                          >
                            <option value="">Relevance</option>
                            <option value="price_low">Price: Low → High</option>
                            <option value="price_high">Price: High → Low</option>
                            <option value="rating">Rating</option>
                            <option value="reviews">Reviews</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select
                            value={shopNumResults}
                            onChange={(e) => setShopNumResults(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-amber-500/40 transition-colors"
                          >
                            {[5, 10, 20, 30, 50, 75, 100].map((n) => (
                              <option key={n} value={n}>{n}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Minimum Rating */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Minimum Rating</label>
                      <div className="flex gap-2">
                        {[0, 1, 2, 3, 4].map((r) => (
                          <button
                            key={r}
                            onClick={() => setShopMinRating(r)}
                            className={`px-3 py-2 text-[12px] font-mono border transition-colors ${
                              shopMinRating === r
                                ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
                                : "border-white/10 text-white/30 hover:text-white/60"
                            }`}
                          >
                            {r === 0 ? "Any" : `${r}★+`}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Country */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Country</label>
                      <div className="relative">
                        <select
                          value={shopCountry}
                          onChange={(e) => setShopCountry(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-amber-500/40 transition-colors"
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
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                      </div>
                    </div>

                    {/* Submit button */}
                    <button
                      onClick={handleGoogleShopping}
                      disabled={loading || !shopQuery.trim()}
                      className="w-full border border-amber-500/40 bg-amber-500/10 text-amber-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-amber-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching Products...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search Products
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
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Products</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.products?.length || 0} products &middot; {result.time_taken?.toFixed(2)}s
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
                          <ShoppingCart className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search for products to see results</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-amber-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching product listings...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Filters applied badge */}
                        {result.filters_applied && Object.keys(result.filters_applied).length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(result.filters_applied).map(([k, v]: [string, any]) => (
                              <span key={k} className="text-[10px] font-mono border border-amber-500/20 bg-amber-500/5 text-amber-400 px-2 py-1">
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Product cards */}
                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.products?.map((product: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-4 hover:border-white/[0.08] transition-colors">
                              <div className="flex gap-4">
                                {/* Product image */}
                                {product.image_url && (
                                  <div className="flex-shrink-0 h-16 w-16 border border-white/[0.06] bg-white/[0.02] grid place-items-center overflow-hidden">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src={product.image_url} alt={product.title} className="h-full w-full object-contain" />
                                  </div>
                                )}

                                <div className="min-w-0 flex-1">
                                  {/* Title + position */}
                                  <div className="flex items-start justify-between gap-2 mb-1">
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center gap-2 mb-0.5">
                                        <span className="text-[10px] text-white/20 font-mono">#{product.position}</span>
                                        {product.badge && (
                                          <span className="text-[9px] uppercase tracking-wider text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 font-mono">
                                            {product.badge}
                                          </span>
                                        )}
                                      </div>
                                      <a href={product.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-white/80 font-mono hover:text-amber-400 transition-colors line-clamp-2">
                                        {product.title}
                                      </a>
                                    </div>
                                    <a href={product.url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0 mt-1">
                                      <ExternalLink className="h-3.5 w-3.5" />
                                    </a>
                                  </div>

                                  {/* Price row */}
                                  <div className="flex items-center gap-3 mb-1">
                                    {product.price && (
                                      <span className="text-[15px] font-bold text-amber-400 font-mono">{product.price}</span>
                                    )}
                                    {product.original_price && (
                                      <span className="text-[12px] text-white/25 font-mono line-through">{product.original_price}</span>
                                    )}
                                  </div>

                                  {/* Merchant + Rating + Shipping */}
                                  <div className="flex items-center gap-3 flex-wrap">
                                    {product.merchant && (
                                      <span className="text-[11px] text-white/40 font-mono">{product.merchant}</span>
                                    )}
                                    {product.rating != null && (
                                      <span className="text-[11px] text-amber-400/70 font-mono flex items-center gap-1">
                                        {"★".repeat(Math.round(product.rating))}{"☆".repeat(5 - Math.round(product.rating))}
                                        <span className="text-white/30">{product.rating}</span>
                                        {product.review_count != null && (
                                          <span className="text-white/20">({product.review_count.toLocaleString()})</span>
                                        )}
                                      </span>
                                    )}
                                    {product.shipping && (
                                      <span className={`text-[10px] font-mono ${product.shipping.toLowerCase().includes("free") ? "text-emerald-400/60" : "text-white/25"}`}>
                                        {product.shipping}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Related searches */}
                        {result.related_searches && result.related_searches.length > 0 && (
                          <div className="border border-white/[0.06] p-4">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-white/30 font-mono mb-3">Related Searches</div>
                            <div className="flex flex-wrap gap-2">
                              {result.related_searches.map((rs: any, i: number) => (
                                <button
                                  key={i}
                                  onClick={() => setShopQuery(rs.query)}
                                  className="text-[11px] text-white/40 font-mono border border-white/[0.08] px-3 py-1.5 hover:text-amber-400 hover:border-amber-500/20 transition-colors"
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

            {/* ── TRYOUT PANEL: Google Maps ── */}
            {activePanel === "google-maps" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                {/* Panel header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-emerald-500/20 grid place-items-center">
                      <MapPin className="h-4 w-4 text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Maps API</h3>
                      <code className="text-[11px] text-emerald-400/60 font-mono">POST /v1/data/google/maps</code>
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

                    {/* Search Query */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Search Query</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={mapsQuery}
                          onChange={(e) => setMapsQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleMaps()}
                          placeholder="e.g. restaurants near Times Square"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/40 transition-colors"
                        />
                        <MapPin className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    {/* Coordinates + Type */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">GPS Coordinates</label>
                        <input
                          type="text"
                          value={mapsCoordinates}
                          onChange={(e) => setMapsCoordinates(e.target.value)}
                          placeholder="40.7580,-73.9855"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/40 transition-colors"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Place Type</label>
                        <div className="relative">
                          <select
                            value={mapsType}
                            onChange={(e) => setMapsType(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-emerald-500/40 transition-colors"
                          >
                            <option value="">Any</option>
                            <option value="restaurant">Restaurant</option>
                            <option value="hotel">Hotel</option>
                            <option value="cafe">Cafe</option>
                            <option value="bar">Bar</option>
                            <option value="hospital">Hospital</option>
                            <option value="pharmacy">Pharmacy</option>
                            <option value="gas_station">Gas Station</option>
                            <option value="gym">Gym</option>
                            <option value="bank">Bank</option>
                            <option value="supermarket">Supermarket</option>
                            <option value="park">Park</option>
                            <option value="museum">Museum</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Place ID + CID (for detail lookups) */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Place ID</label>
                        <input
                          type="text"
                          value={mapsPlaceId}
                          onChange={(e) => setMapsPlaceId(e.target.value)}
                          placeholder="ChIJN1t_tDeuEmsR..."
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/40 transition-colors"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">CID / Ludocid</label>
                        <input
                          type="text"
                          value={mapsCid}
                          onChange={(e) => setMapsCid(e.target.value)}
                          placeholder="0x89c25090:0x40c6a577..."
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-emerald-500/40 transition-colors"
                        />
                      </div>
                    </div>

                    {/* Results + Sort By */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select
                            value={mapsNumResults}
                            onChange={(e) => setMapsNumResults(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-emerald-500/40 transition-colors"
                          >
                            {[10, 20, 40, 60, 80, 100, 150, 200].map((n) => (
                              <option key={n} value={n}>{n}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Sort By</label>
                        <div className="relative">
                          <select
                            value={mapsSortBy}
                            onChange={(e) => setMapsSortBy(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-emerald-500/40 transition-colors"
                          >
                            <option value="">Relevance</option>
                            <option value="rating">Rating</option>
                            <option value="reviews">Reviews</option>
                            <option value="distance">Distance</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Submit button */}
                    <button
                      onClick={handleGoogleMaps}
                      disabled={loading || (!mapsQuery.trim() && !mapsCoordinates.trim() && !mapsPlaceId.trim() && !mapsCid.trim())}
                      className="w-full border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-emerald-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching Places...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search Places
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
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Places</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.places?.length || 0} places &middot; {result.time_taken?.toFixed(2)}s
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
                          <MapPin className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search for places to see results</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-emerald-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching places from Google Maps...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Filters applied badge */}
                        {result.filters_applied && Object.keys(result.filters_applied).length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(result.filters_applied).map(([k, v]: [string, any]) => (
                              <span key={k} className="text-[10px] font-mono border border-emerald-500/20 bg-emerald-500/5 text-emerald-400 px-2 py-1">
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Place cards */}
                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.places?.map((place: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-4 hover:border-white/[0.08] transition-colors">
                              <div className="flex gap-4">
                                {/* Thumbnail */}
                                {place.thumbnail && (
                                  <div className="flex-shrink-0 h-16 w-16 border border-white/[0.06] bg-white/[0.02] grid place-items-center overflow-hidden">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src={place.thumbnail} alt={place.title} className="h-full w-full object-cover" />
                                  </div>
                                )}

                                <div className="min-w-0 flex-1">
                                  {/* Title + position */}
                                  <div className="flex items-start justify-between gap-2 mb-1">
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center gap-2 mb-0.5">
                                        <span className="text-[10px] text-white/20 font-mono">#{place.position}</span>
                                        {place.type && (
                                          <span className="text-[9px] uppercase tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 font-mono">
                                            {place.type}
                                          </span>
                                        )}
                                        {place.price_level_text && (
                                          <span className="text-[10px] text-white/30 font-mono">{place.price_level_text}</span>
                                        )}
                                      </div>
                                      <a href={place.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-white/80 font-mono hover:text-emerald-400 transition-colors line-clamp-2">
                                        {place.title}
                                      </a>
                                    </div>
                                    <a href={place.url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0 mt-1">
                                      <ExternalLink className="h-3.5 w-3.5" />
                                    </a>
                                  </div>

                                  {/* Rating + Address */}
                                  <div className="flex items-center gap-3 flex-wrap mb-1">
                                    {place.rating != null && (
                                      <span className="text-[11px] text-emerald-400/70 font-mono flex items-center gap-1">
                                        {"★".repeat(Math.round(place.rating))}{"☆".repeat(5 - Math.round(place.rating))}
                                        <span className="text-white/30">{place.rating}</span>
                                        {place.review_count != null && (
                                          <span className="text-white/20">({place.review_count.toLocaleString()})</span>
                                        )}
                                      </span>
                                    )}
                                    {place.open_now != null && (
                                      <span className={`text-[10px] font-mono ${place.open_now ? "text-emerald-400/60" : "text-red-400/60"}`}>
                                        {place.open_now ? "Open" : "Closed"}
                                      </span>
                                    )}
                                  </div>

                                  {/* Address + Phone + Website */}
                                  <div className="flex items-center gap-3 flex-wrap">
                                    {place.address && (
                                      <span className="text-[11px] text-white/30 font-mono">{place.address}</span>
                                    )}
                                    {place.phone && (
                                      <span className="text-[11px] text-white/25 font-mono">{place.phone}</span>
                                    )}
                                  </div>

                                  {/* Attributes */}
                                  {place.attributes && place.attributes.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {place.attributes.map((attr: string, j: number) => (
                                        <span key={j} className="text-[9px] text-white/20 font-mono border border-white/[0.06] px-1.5 py-0.5">
                                          {attr}
                                        </span>
                                      ))}
                                    </div>
                                  )}

                                  {/* Reviews */}
                                  {place.user_reviews && place.user_reviews.length > 0 && (
                                    <div className="mt-2 space-y-1">
                                      {place.user_reviews.slice(0, 2).map((review: any, j: number) => (
                                        <div key={j} className="text-[11px] text-white/20 font-mono border-l border-white/[0.06] pl-2">
                                          <span className="text-white/30">{review.author_name}</span>
                                          {review.rating && <span className="text-emerald-400/50 ml-1">{"★".repeat(review.rating)}</span>}
                                          {review.text && <span className="ml-1">{review.text.slice(0, 80)}...</span>}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

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
