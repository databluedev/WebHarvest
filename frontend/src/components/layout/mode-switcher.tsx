"use client";

import { Suspense } from "react";
import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Search,
  Globe,
  Map,
  Layers,
  Radar,
  Crosshair,
  Satellite,
  Network,
  Bug,
} from "lucide-react";

const modes = [
  { id: "scrape", label: "Scrape", icon: Crosshair },
  { id: "search", label: "Search", icon: Satellite },
  { id: "map", label: "Map", icon: Network },
  { id: "crawl", label: "Crawl", icon: Bug },
];

function ModeSwitcherInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  const isPlayground = pathname === "/playground";
  const endpointParam = searchParams.get("endpoint");
  const activeMode = isPlayground ? (endpointParam || "scrape") : undefined;

  const handleClick = (modeId: string) => {
    router.push(`/playground?endpoint=${modeId}`);
  };

  return (
    <div className="flex justify-center">
      <div className="inline-flex items-center gap-1 rounded-2xl border border-border/60 bg-card/70 backdrop-blur-md p-1.5 shadow-lg shadow-black/10">
        {modes.map((mode) => {
          const isActive = activeMode === mode.id;
          return (
            <button
              key={mode.id}
              onClick={() => handleClick(mode.id)}
              className={cn(
                "flex items-center gap-2 rounded-xl px-5 py-2.5 text-[15px] font-semibold transition-all duration-200",
                isActive
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <mode.icon className="h-[18px] w-[18px]" />
              <span>{mode.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ModeSwitcher() {
  return (
    <Suspense fallback={null}>
      <ModeSwitcherInner />
    </Suspense>
  );
}
