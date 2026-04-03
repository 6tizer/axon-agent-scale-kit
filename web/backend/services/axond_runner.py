"""
axond_runner.py — build and execute axond CLI commands via subprocess.

Follows the same pattern as scripts/axond_tx.py:
    subprocess.run(["axond"] + args, ...)

All command builders return both a human-readable string (for the
ConfirmDialog) and the args list to pass to _run().
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import NamedTuple

import config as cfg

_TIMEOUT = 60  # seconds


class CmdResult(NamedTuple):
    ok: bool
    tx_hash: str    # tx hash on success
    error: str      # error message on failure (empty string on success)
    raw_output: str
    dry_run_command: str


# ── Low-level executor ─────────────────────────────────────────────────────────
def _run(args: list[str], timeout: int = _TIMEOUT) -> tuple[int, str, str]:
    """Run axond with args. Returns (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["axond"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "axond binary not found in PATH"
    except Exception as exc:
        return 1, "", str(exc)


def _extract_tx_hash(stdout: str) -> str | None:
    """Extract txhash from axond JSON output."""
    try:
        data = json.loads(stdout)
        return data.get("txhash") or data.get("tx_hash")
    except Exception:
        pass
    for line in stdout.splitlines():
        if "txhash" in line.lower():
            parts = line.split(":")
            if len(parts) >= 2:
                candidate = parts[-1].strip().strip('"').strip(",")
                if len(candidate) == 64:
                    return candidate
    return None


def _fmt(args: list[str]) -> str:
    """Return the full command as a printable string."""
    return "axond " + " ".join(args)


# ── Shared flags ───────────────────────────────────────────────────────────────
def _common_flags() -> list[str]:
    return [
        "--chain-id", cfg.chain_id(),
        "--keyring-dir", str(Path(cfg.keyring_dir()).expanduser()),
        "--keyring-backend", cfg.keyring_backend(),
        "--broadcast-mode", cfg.broadcast_mode(),
        "--node", cfg.cometbft_rpc_url(),
        "--fees", cfg.fees(),
        "--yes",
    ]


# ── Bank send (transfer) ───────────────────────────────────────────────────────
def build_bank_send(from_key: str, to_addr: str, amount_aaxon: int) -> list[str]:
    return [
        "tx", "bank", "send",
        from_key,
        to_addr,
        f"{amount_aaxon}aaxon",
    ] + _common_flags()


def run_bank_send(from_key: str, to_addr: str, amount_aaxon: int) -> CmdResult:
    args = build_bank_send(from_key, to_addr, amount_aaxon)
    cmd_str = _fmt(args)
    rc, stdout, stderr = _run(args)
    if rc != 0:
        return CmdResult(ok=False, tx_hash="", error=stderr or stdout, raw_output=stderr, dry_run_command=cmd_str)
    tx_hash = _extract_tx_hash(stdout) or ""
    return CmdResult(ok=True, tx_hash=tx_hash, error="", raw_output=stdout, dry_run_command=cmd_str)


# ── Add stake ─────────────────────────────────────────────────────────────────
def build_add_stake(agent_name: str, amount_aaxon: int) -> list[str]:
    """
    axond tx agent add-stake --amount {amount}aaxon --from {agent_name} ...
    """
    return [
        "tx", "agent", "add-stake",
        "--amount", f"{amount_aaxon}aaxon",
        "--from", agent_name,
    ] + _common_flags()


def run_add_stake(agent_name: str, amount_aaxon: int) -> CmdResult:
    args = build_add_stake(agent_name, amount_aaxon)
    cmd_str = _fmt(args)
    rc, stdout, stderr = _run(args)
    if rc != 0:
        return CmdResult(ok=False, tx_hash="", error=stderr or stdout, raw_output=stderr, dry_run_command=cmd_str)
    tx_hash = _extract_tx_hash(stdout) or ""
    return CmdResult(ok=True, tx_hash=tx_hash, error="", raw_output=stdout, dry_run_command=cmd_str)


# ── Unjail ────────────────────────────────────────────────────────────────────
def build_unjail(validator_key: str = cfg.VALIDATOR_AGENT_NAME) -> list[str]:
    return [
        "tx", "slashing", "unjail",
        "--from", validator_key,
    ] + _common_flags()


def run_unjail(validator_key: str = cfg.VALIDATOR_AGENT_NAME) -> CmdResult:
    args = build_unjail(validator_key)
    cmd_str = _fmt(args)
    rc, stdout, stderr = _run(args)
    if rc != 0:
        return CmdResult(ok=False, tx_hash="", error=stderr or stdout, raw_output=stderr, dry_run_command=cmd_str)
    tx_hash = _extract_tx_hash(stdout) or ""
    return CmdResult(ok=True, tx_hash=tx_hash, error="", raw_output=stdout, dry_run_command=cmd_str)


# ── Dry-run helpers (return command string without executing) ──────────────────
def dry_run_bank_send(from_key: str, to_addr: str, amount_aaxon: int) -> str:
    return _fmt(build_bank_send(from_key, to_addr, amount_aaxon))


def dry_run_add_stake(agent_name: str, amount_aaxon: int) -> str:
    return _fmt(build_add_stake(agent_name, amount_aaxon))


def dry_run_unjail(validator_key: str = cfg.VALIDATOR_AGENT_NAME) -> str:
    return _fmt(build_unjail(validator_key))


# ── Async wrappers (use from FastAPI async route handlers) ─────────────────────
# These prevent blocking the uvicorn event loop during long-running subprocess
# calls (axond tx can take 5-30 seconds waiting for block confirmation).

async def run_bank_send_async(from_key: str, to_addr: str, amount_aaxon: int) -> CmdResult:
    return await asyncio.to_thread(run_bank_send, from_key, to_addr, amount_aaxon)


async def run_add_stake_async(agent_name: str, amount_aaxon: int) -> CmdResult:
    return await asyncio.to_thread(run_add_stake, agent_name, amount_aaxon)


async def run_unjail_async(validator_key: str = cfg.VALIDATOR_AGENT_NAME) -> CmdResult:
    return await asyncio.to_thread(run_unjail, validator_key)
