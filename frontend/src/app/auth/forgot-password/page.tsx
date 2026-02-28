"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.forgotPassword(email);
      setSubmitted(true);
      setResetToken(res.token);
    } catch (err: any) {
      if (err.status === 429) {
        setError(`Too many attempts. Try again in ${err.retryAfter || 60} seconds.`);
      } else {
        setError(err.message || "Request failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center relative overflow-hidden">
      {/* Grid bg */}
      <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />
      <div className="absolute top-[-30%] left-[20%] w-[500px] h-[500px] bg-[radial-gradient(circle,rgba(245,158,11,0.06)_0%,transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-[460px] px-6 relative z-10 animate-float-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="h-5 w-5 bg-gradient-to-br from-emerald-400 to-cyan-500" />
          <span className="text-[20px] font-extrabold tracking-tight uppercase font-mono">DATABLUE</span>
        </div>

        {/* Card */}
        <div className="border border-border bg-card/50 relative overflow-hidden">
          <div className="h-[2px] bg-gradient-to-r from-amber-500 via-pink-500 to-violet-500" />

          <div className="p-8 md:p-10">
            {submitted ? (
              <div>
                <div className="mb-6">
                  <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text">Token Generated</h1>
                  <p className="text-[13px] text-muted-foreground font-mono mt-2">
                    If an account exists with that email, a reset token has been generated.
                  </p>
                </div>

                {resetToken && (
                  <div className="space-y-4">
                    <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                      Self-hosted convenience — your reset token:
                    </p>
                    <div className="border border-border bg-background/40 p-4 font-mono text-[12px] text-amber-400/80 break-all">
                      {resetToken}
                    </div>
                    <Link
                      href={`/auth/reset-password?token=${encodeURIComponent(resetToken)}`}
                      className="w-full bg-foreground text-background h-12 text-[13px] font-bold uppercase tracking-[0.15em] font-mono hover:bg-emerald-400 transition-colors flex items-center justify-center gap-2"
                    >
                      Reset Password <span className="text-[16px]">→</span>
                    </Link>
                  </div>
                )}

                <p className="text-center text-[13px] font-mono text-muted-foreground mt-8">
                  <Link href="/auth/login" className="text-cyan-400 hover:text-cyan-300 transition-colors inline-flex items-center gap-2">
                    ← Back to login
                  </Link>
                </p>
              </div>
            ) : (
              <div>
                <div className="mb-8">
                  <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text-pink">Forgot Password</h1>
                  <p className="text-[13px] text-muted-foreground font-mono mt-2">
                    Enter your email to get a password reset token
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

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-foreground text-background h-12 text-[13px] font-bold uppercase tracking-[0.15em] font-mono hover:bg-emerald-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {loading ? "Sending..." : <>Send Reset Token <span className="text-[16px]">→</span></>}
                  </button>
                </form>

                <p className="text-center text-[13px] font-mono text-muted-foreground mt-8">
                  <Link href="/auth/login" className="text-cyan-400 hover:text-cyan-300 transition-colors inline-flex items-center gap-2">
                    ← Back to login
                  </Link>
                </p>
              </div>
            )}
          </div>
        </div>

        <p className="text-center text-[11px] text-muted-foreground/50 font-mono mt-6 tracking-wider">
          OPEN SOURCE · SELF-HOSTED · MIT LICENSE
        </p>
      </div>
    </div>
  );
}
