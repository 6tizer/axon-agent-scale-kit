"""
cosmos_api.py — async helpers for querying the Axon Cosmos REST API.

All functions use httpx.AsyncClient and are safe to call from FastAPI
async route handlers.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

import config as cfg

_TIMEOUT = 10.0  # seconds


async def _get(path: str) -> dict[str, Any] | None:
    """GET {rest_url}{path} and return parsed JSON or None on error."""
    url = f"{cfg.rest_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


# ── Validator ───────────────────────────────────────────────────────────────────
async def get_validator_status() -> dict[str, Any] | None:
    """
    Query /cosmos/staking/v1beta1/validators/{valoper}.
    Returns a simplified dict:
        moniker, status, jailed, tokens_axon, commission_rate, valoper
    or None on failure.
    """
    data = await _get(f"/cosmos/staking/v1beta1/validators/{cfg.VALIDATOR_VALOPER}")
    if not data or "validator" not in data:
        return None
    v = data["validator"]
    try:
        tokens_axon = int(v.get("tokens", 0)) / 1e18
    except (ValueError, TypeError):
        tokens_axon = 0.0
    return {
        "moniker": v.get("description", {}).get("moniker", ""),
        "status": v.get("status", ""),
        "jailed": bool(v.get("jailed", False)),
        "tokens_axon": tokens_axon,
        "commission_rate": v.get("commission", {}).get("commission_rates", {}).get("rate", "0"),
        "valoper": cfg.VALIDATOR_VALOPER,
    }


# ── Balances ────────────────────────────────────────────────────────────────────
async def get_balance_axon(bech32_address: str) -> float:
    """
    Query /cosmos/bank/v1beta1/balances/{addr}.
    Returns the AXON balance as a float (converted from aaxon), or 0.0.
    """
    data = await _get(f"/cosmos/bank/v1beta1/balances/{bech32_address}")
    if not data:
        return 0.0
    for coin in data.get("balances", []):
        denom = coin.get("denom", "")
        if denom in ("aaxon", "axon"):
            try:
                raw = int(coin["amount"])
                return raw / 1e18 if denom == "aaxon" else float(raw)
            except (ValueError, KeyError):
                pass
    return 0.0


async def get_balances_batch(addresses: dict[str, str]) -> dict[str, float]:
    """
    Fetch balances for multiple agents concurrently.
    addresses: {agent_name: bech32_address}
    Returns: {agent_name: balance_axon}
    """
    results: dict[str, float] = {}
    tasks = {name: get_balance_axon(addr) for name, addr in addresses.items()}
    resolved = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for name, result in zip(tasks.keys(), resolved):
        results[name] = float(result) if isinstance(result, (int, float)) else 0.0
    return results


# ── Agent on-chain info ────────────────────────────────────────────────────────
async def get_agent_onchain(bech32_address: str) -> dict[str, Any] | None:
    """
    Fetch a single registered agent from /axon/agent/v1/agent/{addr}.
    Uses the singular per-agent endpoint to avoid the 200-result cap on the
    list endpoint (/axon/agent/v1/agents).
    Returns the agent dict or None if not found / on error.
    """
    data = await _get(f"/axon/agent/v1/agent/{bech32_address}")
    if not data:
        return None
    return data.get("agent") or None


# ── EVM → bech32 conversion (pure Python, no subprocess) ──────────────────────
# Standard Cosmos bech32 encoding — same algorithm as the Go SDK.

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: bytes, frombits: int, tobits: int) -> list[int] | None:
    acc, bits, ret = 0, 0, []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def evm_to_bech32(evm_address: str, hrp: str = "axon") -> str | None:
    """
    Convert a 0x EVM address to an axon1... bech32 address without subprocess.
    Pure Python — safe to call from an async context.
    """
    try:
        hex_addr = evm_address.lower().removeprefix("0x")
        if len(hex_addr) != 40:
            return None
        addr_bytes = bytes.fromhex(hex_addr)
        converted = _convertbits(addr_bytes, 8, 5)
        if converted is None:
            return None
        checksum = _bech32_create_checksum(hrp, converted)
        return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in converted + checksum)
    except Exception:
        return None


# ── Current block ──────────────────────────────────────────────────────────────
async def get_current_block() -> int | None:
    """Return the latest block height from the Cosmos REST API."""
    data = await _get("/cosmos/base/tendermint/v1beta1/blocks/latest")
    if not data:
        return None
    try:
        return int(data["block"]["header"]["height"])
    except (KeyError, TypeError, ValueError):
        return None
