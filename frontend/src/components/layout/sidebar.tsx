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
  LayoutDashboard,
  Bug,
  LogOut,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scrape", label: "Scrape", icon: Search },
  { href: "/crawl", label: "Crawl", icon: Globe },
  { href: "/batch", label: "Batch", icon: Layers },
  { href: "/search", label: "Search", icon: Search },
  { href: "/map", label: "Map", icon: Map },
  { href: "/jobs", label: "Jobs", icon: History },
  { href: "/api-keys", label: "API Keys", icon: Key },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = () => {
    api.clearToken();
    window.location.href = "/auth/login";
  };

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Bug className="h-6 w-6 text-primary" />
        <span className="text-xl font-bold">WebHarvest</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
        <p className="mt-3 px-3 text-xs text-muted-foreground">
          WebHarvest v0.1.0
        </p>
      </div>
    </aside>
  );
}
