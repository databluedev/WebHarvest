"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Scroll reveal ──────────────────────────────────────────

function useReveal(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.unobserve(e.target); } },
      { threshold, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, visible } = useReveal();
  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-700",
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8",
        className
      )}
      style={{ transitionDelay: `${delay}ms`, transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
    >
      {children}
    </div>
  );
}

// ── Data ───────────────────────────────────────────────────

const FEATURES = [
  { icon: "⚡", title: "RESTful API", desc: "Clean, well-documented endpoints for every operation. Scrape, crawl, map, search, and extract — all from a single unified API.", tag: "// /v1/scrape, /v1/crawl, /v1/map" },
  { icon: "🛡", title: "5-Tier Pipeline", desc: "Parallel race across HTTP, curl-impersonate, stealth Chromium, Camoufox Firefox, and stealth engine. Fastest valid response wins.", tag: "// anti-detection at every layer" },
  { icon: "🕸", title: "Smart Crawling", desc: "BFS and DFS strategies with configurable depth, concurrency, path filters, and robots.txt compliance. Producer-consumer architecture.", tag: "// max_depth, max_pages, concurrency" },
  { icon: "🧠", title: "AI Extraction", desc: "Define a schema, get structured data. LLM-powered extraction turns any webpage into clean JSON. Works with any OpenAI-compatible API.", tag: "// schema in, structured data out" },
  { icon: "🔓", title: "Anti-Bot Bypass", desc: "Cloudflare challenges, Turnstile CAPTCHAs, session gates. Automated solving with human-like mouse movement and browser fingerprinting.", tag: "// cloudflare, turnstile, datadome" },
  { icon: "📡", title: "Real-time Webhooks", desc: "Get notified on crawl completion, page changes, and monitor alerts. HMAC-signed payloads with configurable retry logic.", tag: "// webhooks, monitors, schedules" },
];

const STEPS = [
  {
    num: "01", title: "Deploy", desc: "One command spins up the entire stack — API, workers, database, cache, and browser pool.",
    code: (
      <>
        <span className="text-emerald-500">$</span> <span className="text-muted-foreground">git clone https://github.com/webharvest</span>{"\n"}
        <span className="text-emerald-500">$</span> <span className="text-muted-foreground">cd webharvest</span>{"\n"}
        <span className="text-emerald-500">$</span> <span className="text-muted-foreground">docker compose up -d</span>{"\n"}
        <span className="text-emerald-500">✓ backend     ready  :8000</span>{"\n"}
        <span className="text-emerald-500">✓ worker x2   ready  (8 concurrency)</span>{"\n"}
        <span className="text-emerald-500">✓ frontend    ready  :3000</span>
      </>
    ),
  },
  {
    num: "02", title: "Scrape", desc: "Hit the API with any URL. The pipeline selects the optimal strategy automatically.",
    code: (
      <>
        <span className="text-emerald-500">POST</span> <span className="text-amber-500">/v1/scrape</span>{"\n"}
        {"{"}{"\n"}
        {"  "}<span className="text-emerald-500">&quot;url&quot;</span>: <span className="text-amber-500">&quot;https://example.com&quot;</span>,{"\n"}
        {"  "}<span className="text-emerald-500">&quot;formats&quot;</span>: [<span className="text-amber-500">&quot;markdown&quot;</span>],{"\n"}
        {"  "}<span className="text-emerald-500">&quot;onlyMainContent&quot;</span>: <span className="text-muted-foreground">true</span>{"\n"}
        {"}"}
      </>
    ),
  },
  {
    num: "03", title: "Extract", desc: "Get clean markdown, HTML, screenshots, or AI-extracted structured data back instantly.",
    code: (
      <>
        {"{"}{"\n"}
        {"  "}<span className="text-emerald-500">&quot;success&quot;</span>: <span className="text-muted-foreground">true</span>,{"\n"}
        {"  "}<span className="text-emerald-500">&quot;data&quot;</span>: {"{"}{"\n"}
        {"    "}<span className="text-emerald-500">&quot;markdown&quot;</span>: <span className="text-amber-500">&quot;# Example...&quot;</span>,{"\n"}
        {"    "}<span className="text-emerald-500">&quot;metadata&quot;</span>: {"{"}{"\n"}
        {"      "}<span className="text-emerald-500">&quot;statusCode&quot;</span>: <span className="text-indigo-400">200</span>,{"\n"}
        {"      "}<span className="text-emerald-500">&quot;title&quot;</span>: <span className="text-amber-500">&quot;Example&quot;</span>{"\n"}
        {"    }"}{"\n"}
        {"  }"}{"\n"}
        {"}"}
      </>
    ),
  },
];

const TICKER_ITEMS = [
  { label: "PAGES_SCRAPED", value: "2.4M+", color: "text-emerald-500" },
  { label: "ACTIVE_CRAWLS", value: "142", color: "text-emerald-500" },
  { label: "AVG_RESPONSE", value: "1.2s", color: "text-amber-500" },
  { label: "UPTIME", value: "99.9%", color: "text-emerald-500" },
  { label: "ANTI_BOT_BYPASS", value: "94.2%", color: "text-emerald-500" },
  { label: "CONCURRENT_WORKERS", value: "8", color: "text-emerald-500" },
  { label: "QUEUE_DEPTH", value: "23", color: "text-amber-500" },
  { label: "MEMORY", value: "2.1GB", color: "text-emerald-500" },
  { label: "STATUS", value: "■ OPERATIONAL", color: "text-emerald-500" },
];

const CAPABILITIES_LIST = [
  { feature: "Self-Hosted", detail: "Full control over your data and infrastructure" },
  { feature: "Open Source", detail: "MIT License — fork, modify, contribute" },
  { feature: "Unlimited Usage", detail: "$0 forever, no per-page pricing" },
  { feature: "5-Tier Anti-Bot", detail: "HTTP → curl → Chromium → Firefox → Stealth Engine" },
  { feature: "AI Extraction", detail: "Structured data with any OpenAI-compatible LLM" },
  { feature: "Stealth Browsers", detail: "Patchright + Camoufox fingerprint evasion" },
  { feature: "BFS/DFS Crawling", detail: "Configurable depth, concurrency, path filters" },
  { feature: "Real-time Webhooks", detail: "HMAC-signed payloads with retry logic" },
  { feature: "Scheduled Jobs", detail: "Cron-based scraping with monitoring alerts" },
  { feature: "Dashboard UI", detail: "Full Next.js frontend with playground & analytics" },
];

const TESTIMONIALS = [
  { quote: "We switched to WebHarvest and cut our scraping costs to zero. The 5-tier pipeline handles sites that no other tool could even load.", name: "Alex Kim", role: "CTO @ DataStack", initials: "AK" },
  { quote: "We crawl 100K pages daily for our RAG pipeline. WebHarvest on a $40/mo server outperforms what we were paying $800/mo for on managed scraping APIs.", name: "Sarah Reeves", role: "ML Engineer @ NeuralSearch", initials: "SR" },
  { quote: "The Cloudflare bypass actually works. We monitor competitor pricing across 2,000 product pages and WebHarvest handles the anti-bot detection flawlessly.", name: "Marcus Johnson", role: "Lead Dev @ PriceWatch", initials: "MJ" },
];

// ── Logo SVG ──────────────────────────────────────────────

function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" width={size} height={size}>
      <rect x="2" y="2" width="28" height="28" rx="4" stroke="#10b981" strokeWidth="2" />
      <path d="M16 8v16M8 16h16M10 10l12 12M22 10L10 22" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
      <circle cx="16" cy="16" r="3" fill="#10b981" />
    </svg>
  );
}

// ── GitHub Icon ───────────────────────────────────────────

function GitHubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

// ── Main Component ────────────────────────────────────────

export default function LandingPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (token) {
      api.getMe().then(setUser).catch(() => {}).finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, []);

  const ctaHref = user ? "/playground?endpoint=scrape" : "/auth/register";
  const ctaLabel = user ? "Open Playground" : "Deploy Now";

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">

      {/* ═══ NAV ═══ */}
      <nav className="fixed top-0 left-0 right-0 z-50 px-6 backdrop-blur-xl bg-background/80 border-b border-border">
        <div className="max-w-[1280px] mx-auto flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2.5 no-underline text-foreground">
            <Logo />
            <span className="font-display font-extrabold text-lg tracking-[2px]">WEBHARVEST</span>
          </Link>
          <ul className="hidden md:flex items-center gap-8 list-none">
            {[["Features", "#features"], ["How It Works", "#how"], ["Pricing", "#pricing"], ["GitHub", "https://github.com/Takezo49/WebHarvest"]].map(([label, href]) => (
              <li key={label}>
                <a href={href} target={href.startsWith("http") ? "_blank" : undefined} rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
                  className="font-mono text-xs tracking-[1px] uppercase text-muted-foreground hover:text-emerald-500 transition-colors no-underline">
                  {label}
                </a>
              </li>
            ))}
          </ul>
          {authChecked && (
            <Link href={ctaHref}
              className="font-mono text-xs tracking-[1px] uppercase px-5 py-2 border border-emerald-500 text-emerald-500 hover:bg-emerald-500 hover:text-background hover:shadow-[0_0_30px_rgba(16,185,129,0.15)] transition-all no-underline">
              {ctaLabel} →
            </Link>
          )}
        </div>
      </nav>

      {/* ═══ HERO ═══ */}
      <section className="min-h-screen flex items-center pt-16 relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute -top-[50%] -right-[20%] w-[800px] h-[800px] bg-[radial-gradient(circle,rgba(16,185,129,0.15)_0%,transparent_70%)] pointer-events-none" />

        <div className="max-w-[1280px] mx-auto px-6 w-full">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <Reveal>
                <div className="inline-flex items-center gap-2 font-mono text-[11px] tracking-[2px] uppercase text-emerald-500 border border-emerald-900 px-3.5 py-1.5 mb-8 bg-emerald-500/5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-dot" />
                  Open Source · Self-Hosted · Anti-Bot Pipeline
                </div>
              </Reveal>

              <Reveal delay={80}>
                <h1 className="font-display text-[clamp(48px,6vw,82px)] font-extrabold leading-[0.95] tracking-[-2px] mb-7">
                  <span className="block">HARVEST</span>
                  <span className="block animate-gradient-text italic">THE ENTIRE</span>
                  <span className="block">WEB.</span>
                </h1>
              </Reveal>

              <Reveal delay={160}>
                <p className="text-[17px] leading-[1.7] text-muted-foreground max-w-[480px] mb-10">
                  The open-source web scraping platform. Deploy on your infrastructure, scrape at scale with a 5-tier anti-bot pipeline, and extract structured data with AI.
                </p>
              </Reveal>

              <Reveal delay={240}>
                <div className="flex flex-wrap gap-4 mb-10">
                  <Link href={ctaHref}
                    className="font-mono text-[13px] font-semibold tracking-[1px] uppercase px-8 py-3.5 bg-emerald-500 text-background hover:shadow-[0_0_40px_rgba(16,185,129,0.15)] hover:-translate-y-0.5 transition-all no-underline inline-flex items-center gap-2">
                    {ctaLabel} →
                  </Link>
                  <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer"
                    className="font-mono text-[13px] font-medium tracking-[1px] uppercase px-8 py-3.5 border border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground transition-all no-underline inline-flex items-center gap-2">
                    <GitHubIcon /> View on GitHub
                  </a>
                </div>
              </Reveal>

              <Reveal delay={320}>
                <div className="flex items-center gap-5 text-[13px] text-muted-foreground/50">
                  <div className="flex gap-0.5 text-amber-500 text-sm">{"★★★★★"}</div>
                  <span>Trusted by 2,400+ developers</span>
                </div>
              </Reveal>
            </div>

            {/* Hero card */}
            <Reveal delay={160}>
              <div className="animate-landing-float">
                <div className="bg-card border border-border p-6 relative overflow-hidden">
                  {/* Top gradient line */}
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-emerald-500 to-amber-500" />

                  <div className="flex justify-between items-center mb-5">
                    <span className="font-display font-bold text-lg">Live Pipeline</span>
                    <span className="font-mono text-[10px] tracking-[1px] text-emerald-500 bg-emerald-900 px-2 py-0.5">ACTIVE</span>
                  </div>

                  <div className="grid grid-cols-3 gap-3 mb-5">
                    {[
                      { label: "Pages/min", value: "847", cls: "text-emerald-500" },
                      { label: "Success", value: "98.4%", cls: "text-amber-500" },
                      { label: "Avg Resp", value: "1.2s", cls: "text-foreground" },
                    ].map((s) => (
                      <div key={s.label} className="bg-muted border border-border p-3.5">
                        <div className="font-mono text-[10px] tracking-[1px] text-muted-foreground/50 uppercase mb-1.5">{s.label}</div>
                        <div className={cn("font-mono text-[22px] font-bold", s.cls)}>{s.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Terminal */}
                  <div className="bg-muted border border-border p-4">
                    <div className="flex items-center gap-1.5 mb-3">
                      <span className="w-2 h-2 rounded-full bg-red-500" />
                      <span className="w-2 h-2 rounded-full bg-yellow-500" />
                      <span className="w-2 h-2 rounded-full bg-green-500" />
                    </div>
                    <pre className="font-mono text-[11px] leading-[1.6] text-muted-foreground overflow-x-auto whitespace-pre">
                      <span className="text-muted-foreground/50"># Scrape any URL in one call</span>{"\n"}
                      curl <span className="text-amber-500">-X POST</span> http://localhost:8000/v1/scrape \{"\n"}
                      {"  "}<span className="text-amber-500">-H</span> <span className="text-amber-500">&quot;Authorization: Bearer wh_...&quot;</span> \{"\n"}
                      {"  "}<span className="text-amber-500">-d</span> {`'{"url": "https://example.com",`}{"\n"}
                      {"       "}{`"formats": ["markdown"]}'`}
                    </pre>
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═══ TICKER ═══ */}
      <div className="border-t border-b border-border py-3 overflow-hidden whitespace-nowrap bg-card">
        <div className="inline-flex animate-ticker">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span key={i} className="font-mono text-xs tracking-[1px] px-8 text-muted-foreground/50">
              {item.label} <span className={cn("font-semibold", item.color)}>{item.value}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ═══ FEATURES ═══ */}
      <section className="py-28" id="features">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-16">
            <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">Architecture</span></Reveal>
            <Reveal delay={80}><h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4">Built for Scale</h2></Reveal>
            <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7]">A production-grade scraping engine with every layer designed to bypass, extract, and deliver.</p></Reveal>
          </div>

          <div className="landing-feature-grid">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 60}>
                <div className="bg-card p-10 group transition-all duration-300 hover:bg-muted h-full">
                  <div className="w-11 h-11 border border-border flex items-center justify-center mb-6 text-xl text-muted-foreground transition-all duration-300 group-hover:text-emerald-500 group-hover:border-emerald-500 group-hover:shadow-[0_0_20px_rgba(16,185,129,0.15)]">
                    {f.icon}
                  </div>
                  <h3 className="font-display text-lg font-bold mb-3">{f.title}</h3>
                  <p className="text-sm text-muted-foreground leading-[1.7]">{f.desc}</p>
                  <div className="font-mono text-[10px] tracking-[1px] text-muted-foreground/50 mt-4 uppercase">{f.tag}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="py-28 bg-card border-t border-b border-border" id="how">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-16">
            <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">Process</span></Reveal>
            <Reveal delay={80}><h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4">Three Commands to Data</h2></Reveal>
            <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7]">From zero to scraping in under two minutes. No managed service, no per-page pricing.</p></Reveal>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {STEPS.map((step, i) => (
              <Reveal key={step.num} delay={i * 100}>
                <div className="border border-border bg-card p-10 relative overflow-hidden group h-full">
                  <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-400" />
                  <div className="font-mono text-5xl font-bold text-border leading-none mb-6">{step.num}</div>
                  <h3 className="font-display text-[22px] font-bold mb-4">{step.title}</h3>
                  <p className="text-sm text-muted-foreground leading-[1.7] mb-6">{step.desc}</p>
                  <pre className="bg-background border border-border p-4 font-mono text-[11px] leading-[1.7] text-muted-foreground/50 overflow-x-auto whitespace-pre">
                    {step.code}
                  </pre>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ CODE EXAMPLE ═══ */}
      <section className="py-28 bg-card border-b border-border">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-16">
            <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">API</span></Reveal>
            <Reveal delay={80}><h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4">Developer-First API</h2></Reveal>
            <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7]">Clean REST endpoints for every operation. Scrape, crawl, map, and extract with a single POST request.</p></Reveal>
          </div>

          <Reveal delay={160}>
            <div className="grid lg:grid-cols-2 border border-border">
              {/* Request panel */}
              <div className="border-b lg:border-b-0 lg:border-r border-border">
                <div className="font-mono text-[11px] tracking-[1px] uppercase px-5 py-3 border-b border-border text-muted-foreground/50 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Request
                </div>
                <pre className="font-mono text-xs leading-[1.8] p-5 overflow-x-auto text-muted-foreground whitespace-pre"
                  dangerouslySetInnerHTML={{ __html: `<span class="text-emerald-500">import</span> requests

response = requests.post(
    <span class="text-amber-500">"http://localhost:8000/v1/crawl"</span>,
    headers={
        <span class="text-amber-500">"Authorization"</span>: <span class="text-amber-500">"Bearer wh_live_..."</span>
    },
    json={
        <span class="text-amber-500">"url"</span>: <span class="text-amber-500">"https://docs.example.com"</span>,
        <span class="text-amber-500">"maxDepth"</span>: <span class="text-indigo-400">3</span>,
        <span class="text-amber-500">"maxPages"</span>: <span class="text-indigo-400">100</span>,
        <span class="text-amber-500">"scrapeOptions"</span>: {
            <span class="text-amber-500">"formats"</span>: [<span class="text-amber-500">"markdown"</span>],
            <span class="text-amber-500">"onlyMainContent"</span>: <span class="text-emerald-500">True</span>
        }
    }
)
<span class="text-muted-foreground/50"># Returns crawl job ID for async polling</span>
job = response.json()
<span class="text-emerald-500">print</span>(job[<span class="text-amber-500">"id"</span>])  <span class="text-muted-foreground/50"># "9e6c8b0b-..."</span>` }}
                />
              </div>
              {/* Response panel */}
              <div>
                <div className="font-mono text-[11px] tracking-[1px] uppercase px-5 py-3 border-b border-border text-muted-foreground/50 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Response
                </div>
                <pre className="font-mono text-xs leading-[1.8] p-5 overflow-x-auto text-muted-foreground whitespace-pre"
                  dangerouslySetInnerHTML={{ __html: `{
  <span class="text-pink-400">"success"</span>: <span class="text-emerald-500">true</span>,
  <span class="text-pink-400">"id"</span>: <span class="text-amber-500">"9e6c8b0b-bbd6-4b79..."</span>,
  <span class="text-pink-400">"status"</span>: <span class="text-amber-500">"completed"</span>,
  <span class="text-pink-400">"total"</span>: <span class="text-indigo-400">87</span>,
  <span class="text-pink-400">"completed"</span>: <span class="text-indigo-400">87</span>,
  <span class="text-pink-400">"data"</span>: [
    {
      <span class="text-pink-400">"markdown"</span>: <span class="text-amber-500">"# Getting Started\\n\\n..."</span>,
      <span class="text-pink-400">"metadata"</span>: {
        <span class="text-pink-400">"title"</span>: <span class="text-amber-500">"Getting Started"</span>,
        <span class="text-pink-400">"statusCode"</span>: <span class="text-indigo-400">200</span>,
        <span class="text-pink-400">"sourceURL"</span>: <span class="text-amber-500">"https://docs.example.com/start"</span>
      }
    },
    <span class="text-muted-foreground/50">// ... 86 more pages</span>
  ]
}` }}
                />
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ WHY WEBHARVEST ═══ */}
      <section className="py-28" id="compare">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-16">
            <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">Everything Included</span></Reveal>
            <Reveal delay={80}><h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4">Why WebHarvest?</h2></Reveal>
            <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7]">Full control over your scraping infrastructure. No vendor lock-in, no per-page costs, no limits.</p></Reveal>
          </div>

          <Reveal delay={160}>
            <div className="max-w-[700px] mx-auto">
              {CAPABILITIES_LIST.map((cap, i) => (
                <div key={cap.feature} className="flex items-center gap-4 py-4 border-b border-border">
                  <span className="text-emerald-500 font-mono text-sm font-semibold shrink-0">✓</span>
                  <div className="flex-1">
                    <span className="font-display font-bold text-[15px]">{cap.feature}</span>
                    <span className="text-muted-foreground text-sm ml-3">{cap.detail}</span>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ SOCIAL PROOF ═══ */}
      <section className="py-28 bg-card border-t border-b border-border">
        <div className="max-w-[1280px] mx-auto px-6">
          <Reveal>
            <div className="flex flex-col sm:flex-row justify-center gap-16 mb-16 py-10 border-t border-b border-border">
              {[
                { value: "2,400+", label: "GitHub Stars", cls: "text-emerald-500" },
                { value: "180+", label: "Contributors", cls: "text-foreground" },
                { value: "50M+", label: "Pages Scraped", cls: "text-amber-500" },
                { value: "12K+", label: "Deployments", cls: "text-foreground" },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <div className={cn("font-display text-[42px] font-extrabold mb-1", s.cls)}>{s.value}</div>
                  <div className="font-mono text-[11px] tracking-[2px] uppercase text-muted-foreground/50">{s.label}</div>
                </div>
              ))}
            </div>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t, i) => (
              <Reveal key={t.name} delay={i * 100}>
                <div className="border border-border p-8 bg-card relative h-full">
                  <span className="absolute top-5 right-6 font-display text-5xl text-border leading-none">&ldquo;</span>
                  <p className="text-sm text-muted-foreground leading-[1.8] italic mb-6">{t.quote}</p>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-muted border border-border flex items-center justify-center font-mono text-xs font-semibold text-emerald-500">
                      {t.initials}
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold">{t.name}</div>
                      <div className="font-mono text-[11px] text-muted-foreground/50">{t.role}</div>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ PRICING ═══ */}
      <section className="py-28" id="pricing">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-16">
            <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">Pricing</span></Reveal>
            <Reveal delay={80}><h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4">Radically Simple</h2></Reveal>
            <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7]">No per-page pricing. No rate limits you don&apos;t set yourself. Your servers, your rules.</p></Reveal>
          </div>

          <div className="grid md:grid-cols-2 gap-6 max-w-[800px] mx-auto">
            <Reveal>
              <div className="border border-emerald-900 p-12 bg-gradient-to-b from-emerald-500/[0.03] to-card relative h-full">
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-emerald-500" />
                <div className="font-mono text-[11px] tracking-[2px] uppercase text-muted-foreground/50 mb-2">Self-Hosted</div>
                <div className="font-display text-[28px] font-extrabold mb-2">Open Source</div>
                <div className="font-mono text-4xl font-bold mb-2">$0 <span className="text-sm text-muted-foreground/50 font-normal">/ forever</span></div>
                <p className="text-sm text-muted-foreground mb-8 leading-[1.6]">Deploy on your own infrastructure. Full access to every feature, no limits.</p>
                <ul className="list-none mb-8">
                  {["Unlimited scraping & crawling", "All 5 scraping tiers", "AI extraction (bring your LLM key)", "Webhooks, monitors, schedules", "Dashboard UI included", "Docker Compose one-liner deploy", "Community support via GitHub"].map((item) => (
                    <li key={item} className="text-[13px] text-muted-foreground py-2 border-b border-border flex items-center gap-2.5">
                      <span className="font-mono text-xs text-emerald-500">→</span> {item}
                    </li>
                  ))}
                </ul>
                <Link href={ctaHref}
                  className="block text-center font-mono text-xs tracking-[1px] uppercase py-3.5 bg-emerald-500 text-background hover:shadow-[0_0_30px_rgba(16,185,129,0.15)] transition-all no-underline">
                  {ctaLabel} →
                </Link>
              </div>
            </Reveal>

            <Reveal delay={100}>
              <div className="border border-border p-12 bg-card h-full">
                <div className="font-mono text-[11px] tracking-[2px] uppercase text-muted-foreground/50 mb-2">Managed</div>
                <div className="font-display text-[28px] font-extrabold mb-2">Cloud</div>
                <div className="font-mono text-4xl font-bold text-muted-foreground mb-2">Soon <span className="text-sm text-muted-foreground/50 font-normal">/ coming Q2</span></div>
                <p className="text-sm text-muted-foreground mb-8 leading-[1.6]">Managed hosting with zero ops. Same engine, we handle the infrastructure.</p>
                <ul className="list-none mb-8">
                  {["Everything in self-hosted", "Managed infrastructure", "Auto-scaling workers", "Global proxy network", "99.9% SLA", "Priority support", "SOC 2 compliance"].map((item) => (
                    <li key={item} className="text-[13px] text-muted-foreground py-2 border-b border-border flex items-center gap-2.5">
                      <span className="font-mono text-xs text-emerald-500">→</span> {item}
                    </li>
                  ))}
                </ul>
                <button disabled
                  className="w-full text-center font-mono text-xs tracking-[1px] uppercase py-3.5 border border-border text-muted-foreground cursor-not-allowed opacity-60">
                  Join Waitlist
                </button>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="py-28 text-center">
        <div className="max-w-[1280px] mx-auto px-6">
          <Reveal><span className="font-mono text-[11px] tracking-[3px] uppercase text-emerald-500 block mb-4">Ready?</span></Reveal>
          <Reveal delay={80}>
            <h2 className="font-display text-[clamp(32px,4vw,48px)] font-extrabold tracking-[-1px] mb-4 max-w-[600px] mx-auto">
              Start Harvesting<br /><span className="text-emerald-500">in Two Minutes.</span>
            </h2>
          </Reveal>
          <Reveal delay={160}><p className="text-base text-muted-foreground max-w-[560px] mx-auto leading-[1.7] mb-10">One command. Full stack. No credit card, no vendor lock-in.</p></Reveal>
          <Reveal delay={240}>
            <div className="inline-block bg-muted border border-border px-8 py-4 font-mono text-sm mb-8">
              <span className="text-emerald-500">$</span>{" "}
              <span className="text-muted-foreground">docker compose up -d</span>
              <button
                onClick={() => navigator.clipboard.writeText("docker compose up -d")}
                className="ml-4 text-muted-foreground/50 hover:text-muted-foreground transition-colors bg-transparent border-none cursor-pointer"
                title="Copy"
              >
                ⎘
              </button>
            </div>
          </Reveal>
          <Reveal delay={320}>
            <div className="flex flex-wrap gap-4 justify-center">
              <Link href={ctaHref}
                className="font-mono text-[13px] font-semibold tracking-[1px] uppercase px-8 py-3.5 bg-emerald-500 text-background hover:shadow-[0_0_40px_rgba(16,185,129,0.15)] hover:-translate-y-0.5 transition-all no-underline inline-flex items-center gap-2">
                {ctaLabel} →
              </Link>
              <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer"
                className="font-mono text-[13px] font-medium tracking-[1px] uppercase px-8 py-3.5 border border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground transition-all no-underline inline-flex items-center gap-2">
                Read the Docs
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-border pt-16 pb-8">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 mb-12">
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="inline-flex items-center gap-2 mb-4 no-underline text-foreground">
                <Logo size={24} />
                <span className="font-display font-extrabold text-base tracking-[2px]">WEBHARVEST</span>
              </Link>
              <p className="text-sm text-muted-foreground/50 leading-[1.7] max-w-[300px]">
                Open-source web scraping platform. Self-hosted, anti-bot pipeline, built for scale.
              </p>
            </div>
            {[
              { title: "Product", links: [["Features", "#features"], ["Pricing", "#pricing"], ["Changelog", "#"], ["Roadmap", "#"]] },
              { title: "Resources", links: [["Documentation", "#"], ["API Reference", "#"], ["SDK", "#"], ["Examples", "#"]] },
              { title: "Community", links: [["GitHub", "https://github.com/Takezo49/WebHarvest"], ["Discord", "#"], ["Twitter", "#"], ["Contributing", "#"]] },
            ].map((col) => (
              <div key={col.title}>
                <h4 className="font-mono text-[11px] tracking-[2px] uppercase text-muted-foreground/50 mb-5">{col.title}</h4>
                {col.links.map(([text, href]) => (
                  <a key={text} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
                    className="block text-sm text-muted-foreground py-1 hover:text-emerald-500 transition-colors no-underline">
                    {text}
                  </a>
                ))}
              </div>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row justify-between items-center pt-6 border-t border-border gap-4">
            <span className="font-mono text-[11px] text-muted-foreground/50">&copy; {new Date().getFullYear()} WebHarvest. MIT License.</span>
            <div className="flex gap-3">
              {["FastAPI", "Next.js", "Celery", "PostgreSQL"].map((badge) => (
                <span key={badge} className="font-mono text-[10px] tracking-[1px] px-2.5 py-1 border border-border text-muted-foreground/50">
                  {badge}
                </span>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
