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
} from "lucide-react";

const modes = [
  { id: "scrape", label: "Scrape", icon: Search },
  { id: "search", label: "Search", icon: Radar },
  { id: "map", label: "Map", icon: Map },
  { id: "crawl", label: "Crawl", icon: Globe },
  { id: "batch", label: "Batch", icon: Layers },
];

function ModeSwitcherInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  // Determine active mode from query param when on /playground
  const isPlayground = pathname === "/playground";
  const endpointParam = searchParams.get("endpoint");
  const activeMode = isPlayground ? (endpointParam || "scrape") : undefined;

  const handleClick = (modeId: string) => {
    // Always navigate to /playground with the endpoint query param
    router.push(`/playground?endpoint=${modeId}`);
  };

  return (
    <div className="flex justify-center">
      <div className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-card/80 backdrop-blur-sm p-1">
        {modes.map((mode) => {
          const isActive = activeMode === mode.id;
          return (
            <button
              key={mode.id}
              onClick={() => handleClick(mode.id)}
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

export function ModeSwitcher() {
  return (
    <Suspense fallback={null}>
      <ModeSwitcherInner />
    </Suspense>
  );
}
