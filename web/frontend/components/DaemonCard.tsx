"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { type Daemon, api } from "@/lib/api";
import { Activity, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

interface DaemonCardProps {
  daemon: Daemon;
  onRestarted?: () => void;
}

export function DaemonCard({ daemon, onRestarted }: DaemonCardProps) {
  const [restarting, setRestarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState<string | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);

  const isActive = daemon.status === "active";
  const isFailed = daemon.status === "failed";

  const shortName = daemon.name
    .replace(".service", "")
    .replace("axon-", "")
    .replace("-daemon", "");

  const statusColor = isActive
    ? "text-green-400"
    : isFailed
    ? "text-red-400"
    : "text-yellow-400";

  const dotColor = isActive
    ? "bg-green-500"
    : isFailed
    ? "bg-red-500"
    : "bg-yellow-500";

  async function handleRestart() {
    if (!confirmRestart) {
      setConfirmRestart(true);
      setTimeout(() => setConfirmRestart(false), 5000);
      return;
    }
    setConfirmRestart(false);
    setRestarting(true);
    setError(null);
    try {
      const res = await api.restartDaemon(daemon.name);
      if (!res.ok) setError(res.error ?? "Restart failed");
      else onRestarted?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setRestarting(false);
    }
  }

  async function handleToggleLogs() {
    if (showLogs) {
      setShowLogs(false);
      setLogs(null); // reset cache so next open always fetches fresh
      return;
    }
    setShowLogs(true);
    setLoadingLogs(true);
    try {
      const res = await api.daemonLogs(daemon.name);
      setLogs(res.logs);
    } catch {
      setLogs("Could not fetch logs.");
    } finally {
      setLoadingLogs(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4",
        isActive ? "border-green-500/30" : isFailed ? "border-red-500/30" : "border-yellow-500/30"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className={cn("h-2.5 w-2.5 rounded-full shrink-0 animate-pulse", dotColor)} />
          <div>
            <div className="font-mono text-sm font-semibold capitalize text-foreground">
              {shortName}
            </div>
            <div className={cn("text-xs font-medium", statusColor)}>
              {daemon.status}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleToggleLogs}
            className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Activity className="h-3 w-3" />
            Logs
            {showLogs ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>

          <button
            onClick={handleRestart}
            disabled={restarting}
            className={cn(
              "flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium transition-colors",
              confirmRestart
                ? "bg-orange-500/20 border border-orange-500/60 text-orange-300 hover:bg-orange-500/30"
                : "bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20"
            )}
          >
            <RefreshCw
              className={cn("h-3 w-3", restarting && "animate-spin")}
            />
            {restarting
              ? "Restarting…"
              : confirmRestart
              ? "Confirm?"
              : "Restart"}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-2 rounded bg-destructive/10 px-2 py-1 text-xs text-red-400">
          {error}
        </p>
      )}

      {showLogs && (
        <div className="mt-3 rounded border border-border bg-muted/50">
          {loadingLogs ? (
            <p className="p-3 text-xs text-muted-foreground">Loading logs…</p>
          ) : (
            <pre className="max-h-48 overflow-auto p-3 font-mono text-[11px] text-muted-foreground whitespace-pre-wrap">
              {logs || "No logs available."}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
