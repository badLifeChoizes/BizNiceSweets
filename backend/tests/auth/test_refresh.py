"""
Token refresh tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-02 when POST /auth/refresh is implemented:
  CORE-03: Valid refresh cookie → new access_token returned; new refresh cookie set
  CORE-03: Missing refresh cookie → 401
  CORE-03: Revoked refresh token → 401

These tests are intentionally xfail until plan 02-02 wires the refresh endpoint.
"""
import pytest
import httpx


@pytest.mark.xfail(reason="POST /auth/refresh implemented in plan 02-02", strict=False)
async def test_token_refresh(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Valid refresh cookie returns new access_token and rotates refresh cookie."""
    # First log in to obtain a refresh cookie
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200

    # Use the refresh cookie to get a new access token
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    # New refresh cookie must be set (rotation)
    assert "refresh_token" in response.cookies


@pytest.mark.xfail(reason="POST /auth/refresh implemented in plan 02-02", strict=False)
async def test_refresh_missing_cookie(client: httpx.AsyncClient) -> None:
    """No refresh cookie → 401."""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


@pytest.mark.xfail(reason="POST /auth/refresh implemented in plan 02-02", strict=False)
async def test_refresh_revoked_token(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Revoked refresh token returns 401."""
    # Log in, then log out (revoke), then try to refresh
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200

    await client.post("/api/v1/auth/logout")

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
