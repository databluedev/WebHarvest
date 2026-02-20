"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Key, Plus, Trash2, Copy, Check, Eye, EyeOff } from "lucide-react";

export default function ApiKeysPage() {
  const router = useRouter();
  const [keys, setKeys] = useState<any[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKey, setNewKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    if (!api.getToken()) {
      router.push("/auth/login");
      return;
    }
    loadKeys();
  }, [router]);

  const loadKeys = async () => {
    try {
      const res = await api.listApiKeys();
      setKeys(res);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreate = async () => {
    setLoading(true);
    try {
      const res = await api.createApiKey(newKeyName || undefined);
      setNewKey(res.full_key);
      setShowKey(true);
      setNewKeyName("");
      loadKeys();
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    try {
      await api.revokeApiKey(keyId);
      loadKeys();
    } catch (err) {
      console.error(err);
    }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopied(key);
    setTimeout(() => setCopied(""), 2000);
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto grid-bg">
        <div className="mesh-gradient min-h-full">
        <div className="p-8 max-w-4xl mx-auto">
          <div className="mb-8 animate-float-in">
            <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
            <p className="text-muted-foreground mt-1">
              Manage your API keys for programmatic access
            </p>
          </div>

          {/* Create New Key */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Create New Key</CardTitle>
              <CardDescription>
                API keys authenticate your requests. Prefix: <code className="text-xs bg-muted px-1 py-0.5 rounded">wh_</code>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input
                  placeholder="Key name (optional)"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                />
                <Button onClick={handleCreate} disabled={loading} className="gap-1 shrink-0">
                  <Plus className="h-4 w-4" />
                  Create Key
                </Button>
              </div>

              {newKey && (
                <div className="mt-4 rounded-md border border-primary/30 bg-primary/5 p-4">
                  <p className="text-sm font-medium mb-2">
                    Your new API key (save it now - you won&apos;t see it again):
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-sm bg-muted px-3 py-2 rounded font-mono">
                      {showKey ? newKey : "wh_" + "*".repeat(40)}
                    </code>
                    <Button variant="ghost" size="icon" onClick={() => setShowKey(!showKey)}>
                      {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => copyKey(newKey)}
                    >
                      {copied === newKey ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Key List */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Your API Keys</CardTitle>
            </CardHeader>
            <CardContent>
              {keys.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Key className="h-12 w-12 text-muted-foreground mb-4" />
                  <p className="text-sm text-muted-foreground">No API keys yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {keys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between rounded-md border p-4"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <code className="text-sm font-mono">{key.key_prefix}...</code>
                          {key.name && (
                            <span className="text-sm text-muted-foreground">({key.name})</span>
                          )}
                          <Badge variant={key.is_active ? "success" : "secondary"}>
                            {key.is_active ? "Active" : "Revoked"}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Created {new Date(key.created_at).toLocaleDateString()}
                          {key.last_used_at &&
                            ` | Last used ${new Date(key.last_used_at).toLocaleDateString()}`}
                        </p>
                      </div>
                      {key.is_active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => handleRevoke(key.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Usage Examples */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-lg">Usage Examples</CardTitle>
              <CardDescription>Use your API key in the <code className="text-xs bg-muted px-1 py-0.5 rounded">Authorization</code> header with all requests</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">Scrape a URL</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/scrape \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "links", "screenshot"]
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Crawl an entire website</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/crawl \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://docs.example.com",
    "max_pages": 50,
    "max_depth": 3
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Batch scrape multiple URLs</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/batch/scrape \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "urls": [
      "https://example.com/page-1",
      "https://example.com/page-2",
      "https://example.com/page-3"
    ],
    "formats": ["markdown", "structured_data"],
    "concurrency": 5
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Search & scrape results</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/search \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "best web scraping tools 2025",
    "num_results": 5,
    "engine": "duckduckgo",
    "formats": ["markdown", "links"]
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Map a website (discover all URLs)</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/map \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://example.com",
    "use_sitemap": true,
    "limit": 500
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Extract structured data with AI</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl -X POST https://api-datablue.welocalhost.com/v1/extract \\
  -H "Authorization: Bearer wh_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "urls": ["https://example.com/pricing"],
    "prompt": "Extract all pricing plans with name, price, and features",
    "provider": "openai"
  }'`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Check job status (works for all job types)</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`curl https://api-datablue.welocalhost.com/v1/scrape/JOB_ID \\
  -H "Authorization: Bearer wh_your_api_key"`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Python example</p>
                <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto font-mono">
{`import requests

API_KEY = "wh_your_api_key"
BASE = "https://api-datablue.welocalhost.com/v1"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Start a scrape
resp = requests.post(f"{BASE}/scrape", headers=headers, json={
    "url": "https://example.com",
    "formats": ["markdown", "screenshot", "structured_data"]
})
job_id = resp.json()["job_id"]

# Poll for results
import time
while True:
    status = requests.get(f"{BASE}/scrape/{job_id}", headers=headers).json()
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(2)

print(status["data"][0]["markdown"][:500])`}
                </pre>
              </div>
            </CardContent>
          </Card>
        </div>
        </div>
      </main>
    </div>
  );
}
