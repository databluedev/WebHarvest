"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.register(email, password, name || undefined);
      api.setToken(res.access_token);
      router.push("/");
    } catch (err: any) {
      if (err.status === 429) {
        setError(`Too many attempts. Try again in ${err.retryAfter || 60} seconds.`);
      } else {
        setError(err.message || "Registration failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center relative overflow-hidden">
      {/* Grid bg */}
      <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />
      {/* Background glow */}
      <div className="absolute top-[-30%] right-[-10%] w-[600px] h-[600px] bg-[radial-gradient(circle,rgba(16,185,129,0.08)_0%,transparent_70%)] pointer-events-none" />
      <div className="absolute bottom-[-20%] left-[-10%] w-[500px] h-[500px] bg-[radial-gradient(circle,rgba(139,92,246,0.06)_0%,transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-[460px] px-6 relative z-10 animate-float-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="h-5 w-5 bg-gradient-to-br from-emerald-400 to-cyan-500" />
          <span className="text-[20px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
        </div>

        {/* Register Card */}
        <div className="border border-border bg-card/50 relative overflow-hidden">
          <div className="h-[2px] bg-gradient-to-r from-emerald-500 via-cyan-500 to-violet-500" />

          <div className="p-8 md:p-10">
            <div className="mb-8">
              <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text">Create Account</h1>
              <p className="text-[13px] text-muted-foreground font-mono mt-2">
                Deploy your own scraping infrastructure
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="border border-red-500/20 bg-red-500/[0.05] px-4 py-3 text-[13px] font-mono text-red-400">
                  <span className="text-red-500/60 mr-2 font-bold">ERR</span>{error}
                </div>
              )}

              <div className="space-y-2">
                <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                  Name <span className="text-muted-foreground/50">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-12 w-full bg-transparent border border-border px-4 text-[14px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 transition-colors"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Email</label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-12 w-full bg-transparent border border-border px-4 text-[14px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 transition-colors"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Password</label>
                <input
                  type="password"
                  placeholder="Min. 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="h-12 w-full bg-transparent border border-border px-4 text-[14px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 transition-colors"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-foreground text-background h-12 text-[13px] font-bold uppercase tracking-[0.15em] font-mono hover:bg-emerald-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? "Creating account..." : <>Create Account <span className="text-[16px]">→</span></>}
              </button>
            </form>

            <div className="flex items-center gap-4 my-6">
              <div className="h-px flex-1 bg-muted" />
              <span className="text-[11px] font-mono text-muted-foreground/50 uppercase tracking-wider">or</span>
              <div className="h-px flex-1 bg-muted" />
            </div>

            <p className="text-center text-[13px] font-mono text-muted-foreground">
              Already registered?{" "}
              <Link href="/auth/login" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                Sign in
              </Link>
            </p>
          </div>
        </div>

        <p className="text-center text-[11px] text-muted-foreground/50 font-mono mt-6 tracking-wider">
          OPEN SOURCE · SELF-HOSTED · MIT LICENSE
        </p>
      </div>
    </div>
  );
}
