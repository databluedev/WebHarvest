"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageLayout } from "@/components/layout/page-layout";
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
    <PageLayout activePage="settings">
      <div className="max-w-[1000px] mx-auto px-6 md:px-10 py-10">
        {/* Page Header */}
        <div className="mb-10">
          <h1 className="text-[36px] font-extrabold tracking-tight uppercase font-mono text-white">Settings</h1>
          <p className="text-white/50 font-mono text-[14px] mt-1">
            Manage your LLM API keys and proxy configuration
          </p>
        </div>

        {/* BYOK Section */}
        <div className="border border-white/10 bg-white/[0.02] p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-[16px] font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <SettingsIcon className="h-5 w-5 text-emerald-400" />
              Bring Your Own Key (BYOK)
            </h2>
            <p className="text-white/50 text-[13px] font-mono mt-1">
              Add your LLM API keys to enable AI-powered data extraction.
              Keys are encrypted at rest using AES-256.
            </p>
          </div>

          <div className="space-y-4">
            {/* Provider Selection */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Provider</label>
              <div className="flex flex-wrap gap-2">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setSelectedProvider(p.id);
                      setModel(p.defaultModel);
                    }}
                    className={
                      selectedProvider === p.id
                        ? "bg-white text-black text-[12px] font-mono uppercase tracking-wider px-3 py-1.5"
                        : "border border-white/20 text-white/50 text-[12px] font-mono uppercase tracking-wider px-3 py-1.5 hover:border-white/40 hover:text-white"
                    }
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            {/* API Key Input */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">API Key</label>
              <input
                type="password"
                placeholder={currentProvider.placeholder}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="h-10 w-full bg-transparent border border-white/10 px-3 text-[14px] font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-white/30"
              />
            </div>

            {/* Model Input */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Model (optional)</label>
              <input
                placeholder={currentProvider.defaultModel}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="h-10 w-full bg-transparent border border-white/10 px-3 text-[14px] font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-white/30"
              />
              <p className="text-white/50 text-[13px] font-mono">
                Leave empty to use default: {currentProvider.defaultModel}
              </p>
            </div>

            {/* Default Toggle */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsDefault(!isDefault)}
                className={
                  isDefault
                    ? "bg-white text-black text-[12px] font-mono uppercase tracking-wider px-3 py-1.5 flex items-center gap-1"
                    : "border border-white/20 text-white/50 text-[12px] font-mono uppercase tracking-wider px-3 py-1.5 hover:border-white/40 hover:text-white flex items-center gap-1"
                }
              >
                <Star className={`h-3.5 w-3.5 ${isDefault ? "text-amber-400" : "text-white/50"}`} />
                {isDefault ? "Set as default" : "Not default"}
              </button>
            </div>

            {/* Error/Success Messages */}
            {error && (
              <div className="border border-red-500/30 bg-red-500/10 text-red-400 text-[13px] font-mono p-3">{error}</div>
            )}
            {success && (
              <div className="border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[13px] font-mono p-3 flex items-center gap-2">
                <Check className="h-4 w-4" />
                Key saved successfully
              </div>
            )}

            {/* Save Button */}
            <button
              onClick={handleSave}
              disabled={loading || !apiKey}
              className="border border-white/20 px-5 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-white hover:bg-white hover:text-black transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <Plus className="h-4 w-4" />
              {loading ? "Saving..." : "Save Key"}
            </button>
          </div>
        </div>

        {/* Saved Keys */}
        <div className="border border-white/10 bg-white/[0.02] p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-[16px] font-bold text-white font-mono uppercase tracking-wider">Saved LLM Keys</h2>
          </div>
          {keys.length === 0 ? (
            <p className="text-white/40 text-[13px] font-mono text-center py-8">
              No LLM keys saved yet. Add one above to enable AI extraction.
            </p>
          ) : (
            <div className="space-y-3">
              {keys.map((key) => (
                <div
                  key={key.id}
                  className="border border-white/10 bg-white/[0.02] p-4 flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-mono text-white capitalize">{key.provider}</span>
                      {key.is_default && (
                        <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-emerald-500/30 text-emerald-400 bg-emerald-500/10 flex items-center gap-1">
                          <Star className="h-3 w-3" />
                          Default
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <code className="text-[12px] text-white/40 font-mono">{key.key_preview}</code>
                      {key.model && (
                        <span className="border border-white/20 text-white/50 text-[11px] font-mono px-2 py-0.5">{key.model}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(key.id)}
                    className="text-white/30 hover:text-red-400 p-2"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Proxy Configuration */}
        <div className="border border-white/10 bg-white/[0.02] p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-[16px] font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <Shield className="h-5 w-5 text-emerald-400" />
              Proxy Configuration
            </h2>
            <p className="text-white/50 text-[13px] font-mono mt-1">
              Add rotating proxies for anti-bot bypassing. Supports HTTP, HTTPS, and SOCKS5 proxies.
              Enable &quot;Use Proxy&quot; on scrape/crawl requests to route through these proxies.
            </p>
          </div>

          <div className="space-y-4">
            {/* Proxy Type Selection */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Proxy Type</label>
              <div className="flex gap-2">
                {["http", "https", "socks5"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setProxyType(t)}
                    className={
                      proxyType === t
                        ? "bg-white text-black text-[12px] font-mono uppercase tracking-wider px-3 py-1.5"
                        : "border border-white/20 text-white/50 text-[12px] font-mono uppercase tracking-wider px-3 py-1.5 hover:border-white/40 hover:text-white"
                    }
                  >
                    {t.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Proxy URLs Textarea */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Proxy URLs (one per line)</label>
              <textarea
                className="min-h-[120px] w-full bg-transparent border border-white/10 px-3 py-2 text-[14px] font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-white/30"
                placeholder={"http://user:pass@proxy1.example.com:8080\nhttp://proxy2.example.com:3128\nsocks5://user:pass@proxy3.example.com:1080"}
                value={proxyText}
                onChange={(e) => setProxyText(e.target.value)}
              />
            </div>

            {/* Error/Success Messages */}
            {proxyError && (
              <div className="border border-red-500/30 bg-red-500/10 text-red-400 text-[13px] font-mono p-3">{proxyError}</div>
            )}
            {proxySuccess && (
              <div className="border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[13px] font-mono p-3 flex items-center gap-2">
                <Check className="h-4 w-4" />
                Proxies added successfully
              </div>
            )}

            {/* Add Proxies Button */}
            <button
              onClick={handleAddProxies}
              disabled={proxyLoading || !proxyText.trim()}
              className="border border-white/20 px-5 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-white hover:bg-white hover:text-black transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <Plus className="h-4 w-4" />
              {proxyLoading ? "Adding..." : "Add Proxies"}
            </button>
          </div>
        </div>

        {/* Default Webhook */}
        <div className="border border-white/10 bg-white/[0.02] p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-[16px] font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <Webhook className="h-5 w-5 text-emerald-400" />
              Default Webhook
            </h2>
            <p className="text-white/50 text-[13px] font-mono mt-1">
              Set a default webhook URL and secret that will be auto-applied to new jobs from the playground.
              Stored locally in your browser.
            </p>
          </div>

          <div className="space-y-4">
            {/* Webhook URL */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Webhook URL</label>
              <input
                placeholder="https://your-server.com/webhook"
                value={defaultWebhookUrl}
                onChange={(e) => setDefaultWebhookUrl(e.target.value)}
                className="h-10 w-full bg-transparent border border-white/10 px-3 text-[14px] font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-white/30"
              />
            </div>

            {/* Webhook Secret */}
            <div className="space-y-2">
              <label className="text-[13px] font-mono text-white/70">Webhook Secret (optional)</label>
              <input
                type="password"
                placeholder="Optional HMAC signing secret"
                value={defaultWebhookSecret}
                onChange={(e) => setDefaultWebhookSecret(e.target.value)}
                className="h-10 w-full bg-transparent border border-white/10 px-3 text-[14px] font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-white/30"
              />
            </div>

            {/* Success Message */}
            {webhookSaved && (
              <div className="border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[13px] font-mono p-3 flex items-center gap-2">
                <Check className="h-4 w-4" />
                Default webhook saved
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (typeof window !== "undefined") {
                    localStorage.setItem("wh_default_webhook_url", defaultWebhookUrl);
                    localStorage.setItem("wh_default_webhook_secret", defaultWebhookSecret);
                  }
                  setWebhookSaved(true);
                  setTimeout(() => setWebhookSaved(false), 3000);
                }}
                className="border border-white/20 px-5 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-white hover:bg-white hover:text-black transition-all flex items-center gap-1"
              >
                <Check className="h-4 w-4" />
                Save Webhook
              </button>
              {defaultWebhookUrl && (
                <button
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
                  className="border border-white/20 px-4 py-2 text-[12px] uppercase tracking-[0.15em] font-mono text-white/50 hover:text-white hover:border-white/40 flex items-center gap-1"
                >
                  <Trash2 className="h-4 w-4" />
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Saved Proxies */}
        <div className="border border-white/10 bg-white/[0.02] p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-[16px] font-bold text-white font-mono uppercase tracking-wider">Saved Proxies</h2>
          </div>
          {proxies.length === 0 ? (
            <p className="text-white/40 text-[13px] font-mono text-center py-8">
              No proxies configured. Add proxies above to enable rotating proxy support.
            </p>
          ) : (
            <div className="space-y-3">
              {proxies.map((proxy) => (
                <div
                  key={proxy.id}
                  className="border border-white/10 bg-white/[0.02] p-4 flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <Globe className="h-4 w-4 text-white/50" />
                      <code className="text-[12px] text-white/40 font-mono">{proxy.proxy_url_masked}</code>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="border border-white/20 text-white/50 text-[11px] font-mono uppercase px-2 py-0.5">{proxy.proxy_type}</span>
                      {proxy.is_active ? (
                        <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-emerald-500/30 text-emerald-400 bg-emerald-500/10">Active</span>
                      ) : (
                        <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 border border-white/20 text-white/40">Inactive</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteProxy(proxy.id)}
                    className="text-white/30 hover:text-red-400 p-2"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
