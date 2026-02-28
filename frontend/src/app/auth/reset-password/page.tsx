"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") || "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);

    try {
      await api.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => router.push("/auth/login"), 2000);
    } catch (err: any) {
      if (err.status === 429) {
        setError(`Too many attempts. Try again in ${err.retryAfter || 60} seconds.`);
      } else {
        setError(err.message || "Reset failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center relative overflow-hidden">
      {/* Grid bg */}
      <div className="fixed inset-0 opacity-[0.025] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "40px 40px" }} />
      <div className="absolute bottom-[-30%] right-[10%] w-[500px] h-[500px] bg-[radial-gradient(circle,rgba(139,92,246,0.06)_0%,transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-[460px] px-6 relative z-10 animate-float-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="h-5 w-5 bg-gradient-to-br from-emerald-400 to-cyan-500" />
          <span className="text-[20px] font-extrabold tracking-tight uppercase font-mono">WEBHARVEST</span>
        </div>

        {/* Card */}
        <div className="border border-border bg-card/50 relative overflow-hidden">
          <div className="h-[2px] bg-gradient-to-r from-violet-500 via-cyan-500 to-emerald-500" />

          <div className="p-8 md:p-10">
            {success ? (
              <div className="text-center py-4">
                <div className="h-14 w-14 border border-emerald-500/20 bg-emerald-500/[0.05] grid place-items-center mx-auto mb-6">
                  <span className="text-emerald-400 text-[24px]">✓</span>
                </div>
                <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono text-foreground mb-2">Password Reset</h1>
                <p className="text-[13px] text-muted-foreground font-mono">
                  Redirecting to login...
                </p>
              </div>
            ) : (
              <div>
                <div className="mb-8">
                  <h1 className="text-[28px] font-extrabold tracking-tight uppercase font-mono animate-gradient-text-violet">Reset Password</h1>
                  <p className="text-[13px] text-muted-foreground font-mono mt-2">
                    Enter your reset token and new password
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                  {error && (
                    <div className="border border-red-500/20 bg-red-500/[0.05] px-4 py-3 text-[13px] font-mono text-red-400">
                      <span className="text-red-500/60 mr-2 font-bold">ERR</span>{error}
                    </div>
                  )}

                  <div className="space-y-2">
                    <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Reset Token</label>
                    <input
                      type="text"
                      placeholder="Paste your reset token"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      required
                      className="h-12 w-full bg-transparent border border-border px-4 text-[12px] font-mono text-amber-400/80 placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/30 transition-colors"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">New Password</label>
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

                  <div className="space-y-2">
                    <label className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Confirm Password</label>
                    <input
                      type="password"
                      placeholder="Confirm new password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
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
                    {loading ? "Resetting..." : <>Reset Password <span className="text-[16px]">→</span></>}
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

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
