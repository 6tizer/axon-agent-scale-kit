"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { X, AlertTriangle, Terminal } from "lucide-react";

interface ConfirmDialogProps {
  title: string;
  description?: string;
  command: string;
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
  result?: { ok: boolean; tx_hash?: string; error?: string } | null;
}

export function ConfirmDialog({
  title,
  description,
  command,
  open,
  onConfirm,
  onCancel,
  loading = false,
  result,
}: ConfirmDialogProps) {
  const [confirmText, setConfirmText] = useState("");

  // Reset input when dialog opens
  useEffect(() => {
    if (open) setConfirmText("");
  }, [open]);

  // Close on Escape key (unless a transaction is in progress)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, loading, onCancel]);

  if (!open) return null;

  const canConfirm = confirmText.toLowerCase() === "confirm";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={!loading ? onCancel : undefined}
      />

      {/* Dialog */}
      <div className="relative z-10 w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2 text-yellow-400">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-semibold text-foreground">{title}</span>
          </div>
          {!loading && (
            <button
              onClick={onCancel}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}

          {/* Command preview */}
          <div className="rounded-lg border border-border bg-muted/50">
            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
              <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[11px] text-muted-foreground uppercase tracking-wide">
                Command to execute
              </span>
            </div>
            <pre className="overflow-x-auto p-3 font-mono text-xs text-foreground whitespace-pre-wrap break-all">
              {command}
            </pre>
          </div>

          {/* Result */}
          {result && (
            <div
              className={cn(
                "rounded-lg border p-3 text-sm",
                result.ok
                  ? "border-green-500/40 bg-green-500/10 text-green-300"
                  : "border-red-500/40 bg-red-500/10 text-red-300"
              )}
            >
              {result.ok ? (
                <div>
                  <p className="font-semibold">Transaction submitted</p>
                  {result.tx_hash && (
                    <p className="mt-1 font-mono text-xs break-all">
                      TX: {result.tx_hash}
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <p className="font-semibold">Transaction failed</p>
                  {result.error && (
                    <p className="mt-1 text-xs break-all">{result.error}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Confirm input (only show if not yet submitted) */}
          {!result && (
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Type <span className="font-mono font-medium text-foreground">confirm</span> to proceed
              </label>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="confirm"
                disabled={loading}
                className="w-full rounded border border-border bg-muted px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none disabled:opacity-50"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canConfirm && !loading) onConfirm();
                }}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-border px-5 py-4">
          {result ? (
            <button
              onClick={onCancel}
              className="rounded px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/80 transition-colors"
            >
              Close
            </button>
          ) : (
            <>
              <button
                onClick={onCancel}
                disabled={loading}
                className="rounded px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={!canConfirm || loading}
                className={cn(
                  "rounded px-4 py-2 text-sm font-medium transition-colors",
                  canConfirm && !loading
                    ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    : "bg-muted text-muted-foreground cursor-not-allowed opacity-50"
                )}
              >
                {loading ? "Executing…" : "Execute"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
