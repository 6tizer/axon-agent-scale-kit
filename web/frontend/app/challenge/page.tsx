"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { ChallengeHistoryResponse } from "@/lib/api";
import { ChallengeTable } from "@/components/ChallengeTable";
import { NavBar } from "@/components/NavBar";
import { TokenGate } from "@/components/TokenGate";
import { Swords } from "lucide-react";

export default function ChallengePage() {
  const { data, error, isLoading, mutate } = useSWR<ChallengeHistoryResponse>(
    "/api/challenge/history?limit=40",
    swrFetcher,
    { refreshInterval: 30_000 }
  );

  return (
    <TokenGate>
      <NavBar onRefresh={() => mutate()} refreshing={isLoading} />

      <main className="mx-auto max-w-5xl px-4 pb-24 md:pb-8 pt-6">
        <div className="mb-6 flex items-center gap-3">
          <Swords className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-xl font-bold text-foreground">
              Challenge History
            </h1>
            <p className="text-sm text-muted-foreground">
              Recent AI challenge commit / reveal events. Only{" "}
              <span className="font-mono text-foreground">qqclaw-validator</span>{" "}
              is eligible to submit challenge TXs (protocol requirement).
            </p>
          </div>
        </div>

        {/* Summary stats */}
        {data && !error && (
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MiniStat
              label="Total Events"
              value={data.count}
            />
            <MiniStat
              label="Commits"
              value={data.events.filter((e) => e.type === "challenge_commit").length}
            />
            <MiniStat
              label="Reveals"
              value={data.events.filter((e) => e.type === "challenge_reveal").length}
            />
            <MiniStat
              label="Errors"
              value={data.events.filter((e) => e.type === "challenge_error" || e.ok === false).length}
              error={data.events.filter((e) => e.type === "challenge_error" || e.ok === false).length > 0}
            />
          </div>
        )}

        <ChallengeTable
          events={data?.events ?? []}
          loading={isLoading}
          error={error ? "Failed to load challenge history." : undefined}
        />
      </main>
    </TokenGate>
  );
}

function MiniStat({
  label,
  value,
  error,
}: {
  label: string;
  value: number;
  error?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-1 text-xl font-bold tabular-nums ${
          error && value > 0 ? "text-red-400" : "text-foreground"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
