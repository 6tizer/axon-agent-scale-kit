"""
routes/operations.py — P1 write operations: transfer, stake, unjail.

All endpoints follow a two-step pattern:
  1. GET (or POST with dry_run=true) → returns dry_run_command for ConfirmDialog
  2. POST with confirmed=true → executes the command

The `confirmed` flag must be explicitly set to True in the request body.
"""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

import config as cfg
from services import axond_runner

router = APIRouter(tags=["operations"])


# ── Request models ─────────────────────────────────────────────────────────────
class TransferRequest(BaseModel):
    from_agent: str = Field(..., description="Agent name (must be a key in axond keyring)")
    to_address: str = Field(..., description="Target bech32 address (axon1...)")
    amount_axon: float = Field(..., gt=0, description="Amount in AXON (e.g. 1.5)")
    confirmed: bool = Field(default=False, description="Set true to execute; false returns dry-run only")

    @field_validator("to_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v.startswith("axon1") and not v.startswith("0x"):
            raise ValueError("to_address must be a bech32 (axon1...) or EVM (0x...) address")
        return v


class StakeRequest(BaseModel):
    agent_name: str = Field(..., description="Agent name (key in axond keyring)")
    amount_axon: float = Field(..., gt=0, description="Amount of AXON to stake")
    confirmed: bool = Field(default=False)


class UnjailRequest(BaseModel):
    confirmed: bool = Field(default=False)


# ── Helper ─────────────────────────────────────────────────────────────────────
def _axon_to_aaxon(amount_axon: float) -> int:
    """
    Convert AXON (float) to aaxon integer (1 AXON = 1e18 aaxon).
    Uses Decimal arithmetic to avoid IEEE-754 floating-point precision loss
    (e.g. 0.1 AXON → 100000000000000000, not 99999999999999984).
    """
    return int(Decimal(str(amount_axon)).scaleb(18).to_integral_value(rounding=ROUND_DOWN))


def _validate_agent_name(name: str) -> None:
    known = {a["name"] for a in cfg.get_agents_cfg()}
    if name not in known:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{name}'. Known agents: {sorted(known)}",
        )


# ── Transfer ───────────────────────────────────────────────────────────────────
@router.post("/transfer")
async def transfer(req: TransferRequest) -> dict[str, Any]:
    """
    Send AXON from an agent wallet to a target address.
    Set confirmed=false (default) to preview the command.
    Set confirmed=true to execute.
    """
    _validate_agent_name(req.from_agent)
    amount_aaxon = _axon_to_aaxon(req.amount_axon)
    dry_cmd = axond_runner.dry_run_bank_send(req.from_agent, req.to_address, amount_aaxon)

    if not req.confirmed:
        return {
            "ok": True,
            "dry_run": True,
            "dry_run_command": dry_cmd,
            "message": "Set confirmed=true to execute this command.",
        }

    result = await axond_runner.run_bank_send_async(req.from_agent, req.to_address, amount_aaxon)
    return {
        "ok": result.ok,
        "dry_run": False,
        "dry_run_command": dry_cmd,
        "tx_hash": result.tx_hash,
        "error": result.error,
        "raw_output": result.raw_output,
    }


# ── Stake ──────────────────────────────────────────────────────────────────────
@router.post("/stake")
async def add_stake(req: StakeRequest) -> dict[str, Any]:
    """
    Add stake to an agent via `axond tx agent add-stake`.
    Set confirmed=false (default) to preview the command.
    Set confirmed=true to execute.
    """
    _validate_agent_name(req.agent_name)
    amount_aaxon = _axon_to_aaxon(req.amount_axon)
    dry_cmd = axond_runner.dry_run_add_stake(req.agent_name, amount_aaxon)

    if not req.confirmed:
        return {
            "ok": True,
            "dry_run": True,
            "dry_run_command": dry_cmd,
            "message": "Set confirmed=true to execute this command.",
        }

    result = await axond_runner.run_add_stake_async(req.agent_name, amount_aaxon)
    return {
        "ok": result.ok,
        "dry_run": False,
        "dry_run_command": dry_cmd,
        "tx_hash": result.tx_hash,
        "error": result.error,
        "raw_output": result.raw_output,
    }


# ── Unjail ────────────────────────────────────────────────────────────────────
@router.post("/unjail")
async def unjail(req: UnjailRequest) -> dict[str, Any]:
    """
    Send unjail TX for qqclaw-validator.
    Set confirmed=false (default) to preview the command.
    Set confirmed=true to execute.
    """
    dry_cmd = axond_runner.dry_run_unjail()

    if not req.confirmed:
        return {
            "ok": True,
            "dry_run": True,
            "dry_run_command": dry_cmd,
            "message": "Set confirmed=true to execute this command.",
        }

    result = await axond_runner.run_unjail_async()
    return {
        "ok": result.ok,
        "dry_run": False,
        "dry_run_command": dry_cmd,
        "tx_hash": result.tx_hash,
        "error": result.error,
        "raw_output": result.raw_output,
    }
