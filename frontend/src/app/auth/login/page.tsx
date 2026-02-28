"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.login(email, password);
      api.setToken(res.access_token);
      router.push("/");
    } catch (err: any) {
      if (err.status === 429) {
        setError(`Too many attempts. Try again in ${err.retryAfter || 60} seconds.`);
      } else {
        setError(err.message || "Login failed");
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
      <div className="absolute top-[-30%] left-[-10%] w-[600px] h-[600px] bg-[radial-gradient(circle,rgba(6,182,212,0.08)_0%,transparent_70%)] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-[radial-gradient(circle,rgba(16,185,129,0.06)_0%,transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-[460px] px-6 relative z-10 animate-float-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="h-5 w-5 bg-gradient-to-br from-emerald-400 to-cyan-500" />
          <span className="text-[20px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
        </div>

        {/* Login Card */}
        <div className="border border-border bg-card/50 relative overflow-hidden">
          <div className="h-[2px] bg-gradient-to-r from-cyan-500 via-emerald-500 to-amber-500" />

          <div className="p-8 md:p-10">
            <div className="mb-8">
              <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text-blue">Sign In</h1>
              <p className="text-[13px] text-muted-foreground font-mono mt-2">
                Access your scraping dashboard
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="border border-red-500/20 bg-red-500/[0.05] px-4 py-3 text-[13px] font-mono text-red-400">
                  <span className="text-red-500/60 mr-2 font-bold">ERR</span>{error}
                </div>
              )}

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
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Password</label>
                  <Link href="/auth/forgot-password" className="text-[11px] font-mono text-muted-foreground/70 hover:text-foreground/60 transition-colors uppercase tracking-wider">
                    Forgot?
                  </Link>
                </div>
                <input
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-12 w-full bg-transparent border border-border px-4 text-[14px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 transition-colors"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-foreground text-background h-12 text-[13px] font-bold uppercase tracking-[0.15em] font-mono hover:bg-emerald-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? "Signing in..." : <>Sign In <span className="text-[16px]">→</span></>}
              </button>
            </form>

            <div className="flex items-center gap-4 my-6">
              <div className="h-px flex-1 bg-muted" />
              <span className="text-[11px] font-mono text-muted-foreground/50 uppercase tracking-wider">or</span>
              <div className="h-px flex-1 bg-muted" />
            </div>

            <p className="text-center text-[13px] font-mono text-muted-foreground">
              No account?{" "}
              <Link href="/auth/register" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                Create one
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
