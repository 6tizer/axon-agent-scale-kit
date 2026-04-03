import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatAxon(amount: number, decimals = 4): string {
  if (amount === 0) return "0 AXON";
  if (amount < 0.0001) return `<0.0001 AXON`;
  return `${amount.toFixed(decimals)} AXON`;
}

export function shortAddr(addr: string | null | undefined, chars = 8): string {
  if (!addr) return "—";
  if (addr.length <= chars * 2 + 3) return addr;
  return `${addr.slice(0, chars)}...${addr.slice(-chars)}`;
}

export function formatTs(ts: number | string | null | undefined): string {
  if (!ts) return "—";
  try {
    const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}

export function validatorStatusLabel(status: string): string {
  if (!status) return "Unknown";
  const map: Record<string, string> = {
    BOND_STATUS_BONDED: "BONDED",
    BOND_STATUS_UNBONDING: "UNBONDING",
    BOND_STATUS_UNBONDED: "UNBONDED",
    bonded: "BONDED",
    unbonding: "UNBONDING",
    unbonded: "UNBONDED",
  };
  return map[status] ?? status;
}
