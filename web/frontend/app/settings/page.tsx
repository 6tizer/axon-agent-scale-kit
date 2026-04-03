"use client";

import { useState } from "react";
import { getToken, setToken, clearToken, apiFetch } from "@/lib/api";
import { NavBar } from "@/components/NavBar";
import { TokenGate } from "@/components/TokenGate";
import { Settings, Eye, EyeOff, Trash2 } from "lucide-react";

export default function SettingsPage() {
  const [newToken, setNewToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const currentToken = typeof window !== "undefined" ? getToken() : "";

  async function handleSave() {
    if (!newToken || saving) return;
    const oldToken = getToken();
    setSaving(true);
    setError("");
    setToken(newToken);
    try {
      await apiFetch("/agents");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setToken(oldToken); // revert — new token is invalid
      setError("Token verification failed — could not authenticate with this token.");
    } finally {
      setSaving(false);
    }
  }

  function handleClear() {
    clearToken();
    window.location.reload();
  }

  return (
    <TokenGate>
      <NavBar />

      <main className="mx-auto max-w-lg px-4 pb-24 md:pb-8 pt-6">
        <div className="mb-6 flex items-center gap-3">
          <Settings className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold text-foreground">Settings</h1>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-5">
          <h2 className="font-semibold text-foreground">API Token</h2>

          <div>
            <label className="block text-xs text-muted-foreground mb-1.5">
              Current token (masked)
            </label>
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                readOnly
                value={currentToken}
                className="w-full rounded-lg border border-border bg-muted px-3 py-2.5 font-mono text-sm text-foreground focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs text-muted-foreground mb-1.5">
              Update token
            </label>
            <input
              type="password"
              value={newToken}
              onChange={(e) => setNewToken(e.target.value)}
              placeholder="New API token…"
              className="w-full rounded-lg border border-border bg-muted px-3 py-2.5 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={!newToken || saving}
              className="flex-1 rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Verifying…" : saved ? "Saved!" : "Save Token"}
            </button>
            <button
              onClick={handleClear}
              className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm font-medium text-red-400 hover:bg-destructive/20 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Sign Out
            </button>
          </div>

          {error && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            The token is stored in your browser&apos;s localStorage and sent as the{" "}
            <span className="font-mono">X-API-Key</span> header.
            Set <span className="font-mono">AXON_API_TOKEN</span> in the server&apos;s
            systemd unit to match.
          </p>
        </div>
      </main>
    </TokenGate>
  );
}
