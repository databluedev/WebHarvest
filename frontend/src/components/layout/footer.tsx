"use client";

import Link from "next/link";
import { Flame } from "lucide-react";

const footerLinks = [
  {
    label: "Product",
    links: [
      { text: "Scrape", href: "/playground?endpoint=scrape" },
      { text: "Crawl", href: "/playground?endpoint=crawl" },
      { text: "Map", href: "/playground?endpoint=map" },
      { text: "Search", href: "/playground?endpoint=search" },
    ],
  },
  {
    label: "Resources",
    links: [
      { text: "API Docs", href: "/docs" },
      { text: "Dashboard", href: "/dashboard" },
      { text: "Jobs", href: "/jobs" },
      { text: "Schedules", href: "/schedules" },
    ],
  },
  {
    label: "Tools",
    links: [
      { text: "API Keys", href: "/api-keys" },
      { text: "Settings", href: "/settings" },
      { text: "Monitors", href: "/monitors" },
      { text: "Webhooks", href: "/webhooks" },
    ],
  },
  {
    label: "Connect",
    links: [
      { text: "GitHub", href: "https://github.com/Takezo49/DataBlue" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-border/30 mt-16">
      <div className="max-w-6xl mx-auto px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          {/* Brand */}
          <div className="col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <div className="h-7 w-7 rounded-lg bg-primary/10 grid place-items-center">
                <Flame className="h-4 w-4 text-primary" />
              </div>
              <span className="text-sm font-semibold tracking-tight">DataBlue</span>
            </div>
            <p className="text-[12px] text-muted-foreground/60 leading-relaxed max-w-xs">
              Open-source web scraping platform with multi-strategy anti-detection.
              Self-hosted, no limits, no vendor lock-in.
            </p>
          </div>

          {/* Link Columns */}
          {footerLinks.map((section) => (
            <div key={section.label}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/40 mb-3">
                {section.label}
              </p>
              <ul className="space-y-2">
                {section.links.map((link) => (
                  <li key={link.text}>
                    {link.href.startsWith("http") ? (
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[13px] text-muted-foreground/60 hover:text-foreground transition-colors"
                      >
                        {link.text}
                      </a>
                    ) : (
                      <Link
                        href={link.href}
                        className="text-[13px] text-muted-foreground/60 hover:text-foreground transition-colors"
                      >
                        {link.text}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-10 pt-6 border-t border-border/20 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-[11px] text-muted-foreground/40">
            &copy; {new Date().getFullYear()} DataBlue. All rights reserved.
          </p>
          <div className="flex items-center gap-3">
            {/* GitHub */}
            <a
              href="https://github.com/Takezo49/DataBlue"
              target="_blank"
              rel="noopener noreferrer"
              className="h-8 w-8 rounded-full bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
            >
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
