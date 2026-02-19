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

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/scrape", label: "Scrape", icon: Search },
  { href: "/crawl", label: "Crawl", icon: Globe },
  { href: "/batch", label: "Batch", icon: Layers },
  { href: "/search", label: "Search", icon: Search },
  { href: "/map", label: "Map", icon: Map },
  { href: "/extract", label: "Extract", icon: Sparkles },
  { href: "/monitors", label: "Monitors", icon: Eye },
  { href: "/jobs", label: "Jobs", icon: History },
  { href: "/schedules", label: "Schedules", icon: Clock },
  { href: "/webhooks", label: "Webhooks", icon: Webhook },
  { href: "/api-keys", label: "API Keys", icon: Key },
  { href: "/docs", label: "API Docs", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = () => {
    api.clearToken();
    window.location.href = "/auth/login";
  };

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-border/50 bg-card/80 backdrop-blur-sm">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2.5 border-b border-border/50 px-5">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 border border-primary/20">
          <Globe className="h-4 w-4 text-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold tracking-tight">WebHarvest</span>
          <span className="text-[10px] text-foreground/40">v0.1.0</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition-all duration-200",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-foreground/50 hover:bg-foreground/[0.04] hover:text-foreground/80"
              )}
            >
              <item.icon className={cn("h-4 w-4", isActive ? "text-primary" : "text-foreground/40")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border/50 p-3 space-y-0.5">
        <ThemeToggle />
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium text-foreground/50 transition-all duration-200 hover:bg-red-500/10 hover:text-red-400"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
