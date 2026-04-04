"""
Runtime configuration loader.

Reads configs/network.yaml and configs/agents.yaml from the project root.
Project root is resolved relative to this file: web/backend/ → ../../
Also optionally reads configs/runtime/local_env.md for per-machine overrides
(SSH key path, local repo root) but those aren't needed when running on-server.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
PROJECT_ROOT = (_HERE / ".." / "..").resolve()

NETWORK_YAML = PROJECT_ROOT / "configs" / "network.yaml"
AGENTS_YAML = PROJECT_ROOT / "configs" / "agents.yaml"
# The state file lives OUTSIDE the release directory (persists across deploys).
# Allow override via env var; default to the well-known stable path on the server.
_STATE_FILE_DEFAULT = PROJECT_ROOT / "state" / "deploy_state.json"
_STATE_FILE_ENV = os.environ.get("AXON_STATE_FILE")
STATE_FILE = Path(_STATE_FILE_ENV) if _STATE_FILE_ENV else _STATE_FILE_DEFAULT
LOCAL_ENV_MD = PROJECT_ROOT / "configs" / "runtime" / "local_env.md"


# ── YAML loaders ───────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_network_cfg() -> dict[str, Any]:
    with open(NETWORK_YAML) as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_agents_cfg() -> list[dict[str, Any]]:
    with open(AGENTS_YAML) as f:
        data = yaml.safe_load(f)
    return data.get("agents", [])


# ── Cosmos settings (convenience accessors) ────────────────────────────────────
def cosmos_cfg() -> dict[str, Any]:
    return get_network_cfg().get("cosmos", {})


def chain_id() -> str:
    return cosmos_cfg().get("chain_id", "axon_8210-1")


def rest_url() -> str:
    return cosmos_cfg().get("rest_url", "https://mainnet-api.axonchain.ai").rstrip("/")


def cometbft_rpc_url() -> str:
    return cosmos_cfg().get("cometbft_rpc_url", "https://mainnet-cometbft.axonchain.ai/").rstrip("/")


def keyring_dir() -> str:
    return cosmos_cfg().get("keyring_dir", "/home/ubuntu/.axond")


def keyring_backend() -> str:
    return cosmos_cfg().get("keyring_backend", "test")


def broadcast_mode() -> str:
    return cosmos_cfg().get("broadcast_mode", "sync")


def fees() -> str:
    return cosmos_cfg().get("fees", "300000000000000aaxon")


# ── local_env.md parser (optional, best-effort) ────────────────────────────────
def _parse_local_env() -> dict[str, str]:
    """Extract key→value pairs from the markdown table in local_env.md."""
    result: dict[str, str] = {}
    if not LOCAL_ENV_MD.exists():
        return result
    text = LOCAL_ENV_MD.read_text()
    for line in text.splitlines():
        # Match markdown table rows like: | SSH 密钥路径 | /path/to/key.pem |
        m = re.match(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if m:
            result[m.group(1).strip()] = m.group(2).strip()
    return result


@lru_cache(maxsize=1)
def local_env() -> dict[str, str]:
    return _parse_local_env()


# ── API token auth ─────────────────────────────────────────────────────────────
def api_token() -> str:
    token = os.environ.get("AXON_API_TOKEN", "")
    if not token:
        raise RuntimeError(
            "AXON_API_TOKEN environment variable is not set. "
            "Set it in the systemd unit or your shell before starting the server."
        )
    return token


# ── Validator metadata ─────────────────────────────────────────────────────────
VALIDATOR_VALOPER = "axonvaloper14xxu9g0fvnkclwt98yz9cldtwhpam560sgc8s0"
VALIDATOR_AGENT_NAME = "qqclaw-validator"


def evm_rpc_url() -> str:
    return get_network_cfg().get("rpc_url", "https://mainnet-rpc.axonchain.ai/").rstrip("/")


# Daemon service names
DAEMON_HEARTBEAT = "axon-heartbeat-daemon.service"
DAEMON_CHALLENGE = "axon-challenge-daemon.service"
DAEMON_COMPOUND = "axon-compound-daemon.service"
ALLOWED_DAEMONS = {DAEMON_HEARTBEAT, DAEMON_CHALLENGE, DAEMON_COMPOUND}
