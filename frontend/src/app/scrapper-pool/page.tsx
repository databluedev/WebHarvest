"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Search,
  ShoppingCart,
  MapPin,
  Newspaper,
  Briefcase,
  Image,
  Package,
  Linkedin,
  Plane,
  TrendingUp,
  Menu,
  Lock,
  Play,
  Loader2,
  ChevronDown,
  X,
  ExternalLink,
  Copy,
  Check,
  Clock,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";

type ApiStatus = "active" | "coming-soon";

type ScraperApi = {
  id: string;
  name: string;
  endpoint: string;
  description: string;
  icon: typeof Search;
  accent: string;
  status: ApiStatus;
  category: string;
};

const SCRAPER_APIS: ScraperApi[] = [
  {
    id: "google-search",
    name: "Google Search",
    endpoint: "/v1/data/google/search",
    description: "Search results with titles, links, snippets, and positions",
    icon: Search,
    accent: "cyan",
    status: "active",
    category: "google",
  },
  {
    id: "google-shopping",
    name: "Google Shopping",
    endpoint: "/v1/data/google/shopping",
    description: "Product listings with prices, merchants, ratings, and filters",
    icon: ShoppingCart,
    accent: "amber",
    status: "active",
    category: "google",
  },
  {
    id: "google-maps",
    name: "Google Maps",
    endpoint: "/v1/data/google/maps",
    description: "Business listings with addresses, ratings, reviews, and coordinates",
    icon: MapPin,
    accent: "emerald",
    status: "active",
    category: "google",
  },
  {
    id: "google-news",
    name: "Google News",
    endpoint: "/v1/data/google/news",
    description: "News articles with sources, dates, and snippets",
    icon: Newspaper,
    accent: "violet",
    status: "active",
    category: "google",
  },
  {
    id: "google-jobs",
    name: "Google Jobs",
    endpoint: "/v1/data/google/jobs",
    description: "Job listings with company, location, qualifications, and experience levels",
    icon: Briefcase,
    accent: "pink",
    status: "active",
    category: "google",
  },
  {
    id: "google-images",
    name: "Google Images",
    endpoint: "/v1/data/google/images",
    description: "Image results with full URLs, dimensions, thumbnails, and source pages",
    icon: Image,
    accent: "rose",
    status: "active",
    category: "google",
  },
  {
    id: "google-flights",
    name: "Google Flights",
    endpoint: "/v1/data/google/flights",
    description: "Flight search with prices, airlines, routes, stops, and aircraft details",
    icon: Plane,
    accent: "sky",
    status: "active",
    category: "google",
  },
  {
    id: "google-finance",
    name: "Google Finance",
    endpoint: "/v1/data/google/finance",
    description: "Market overview, stock quotes, price movements, and financial news",
    icon: TrendingUp,
    accent: "lime",
    status: "active",
    category: "google",
  },
  {
    id: "amazon-products",
    name: "Amazon Products",
    endpoint: "/v1/data/amazon/products",
    description: "Product search with pricing, ratings, reviews, badges, and ASIN data",
    icon: Package,
    accent: "orange",
    status: "active",
    category: "other",
  },
  {
    id: "linkedin-profile",
    name: "LinkedIn Profile",
    endpoint: "/v1/data/linkedin/profile",
    description: "Professional profiles with experience, education, and skills",
    icon: Linkedin,
    accent: "cyan",
    status: "coming-soon",
    category: "other",
  },
];

const API_CATEGORIES: Array<{ key: string; label: string; sublabel: string }> = [
  { key: "google", label: "Google", sublabel: "Search, Shopping, Maps, News, Jobs, Images, Flights & Finance" },
  { key: "other", label: "More Platforms", sublabel: "Amazon & More" },
];

const ACCENT_MAP: Record<string, { text: string; border: string; bg: string }> = {
  cyan: { text: "text-cyan-400", border: "border-cyan-500/20", bg: "bg-cyan-500/10" },
  amber: { text: "text-amber-400", border: "border-amber-500/20", bg: "bg-amber-500/10" },
  emerald: { text: "text-emerald-400", border: "border-emerald-500/20", bg: "bg-emerald-500/10" },
  violet: { text: "text-violet-400", border: "border-violet-500/20", bg: "bg-violet-500/10" },
  pink: { text: "text-pink-400", border: "border-pink-500/20", bg: "bg-pink-500/10" },
  rose: { text: "text-rose-400", border: "border-rose-500/20", bg: "bg-rose-500/10" },
  sky: { text: "text-sky-400", border: "border-sky-500/20", bg: "bg-sky-500/10" },
  lime: { text: "text-lime-400", border: "border-lime-500/20", bg: "bg-lime-500/10" },
  orange: { text: "text-orange-400", border: "border-orange-500/20", bg: "bg-orange-500/10" },
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
  const [activeCategory, setActiveCategory] = useState("google");
  const [slideDir, setSlideDir] = useState<"left" | "right">("right");

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

  // Google News state
  const [newsQuery, setNewsQuery] = useState("");
  const [newsNumResults, setNewsNumResults] = useState(100);
  const [newsLanguage, setNewsLanguage] = useState("en");
  const [newsCountry, setNewsCountry] = useState("");
  const [newsTimeRange, setNewsTimeRange] = useState("");
  const [newsSortBy, setNewsSortBy] = useState("");

  // Google Jobs state
  const [jobsQuery, setJobsQuery] = useState("");
  const [jobsNumResults, setJobsNumResults] = useState(100);
  const [jobsRemote, setJobsRemote] = useState(false);
  const [jobsSortBy, setJobsSortBy] = useState("relevance");
  const [jobsCompany, setJobsCompany] = useState("");
  const [jobsLevel, setJobsLevel] = useState("");
  const [jobsType, setJobsType] = useState("");
  const [jobsLocation, setJobsLocation] = useState("");

  // Google Images
  const [imagesQuery, setImagesQuery] = useState("");
  const [imagesNumResults, setImagesNumResults] = useState(0);
  const [imagesColour, setImagesColour] = useState("");
  const [imagesSize, setImagesSize] = useState("");
  const [imagesType, setImagesType] = useState("");
  const [imagesAspect, setImagesAspect] = useState("");
  const [imagesSafe, setImagesSafe] = useState(false);

  // Google Flights
  const [flightsOrigin, setFlightsOrigin] = useState("");
  const [flightsDestination, setFlightsDestination] = useState("");
  const [flightsDeparture, setFlightsDeparture] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  });
  const [flightsReturn, setFlightsReturn] = useState("");
  const [flightsAdults, setFlightsAdults] = useState(1);
  const [flightsSeat, setFlightsSeat] = useState("economy");
  const [flightsCurrency, setFlightsCurrency] = useState("");
  const [flightsMaxStops, setFlightsMaxStops] = useState("");

  // Google Finance
  const [financeQuery, setFinanceQuery] = useState("");
  const [financeLanguage, setFinanceLanguage] = useState("");
  const [financeCountry, setFinanceCountry] = useState("");

  // Amazon Products
  const [amazonQuery, setAmazonQuery] = useState("");
  const [amazonPages, setAmazonPages] = useState(1);
  const [amazonDomain, setAmazonDomain] = useState("amazon.in");
  const [amazonSortBy, setAmazonSortBy] = useState("");
  const [amazonPrimeOnly, setAmazonPrimeOnly] = useState(false);

  const handleCategorySwitch = (key: string) => {
    if (key === activeCategory) return;
    const currentIdx = API_CATEGORIES.findIndex((c) => c.key === activeCategory);
    const nextIdx = API_CATEGORIES.findIndex((c) => c.key === key);
    setSlideDir(nextIdx > currentIdx ? "right" : "left");
    setActivePanel(null);
    setActiveCategory(key);
  };

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

  const handleGoogleNews = async () => {
    if (!newsQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleNews({
        query: newsQuery.trim(),
        num_results: newsNumResults,
        language: newsLanguage,
        ...(newsCountry && { country: newsCountry }),
        ...(newsTimeRange && { time_range: newsTimeRange }),
        ...(newsSortBy && { sort_by: newsSortBy }),
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleJobs = async () => {
    if (!jobsQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleJobs({
        query: jobsQuery.trim(),
        num_results: jobsNumResults,
        has_remote: jobsRemote || undefined,
        sort_by: jobsSortBy,
        ...(jobsCompany && { company: [jobsCompany] }),
        ...(jobsLevel && { target_level: [jobsLevel] }),
        ...(jobsType && { employment_type: [jobsType] }),
        ...(jobsLocation.trim() && { location: [jobsLocation.trim()] }),
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleImages = async () => {
    if (!imagesQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleImages({
        query: imagesQuery.trim(),
        num_results: imagesNumResults,
        safe_search: imagesSafe || undefined,
        ...(imagesColour && { colour: imagesColour }),
        ...(imagesSize && { size: imagesSize }),
        ...(imagesType && { type: imagesType }),
        ...(imagesAspect && { aspect_ratio: imagesAspect }),
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleFlights = async () => {
    if (!flightsOrigin.trim() || !flightsDestination.trim() || !flightsDeparture.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleFlights({
        origin: flightsOrigin.trim().toUpperCase(),
        destination: flightsDestination.trim().toUpperCase(),
        departure_date: flightsDeparture,
        ...(flightsReturn && { return_date: flightsReturn }),
        adults: flightsAdults,
        seat: flightsSeat,
        ...(flightsCurrency && { currency: flightsCurrency }),
        ...(flightsMaxStops && { max_stops: Number(flightsMaxStops) }),
      });
      if (res.error) {
        setError(res.error);
      }
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleFinance = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.googleFinance({
        ...(financeQuery.trim() && { query: financeQuery.trim() }),
        ...(financeLanguage && { language: financeLanguage }),
        ...(financeCountry && { country: financeCountry }),
      });
      if (res.error) {
        setError(res.error);
      }
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleAmazonProducts = async () => {
    if (!amazonQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.amazonProducts({
        query: amazonQuery.trim(),
        num_results: amazonPages * 48,
        domain: amazonDomain,
        ...(amazonSortBy && { sort_by: amazonSortBy }),
        prime_only: amazonPrimeOnly || undefined,
      });
      if (res.error) {
        setError(res.error);
      }
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
            {/* Category tabs */}
            <div className="flex items-center gap-3 mb-8">
              {API_CATEGORIES.map((cat) => {
                const isSelected = activeCategory === cat.key;
                const count = SCRAPER_APIS.filter((a) => a.category === cat.key).length;
                return (
                  <button
                    key={cat.key}
                    onClick={() => handleCategorySwitch(cat.key)}
                    className={`group relative px-6 py-3.5 border font-mono text-left transition-all duration-200 ${
                      isSelected
                        ? "border-cyan-500/40 bg-cyan-500/[0.06]"
                        : "border-white/[0.08] bg-white/[0.02] hover:border-white/[0.15] hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-[14px] font-bold uppercase tracking-[0.05em] transition-colors ${isSelected ? "text-white" : "text-white/50 group-hover:text-white/70"}`}>
                        {cat.label}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 font-mono transition-colors ${
                        isSelected ? "bg-cyan-500/20 text-cyan-400" : "bg-white/[0.06] text-white/30"
                      }`}>
                        {count}
                      </span>
                    </div>
                    <div className={`text-[10px] uppercase tracking-[0.15em] mt-0.5 transition-colors ${isSelected ? "text-white/40" : "text-white/20"}`}>
                      {cat.sublabel}
                    </div>
                    {isSelected && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-cyan-500" />}
                  </button>
                );
              })}
              <div className="flex-1 h-[1px] bg-white/[0.06]" />
            </div>

            {/* Animated cards container */}
            <div className="overflow-hidden">
              {API_CATEGORIES.map((cat) => {
                if (cat.key !== activeCategory) return null;
                const categoryApis = SCRAPER_APIS.filter((a) => a.category === cat.key);
                return (
                  <div
                    key={cat.key}
                    className={`animate-slide-in-${slideDir}`}
                    style={{ animation: `slide-in-${slideDir} 0.3s ease-out` }}
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[1px] bg-white/[0.06]">
                      {categoryApis.map((scraperApi) => {
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

            {/* ── TRYOUT PANEL: Google News ── */}
            {activePanel === "google-news" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                {/* Panel header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-violet-500/20 grid place-items-center">
                      <Newspaper className="h-4 w-4 text-violet-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google News API</h3>
                      <code className="text-[11px] text-violet-400/60 font-mono">POST /v1/data/google/news</code>
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
                          value={newsQuery}
                          onChange={(e) => setNewsQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleNews()}
                          placeholder="e.g. artificial intelligence breakthroughs"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-violet-500/40 transition-colors"
                        />
                        <Newspaper className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    {/* Results + Language */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select
                            value={newsNumResults}
                            onChange={(e) => setNewsNumResults(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-violet-500/40 transition-colors"
                          >
                            {[10, 25, 50, 100, 200, 300, 500].map((n) => (
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
                            value={newsLanguage}
                            onChange={(e) => setNewsLanguage(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-violet-500/40 transition-colors"
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

                    {/* Country + Time Range */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Country</label>
                        <div className="relative">
                          <select
                            value={newsCountry}
                            onChange={(e) => setNewsCountry(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-violet-500/40 transition-colors"
                          >
                            <option value="">Any</option>
                            <option value="us">United States</option>
                            <option value="gb">United Kingdom</option>
                            <option value="ca">Canada</option>
                            <option value="au">Australia</option>
                            <option value="in">India</option>
                            <option value="de">Germany</option>
                            <option value="fr">France</option>
                            <option value="jp">Japan</option>
                            <option value="br">Brazil</option>
                            <option value="mx">Mexico</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Time Range</label>
                        <div className="relative">
                          <select
                            value={newsTimeRange}
                            onChange={(e) => setNewsTimeRange(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-violet-500/40 transition-colors"
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

                    {/* Sort By */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Sort By</label>
                        <div className="relative">
                          <select
                            value={newsSortBy}
                            onChange={(e) => setNewsSortBy(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-violet-500/40 transition-colors"
                          >
                            <option value="">Relevance</option>
                            <option value="date">Date (newest first)</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Submit button */}
                    <button
                      onClick={handleGoogleNews}
                      disabled={loading || !newsQuery.trim()}
                      className="w-full border border-violet-500/40 bg-violet-500/10 text-violet-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-violet-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Fetching News...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search News
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
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Articles</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.articles?.length || 0} articles &middot; {result.time_taken?.toFixed(2)}s
                            {result.source_strategy && (
                              <span className="text-violet-400/50 ml-1">via {result.source_strategy}</span>
                            )}
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-violet-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Newspaper className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search for news to see results</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-violet-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching news articles...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Article cards */}
                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.articles?.map((article: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-4 hover:border-white/[0.08] transition-colors">
                              <div className="flex gap-4">
                                {/* Thumbnail */}
                                {article.thumbnail && (
                                  <div className="flex-shrink-0 h-16 w-20 border border-white/[0.06] bg-white/[0.02] grid place-items-center overflow-hidden">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src={article.thumbnail} alt={article.title} className="h-full w-full object-cover" />
                                  </div>
                                )}

                                <div className="min-w-0 flex-1">
                                  {/* Position + Source + Date */}
                                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                                    <span className="text-[10px] text-white/20 font-mono">#{article.position}</span>
                                    {article.source && (
                                      <span className="text-[9px] uppercase tracking-wider text-violet-400 bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 font-mono">
                                        {article.source}
                                      </span>
                                    )}
                                    {(article.date || article.published_date) && (
                                      <span className="text-[10px] text-white/25 font-mono">
                                        {article.date || article.published_date}
                                      </span>
                                    )}
                                  </div>

                                  {/* Title */}
                                  <div className="flex items-start justify-between gap-2 mb-1">
                                    <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-white/80 font-mono hover:text-violet-400 transition-colors line-clamp-2">
                                      {article.title}
                                    </a>
                                    <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0 mt-0.5">
                                      <ExternalLink className="h-3.5 w-3.5" />
                                    </a>
                                  </div>

                                  {/* Snippet */}
                                  {article.snippet && (
                                    <p className="text-[11px] text-white/30 font-mono line-clamp-2 leading-relaxed">
                                      {article.snippet}
                                    </p>
                                  )}

                                  {/* Source URL */}
                                  {article.source_url && (
                                    <span className="text-[10px] text-white/15 font-mono">{article.source_url}</span>
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

            {/* ═══ GOOGLE JOBS TRYOUT PANEL ═══ */}
            {activePanel === "google-jobs" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-pink-500/20 grid place-items-center">
                      <Briefcase className="h-4 w-4 text-pink-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Jobs API</h3>
                      <code className="text-[11px] text-pink-400/60 font-mono">POST /v1/data/google/jobs</code>
                    </div>
                  </div>
                  <button onClick={() => setActivePanel(null)} className="h-8 w-8 grid place-items-center text-white/30 hover:text-white transition-colors">
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
                  <div className="p-6 space-y-5">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono mb-4">Request Parameters</div>

                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Query *</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={jobsQuery}
                          onChange={(e) => setJobsQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleJobs()}
                          placeholder="e.g. software engineer, penetration tester"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-pink-500/40 transition-colors"
                        />
                        <Briefcase className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Location <span className="normal-case tracking-normal text-white/20">(Google/Alphabet offices only)</span></label>
                      <div className="relative">
                        <input
                          type="text"
                          value={jobsLocation}
                          onChange={(e) => setJobsLocation(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleJobs()}
                          placeholder="e.g. Bengaluru, India / New York / London"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-pink-500/40 transition-colors"
                        />
                        <MapPin className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Organization</label>
                        <div className="relative">
                          <select value={jobsCompany} onChange={(e) => setJobsCompany(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-pink-500/40 transition-colors">
                            <option value="">All</option>
                            <option value="Google">Google</option>
                            <option value="DeepMind">DeepMind</option>
                            <option value="YouTube">YouTube</option>
                            <option value="Waymo">Waymo</option>
                            <option value="GFiber">GFiber</option>
                            <option value="Wing">Wing</option>
                            <option value="Verily Life Sciences">Verily Life Sciences</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Experience</label>
                        <div className="relative">
                          <select value={jobsLevel} onChange={(e) => setJobsLevel(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-pink-500/40 transition-colors">
                            <option value="">All Levels</option>
                            <option value="INTERN_AND_APPRENTICE">Intern & Apprentice</option>
                            <option value="EARLY">Early</option>
                            <option value="MID">Mid</option>
                            <option value="ADVANCED">Advanced</option>
                            <option value="DIRECTOR">Director+</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Job Type</label>
                        <div className="relative">
                          <select value={jobsType} onChange={(e) => setJobsType(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-pink-500/40 transition-colors">
                            <option value="">All Types</option>
                            <option value="FULL_TIME">Full-time</option>
                            <option value="PART_TIME">Part-time</option>
                            <option value="TEMPORARY">Temporary</option>
                            <option value="INTERN">Intern</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Sort By</label>
                        <div className="relative">
                          <select value={jobsSortBy} onChange={(e) => setJobsSortBy(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-pink-500/40 transition-colors">
                            <option value="relevance">Relevance</option>
                            <option value="date">Date (newest)</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select value={jobsNumResults} onChange={(e) => setJobsNumResults(Number(e.target.value))} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-pink-500/40 transition-colors">
                            {[20, 50, 100, 200, 500, 1000, 2000].map((n) => (
                              <option key={n} value={n}>{n}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div className="flex items-end pb-1">
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={jobsRemote}
                            onChange={(e) => setJobsRemote(e.target.checked)}
                            className="h-4 w-4 accent-pink-500"
                          />
                          <span className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono">Remote Only</span>
                        </label>
                      </div>
                    </div>

                    <button
                      onClick={handleGoogleJobs}
                      disabled={loading || !jobsQuery.trim()}
                      className="w-full border border-pink-500/40 bg-pink-500/10 text-pink-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-pink-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Fetching Jobs...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search Jobs
                        </>
                      )}
                    </button>

                    {error && (
                      <div className="border border-red-500/20 bg-red-500/5 px-4 py-3 text-[12px] text-red-400 font-mono">
                        {error}
                      </div>
                    )}
                  </div>

                  <div className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Job Listings</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.jobs?.length || 0} jobs &middot; {result.time_taken?.toFixed(2)}s
                            {result.total_results && (
                              <span className="text-pink-400/50 ml-1">of {result.total_results} total</span>
                            )}
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-pink-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Briefcase className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search for jobs to see results</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-pink-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching job listings...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {result.jobs?.length === 0 && (
                          <div className="text-center py-8 border border-white/[0.06] bg-[#050505]">
                            <Briefcase className="h-8 w-8 text-white/10 mx-auto mb-3" />
                            <p className="text-[13px] text-white/40 font-mono mb-2">No jobs found{jobsLocation.trim() ? ` in "${jobsLocation.trim()}"` : ""}</p>
                            {jobsLocation.trim() && (
                              <p className="text-[11px] text-white/20 font-mono px-6">
                                Google Careers only lists jobs at Alphabet office locations. Try: Bengaluru, Hyderabad, Pune, New York, London, Singapore, Tokyo, or a country name like India, USA.
                              </p>
                            )}
                          </div>
                        )}
                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.jobs?.map((job: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-4 hover:border-white/[0.08] transition-colors">
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                                    <span className="text-[10px] text-white/20 font-mono">#{job.position}</span>
                                    <span className="text-[9px] uppercase tracking-wider text-pink-400 bg-pink-500/10 border border-pink-500/20 px-1.5 py-0.5 font-mono">
                                      {job.company}
                                    </span>
                                    {job.experience_level && (
                                      <span className="text-[9px] uppercase tracking-wider text-white/30 bg-white/5 border border-white/10 px-1.5 py-0.5 font-mono">
                                        {job.experience_level}
                                      </span>
                                    )}
                                  </div>
                                  <a href={job.detail_url || job.apply_url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-white/80 font-mono hover:text-pink-400 transition-colors line-clamp-2">
                                    {job.title}
                                  </a>
                                </div>
                                <a href={job.apply_url || job.detail_url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0 mt-0.5">
                                  <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              </div>
                              <div className="flex items-center gap-2 flex-wrap">
                                {job.locations?.map((loc: any, j: number) => (
                                  <span key={j} className="text-[10px] text-white/30 font-mono flex items-center gap-1">
                                    <MapPin className="h-3 w-3 text-white/15" />
                                    {loc.display_name}
                                  </span>
                                ))}
                              </div>
                              {job.created_at && (
                                <span className="text-[10px] text-white/15 font-mono mt-1 block">
                                  Posted: {new Date(job.created_at).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>

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
            {activePanel === "google-images" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-rose-500/20 grid place-items-center">
                      <Image className="h-4 w-4 text-rose-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Images API</h3>
                      <code className="text-[11px] text-rose-400/60 font-mono">POST /v1/data/google/images</code>
                    </div>
                  </div>
                  <button onClick={() => setActivePanel(null)} className="h-8 w-8 grid place-items-center text-white/30 hover:text-white transition-colors">
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
                  <div className="p-6 space-y-5">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono mb-4">Request Parameters</div>

                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Query *</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={imagesQuery}
                          onChange={(e) => setImagesQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleImages()}
                          placeholder="e.g. sunset, cat, hinata, architecture"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-rose-500/40 transition-colors"
                        />
                        <Image className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Results</label>
                        <div className="relative">
                          <select value={imagesNumResults} onChange={(e) => setImagesNumResults(Number(e.target.value))} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-rose-500/40 transition-colors">
                            <option value={25}>25</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                            <option value={200}>200</option>
                            <option value={500}>500</option>
                            <option value={0}>Max (all)</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Colour</label>
                        <div className="relative">
                          <select value={imagesColour} onChange={(e) => setImagesColour(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-rose-500/40 transition-colors">
                            <option value="">Any</option>
                            <option value="red">Red</option>
                            <option value="orange">Orange</option>
                            <option value="yellow">Yellow</option>
                            <option value="green">Green</option>
                            <option value="teal">Teal</option>
                            <option value="blue">Blue</option>
                            <option value="purple">Purple</option>
                            <option value="pink">Pink</option>
                            <option value="white">White</option>
                            <option value="gray">Gray</option>
                            <option value="black">Black</option>
                            <option value="brown">Brown</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Size</label>
                        <div className="relative">
                          <select value={imagesSize} onChange={(e) => setImagesSize(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-rose-500/40 transition-colors">
                            <option value="">Any</option>
                            <option value="large">Large</option>
                            <option value="medium">Medium</option>
                            <option value="icon">Icon</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Type</label>
                        <div className="relative">
                          <select value={imagesType} onChange={(e) => setImagesType(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-rose-500/40 transition-colors">
                            <option value="">Any</option>
                            <option value="photo">Photo</option>
                            <option value="clipart">Clip Art</option>
                            <option value="lineart">Line Art</option>
                            <option value="animated">Animated</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Aspect Ratio</label>
                        <div className="relative">
                          <select value={imagesAspect} onChange={(e) => setImagesAspect(e.target.value)} className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-rose-500/40 transition-colors">
                            <option value="">Any</option>
                            <option value="tall">Tall</option>
                            <option value="square">Square</option>
                            <option value="wide">Wide</option>
                            <option value="panoramic">Panoramic</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div className="flex items-end pb-1">
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={imagesSafe}
                            onChange={(e) => setImagesSafe(e.target.checked)}
                            className="h-4 w-4 accent-rose-500"
                          />
                          <span className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono">Safe Search</span>
                        </label>
                      </div>
                    </div>

                    <button
                      onClick={handleGoogleImages}
                      disabled={loading || !imagesQuery.trim()}
                      className="w-full border border-rose-500/40 bg-rose-500/10 text-rose-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-rose-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching Images...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search Images
                        </>
                      )}
                    </button>

                    {error && (
                      <div className="border border-red-500/20 bg-red-500/5 px-4 py-3 text-[12px] text-red-400 font-mono">
                        {error}
                      </div>
                    )}
                  </div>

                  <div className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Image Results</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.images?.length || 0} images &middot; {result.time_taken?.toFixed(2)}s
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-rose-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Image className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search for images to see results</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-rose-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching images...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {result.images?.length === 0 && (
                          <div className="text-center py-8 border border-white/[0.06] bg-[#050505]">
                            <Image className="h-8 w-8 text-white/10 mx-auto mb-3" />
                            <p className="text-[13px] text-white/40 font-mono">No images found</p>
                          </div>
                        )}
                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.images?.map((img: any, i: number) => (
                            <div key={i} className="bg-[#050505] border border-white/[0.04] p-3 hover:border-white/[0.08] transition-colors">
                              <div className="flex gap-3">
                                {img.thumbnail_url && (
                                  <a href={img.image_url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
                                    <img
                                      src={img.thumbnail_url}
                                      alt={img.title}
                                      className="w-20 h-16 object-cover border border-white/10"
                                      loading="lazy"
                                    />
                                  </a>
                                )}
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] text-white/20 font-mono">#{img.position}</span>
                                    {img.domain && (
                                      <span className="text-[9px] uppercase tracking-wider text-rose-400 bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 font-mono truncate max-w-[150px]">
                                        {img.domain}
                                      </span>
                                    )}
                                    {img.file_size && (
                                      <span className="text-[9px] text-white/25 font-mono">{img.file_size}</span>
                                    )}
                                  </div>
                                  <a href={img.url} target="_blank" rel="noopener noreferrer" className="text-[12px] text-white/70 font-mono hover:text-rose-400 transition-colors line-clamp-1 block">
                                    {img.title}
                                  </a>
                                  <div className="flex items-center gap-3 mt-1">
                                    {img.image_width && img.image_height && (
                                      <span className="text-[10px] text-white/20 font-mono">{img.image_width}×{img.image_height}</span>
                                    )}
                                    {img.site_name && (
                                      <span className="text-[10px] text-white/20 font-mono">{img.site_name}</span>
                                    )}
                                  </div>
                                </div>
                                <a href={img.image_url} target="_blank" rel="noopener noreferrer" className="text-white/20 hover:text-white/50 flex-shrink-0 mt-0.5">
                                  <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              </div>
                            </div>
                          ))}
                        </div>

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

            {/* ── TRYOUT PANEL: Google Flights ── */}
            {activePanel === "google-flights" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-sky-500/20 grid place-items-center">
                      <Plane className="h-4 w-4 text-sky-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Flights API</h3>
                      <code className="text-[11px] text-sky-400/60 font-mono">POST /v1/data/google/flights</code>
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

                    {/* Origin & Destination */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Origin *</label>
                        <div className="relative">
                          <input
                            type="text"
                            value={flightsOrigin}
                            onChange={(e) => setFlightsOrigin(e.target.value.toUpperCase().slice(0, 3))}
                            onKeyDown={(e) => e.key === "Enter" && handleGoogleFlights()}
                            placeholder="MAA"
                            maxLength={3}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-sky-500/40 transition-colors uppercase"
                          />
                          <Plane className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Destination *</label>
                        <div className="relative">
                          <input
                            type="text"
                            value={flightsDestination}
                            onChange={(e) => setFlightsDestination(e.target.value.toUpperCase().slice(0, 3))}
                            onKeyDown={(e) => e.key === "Enter" && handleGoogleFlights()}
                            placeholder="BLR"
                            maxLength={3}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-sky-500/40 transition-colors uppercase"
                          />
                          <MapPin className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                        </div>
                      </div>
                    </div>

                    {/* Departure & Return dates */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Departure Date *</label>
                        <input
                          type="date"
                          value={flightsDeparture}
                          min={new Date().toISOString().split("T")[0]}
                          onChange={(e) => setFlightsDeparture(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white focus:outline-none focus:border-sky-500/40 transition-colors [color-scheme:dark]"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Return Date</label>
                        <input
                          type="date"
                          value={flightsReturn}
                          min={flightsDeparture || new Date().toISOString().split("T")[0]}
                          onChange={(e) => setFlightsReturn(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white focus:outline-none focus:border-sky-500/40 transition-colors [color-scheme:dark]"
                        />
                      </div>
                    </div>

                    {/* Adults & Cabin Class */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Adults</label>
                        <div className="relative">
                          <select
                            value={flightsAdults}
                            onChange={(e) => setFlightsAdults(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-sky-500/40 transition-colors"
                          >
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                              <option key={n} value={n}>{n}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Cabin Class</label>
                        <div className="relative">
                          <select
                            value={flightsSeat}
                            onChange={(e) => setFlightsSeat(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-sky-500/40 transition-colors"
                          >
                            <option value="economy">Economy</option>
                            <option value="premium_economy">Premium Economy</option>
                            <option value="business">Business</option>
                            <option value="first">First</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Max Stops & Currency */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Max Stops</label>
                        <div className="relative">
                          <select
                            value={flightsMaxStops}
                            onChange={(e) => setFlightsMaxStops(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-sky-500/40 transition-colors"
                          >
                            <option value="">Any</option>
                            <option value="0">Nonstop only</option>
                            <option value="1">Max 1 stop</option>
                            <option value="2">Max 2 stops</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Currency</label>
                        <div className="relative">
                          <select
                            value={flightsCurrency}
                            onChange={(e) => setFlightsCurrency(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-sky-500/40 transition-colors"
                          >
                            <option value="">Default</option>
                            <option value="USD">USD ($)</option>
                            <option value="EUR">EUR (€)</option>
                            <option value="GBP">GBP (£)</option>
                            <option value="INR">INR (₹)</option>
                            <option value="JPY">JPY (¥)</option>
                            <option value="AUD">AUD (A$)</option>
                            <option value="CAD">CAD (C$)</option>
                            <option value="SGD">SGD (S$)</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={handleGoogleFlights}
                      disabled={loading || !flightsOrigin.trim() || !flightsDestination.trim() || !flightsDeparture}
                      className="w-full border border-sky-500/40 bg-sky-500/10 text-sky-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-sky-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching Flights...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Search Flights
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
                      <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-mono">Flight Results</div>
                      {result && (
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-white/30 font-mono">
                            {result.total_results || result.flights?.length || 0} flights &middot; {result.time_taken?.toFixed(2)}s
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-sky-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Plane className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Enter origin, destination & date to search flights</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-sky-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching flights from Google...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {result.flights?.length === 0 && (
                          <div className="text-center py-8 border border-white/[0.06] bg-[#050505]">
                            <Plane className="h-8 w-8 text-white/10 mx-auto mb-3" />
                            <p className="text-[13px] text-white/40 font-mono">No flights found for this route</p>
                          </div>
                        )}

                        {result.search_url && (
                          <a href={result.search_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[11px] text-sky-400/60 hover:text-sky-400 font-mono transition-colors mb-2">
                            <ExternalLink className="h-3 w-3" />
                            View on Google Flights
                          </a>
                        )}

                        <div className="max-h-[600px] overflow-y-auto space-y-[1px] scrollbar-thin">
                          {result.flights?.map((flight: any, i: number) => (
                            <a
                              key={i}
                              href={result.search_url || `https://www.google.com/travel/flights?q=${encodeURIComponent(`${flight.origin} to ${flight.destination}`)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`block bg-[#050505] border p-4 hover:border-white/[0.12] hover:bg-white/[0.02] transition-colors cursor-pointer ${flight.is_best ? "border-sky-500/20" : "border-white/[0.04]"}`}
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                  {/* Airline & flight number */}
                                  <div className="flex items-center gap-2 mb-2">
                                    <span className="text-[10px] text-white/20 font-mono">#{flight.position}</span>
                                    {flight.is_best && (
                                      <span className="text-[9px] uppercase tracking-wider text-sky-400 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 font-mono">
                                        Best
                                      </span>
                                    )}
                                    <span className="text-[12px] text-white/70 font-mono font-bold">{flight.airline}</span>
                                    {flight.flight_number && (
                                      <span className="text-[10px] text-white/30 font-mono">{flight.flight_number}</span>
                                    )}
                                  </div>

                                  {/* Route: times & duration */}
                                  <div className="flex items-center gap-3 mb-1.5">
                                    <span className="text-[14px] font-bold font-mono text-white">{flight.departure_time}</span>
                                    <div className="flex items-center gap-1.5 text-white/20">
                                      <div className="w-8 h-[1px] bg-white/20" />
                                      <Clock className="h-3 w-3" />
                                      <span className="text-[10px] font-mono">{flight.duration}</span>
                                      <div className="w-8 h-[1px] bg-white/20" />
                                    </div>
                                    <span className="text-[14px] font-bold font-mono text-white">
                                      {flight.arrival_time}
                                      {flight.arrival_time_ahead && (
                                        <span className="text-[10px] text-sky-400 ml-1">{flight.arrival_time_ahead}</span>
                                      )}
                                    </span>
                                  </div>

                                  {/* Origin → Destination + stops */}
                                  <div className="flex items-center gap-3">
                                    <span className="text-[11px] text-white/40 font-mono">
                                      {flight.origin} <ArrowRight className="inline h-3 w-3" /> {flight.destination}
                                    </span>
                                    <span className={`text-[10px] font-mono ${flight.stops === 0 ? "text-emerald-400" : "text-amber-400"}`}>
                                      {flight.stops_text}
                                    </span>
                                    {flight.aircraft && (
                                      <span className="text-[10px] text-white/20 font-mono">{flight.aircraft}</span>
                                    )}
                                    {flight.layover_airports?.length > 0 && (
                                      <span className="text-[10px] text-white/25 font-mono">via {flight.layover_airports.join(", ")}</span>
                                    )}
                                  </div>
                                </div>

                                {/* Price */}
                                <div className="text-right flex-shrink-0">
                                  {flight.price_value ? (
                                    <div className="text-[16px] font-bold font-mono text-sky-400">
                                      {flight.price}
                                    </div>
                                  ) : (
                                    <div className="text-[12px] text-white/20 font-mono">—</div>
                                  )}
                                  {flight.emissions && (
                                    <div className="text-[9px] text-white/20 font-mono mt-1">{flight.emissions}</div>
                                  )}
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>

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

            {/* ── TRYOUT PANEL: Google Finance ── */}
            {activePanel === "google-finance" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-lime-500/20 grid place-items-center">
                      <TrendingUp className="h-4 w-4 text-lime-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Google Finance API</h3>
                      <code className="text-[11px] text-lime-400/60 font-mono">POST /v1/data/google/finance</code>
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

                    {/* Query */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Ticker / Query</label>
                      <div className="relative">
                        <input
                          type="text"
                          value={financeQuery}
                          onChange={(e) => setFinanceQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleGoogleFinance()}
                          placeholder="AAPL:NASDAQ, BTC-USD, or leave empty for market overview"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-lime-500/40 transition-colors"
                        />
                        <TrendingUp className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                      <p className="text-[10px] text-white/20 font-mono mt-1.5">Leave empty for market overview with all indexes, crypto, futures & trends</p>
                    </div>

                    {/* Language */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Language</label>
                      <div className="relative">
                        <select
                          value={financeLanguage}
                          onChange={(e) => setFinanceLanguage(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-lime-500/40 transition-colors"
                        >
                          <option value="">Default (en)</option>
                          <option value="en">English</option>
                          <option value="es">Spanish</option>
                          <option value="fr">French</option>
                          <option value="de">German</option>
                          <option value="ja">Japanese</option>
                          <option value="hi">Hindi</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                      </div>
                    </div>

                    {/* Country */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Country</label>
                      <div className="relative">
                        <select
                          value={financeCountry}
                          onChange={(e) => setFinanceCountry(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-lime-500/40 transition-colors"
                        >
                          <option value="">Default</option>
                          <option value="US">United States</option>
                          <option value="GB">United Kingdom</option>
                          <option value="IN">India</option>
                          <option value="DE">Germany</option>
                          <option value="FR">France</option>
                          <option value="JP">Japan</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                      </div>
                    </div>

                    <button
                      onClick={handleGoogleFinance}
                      disabled={loading}
                      className="w-full border border-lime-500/40 bg-lime-500/10 text-lime-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-lime-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Fetching Finance Data...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          {financeQuery.trim() ? "Get Quote" : "Get Market Overview"}
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
                            {result.time_taken?.toFixed(2)}s
                          </span>
                          <button onClick={handleCopyResult} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-white/30 hover:text-white/60 font-mono transition-colors">
                            {copied ? <Check className="h-3 w-3 text-lime-400" /> : <Copy className="h-3 w-3" />}
                            {copied ? "Copied" : "Copy"}
                          </button>
                        </div>
                      )}
                    </div>

                    {!result && !loading && !error && (
                      <div className="h-[400px] border border-dashed border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <TrendingUp className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Enter a ticker or click to get market overview</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-lime-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching from Google Finance...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Quote summary card */}
                        {result.stock && (
                          <div className="border border-white/[0.06] p-4 space-y-2">
                            <div className="flex items-center justify-between">
                              <div>
                                <div className="text-[14px] font-bold font-mono text-white">{result.name || result.stock}</div>
                                <div className="text-[11px] text-white/40 font-mono">{result.stock}</div>
                              </div>
                              <div className="text-right">
                                <div className="text-[18px] font-bold font-mono text-white">{result.price}</div>
                                {result.price_movement && (
                                  <div className={`text-[12px] font-mono ${result.price_movement.movement === "up" ? "text-emerald-400" : "text-red-400"}`}>
                                    {result.price_movement.value} ({result.price_movement.percentage})
                                  </div>
                                )}
                              </div>
                            </div>
                            {result.previous_close && (
                              <div className="text-[11px] text-white/30 font-mono">Prev close: {result.previous_close}</div>
                            )}
                            {result.after_hours_price && (
                              <div className="text-[11px] text-white/30 font-mono">
                                After hours: {result.after_hours_price}
                                {result.after_hours_movement && (
                                  <span className={result.after_hours_movement.movement === "up" ? "text-emerald-400" : "text-red-400"}>
                                    {" "}{result.after_hours_movement.value} ({result.after_hours_movement.percentage})
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Market sections summary */}
                        {result.markets && (
                          <div className="space-y-3">
                            {Object.entries(result.markets).map(([section, stocks]) => (
                              <details key={section} className="border border-white/[0.06]">
                                <summary className="px-4 py-3 text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono cursor-pointer hover:text-white/60 transition-colors flex items-center justify-between">
                                  <span>{section}</span>
                                  <span className="text-[10px] text-white/20">{(stocks as any[]).length} stocks</span>
                                </summary>
                                <div className="px-4 pb-3 space-y-1">
                                  {(stocks as any[]).map((s: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between py-1 border-b border-white/[0.03] last:border-0">
                                      <div>
                                        <span className="text-[11px] font-mono text-lime-400/80">{s.stock}</span>
                                        <span className="text-[10px] text-white/30 font-mono ml-2">{s.name}</span>
                                      </div>
                                      <div className="flex items-center gap-3">
                                        <span className="text-[11px] font-mono text-white/60">{s.price}</span>
                                        {s.price_movement && (
                                          <span className={`text-[10px] font-mono ${s.price_movement.movement === "up" ? "text-emerald-400" : "text-red-400"}`}>
                                            {s.price_movement.percentage}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ))}
                          </div>
                        )}

                        {/* Similar stocks */}
                        {result.similar_stocks && result.similar_stocks.length > 0 && (
                          <details className="border border-white/[0.06]">
                            <summary className="px-4 py-3 text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono cursor-pointer hover:text-white/60 transition-colors flex items-center justify-between">
                              <span>Similar Stocks</span>
                              <span className="text-[10px] text-white/20">{result.similar_stocks.length}</span>
                            </summary>
                            <div className="px-4 pb-3 space-y-1">
                              {result.similar_stocks.map((s: any, i: number) => (
                                <div key={i} className="flex items-center justify-between py-1 border-b border-white/[0.03] last:border-0">
                                  <div>
                                    <span className="text-[11px] font-mono text-lime-400/80">{s.stock}</span>
                                    <span className="text-[10px] text-white/30 font-mono ml-2">{s.name}</span>
                                  </div>
                                  <div className="flex items-center gap-3">
                                    <span className="text-[11px] font-mono text-white/60">{s.price}</span>
                                    {s.price_movement && (
                                      <span className={`text-[10px] font-mono ${s.price_movement.movement === "up" ? "text-emerald-400" : "text-red-400"}`}>
                                        {s.price_movement.percentage}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}

                        {/* News */}
                        {result.news && result.news.length > 0 && (
                          <details className="border border-white/[0.06]">
                            <summary className="px-4 py-3 text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono cursor-pointer hover:text-white/60 transition-colors flex items-center justify-between">
                              <span>News</span>
                              <span className="text-[10px] text-white/20">{result.news.length} articles</span>
                            </summary>
                            <div className="px-4 pb-3 space-y-2">
                              {result.news.map((article: any, i: number) => (
                                <a key={i} href={article.url} target="_blank" rel="noopener noreferrer" className="block py-2 border-b border-white/[0.03] last:border-0 hover:bg-white/[0.02] transition-colors -mx-1 px-1">
                                  <div className="flex items-start gap-3">
                                    {article.thumbnail && (
                                      <img src={article.thumbnail} alt="" className="w-12 h-12 object-cover flex-shrink-0 border border-white/[0.06]" />
                                    )}
                                    <div>
                                      <div className="text-[11px] font-mono text-white/70 leading-relaxed">{article.title}</div>
                                      {article.source && (
                                        <div className="text-[10px] text-white/30 font-mono mt-0.5">{article.source}</div>
                                      )}
                                    </div>
                                  </div>
                                </a>
                              ))}
                            </div>
                          </details>
                        )}

                        {/* Market trends */}
                        {result.market_trends && (
                          <div className="space-y-3">
                            {Object.entries(result.market_trends).map(([label, stocks]) => (
                              <details key={label} className="border border-white/[0.06]">
                                <summary className="px-4 py-3 text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono cursor-pointer hover:text-white/60 transition-colors flex items-center justify-between">
                                  <span>{label}</span>
                                  <span className="text-[10px] text-white/20">{(stocks as any[]).length} stocks</span>
                                </summary>
                                <div className="px-4 pb-3 space-y-1">
                                  {(stocks as any[]).map((s: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between py-1 border-b border-white/[0.03] last:border-0">
                                      <div>
                                        <span className="text-[11px] font-mono text-lime-400/80">{s.stock}</span>
                                        <span className="text-[10px] text-white/30 font-mono ml-2">{s.name}</span>
                                      </div>
                                      <div className="flex items-center gap-3">
                                        <span className="text-[11px] font-mono text-white/60">{s.price}</span>
                                        {s.price_movement && (
                                          <span className={`text-[10px] font-mono ${s.price_movement.movement === "up" ? "text-emerald-400" : "text-red-400"}`}>
                                            {s.price_movement.percentage}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ))}
                          </div>
                        )}

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
            {/* ═══ AMAZON PRODUCTS PANEL ═══ */}
            {activePanel === "amazon-products" && (
              <div ref={panelRef} className="mt-[1px] border border-white/[0.08] bg-[#0a0a0a]">
                {/* Panel header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 border border-orange-500/20 grid place-items-center">
                      <Package className="h-4 w-4 text-orange-400" />
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] font-mono">Amazon Products API</h3>
                      <code className="text-[11px] text-orange-400/60 font-mono">POST /v1/data/amazon/products</code>
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
                          value={amazonQuery}
                          onChange={(e) => setAmazonQuery(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleAmazonProducts()}
                          placeholder="e.g. wireless headphones bluetooth"
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-orange-500/40 transition-colors"
                        />
                        <Package className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                      </div>
                    </div>

                    {/* Domain + Pages */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Domain</label>
                        <div className="relative">
                          <select
                            value={amazonDomain}
                            onChange={(e) => setAmazonDomain(e.target.value)}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-orange-500/40 transition-colors"
                          >
                            <option value="amazon.in">amazon.in</option>
                            <option value="amazon.com">amazon.com</option>
                            <option value="amazon.co.uk">amazon.co.uk</option>
                            <option value="amazon.de">amazon.de</option>
                            <option value="amazon.fr">amazon.fr</option>
                            <option value="amazon.co.jp">amazon.co.jp</option>
                            <option value="amazon.ca">amazon.ca</option>
                            <option value="amazon.com.au">amazon.com.au</option>
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Pages</label>
                        <div className="relative">
                          <select
                            value={amazonPages}
                            onChange={(e) => setAmazonPages(Number(e.target.value))}
                            className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-orange-500/40 transition-colors"
                          >
                            {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => (
                              <option key={n} value={n}>{n} {n === 1 ? "page" : "pages"} (~{n * 48} results)</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Sort By */}
                    <div>
                      <label className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono mb-2 block">Sort By</label>
                      <div className="relative">
                        <select
                          value={amazonSortBy}
                          onChange={(e) => setAmazonSortBy(e.target.value)}
                          className="w-full bg-[#050505] border border-white/10 px-4 py-3 text-[13px] font-mono text-white appearance-none focus:outline-none focus:border-orange-500/40 transition-colors"
                        >
                          <option value="">Relevance</option>
                          <option value="price_low">Price: Low to High</option>
                          <option value="price_high">Price: High to Low</option>
                          <option value="rating">Avg. Rating</option>
                          <option value="newest">Newest Arrivals</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-white/30 pointer-events-none" />
                      </div>
                    </div>

                    {/* Prime Only toggle */}
                    <div>
                      <label className="flex items-center gap-3 cursor-pointer group">
                        <div
                          onClick={() => setAmazonPrimeOnly(!amazonPrimeOnly)}
                          className={`h-5 w-9 rounded-full border transition-colors flex items-center px-0.5 ${
                            amazonPrimeOnly
                              ? "bg-orange-500/20 border-orange-500/40"
                              : "bg-white/5 border-white/10"
                          }`}
                        >
                          <div className={`h-3.5 w-3.5 rounded-full transition-all ${
                            amazonPrimeOnly
                              ? "bg-orange-400 translate-x-3.5"
                              : "bg-white/30 translate-x-0"
                          }`} />
                        </div>
                        <span className="text-[11px] uppercase tracking-[0.15em] text-white/40 font-mono group-hover:text-white/60 transition-colors">Prime Only</span>
                      </label>
                    </div>

                    {/* Submit button */}
                    <button
                      onClick={handleAmazonProducts}
                      disabled={loading || !amazonQuery.trim()}
                      className="w-full border border-orange-500/40 bg-orange-500/10 text-orange-400 py-3 text-[12px] uppercase tracking-[0.2em] font-mono hover:bg-orange-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching Amazon...
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
                            {result.products?.length || 0} products &middot; {result.pages_fetched} pages &middot; {result.time_taken?.toFixed(2)}s
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
                          <Package className="h-8 w-8 text-white/10 mx-auto mb-3" />
                          <p className="text-[12px] text-white/20 font-mono">Search Amazon to see products</p>
                        </div>
                      </div>
                    )}

                    {loading && (
                      <div className="h-[400px] border border-white/[0.06] grid place-items-center">
                        <div className="text-center">
                          <Loader2 className="h-6 w-6 text-orange-400 animate-spin mx-auto mb-3" />
                          <p className="text-[12px] text-white/30 font-mono">Fetching Amazon products...</p>
                        </div>
                      </div>
                    )}

                    {result && (
                      <div className="space-y-4">
                        {/* Domain + total results badge */}
                        <div className="flex flex-wrap gap-2">
                          <span className="text-[10px] font-mono border border-orange-500/20 bg-orange-500/5 text-orange-400 px-2 py-1">
                            {result.domain}
                          </span>
                          {result.total_results && (
                            <span className="text-[10px] font-mono border border-white/10 bg-white/5 text-white/40 px-2 py-1">
                              {result.total_results}
                            </span>
                          )}
                        </div>

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
                                          <span className="text-[9px] uppercase tracking-wider text-orange-400 bg-orange-500/10 border border-orange-500/20 px-1.5 py-0.5 font-mono">
                                            {product.badge}
                                          </span>
                                        )}
                                        {product.is_sponsored && (
                                          <span className="text-[9px] uppercase tracking-wider text-white/30 bg-white/5 border border-white/10 px-1.5 py-0.5 font-mono">AD</span>
                                        )}
                                        {product.is_prime && (
                                          <span className="text-[9px] uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-1.5 py-0.5 font-mono">Prime</span>
                                        )}
                                      </div>
                                      <a href={product.url} target="_blank" rel="noopener noreferrer" className="text-[12px] font-mono text-white/80 hover:text-white leading-snug line-clamp-2 transition-colors">
                                        {product.title}
                                        <ExternalLink className="inline h-2.5 w-2.5 ml-1 text-white/20" />
                                      </a>
                                    </div>
                                  </div>

                                  {/* Price + Rating row */}
                                  <div className="flex items-center gap-4 mt-2">
                                    {product.price && (
                                      <span className="text-[13px] font-mono font-bold text-orange-400">{product.price}</span>
                                    )}
                                    {product.original_price && (
                                      <span className="text-[11px] font-mono text-white/30 line-through">{product.original_price}</span>
                                    )}
                                    {product.discount && (
                                      <span className="text-[10px] font-mono text-emerald-400">{product.discount}</span>
                                    )}
                                  </div>

                                  {/* Rating + reviews + meta */}
                                  <div className="flex items-center gap-4 mt-1.5 flex-wrap">
                                    {product.rating != null && (
                                      <span className="text-[11px] font-mono text-amber-400">
                                        {"★".repeat(Math.round(product.rating))}{"☆".repeat(5 - Math.round(product.rating))} {product.rating}
                                      </span>
                                    )}
                                    {product.review_count != null && (
                                      <span className="text-[10px] font-mono text-white/30">{product.review_count.toLocaleString()} reviews</span>
                                    )}
                                    <span className="text-[10px] font-mono text-white/20">{product.asin}</span>
                                  </div>

                                  {/* Delivery + coupon */}
                                  <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                                    {product.delivery && (
                                      <span className="text-[10px] font-mono text-white/30">{product.delivery}</span>
                                    )}
                                    {product.coupon && (
                                      <span className="text-[10px] font-mono text-emerald-400/80 border border-emerald-500/20 bg-emerald-500/5 px-1.5 py-0.5">{product.coupon}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

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
