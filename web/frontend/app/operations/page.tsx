"use client";

import { useState } from "react";
import useSWR from "swr";
import { swrFetcher, api } from "@/lib/api";
import type { AgentsResponse } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { NavBar } from "@/components/NavBar";
import { TokenGate } from "@/components/TokenGate";
import { ArrowRightLeft, Plus, ShieldOff } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "transfer" | "stake" | "unjail";

export default function OperationsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("transfer");

  const { data: agentsData } = useSWR<AgentsResponse>("/api/agents", swrFetcher);
  const agents = agentsData?.agents ?? [];
  const agentNames = agents.map((a) => a.name);

  return (
    <TokenGate>
      <NavBar />

      <main className="mx-auto max-w-2xl px-4 pb-24 md:pb-8 pt-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-foreground">Operations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            On-chain write operations. All commands require confirmation before execution.
            Operations are executed via the server-side{" "}
            <span className="font-mono text-foreground">axond</span> keyring.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg border border-border bg-muted p-1 mb-6">
          {(["transfer", "stake", "unjail"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "flex-1 rounded-md px-3 py-2 text-sm font-medium capitalize transition-colors",
                activeTab === tab
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "transfer" && (
          <TransferForm agentNames={agentNames} />
        )}
        {activeTab === "stake" && <StakeForm agentNames={agentNames} />}
        {activeTab === "unjail" && <UnjailForm />}
      </main>
    </TokenGate>
  );
}

// ── Transfer Form ────────────────────────────────────────────────────────────
function TransferForm({ agentNames }: { agentNames: string[] }) {
  const [fromAgent, setFromAgent] = useState("");
  const [toAddress, setToAddress] = useState("");
  const [amount, setAmount] = useState("");
  const [dialog, setDialog] = useState<{
    open: boolean;
    command: string;
    loading: boolean;
    result: { ok: boolean; tx_hash?: string; error?: string } | null;
  }>({ open: false, command: "", loading: false, result: null });

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    if (!fromAgent || !toAddress || !amount) return;
    try {
      const res = await api.transferDryRun(fromAgent, toAddress, parseFloat(amount));
      setDialog({ open: true, command: res.dry_run_command, loading: false, result: null });
    } catch (err: unknown) {
      // #region agent debug
      fetch('http://127.0.0.1:7370/ingest/32bda30b-d6ad-424e-9eb6-358857c9337b',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'73fe36'},body:JSON.stringify({sessionId:'73fe36',location:'operations/page.tsx:transfer_preview',message:'handlePreview_error',data:{error:String(err)},timestamp:Date.now(),hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      setDialog({ open: true, command: "", loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Failed to get preview" } });
    }
  }

  async function handleConfirm() {
    setDialog((d) => ({ ...d, loading: true }));
    try {
      const res = await api.transferConfirm(fromAgent, toAddress, parseFloat(amount));
      setDialog((d) => ({
        ...d,
        loading: false,
        result: { ok: res.ok, tx_hash: res.tx_hash, error: res.ok ? undefined : (res.error ?? res.tx_hash) },
      }));
    } catch (err: unknown) {
      // #region agent debug
      fetch('http://127.0.0.1:7370/ingest/32bda30b-d6ad-424e-9eb6-358857c9337b',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'73fe36'},body:JSON.stringify({sessionId:'73fe36',location:'operations/page.tsx:transfer_confirm',message:'handleConfirm_error',data:{error:String(err)},timestamp:Date.now(),hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      setDialog((d) => ({ ...d, loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Request failed" } }));
    }
  }

  return (
    <>
      <form onSubmit={handlePreview} className="space-y-4">
        <FormCard title="Send AXON" icon={<ArrowRightLeft className="h-4 w-4" />}>
          <Field label="From Agent">
            <AgentSelect value={fromAgent} onChange={setFromAgent} agentNames={agentNames} />
          </Field>
          <Field label="To Address (axon1... or 0x...)">
            <input
              type="text"
              value={toAddress}
              onChange={(e) => setToAddress(e.target.value)}
              placeholder="axon1abc..."
              required
              className={inputCls}
            />
          </Field>
          <Field label="Amount (AXON)">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="1.0"
              min="0.000001"
              step="any"
              required
              className={inputCls}
            />
          </Field>
          <PreviewButton />
        </FormCard>
      </form>

      <ConfirmDialog
        title="Confirm Transfer"
        description={`Send ${amount} AXON from ${fromAgent} to ${toAddress}`}
        command={dialog.command}
        open={dialog.open}
        onConfirm={handleConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
        loading={dialog.loading}
        result={dialog.result}
      />
    </>
  );
}

// ── Stake Form ───────────────────────────────────────────────────────────────
function StakeForm({ agentNames }: { agentNames: string[] }) {
  const [agentName, setAgentName] = useState("");
  const [amount, setAmount] = useState("");
  const [dialog, setDialog] = useState<{
    open: boolean;
    command: string;
    loading: boolean;
    result: { ok: boolean; tx_hash?: string; error?: string } | null;
  }>({ open: false, command: "", loading: false, result: null });

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    if (!agentName || !amount) return;
    try {
      const res = await api.stakeDryRun(agentName, parseFloat(amount));
      setDialog({ open: true, command: res.dry_run_command, loading: false, result: null });
    } catch (err: unknown) {
      setDialog({ open: true, command: "", loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Failed to get preview" } });
    }
  }

  async function handleConfirm() {
    setDialog((d) => ({ ...d, loading: true }));
    try {
      const res = await api.stakeConfirm(agentName, parseFloat(amount));
      setDialog((d) => ({
        ...d,
        loading: false,
        result: { ok: res.ok, tx_hash: res.tx_hash, error: res.ok ? undefined : (res.error ?? res.tx_hash) },
      }));
    } catch (err: unknown) {
      setDialog((d) => ({ ...d, loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Request failed" } }));
    }
  }

  return (
    <>
      <form onSubmit={handlePreview} className="space-y-4">
        <FormCard title="Add Stake" icon={<Plus className="h-4 w-4" />}>
          <Field label="Agent">
            <AgentSelect value={agentName} onChange={setAgentName} agentNames={agentNames} />
          </Field>
          <Field label="Amount (AXON)">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="100"
              min="1"
              step="any"
              required
              className={inputCls}
            />
          </Field>
          <p className="text-xs text-muted-foreground">
            Stake is sent from the agent&apos;s own wallet. Ensure the wallet has
            sufficient balance.
          </p>
          <PreviewButton />
        </FormCard>
      </form>

      <ConfirmDialog
        title="Confirm Stake"
        description={`Add ${amount} AXON stake to ${agentName}`}
        command={dialog.command}
        open={dialog.open}
        onConfirm={handleConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
        loading={dialog.loading}
        result={dialog.result}
      />
    </>
  );
}

// ── Unjail Form ──────────────────────────────────────────────────────────────
function UnjailForm() {
  const [dialog, setDialog] = useState<{
    open: boolean;
    command: string;
    loading: boolean;
    result: { ok: boolean; tx_hash?: string; error?: string } | null;
  }>({ open: false, command: "", loading: false, result: null });

  async function handlePreview() {
    try {
      const res = await api.unjailDryRun();
      setDialog({ open: true, command: res.dry_run_command, loading: false, result: null });
    } catch (err: unknown) {
      setDialog({ open: true, command: "", loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Failed to get preview" } });
    }
  }

  async function handleConfirm() {
    setDialog((d) => ({ ...d, loading: true }));
    try {
      const res = await api.unjailConfirm();
      setDialog((d) => ({
        ...d,
        loading: false,
        result: { ok: res.ok, tx_hash: res.tx_hash, error: res.ok ? undefined : (res.error ?? res.tx_hash) },
      }));
    } catch (err: unknown) {
      setDialog((d) => ({ ...d, loading: false, result: { ok: false, error: err instanceof Error ? err.message : "Request failed" } }));
    }
  }

  return (
    <>
      <FormCard title="Unjail Validator" icon={<ShieldOff className="h-4 w-4" />}>
        <p className="text-sm text-muted-foreground">
          Send an unjail transaction for{" "}
          <span className="font-mono text-foreground">qqclaw-validator</span>.
          The validator must have been slashed and the unbonding period must have
          passed before unjailing will succeed on-chain.
        </p>
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3 text-sm text-yellow-300">
          This will send a live on-chain transaction from the validator keyring.
          Ensure the validator is genuinely jailed before proceeding.
        </div>
        <button
          onClick={handlePreview}
          type="button"
          className="w-full rounded-lg border border-primary/40 bg-primary/10 px-4 py-2.5 font-medium text-primary hover:bg-primary/20 transition-colors"
        >
          Preview Unjail Command
        </button>
      </FormCard>

      <ConfirmDialog
        title="Confirm Unjail"
        description="Submit unjail transaction for qqclaw-validator"
        command={dialog.command}
        open={dialog.open}
        onConfirm={handleConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
        loading={dialog.loading}
        result={dialog.result}
      />
    </>
  );
}

// ── Shared sub-components ────────────────────────────────────────────────────
const inputCls =
  "w-full rounded-lg border border-border bg-muted px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none font-mono";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function AgentSelect({
  value,
  onChange,
  agentNames,
}: {
  value: string;
  onChange: (v: string) => void;
  agentNames: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required
      className={cn(inputCls, "cursor-pointer")}
    >
      <option value="">— select agent —</option>
      {agentNames.map((n) => (
        <option key={n} value={n}>
          {n}
        </option>
      ))}
    </select>
  );
}

function FormCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2 text-foreground">
        <div className="text-primary">{icon}</div>
        <h2 className="font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function PreviewButton() {
  return (
    <button
      type="submit"
      className="w-full rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      Preview Command
    </button>
  );
}
