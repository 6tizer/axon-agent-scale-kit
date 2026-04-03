"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { AgentsResponse, ValidatorResponse, DaemonsResponse } from "@/lib/api";
import { AgentCard } from "@/components/AgentCard";
import { ValidatorCard } from "@/components/ValidatorCard";
import { DaemonCard } from "@/components/DaemonCard";
import { NavBar } from "@/components/NavBar";
import { TokenGate } from "@/components/TokenGate";
import { Users, Server, RefreshCw } from "lucide-react";

const REFRESH_INTERVAL = 30_000; // 30 seconds

export default function DashboardPage() {
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [manualRefreshing, setManualRefreshing] = useState(false);

  const {
    data: agentsData,
    error: agentsError,
    isLoading: agentsLoading,
    mutate: mutateAgents,
  } = useSWR<AgentsResponse>("/api/agents", swrFetcher, {
    refreshInterval: REFRESH_INTERVAL,
    onSuccess: () => setLastRefresh(new Date()),
  });

  const {
    data: validatorData,
    error: validatorError,
    isLoading: validatorLoading,
    mutate: mutateValidator,
  } = useSWR<ValidatorResponse>("/api/validator", swrFetcher, {
    refreshInterval: REFRESH_INTERVAL,
    onSuccess: () => setLastRefresh(new Date()),
  });

  const {
    data: daemonsData,
    isLoading: daemonsLoading,
    mutate: mutateDaemons,
  } = useSWR<DaemonsResponse>("/api/daemons", swrFetcher, {
    refreshInterval: REFRESH_INTERVAL,
    onSuccess: () => setLastRefresh(new Date()),
  });

  const handleRefresh = useCallback(async () => {
    setManualRefreshing(true);
    await Promise.all([mutateAgents(), mutateValidator(), mutateDaemons()]);
    setLastRefresh(new Date());
    setManualRefreshing(false);
  }, [mutateAgents, mutateValidator, mutateDaemons]);

  const agents = agentsData?.agents ?? [];
  const validatorAgent = agents.find((a) => a.is_validator);
  const regularAgents = agents.filter((a) => !a.is_validator);

  const onlineCount = agents.filter((a) => a.online).length;
  const totalCount = agents.length;

  return (
    <TokenGate>
      <NavBar
        lastRefresh={lastRefresh}
        onRefresh={handleRefresh}
        refreshing={manualRefreshing || agentsLoading}
      />

      <main className="mx-auto max-w-7xl px-4 pb-24 md:pb-8 pt-6 space-y-8">
        {/* Summary stats */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            label="Online"
            value={`${onlineCount}/${totalCount}`}
            color={onlineCount === totalCount ? "green" : "yellow"}
          />
          <StatCard
            label="Registered"
            value={agents.filter((a) => a.registered).length}
            color="blue"
          />
          <StatCard
            label="Staked"
            value={agents.filter((a) => a.staked).length}
            color="blue"
          />
          <StatCard
            label="Suspended"
            value={agents.filter((a) => a.suspended).length}
            color={agents.filter((a) => a.suspended).length > 0 ? "red" : "green"}
          />
        </div>

        {/* Validator status (prominent) */}
        <section>
          <SectionHeader icon={<Server className="h-4 w-4" />} title="Validator" />
          <ValidatorCard
            validator={validatorData?.validator}
            loading={validatorLoading}
            error={validatorData?.error}
          />
        </section>

        {/* Daemons */}
        <section>
          <SectionHeader icon={<RefreshCw className="h-4 w-4" />} title="System Daemons" />
          {daemonsLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="h-16 rounded-lg bg-muted animate-pulse" />
              <div className="h-16 rounded-lg bg-muted animate-pulse" />
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(daemonsData?.daemons ?? []).map((daemon) => (
                <DaemonCard
                  key={daemon.name}
                  daemon={daemon}
                  onRestarted={handleRefresh}
                />
              ))}
            </div>
          )}
        </section>

        {/* Validator agent card */}
        {validatorAgent && (
          <section>
            <SectionHeader icon={<Users className="h-4 w-4" />} title="Validator Agent" />
            <div className="max-w-sm">
              <AgentCard agent={validatorAgent} />
            </div>
          </section>
        )}

        {/* Regular agents */}
        <section>
          <SectionHeader
            icon={<Users className="h-4 w-4" />}
            title={`Agents (${regularAgents.length})`}
          />
          {agentsLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-48 rounded-lg bg-muted animate-pulse" />
              ))}
            </div>
          ) : agentsError ? (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-red-400">
              Failed to load agents. Check your API token.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {regularAgents.map((agent) => (
                <AgentCard key={agent.name} agent={agent} />
              ))}
            </div>
          )}
        </section>
      </main>
    </TokenGate>
  );
}

function SectionHeader({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <div className="text-primary">{icon}</div>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color: "green" | "blue" | "yellow" | "red";
}) {
  const colors = {
    green: "text-green-400",
    blue: "text-blue-400",
    yellow: "text-yellow-400",
    red: "text-red-400",
  };
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${colors[color]}`}>
        {value}
      </div>
    </div>
  );
}
