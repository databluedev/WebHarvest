"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import {
  Layers,
  Search,
  ShoppingCart,
  MapPin,
  Newspaper,
  Briefcase,
  Package,
  Linkedin,
  ChevronRight,
} from "lucide-react";

type ApiStatus = "active" | "coming-soon";

const SCRAPER_APIS: Array<{
  id: string;
  name: string;
  description: string;
  icon: typeof Search;
  color: string;
  bgGlow: string;
  textColor: string;
  borderColor: string;
  status: ApiStatus;
}> = [
  {
    id: "google-search",
    name: "Google Search",
    description: "Search results with titles, links, snippets, and positions",
    icon: Search,
    color: "from-cyan-500 to-blue-500",
    bgGlow: "bg-cyan-500/10",
    textColor: "text-cyan-400",
    borderColor: "border-cyan-500/20",
    status: "coming-soon",
  },
  {
    id: "google-shopping",
    name: "Google Shopping",
    description: "Product listings with prices, merchants, and ratings",
    icon: ShoppingCart,
    color: "from-amber-500 to-orange-500",
    bgGlow: "bg-amber-500/10",
    textColor: "text-amber-400",
    borderColor: "border-amber-500/20",
    status: "coming-soon",
  },
  {
    id: "google-maps",
    name: "Google Maps",
    description: "Business listings with addresses, ratings, reviews, and coordinates",
    icon: MapPin,
    color: "from-emerald-500 to-green-500",
    bgGlow: "bg-emerald-500/10",
    textColor: "text-emerald-400",
    borderColor: "border-emerald-500/20",
    status: "coming-soon",
  },
  {
    id: "google-news",
    name: "Google News",
    description: "News articles with sources, dates, and snippets",
    icon: Newspaper,
    color: "from-violet-500 to-purple-500",
    bgGlow: "bg-violet-500/10",
    textColor: "text-violet-400",
    borderColor: "border-violet-500/20",
    status: "coming-soon",
  },
  {
    id: "google-jobs",
    name: "Google Jobs",
    description: "Job listings with company, location, salary, and requirements",
    icon: Briefcase,
    color: "from-pink-500 to-rose-500",
    bgGlow: "bg-pink-500/10",
    textColor: "text-pink-400",
    borderColor: "border-pink-500/20",
    status: "coming-soon",
  },
  {
    id: "amazon-product",
    name: "Amazon Product",
    description: "Product details with pricing, reviews, images, and ASIN data",
    icon: Package,
    color: "from-orange-500 to-yellow-500",
    bgGlow: "bg-orange-500/10",
    textColor: "text-orange-400",
    borderColor: "border-orange-500/20",
    status: "coming-soon",
  },
  {
    id: "linkedin-profile",
    name: "LinkedIn Profile",
    description: "Professional profiles with experience, education, and skills",
    icon: Linkedin,
    color: "from-blue-500 to-indigo-500",
    bgGlow: "bg-blue-500/10",
    textColor: "text-blue-400",
    borderColor: "border-blue-500/20",
    status: "coming-soon",
  },
];

export default function ScrapperPoolPage() {
  const router = useRouter();
  const [hoveredApi, setHoveredApi] = useState<string | null>(null);

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-7xl mx-auto">

          {/* Header */}
          <div className="mb-10 animate-float-in">
            <div className="flex items-center gap-3 mb-1">
              <div className="h-9 w-9 rounded-xl bg-cyan-500/10 grid place-items-center">
                <Layers className="h-4.5 w-4.5 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Scrapper Pool</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Domain-specific scraping APIs — structured data from any platform
                </p>
              </div>
            </div>
          </div>

          {/* Stats bar */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="border border-white/[0.06] rounded-lg p-4 bg-white/[0.02]">
              <p className="text-[11px] uppercase tracking-widest text-white/40 font-mono mb-1">Total APIs</p>
              <p className="text-2xl font-bold">{SCRAPER_APIS.length}</p>
            </div>
            <div className="border border-white/[0.06] rounded-lg p-4 bg-white/[0.02]">
              <p className="text-[11px] uppercase tracking-widest text-white/40 font-mono mb-1">Active</p>
              <p className="text-2xl font-bold text-emerald-400">
                {SCRAPER_APIS.filter((a) => a.status === "active").length}
              </p>
            </div>
            <div className="border border-white/[0.06] rounded-lg p-4 bg-white/[0.02]">
              <p className="text-[11px] uppercase tracking-widest text-white/40 font-mono mb-1">Coming Soon</p>
              <p className="text-2xl font-bold text-amber-400">
                {SCRAPER_APIS.filter((a) => a.status === "coming-soon").length}
              </p>
            </div>
          </div>

          {/* API Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {SCRAPER_APIS.map((scraperApi) => {
              const Icon = scraperApi.icon;
              const isHovered = hoveredApi === scraperApi.id;
              const isActive = scraperApi.status === "active";

              return (
                <div
                  key={scraperApi.id}
                  className={`
                    group relative border rounded-xl p-5 transition-all duration-300 cursor-pointer
                    ${scraperApi.borderColor} bg-white/[0.02]
                    hover:bg-white/[0.04] hover:border-white/20
                    ${isActive ? "" : "opacity-70 hover:opacity-100"}
                  `}
                  onMouseEnter={() => setHoveredApi(scraperApi.id)}
                  onMouseLeave={() => setHoveredApi(null)}
                  onClick={() => {
                    if (isActive) {
                      router.push(`/scrapper-pool/${scraperApi.id}`);
                    }
                  }}
                >
                  {/* Glow effect on hover */}
                  <div
                    className={`
                      absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500
                      bg-gradient-to-br ${scraperApi.color} blur-xl -z-10
                    `}
                    style={{ opacity: isHovered ? 0.05 : 0 }}
                  />

                  <div className="flex items-start justify-between mb-3">
                    <div className={`h-10 w-10 rounded-lg ${scraperApi.bgGlow} grid place-items-center`}>
                      <Icon className={`h-5 w-5 ${scraperApi.textColor}`} />
                    </div>
                    {isActive ? (
                      <span className="text-[10px] uppercase tracking-widest text-emerald-400 border border-emerald-500/20 rounded-full px-2.5 py-0.5 bg-emerald-500/10 font-mono">
                        Active
                      </span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-widest text-white/30 border border-white/10 rounded-full px-2.5 py-0.5 bg-white/[0.03] font-mono">
                        Soon
                      </span>
                    )}
                  </div>

                  <h3 className="text-base font-semibold mb-1">{scraperApi.name}</h3>
                  <p className="text-xs text-white/40 leading-relaxed mb-4">{scraperApi.description}</p>

                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-widest text-white/20 font-mono">
                      /v1/data/{scraperApi.id.replace("-", "/")}
                    </span>
                    {isActive && (
                      <ChevronRight className="h-4 w-4 text-white/20 group-hover:text-white/50 transition-colors" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
