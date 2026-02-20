"use client";

import { useState, useEffect, createContext, useContext, useRef } from "react";
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
  Flame,
  Menu,
  X,
  User,
  ChevronLeft,
  Moon,
  Sun,
  Monitor,
  Activity,
} from "lucide-react";
import { api } from "@/lib/api";

const navSections = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Home", icon: Home },
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
    ],
  },
  {
    label: "Management",
    items: [
      { href: "/jobs", label: "Jobs", icon: History },
      { href: "/dashboard", label: "Activity Logs", icon: Activity },
    ],
  },
  {
    label: "Configure",
    items: [
      { href: "/api-keys", label: "API Keys", icon: Key },
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

// Account popup component
function AccountPopup({
  user,
  onClose,
  popupRef,
}: {
  user: { email: string; name?: string } | null;
  onClose: () => void;
  popupRef: React.RefObject<HTMLDivElement>;
}) {
  const handleLogout = () => {
    api.clearToken();
    window.location.href = "/auth/login";
  };

  return (
    <div
      ref={popupRef}
      className="absolute bottom-16 left-2 w-64 rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/40 z-[60] animate-scale-in overflow-hidden"
      style={{ transformOrigin: "bottom left" }}
    >
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-border/40">
        <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50 mb-2">
          Welcome back
        </p>
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-full bg-primary/15 grid place-items-center shrink-0">
            <User className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{user?.name || "User"}</p>
            <p className="text-[11px] text-muted-foreground/60 truncate">{user?.email}</p>
          </div>
        </div>
      </div>

      {/* Usage Stats */}
      <div className="px-4 py-3 border-b border-border/40 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground/70">Subscription</span>
          <span className="text-[11px] font-medium text-primary">Self-Hosted</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground/70">Plan</span>
          <span className="text-[11px] font-medium">Unlimited</span>
        </div>
      </div>

      {/* Links */}
      <div className="p-2">
        <Link
          href="/settings"
          onClick={onClose}
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <Settings className="h-3.5 w-3.5" />
          Settings
        </Link>
        <Link
          href="/api-keys"
          onClick={onClose}
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <Key className="h-3.5 w-3.5" />
          API Keys
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
          Log out
        </button>
      </div>
    </div>
  );
}

// Inline theme toggle for sidebar (icon-only when collapsed)
function SidebarThemeToggle({ collapsed }: { collapsed: boolean }) {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("dark");

  useEffect(() => {
    const stored = localStorage.getItem("wh_theme") as "light" | "dark" | "system" | null;
    if (stored) {
      setTheme(stored);
      applyTheme(stored);
    }
  }, []);

  const applyTheme = (t: "light" | "dark" | "system") => {
    const root = document.documentElement;
    if (t === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.toggle("dark", prefersDark);
      root.classList.toggle("light", !prefersDark);
    } else {
      root.classList.toggle("dark", t === "dark");
      root.classList.toggle("light", t === "light");
    }
  };

  const cycleTheme = () => {
    const order: ("light" | "dark" | "system")[] = ["dark", "light", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    localStorage.setItem("wh_theme", next);
    applyTheme(next);
  };

  const icon =
    theme === "dark" ? <Moon className="h-4 w-4 shrink-0" /> :
    theme === "light" ? <Sun className="h-4 w-4 shrink-0" /> :
    <Monitor className="h-4 w-4 shrink-0" />;

  const label =
    theme === "dark" ? "Dark" :
    theme === "light" ? "Light" :
    "System";

  return (
    <button
      onClick={cycleTheme}
      className={cn(
        "flex items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
        collapsed
          ? "w-9 h-9 justify-center mx-auto"
          : "w-full gap-2.5 px-2 py-1.5 text-[13px] font-medium"
      )}
      title={`Theme: ${label}`}
    >
      {icon}
      {!collapsed && <span className="whitespace-nowrap overflow-hidden">{label}</span>}
    </button>
  );
}

function DesktopSidebar() {
  const pathname = usePathname();
  const [hovered, setHovered] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [user, setUser] = useState<{ email: string; name?: string } | null>(null);
  const popupRef = useRef<HTMLDivElement>(null!);
  // eslint-disable-next-line

  useEffect(() => {
    api.getMe().then(setUser).catch(() => {});
  }, []);

  // Close account popup when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setShowAccount(false);
      }
    }
    if (showAccount) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showAccount]);

  const collapsed = !hovered;
  const sidebarWidth = collapsed ? 60 : 240;

  return (
    <aside
      className="hidden lg:flex h-screen flex-col border-r border-border/50 bg-sidebar shrink-0 relative z-30 select-none"
      style={{
        width: sidebarWidth,
        transition: "width 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setShowAccount(false);
      }}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex h-14 items-center border-b border-border/40 shrink-0 overflow-hidden",
          collapsed ? "justify-center px-0" : "gap-2.5 px-4"
        )}
      >
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 shrink-0">
          <Flame className="h-4.5 w-4.5 text-primary" />
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight whitespace-nowrap overflow-hidden">
            WebHarvest
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto overflow-x-hidden">
        {navSections.map((section) => (
          <div key={section.label} className="mb-3">
            {!collapsed && (
              <p className="px-4 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/40">
                {section.label}
              </p>
            )}
            {collapsed && <div className="h-px bg-border/30 mx-3 mb-2 mt-1" />}
            <div className={cn("space-y-0.5", collapsed ? "px-2" : "px-3")}>
              {section.items.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center rounded-lg transition-all duration-150 group relative",
                      collapsed
                        ? "w-9 h-9 justify-center mx-auto"
                        : "gap-2.5 px-2.5 py-1.5 text-[13px] font-medium",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    <item.icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        isActive && "text-primary"
                      )}
                    />
                    {!collapsed && (
                      <span className="whitespace-nowrap overflow-hidden">
                        {item.label}
                      </span>
                    )}
                    {/* Active indicator bar */}
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-primary" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer: Theme + Account */}
      <div className="border-t border-border/40 shrink-0 overflow-hidden relative">
        <div className={cn("py-2", collapsed ? "px-2" : "px-3")}>
          <SidebarThemeToggle collapsed={collapsed} />
        </div>

        {/* User account button */}
        <div className={cn("pb-3", collapsed ? "px-2" : "px-3")}>
          <button
            onClick={() => setShowAccount(!showAccount)}
            className={cn(
              "flex items-center rounded-lg transition-all duration-150 w-full",
              collapsed
                ? "w-9 h-9 justify-center mx-auto"
                : "gap-2.5 px-2.5 py-1.5",
              showAccount
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            title={collapsed ? (user?.email || "Account") : undefined}
          >
            <div className="h-6 w-6 rounded-full bg-primary/15 grid place-items-center shrink-0">
              <User className="h-3 w-3 text-primary" />
            </div>
            {!collapsed && (
              <span className="text-[12px] font-medium truncate min-w-0">
                {user?.email || "Account"}
              </span>
            )}
          </button>
        </div>

        {/* Account popup */}
        {showAccount && (
          <AccountPopup
            user={user}
            onClose={() => setShowAccount(false)}
            popupRef={popupRef}
          />
        )}
      </div>
    </aside>
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

function MobileSidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const [user, setUser] = useState<{ email: string; name?: string } | null>(null);

  useEffect(() => {
    api.getMe().then(setUser).catch(() => {});
  }, []);

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
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/" && pathname.startsWith(item.href));
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
                    <item.icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        isActive && "text-primary"
                      )}
                    />
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
        {user && (
          <div className="flex items-center gap-2 px-2 py-1.5 mb-1">
            <div className="h-6 w-6 rounded-full bg-primary/15 grid place-items-center">
              <User className="h-3 w-3 text-primary" />
            </div>
            <span className="text-[12px] text-muted-foreground truncate">{user.email}</span>
          </div>
        )}
        <SidebarThemeToggle collapsed={false} />
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
      {/* Desktop sidebar - hover expandable */}
      <DesktopSidebar />

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
        <MobileSidebarContent onNavigate={() => setOpen(false)} />
      </aside>
    </>
  );
}
