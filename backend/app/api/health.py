"""
Health check endpoints.

GET /health/live  — liveness probe (no external I/O; returns 200 if process is alive)
GET /health/ready — readiness probe (checks DB connectivity; returns 503 if DB unreachable)

Threat mitigations:
  T-01-03: readiness uses parameterless text("SELECT 1") — no user input, no injection risk.
  T-01-04: DB failure returns a generic 503 detail string — no credentials/host internals leaked.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe: is the process alive? No external I/O."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe: can the process serve traffic? Checks DB connection."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        # T-01-04: generic message — do NOT expose connection details
        raise HTTPException(status_code=503, detail="Database unavailable")
