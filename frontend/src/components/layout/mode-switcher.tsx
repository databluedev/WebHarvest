"use client";

import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Search,
  Globe,
  Map,
  Layers,
  Radar,
} from "lucide-react";

const modes = [
  { id: "scrape", label: "Scrape", icon: Search, href: "/scrape" },
  { id: "search", label: "Search", icon: Radar, href: "/search" },
  { id: "map", label: "Map", icon: Map, href: "/map" },
  { id: "crawl", label: "Crawl", icon: Globe, href: "/crawl" },
  { id: "batch", label: "Batch", icon: Layers, href: "/batch" },
];

export function ModeSwitcher() {
  const pathname = usePathname();
  const router = useRouter();

  const activeMode = modes.find(
    (m) => pathname === m.href || pathname.startsWith(m.href + "/")
  )?.id;

  return (
    <div className="flex justify-center">
      <div className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-card/80 backdrop-blur-sm p-1">
        {modes.map((mode) => {
          const isActive = activeMode === mode.id;
          return (
            <button
              key={mode.id}
              onClick={() => router.push(mode.href)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-medium transition-all duration-200",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <mode.icon className="h-3.5 w-3.5" />
              <span>{mode.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
