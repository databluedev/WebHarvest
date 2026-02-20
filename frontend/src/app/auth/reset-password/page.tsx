"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ArrowLeft, ArrowRight, Flame, Check } from "lucide-react";

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
          {success ? (
            <div className="text-center">
              <div className="h-12 w-12 rounded-full bg-green-500/10 grid place-items-center mx-auto mb-4">
                <Check className="h-6 w-6 text-green-500" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight mb-2">Password reset</h1>
              <p className="text-sm text-muted-foreground/60">
                Redirecting to login...
              </p>
            </div>
          ) : (
            <div>
              <div className="mb-6">
                <h1 className="text-2xl font-bold tracking-tight">Reset password</h1>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Enter your reset token and new password
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="rounded-md border border-red-500/15 bg-red-500/8 p-3 text-sm text-red-400">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground/60 font-medium">Reset Token</label>
                  <Input
                    placeholder="Paste your reset token"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    required
                    className="rounded-md font-mono text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground/60 font-medium">New Password</label>
                  <Input
                    type="password"
                    placeholder="Enter new password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    className="rounded-md"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground/60 font-medium">Confirm Password</label>
                  <Input
                    type="password"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={8}
                    className="rounded-md"
                  />
                </div>
                <Button type="submit" variant="default" className="w-full rounded-lg gap-2" disabled={loading}>
                  {loading ? "Resetting..." : (
                    <>
                      Reset Password
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
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

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
