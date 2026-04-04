"""
cosmos_api.py — async helpers for querying the Axon Cosmos REST API.

All functions use a shared httpx.AsyncClient (connection reuse / keep-alive)
and an in-process 25-second TTL cache to avoid triggering HTTP 429 from the
public Axon REST API when 20 concurrent requests arrive per page refresh.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

import config as cfg

_TIMEOUT = 10.0  # seconds per request

# ── Shared AsyncClient (connection reuse) ──────────────────────────────────────
# Creating a new client per request establishes a fresh TLS connection each
# time. A module-level singleton reuses keep-alive connections, which both
# reduces latency and lowers the chance of triggering per-IP rate limits.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )
    return _client


# ── Simple in-process TTL cache ────────────────────────────────────────────────
# Caches individual balance and on-chain agent responses for 25 seconds.
# The frontend auto-refreshes every 30 seconds, so a 25s TTL means at most
# one real batch of requests per refresh cycle, regardless of how many browser
# tabs are open.  Keys are the URL path strings.
_cache: dict[str, tuple[float, Any]] = {}  # path → (expires_at, value)
_CACHE_TTL = 25.0  # seconds


def _cache_get(key: str) -> Any:
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[0]:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.monotonic() + _CACHE_TTL, value)


async def _get(path: str, cache: bool = False) -> dict[str, Any] | None:
    """GET {rest_url}{path} and return parsed JSON or None on error.

    When cache=True, results are served from the in-process TTL cache so
    repeated calls within _CACHE_TTL seconds skip the network entirely.
    """
    if cache:
        cached = _cache_get(path)
        if cached is not None:
            return cached

    url = f"{cfg.rest_url()}{path}"
    try:
        resp = await _get_client().get(url)
        resp.raise_for_status()
        data = resp.json()
        if cache:
            _cache_set(path, data)
        return data
    except Exception:
        return None


# ── EVM Registry precompile (stake queries) ────────────────────────────────────
# The stake data lives in the EVM precompile, not the Cosmos module, so it
# cannot be fetched from the Cosmos REST API. We use a raw eth_call POST
# to the EVM JSON-RPC endpoint — no web3 dependency needed.
_REGISTRY = "0x0000000000000000000000000000000000000801"
# keccak256("getStakeInfo(address)")[:4] — pre-computed, ABI is stable.
# Verification: keccak256(b"getStakeInfo(address)").hex()[:8] == "c3453153"
_GET_STAKE_SELECTOR = "c3453153"


async def _eth_call(to: str, data: str) -> str | None:
    """POST an eth_call JSON-RPC request; returns hex result string or None on error.

    Results are cached for _CACHE_TTL seconds so repeated page refreshes within
    the TTL window skip the network entirely.
    """
    cache_key = f"eth_call:{to}:{data}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": to, "data": f"0x{data}"}, "latest"],
            "id": 1,
        }
        resp = await _get_client().post(cfg.evm_rpc_url(), json=payload)
        resp.raise_for_status()
        result = resp.json().get("result")
        if result and result != "0x":
            _cache_set(cache_key, result)
        return result
    except Exception:
        return None


async def get_stake_axon(evm_address: str) -> float:
    """Return totalStake in AXON for evm_address via getStakeInfo on the Registry precompile.

    ABI: getStakeInfo(address) → (totalStake uint256, pendingReduce uint256, reduceUnlockHeight uint64)
    We decode only the first 32-byte word (totalStake) and convert from aaxon (1e18) to AXON.
    """
    addr_padded = evm_address.lower().removeprefix("0x").zfill(64)
    calldata = _GET_STAKE_SELECTOR + addr_padded
    result = await _eth_call(_REGISTRY, calldata)
    if not result or result == "0x":
        return 0.0
    try:
        return int(result.removeprefix("0x")[:64], 16) / 1e18
    except Exception:
        return 0.0


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
    Results are cached for _CACHE_TTL seconds.
    """
    data = await _get(f"/cosmos/bank/v1beta1/balances/{bech32_address}", cache=True)
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
    Results are cached for _CACHE_TTL seconds.
    """
    data = await _get(f"/axon/agent/v1/agent/{bech32_address}", cache=True)
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
