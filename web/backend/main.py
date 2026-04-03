"""
FastAPI application entry-point.

Authentication: every request (except GET /api/health) must carry the header
    X-API-Key: <AXON_API_TOKEN>
The token is read from the AXON_API_TOKEN environment variable at startup.
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from config import api_token
from routes import agents, challenge, daemons, operations

app = FastAPI(
    title="Axon Agent Dashboard",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# In production, set AXON_CORS_ORIGINS to your Cloudflare Tunnel domain:
#   AXON_CORS_ORIGINS=https://axon-dashboard.example.com
# Multiple origins can be separated by commas.
# Falls back to localhost only when the env var is absent (local dev).
_raw_origins = os.environ.get("AXON_CORS_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# ── Auth dependency ────────────────────────────────────────────────────────────
async def verify_token(request: Request) -> None:
    """Dependency that enforces X-API-Key on all non-health routes."""
    key = request.headers.get("X-API-Key", "")
    try:
        expected = api_token()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )


# ── Health (public) ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {"ok": True, "service": "axon-dashboard"}


# ── Protected routers ──────────────────────────────────────────────────────────
_auth = Depends(verify_token)

app.include_router(agents.router, prefix="/api", dependencies=[_auth])
app.include_router(challenge.router, prefix="/api", dependencies=[_auth])
app.include_router(daemons.router, prefix="/api", dependencies=[_auth])
app.include_router(operations.router, prefix="/api", dependencies=[_auth])
