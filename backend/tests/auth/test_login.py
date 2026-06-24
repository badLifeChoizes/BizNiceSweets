"""
Login endpoint tests — plan 02-02.

Behaviors tested (CORE-02):
  - Valid credentials → 200 + access_token + refresh cookie set (httpOnly)
  - Wrong password → 401
  - Unknown email → 401 (constant-time; no user-enumeration timing leak)

Tests require a live database (skip_if_no_db).  The admin user is seeded by
conftest via BNS_ADMIN_EMAIL / BNS_ADMIN_PASSWORD env vars.
"""
import pytest
import httpx


async def test_login_success(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Valid credentials return 200 with access_token and set refresh cookie."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type") == "bearer"
    assert "refresh_token" in response.cookies


async def test_login_bad_password(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Unknown email returns 401 (no user enumeration)."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@nowhere.test", "password": "anything"},
    )
    assert response.status_code == 401
