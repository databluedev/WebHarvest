"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ArrowRight, Flame } from "lucide-react";

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

        {/* Register Card */}
        <div className="bg-card border border-border rounded-lg p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight">Create account</h1>
            <p className="text-sm text-muted-foreground/60 mt-1">
              Get started with WebHarvest
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-md border border-red-500/15 bg-red-500/8 p-3 text-sm text-red-400">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground/60 font-medium">
                Name <span className="text-foreground/30">(optional)</span>
              </label>
              <Input
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="rounded-md"
              />
            </div>
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
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground/60 font-medium">Password</label>
              <Input
                type="password"
                placeholder="Create a password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="rounded-md"
              />
            </div>
            <Button type="submit" variant="default" className="w-full rounded-lg gap-2" disabled={loading}>
              {loading ? "Creating account..." : (
                <>
                  Create Account
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border/30" />
            <span className="text-xs text-muted-foreground/30">or</span>
            <div className="h-px flex-1 bg-border/30" />
          </div>

          <p className="text-center text-sm text-muted-foreground/60 mt-4">
            Already registered?{" "}
            <Link href="/auth/login" className="text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center text-[11px] text-muted-foreground/25 mt-6">
          Open source web crawling platform
        </p>
      </div>
    </div>
  );
}
