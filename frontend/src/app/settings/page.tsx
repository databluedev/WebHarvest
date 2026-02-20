"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, SidebarProvider, MobileMenuButton } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Settings as SettingsIcon, Plus, Trash2, Star, Check, Shield, Globe, Webhook } from "lucide-react";

const PROVIDERS = [
  { id: "openai", name: "OpenAI", placeholder: "sk-...", defaultModel: "gpt-4o-mini" },
  { id: "anthropic", name: "Anthropic", placeholder: "sk-ant-...", defaultModel: "claude-sonnet-4-20250514" },
  { id: "openrouter", name: "OpenRouter", placeholder: "sk-or-v1-...", defaultModel: "deepseek/deepseek-r1-0528:free" },
  { id: "groq", name: "Groq", placeholder: "gsk_...", defaultModel: "llama-3.1-70b-versatile" },
  { id: "together", name: "Together AI", placeholder: "...", defaultModel: "meta-llama/Llama-3.1-70B-Instruct-Turbo" },
  { id: "mistral", name: "Mistral", placeholder: "...", defaultModel: "mistral-large-latest" },
  { id: "deepseek", name: "DeepSeek", placeholder: "sk-...", defaultModel: "deepseek-chat" },
  { id: "fireworks", name: "Fireworks", placeholder: "...", defaultModel: "accounts/fireworks/models/llama-v3p1-70b-instruct" },
  { id: "cohere", name: "Cohere", placeholder: "...", defaultModel: "command-r-plus" },
  { id: "ollama", name: "Ollama (Local)", placeholder: "not needed", defaultModel: "llama3.1" },
];

export default function SettingsPage() {
  const router = useRouter();
  const [keys, setKeys] = useState<any[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [isDefault, setIsDefault] = useState(true);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  // Default webhook state
  const [defaultWebhookUrl, setDefaultWebhookUrl] = useState("");
  const [defaultWebhookSecret, setDefaultWebhookSecret] = useState("");
  const [webhookSaved, setWebhookSaved] = useState(false);

  // Proxy state
  const [proxies, setProxies] = useState<any[]>([]);
  const [proxyText, setProxyText] = useState("");
  const [proxyType, setProxyType] = useState("http");
  const [proxyLoading, setProxyLoading] = useState(false);
  const [proxySuccess, setProxySuccess] = useState(false);
  const [proxyError, setProxyError] = useState("");

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    loadKeys();
    loadProxies();
    // Load default webhook from localStorage
    if (typeof window !== "undefined") {
      setDefaultWebhookUrl(localStorage.getItem("wh_default_webhook_url") || "");
      setDefaultWebhookSecret(localStorage.getItem("wh_default_webhook_secret") || "");
    }
  }, [router]);

  const loadKeys = async () => {
    try {
      const res = await api.listLlmKeys();
      setKeys(res.keys);
    } catch (err) {
      console.error(err);
    }
  };

  const loadProxies = async () => {
    try {
      const res = await api.listProxies();
      setProxies(res.proxies);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSave = async () => {
    if (!apiKey) return;
    setLoading(true);
    setError("");
    setSuccess(false);

    try {
      await api.saveLlmKey({
        provider: selectedProvider,
        api_key: apiKey,
        model: model || undefined,
        is_default: isDefault,
      });
      setApiKey("");
      setModel("");
      setSuccess(true);
      loadKeys();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (keyId: string) => {
    try {
      await api.deleteLlmKey(keyId);
      loadKeys();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddProxies = async () => {
    const lines = proxyText.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    setProxyLoading(true);
    setProxyError("");
    setProxySuccess(false);

    try {
      await api.addProxies(lines, proxyType);
      setProxyText("");
      setProxySuccess(true);
      loadProxies();
      setTimeout(() => setProxySuccess(false), 3000);
    } catch (err: any) {
      setProxyError(err.message);
    } finally {
      setProxyLoading(false);
    }
  };

  const handleDeleteProxy = async (proxyId: string) => {
    try {
      await api.deleteProxy(proxyId);
      loadProxies();
    } catch (err) {
      console.error(err);
    }
  };

  const currentProvider = PROVIDERS.find((p) => p.id === selectedProvider)!;

  return (
    <SidebarProvider>
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background">
        <MobileMenuButton />
        <div className="p-8 max-w-4xl mx-auto">
          <div className="mb-8 animate-float-in">
            <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
            <p className="text-muted-foreground mt-1">
              Manage your LLM API keys and proxy configuration
            </p>
          </div>

          {/* BYOK Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <SettingsIcon className="h-5 w-5 text-primary" />
                Bring Your Own Key (BYOK)
              </CardTitle>
              <CardDescription>
                Add your LLM API keys to enable AI-powered data extraction.
                Keys are encrypted at rest using AES-256.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Provider</label>
                <div className="flex flex-wrap gap-2">
                  {PROVIDERS.map((p) => (
                    <Button
                      key={p.id}
                      variant={selectedProvider === p.id ? "default" : "outline"}
                      size="sm"
                      onClick={() => {
                        setSelectedProvider(p.id);
                        setModel(p.defaultModel);
                      }}
                    >
                      {p.name}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">API Key</label>
                <Input
                  type="password"
                  placeholder={currentProvider.placeholder}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Model (optional)</label>
                <Input
                  placeholder={currentProvider.defaultModel}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Leave empty to use default: {currentProvider.defaultModel}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant={isDefault ? "default" : "outline"}
                  size="sm"
                  onClick={() => setIsDefault(!isDefault)}
                  className="gap-1"
                >
                  <Star className="h-3.5 w-3.5" />
                  {isDefault ? "Set as default" : "Not default"}
                </Button>
              </div>

              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">{error}</div>
              )}
              {success && (
                <div className="rounded-md bg-green-500/10 p-3 text-sm text-green-400 flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  Key saved successfully
                </div>
              )}

              <Button onClick={handleSave} disabled={loading || !apiKey} className="gap-1">
                <Plus className="h-4 w-4" />
                {loading ? "Saving..." : "Save Key"}
              </Button>
            </CardContent>
          </Card>

          {/* Saved Keys */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Saved LLM Keys</CardTitle>
            </CardHeader>
            <CardContent>
              {keys.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No LLM keys saved yet. Add one above to enable AI extraction.
                </p>
              ) : (
                <div className="space-y-3">
                  {keys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between rounded-md border p-4"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium capitalize">{key.provider}</span>
                          {key.is_default && (
                            <Badge variant="success" className="gap-1">
                              <Star className="h-3 w-3" />
                              Default
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <code className="text-xs text-muted-foreground">{key.key_preview}</code>
                          {key.model && (
                            <Badge variant="outline" className="text-xs">{key.model}</Badge>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(key.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Proxy Configuration */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield className="h-5 w-5 text-primary" />
                Proxy Configuration
              </CardTitle>
              <CardDescription>
                Add rotating proxies for anti-bot bypassing. Supports HTTP, HTTPS, and SOCKS5 proxies.
                Enable "Use Proxy" on scrape/crawl/batch requests to route through these proxies.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Proxy Type</label>
                <div className="flex gap-2">
                  {["http", "https", "socks5"].map((t) => (
                    <Button
                      key={t}
                      variant={proxyType === t ? "default" : "outline"}
                      size="sm"
                      onClick={() => setProxyType(t)}
                    >
                      {t.toUpperCase()}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Proxy URLs (one per line)</label>
                <textarea
                  className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                  placeholder={"http://user:pass@proxy1.example.com:8080\nhttp://proxy2.example.com:3128\nsocks5://user:pass@proxy3.example.com:1080"}
                  value={proxyText}
                  onChange={(e) => setProxyText(e.target.value)}
                />
              </div>

              {proxyError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-red-400">{proxyError}</div>
              )}
              {proxySuccess && (
                <div className="rounded-md bg-green-500/10 p-3 text-sm text-green-400 flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  Proxies added successfully
                </div>
              )}

              <Button onClick={handleAddProxies} disabled={proxyLoading || !proxyText.trim()} className="gap-1">
                <Plus className="h-4 w-4" />
                {proxyLoading ? "Adding..." : "Add Proxies"}
              </Button>
            </CardContent>
          </Card>

          {/* Default Webhook */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Webhook className="h-5 w-5 text-primary" />
                Default Webhook
              </CardTitle>
              <CardDescription>
                Set a default webhook URL and secret that will be auto-applied to new jobs from the playground.
                Stored locally in your browser.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Webhook URL</label>
                <Input
                  placeholder="https://your-server.com/webhook"
                  value={defaultWebhookUrl}
                  onChange={(e) => setDefaultWebhookUrl(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Webhook Secret (optional)</label>
                <Input
                  type="password"
                  placeholder="Optional HMAC signing secret"
                  value={defaultWebhookSecret}
                  onChange={(e) => setDefaultWebhookSecret(e.target.value)}
                />
              </div>

              {webhookSaved && (
                <div className="rounded-md bg-green-500/10 p-3 text-sm text-green-400 flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  Default webhook saved
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  onClick={() => {
                    if (typeof window !== "undefined") {
                      localStorage.setItem("wh_default_webhook_url", defaultWebhookUrl);
                      localStorage.setItem("wh_default_webhook_secret", defaultWebhookSecret);
                    }
                    setWebhookSaved(true);
                    setTimeout(() => setWebhookSaved(false), 3000);
                  }}
                  className="gap-1"
                >
                  <Check className="h-4 w-4" />
                  Save Webhook
                </Button>
                {defaultWebhookUrl && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDefaultWebhookUrl("");
                      setDefaultWebhookSecret("");
                      if (typeof window !== "undefined") {
                        localStorage.removeItem("wh_default_webhook_url");
                        localStorage.removeItem("wh_default_webhook_secret");
                      }
                      setWebhookSaved(true);
                      setTimeout(() => setWebhookSaved(false), 3000);
                    }}
                    className="gap-1"
                  >
                    <Trash2 className="h-4 w-4" />
                    Clear
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Saved Proxies */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Saved Proxies</CardTitle>
            </CardHeader>
            <CardContent>
              {proxies.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No proxies configured. Add proxies above to enable rotating proxy support.
                </p>
              ) : (
                <div className="space-y-3">
                  {proxies.map((proxy) => (
                    <div
                      key={proxy.id}
                      className="flex items-center justify-between rounded-md border p-4"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <Globe className="h-4 w-4 text-muted-foreground" />
                          <code className="text-sm font-mono">{proxy.proxy_url_masked}</code>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className="text-xs">{proxy.proxy_type}</Badge>
                          {proxy.is_active ? (
                            <Badge variant="success" className="text-xs">Active</Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs">Inactive</Badge>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDeleteProxy(proxy.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
    </SidebarProvider>
  );
}
