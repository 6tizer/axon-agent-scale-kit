"use client";

import { cn, formatAxon as fmt, shortAddr, formatTs as fts } from "@/lib/utils";
import { type Agent } from "@/lib/api";
import { Activity, Hash, Shield, Wallet, Clock } from "lucide-react";

interface AgentCardProps {
  agent: Agent;
  className?: string;
}

export function AgentCard({ agent, className }: AgentCardProps) {
  const statusColor = agent.online
    ? "bg-green-500"
    : agent.service_active
    ? "bg-yellow-500"
    : "bg-red-500";

  const statusLabel = agent.online
    ? "Online"
    : agent.service_active
    ? "Degraded"
    : "Offline";

  return (
    <div
      className={cn(
        "relative rounded-lg border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5",
        agent.is_validator && "border-primary/60 bg-primary/5",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {agent.is_validator && (
              <Shield className="h-4 w-4 shrink-0 text-primary" />
            )}
            <span className="truncate font-mono text-sm font-semibold text-foreground">
              {agent.name}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            <span
              className={cn(
                "h-2 w-2 rounded-full shrink-0 animate-pulse",
                statusColor
              )}
            />
            <span
              className={cn(
                "text-xs font-medium",
                agent.online
                  ? "text-green-400"
                  : agent.service_active
                  ? "text-yellow-400"
                  : "text-red-400"
              )}
            >
              {statusLabel}
            </span>
          </div>
        </div>

        {/* Reputation badge */}
        {agent.reputation !== null && (
          <div className="shrink-0 rounded-full bg-muted px-2.5 py-1 text-center">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Rep
            </div>
            <div
              className={cn(
                "text-sm font-bold tabular-nums",
                // 0 is normal for newly registered agents — show neutral color
                (agent.reputation ?? 0) === 0
                  ? "text-muted-foreground"
                  : (agent.reputation ?? 0) >= 70
                  ? "text-green-400"
                  : (agent.reputation ?? 0) >= 30
                  ? "text-yellow-400"
                  : "text-orange-400"
              )}
            >
              {Math.round(agent.reputation ?? 0)}
            </div>
          </div>
        )}
      </div>

      {/* Details */}
      <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Hash className="h-3.5 w-3.5 shrink-0" />
          <span className="font-mono">{shortAddr(agent.bech32_address ?? agent.wallet_address)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Wallet className="h-3.5 w-3.5 shrink-0" />
          <span className="font-medium text-foreground">
            {fmt(agent.balance_axon)}
          </span>
        </div>
        {agent.last_heartbeat_block && (
          <div className="flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 shrink-0" />
            <span>Block #{agent.last_heartbeat_block.toLocaleString()}</span>
          </div>
        )}
        {agent.heartbeat_at && (
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 shrink-0" />
            <span>{fts(agent.heartbeat_at)}</span>
          </div>
        )}
      </div>

      {/* Status chips */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {agent.registered && (
          <Chip color="green">Registered</Chip>
        )}
        {agent.staked && <Chip color="blue">Staked</Chip>}
        {agent.suspended && (
          <Chip color="red">Suspended</Chip>
        )}
        {!agent.registered && (
          <Chip color="red">Not Registered</Chip>
        )}
      </div>
    </div>
  );
}

function Chip({
  children,
  color,
}: {
  children: React.ReactNode;
  color: "green" | "blue" | "red" | "yellow";
}) {
  const colors = {
    green: "bg-green-500/15 text-green-400 border-green-500/30",
    blue: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    red: "bg-red-500/15 text-red-400 border-red-500/30",
    yellow: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  };
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        colors[color]
      )}
    >
      {children}
    </span>
  );
}
