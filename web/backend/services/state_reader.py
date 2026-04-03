"""
state_reader.py — read-only access to deploy_state.json.

All functions are synchronous (file I/O is fast enough at this scale).
Call sites that need async should run these in a thread executor.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from config import STATE_FILE, get_agents_cfg, get_network_cfg


# ── Loader ─────────────────────────────────────────────────────────────────────
def load_state() -> dict[str, Any]:
    """Return the full deploy_state.json contents."""
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except FileNotFoundError:
        return {"agents": {}, "events": [], "requests": {}, "settings": {}}


# ── Agent summary ──────────────────────────────────────────────────────────────
def get_agent_names() -> list[str]:
    """Return agent names from agents.yaml (canonical order)."""
    return [a["name"] for a in get_agents_cfg()]


def get_agent_state(name: str) -> dict[str, Any]:
    """Return the per-agent block from deploy_state.json (empty dict if missing)."""
    return load_state().get("agents", {}).get(name, {})


def get_all_agent_states() -> dict[str, dict[str, Any]]:
    """Return {name: state_dict} for all configured agents."""
    state = load_state()
    agents_block = state.get("agents", {})
    return {name: agents_block.get(name, {}) for name in get_agent_names()}


# ── Challenge history ──────────────────────────────────────────────────────────

def get_challenge_history(limit: int = 20) -> list[dict[str, Any]]:
    """
    Return the last `limit` challenge-related events from state.events,
    newest first.
    """
    events: list[dict[str, Any]] = load_state().get("events", [])
    challenge_events = [
        e for e in events
        if e.get("type", "").startswith("challenge")
    ]
    # Most recent last in the file → reverse to get newest first
    return list(reversed(challenge_events))[:limit]


# ── Wallet addresses ───────────────────────────────────────────────────────────
def get_wallet_address(agent_name: str) -> str | None:
    """Return the EVM wallet address stored in state for an agent."""
    return get_agent_state(agent_name).get("wallet_address")


def get_all_wallet_addresses() -> dict[str, str]:
    """Return {agent_name: evm_address} for agents that have a wallet address."""
    result: dict[str, str] = {}
    for name, state in get_all_agent_states().items():
        addr = state.get("wallet_address")
        if addr:
            result[name] = addr
    return result


# ── Online / health heuristic ──────────────────────────────────────────────────
def _stale_threshold_sec() -> float:
    """
    Derive the stale threshold from network.yaml heartbeat.timeout_blocks.
    Axon blocks are ~6 seconds each, so timeout_blocks * 6 gives the wall-clock
    window before the chain considers an agent jailed/offline.
    Defaults to 4320s (720 blocks × 6s) if config is unavailable.
    """
    try:
        hb_cfg = get_network_cfg().get("heartbeat", {})
        return float(hb_cfg.get("timeout_blocks", 720)) * 6.0
    except Exception:
        return 4320.0


def is_online(agent_state: dict[str, Any]) -> bool:
    """
    Heuristic: agent is online if service_active=True and last heartbeat
    is within the stale threshold.
    """
    if not agent_state.get("service_active", False):
        return False
    heartbeat_at = agent_state.get("heartbeat_at")
    if heartbeat_at is None:
        return False
    try:
        if isinstance(heartbeat_at, (int, float)):
            age = time.time() - float(heartbeat_at)
        else:
            dt = datetime.fromisoformat(str(heartbeat_at))
            age = time.time() - dt.timestamp()
        return age < _stale_threshold_sec()
    except Exception:
        return bool(agent_state.get("service_active", False))
