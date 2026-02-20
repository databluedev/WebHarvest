"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Globe,
  Search,
  Map,
  History,
  Key,
  Settings,
  Home,
  LogOut,
  Layers,
  Clock,
  BarChart3,
  FileText,
  Eye,
  Webhook,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

const navSections = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Home", icon: Home },
      { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/scrape", label: "Scrape", icon: Search },
      { href: "/crawl", label: "Crawl", icon: Globe },
      { href: "/batch", label: "Batch", icon: Layers },
      { href: "/search", label: "Search", icon: Search },
      { href: "/map", label: "Map", icon: Map },
      { href: "/extract", label: "Extract", icon: Sparkles },
    ],
  },
  {
    label: "Management",
    items: [
      { href: "/monitors", label: "Monitors", icon: Eye },
      { href: "/jobs", label: "Jobs", icon: History },
      { href: "/schedules", label: "Schedules", icon: Clock },
      { href: "/webhooks", label: "Webhooks", icon: Webhook },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/api-keys", label: "API Keys", icon: Key },
      { href: "/docs", label: "API Docs", icon: FileText },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = () => {
    api.clearToken();
    window.location.href = "/auth/login";
  };

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-border/40 bg-card/60 backdrop-blur-sm">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border/40 px-5">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 border border-primary/20">
          <Globe className="h-4 w-4 text-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold tracking-tight gradient-text">WebHarvest</span>
          <span className="text-[10px] text-muted-foreground/60">v0.1.0</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-4">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground/50">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground/80"
                    )}
                  >
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-r-full bg-primary" />
                    )}
                    <item.icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground/60")} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border/40 p-3 space-y-0.5">
        <ThemeToggle />
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-muted-foreground transition-all duration-150 hover:bg-red-500/10 hover:text-red-400"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
