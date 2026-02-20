"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ArrowLeft, Flame, Mail } from "lucide-react";

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
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md px-6 animate-float-in relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-primary/10 grid place-items-center">
              <Flame className="h-6 w-6 text-primary" />
            </div>
            <span className="text-2xl font-bold tracking-tight">WebHarvest</span>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-8">
          {submitted ? (
            <div>
              <div className="mb-6">
                <h1 className="text-2xl font-bold tracking-tight">Check your logs</h1>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  If an account exists with that email, a reset token has been generated.
                </p>
              </div>

              {resetToken && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground/60">
                    Self-hosted convenience — your reset token:
                  </p>
                  <div className="rounded-md border border-border bg-muted/50 p-3 font-mono text-xs break-all">
                    {resetToken}
                  </div>
                  <Link href={`/auth/reset-password?token=${encodeURIComponent(resetToken)}`}>
                    <Button variant="default" className="w-full rounded-lg gap-2 mt-3">
                      Reset Password
                      <Mail className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              )}

              <p className="text-center text-sm text-muted-foreground/60 mt-6">
                <Link href="/auth/login" className="text-primary hover:underline inline-flex items-center gap-1">
                  <ArrowLeft className="h-3 w-3" />
                  Back to login
                </Link>
              </p>
            </div>
          ) : (
            <div>
              <div className="mb-6">
                <h1 className="text-2xl font-bold tracking-tight">Forgot password</h1>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Enter your email to get a password reset token
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="rounded-md border border-red-500/15 bg-red-500/8 p-3 text-sm text-red-400">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground/60 font-medium">Email</label>
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="rounded-md"
                  />
                </div>
                <Button type="submit" variant="default" className="w-full rounded-lg gap-2" disabled={loading}>
                  {loading ? "Sending..." : "Send Reset Token"}
                </Button>
              </form>

              <p className="text-center text-sm text-muted-foreground/60 mt-6">
                <Link href="/auth/login" className="text-primary hover:underline inline-flex items-center gap-1">
                  <ArrowLeft className="h-3 w-3" />
                  Back to login
                </Link>
              </p>
            </div>
          )}
        </div>

        <p className="text-center text-[11px] text-muted-foreground/25 mt-6">
          Open source web crawling platform
        </p>
      </div>
    </div>
  );
}
