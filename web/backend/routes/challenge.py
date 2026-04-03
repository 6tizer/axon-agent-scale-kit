"""
routes/challenge.py — challenge history endpoint.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services import state_reader

router = APIRouter(tags=["challenge"])


@router.get("/challenge/history")
async def challenge_history(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    """
    Return the last `limit` challenge-related events from state.events,
    newest first.
    """
    events = state_reader.get_challenge_history(limit=limit)
    return {"ok": True, "events": events, "count": len(events)}
