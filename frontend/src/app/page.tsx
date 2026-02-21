"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Crosshair,
  Satellite,
  Network,
  Bug,
  Flame,
  ArrowRight,
  Code,
  FileText,
  Braces,
  Camera,
  Shield,
  Shuffle,
  Smartphone,
  Sparkles,
  Globe,
  Zap,
  BarChart3,
  Users,
  Search,
  BookOpen,
  ShoppingCart,
  ChevronDown,
  ChevronUp,
  Terminal,
  Loader2,
  ExternalLink,
  Play,
  CheckCircle2,
  Layers,
  MousePointerClick,
  DatabaseZap,
} from "lucide-react";

// ── Scroll animation hook ──────────────────────────────────

function useScrollReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.unobserve(e.target); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, visible } = useScrollReveal();
  return (
    <div
      ref={ref}
      className={cn("transition-all duration-700 ease-out", visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

// ── Counter animation ──────────────────────────────────────

function AnimatedCounter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  const { ref, visible } = useScrollReveal();

  useEffect(() => {
    if (!visible) return;
    let start = 0;
    const duration = 1500;
    const step = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [visible, target]);

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// ── FAQ Accordion ──────────────────────────────────────────

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border/40 rounded-xl overflow-hidden transition-all hover:border-border/60">
      <button onClick={() => setOpen(!open)} className="flex items-center justify-between w-full px-6 py-5 text-left">
        <span className="text-base font-semibold pr-4">{q}</span>
        {open ? <ChevronUp className="h-5 w-5 text-primary shrink-0" /> : <ChevronDown className="h-5 w-5 text-muted-foreground shrink-0" />}
      </button>
      <div className={cn("grid transition-all duration-300", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div className="overflow-hidden">
          <p className="px-6 pb-5 text-[15px] text-muted-foreground leading-relaxed">{a}</p>
        </div>
      </div>
    </div>
  );
}

// ── Data ───────────────────────────────────────────────────

const MODES = [
  { icon: Crosshair, title: "Scrape", desc: "Extract clean content from any webpage. Get markdown, HTML, screenshots, structured data, and more in a single API call.", color: "from-teal-500/20 to-cyan-500/10" },
  { icon: Bug, title: "Crawl", desc: "Recursively crawl entire websites. Follow links with depth control, concurrent workers, and automatic deduplication.", color: "from-emerald-500/20 to-teal-500/10" },
  { icon: Satellite, title: "Search", desc: "Search the web and scrape every result. Multi-engine support with DuckDuckGo, Brave, and Google integration.", color: "from-cyan-500/20 to-blue-500/10" },
  { icon: Network, title: "Map", desc: "Discover every URL on a website instantly. Sitemap parsing, subdomain discovery, and keyword-based filtering.", color: "from-teal-500/20 to-emerald-500/10" },
];

const CAPABILITIES = [
  { icon: FileText, title: "Smart Parsing", desc: "Automatic main content extraction, boilerplate removal, and clean markdown output with heading structure." },
  { icon: Shield, title: "Anti-Detection", desc: "Browser fingerprint randomization, stealth mode, human-like behavior patterns, and TLS fingerprint spoofing." },
  { icon: Shuffle, title: "Proxy Rotation", desc: "Built-in proxy management with automatic rotation, health checking, and geographic targeting support." },
  { icon: Camera, title: "Screenshots", desc: "Full-page and viewport captures with device emulation. Perfect for visual archiving and monitoring." },
  { icon: Sparkles, title: "LLM Extraction", desc: "AI-powered structured data extraction with custom prompts. Bring your own key for OpenAI, Anthropic, or local models." },
  { icon: Braces, title: "Structured Output", desc: "JSON, markdown, HTML, links, images, and headings. Multiple formats in a single request." },
];

const STEPS = [
  { num: "01", title: "Enter your target", desc: "Paste a URL or search query into the start bar. Choose your extraction mode.", icon: MousePointerClick },
  { num: "02", title: "Configure & launch", desc: "Select output formats, set depth limits, enable AI extraction. Click start.", icon: Zap },
  { num: "03", title: "Get structured data", desc: "Download clean, structured results as JSON, markdown, or screenshots. Use webhooks for automation.", icon: DatabaseZap },
];

const USE_CASES = [
  { icon: BarChart3, title: "Market Research", desc: "Monitor competitors, track pricing changes, and analyze market trends at scale." },
  { icon: Users, title: "Lead Generation", desc: "Extract contact information, company data, and business intelligence from the web." },
  { icon: BookOpen, title: "Content Aggregation", desc: "Collect articles, news, reviews, and publications from hundreds of sources." },
  { icon: ShoppingCart, title: "Price Monitoring", desc: "Track product prices across retailers. Detect changes and compare automatically." },
  { icon: Search, title: "SEO Analysis", desc: "Audit website structure, analyze internal links, and discover optimization opportunities." },
  { icon: Globe, title: "Academic Research", desc: "Gather datasets, collect publications, and archive web content for research." },
];

const FAQS = [
  { q: "Is WebHarvest self-hosted?", a: "Yes, WebHarvest is fully self-hosted. You run it on your own infrastructure with no external dependencies, no vendor lock-in, and no usage limits." },
  { q: "What anti-detection features are included?", a: "WebHarvest includes browser fingerprint randomization, stealth mode with human-like behavior patterns, TLS fingerprint spoofing, and automatic proxy rotation to avoid detection." },
  { q: "Can I use my own proxies?", a: "Absolutely. Configure your own proxy lists in settings, or use the built-in proxy rotation system. Supports HTTP, HTTPS, and SOCKS5 proxies." },
  { q: "What output formats are supported?", a: "Markdown, HTML (cleaned and raw), JSON structured data, screenshots (viewport and full-page), extracted links, images, and heading summaries. Request multiple formats in a single API call." },
  { q: "Does it handle JavaScript-rendered pages?", a: "Yes. WebHarvest uses Playwright for full browser rendering, so it handles SPAs, dynamic content, lazy loading, and any JavaScript-dependent pages." },
  { q: "Is there an API?", a: "Yes, WebHarvest exposes a full REST API with endpoints for scrape, crawl, search, and map operations. Use cURL, Python, Node.js, or any HTTP client." },
];

// ── Main Component ─────────────────────────────────────────

export default function LandingPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (token) {
      api.getMe().then(setUser).catch(() => {}).finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, []);

  const handleScrape = async () => {
    if (!url.trim()) return;
    if (!user) { router.push("/auth/login"); return; }
    setLoading(true);
    try {
      const fullUrl = url.startsWith("http") ? url : `https://${url}`;
      const res = await api.scrape({ url: fullUrl, formats: ["markdown"], only_main_content: true });
      if (res.job_id) router.push(`/scrape/${res.job_id}`);
      else router.push("/playground?endpoint=scrape");
    } catch {
      router.push("/playground?endpoint=scrape");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">

      {/* ════════════════════════════════════════════════════════
          NAVBAR
         ════════════════════════════════════════════════════════ */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border/30 bg-background/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-primary/10 grid place-items-center">
              <Flame className="h-5 w-5 text-primary" />
            </div>
            <span className="text-lg font-bold tracking-tight">WebHarvest</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Features</a>
            <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">How It Works</a>
            <a href="#use-cases" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Use Cases</a>
            <a href="#faq" className="text-sm text-muted-foreground hover:text-foreground transition-colors">FAQ</a>
          </div>

          <div className="flex items-center gap-3">
            {authChecked && user ? (
              <Link href="/playground?endpoint=scrape" className="flex items-center gap-2 h-10 px-5 rounded-lg text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-md shadow-primary/15">
                Go to Playground <ArrowRight className="h-4 w-4" />
              </Link>
            ) : authChecked ? (
              <>
                <Link href="/auth/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors px-3 py-2">
                  Sign In
                </Link>
                <Link href="/auth/register" className="flex items-center gap-2 h-10 px-5 rounded-lg text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-md shadow-primary/15">
                  Get Started
                </Link>
              </>
            ) : null}
          </div>
        </div>
      </nav>

      {/* ════════════════════════════════════════════════════════
          HERO
         ════════════════════════════════════════════════════════ */}
      <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-28">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-primary/[0.04] rounded-full blur-[120px]" />
          <div className="absolute top-40 left-20 w-2 h-2 rounded-full bg-primary/30 animate-pulse" />
          <div className="absolute top-60 right-32 w-1.5 h-1.5 rounded-full bg-primary/20 animate-pulse" style={{ animationDelay: "1s" }} />
          <div className="absolute top-80 left-1/3 w-1 h-1 rounded-full bg-primary/25 animate-pulse" style={{ animationDelay: "2s" }} />
        </div>

        <div className="max-w-5xl mx-auto px-6 lg:px-8 relative">
          {/* Badge */}
          <div className="flex justify-center mb-8 animate-float-in">
            <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-primary/20 bg-primary/5">
              <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              <span className="text-[13px] font-semibold text-primary">Open Source Web Scraping Platform</span>
            </div>
          </div>

          {/* Headline */}
          <h1 className="text-center animate-float-in" style={{ animationDelay: "0.08s" }}>
            <span className="block text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.1]">
              Extract the web
            </span>
            <span className="block text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.1] gradient-text mt-2">
              with precision
            </span>
          </h1>

          <p className="text-center text-lg lg:text-xl text-muted-foreground max-w-2xl mx-auto mt-6 mb-10 animate-float-in leading-relaxed" style={{ animationDelay: "0.15s" }}>
            Scrape, crawl, search, and map any website. Self-hosted, no limits.
            Anti-detection built in. Clean structured data out.
          </p>

          {/* Start Bar */}
          <div className="max-w-2xl mx-auto animate-float-in" style={{ animationDelay: "0.22s" }}>
            <div className="rounded-2xl border border-primary/15 bg-card/80 backdrop-blur-sm p-5 shadow-2xl shadow-primary/5">
              <div className="flex items-center gap-0 rounded-xl bg-background border border-border/50 px-5 h-14 mb-4 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/25 transition-all">
                <span className="text-base text-muted-foreground shrink-0 select-none font-mono">https://</span>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value.replace(/^https?:\/\//, ""))}
                  onKeyDown={(e) => e.key === "Enter" && !loading && handleScrape()}
                  placeholder="example.com"
                  className="flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground/50 ml-1"
                />
                <Crosshair className="h-5 w-5 text-primary/40 shrink-0 ml-2" />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {[
                    { label: "Scrape", icon: Crosshair },
                    { label: "Crawl", icon: Bug },
                    { label: "Search", icon: Satellite },
                    { label: "Map", icon: Network },
                  ].map((m) => (
                    <Link key={m.label} href={`/playground?endpoint=${m.label.toLowerCase()}`} className="flex items-center gap-1.5 h-9 px-3 rounded-lg bg-muted/60 text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all">
                      <m.icon className="h-3.5 w-3.5" /> {m.label}
                    </Link>
                  ))}
                </div>
                <button
                  onClick={handleScrape}
                  disabled={loading || !url.trim()}
                  className="flex items-center gap-2 h-11 rounded-lg px-6 text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/15"
                >
                  {loading ? <Loader2 className="h-[18px] w-[18px] animate-spin" /> : <><Play className="h-4 w-4" /> Start scraping</>}
                </button>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto mt-16 animate-float-in" style={{ animationDelay: "0.3s" }}>
            {[
              { value: 5, suffix: "", label: "Extraction Modes" },
              { value: 7, suffix: "+", label: "Output Formats" },
              { value: 100, suffix: "%", label: "Self-Hosted" },
              { value: 0, suffix: "", label: "Rate Limits", display: "Zero" },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-3xl lg:text-4xl font-extrabold gradient-text">
                  {s.display || <AnimatedCounter target={s.value} suffix={s.suffix} />}
                </div>
                <p className="text-sm text-muted-foreground mt-1 font-medium">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          EXTRACTION MODES
         ════════════════════════════════════════════════════════ */}
      <section id="features" className="py-24 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/[0.02] to-transparent pointer-events-none" />
        <div className="max-w-6xl mx-auto px-6 lg:px-8 relative">
          <Reveal>
            <div className="text-center mb-16">
              <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">Extraction Modes</p>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight">Five ways to harvest data</h2>
              <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">Each mode is purpose-built for a different workflow. Use them individually or combine them for complex pipelines.</p>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {MODES.map((mode, i) => (
              <Reveal key={mode.title} delay={i * 80}>
                <Link href={`/playground?endpoint=${mode.title.toLowerCase()}`} className="group block">
                  <div className={cn("rounded-2xl border border-border/40 p-6 h-full transition-all duration-300 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-1 bg-gradient-to-br", mode.color)}>
                    <div className="h-12 w-12 rounded-xl bg-primary/10 grid place-items-center mb-4 group-hover:bg-primary/15 transition-colors">
                      <mode.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="text-xl font-bold mb-2">{mode.title}</h3>
                    <p className="text-[15px] text-muted-foreground leading-relaxed">{mode.desc}</p>
                    <div className="flex items-center gap-1.5 mt-4 text-sm font-semibold text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                      Try it <ArrowRight className="h-4 w-4" />
                    </div>
                  </div>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          CAPABILITIES
         ════════════════════════════════════════════════════════ */}
      <section className="py-24">
        <div className="max-w-6xl mx-auto px-6 lg:px-8">
          <Reveal>
            <div className="text-center mb-16">
              <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">Capabilities</p>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight">Built for serious scraping</h2>
              <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">Every feature you need to extract data reliably at scale, without getting blocked.</p>
            </div>
          </Reveal>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {CAPABILITIES.map((cap, i) => (
              <Reveal key={cap.title} delay={i * 60}>
                <div className="rounded-2xl border border-border/40 p-6 hover:border-border/60 transition-all duration-300 hover:-translate-y-0.5 h-full">
                  <cap.icon className="h-7 w-7 text-primary mb-4" />
                  <h3 className="text-lg font-bold mb-2">{cap.title}</h3>
                  <p className="text-[15px] text-muted-foreground leading-relaxed">{cap.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          HOW IT WORKS
         ════════════════════════════════════════════════════════ */}
      <section id="how-it-works" className="py-24 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/[0.02] to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto px-6 lg:px-8 relative">
          <Reveal>
            <div className="text-center mb-16">
              <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">How It Works</p>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight">Three steps to clean data</h2>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-8">
            {STEPS.map((step, i) => (
              <Reveal key={step.num} delay={i * 120}>
                <div className="text-center">
                  <div className="relative mx-auto w-20 h-20 rounded-2xl bg-primary/10 grid place-items-center mb-6">
                    <step.icon className="h-9 w-9 text-primary" />
                    <span className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-primary text-primary-foreground text-xs font-bold grid place-items-center shadow-lg shadow-primary/20">
                      {step.num.replace("0", "")}
                    </span>
                  </div>
                  <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                  <p className="text-[15px] text-muted-foreground leading-relaxed">{step.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          CODE / API PREVIEW
         ════════════════════════════════════════════════════════ */}
      <section className="py-24">
        <div className="max-w-6xl mx-auto px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <Reveal>
              <div>
                <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">Developer First</p>
                <h2 className="text-4xl font-extrabold tracking-tight mb-4">Simple, powerful API</h2>
                <p className="text-lg text-muted-foreground leading-relaxed mb-8">
                  One POST request is all it takes. Get clean markdown, structured JSON, screenshots, and more.
                  Works with cURL, Python, Node.js, or any HTTP client.
                </p>
                <div className="flex flex-wrap gap-3">
                  {["REST API", "Webhooks", "JSON Output", "cURL", "Python", "Node.js"].map((t) => (
                    <span key={t} className="px-3.5 py-1.5 rounded-lg bg-muted/60 text-sm font-medium text-muted-foreground border border-border/30">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>

            <Reveal delay={150}>
              <div className="rounded-2xl border border-border/40 bg-card/80 overflow-hidden shadow-2xl shadow-black/20">
                <div className="flex items-center gap-2 px-5 py-3 border-b border-border/30 bg-muted/30">
                  <div className="flex gap-1.5">
                    <div className="h-3 w-3 rounded-full bg-red-500/60" />
                    <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                    <div className="h-3 w-3 rounded-full bg-green-500/60" />
                  </div>
                  <span className="text-xs text-muted-foreground font-mono ml-2">terminal</span>
                </div>
                <pre className="px-5 py-5 text-[13px] leading-relaxed font-mono overflow-x-auto">
                  <code>
                    <span className="text-muted-foreground">$ </span>
                    <span className="text-primary">curl</span>
                    <span className="text-foreground"> -X POST /v1/scrape \</span>
                    {"\n"}
                    <span className="text-foreground">{"  "}-H </span>
                    <span className="text-emerald-400">{'"Content-Type: application/json"'}</span>
                    <span className="text-foreground"> \</span>
                    {"\n"}
                    <span className="text-foreground">{"  "}-d </span>
                    <span className="text-amber-400">{"'"}</span>
                    <span className="text-amber-400">{'{"url": "https://example.com",'}</span>
                    {"\n"}
                    <span className="text-amber-400">{"       "}{'"formats": ["markdown"]}'}</span>
                    <span className="text-amber-400">{"'"}</span>
                    {"\n\n"}
                    <span className="text-muted-foreground">{"// Response:"}</span>
                    {"\n"}
                    <span className="text-foreground">{"{"}</span>
                    {"\n"}
                    <span className="text-foreground">{"  "}</span>
                    <span className="text-cyan-400">{'"success"'}</span>
                    <span className="text-foreground">: </span>
                    <span className="text-emerald-400">true</span>
                    <span className="text-foreground">,</span>
                    {"\n"}
                    <span className="text-foreground">{"  "}</span>
                    <span className="text-cyan-400">{'"data"'}</span>
                    <span className="text-foreground">: {"{"}</span>
                    {"\n"}
                    <span className="text-foreground">{"    "}</span>
                    <span className="text-cyan-400">{'"markdown"'}</span>
                    <span className="text-foreground">: </span>
                    <span className="text-amber-400">{'"# Example Domain\\n..."'}</span>
                    {"\n"}
                    <span className="text-foreground">{"  }"}</span>
                    {"\n"}
                    <span className="text-foreground">{"}"}</span>
                  </code>
                </pre>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          USE CASES
         ════════════════════════════════════════════════════════ */}
      <section id="use-cases" className="py-24 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/[0.02] to-transparent pointer-events-none" />
        <div className="max-w-6xl mx-auto px-6 lg:px-8 relative">
          <Reveal>
            <div className="text-center mb-16">
              <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">Use Cases</p>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight">Built for every workflow</h2>
              <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">From market research to academic data collection, WebHarvest adapts to your needs.</p>
            </div>
          </Reveal>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {USE_CASES.map((uc, i) => (
              <Reveal key={uc.title} delay={i * 60}>
                <div className="rounded-2xl border border-border/40 p-6 hover:border-primary/20 transition-all duration-300 hover:-translate-y-0.5 h-full group">
                  <div className="h-11 w-11 rounded-xl bg-primary/10 grid place-items-center mb-4 group-hover:bg-primary/15 transition-colors">
                    <uc.icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-bold mb-2">{uc.title}</h3>
                  <p className="text-[15px] text-muted-foreground leading-relaxed">{uc.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          FAQ
         ════════════════════════════════════════════════════════ */}
      <section id="faq" className="py-24">
        <div className="max-w-3xl mx-auto px-6 lg:px-8">
          <Reveal>
            <div className="text-center mb-12">
              <p className="text-sm font-bold text-primary uppercase tracking-widest mb-3">FAQ</p>
              <h2 className="text-4xl font-extrabold tracking-tight">Common questions</h2>
            </div>
          </Reveal>

          <div className="space-y-3">
            {FAQS.map((faq, i) => (
              <Reveal key={i} delay={i * 50}>
                <FAQItem q={faq.q} a={faq.a} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          CTA
         ════════════════════════════════════════════════════════ */}
      <section className="py-24 relative">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary/[0.06] rounded-full blur-[100px]" />
        </div>
        <div className="max-w-3xl mx-auto px-6 lg:px-8 relative">
          <Reveal>
            <div className="text-center">
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight mb-4">
                Ready to start <span className="gradient-text">harvesting?</span>
              </h2>
              <p className="text-lg text-muted-foreground mb-8 max-w-xl mx-auto">
                Deploy WebHarvest on your infrastructure and start extracting clean, structured data in minutes.
              </p>
              <div className="flex items-center justify-center gap-4">
                {user ? (
                  <Link href="/playground?endpoint=scrape" className="flex items-center gap-2 h-12 px-8 rounded-xl text-base font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-lg shadow-primary/20">
                    Open Playground <ArrowRight className="h-5 w-5" />
                  </Link>
                ) : (
                  <>
                    <Link href="/auth/register" className="flex items-center gap-2 h-12 px-8 rounded-xl text-base font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-lg shadow-primary/20">
                      Get Started Free <ArrowRight className="h-5 w-5" />
                    </Link>
                    <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 h-12 px-6 rounded-xl text-base font-semibold border border-border/60 hover:bg-muted/50 transition-all">
                      <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" /></svg>
                      GitHub
                    </a>
                  </>
                )}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          FOOTER
         ════════════════════════════════════════════════════════ */}
      <footer className="border-t border-border/30">
        <div className="max-w-6xl mx-auto px-6 lg:px-8 py-16">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
            {/* Brand */}
            <div className="col-span-2">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="h-8 w-8 rounded-lg bg-primary/10 grid place-items-center">
                  <Flame className="h-4 w-4 text-primary" />
                </div>
                <span className="text-base font-bold tracking-tight">WebHarvest</span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                Open-source web scraping platform with multi-strategy anti-detection. Self-hosted, no limits, no vendor lock-in.
              </p>
            </div>

            {/* Links */}
            {[
              { title: "Product", links: [
                { text: "Scrape", href: "/playground?endpoint=scrape" },
                { text: "Crawl", href: "/playground?endpoint=crawl" },
                { text: "Search", href: "/playground?endpoint=search" },
                { text: "Map", href: "/playground?endpoint=map" },
              ]},
              { title: "Resources", links: [
                { text: "API Docs", href: "/docs" },
                { text: "Dashboard", href: "/dashboard" },
                { text: "Jobs", href: "/jobs" },
              ]},
              { title: "Connect", links: [
                { text: "GitHub", href: "https://github.com/Takezo49/WebHarvest" },
                { text: "API Keys", href: "/api-keys" },
                { text: "Settings", href: "/settings" },
              ]},
            ].map((section) => (
              <div key={section.title}>
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground/50 mb-4">{section.title}</p>
                <ul className="space-y-2.5">
                  {section.links.map((link) => (
                    <li key={link.text}>
                      {link.href.startsWith("http") ? (
                        <a href={link.href} target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:text-foreground transition-colors">{link.text}</a>
                      ) : (
                        <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">{link.text}</Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 pt-8 border-t border-border/20 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-muted-foreground/50">&copy; {new Date().getFullYear()} WebHarvest. All rights reserved.</p>
            <a href="https://github.com/Takezo49/WebHarvest" target="_blank" rel="noopener noreferrer" className="h-8 w-8 rounded-full bg-muted/50 grid place-items-center text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors">
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" /></svg>
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
