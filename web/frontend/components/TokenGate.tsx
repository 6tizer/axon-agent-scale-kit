"use client";

import { useState, useEffect } from "react";
import { getToken, setToken, apiFetch } from "@/lib/api";
import { Shield, Eye, EyeOff } from "lucide-react";

interface TokenGateProps {
  children: React.ReactNode;
}

export function TokenGate({ children }: TokenGateProps) {
  const [token, setTokenState] = useState("");
  const [checking, setChecking] = useState(true);
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [showToken, setShowToken] = useState(false);

  useEffect(() => {
    const existing = getToken();
    if (existing) {
      // Verify it works
      apiFetch("/agents")
        .then(() => setAuthed(true))
        .catch(() => setAuthed(false))
        .finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setToken(token);
    try {
      await apiFetch("/agents");
      setAuthed(true);
    } catch {
      setError("Invalid token. Please check your AXON_API_TOKEN.");
      setToken("");
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-border border-t-primary" />
      </div>
    );
  }

  if (authed) return <>{children}</>;

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-background">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/20">
            <Shield className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Axon Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your API token to continue
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-muted-foreground mb-1.5">
              API Token
            </label>
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                value={token}
                onChange={(e) => setTokenState(e.target.value)}
                placeholder="your-axon-api-token"
                required
                className="w-full rounded-lg border border-border bg-muted px-3 py-2.5 pr-10 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showToken ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!token}
            className="w-full rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Sign In
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          Token is stored in browser localStorage and sent as X-API-Key header.
        </p>
      </div>
    </div>
  );
}
