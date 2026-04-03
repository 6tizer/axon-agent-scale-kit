"""
routes/daemons.py — daemon status and restart endpoints.
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from fastapi import APIRouter, HTTPException

import config as cfg

router = APIRouter(tags=["daemons"])

_DAEMONS = [cfg.DAEMON_HEARTBEAT, cfg.DAEMON_CHALLENGE]


def _systemctl_is_active(service: str) -> str:
    """Return 'active', 'inactive', 'failed', or 'unknown'."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _run_cmd(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Synchronous wrapper for subprocess.run — call via asyncio.to_thread."""
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


@router.get("/daemons")
async def list_daemons() -> dict[str, Any]:
    """Return active/inactive status for both daemons."""
    # _systemctl_is_active is fast (<100ms), but still offload to avoid blocking
    statuses = await asyncio.gather(
        *[asyncio.to_thread(_systemctl_is_active, name) for name in _DAEMONS]
    )
    items = [{"name": name, "status": status} for name, status in zip(_DAEMONS, statuses)]
    return {"ok": True, "daemons": items}


@router.post("/daemons/{daemon_name}/restart")
async def restart_daemon(daemon_name: str) -> dict[str, Any]:
    """
    Restart a daemon via `sudo systemctl restart {name}`.
    The ubuntu user must have a sudoers entry allowing this without a password:
        ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart axon-heartbeat-daemon.service
        ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart axon-challenge-daemon.service
    """
    if daemon_name not in cfg.ALLOWED_DAEMONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown daemon '{daemon_name}'. Allowed: {sorted(cfg.ALLOWED_DAEMONS)}",
        )
    try:
        r = await asyncio.to_thread(
            _run_cmd, ["sudo", "systemctl", "restart", daemon_name], 30
        )
        if r.returncode != 0:
            return {
                "ok": False,
                "daemon": daemon_name,
                "error": r.stderr or r.stdout,
            }
        await asyncio.sleep(1)
        status = await asyncio.to_thread(_systemctl_is_active, daemon_name)
        return {"ok": True, "daemon": daemon_name, "status": status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/daemons/{daemon_name}/logs")
async def daemon_logs(daemon_name: str, lines: int = 50) -> dict[str, Any]:
    """Return recent journal logs for a daemon."""
    if daemon_name not in cfg.ALLOWED_DAEMONS:
        raise HTTPException(status_code=400, detail=f"Unknown daemon '{daemon_name}'")
    try:
        r = await asyncio.to_thread(
            _run_cmd, ["journalctl", "-u", daemon_name, "-n", str(lines), "--no-pager"], 10
        )
        return {"ok": True, "daemon": daemon_name, "logs": r.stdout}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
