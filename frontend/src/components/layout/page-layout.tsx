"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";

type NavPage = "dashboard" | "playground" | "docs" | "jobs";

const NAV_LINKS: { id: NavPage; label: string; href: string }[] = [
  { id: "dashboard", label: "Dashboard", href: "/dashboard" },
  { id: "playground", label: "Playground", href: "/playground" },
  { id: "docs", label: "API Docs", href: "/docs" },
  { id: "jobs", label: "Jobs", href: "/jobs" },
];

const TICKER_ITEMS = [
  { label: "PAGES_SCRAPED", value: "14,203", color: "text-emerald-400", prefix: "▲ " },
  { label: "AVG_RESPONSE", value: "2.3s", color: "text-white/50" },
  { label: "SUCCESS_RATE", value: "98.7%", color: "text-emerald-400", prefix: "▲ " },
  { label: "ANTI_BOT_BYPASS", value: "ACTIVE", color: "text-emerald-400" },
  { label: "WORKERS", value: "4/4", color: "text-white/50" },
  { label: "QUEUE", value: "0 pending", color: "text-white/50" },
  { label: "UPTIME", value: "99.9%", color: "text-emerald-400" },
  { label: "PROXY_POOL", value: "ROTATING", color: "text-white/50" },
];

export function PageLayout({
  activePage,
  children,
}: {
  activePage: NavPage;
  children: React.ReactNode;
}) {
  const [mobileNav, setMobileNav] = useState(false);

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      {/* ═══ NAV ═══ */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-[#050505]/95 backdrop-blur-sm">
        <div className="flex items-center justify-between px-6 md:px-10 h-16">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-4 w-4 bg-emerald-500" />
            <span className="text-[18px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
          </Link>
          <div className="hidden md:flex items-center gap-10">
            {NAV_LINKS.map((link) => (
              link.id === activePage ? (
                <span key={link.id} className="text-[12px] uppercase tracking-[0.2em] text-white border-b border-white/40 pb-0.5 font-mono cursor-default">{link.label}</span>
              ) : (
                <Link key={link.id} href={link.href} className="text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white transition-colors font-mono">{link.label}</Link>
              )
            ))}
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
            {NAV_LINKS.map((link) => (
              link.id === activePage ? (
                <span key={link.id} className="block text-[12px] uppercase tracking-[0.2em] text-white font-mono py-2">{link.label}</span>
              ) : (
                <Link key={link.id} href={link.href} className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">{link.label}</Link>
              )
            ))}
            <Link href="/settings" className="block text-[12px] uppercase tracking-[0.2em] text-white/50 hover:text-white font-mono py-2">Settings</Link>
          </div>
        )}
      </nav>

      {/* ═══ TICKER ═══ */}
      <div className="fixed top-16 left-0 right-0 z-40 border-b border-white/[0.06] bg-[#050505] overflow-hidden h-8 flex items-center">
        <div className="flex whitespace-nowrap animate-ticker-slide">
          {[0, 1].map((dup) => (
            <div key={dup} className="flex">
              {TICKER_ITEMS.map((item, i) => (
                <span key={`${dup}-${i}`} className="text-[11px] tracking-wider mx-8 text-white/30 font-mono">
                  {item.label} <span className={item.color}>{item.prefix || ""}{item.value}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ MAIN ═══ */}
      <main className="pt-28">
        {/* Grid bg */}
        <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />
        <div className="relative z-10">
          {children}
        </div>
      </main>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-white/[0.06] relative z-10">
        <div className="flex flex-col md:flex-row items-center justify-between px-6 md:px-10 max-w-[1400px] mx-auto py-8 gap-4">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="h-3 w-3 bg-emerald-500" />
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
