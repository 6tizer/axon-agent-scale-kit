"""
routes/agents.py — agent overview and validator status endpoints.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

import config as cfg
from services import cosmos_api, state_reader

router = APIRouter(tags=["agents"])


# ── /api/agents ────────────────────────────────────────────────────────────────
@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    """
    Return a list of all 10 configured agents with:
    - Local state (registered, staked, last heartbeat, service_active)
    - On-chain balance (from Cosmos REST, best-effort)
    - On-chain reputation (from Cosmos REST, best-effort)
    - Derived online status
    """
    agent_states = state_reader.get_all_agent_states()
    agents_cfg = cfg.get_agents_cfg()

    # Collect EVM addresses and convert to bech32 for balance queries
    evm_addresses: dict[str, str] = {}
    bech32_map: dict[str, str] = {}
    for name, state in agent_states.items():
        evm = state.get("wallet_address")
        if evm:
            evm_addresses[name] = evm
            bech32 = cosmos_api.evm_to_bech32(evm)
            if bech32:
                bech32_map[name] = bech32

    # Fetch balances and per-agent on-chain data concurrently.
    # Use per-agent /axon/agent/v1/agent/{addr} endpoint to avoid the 200-result
    # cap on the list endpoint.
    onchain_tasks = {name: cosmos_api.get_agent_onchain(bech32) for name, bech32 in bech32_map.items()}
    balances_result, *onchain_results = await asyncio.gather(
        cosmos_api.get_balances_batch(bech32_map),
        *onchain_tasks.values(),
    )
    balances = balances_result

    # Map our agents' on-chain data by agent name
    onchain_map: dict[str, dict] = {}
    for name, agent_data in zip(onchain_tasks.keys(), onchain_results):
        if agent_data:
            onchain_map[name] = agent_data

    items = []
    for agent_meta in agents_cfg:
        name = agent_meta["name"]
        state = agent_states.get(name, {})
        onchain = onchain_map.get(name, {})

        # Reputation: prefer on-chain (API returns string int e.g. "18"), fall back to state
        reputation = None
        if onchain:
            rep_val = onchain.get("reputation")
            if rep_val is not None:
                try:
                    reputation = int(rep_val)
                except (ValueError, TypeError):
                    reputation = rep_val
            if reputation is None:
                l1_val = onchain.get("l1_reputation")
                if l1_val is not None:
                    try:
                        reputation = int(l1_val)
                    except (ValueError, TypeError):
                        reputation = l1_val
        if reputation is None:
            reputation = state.get("reputation")

        items.append({
            "name": name,
            "is_validator": agent_meta.get("is_validator", False),
            "online": state_reader.is_online(state),
            "registered": bool(state.get("registered", False)),
            "staked": bool(state.get("staked", False)),
            "service_active": bool(state.get("service_active", False)),
            "wallet_address": state.get("wallet_address"),
            "bech32_address": bech32_map.get(name),
            "balance_axon": balances.get(name, 0.0),
            "reputation": reputation,
            "last_heartbeat_block": state.get("last_heartbeat_block"),
            "heartbeat_at": state.get("heartbeat_at"),
            "suspended": bool(state.get("suspended", False)),
        })

    return {"ok": True, "agents": items}


# ── /api/validator ──────────────────────────────────────────────────────────────
@router.get("/validator")
async def validator_status() -> dict[str, Any]:
    """
    Return qqclaw-validator's on-chain staking status.
    """
    validator = await cosmos_api.get_validator_status()
    if validator is None:
        return {"ok": False, "error": "could not fetch validator status"}
    return {"ok": True, "validator": validator}
