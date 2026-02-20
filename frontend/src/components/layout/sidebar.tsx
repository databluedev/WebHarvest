"use client";

import { useState, useEffect, createContext, useContext } from "react";
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
  Menu,
  X,
  Flame,
  ChevronLeft,
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
    label: "Playground",
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
    label: "Configure",
    items: [
      { href: "/api-keys", label: "API Keys", icon: Key },
      { href: "/docs", label: "Docs", icon: FileText },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

// Context for mobile menu state
const SidebarContext = createContext<{
  open: boolean;
  setOpen: (v: boolean) => void;
}>({ open: false, setOpen: () => {} });

export function useSidebar() {
  return useContext(SidebarContext);
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  const handleLogout = () => {
    api.clearToken();
    window.location.href = "/auth/login";
  };

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-border shrink-0">
        <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10">
          <Flame className="h-4 w-4 text-primary" />
        </div>
        <span className="text-sm font-semibold tracking-tight">WebHarvest</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-4">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-2 mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <item.icon className={cn("h-4 w-4 shrink-0", isActive && "text-primary")} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3 space-y-0.5 shrink-0">
        <ThemeToggle />
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </div>
  );
}

export function MobileMenuButton() {
  const { open, setOpen } = useSidebar();

  return (
    <button
      onClick={() => setOpen(!open)}
      className="lg:hidden fixed top-3 left-3 z-50 flex items-center justify-center w-9 h-9 rounded-md bg-card border border-border text-muted-foreground hover:text-foreground transition-colors"
      aria-label="Toggle menu"
    >
      {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
    </button>
  );
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Close mobile menu on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <SidebarContext.Provider value={{ open, setOpen }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function Sidebar() {
  const { open, setOpen } = useSidebar();

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex h-screen w-[240px] flex-col border-r border-border bg-sidebar shrink-0">
        <SidebarContent />
      </aside>

      {/* Mobile overlay */}
      {open && (
        <div className="sidebar-overlay" onClick={() => setOpen(false)} />
      )}

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[260px] bg-sidebar border-r border-border transform transition-transform duration-200 ease-out lg:hidden",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <SidebarContent onNavigate={() => setOpen(false)} />
      </aside>
    </>
  );
}
