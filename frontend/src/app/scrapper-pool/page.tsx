"use client";

import { useState } from "react";
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
} from "lucide-react";

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
    status: "coming-soon",
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

                return (
                  <div
                    key={scraperApi.id}
                    className="bg-[#050505] p-8 group hover:bg-white/[0.02] transition-colors relative"
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

                    {/* Endpoint */}
                    <div className="border-t border-white/[0.06] pt-4">
                      <code className={`text-[11px] ${colors.text} font-mono tracking-wider`}>
                        {scraperApi.endpoint}
                      </code>
                    </div>
                  </div>
                );
              })}
            </div>
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
