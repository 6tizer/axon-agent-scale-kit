"use client";

import { type ChallengeEvent } from "@/lib/api";
import { formatTs } from "@/lib/utils";
import { CheckCircle, XCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChallengeTableProps {
  events: ChallengeEvent[];
  loading?: boolean;
  error?: string;
}

export function ChallengeTable({ events, loading, error }: ChallengeTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-red-400">
        {error}
      </p>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
        <Clock className="h-8 w-8 opacity-40" />
        <p>No challenge events recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Time
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Type
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Agent
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Epoch
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Result
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                TX Hash
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {events.map((e, i) => (
              <EventRow key={`${e.ts}-${e.type}-${e.epoch ?? i}`} event={e} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden divide-y divide-border">
        {events.map((e, i) => (
          <MobileEventCard key={`${e.ts}-${e.type}-${e.epoch ?? i}`} event={e} />
        ))}
      </div>
    </div>
  );
}

function EventRow({ event: e }: { event: ChallengeEvent }) {
  return (
    <tr className="hover:bg-muted/20 transition-colors">
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
        {formatTs(e.ts)}
      </td>
      <td className="px-4 py-3">
        <EventTypeBadge type={e.type} />
      </td>
      <td className="px-4 py-3 font-mono text-xs text-foreground">
        {e.agent ?? "—"}
      </td>
      <td className="px-4 py-3 font-mono text-xs text-foreground">
        {e.epoch != null ? `#${e.epoch}` : "—"}
      </td>
      <td className="px-4 py-3">
        <StatusIcon ok={e.ok} type={e.type} error={e.error} />
      </td>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground max-w-[120px] truncate">
        {e.tx_hash ? (
          <span title={e.tx_hash}>{e.tx_hash.slice(0, 12)}…</span>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

function MobileEventCard({ event: e }: { event: ChallengeEvent }) {
  return (
    <div className="p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <EventTypeBadge type={e.type} />
        <StatusIcon ok={e.ok} type={e.type} error={e.error} />
      </div>
      <div className="text-xs text-muted-foreground">{formatTs(e.ts)}</div>
      {e.agent && (
        <div className="font-mono text-xs text-foreground">{e.agent}</div>
      )}
      {e.epoch != null && (
        <div className="text-xs text-muted-foreground">Epoch #{e.epoch}</div>
      )}
      {e.tx_hash && (
        <div className="font-mono text-[11px] text-muted-foreground truncate">
          {e.tx_hash.slice(0, 20)}…
        </div>
      )}
    </div>
  );
}

function EventTypeBadge({ type }: { type: string }) {
  const label = type.replace("challenge_", "").replace("_", " ");
  const colorMap: Record<string, string> = {
    challenge_commit: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    challenge_reveal: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    challenge_batch_done:
      "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
    challenge_run: "bg-teal-500/15 text-teal-400 border-teal-500/30",
    challenge_error: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  return (
    <span
      className={cn(
        "rounded border px-2 py-0.5 text-[11px] font-medium capitalize",
        colorMap[type] ?? "bg-muted text-muted-foreground border-border"
      )}
    >
      {label}
    </span>
  );
}

function StatusIcon({
  ok,
  type,
  error,
}: {
  ok?: boolean;
  type: string;
  error?: string;
}) {
  if (type === "challenge_error" || error) {
    return <span title={error}><XCircle className="h-4 w-4 text-red-400" /></span>;
  }
  if (ok === false) {
    return <XCircle className="h-4 w-4 text-red-400" />;
  }
  if (ok === true) {
    return <CheckCircle className="h-4 w-4 text-green-400" />;
  }
  return <Clock className="h-4 w-4 text-muted-foreground" />;
}
