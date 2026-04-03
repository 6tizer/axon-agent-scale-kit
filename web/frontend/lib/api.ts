/**
 * API client — all requests include X-API-Key from localStorage.
 * The API base URL is set via the NEXT_PUBLIC_API_URL env var
 * (defaults to /api for production nginx proxy).
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "/api";

const STORAGE_KEY = "axon_api_token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// ── Core fetch wrapper ─────────────────────────────────────────────────────────
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-API-Key": token } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (resp.status === 401) {
    throw new ApiError(401, "Unauthorized — check your API token.");
  }
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body);
  }
  return resp.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── SWR fetcher ────────────────────────────────────────────────────────────────
// Strip the API_BASE prefix from SWR cache keys before passing to apiFetch,
// so keys like "/api/agents" work regardless of what API_BASE is set to.
export const swrFetcher = <T = unknown>(url: string): Promise<T> => {
  const path = url.startsWith(API_BASE)
    ? url.slice(API_BASE.length)
    : url.startsWith("/api")
    ? url.slice(4)
    : url;
  return apiFetch<T>(path);
};

// ── Typed request helpers ──────────────────────────────────────────────────────
export type Agent = {
  name: string;
  is_validator: boolean;
  online: boolean;
  registered: boolean;
  staked: boolean;
  service_active: boolean;
  wallet_address: string | null;
  bech32_address: string | null;
  balance_axon: number;
  reputation: number | null;
  last_heartbeat_block: number | null;
  heartbeat_at: number | string | null;
  suspended: boolean;
};

export type AgentsResponse = {
  ok: boolean;
  agents: Agent[];
};

export type ValidatorInfo = {
  moniker: string;
  status: string;
  jailed: boolean;
  tokens_axon: number;
  commission_rate: string;
  valoper: string;
};

export type ValidatorResponse = {
  ok: boolean;
  validator?: ValidatorInfo;
  error?: string;
};

export type ChallengeEvent = {
  ts: number | string;
  type: string;
  agent?: string;
  epoch?: number;
  ok?: boolean;
  tx_hash?: string;
  error?: string;
  [key: string]: unknown;
};

export type ChallengeHistoryResponse = {
  ok: boolean;
  events: ChallengeEvent[];
  count: number;
};

export type Daemon = {
  name: string;
  status: "active" | "inactive" | "failed" | "unknown" | string;
};

export type DaemonsResponse = {
  ok: boolean;
  daemons: Daemon[];
};

export type OperationResponse = {
  ok: boolean;
  dry_run: boolean;
  dry_run_command: string;
  tx_hash?: string;
  error?: string;   // separate error message field (distinct from tx_hash)
  raw_output?: string;
  message?: string;
};

// ── API calls ──────────────────────────────────────────────────────────────────
export const api = {
  agents: () => apiFetch<AgentsResponse>("/agents"),
  validator: () => apiFetch<ValidatorResponse>("/validator"),
  challengeHistory: (limit = 20) =>
    apiFetch<ChallengeHistoryResponse>(`/challenge/history?limit=${limit}`),
  daemons: () => apiFetch<DaemonsResponse>("/daemons"),
  daemonLogs: (name: string) =>
    apiFetch<{ ok: boolean; logs: string }>(`/daemons/${encodeURIComponent(name)}/logs`),

  restartDaemon: (name: string) =>
    apiFetch<{ ok: boolean; daemon: string; status: string; error?: string }>(
      `/daemons/${encodeURIComponent(name)}/restart`,
      { method: "POST" }
    ),

  transferDryRun: (from_agent: string, to_address: string, amount_axon: number) =>
    apiFetch<OperationResponse>("/transfer", {
      method: "POST",
      body: JSON.stringify({ from_agent, to_address, amount_axon, confirmed: false }),
    }),
  transferConfirm: (from_agent: string, to_address: string, amount_axon: number) =>
    apiFetch<OperationResponse>("/transfer", {
      method: "POST",
      body: JSON.stringify({ from_agent, to_address, amount_axon, confirmed: true }),
    }),

  stakeDryRun: (agent_name: string, amount_axon: number) =>
    apiFetch<OperationResponse>("/stake", {
      method: "POST",
      body: JSON.stringify({ agent_name, amount_axon, confirmed: false }),
    }),
  stakeConfirm: (agent_name: string, amount_axon: number) =>
    apiFetch<OperationResponse>("/stake", {
      method: "POST",
      body: JSON.stringify({ agent_name, amount_axon, confirmed: true }),
    }),

  unjailDryRun: () =>
    apiFetch<OperationResponse>("/unjail", {
      method: "POST",
      body: JSON.stringify({ confirmed: false }),
    }),
  unjailConfirm: () =>
    apiFetch<OperationResponse>("/unjail", {
      method: "POST",
      body: JSON.stringify({ confirmed: true }),
    }),
};
