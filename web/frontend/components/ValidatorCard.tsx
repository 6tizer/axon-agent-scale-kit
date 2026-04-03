"use client";

import { cn } from "@/lib/utils";
import { type ValidatorInfo } from "@/lib/api";
import { formatAxon, shortAddr, validatorStatusLabel } from "@/lib/utils";
import { ShieldCheck, ShieldAlert, ShieldOff, ExternalLink } from "lucide-react";

interface ValidatorCardProps {
  validator: ValidatorInfo | null | undefined;
  loading?: boolean;
  error?: string;
}

export function ValidatorCard({ validator, loading, error }: ValidatorCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-5 animate-pulse">
        <div className="h-6 w-48 rounded bg-muted" />
        <div className="mt-4 h-4 w-72 rounded bg-muted" />
      </div>
    );
  }

  if (error || !validator) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-5">
        <div className="flex items-center gap-2 text-destructive">
          <ShieldOff className="h-5 w-5" />
          <span className="font-semibold">Validator status unavailable</span>
        </div>
        {error && <p className="mt-1 text-sm text-muted-foreground">{error}</p>}
      </div>
    );
  }

  const statusLabel = validatorStatusLabel(validator.status);
  const isBonded = statusLabel === "BONDED";
  const isJailed = validator.jailed;

  const StatusIcon = isJailed
    ? ShieldAlert
    : isBonded
    ? ShieldCheck
    : ShieldOff;

  const statusColors = isJailed
    ? {
        border: "border-red-500/60",
        bg: "bg-red-500/5",
        text: "text-red-400",
        badge: "bg-red-500/20 text-red-300 border-red-500/40",
      }
    : isBonded
    ? {
        border: "border-green-500/60",
        bg: "bg-green-500/5",
        text: "text-green-400",
        badge: "bg-green-500/20 text-green-300 border-green-500/40",
      }
    : {
        border: "border-yellow-500/60",
        bg: "bg-yellow-500/5",
        text: "text-yellow-400",
        badge: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
      };

  return (
    <div
      className={cn(
        "rounded-lg border p-5",
        statusColors.border,
        statusColors.bg
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* Left: identity */}
        <div>
          <div className="flex items-center gap-2">
            <StatusIcon className={cn("h-5 w-5", statusColors.text)} />
            <h2 className="text-lg font-bold text-foreground">
              {validator.moniker || "QQClaw-Validator"}
            </h2>
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {shortAddr(validator.valoper, 12)}
          </p>
        </div>

        {/* Right: status badges */}
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "rounded border px-3 py-1 text-sm font-bold uppercase tracking-wide",
              statusColors.badge
            )}
          >
            {statusLabel}
          </span>
          {isJailed && (
            <span className="rounded border border-red-500/40 bg-red-500/20 px-3 py-1 text-sm font-bold text-red-300">
              JAILED
            </span>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label="Staked" value={`${validator.tokens_axon.toFixed(2)} AXON`} />
        <Stat
          label="Commission"
          value={`${(parseFloat(validator.commission_rate) * 100).toFixed(1)}%`}
        />
        <Stat
          label="Voting Power"
          value={validator.tokens_axon.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}
        />
      </div>

      {/* Explorer link */}
      <div className="mt-3">
        <a
          href={`https://explorer.axonchain.ai/validators/${validator.valoper}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          View on Explorer
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-foreground">
        {value}
      </div>
    </div>
  );
}
