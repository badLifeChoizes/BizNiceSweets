"""
Health endpoint tests — Wave 0 harness.

Maps to CORE-01 (liveness, /docs reachable) and CORE-09 (readiness checks DB).

test_liveness: passes without a live database.
test_readiness: passes when a DB is reachable; skipped otherwise.
"""
import pytest
import httpx


async def test_liveness(client: httpx.AsyncClient) -> None:
    """GET /health/live returns 200 with status=ok (no DB required)."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


async def test_readiness(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """GET /health/ready returns 200 with db=connected when DB is available."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
