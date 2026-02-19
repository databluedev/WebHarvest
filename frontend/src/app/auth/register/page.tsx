"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ArrowRight } from "lucide-react";

const ASCII_SMALL = `
██╗    ██╗██╗  ██╗
██║    ██║██║  ██║
██║ █╗ ██║███████║
██║███╗██║██╔══██║
╚███╔███╔╝██║  ██║
 ╚══╝╚══╝ ╚═╝  ╚═╝`.trimStart();

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
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background grid-bg mesh-gradient noise">
      <div className="w-full max-w-md px-6 animate-fade-in">
        {/* ASCII Logo */}
        <div className="text-center mb-8">
          <pre className="ascii-art text-primary/60 glow-green-sm inline-block select-none">
            {ASCII_SMALL}
          </pre>
          <div className="flex items-center gap-2 justify-center mt-4">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse-glow" />
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              WebHarvest
            </span>
          </div>
        </div>

        {/* Register Card */}
        <div className="rounded-xl border border-border/50 bg-card/80 backdrop-blur-md p-8 shadow-2xl shadow-black/20">
          {/* Terminal Header */}
          <div className="flex items-center gap-1.5 mb-6">
            <div className="w-3 h-3 rounded-full bg-red-500/60" />
            <div className="w-3 h-3 rounded-full bg-amber-500/60" />
            <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
            <span className="ml-3 text-xs font-mono text-muted-foreground">~/auth/register</span>
          </div>

          <div className="mb-6">
            <h1 className="text-xl font-bold font-mono">Create account</h1>
            <p className="text-sm text-muted-foreground font-mono mt-1">
              <span className="text-primary">$</span> register --new-user
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400 font-mono">
                <span className="text-red-500">ERR</span> {error}
              </div>
            )}
            <div className="space-y-2">
              <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                Name <span className="text-muted-foreground/50">(optional)</span>
              </label>
              <Input
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="bg-background/50"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                Email
              </label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-background/50"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                Password
              </label>
              <Input
                type="password"
                placeholder="Create a password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="bg-background/50"
              />
            </div>
            <Button type="submit" variant="glow" className="w-full font-mono gap-2" disabled={loading}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="animate-pulse">Creating</span>
                  <span className="animate-blink">_</span>
                </span>
              ) : (
                <>
                  Create Account
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs font-mono text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <p className="text-center text-sm text-muted-foreground font-mono mt-4">
            Already registered?{" "}
            <Link href="/auth/login" className="text-primary hover:underline">
              sign in
            </Link>
          </p>
        </div>

        <p className="text-center text-[10px] font-mono text-muted-foreground/50 mt-6">
          Open source web crawling platform
        </p>
      </div>
    </div>
  );
}
